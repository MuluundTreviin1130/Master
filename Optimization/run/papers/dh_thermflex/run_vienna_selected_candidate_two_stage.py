from __future__ import annotations

"""Replay one selected biobjective candidate with the explicit two-stage gold path.

This runner keeps the endpoint validation explicit and reproducible:

1. load a previously exported `selected_candidate.json`,
2. rebuild a gold settings object from the active Wiener day-ahead optimize SSOT,
3. switch only the dispatch block to the explicit `milp_two_stage` SSOT,
4. replay the exact design vector as a gold run with reporting enabled.

There are no silent fallbacks:
- the selected candidate file must exist,
- every active bound name must be present in `x_named`,
- the two-stage dispatch override must exist,
- runtime failures are surfaced as explicit errors.
"""

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict

import numpy as np


def _bootstrap_project_root() -> Path:
    current = Path(__file__).resolve()
    for parent in current.parents:
        if (parent / "Optimization").is_dir() and (parent / "Data").is_dir():
            project_root = parent
            project_root_str = str(project_root)
            if project_root_str not in sys.path:
                sys.path.insert(0, project_root_str)
            return project_root
    raise RuntimeError("[run_vienna_selected_candidate_two_stage] Project root not found.")


PROJECT_ROOT = _bootstrap_project_root()

from Settings.get_settings import get_settings
from Optimization.framework.engines.Gold.gold_engine import GoldEngine


DEFAULT_BASE_OVERRIDE = (
    PROJECT_ROOT
    / "Optimization"
    / "validation"
    / "model_validation"
    / "overrides"
    / "thermflex"
    / "vienna_ref2023_dh_day_night_thermflex_surrogate_optimize.json"
)

DEFAULT_DISPATCH_OVERRIDE = (
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
        raise FileNotFoundError(f"[run_vienna_selected_candidate_two_stage] File not found: {path}")
    return json.loads(path.read_text(encoding="utf-8-sig"))


def _build_two_stage_settings(
    *,
    base_override_path: Path,
    dispatch_override_path: Path,
    selected_payload: Dict[str, Any],
) -> Any:
    # The day-ahead optimize override stays the structural SSOT for bounds, active
    # technologies and calibrated runtime behavior. Only the dispatch block is
    # switched to the explicit two-stage SSOT so the endpoint check stays aligned
    # with the already documented `milp_two_stage` path.
    override = _load_json(base_override_path)
    dispatch_override = _load_json(dispatch_override_path)

    if "dispatch" not in dispatch_override:
        raise KeyError(
            "[run_vienna_selected_candidate_two_stage] dispatch override does not define a dispatch block."
        )

    override.setdefault("engine", {})
    override["engine"]["name"] = "gold"

    # Reuse the exact dispatch semantics from the explicit two-stage SSOT.
    override["dispatch"] = dispatch_override["dispatch"]

    # Keep reporting explicit so the endpoint check produces the normal gold
    # artifacts used elsewhere in the repo.
    override.setdefault("reporting", {})
    override["reporting"]["write_csv"] = True
    override["reporting"]["write_summary"] = True
    override["reporting"]["write_plot"] = False
    override["reporting"]["write_timeseries"] = False
    override["reporting"]["write_dispatch_kpis"] = True
    override["reporting"]["write_thermflex_hourly"] = False

    # Feasibility screens are a surrogate concern and must stay off in the gold
    # endpoint validation path.
    override.setdefault("feasibility", {})
    override["feasibility"]["enabled"] = False

    override.setdefault("surrogate_train", {})
    override["surrogate_train"]["feasibility_screen_enabled"] = False

    runtime_meta = {
        "selection_label": str(selected_payload["selection_label"]),
        "selection_source": "selected_candidate_two_stage",
        "selected_candidate_path": str(selected_payload["_selected_candidate_path"]),
        "surrogate_run_dir": str(selected_payload["surrogate_run_dir"]),
        "pareto_idx": int(selected_payload["pareto_idx"]),
    }
    settings = get_settings(overrides=override)
    settings._runtime_meta = runtime_meta
    return settings


def _resolve_x(settings: Any, selected_payload: Dict[str, Any]) -> np.ndarray:
    if "x_named" not in selected_payload or not isinstance(selected_payload["x_named"], dict):
        raise KeyError("[run_vienna_selected_candidate_two_stage] selected_candidate.json has no usable 'x_named' block.")

    x_named = selected_payload["x_named"]
    missing = [name for name in settings.bounds.names if name not in x_named]
    if missing:
        raise KeyError(
            "[run_vienna_selected_candidate_two_stage] selected candidate is missing active bound values: "
            + ", ".join(missing)
        )

    # Preserve bound order from settings exactly so the replayed vector is identical
    # to the original surrogate/gold day-ahead candidate.
    x = np.array([float(x_named[name]) for name in settings.bounds.names], dtype=float)
    return x.reshape(1, -1)


def _write_request(run_dir: Path, selected_payload: Dict[str, Any], base_override: Path, dispatch_override: Path) -> None:
    request_payload = {
        "selection_label": str(selected_payload["selection_label"]),
        "pareto_idx": int(selected_payload["pareto_idx"]),
        "sort_key": str(selected_payload["sort_key"]),
        "sort_value": float(selected_payload["sort_value"]),
        "surrogate_dispatch_cost_eur": float(selected_payload["surrogate_dispatch_cost_eur"]),
        "surrogate_co2_emissions_total_t": float(selected_payload["surrogate_co2_emissions_total_t"]),
        "gold_dispatch_cost_eur_recheck": float(selected_payload["gold_dispatch_cost_eur_recheck"]),
        "surrogate_run_dir": str(selected_payload["surrogate_run_dir"]),
        "selected_candidate_path": str(selected_payload["_selected_candidate_path"]),
        "base_override": str(base_override),
        "dispatch_override": str(dispatch_override),
        "x_named": dict(selected_payload["x_named"]),
    }
    (run_dir / "selected_candidate_request.json").write_text(
        json.dumps(request_payload, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )


def _write_summary(
    *,
    run_dir: Path,
    selected_payload: Dict[str, Any],
    status: str,
    exception: Exception | None = None,
) -> None:
    summary: Dict[str, Any] = {
        "status": str(status),
        "selection_label": str(selected_payload["selection_label"]),
        "pareto_idx": int(selected_payload["pareto_idx"]),
        "surrogate_run_dir": str(selected_payload["surrogate_run_dir"]),
        "selected_candidate_path": str(selected_payload["_selected_candidate_path"]),
    }
    if exception is not None:
        summary["exception_type"] = type(exception).__name__
        summary["exception"] = str(exception)
    (run_dir / "two_stage_endpoint_summary.json").write_text(
        json.dumps(summary, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )


def _parse_args() -> argparse.Namespace:
    ap = argparse.ArgumentParser()
    ap.add_argument("--selected-candidate-json", required=True, type=str)
    ap.add_argument("--base-override", default=str(DEFAULT_BASE_OVERRIDE), type=str)
    ap.add_argument("--dispatch-override", default=str(DEFAULT_DISPATCH_OVERRIDE), type=str)
    return ap.parse_args()


def main() -> None:
    args = _parse_args()
    selected_candidate_path = Path(args.selected_candidate_json).resolve()
    base_override_path = Path(args.base_override).resolve()
    dispatch_override_path = Path(args.dispatch_override).resolve()

    selected_payload = _load_json(selected_candidate_path)
    selected_payload["_selected_candidate_path"] = str(selected_candidate_path)

    settings = _build_two_stage_settings(
        base_override_path=base_override_path,
        dispatch_override_path=dispatch_override_path,
        selected_payload=selected_payload,
    )
    x = _resolve_x(settings, selected_payload)

    parent_dir = selected_candidate_path.parent
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    selection_label = str(selected_payload["selection_label"])
    run_dir = parent_dir / f"{stamp}_{selection_label}_gold_two_stage"
    run_dir.mkdir(parents=True, exist_ok=False)
    _write_request(run_dir, selected_payload, base_override_path, dispatch_override_path)

    try:
        engine = GoldEngine(settings, run_dir=str(run_dir))
        engine.evaluate(x)
    except Exception as exc:
        # Persist the failure as an explicit artifact so endpoint infeasibility is
        # documented in the same way as successful gold runs.
        _write_summary(run_dir=run_dir, selected_payload=selected_payload, status="failed", exception=exc)
        raise
    _write_summary(run_dir=run_dir, selected_payload=selected_payload, status="ok")


if __name__ == "__main__":
    main()
