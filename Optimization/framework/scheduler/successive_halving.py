from __future__ import annotations

"""Optuna-based scheduler for Successive Halving / Hyperband meta-runs."""

import json
import logging
import shutil
from copy import deepcopy
from dataclasses import asdict
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List

import numpy as np
import pandas as pd

from Settings import get_settings
from Optimization.framework.hypervolume import (
    build_hv_summary,
    compute_hv,
    hv_mode,
    resolve_reference_point,
    zero_hv_fraction,
)
from Optimization.framework.Orchestrator.optimize import run
from Optimization.run.analysis import csv_exports
from Optimization.run.analysis import run_metrics

logger = logging.getLogger(__name__)


def _field(obj: Any, key: str, default: Any = None) -> Any:
    """Read scheduler-arm fields from dataclass objects or plain dicts."""
    if isinstance(obj, dict):
        return obj.get(key, default)
    return getattr(obj, key, default)


def _merge_dict(base: Dict[str, Any], extra: Dict[str, Any]) -> Dict[str, Any]:
    out = deepcopy(base)
    for k, v in (extra or {}).items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = _merge_dict(out[k], v)
        else:
            out[k] = deepcopy(v)
    return out


def _arm_overrides(arm: Any) -> Dict[str, Any]:
    features = dict(_field(arm, "features", {}) or {})
    bounds_override = dict(_field(arm, "bounds_override", {}) or {})
    caps_override = dict(_field(arm, "caps_override", {}) or {})
    delta_t = _field(arm, "delta_t_override", None)
    members_override = _field(arm, "members_override", None)
    tariff_arm = _field(arm, "tariff_arm", None)

    out: Dict[str, Any] = {}
    if features:
        out.setdefault("engine", {}).setdefault("features", {}).update(features)
    if bounds_override:
        out.setdefault("bounds", {}).update(bounds_override)
    if caps_override:
        out.setdefault("bounds", {}).setdefault("caps", {}).update(caps_override)
    if delta_t is not None:
        out.setdefault("thermal", {})["delta_T"] = float(delta_t)
    if members_override is not None:
        out.setdefault("technical", {})["members"] = members_override
    if tariff_arm is not None:
        out.setdefault("market", {})["active_tariff_arm"] = str(tariff_arm)
    return out


def _constraints_active(constraint_names: List[str]) -> bool:
    return bool(list(constraint_names or []))


def _feasible_mask_from_g(F: np.ndarray, G: np.ndarray | None, constraints_active: bool) -> np.ndarray:
    """Compute feasibility mask with strict guards when constraints are active."""
    if not constraints_active:
        return np.ones(F.shape[0], dtype=bool)
    if G is None:
        raise RuntimeError("[scheduler] G_opt.npy missing but constraints are active.")
    if G.ndim == 1:
        G = G.reshape(1, -1)
    if G.shape[0] != F.shape[0]:
        raise RuntimeError(
            f"[scheduler] Shape mismatch between F and G: F rows={F.shape[0]}, G rows={G.shape[0]}."
        )
    return np.all(G <= 0.0, axis=1)


def _feasible_mask_from_selected_constraints(
    F: np.ndarray,
    G: np.ndarray | None,
    run_constraint_names: List[str],
    scoring_constraints: List[str],
    require_scoring_constraints_present: bool,
) -> np.ndarray:
    """Compute feasibility using configured scoring constraints (settings-driven)."""
    # Empty selection => use run-specific active constraints.
    if not scoring_constraints:
        return _feasible_mask_from_g(F, G, constraints_active=bool(run_constraint_names))

    if G is None:
        raise RuntimeError("[scheduler] G_opt.npy missing but scoring_constraints are configured.")
    if G.ndim == 1:
        G = G.reshape(1, -1)
    if G.shape[0] != F.shape[0]:
        raise RuntimeError(
            f"[scheduler] Shape mismatch between F and G: F rows={F.shape[0]}, G rows={G.shape[0]}."
        )

    idx_by_name = {str(n): i for i, n in enumerate(run_constraint_names)}
    missing = [str(n) for n in scoring_constraints if str(n) not in idx_by_name]
    if missing and require_scoring_constraints_present:
        raise RuntimeError(
            f"[scheduler] Run is missing required scoring constraints: {missing}. "
            f"Available: {run_constraint_names}"
        )
    selected_idx = [idx_by_name[str(n)] for n in scoring_constraints if str(n) in idx_by_name and idx_by_name[str(n)] < G.shape[1]]
    if not selected_idx:
        # If none are available and strict mode is off, treat as unconstrained for scoring.
        return np.ones(F.shape[0], dtype=bool)
    return np.all(G[:, selected_idx] <= 0.0, axis=1)


def _load_fg(run_dir: str) -> tuple[np.ndarray, np.ndarray | None]:
    """Load F/G matrices from a run directory with stable 2D shapes."""
    f_path = Path(run_dir) / "F_opt.npy"
    g_path = Path(run_dir) / "G_opt.npy"
    if not f_path.exists():
        raise FileNotFoundError(f"[scheduler] Missing F_opt.npy in run_dir={run_dir}")
    F = np.asarray(np.load(f_path), dtype=float)
    if F.ndim == 1:
        F = F.reshape(1, -1)
    G = None
    if g_path.exists():
        G = np.asarray(np.load(g_path), dtype=float)
        if G.ndim == 1:
            G = G.reshape(1, -1)
    return F, G


def _load_objective_names_from_results(run_dir: str) -> List[str]:
    """Read objective names from run results metadata (preferred) with safe fallbacks."""
    results_path = Path(run_dir) / "results.json"
    if not results_path.exists():
        return []
    try:
        payload = json.loads(results_path.read_text(encoding="utf-8"))
    except Exception:
        return []
    metadata = payload.get("metadata", {}) if isinstance(payload, dict) else {}
    names = metadata.get("objective_names", []) if isinstance(metadata, dict) else []
    if isinstance(names, list) and names:
        return [str(x) for x in names]
    legacy = payload.get("objectives", []) if isinstance(payload, dict) else []
    if isinstance(legacy, list) and legacy:
        return [str(x) for x in legacy]
    return []


def _load_constraints_from_results(run_dir: str) -> Dict[str, List[Any]]:
    """Read constraint names/senses/rhs from results metadata when available."""
    out: Dict[str, List[Any]] = {"names": [], "senses": [], "rhs": []}
    results_path = Path(run_dir) / "results.json"
    if not results_path.exists():
        return out
    try:
        payload = json.loads(results_path.read_text(encoding="utf-8"))
    except Exception:
        return out
    if not isinstance(payload, dict):
        return out
    metadata = payload.get("metadata", {})
    if isinstance(metadata, dict):
        cmeta = metadata.get("constraints", {})
        if isinstance(cmeta, dict):
            names = cmeta.get("names", [])
            senses = cmeta.get("senses", [])
            rhs = cmeta.get("rhs", [])
            if isinstance(names, list):
                out["names"] = [str(x) for x in names]
            if isinstance(senses, list):
                out["senses"] = [str(x) for x in senses]
            if isinstance(rhs, list):
                out["rhs"] = [float(x) for x in rhs]
    if not out["names"]:
        legacy_names = payload.get("constraints", [])
        if isinstance(legacy_names, list):
            out["names"] = [str(x) for x in legacy_names]
    return out


def _load_feasibility_from_results(run_dir: str) -> Dict[str, Any]:
    """Read feasibility gate metadata from run results when available."""
    results_path = Path(run_dir) / "results.json"
    if not results_path.exists():
        return {}
    try:
        payload = json.loads(results_path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    if not isinstance(payload, dict):
        return {}
    metadata = payload.get("metadata", {})
    if not isinstance(metadata, dict):
        return {}
    feasibility = metadata.get("feasibility", {})
    return feasibility if isinstance(feasibility, dict) else {}


def _feasible_mask_from_gate_labels(
    F: np.ndarray,
    labels: List[Any],
    ranking_mode: str,
    source: str,
) -> np.ndarray:
    """Translate gate labels into a scheduler feasibility mask."""
    F = np.asarray(F, dtype=float)
    if F.ndim == 1:
        F = F.reshape(1, -1)
    as_list = [str(x) for x in list(labels or [])]
    if len(as_list) != F.shape[0]:
        raise RuntimeError(
            f"[scheduler] Feasibility labels from {source} do not match F rows: "
            f"labels={len(as_list)} vs F rows={F.shape[0]}."
        )

    mode = str(ranking_mode or "lexicographic").strip().lower()
    if mode in {"lexicographic", "hard_filter"}:
        allowed = {"feasible", "verified_feasible"}
    elif mode == "penalty":
        allowed = {"feasible", "verified_feasible", "uncertain"}
    else:
        raise RuntimeError(f"[scheduler] Unsupported feasibility.ranking_mode='{ranking_mode}'.")
    return np.asarray([lbl in allowed for lbl in as_list], dtype=bool)


def _resolve_scheduler_feasible_mask(
    *,
    base_settings: Any,
    run_dir: str,
    scoring_run_dir: str,
    F: np.ndarray,
    G: np.ndarray | None,
    run_constraint_names: List[str],
    scoring_constraints: List[str],
    require_scoring_constraints_present: bool,
) -> tuple[np.ndarray, List[str], str]:
    """Resolve the scheduler feasibility mask from gate metadata or strict G logic."""
    feasibility_cfg = getattr(base_settings, "feasibility", None)
    if feasibility_cfg is None or not bool(getattr(feasibility_cfg, "enabled", False)):
        mask = _feasible_mask_from_selected_constraints(
            F=F,
            G=G,
            run_constraint_names=run_constraint_names,
            scoring_constraints=scoring_constraints,
            require_scoring_constraints_present=require_scoring_constraints_present,
        )
        labels = ["feasible" if bool(x) else "infeasible" for x in mask.tolist()]
        return mask, labels, "constraints"

    ranking_mode = str(getattr(feasibility_cfg, "ranking_mode", "lexicographic"))
    candidate_sources: List[tuple[str, str]] = []
    if scoring_run_dir:
        candidate_sources.append((str(scoring_run_dir), "scoring_run"))
    if run_dir and str(run_dir) != str(scoring_run_dir):
        candidate_sources.append((str(run_dir), "primary_run"))

    for candidate_dir, source_name in candidate_sources:
        feasibility_meta = _load_feasibility_from_results(candidate_dir)
        labels = list(feasibility_meta.get("labels", []) or [])
        if not labels:
            continue
        mask = _feasible_mask_from_gate_labels(
            F=F,
            labels=labels,
            ranking_mode=ranking_mode,
            source=f"{source_name}:{candidate_dir}",
        )
        return mask, [str(x) for x in labels], source_name

    raise RuntimeError(
        "[scheduler] Feasibility gate is enabled, but no gate labels were found in run results. "
        "The scheduler refuses to fall back to raw constraint checks in this mode."
    )


def _append_stage_records(
    *,
    stage_log: List[Dict[str, Any]],
    pareto_rows: List[Dict[str, Any]],
    trial_no: int,
    arm_name: str,
    step_idx: int,
    budget: int,
    run_dir: str,
    F: np.ndarray,
    G: np.ndarray | None,
    feasible_mask: np.ndarray,
    feasibility_labels: List[str],
    feasibility_source: str,
    run_constraint_names: List[str],
    hv_value: float,
) -> None:
    n_pareto = int(F.shape[0])
    f_min = np.min(F, axis=0) if n_pareto else np.asarray([])
    f_median = np.median(F, axis=0) if n_pareto else np.asarray([])
    n_feasible = int(np.sum(feasible_mask)) if feasible_mask.size else 0
    feasible_ratio = float(n_feasible / n_pareto) if n_pareto > 0 else 0.0
    stage_log.append(
        {
            "trial": int(trial_no),
            "arm": arm_name,
            "stage_index": int(step_idx),
            "budget_n_gen": int(budget),
            "run_dir": run_dir,
            "status": "running",
            "hv": float(hv_value),
            "n_pareto": n_pareto,
            "n_feasible": n_feasible,
            "feasible_ratio": feasible_ratio,
            "feasibility_source": str(feasibility_source),
            "f0_min": float(f_min[0]) if f_min.size >= 1 else None,
            "f1_min": float(f_min[1]) if f_min.size >= 2 else None,
            "f0_median": float(f_median[0]) if f_median.size >= 1 else None,
            "f1_median": float(f_median[1]) if f_median.size >= 2 else None,
        }
    )
    for i in range(F.shape[0]):
        row = {
            "trial": int(trial_no),
            "arm": arm_name,
            "stage_index": int(step_idx),
            "point_index": int(i),
            "budget_n_gen": int(budget),
            "run_dir": run_dir,
            "f0": float(F[i, 0]) if F.shape[1] >= 1 else None,
            "f1": float(F[i, 1]) if F.shape[1] >= 2 else None,
            "feasible": bool(feasible_mask[i]) if feasible_mask.size else None,
            "feasibility_label": str(feasibility_labels[i]) if i < len(feasibility_labels) else None,
            "feasibility_source": str(feasibility_source),
        }
        if G is not None and G.size:
            for j, c_name in enumerate(run_constraint_names):
                row[f"G_{c_name}"] = float(G[i, j]) if G.shape[1] > j else None
        pareto_rows.append(row)


def _validated_constraint_triplet(names: List[Any], senses: List[Any], rhs: List[Any], source: str) -> tuple[List[str], List[str], List[float]]:
    n = [str(x) for x in (names or [])]
    s = [str(x) for x in (senses or [])]
    r = [float(x) for x in (rhs or [])]
    if not (len(n) == len(s) == len(r)):
        raise ValueError(
            f"Constraint metadata length mismatch from {source}: "
            f"len(names)={len(n)}, len(senses)={len(s)}, len(rhs)={len(r)}"
        )
    return n, s, r


def _select_active_constraints(
    settings_names: List[Any],
    settings_senses: List[Any],
    settings_rhs: List[Any],
    results_constraints: Dict[str, List[Any]] | None,
) -> tuple[List[str], List[str], List[float], str]:
    set_n, set_s, set_r = _validated_constraint_triplet(settings_names, settings_senses, settings_rhs, source="settings")
    rc = results_constraints or {}
    res_names = list(rc.get("names", []) or [])
    res_senses = list(rc.get("senses", []) or [])
    res_rhs = list(rc.get("rhs", []) or [])
    # Use results.json only if full aligned triplet is present.
    if res_names and res_senses and res_rhs:
        res_n, res_s, res_r = _validated_constraint_triplet(res_names, res_senses, res_rhs, source="results.json")
        return res_n, res_s, res_r, "results.json"
    return set_n, set_s, set_r, "settings"


def _build_constraints_report(
    final_df: pd.DataFrame,
    constraint_names: List[str],
    constraint_senses: List[str],
    constraint_rhs: List[float],
    active_constraints_source: str,
) -> Dict[str, Any]:
    constraint_names, constraint_senses, constraint_rhs = _validated_constraint_triplet(
        constraint_names,
        constraint_senses,
        constraint_rhs,
        source=active_constraints_source,
    )
    report: Dict[str, Any] = {
        "active_constraints_source": str(active_constraints_source),
        "active_constraints": {
            "names": [str(x) for x in constraint_names],
            "senses": [str(x) for x in constraint_senses],
            "rhs": [float(x) for x in constraint_rhs],
        },
        "missing_constraints": [],
        "is_complete": True,
        "final_stage": {
            "n_points_total": int(final_df.shape[0]),
            "n_points_feasible": 0,
            "feasible_ratio": 0.0,
            "by_arm": {},
        },
    }
    by_arm: Dict[str, Any] = {}
    g_cols = {name: f"G_{name}" for name in constraint_names}
    available_constraints: List[str] = []
    missing_constraints: List[str] = []
    if final_df.shape[0] > 0 and constraint_names:
        for c_name in constraint_names:
            g_col = g_cols[c_name]
            if g_col not in final_df.columns:
                missing_constraints.append(c_name)
                continue
            vals = pd.to_numeric(final_df[g_col], errors="coerce")
            if vals.isna().any():
                missing_constraints.append(c_name)
                continue
            available_constraints.append(c_name)
        if missing_constraints:
            logger.warning(
                "[scheduler] constraints_report incomplete. Missing/NaN constraint columns for: %s",
                ", ".join(missing_constraints),
            )
    report["missing_constraints"] = missing_constraints
    report["is_complete"] = len(missing_constraints) == 0

    if final_df.shape[0] > 0:
        if available_constraints:
            available_cols = [g_cols[name] for name in available_constraints]
            feasible_mask = (final_df[available_cols] <= 0.0).all(axis=1)
            report["final_stage"]["n_points_feasible"] = int(feasible_mask.sum())
            report["final_stage"]["feasible_ratio"] = float(feasible_mask.mean())
        elif not constraint_names:
            report["final_stage"]["n_points_feasible"] = int(final_df.shape[0])
            report["final_stage"]["feasible_ratio"] = 1.0
    if "arm" not in final_df.columns:
        report["final_stage"]["by_arm"] = by_arm
        return report
    for arm_name, grp in final_df.groupby("arm", dropna=False):
        arm_key = str(arm_name)
        n_total = int(grp.shape[0])
        if available_constraints:
            available_cols = [g_cols[name] for name in available_constraints]
            n_feasible = int((grp[available_cols] <= 0.0).all(axis=1).sum())
        elif not constraint_names:
            n_feasible = n_total
        else:
            n_feasible = 0
        arm_payload = {
            "n_total": n_total,
            "n_feasible": n_feasible,
            "feasible_ratio": float(n_feasible / n_total) if n_total > 0 else 0.0,
            "mean_violation_by_constraint": {},
            "max_violation_by_constraint": {},
        }
        for c_name in constraint_names:
            g_col = g_cols[c_name]
            if c_name in missing_constraints:
                arm_payload["mean_violation_by_constraint"][g_col] = None
                arm_payload["max_violation_by_constraint"][g_col] = None
                continue
            vals = pd.to_numeric(grp[g_col], errors="coerce").to_numpy(dtype=float)
            viol = np.maximum(vals, 0.0)
            arm_payload["mean_violation_by_constraint"][g_col] = float(np.mean(viol)) if viol.size else 0.0
            arm_payload["max_violation_by_constraint"][g_col] = float(np.max(viol)) if viol.size else 0.0
        by_arm[arm_key] = arm_payload
    report["final_stage"]["by_arm"] = by_arm
    return report


def _save_final_meta_pareto_plot(
    out_dir: Path,
    pareto_csv_name: str,
    n_gen_max: int,
    objective_names: List[str],
) -> str | None:
    """Create a single final-stage meta Pareto plot from pareto_aggregate.csv."""
    try:
        import matplotlib
        matplotlib.use("Agg", force=True)
        import matplotlib.pyplot as plt
    except Exception:
        return None

    csv_path = out_dir / pareto_csv_name
    if not csv_path.exists():
        return None

    df = pd.read_csv(csv_path)
    if df.empty or "budget_n_gen" not in df.columns:
        return None

    df = df[df["budget_n_gen"] == int(n_gen_max)]
    if "feasible" in df.columns:
        feasible = df["feasible"]
        if feasible.dtype == bool:
            mask = feasible
        else:
            mask = feasible.astype(str).str.lower().isin({"true", "1", "yes"})
        df = df[mask]
    if df.empty or "f0" not in df.columns or "f1" not in df.columns:
        return None

    x_label = str(objective_names[0]) if len(objective_names) >= 1 else "f0"
    y_label = str(objective_names[1]) if len(objective_names) >= 2 else "f1"
    color_key = "arm" if "arm" in df.columns else None

    fig, ax = plt.subplots(figsize=(9, 6))
    if color_key is None:
        ax.scatter(df["f0"], df["f1"], s=18, alpha=0.8)
    else:
        for name, grp in df.groupby(color_key, dropna=False):
            ax.scatter(grp["f0"], grp["f1"], s=18, alpha=0.8, label=str(name))
        ax.legend(loc="best", fontsize=8, frameon=True)

    ax.set_xlabel(x_label)
    ax.set_ylabel(y_label)
    ax.set_title("Meta Pareto Front (Final Stage)")
    ax.grid(True, alpha=0.3)
    fig.tight_layout()

    plot_name = "pareto_meta.png"
    fig.savefig(out_dir / plot_name, dpi=150)
    plt.close(fig)
    return plot_name


def _save_all_stage_meta_plot(
    out_dir: Path,
    pareto_csv_name: str,
    n_gen_max: int,
    objective_names: List[str],
) -> str | None:
    """Create a second meta plot with all stage points plus final-stage overlay."""
    try:
        import matplotlib
        matplotlib.use("Agg", force=True)
        import matplotlib.pyplot as plt
    except Exception:
        return None

    csv_path = out_dir / pareto_csv_name
    if not csv_path.exists():
        return None

    df = pd.read_csv(csv_path)
    if df.empty or "budget_n_gen" not in df.columns or "f0" not in df.columns or "f1" not in df.columns:
        return None

    if "feasible" in df.columns:
        feasible = df["feasible"]
        if feasible.dtype == bool:
            mask = feasible
        else:
            mask = feasible.astype(str).str.lower().isin({"true", "1", "yes"})
        df = df[mask]
    if df.empty:
        return None

    final_df = df[df["budget_n_gen"] == int(n_gen_max)].copy()
    early_df = df[df["budget_n_gen"] < int(n_gen_max)].copy()

    x_label = str(objective_names[0]) if len(objective_names) >= 1 else "f0"
    y_label = str(objective_names[1]) if len(objective_names) >= 2 else "f1"

    fig, ax = plt.subplots(figsize=(9, 6))
    if not early_df.empty:
        budgets = sorted(set(int(x) for x in early_df["budget_n_gen"].dropna().tolist()))
        cmap = plt.get_cmap("Greys")
        n_b = max(1, len(budgets))
        for i, budget in enumerate(budgets):
            grp = early_df[early_df["budget_n_gen"] == budget]
            shade = 0.35 + (0.45 * (i / max(1, n_b - 1)))
            ax.scatter(
                grp["f0"],
                grp["f1"],
                s=10,
                alpha=0.45,
                color=cmap(shade),
                label=f"stage n_gen={budget}",
            )
    if not final_df.empty:
        if "arm" in final_df.columns:
            for name, grp in final_df.groupby("arm", dropna=False):
                ax.scatter(grp["f0"], grp["f1"], s=20, alpha=0.9, label=f"final {name}")
        else:
            ax.scatter(final_df["f0"], final_df["f1"], s=20, alpha=0.9, color="tab:blue", label="final")

    ax.set_xlabel(x_label)
    ax.set_ylabel(y_label)
    ax.set_title("Meta Pareto Front (All Stages + Final Overlay)")
    ax.grid(True, alpha=0.3)
    ax.legend(loc="best", fontsize=7, frameon=True, ncol=2)
    fig.tight_layout()

    plot_name = "pareto_meta_all_stages.png"
    fig.savefig(out_dir / plot_name, dpi=150)
    plt.close(fig)
    return plot_name


def _sanitize_sheet_name(name: str, used: set[str]) -> str:
    invalid = '[]:*?/\\'
    clean = "".join("_" if ch in invalid else ch for ch in str(name or "arm"))
    clean = clean[:31] if len(clean) > 31 else clean
    if not clean:
        clean = "arm"
    base = clean
    i = 1
    while clean in used:
        suffix = f"_{i}"
        clean = (base[: 31 - len(suffix)] + suffix) if len(base) + len(suffix) > 31 else (base + suffix)
        i += 1
    used.add(clean)
    return clean


def _build_arm_ranking(trials_log: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    best_by_arm: Dict[str, Dict[str, Any]] = {}
    for row in trials_log:
        arm = str(row.get("arm", ""))
        if not arm:
            continue
        hv = float(row.get("hv", 0.0))
        prev = best_by_arm.get(arm)
        if prev is None or hv > float(prev.get("hv", float("-inf"))):
            best_by_arm[arm] = {
                "arm": arm,
                "trial": int(row.get("trial", -1)),
                "status": str(row.get("status", "")),
                "hv": hv,
            }
    ranked = sorted(best_by_arm.values(), key=lambda x: (-float(x["hv"]), str(x["arm"])))
    for i, row in enumerate(ranked, start=1):
        row["rank"] = int(i)
    return ranked


def _load_design_var_names(run_dir: str, fallback: List[str]) -> List[str]:
    results_path = Path(run_dir) / "results.json"
    if not results_path.exists():
        return list(fallback)
    try:
        payload = json.loads(results_path.read_text(encoding="utf-8"))
    except Exception:
        return list(fallback)
    if not isinstance(payload, dict):
        return list(fallback)
    metadata = payload.get("metadata", {})
    candidates = []
    if isinstance(metadata, dict):
        for key in ("decision_names", "feature_names", "var_names"):
            v = metadata.get(key, [])
            if isinstance(v, list) and v:
                candidates = [str(x) for x in v]
                break
    if not candidates:
        bounds_meta = payload.get("bounds", {})
        if isinstance(bounds_meta, dict):
            bnames = bounds_meta.get("names", [])
            if isinstance(bnames, list) and bnames:
                candidates = [str(x) for x in bnames]
    return candidates or list(fallback)


def _build_pareto_designs_final_df(
    pareto_df: pd.DataFrame,
    n_gen_max: int,
    default_var_names: List[str],
) -> pd.DataFrame:
    if pareto_df.empty or "budget_n_gen" not in pareto_df.columns:
        return pd.DataFrame()
    final_df = pareto_df[pareto_df["budget_n_gen"] == int(n_gen_max)].copy()
    if final_df.empty:
        return final_df

    run_cache: Dict[str, Dict[str, Any]] = {}
    for run_dir in sorted(set(final_df["run_dir"].dropna().astype(str))):
        x_path = Path(run_dir) / "X_opt.npy"
        if not x_path.exists():
            run_cache[run_dir] = {"X": None, "var_names": list(default_var_names)}
            continue
        X = np.asarray(np.load(x_path), dtype=float)
        if X.ndim == 1:
            X = X.reshape(1, -1)
        run_cache[run_dir] = {"X": X, "var_names": _load_design_var_names(run_dir, fallback=default_var_names)}

    for idx, row in final_df.iterrows():
        run_dir = str(row.get("run_dir", ""))
        point_index = row.get("point_index", None)
        if run_dir not in run_cache or point_index is None:
            continue
        try:
            i = int(point_index)
        except Exception:
            continue
        X = run_cache[run_dir]["X"]
        var_names = list(run_cache[run_dir]["var_names"])
        if X is None or i < 0 or i >= X.shape[0]:
            for name in var_names:
                final_df.at[idx, name] = None
            continue
        for j, name in enumerate(var_names):
            final_df.at[idx, name] = float(X[i, j]) if j < X.shape[1] else None

    return final_df


def _write_pareto_designs_excel(out_dir: Path, final_designs_df: pd.DataFrame) -> tuple[str | None, str | None]:
    if final_designs_df.empty:
        return None, None
    excel_name = "pareto_designs_final.xlsx"
    csv_name = "pareto_designs_final_excel.csv"
    with pd.ExcelWriter(out_dir / excel_name, engine="openpyxl") as writer:
        final_designs_df.to_excel(writer, sheet_name="all", index=False)
        used = {"all"}
        if "arm" in final_designs_df.columns:
            for arm_name, grp in final_designs_df.groupby("arm", dropna=False):
                sheet = _sanitize_sheet_name(str(arm_name), used=used)
                grp.to_excel(writer, sheet_name=sheet, index=False)
    final_designs_df.to_csv(out_dir / csv_name, index=False)
    return excel_name, csv_name


def _aggregate_final_run_csv_by_arm(
    *,
    final_stage_runs: List[Dict[str, Any]],
    out_dir: Path,
    source_filename: str,
    excel_name: str,
    flat_csv_name: str,
) -> tuple[str | None, str | None, int]:
    by_arm: Dict[str, List[pd.DataFrame]] = {}
    for rec in final_stage_runs:
        run_dir = str(rec.get("run_dir", ""))
        arm_name = str(rec.get("arm", "arm"))
        src_path = Path(run_dir) / source_filename
        if not src_path.exists():
            continue
        try:
            df = pd.read_csv(src_path)
        except Exception:
            continue
        if df.empty:
            continue
        df.insert(0, "run_dir", run_dir)
        df.insert(1, "trial", int(rec.get("trial", -1)))
        df.insert(2, "stage_index", int(rec.get("stage_index", -1)))
        df.insert(3, "budget_n_gen", int(rec.get("budget_n_gen", -1)))
        df.insert(4, "arm", arm_name)
        by_arm.setdefault(arm_name, []).append(df)

    if not by_arm:
        return None, None, 0

    used: set[str] = set()
    flat_parts: List[pd.DataFrame] = []
    with pd.ExcelWriter(out_dir / excel_name, engine="openpyxl") as writer:
        for arm_name in sorted(by_arm.keys()):
            arm_df = pd.concat(by_arm[arm_name], ignore_index=True)
            sheet = _sanitize_sheet_name(str(arm_name), used=used)
            arm_df.to_excel(writer, sheet_name=sheet, index=False)
            flat_parts.append(arm_df)
    flat_df = pd.concat(flat_parts, ignore_index=True)
    flat_df.to_csv(out_dir / flat_csv_name, index=False)
    return excel_name, flat_csv_name, int(flat_df.shape[0])


def _select_export_runs(
    *,
    final_stage_runs: List[Dict[str, Any]],
    trials_log: List[Dict[str, Any]],
    outputs_cfg: Any,
) -> List[Dict[str, Any]]:
    mode = str(_field(outputs_cfg, "final_export_arm_mode", "top_k")).lower().strip()
    if mode == "none":
        return []
    if mode == "all":
        return list(final_stage_runs)

    best_by_arm: Dict[str, float] = {}
    for rec in trials_log:
        arm = str(rec.get("arm", ""))
        hv = float(rec.get("hv", 0.0) or 0.0)
        if arm and (arm not in best_by_arm or hv > best_by_arm[arm]):
            best_by_arm[arm] = hv

    if mode == "list":
        wanted = {str(x) for x in (_field(outputs_cfg, "final_export_arm_names", []) or [])}
        return [rec for rec in final_stage_runs if str(rec.get("arm", "")) in wanted]

    top_k = max(0, int(_field(outputs_cfg, "final_export_top_k_arms", 3)))
    ranked = sorted(best_by_arm.items(), key=lambda kv: kv[1], reverse=True)
    wanted = {arm for arm, _hv in ranked[:top_k]}
    return [rec for rec in final_stage_runs if str(rec.get("arm", "")) in wanted]


def _export_timeseries_for_selected_runs(
    *,
    selected_runs: List[Dict[str, Any]],
    base_overrides: Dict[str, Any] | None,
    arms: List[Any],
    arm_names: List[str],
    n_gen_max: int,
    max_points_per_arm: int,
) -> None:
    if not selected_runs:
        return
    arm_lookup = {str(_field(arm, "name", f"arm_{i}")): arm for i, arm in enumerate(arms)}
    for rec in selected_runs:
        arm_name = str(rec.get("arm", ""))
        run_dir = str(rec.get("run_dir", ""))
        arm = arm_lookup.get(arm_name)
        if not arm or not run_dir:
            continue
        x_path = Path(run_dir) / "X_opt.npy"
        if not x_path.exists():
            continue
        X = np.asarray(np.load(x_path), dtype=float)
        if X.ndim == 1:
            X = X.reshape(1, -1)
        arm_ovr = _arm_overrides(arm)
        ovr = _merge_dict(base_overrides or {}, arm_ovr)
        ovr = _merge_dict(
            ovr,
            {
                "optimizer": {"kwargs": {"n_gen": int(n_gen_max)}},
                "reporting": {
                    "write_csv": True,
                    "write_timeseries": True,
                    "timeseries_max_points": int(max_points_per_arm),
                    "write_plot": False,
                    "write_summary": False,
                },
            },
        )
        settings = get_settings(overrides=ovr)
        csv_exports.export_load_flows_timeseries(
            run_dir=run_dir,
            settings=settings,
            X_opt=X,
            max_points=int(max_points_per_arm),
        )


def _build_consistency_report(
    *,
    out_dir: Path,
    final_designs_df: pd.DataFrame,
    loadflows_csv_name: str | None,
) -> Dict[str, Any]:
    report: Dict[str, Any] = {
        "enabled": True,
        "status": "skipped",
        "reason": "",
        "n_points_joined": 0,
        "autarky_abs_diff_mean": None,
        "autarky_abs_diff_p95": None,
        "autarky_abs_diff_max": None,
        "n_autarky_diff_gt_0p01": 0,
        "n_autarky_diff_gt_0p05": 0,
        "n_suspicious_pv0_h2_big_no_h2_flow": 0,
        "csv": None,
    }
    if final_designs_df is None or final_designs_df.empty:
        report["reason"] = "final_designs_df empty"
        return report
    if not loadflows_csv_name:
        report["reason"] = "loadflows csv missing"
        return report
    lf_path = out_dir / str(loadflows_csv_name)
    if not lf_path.exists():
        report["reason"] = f"missing file: {lf_path.name}"
        return report

    needed = {"arm", "point_index", "autarky", "pv_kwp", "bess_kwh", "ely_kw", "h2_tank_kwh", "fc_kw", "f0", "f1"}
    if not needed.issubset(set(final_designs_df.columns)):
        report["reason"] = "required columns missing in final_designs_df"
        return report

    use_cols = [
        "arm",
        "point_idx",
        "grid_import",
        "total_load",
        "pv_generation",
        "h2_charge_elec",
        "h2_discharge_elec",
    ]
    lf = pd.read_csv(lf_path, usecols=use_cols)
    if lf.empty:
        report["reason"] = "loadflows empty"
        return report

    agg = (
        lf.groupby(["arm", "point_idx"], as_index=False)
        .sum(numeric_only=True)
        .rename(columns={"point_idx": "point_index"})
    )

    d = final_designs_df.copy()
    d["point_index"] = pd.to_numeric(d["point_index"], errors="coerce")
    merged = d.merge(agg, on=["arm", "point_index"], how="inner")
    if merged.empty:
        report["reason"] = "no join rows between final_designs and loadflows"
        return report

    merged["autarky_from_flows"] = 1.0 - (
        pd.to_numeric(merged["grid_import"], errors="coerce")
        / pd.to_numeric(merged["total_load"], errors="coerce").clip(lower=1e-9)
    )
    merged["autarky_abs_diff"] = (
        pd.to_numeric(merged["autarky"], errors="coerce")
        - pd.to_numeric(merged["autarky_from_flows"], errors="coerce")
    ).abs()

    suspicious = (
        (pd.to_numeric(merged["pv_kwp"], errors="coerce") <= 1e-3)
        & (
            (pd.to_numeric(merged["ely_kw"], errors="coerce") >= 50.0)
            | (pd.to_numeric(merged["h2_tank_kwh"], errors="coerce") >= 500.0)
            | (pd.to_numeric(merged["fc_kw"], errors="coerce") >= 150.0)
            | (pd.to_numeric(merged["bess_kwh"], errors="coerce") >= 500.0)
        )
        & (pd.to_numeric(merged["h2_charge_elec"], errors="coerce") <= 1e-6)
        & (pd.to_numeric(merged["h2_discharge_elec"], errors="coerce") <= 1e-6)
    )
    merged["suspicious_pv0_h2_big_no_h2_flow"] = suspicious.astype(int)

    out_csv = "consistency_checks_final.csv"
    merged.sort_values(["autarky_abs_diff", "f1"], ascending=[False, True]).to_csv(out_dir / out_csv, index=False)

    report.update(
        {
            "status": "ok",
            "reason": "",
            "n_points_joined": int(merged.shape[0]),
            "autarky_abs_diff_mean": float(pd.to_numeric(merged["autarky_abs_diff"], errors="coerce").mean()),
            "autarky_abs_diff_p95": float(pd.to_numeric(merged["autarky_abs_diff"], errors="coerce").quantile(0.95)),
            "autarky_abs_diff_max": float(pd.to_numeric(merged["autarky_abs_diff"], errors="coerce").max()),
            "n_autarky_diff_gt_0p01": int((pd.to_numeric(merged["autarky_abs_diff"], errors="coerce") > 0.01).sum()),
            "n_autarky_diff_gt_0p05": int((pd.to_numeric(merged["autarky_abs_diff"], errors="coerce") > 0.05).sum()),
            "n_suspicious_pv0_h2_big_no_h2_flow": int(merged["suspicious_pv0_h2_big_no_h2_flow"].sum()),
            "csv": out_csv,
        }
    )
    return report


def run_scheduler(base_overrides: Dict[str, Any] | None = None) -> Dict[str, Any]:
    t_scheduler_start = datetime.now()
    try:
        import optuna
        from optuna.exceptions import TrialPruned
        from optuna.pruners import HyperbandPruner, SuccessiveHalvingPruner
    except Exception as exc:
        raise RuntimeError("[scheduler] Optuna is required when scheduler.enabled=True.") from exc

    base_settings = get_settings(overrides=base_overrides or {})
    sched = getattr(base_settings, "scheduler", None)
    if sched is None or not bool(getattr(sched, "enabled", False)):
        raise RuntimeError("[scheduler] scheduler.enabled must be True for run_scheduler().")
    hv_mode_name = hv_mode(base_settings)

    arms = list(getattr(sched, "arms", []) or [])
    if not arms:
        raise ValueError("[scheduler] scheduler.arms must contain at least one arm.")
    constraint_names = list(getattr(getattr(base_settings, "constraints", None), "names", []) or [])
    constraint_senses = list(getattr(getattr(base_settings, "constraints", None), "senses", []) or [])
    constraint_rhs = [float(x) for x in (getattr(getattr(base_settings, "constraints", None), "rhs", []) or [])]
    scoring_constraints = [str(x) for x in (getattr(sched, "scoring_constraints", []) or [])]
    require_scoring_constraints_present = bool(getattr(sched, "require_scoring_constraints_present", True))
    default_var_names = list(getattr(getattr(base_settings, "bounds", None), "names", []) or [])
    if not default_var_names:
        default_var_names = ["pv_kwp", "bess_kwh", "ely_kw", "h2_tank_kwh", "fc_kw"]

    n_gen_max = int(getattr(getattr(base_settings, "optimizer", None), "kwargs", {}).get("n_gen", 0))
    if n_gen_max <= 0:
        raise ValueError("[scheduler] optimizer.kwargs.n_gen must be > 0.")
    min_resource = int(getattr(sched, "min_resource", 1))
    reduction = int(getattr(sched, "reduction_factor", 3))
    budgets = []
    b = min_resource
    while b < n_gen_max:
        budgets.append(int(b))
        b *= max(2, reduction)
    budgets.append(int(n_gen_max))

    if str(getattr(sched, "pruner", "successive_halving")).lower() == "hyperband":
        pruner = HyperbandPruner(min_resource=min_resource, max_resource=n_gen_max, reduction_factor=max(2, reduction))
    else:
        pruner = SuccessiveHalvingPruner(min_resource=min_resource, reduction_factor=max(2, reduction), min_early_stopping_rate=0)

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_dir = Path("Optimization") / "run" / "scheduler" / f"meta_{ts}"
    out_dir.mkdir(parents=True, exist_ok=True)

    arm_names = [str(_field(a, "name", f"arm_{i}")) for i, a in enumerate(arms)]
    trials_log: List[Dict[str, Any]] = []
    stage_log: List[Dict[str, Any]] = []
    pareto_rows: List[Dict[str, Any]] = []
    objective_names: List[str] = []
    cleanup_candidates: List[str] = []
    final_stage_runs: List[Dict[str, Any]] = []
    constraints_from_results: Dict[str, List[Any]] = {"names": [], "senses": [], "rhs": []}
    sched_outputs = _field(sched, "outputs", None)
    cleanup_nonfinal_runs = bool(_field(sched_outputs, "cleanup_nonfinal_runs", bool(getattr(sched, "enabled", False))))
    cleanup_final_runs = bool(_field(sched_outputs, "cleanup_final_runs", bool(getattr(sched, "enabled", False))))
    aggregate_final_loadflows_by_arm = bool(_field(sched_outputs, "aggregate_final_loadflows_by_arm", True))
    aggregate_final_ghg_debug_by_arm = bool(_field(sched_outputs, "aggregate_final_ghg_debug_by_arm", True))
    use_gold_for_final_scoring = bool(getattr(sched, "use_gold_for_final_scoring", False))
    n_trials = int(getattr(sched, "n_trials", 0)) or len(arms)
    seed = int(getattr(sched, "seed", 42))
    unique_once = bool(getattr(sched, "unique_arms_once", True))
    if hv_mode_name == "auto_from_warmup" and not (unique_once and n_trials <= len(arm_names)):
        raise ValueError(
            "[scheduler] hypervolume.mode='auto_from_warmup' currently requires unique_arms_once=True "
            "and n_trials <= number of configured arms."
        )
    resolved_ref_point = None
    hv_source = "unresolved"
    warmup_cache: Dict[str, Dict[str, Any]] = {}

    if hv_mode_name == "fixed":
        resolved_ref_point = resolve_reference_point(base_settings, n_obj=len(getattr(base_settings.objectives, "names", []) or []))
        hv_source = "settings.fixed"

    def _run_stage(arm_name: str, arm_idx: int, arm: Any, step_idx: int, budget: int, trial_no: int) -> Dict[str, Any]:
        nonlocal constraints_from_results, resolved_ref_point
        arm_ovr = _arm_overrides(arm)
        ovr = _merge_dict(base_overrides or {}, arm_ovr)
        is_final_stage = int(budget) == int(n_gen_max)
        ovr = _merge_dict(
            ovr,
            {
                "optimizer": {"kwargs": {"n_gen": int(budget)}},
                "reporting": {
                    "write_csv": bool(is_final_stage),
                    "write_summary": bool(is_final_stage),
                    "write_plot": bool(is_final_stage),
                    "write_timeseries": False,
                },
            },
        )
        settings = get_settings(overrides=ovr)
        runtime_meta = {
            "arm": {
                "arm_id": int(arm_idx),
                "arm_name": arm_name,
                "arm_overrides": arm_ovr,
                "budget_n_gen": int(budget),
                "stage_index": int(step_idx),
                "is_final_stage": bool(is_final_stage),
            }
        }
        res = run(settings, runtime_meta=runtime_meta)
        run_dir = str(res["run_dir"])
        scoring_run_dir = run_dir
        if use_gold_for_final_scoring and is_final_stage:
            ovr_gold = deepcopy(ovr)
            ovr_gold.setdefault("engine", {})["name"] = "gold"
            settings_gold = get_settings(overrides=ovr_gold)
            runtime_meta_gold = deepcopy(runtime_meta)
            runtime_meta_gold["scheduler_temp_gold_scoring"] = True
            res_gold = run(settings_gold, runtime_meta=runtime_meta_gold)
            scoring_run_dir = str(res_gold["run_dir"])

        if not objective_names:
            objective_names.extend(_load_objective_names_from_results(scoring_run_dir))
        if not constraints_from_results["names"]:
            constraints_from_results = _load_constraints_from_results(scoring_run_dir)
        run_constraints = _load_constraints_from_results(scoring_run_dir)
        run_constraint_names = [str(x) for x in (run_constraints.get("names", []) or [])]
        F, G = _load_fg(scoring_run_dir)
        feasible_mask, feasibility_labels, feasibility_source = _resolve_scheduler_feasible_mask(
            base_settings=base_settings,
            run_dir=run_dir,
            scoring_run_dir=scoring_run_dir,
            F=F,
            G=G,
            run_constraint_names=run_constraint_names,
            scoring_constraints=scoring_constraints,
            require_scoring_constraints_present=require_scoring_constraints_present,
        )
        if hv_mode_name == "auto_from_seen":
            resolved_ref_point = resolve_reference_point(
                settings=base_settings,
                n_obj=F.shape[1],
                F_seen=F,
                feasible_mask=feasible_mask,
                current_ref_point=resolved_ref_point,
            )
        hv_value = compute_hv(F, feasible_mask=feasible_mask, ref_point=resolved_ref_point)
        return {
            "arm_overrides": arm_ovr,
            "run_dir": run_dir,
            "scoring_run_dir": scoring_run_dir,
            "F": F,
            "G": G,
            "feasible_mask": feasible_mask,
            "feasibility_labels": feasibility_labels,
            "feasibility_source": feasibility_source,
            "run_constraint_names": run_constraint_names,
            "hv": hv_value,
            "is_final_stage": is_final_stage,
            "trial_no": int(trial_no),
            "step_idx": int(step_idx),
            "budget": int(budget),
        }

    if hv_mode_name == "auto_from_warmup":
        warmup_stage_index = int(getattr(getattr(base_settings, "hypervolume", None), "warmup_stage_index", 0))
        if warmup_stage_index < 0 or warmup_stage_index >= len(budgets):
            raise ValueError(
                f"[scheduler] hypervolume.warmup_stage_index={warmup_stage_index} is out of range for budgets={budgets}."
            )
        warmup_budget = int(budgets[warmup_stage_index])
        warmup_F_rows: List[np.ndarray] = []
        warmup_mask_rows: List[np.ndarray] = []
        for arm_idx, arm_name in enumerate(arm_names):
            arm = arms[arm_idx]
            stage_res = _run_stage(arm_name=arm_name, arm_idx=arm_idx, arm=arm, step_idx=warmup_stage_index, budget=warmup_budget, trial_no=arm_idx)
            warmup_cache[arm_name] = stage_res
            warmup_F_rows.append(stage_res["F"])
            warmup_mask_rows.append(stage_res["feasible_mask"])
        F_seen = np.vstack(warmup_F_rows) if warmup_F_rows else np.zeros((0, len(objective_names) or len(getattr(base_settings.objectives, "names", []) or [])), float)
        feasible_seen = np.concatenate(warmup_mask_rows) if warmup_mask_rows else np.zeros((0,), dtype=bool)
        resolved_ref_point = resolve_reference_point(
            settings=base_settings,
            n_obj=int(F_seen.shape[1]) if F_seen.ndim == 2 and F_seen.shape[1] > 0 else len(getattr(base_settings.objectives, "names", []) or []),
            F_seen=F_seen,
            feasible_mask=feasible_seen,
            current_ref_point=None,
        )
        hv_source = f"warmup_stage_{warmup_stage_index}"
        for arm_idx, arm_name in enumerate(arm_names):
            stage_res = warmup_cache[arm_name]
            stage_res["hv"] = compute_hv(stage_res["F"], feasible_mask=stage_res["feasible_mask"], ref_point=resolved_ref_point)
            _append_stage_records(
                stage_log=stage_log,
                pareto_rows=pareto_rows,
                trial_no=arm_idx,
                arm_name=arm_name,
                step_idx=stage_res["step_idx"],
                budget=stage_res["budget"],
                run_dir=stage_res["scoring_run_dir"],
                F=stage_res["F"],
                G=stage_res["G"],
                feasible_mask=stage_res["feasible_mask"],
                feasibility_labels=stage_res["feasibility_labels"],
                feasibility_source=stage_res["feasibility_source"],
                run_constraint_names=stage_res["run_constraint_names"],
                hv_value=stage_res["hv"],
            )
            if not stage_res["is_final_stage"] and cleanup_nonfinal_runs:
                cleanup_candidates.append(stage_res["run_dir"])
            if stage_res["is_final_stage"]:
                final_stage_runs.append(
                    {
                        "trial": int(arm_idx),
                        "arm": arm_name,
                        "stage_index": int(stage_res["step_idx"]),
                        "budget_n_gen": int(stage_res["budget"]),
                        "run_dir": stage_res["scoring_run_dir"],
                    }
                )

    def objective(trial):
        nonlocal constraints_from_results
        arm_name = trial.suggest_categorical("arm", arm_names)
        arm_idx = arm_names.index(arm_name)
        arm = arms[arm_idx]
        hv_last = 0.0
        run_dirs: List[str] = []
        start_step_idx = 0
        if arm_name in warmup_cache:
            cached = warmup_cache[arm_name]
            hv_last = float(cached["hv"])
            run_dirs.append(str(cached["run_dir"]))
            if str(cached["scoring_run_dir"]) != str(cached["run_dir"]):
                run_dirs.append(str(cached["scoring_run_dir"]))
            trial.report(hv_last, int(cached["budget"]))
            if trial.should_prune():
                for row in reversed(stage_log):
                    if int(row.get("trial", -1)) == int(arm_idx) and str(row.get("arm", "")) == arm_name:
                        row["trial"] = int(trial.number)
                        row["status"] = "pruned"
                        break
                trials_log.append({"trial": int(trial.number), "arm": arm_name, "status": "pruned", "hv": hv_last, "run_dirs": run_dirs})
                raise TrialPruned()
            start_step_idx = int(cached["step_idx"]) + 1

        for step_idx in range(start_step_idx, len(budgets)):
            budget = int(budgets[step_idx])
            stage_res = _run_stage(arm_name=arm_name, arm_idx=arm_idx, arm=arm, step_idx=step_idx, budget=budget, trial_no=int(trial.number))
            hv_last = float(stage_res["hv"])
            run_dirs.append(str(stage_res["run_dir"]))
            if str(stage_res["scoring_run_dir"]) != str(stage_res["run_dir"]):
                run_dirs.append(str(stage_res["scoring_run_dir"]))
            if not stage_res["is_final_stage"] and cleanup_nonfinal_runs:
                cleanup_candidates.append(stage_res["run_dir"])
            if stage_res["is_final_stage"]:
                final_stage_runs.append(
                    {
                        "trial": int(trial.number),
                        "arm": arm_name,
                        "stage_index": int(step_idx),
                        "budget_n_gen": int(budget),
                        "run_dir": stage_res["scoring_run_dir"],
                    }
                )
            _append_stage_records(
                stage_log=stage_log,
                pareto_rows=pareto_rows,
                trial_no=int(trial.number),
                arm_name=arm_name,
                step_idx=step_idx,
                budget=budget,
                run_dir=stage_res["scoring_run_dir"],
                F=stage_res["F"],
                G=stage_res["G"],
                feasible_mask=stage_res["feasible_mask"],
                feasibility_labels=stage_res["feasibility_labels"],
                feasibility_source=stage_res["feasibility_source"],
                run_constraint_names=stage_res["run_constraint_names"],
                hv_value=hv_last,
            )
            trial.report(hv_last, int(budget))
            if trial.should_prune():
                if stage_log:
                    stage_log[-1]["status"] = "pruned"
                trials_log.append({"trial": int(trial.number), "arm": arm_name, "status": "pruned", "hv": hv_last, "run_dirs": run_dirs})
                raise TrialPruned()

        if stage_log:
            stage_log[-1]["status"] = "complete"
        trials_log.append({"trial": int(trial.number), "arm": arm_name, "status": "complete", "hv": hv_last, "run_dirs": run_dirs})
        return hv_last

    def _study_progress_callback(study, trial) -> None:
        trial_arm = str(trial.params.get("arm", "unknown"))
        trial_value = float(trial.value) if trial.value is not None else float("nan")
        best_trial = getattr(study, "best_trial", None)
        best_arm = str(best_trial.params.get("arm", "unknown")) if best_trial is not None else "unknown"
        best_value = float(getattr(study, "best_value", float("nan")))
        print(
            f"[scheduler] trial={int(trial.number)} arm={trial_arm} hv={trial_value:.6g} | "
            f"best_trial={int(best_trial.number) if best_trial is not None else -1} "
            f"best_arm={best_arm} best_hv={best_value:.6g}"
        )

    sampler = optuna.samplers.TPESampler(seed=seed)
    study = optuna.create_study(direction="maximize", pruner=pruner, sampler=sampler)
    if unique_once and n_trials <= len(arm_names):
        for arm_name in arm_names[:n_trials]:
            study.enqueue_trial({"arm": arm_name})
    study.optimize(objective, n_trials=n_trials, callbacks=[_study_progress_callback])

    stage_log_name = "stage_log.csv"
    pareto_aggregate_name = "pareto_aggregate.csv"
    stage_log_df = pd.DataFrame(stage_log)
    pareto_df = pd.DataFrame(pareto_rows)
    active_names, active_senses, active_rhs, active_source = _select_active_constraints(
        settings_names=constraint_names,
        settings_senses=constraint_senses,
        settings_rhs=constraint_rhs,
        results_constraints=constraints_from_results,
    )
    if scoring_constraints:
        rhs_map = {str(constraint_names[i]): float(constraint_rhs[i]) for i in range(min(len(constraint_names), len(constraint_rhs)))}
        sense_map = {str(constraint_names[i]): str(constraint_senses[i]) for i in range(min(len(constraint_names), len(constraint_senses)))}
        active_names = [str(n) for n in scoring_constraints]
        active_senses = [str(sense_map.get(str(n), "<=")) for n in active_names]
        active_rhs = [float(rhs_map.get(str(n), 0.0)) for n in active_names]
        active_source = "scheduler.scoring_constraints"
    if "autarky_min" in active_names:
        aut_idx = active_names.index("autarky_min")
        rhs_autarky = float(active_rhs[aut_idx]) if len(active_rhs) > aut_idx else None
        g_col = "G_autarky_min"
        if rhs_autarky is not None and g_col in pareto_df.columns:
            pareto_df["autarky"] = rhs_autarky - pd.to_numeric(pareto_df[g_col], errors="coerce")
    stage_log_df.to_csv(out_dir / stage_log_name, index=False)
    pareto_df.to_csv(out_dir / pareto_aggregate_name, index=False)
    final_stage_df = pareto_df[pareto_df["budget_n_gen"] == int(n_gen_max)].copy() if not pareto_df.empty and "budget_n_gen" in pareto_df.columns else pd.DataFrame()
    final_designs_df = _build_pareto_designs_final_df(
        pareto_df=pareto_df,
        n_gen_max=n_gen_max,
        default_var_names=default_var_names,
    )
    designs_excel_name = None
    designs_csv_name = None
    try:
        designs_excel_name, designs_csv_name = _write_pareto_designs_excel(out_dir=out_dir, final_designs_df=final_designs_df)
    except Exception as exc:
        logger.warning("[scheduler] failed to write pareto designs excel (best-effort): %s", exc)
    loadflows_excel_name = None
    loadflows_csv_name = None
    loadflows_rows = 0
    ghg_debug_excel_name = None
    ghg_debug_csv_name = None
    ghg_debug_rows = 0
    selected_export_runs = _select_export_runs(
        final_stage_runs=final_stage_runs,
        trials_log=trials_log,
        outputs_cfg=sched_outputs,
    )
    max_points_per_arm = int(_field(sched_outputs, "final_export_max_points_per_arm", 5))
    if selected_export_runs and (aggregate_final_loadflows_by_arm or aggregate_final_ghg_debug_by_arm):
        _export_timeseries_for_selected_runs(
            selected_runs=selected_export_runs,
            base_overrides=base_overrides,
            arms=arms,
            arm_names=arm_names,
            n_gen_max=n_gen_max,
            max_points_per_arm=max_points_per_arm,
        )
    if aggregate_final_loadflows_by_arm:
        try:
            loadflows_excel_name, loadflows_csv_name, loadflows_rows = _aggregate_final_run_csv_by_arm(
                final_stage_runs=selected_export_runs,
                out_dir=out_dir,
                source_filename="load_flows_timeseries.csv",
                excel_name="loadflows_final_by_arm.xlsx",
                flat_csv_name="loadflows_final_by_arm.csv",
            )
        except Exception as exc:
            logger.warning("[scheduler] failed to aggregate final loadflows by arm (best-effort): %s", exc)
    if aggregate_final_ghg_debug_by_arm:
        try:
            ghg_debug_excel_name, ghg_debug_csv_name, ghg_debug_rows = _aggregate_final_run_csv_by_arm(
                final_stage_runs=selected_export_runs,
                out_dir=out_dir,
                source_filename="ghg_debug_by_point.csv",
                excel_name="ghg_debug_final_by_arm.xlsx",
                flat_csv_name="ghg_debug_final_by_arm.csv",
            )
        except Exception as exc:
            logger.warning("[scheduler] failed to aggregate final ghg debug by arm (best-effort): %s", exc)

    summary = {
        "timestamp": ts,
        "scheduler": asdict(sched),
        "hypervolume": build_hv_summary(base_settings, resolved_ref_point=resolved_ref_point, source=hv_source),
        "budgets_n_gen": budgets,
        "objective_names": objective_names,
        "constraints_report": None,
        "best_trial": int(study.best_trial.number) if study.best_trial is not None else None,
        "best_arm": study.best_trial.params.get("arm") if study.best_trial is not None else None,
        "best_hv": float(study.best_value) if study.best_trial is not None else None,
        "arm_ranking": _build_arm_ranking(trials_log),
        "trials": trials_log,
        "stage_log_csv": stage_log_name,
        "pareto_aggregate_csv": pareto_aggregate_name,
        "pareto_designs_excel": designs_excel_name,
        "pareto_designs_excel_csv": designs_csv_name,
        "pareto_meta_plot": None,
        "pareto_meta_all_stages_plot": None,
        "n_pareto_total": int(len(pareto_rows)),
        "outputs_policy": {
            "timeseries_final_only": True,
            "pareto_plot_final_only": True,
            "use_gold_for_final_scoring": bool(use_gold_for_final_scoring),
            "cleanup_nonfinal_runs": cleanup_nonfinal_runs,
            "cleanup_final_runs": cleanup_final_runs,
            "aggregate_final_loadflows_by_arm": aggregate_final_loadflows_by_arm,
            "aggregate_final_ghg_debug_by_arm": aggregate_final_ghg_debug_by_arm,
            "final_export_arm_mode": str(_field(sched_outputs, "final_export_arm_mode", "top_k")),
            "final_export_top_k_arms": int(_field(sched_outputs, "final_export_top_k_arms", 3)),
            "final_export_arm_names": list(_field(sched_outputs, "final_export_arm_names", []) or []),
            "final_export_max_points_per_arm": int(max_points_per_arm),
            "selected_export_arms": [str(r.get("arm", "")) for r in selected_export_runs],
            "cleaned_nonfinal_run_dirs": 0,
            "cleaned_final_run_dirs": 0,
        },
        "loadflows_final_by_arm_excel": loadflows_excel_name,
        "loadflows_final_by_arm_csv": loadflows_csv_name,
        "loadflows_final_rows": int(loadflows_rows),
        "ghg_debug_final_by_arm_excel": ghg_debug_excel_name,
        "ghg_debug_final_by_arm_csv": ghg_debug_csv_name,
        "ghg_debug_final_rows": int(ghg_debug_rows),
        "consistency_report": None,
    }
    if bool(getattr(getattr(base_settings, "hypervolume", None), "require_positive_contributions", False)):
        zero_frac = zero_hv_fraction([float(t.get("hv", 0.0)) for t in trials_log])
        summary["hypervolume"]["zero_hv_fraction"] = float(zero_frac)
        warn_threshold = float(getattr(getattr(base_settings, "hypervolume", None), "zero_hv_fraction_warn_threshold", 0.25))
        summary["hypervolume"]["zero_hv_fraction_warn_threshold"] = float(warn_threshold)
        summary["hypervolume"]["zero_hv_fraction_warned"] = bool(zero_frac > warn_threshold)
    summary["pareto_meta_plot"] = _save_final_meta_pareto_plot(
        out_dir=out_dir,
        pareto_csv_name=pareto_aggregate_name,
        n_gen_max=n_gen_max,
        objective_names=list(summary.get("objective_names", []) or []),
    )
    summary["pareto_meta_all_stages_plot"] = _save_all_stage_meta_plot(
        out_dir=out_dir,
        pareto_csv_name=pareto_aggregate_name,
        n_gen_max=n_gen_max,
        objective_names=list(summary.get("objective_names", []) or []),
    )
    if summary["arm_ranking"]:
        print("[scheduler] final arm ranking:")
        for row in summary["arm_ranking"]:
            print(
                f"[scheduler] rank={int(row['rank'])} arm={row['arm']} "
                f"hv={float(row['hv']):.6g} trial={int(row['trial'])} status={row['status']}"
            )
    (out_dir / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")

    try:
        summary["constraints_report"] = _build_constraints_report(
            final_df=final_stage_df,
            constraint_names=active_names,
            constraint_senses=active_senses,
            constraint_rhs=active_rhs,
            active_constraints_source=active_source,
        )
    except Exception as exc:
        logger.warning("[scheduler] constraints_report generation failed (best-effort): %s", exc)
        summary["constraints_report"] = {
            "active_constraints_source": active_source,
            "active_constraints": {"names": active_names, "senses": active_senses, "rhs": active_rhs},
            "missing_constraints": list(active_names),
            "is_complete": False,
            "error": str(exc),
            "final_stage": {
                "n_points_total": int(final_stage_df.shape[0]),
                "n_points_feasible": None,
                "feasible_ratio": None,
                "by_arm": {},
            },
        }

    try:
        summary["consistency_report"] = _build_consistency_report(
            out_dir=out_dir,
            final_designs_df=final_designs_df,
            loadflows_csv_name=loadflows_csv_name,
        )
    except Exception as exc:
        logger.warning("[scheduler] consistency report generation failed (best-effort): %s", exc)
        summary["consistency_report"] = {
            "enabled": True,
            "status": "error",
            "reason": str(exc),
            "csv": None,
        }

    cleaned_nonfinal_run_dirs = 0
    if cleanup_nonfinal_runs and cleanup_candidates:
        for run_dir in sorted(set(cleanup_candidates)):
            run_path = Path(run_dir)
            if not run_path.exists():
                continue
            try:
                shutil.rmtree(run_path)
                cleaned_nonfinal_run_dirs += 1
            except Exception:
                continue
    summary["outputs_policy"]["cleaned_nonfinal_run_dirs"] = int(cleaned_nonfinal_run_dirs)
    cleaned_final_run_dirs = 0
    if cleanup_final_runs and final_stage_runs:
        for run_dir in sorted(set(str(r.get("run_dir", "")) for r in final_stage_runs)):
            run_path = Path(run_dir)
            if not run_path.exists():
                continue
            try:
                shutil.rmtree(run_path)
                cleaned_final_run_dirs += 1
            except Exception:
                continue
    summary["outputs_policy"]["cleaned_final_run_dirs"] = int(cleaned_final_run_dirs)
    (out_dir / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")

    optimizer_cfg = getattr(base_settings, "optimizer", None)
    optimizer_kwargs = getattr(optimizer_cfg, "kwargs", {}) or {}
    pop_size = int(optimizer_kwargs.get("pop_size", 0) or 0)
    n_arms = int(len(arm_names))
    effective_stage_budget_sum = int(sum(int(row.get("budget_n_gen", 0) or 0) for row in stage_log))
    effective_evaluations = int(pop_size * effective_stage_budget_sum) if pop_size > 0 else None
    baseline_full_evaluations = int(pop_size * n_gen_max * n_arms) if pop_size > 0 else None
    evaluations_saved_abs = (
        int(baseline_full_evaluations - effective_evaluations)
        if baseline_full_evaluations is not None and effective_evaluations is not None
        else None
    )
    evaluations_saved_pct = (
        float(evaluations_saved_abs / baseline_full_evaluations)
        if baseline_full_evaluations and evaluations_saved_abs is not None
        else None
    )
    scheduler_walltime_s = (datetime.now() - t_scheduler_start).total_seconds()
    run_metrics.write_run_metrics(
        out_dir,
        {
            "run_type": "scheduler_meta_run",
            "scheduler_name": str(getattr(sched, "pruner", "successive_halving")),
            "run_dir": str(out_dir),
            "started_at": t_scheduler_start.isoformat(timespec="seconds"),
            "finished_at": datetime.now().isoformat(timespec="seconds"),
            "total_walltime_s": scheduler_walltime_s,
            "scheduler_walltime_s": scheduler_walltime_s,
            "optimizer": {
                "name": str(getattr(optimizer_cfg, "name", "")),
                "pop_size": pop_size,
                "n_gen": n_gen_max,
                "n_jobs": int(getattr(optimizer_cfg, "n_jobs", 0) or 0),
                "seed": getattr(optimizer_cfg, "seed", None),
            },
            "evaluation_metrics": {
                "n_arms": n_arms,
                "budget_requested_total": int(n_gen_max * n_arms),
                "budget_executed_total": int(effective_stage_budget_sum),
                "baseline_full_evaluations": baseline_full_evaluations,
                "effective_evaluations": effective_evaluations,
                "evaluations_saved_abs": evaluations_saved_abs,
                "evaluations_saved_pct": evaluations_saved_pct,
                "mean_eval_walltime_s": (
                    float(scheduler_walltime_s / effective_evaluations)
                    if effective_evaluations
                    else None
                ),
                "median_eval_walltime_s": None,
                "p95_eval_walltime_s": None,
                "max_eval_walltime_s": None,
            },
            "artifacts": {
                "summary_json": "summary.json",
                "stage_log_csv": stage_log_name,
                "pareto_aggregate_csv": pareto_aggregate_name,
                "pareto_designs_csv": designs_csv_name,
            },
        },
    )
    if summary.get("best_arm") is None or summary.get("best_trial") is None or summary.get("best_hv") is None:
        print("BEST ARM: None")
    else:
        print(f"BEST ARM: {summary['best_arm']} (trial={summary['best_trial']}, hv={summary['best_hv']})")
    return {"run_dir": str(out_dir), "summary": summary}
