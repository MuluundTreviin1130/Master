from __future__ import annotations

"""Recheck top surrogate candidates against gold dispatch solvers.

This runner exists because the surrogate optimization path is intentionally fast
and may still produce candidates that sit in gold-infeasible pockets. The
script makes the required validation layer explicit:

1. read `pareto_points.csv` from a surrogate run,
2. re-evaluate the top-k candidates with gold `milp_day_ahead`,
3. optionally replay the best day-ahead-feasible candidate with `milp_two_stage`.

No silent defaults are invented inside the validation itself. When this script
needs solver-specific cleanup, it performs it explicitly and documents why.
"""

import argparse
import json
import sys
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
    raise RuntimeError("[run_vienna_thermflex_surrogate_recheck] Project root with Optimization and Data not found.")


PROJECT_ROOT = _bootstrap_project_root()

from Settings import get_settings
from Optimization.framework.engines.Gold.gold_engine import GoldEngine


DEFAULT_DAY_AHEAD_OVERRIDE = (
    PROJECT_ROOT
    / "Optimization"
    / "validation"
    / "model_validation"
    / "overrides"
    / "thermflex"
    / "vienna_ref2023_dh_day_night_thermflex_surrogate_optimize.json"
)
DEFAULT_TWO_STAGE_OVERRIDE = (
    PROJECT_ROOT
    / "Optimization"
    / "validation"
    / "model_validation"
    / "overrides"
    / "thermflex"
    / "vienna_ref2023_dh_day_night_thermflex_two_stage.json"
)


def _load_json(path: Path) -> Dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(f"[run_vienna_thermflex_surrogate_recheck] File not found: {path}")
    return json.loads(path.read_text(encoding="utf-8-sig"))


def _write_json(path: Path, payload: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")


def _build_gold_settings_from_override(override_path: Path) -> Any:
    override = _load_json(override_path)
    override.setdefault("engine", {})
    override["engine"]["name"] = "gold"

    # A surrogate-only feasibility screen is a runtime artifact of the surrogate
    # optimizer. Gold validation must evaluate the physical dispatch model
    # directly, so the top-level screen constraint is removed explicitly here.
    override.setdefault("constraints", {})
    override["constraints"]["names"] = []
    override["constraints"]["senses"] = []
    override["constraints"]["rhs"] = []

    override.setdefault("feasibility", {})
    override["feasibility"]["enabled"] = False

    override.setdefault("surrogate_train", {})
    override["surrogate_train"]["feasibility_screen_enabled"] = False

    override.setdefault("reporting", {})
    override["reporting"]["write_dispatch_kpis"] = False
    override["reporting"]["write_thermflex_hourly"] = False
    override["reporting"]["write_csv"] = False
    override["reporting"]["write_summary"] = False
    override["reporting"]["write_plot"] = False
    override["reporting"]["write_timeseries"] = False

    return get_settings(overrides=override)


def _sort_pareto(pareto: pd.DataFrame, sort_column: str) -> pd.DataFrame:
    # Recheck ranking must stay explicit.
    # The surrogate run may be single-objective or multiobjective, so the caller
    # has to declare which exported `F_*` column defines the validation order.
    if sort_column not in pareto.columns:
        raise KeyError(
            f"[run_vienna_thermflex_surrogate_recheck] pareto_points.csv is missing '{sort_column}'."
        )
    return pareto.sort_values(sort_column, ascending=True).reset_index(drop=True)


def _evaluate_topk(
    engine: GoldEngine,
    pareto: pd.DataFrame,
    top_k: int,
    sort_column: str,
) -> List[Dict[str, Any]]:
    bounds_names = list(engine.s.bounds.names)
    missing = [name for name in bounds_names if name not in pareto.columns]
    if missing:
        raise KeyError(
            "[run_vienna_thermflex_surrogate_recheck] pareto_points.csv is missing bound columns: "
            + ", ".join(missing)
        )

    records: List[Dict[str, Any]] = []
    for idx, row in pareto.head(top_k).iterrows():
        x = np.array([float(row[name]) for name in bounds_names], dtype=float)
        record: Dict[str, Any] = {
            "rank": int(idx + 1),
            "surrogate_sort_metric_name": str(sort_column),
            "surrogate_sort_metric_value": float(row[sort_column]),
        }
        # Every exported surrogate objective column is copied into the audit row.
        # This keeps later paper/debug analysis explicit and avoids hidden
        # dependence on whichever objective happened to be used for ranking.
        objective_columns = [str(col) for col in pareto.columns if str(col).startswith("F_")]
        for objective_col in objective_columns:
            record[objective_col] = float(row[objective_col])
        for name in bounds_names:
            record[name] = float(row[name])
        try:
            F, G = engine.evaluate(x.reshape(1, -1))
            record["status"] = "feasible"
            record["gold_dispatch_cost_eur"] = float(F[0, 0])
        except Exception as exc:
            record["status"] = "infeasible"
            record["exception_type"] = type(exc).__name__
            record["exception"] = str(exc)
        records.append(record)
    return records


def _run_two_stage_validation(two_stage_settings: Any, selected_row: Dict[str, Any]) -> Dict[str, Any]:
    engine = GoldEngine(two_stage_settings)
    bounds_names = list(engine.s.bounds.names)
    x = np.array([float(selected_row[name]) for name in bounds_names], dtype=float)
    result: Dict[str, Any] = {"rank": int(selected_row["rank"])}
    for name in bounds_names:
        result[name] = float(selected_row[name])
    try:
        F, G = engine.evaluate(x.reshape(1, -1))
        result["status"] = "feasible"
        result["gold_two_stage_dispatch_cost_eur"] = float(F[0, 0])
    except Exception as exc:
        result["status"] = "infeasible"
        result["exception_type"] = type(exc).__name__
        result["exception"] = str(exc)
    return result


def _parse_args() -> argparse.Namespace:
    ap = argparse.ArgumentParser()
    ap.add_argument("--surrogate-run-dir", type=str, required=True)
    ap.add_argument("--top-k", type=int, default=10)
    ap.add_argument("--sort-column", type=str, default="F_dispatch_cost_eur")
    ap.add_argument("--day-ahead-override", type=str, default=str(DEFAULT_DAY_AHEAD_OVERRIDE))
    ap.add_argument("--two-stage-override", type=str, default=str(DEFAULT_TWO_STAGE_OVERRIDE))
    ap.add_argument("--skip-two-stage", action="store_true")
    return ap.parse_args()


def main() -> None:
    args = _parse_args()
    run_dir = Path(args.surrogate_run_dir).resolve()
    pareto_path = run_dir / "pareto_points.csv"
    if not pareto_path.exists():
        raise FileNotFoundError(
            f"[run_vienna_thermflex_surrogate_recheck] Missing pareto_points.csv in {run_dir}"
        )

    pareto = _sort_pareto(pd.read_csv(pareto_path), sort_column=str(args.sort_column))
    day_ahead_settings = _build_gold_settings_from_override(Path(args.day_ahead_override))
    day_ahead_engine = GoldEngine(day_ahead_settings)
    topk_records = _evaluate_topk(
        day_ahead_engine,
        pareto,
        int(args.top_k),
        sort_column=str(args.sort_column),
    )

    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_dir = run_dir / "surrogate_recheck" / stamp
    out_dir.mkdir(parents=True, exist_ok=True)

    topk_df = pd.DataFrame(topk_records)
    topk_df.to_csv(out_dir / "gold_day_ahead_topk.csv", index=False)

    feasible_rows = [row for row in topk_records if row.get("status") == "feasible"]
    summary: Dict[str, Any] = {
        "surrogate_run_dir": str(run_dir),
        "pareto_points_path": str(pareto_path),
        "day_ahead_override": str(Path(args.day_ahead_override).resolve()),
        "two_stage_override": str(Path(args.two_stage_override).resolve()),
        "top_k": int(args.top_k),
        "sort_column": str(args.sort_column),
        "n_topk_feasible_day_ahead": int(len(feasible_rows)),
        "topk_day_ahead_csv": str((out_dir / "gold_day_ahead_topk.csv").resolve()),
    }

    if feasible_rows:
        summary["best_day_ahead_feasible_rank"] = int(feasible_rows[0]["rank"])
        summary["best_day_ahead_feasible_dispatch_cost_eur"] = float(feasible_rows[0]["gold_dispatch_cost_eur"])
    else:
        summary["best_day_ahead_feasible_rank"] = None

    if not args.skip_two_stage and feasible_rows:
        two_stage_settings = _build_gold_settings_from_override(Path(args.two_stage_override))
        two_stage_result = _run_two_stage_validation(two_stage_settings, feasible_rows[0])
        pd.DataFrame([two_stage_result]).to_csv(out_dir / "gold_two_stage_selected.csv", index=False)
        summary["two_stage_selected_csv"] = str((out_dir / "gold_two_stage_selected.csv").resolve())
        summary["two_stage_selected_status"] = str(two_stage_result["status"])
        if "gold_two_stage_dispatch_cost_eur" in two_stage_result:
            summary["two_stage_selected_dispatch_cost_eur"] = float(two_stage_result["gold_two_stage_dispatch_cost_eur"])

    _write_json(out_dir / "summary.json", summary)
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
