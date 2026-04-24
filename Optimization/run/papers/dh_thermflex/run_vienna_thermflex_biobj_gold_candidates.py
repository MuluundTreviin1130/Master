from __future__ import annotations

"""Select and export representative biobjective DH thermflex candidates.

This runner closes the gap between the fast surrogate Pareto search and the
paper-facing gold dispatch comparison.

It performs four explicit steps:

1. load the surrogate `pareto_points.csv`,
2. select three representative candidates from the Pareto front,
3. validate these candidates against gold `milp_day_ahead`,
4. export the selected feasible gold runs and build a comparison against the
   existing three paper baseline runs.

Selection stays explicit on purpose:
- `cost_end`: first gold-feasible point in increasing `F_dispatch_cost_eur`,
- `co2_end`: first gold-feasible point in increasing `F_co2_emissions_total_t`,
- `mid_tradeoff`: first gold-feasible point nearest to the normalized Pareto
  center `(0.5, 0.5)` while excluding already selected points.

There are no silent fallbacks:
- missing columns raise hard errors,
- objective spans must be non-zero,
- every selected candidate must be gold-feasible,
- paper baseline runs must already exist.
"""

import argparse
import json
import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List

import numpy as np
import pandas as pd


def _bootstrap_project_root() -> Path:
    current = Path(__file__).resolve()
    for parent in current.parents:
        if (parent / "Optimization").is_dir() and (parent / "Data").is_dir():
            project_root = parent
            project_root_str = str(project_root)
            if project_root_str not in sys.path:
                sys.path.insert(0, project_root_str)
            return project_root
    raise RuntimeError("[run_vienna_thermflex_biobj_gold_candidates] Project root not found.")


PROJECT_ROOT = _bootstrap_project_root()

from Settings.get_settings import get_settings
from Optimization.framework.engines.Gold.gold_engine import GoldEngine
from Optimization.run.analysis.build_paper_dispatch_comparison import build_paper_dispatch_comparison


DEFAULT_GOLD_OVERRIDE = (
    PROJECT_ROOT
    / "Optimization"
    / "validation"
    / "model_validation"
    / "overrides"
    / "thermflex"
    / "vienna_ref2023_dh_day_night_thermflex_surrogate_optimize.json"
)

PAPER_CASE_SPECS = (
    ("baseline_constant_no_thermflex", "vienna_ref2023_dh_baseline_constant_no_thermflex_paper_day_ahead"),
    ("day_night_no_thermflex", "vienna_ref2023_dh_day_night_no_thermflex_paper_day_ahead"),
    ("day_night_thermflex", "vienna_ref2023_dh_day_night_thermflex_paper_day_ahead"),
)


@dataclass
class CandidateSelection:
    selection_label: str
    pareto_idx: int
    sort_key: str
    sort_value: float
    surrogate_dispatch_cost_eur: float
    surrogate_co2_emissions_total_t: float
    gold_dispatch_cost_eur: float
    x_named: Dict[str, float]


def _load_json(path: Path) -> Dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(f"[run_vienna_thermflex_biobj_gold_candidates] File not found: {path}")
    return json.loads(path.read_text(encoding="utf-8-sig"))


def _build_gold_settings(
    *,
    override_path: Path,
    enable_reporting: bool,
    runtime_meta: Dict[str, Any] | None = None,
) -> Any:
    override = _load_json(override_path)
    override.setdefault("engine", {})
    override["engine"]["name"] = "gold"

    override.setdefault("feasibility", {})
    override["feasibility"]["enabled"] = False

    override.setdefault("surrogate_train", {})
    override["surrogate_train"]["feasibility_screen_enabled"] = False

    override.setdefault("reporting", {})
    override["reporting"]["write_dispatch_kpis"] = bool(enable_reporting)
    override["reporting"]["write_thermflex_hourly"] = False
    override["reporting"]["write_csv"] = bool(enable_reporting)
    override["reporting"]["write_summary"] = bool(enable_reporting)
    override["reporting"]["write_plot"] = False
    override["reporting"]["write_timeseries"] = False

    settings = get_settings(overrides=override)
    if runtime_meta:
        settings._runtime_meta = dict(runtime_meta)
    return settings


def _resolve_latest_run_dir(results_root: Path, run_suffix: str) -> Path:
    matches = [p for p in results_root.iterdir() if p.is_dir() and p.name.endswith(run_suffix)]
    if not matches:
        raise FileNotFoundError(
            f"[run_vienna_thermflex_biobj_gold_candidates] no run directory found for suffix '{run_suffix}' in {results_root}"
        )
    matches.sort(key=lambda p: p.name, reverse=True)
    selected = matches[0]
    dispatch_path = selected / "dispatch_kpis.json"
    if not dispatch_path.exists():
        raise FileNotFoundError(
            f"[run_vienna_thermflex_biobj_gold_candidates] dispatch_kpis.json missing in selected run: {selected}"
        )
    return selected


def _load_pareto_with_metrics(run_dir: Path) -> pd.DataFrame:
    pareto_path = run_dir / "pareto_points.csv"
    if not pareto_path.exists():
        raise FileNotFoundError(
            f"[run_vienna_thermflex_biobj_gold_candidates] Missing pareto_points.csv in {run_dir}"
        )
    df = pd.read_csv(pareto_path).copy()
    required_cols = {"F_dispatch_cost_eur", "F_co2_emissions_total_t"}
    missing = [col for col in required_cols if col not in df.columns]
    if missing:
        raise KeyError(
            "[run_vienna_thermflex_biobj_gold_candidates] pareto_points.csv is missing required objective columns: "
            + ", ".join(sorted(missing))
        )
    df["_pareto_idx"] = np.arange(len(df), dtype=int)

    cost_min = float(df["F_dispatch_cost_eur"].min())
    cost_max = float(df["F_dispatch_cost_eur"].max())
    co2_min = float(df["F_co2_emissions_total_t"].min())
    co2_max = float(df["F_co2_emissions_total_t"].max())
    cost_span = cost_max - cost_min
    co2_span = co2_max - co2_min
    if cost_span <= 0.0:
        raise ValueError("[run_vienna_thermflex_biobj_gold_candidates] Cost span is zero; biobjective selection is undefined.")
    if co2_span <= 0.0:
        raise ValueError("[run_vienna_thermflex_biobj_gold_candidates] CO2 span is zero; biobjective selection is undefined.")

    df["_cost_norm"] = (df["F_dispatch_cost_eur"] - cost_min) / cost_span
    df["_co2_norm"] = (df["F_co2_emissions_total_t"] - co2_min) / co2_span
    df["_center_distance_sq"] = (df["_cost_norm"] - 0.5) ** 2 + (df["_co2_norm"] - 0.5) ** 2
    return df


def _ordered_candidates(df: pd.DataFrame, selection_label: str) -> pd.DataFrame:
    if selection_label == "biobj_cost_end":
        return df.sort_values(
            ["F_dispatch_cost_eur", "F_co2_emissions_total_t", "_pareto_idx"],
            ascending=[True, True, True],
        ).reset_index(drop=True)
    if selection_label == "biobj_co2_end":
        return df.sort_values(
            ["F_co2_emissions_total_t", "F_dispatch_cost_eur", "_pareto_idx"],
            ascending=[True, True, True],
        ).reset_index(drop=True)
    if selection_label == "biobj_mid_tradeoff":
        return df.sort_values(
            ["_center_distance_sq", "F_dispatch_cost_eur", "F_co2_emissions_total_t", "_pareto_idx"],
            ascending=[True, True, True, True],
        ).reset_index(drop=True)
    raise KeyError(f"[run_vienna_thermflex_biobj_gold_candidates] Unknown selection label '{selection_label}'.")


def _evaluate_candidate_once(
    *,
    engine: GoldEngine,
    row: pd.Series,
    bounds_names: List[str],
    cache: Dict[int, Dict[str, Any]],
) -> Dict[str, Any]:
    pareto_idx = int(row["_pareto_idx"])
    if pareto_idx in cache:
        return cache[pareto_idx]

    x = np.array([float(row[name]) for name in bounds_names], dtype=float)
    record: Dict[str, Any] = {
        "pareto_idx": pareto_idx,
        "F_dispatch_cost_eur": float(row["F_dispatch_cost_eur"]),
        "F_co2_emissions_total_t": float(row["F_co2_emissions_total_t"]),
    }
    try:
        F, _G, _flows, _raw = engine.evaluate_one_with_details(x)
        record["status"] = "feasible"
        record["gold_dispatch_cost_eur"] = float(F[0, 0])
    except Exception as exc:
        record["status"] = "infeasible"
        record["exception_type"] = type(exc).__name__
        record["exception"] = str(exc)
    cache[pareto_idx] = record
    return record


def _select_first_feasible_distinct(
    *,
    selection_label: str,
    ordered_df: pd.DataFrame,
    engine: GoldEngine,
    bounds_names: List[str],
    cache: Dict[int, Dict[str, Any]],
    excluded_ids: set[int],
) -> tuple[CandidateSelection, List[Dict[str, Any]]]:
    audit_rows: List[Dict[str, Any]] = []
    for _, row in ordered_df.iterrows():
        pareto_idx = int(row["_pareto_idx"])
        if pareto_idx in excluded_ids:
            continue
        eval_record = _evaluate_candidate_once(
            engine=engine,
            row=row,
            bounds_names=bounds_names,
            cache=cache,
        )
        audit_row = {
            "selection_label": selection_label,
            "pareto_idx": pareto_idx,
            "candidate_status": str(eval_record["status"]),
            "surrogate_dispatch_cost_eur": float(row["F_dispatch_cost_eur"]),
            "surrogate_co2_emissions_total_t": float(row["F_co2_emissions_total_t"]),
        }
        if selection_label == "biobj_cost_end":
            audit_row["selection_metric_name"] = "F_dispatch_cost_eur"
            audit_row["selection_metric_value"] = float(row["F_dispatch_cost_eur"])
        elif selection_label == "biobj_co2_end":
            audit_row["selection_metric_name"] = "F_co2_emissions_total_t"
            audit_row["selection_metric_value"] = float(row["F_co2_emissions_total_t"])
        else:
            audit_row["selection_metric_name"] = "center_distance_sq"
            audit_row["selection_metric_value"] = float(row["_center_distance_sq"])
        if "gold_dispatch_cost_eur" in eval_record:
            audit_row["gold_dispatch_cost_eur"] = float(eval_record["gold_dispatch_cost_eur"])
        if "exception_type" in eval_record:
            audit_row["exception_type"] = str(eval_record["exception_type"])
            audit_row["exception"] = str(eval_record["exception"])
        audit_rows.append(audit_row)
        if str(eval_record["status"]) != "feasible":
            continue
        x_named = {str(name): float(row[name]) for name in bounds_names}
        selection = CandidateSelection(
            selection_label=selection_label,
            pareto_idx=pareto_idx,
            sort_key=str(audit_row["selection_metric_name"]),
            sort_value=float(audit_row["selection_metric_value"]),
            surrogate_dispatch_cost_eur=float(row["F_dispatch_cost_eur"]),
            surrogate_co2_emissions_total_t=float(row["F_co2_emissions_total_t"]),
            gold_dispatch_cost_eur=float(eval_record["gold_dispatch_cost_eur"]),
            x_named=x_named,
        )
        return selection, audit_rows
    raise RuntimeError(
        f"[run_vienna_thermflex_biobj_gold_candidates] No gold-feasible candidate found for selection '{selection_label}'."
    )


def _export_selected_gold_run(
    *,
    selection: CandidateSelection,
    export_settings: Any,
    bounds_names: List[str],
    group_dir: Path,
    surrogate_run_dir: Path,
) -> Path:
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    run_dir = group_dir / f"{stamp}_{selection.selection_label}_gold_day_ahead"
    run_dir.mkdir(parents=True, exist_ok=False)

    payload = {
        "selection_label": selection.selection_label,
        "pareto_idx": int(selection.pareto_idx),
        "sort_key": str(selection.sort_key),
        "sort_value": float(selection.sort_value),
        "surrogate_dispatch_cost_eur": float(selection.surrogate_dispatch_cost_eur),
        "surrogate_co2_emissions_total_t": float(selection.surrogate_co2_emissions_total_t),
        "gold_dispatch_cost_eur_recheck": float(selection.gold_dispatch_cost_eur),
        "surrogate_run_dir": str(surrogate_run_dir),
        "x_named": dict(selection.x_named),
    }
    (run_dir / "selected_candidate.json").write_text(
        json.dumps(payload, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    engine = GoldEngine(export_settings, run_dir=str(run_dir))
    x = np.array([float(selection.x_named[name]) for name in bounds_names], dtype=float).reshape(1, -1)
    engine.evaluate(x)
    return run_dir


def _parse_args() -> argparse.Namespace:
    ap = argparse.ArgumentParser()
    ap.add_argument("--surrogate-run-dir", type=str, required=True)
    ap.add_argument("--gold-override", type=str, default=str(DEFAULT_GOLD_OVERRIDE))
    return ap.parse_args()


def main() -> None:
    args = _parse_args()
    surrogate_run_dir = Path(args.surrogate_run_dir).resolve()
    if not surrogate_run_dir.exists():
        raise FileNotFoundError(
            f"[run_vienna_thermflex_biobj_gold_candidates] surrogate run dir not found: {surrogate_run_dir}"
        )

    pareto_df = _load_pareto_with_metrics(surrogate_run_dir)
    search_settings = _build_gold_settings(
        override_path=Path(args.gold_override).resolve(),
        enable_reporting=False,
    )
    search_engine = GoldEngine(search_settings)
    bounds_names = list(search_engine.s.bounds.names)
    missing_bounds = [name for name in bounds_names if name not in pareto_df.columns]
    if missing_bounds:
        raise KeyError(
            "[run_vienna_thermflex_biobj_gold_candidates] pareto_points.csv is missing bound columns: "
            + ", ".join(missing_bounds)
        )

    excluded_ids: set[int] = set()
    evaluation_cache: Dict[int, Dict[str, Any]] = {}
    audit_rows: List[Dict[str, Any]] = []
    selections: List[CandidateSelection] = []
    for selection_label in ("biobj_cost_end", "biobj_co2_end", "biobj_mid_tradeoff"):
        ordered = _ordered_candidates(pareto_df, selection_label)
        selection, audit_part = _select_first_feasible_distinct(
            selection_label=selection_label,
            ordered_df=ordered,
            engine=search_engine,
            bounds_names=bounds_names,
            cache=evaluation_cache,
            excluded_ids=excluded_ids,
        )
        selections.append(selection)
        excluded_ids.add(int(selection.pareto_idx))
        audit_rows.extend(audit_part)

    gold_root = PROJECT_ROOT / "Optimization" / "run" / "results" / "Vienna" / "gold"
    group_stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    group_dir = gold_root / f"biobj_gold_candidates_{group_stamp}"
    group_dir.mkdir(parents=True, exist_ok=False)

    export_run_dirs: List[Path] = []
    for selection in selections:
        runtime_meta = {
            "selection_label": selection.selection_label,
            "surrogate_run_dir": str(surrogate_run_dir),
            "pareto_idx": int(selection.pareto_idx),
        }
        export_settings = _build_gold_settings(
            override_path=Path(args.gold_override).resolve(),
            enable_reporting=True,
            runtime_meta=runtime_meta,
        )
        run_dir = _export_selected_gold_run(
            selection=selection,
            export_settings=export_settings,
            bounds_names=bounds_names,
            group_dir=group_dir,
            surrogate_run_dir=surrogate_run_dir,
        )
        export_run_dirs.append(run_dir)

    audit_df = pd.DataFrame(audit_rows)
    audit_df.to_csv(group_dir / "selection_audit.csv", index=False)
    (group_dir / "selection_summary.json").write_text(
        json.dumps(
            {
                "surrogate_run_dir": str(surrogate_run_dir),
                "selections": [
                    {
                        "selection_label": selection.selection_label,
                        "pareto_idx": int(selection.pareto_idx),
                        "sort_key": str(selection.sort_key),
                        "sort_value": float(selection.sort_value),
                        "surrogate_dispatch_cost_eur": float(selection.surrogate_dispatch_cost_eur),
                        "surrogate_co2_emissions_total_t": float(selection.surrogate_co2_emissions_total_t),
                        "gold_dispatch_cost_eur_recheck": float(selection.gold_dispatch_cost_eur),
                    }
                    for selection in selections
                ],
            },
            indent=2,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    baseline_root = PROJECT_ROOT / "Optimization" / "run" / "results" / "Vienna" / "gold"
    baseline_labels: List[str] = []
    baseline_run_dirs: List[Path] = []
    baseline_resolution: List[Dict[str, Any]] = []
    for label, suffix in PAPER_CASE_SPECS:
        run_dir = _resolve_latest_run_dir(baseline_root, suffix)
        baseline_labels.append(label)
        baseline_run_dirs.append(run_dir)
        baseline_resolution.append({"label": label, "run_dir": str(run_dir)})

    comparison_labels = baseline_labels + [selection.selection_label for selection in selections]
    comparison_run_dirs = baseline_run_dirs + export_run_dirs
    comparison_output_dir = group_dir / "paper_comparison"
    build_paper_dispatch_comparison(
        run_dirs=comparison_run_dirs,
        labels=comparison_labels,
        output_dir=comparison_output_dir,
    )

    selected_runs_payload = baseline_resolution + [
        {"label": selection.selection_label, "run_dir": str(run_dir)}
        for selection, run_dir in zip(selections, export_run_dirs)
    ]
    (comparison_output_dir / "selected_runs.json").write_text(
        json.dumps(selected_runs_payload, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    print(
        json.dumps(
            {
                "group_dir": str(group_dir),
                "comparison_output_dir": str(comparison_output_dir),
                "selected_run_dirs": [str(p) for p in export_run_dirs],
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
