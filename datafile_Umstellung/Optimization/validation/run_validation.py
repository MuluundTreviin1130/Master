# Optimization/validation/run_validation.py
from __future__ import annotations
import contextlib
import os
from pathlib import Path
import sys

# Workspace-Root finden - suche nach datafile_Umstellung Ordner (da Script bereits darin liegt)
current = Path(__file__).resolve()
workspace_root = None
datafile_umstellung_dir = None

# Suche nach datafile_Umstellung (Script liegt bereits darin)
for parent in current.parents:
    if parent.name == "datafile_Umstellung":
        datafile_umstellung_dir = parent
        # Workspace-Root ist der Parent von datafile_Umstellung
        workspace_root = parent.parent
        break

if datafile_umstellung_dir is None or not datafile_umstellung_dir.exists():
    # Fallback: suche nach V2H_energy_community_surrogat_datafilenew
    for parent in current.parents:
        v2h_dir = parent / "V2H_energy_community_surrogat_datafilenew"
        if v2h_dir.exists():
            workspace_root = parent
            datafile_umstellung_dir = v2h_dir / "datafile_Umstellung"
            break

if datafile_umstellung_dir is None or not datafile_umstellung_dir.exists():
    # Letzter Fallback: verwende die alte Methode
    workspace_root = current.parent.parent.parent.parent.parent
    datafile_umstellung_dir = workspace_root / "V2H_energy_community_surrogat_datafilenew" / "datafile_Umstellung"

# Beide Pfade hinzufügen:
# 1. Workspace-Root (für vollständige Imports)
workspace_root_str = str(workspace_root.resolve())
if workspace_root_str not in sys.path:
    sys.path.insert(0, workspace_root_str)

# 2. datafile_Umstellung (für relative Imports wie Optimization.framework...)
# WICHTIG: Dieser muss VOR allen Imports gesetzt sein, damit Data und Technical_model gefunden werden
if datafile_umstellung_dir and datafile_umstellung_dir.exists():
    datafile_umstellung_str = str(datafile_umstellung_dir.resolve())
    if datafile_umstellung_str not in sys.path:
        sys.path.insert(0, datafile_umstellung_str)
else:
    # Verbesserte Fehlermeldung mit mehr Debug-Info
    raise RuntimeError(
        f"[run_validation] datafile_Umstellung Ordner nicht gefunden!\n"
        f"  Gesucht in: {workspace_root / 'V2H_energy_community_surrogat_datafilenew' / 'datafile_Umstellung'}\n"
        f"  Existiert: {(workspace_root / 'V2H_energy_community_surrogat_datafilenew' / 'datafile_Umstellung').exists()}\n"
        f"  Aktuelles Verzeichnis: {Path.cwd()}\n"
        f"  Script-Pfad: {current}\n"
        f"  Workspace-Root: {workspace_root}\n"
        f"  sys.path: {sys.path[:3]}"
    )

# Debug: Prüfe ob Optimization.framework existiert
_opt_framework = datafile_umstellung_dir / "Optimization" / "framework"
if not _opt_framework.exists():
    raise RuntimeError(
        f"[run_validation] Optimization/framework nicht gefunden!\n"
        f"  Erwartet: {_opt_framework}\n"
        f"  Existiert: {_opt_framework.exists()}\n"
        f"  datafile_Umstellung: {datafile_umstellung_dir}"
    )

import json
import numpy as np
import pandas as pd

from Optimization.framework.Settings.get_settings import get_settings
from Optimization.framework.Samplers import SAMPLERS
from Optimization.framework.Samplers.lhs import snap_to_steps
from Optimization.framework.engines.kpi import compute_objectives
from Optimization.framework.engines.profiles_meta import get_profile_id
from Optimization.framework.engines.signature_utils import build_signature_dict, signature_hash
from Optimization.framework.Orchestrator.registry import resolve_engine
from Optimization.framework.engines.Surrogat_model.validate.holdout import metrics_by_column
from Technical_model.energy_system.precompute.adapter import prepare_profiles_adapter


if __name__ == "__main__":
    with open(os.devnull, "w") as devnull, contextlib.redirect_stdout(devnull), contextlib.redirect_stderr(devnull):
        s = get_settings()
    v = getattr(s, "validation", None)
    h = getattr(v, "holdout", None) if v is not None else None

    if h is None or not bool(getattr(h, "enabled", False)):
        sys.exit(0)

    root_dir = Path(str(getattr(h, "root_dir", "")))
    try:
        root_dir.mkdir(parents=True, exist_ok=True)
    except Exception as exc:
        raise RuntimeError(f"[holdout] cannot create root_dir / no rights: {root_dir}") from exc
    if not root_dir.is_dir():
        raise RuntimeError(f"[holdout] cannot create root_dir / no rights: {root_dir}")

    run_id = str(getattr(getattr(s, "run", None), "tag", "run"))
    out_dir = root_dir / f"holdout_run_{run_id}"
    try:
        out_dir.mkdir(parents=True, exist_ok=True)
    except Exception as exc:
        raise RuntimeError(f"[holdout] cannot create output dir: {out_dir}") from exc

    mode = str(getattr(h, "mode", "generate"))
    n = int(getattr(h, "n", 0))
    seed = int(getattr(h, "seed", 0))
    sampler_name = str(getattr(h, "sampler", "lhs"))
    xschema = list(getattr(h, "xschema", []) or [])
    bounds_source = str(getattr(h, "bounds_source", "settings"))
    report_kpis = list(getattr(h, "report_kpis", []) or [])
    ref_engine = str(getattr(h, "ref_engine", "gold")).lower()
    pred_engine = str(getattr(h, "pred_engine", "surrogate")).lower()
    strict = bool(getattr(h, "strict", True))

    if bounds_source != "settings":
        raise RuntimeError(f"[holdout] bounds_source='{bounds_source}' not supported")

    if not xschema:
        xschema = list(getattr(getattr(s, "bounds", None), "names", []))
    if not xschema:
        raise RuntimeError("[holdout] xschema is empty")

    if mode != "generate":
        raise RuntimeError(f"[holdout] unsupported mode='{mode}'")
    if n <= 0:
        raise RuntimeError("[holdout] n must be > 0 for mode=generate")

    if not report_kpis:
        raise RuntimeError("[holdout] report_kpis is empty")

    # --- bounds ---
    names = list(getattr(getattr(s, "bounds", None), "names", []))
    lower = list(getattr(getattr(s, "bounds", None), "lower", []))
    upper = list(getattr(getattr(s, "bounds", None), "upper", []))
    steps = list(getattr(getattr(s, "bounds", None), "steps", [])) if getattr(s, "bounds", None) else []
    if names != xschema:
        raise RuntimeError(f"[holdout] xschema mismatch: {xschema} vs {names}")
    if len(lower) != len(names) or len(upper) != len(names):
        raise RuntimeError("[holdout] bounds length mismatch")
    if not steps:
        steps = [0.0 for _ in names]

    # --- sample ---
    sampler_key = (sampler_name or "").lower()
    Sampler = SAMPLERS.get(sampler_key)
    if Sampler is None:
        rng = np.random.default_rng(seed)
        U = rng.random((n, len(lower)))
        X = np.asarray(lower, float) + U * (np.asarray(upper, float) - np.asarray(lower, float))
    else:
        sampler = Sampler()
        if sampler_key == "lhs":
            state = np.random.get_state()
            np.random.seed(seed)
            X = sampler.sample(n=n, lower=lower, upper=upper, seed=seed)
            np.random.set_state(state)
        else:
            X = sampler.sample(n=n, lower=lower, upper=upper, seed=seed)
    if steps:
        X = snap_to_steps(X, steps)
    X_holdout = pd.DataFrame(X, columns=xschema)

    # --- profiles / params ---
    with open(os.devnull, "w") as devnull, contextlib.redirect_stdout(devnull), contextlib.redirect_stderr(devnull):
        prep = prepare_profiles_adapter(s)
    params_base = dict(prep.params_base)
    lifetime_years = int(prep.lifetime_years)
    profile_id = get_profile_id(prep.profiles, s)
    system_id = str(getattr(getattr(s, "engine", None), "system_id", "unknown"))

    signature_dict = build_signature_dict(
        s,
        surrogate_meta_hint={},
        system_context={
            "profile_id": profile_id,
            "system_id": system_id,
        },
    )
    sig_hash = signature_hash(signature_dict)

    obj_names = list(getattr(getattr(s, "objectives", None), "names", []) or [])
    missing_obj = [k for k in report_kpis if k not in obj_names]
    if missing_obj:
        raise RuntimeError(f"[holdout] report_kpis not in objectives: {missing_obj}")

    def _kpi_row(flows_L: dict, pv_kwp: float, bess_kwh: float) -> list[float]:
        design_vars = {
            "pv_kwp": float(pv_kwp),
            "bess_kwh": float(bess_kwh),
            "params": params_base,
            "lifetime_years": lifetime_years,
        }
        tmp_settings = type("S", (), {"objectives": type("O", (), {"names": report_kpis})(), "engine": s.engine})
        obj = compute_objectives(flows_L, design_vars, tmp_settings)
        return [float(obj[k]) for k in report_kpis]

    def _kpi_row_from_objectives(F_row: np.ndarray) -> list[float]:
        idx = {name: i for i, name in enumerate(obj_names)}
        return [float(F_row[idx[k]]) for k in report_kpis]

    def _batch_eval(engine_name: str, engine_instance, X_arr: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
        if engine_name == "gated":
            n_total = int(X_arr.shape[0])
            if n_total == 0:
                return np.zeros((0, len(obj_names)), float), np.zeros((0, 0), float)
            
            # Verwende batch_size aus HoldoutConfig (kleinere Batches = mehr nicht-dominante Punkte pro Batch)
            batch_size = int(getattr(h, "batch_size", 10))
            batch_size = max(1, batch_size)
            
            F_chunks = []
            G_chunks = []
            for start in range(0, n_total, batch_size):
                X_chunk = X_arr[start:start + batch_size]
                F_chunk, G_chunk = engine_instance.evaluate(X_chunk)
                F_chunks.append(np.asarray(F_chunk))
                G_chunks.append(np.asarray(G_chunk))
            F = np.vstack(F_chunks) if F_chunks else np.zeros((0, len(obj_names)), float)
            if G_chunks:
                G = np.vstack(G_chunks)
            else:
                G = np.zeros((F.shape[0], 0), float)
            return F, G
        return engine_instance.evaluate(X_arr)

    # --- holdout header ---
    print("[holdout] run_id:", run_id)
    print(f"[holdout] n={n}, seed={seed}, sampler={sampler_name}, bounds_source={bounds_source}")
    print(f"[holdout] report_kpis={report_kpis}")
    print(f"[holdout] ref_engine={ref_engine}, pred_engine={pred_engine}")
    print(f"[holdout] root_dir={root_dir}")
    print(f"[holdout] out_dir={out_dir}")

    # --- reference ---
    RefEngine = resolve_engine(ref_engine)
    ref_engine_instance = RefEngine(s)
    if hasattr(ref_engine_instance, "evaluate_one_with_flows"):
        rows_truth = []
        for i in range(X_holdout.shape[0]):
            x = X_holdout.iloc[i, :].to_numpy(dtype=float)
            _F, _G, flows_L = ref_engine_instance.evaluate_one_with_flows(x)
            rows_truth.append(_kpi_row(flows_L, float(x[0]), float(x[1])))
        gold_truth = pd.DataFrame(rows_truth, columns=report_kpis)
    else:
        F, _G = _batch_eval(ref_engine, ref_engine_instance, X_holdout.values)
        gold_truth = pd.DataFrame(
            [_kpi_row_from_objectives(F[i, :]) for i in range(F.shape[0])],
            columns=report_kpis,
        )

    # --- predictor ---
    if pred_engine == ref_engine:
        pred_holdout = gold_truth.copy(deep=True)
    elif pred_engine in {"gold", "gated"}:
        PredEngine = resolve_engine(pred_engine)
        pred_engine_instance = PredEngine(s)
        if hasattr(pred_engine_instance, "evaluate_one_with_flows"):
            rows_pred = []
            for i in range(X_holdout.shape[0]):
                x = X_holdout.iloc[i, :].to_numpy(dtype=float)
                _F, _G, flows_L = pred_engine_instance.evaluate_one_with_flows(x)
                rows_pred.append(_kpi_row(flows_L, float(x[0]), float(x[1])))
            pred_holdout = pd.DataFrame(rows_pred, columns=report_kpis)
        else:
            F, _G = _batch_eval(pred_engine, pred_engine_instance, X_holdout.values)
            pred_holdout = pd.DataFrame(
                [_kpi_row_from_objectives(F[i, :]) for i in range(F.shape[0])],
                columns=report_kpis,
            )
    elif pred_engine == "surrogate":
        # Verwende SurrogateEngine direkt (hat korrekte Pfadlogik und Feature-Augmentierung)
        from Optimization.framework.engines.Surrogat_model.surrogate_engine import SurrogateEngine
        pred_engine_instance = SurrogateEngine(s, run_dir=None)
        
        # SurrogateEngine hat evaluate(), aber nicht evaluate_one_with_flows
        # Daher verwenden wir evaluate() und mappen die Objectives zu report_kpis
        F, _G = pred_engine_instance.evaluate(X_holdout.values)
        pred_holdout = pd.DataFrame(
            [_kpi_row_from_objectives(F[i, :]) for i in range(F.shape[0])],
            columns=report_kpis,
        )
    else:
        raise RuntimeError(f"[holdout] unknown pred_engine='{pred_engine}'")

    # --- outputs ---
    gold_truth.to_csv(out_dir / "gold_truth_holdout.csv", index=False)
    pred_holdout.to_csv(out_dir / "pred_holdout.csv", index=False)

    metrics = metrics_by_column(gold_truth.values, pred_holdout.values, target_names=report_kpis)
    rows = []
    for i, name in enumerate(metrics.get("targets", [])):
        rows.append({"kpi": name, "metric": "r2", "value": metrics["r2"][i]})
        rows.append({"kpi": name, "metric": "rmse", "value": metrics["rmse"][i]})
        rows.append({"kpi": name, "metric": "mae", "value": metrics["mae"][i]})
        rows.append({"kpi": name, "metric": "rel_MAE%", "value": metrics["rel_mae_percent"][i]})
    pd.DataFrame(rows).to_csv(out_dir / "holdout_metrics.csv", index=False)

    # scatter plots
    for kpi in report_kpis:
        y_true = gold_truth[kpi].values
        y_pred = pred_holdout[kpi].values
        lo = float(np.nanmin([y_true.min(), y_pred.min()]))
        hi = float(np.nanmax([y_true.max(), y_pred.max()]))
        import matplotlib.pyplot as plt

        fig, ax = plt.subplots(figsize=(5, 5))
        ax.scatter(y_true, y_pred, s=10, alpha=0.6)
        ax.plot([lo, hi], [lo, hi], color="black", linestyle="--", linewidth=1)
        ax.set_xlabel("Truth")
        ax.set_ylabel("Pred")
        ax.set_title(kpi)
        fig.tight_layout()
        fig.savefig(out_dir / f"scatter_{kpi}.png", dpi=150)
        plt.close(fig)

    meta = {
        "run_id": run_id,
        "n": int(n),
        "seed": int(seed),
        "sampler": sampler_name,
        "xschema": xschema,
        "report_kpis": report_kpis,
        "ref_engine": ref_engine,
        "pred_engine": pred_engine,
        "strict": strict,
        "signature_hash": sig_hash,
        "batch_size": int(getattr(h, "batch_size", 10)),
    }
    
    # GatingGoldConfig-Einstellungen hinzufügen
    if s.gating and s.gating.gold:
        gold_cfg = s.gating.gold
        meta["gating_gold"] = {
            "enabled": bool(gold_cfg.enabled),
            "mode": str(gold_cfg.mode),
            "fraction_max": float(gold_cfg.fraction_max),
            "min_points": int(gold_cfg.min_points),
            "period_batches": int(gold_cfg.period_batches),
            "finalists_k": int(gold_cfg.finalists_k),
        }
    
    (out_dir / "holdout_run.meta.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")
