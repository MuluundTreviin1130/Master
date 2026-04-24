from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[4]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from Settings.technical.building_calibration import make_building_calibration_config
from Technical_model.technologies.buildings.calibration.teachers.energyplus import (
    run_energyplus_teacher_experiment,
)


def _load_json(path_str: str, *, label: str) -> dict:
    path = Path(path_str).resolve()
    if not path.exists():
        raise FileNotFoundError(f"[energyplus_teacher_batch] Missing {label}: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def _resolve_cohort_ids(requested: list[str] | None) -> list[str]:
    cfg = make_building_calibration_config()
    teacher_bundle = _load_json(cfg.teacher_input_output_json, label="teacher_input_output_json")
    available = [str(item["cohort_id"]) for item in teacher_bundle.get("cohorts", [])]
    if not available:
        raise RuntimeError("[energyplus_teacher_batch] No cohorts found in teacher input bundle.")
    if not requested:
        return available
    missing = [cohort_id for cohort_id in requested if cohort_id not in available]
    if missing:
        raise KeyError(f"[energyplus_teacher_batch] Unknown cohort_ids requested: {missing}")
    return requested


def _resolve_experiment_ids(requested: list[str] | None) -> list[str]:
    cfg = make_building_calibration_config()
    experiment_library = _load_json(cfg.experiment_library_output_json, label="experiment_library_output_json")
    available = [str(item["experiment_id"]) for item in experiment_library.get("experiments", [])]
    if not available:
        raise RuntimeError("[energyplus_teacher_batch] No experiments found in experiment library.")
    if not requested:
        requested = list(cfg.teacher_plausibility_batch_default_experiments)
    missing = [experiment_id for experiment_id in requested if experiment_id not in available]
    if missing:
        raise KeyError(f"[energyplus_teacher_batch] Unknown experiment_ids requested: {missing}")
    return requested


def _build_row(*, cohort_id: str, experiment_id: str, result_meta: dict, summary: dict) -> dict:
    geometry = dict(result_meta.get("geometry", {}))
    return {
        "cohort_id": cohort_id,
        "experiment_id": experiment_id,
        "control_mode": str(result_meta.get("control_mode", "")),
        "teacher_reference_gfa_m2": float(result_meta["teacher_reference_gfa_m2"]),
        "cohort_represented_gfa_m2": float(result_meta["cohort_represented_gfa_m2"]),
        "dh_connected_share_used": (
            None if summary["dh_connected_share_used"] is None else float(summary["dh_connected_share_used"])
        ),
        "dh_connected_share_source": (
            None if summary["dh_connected_share_source"] is None else str(summary["dh_connected_share_source"])
        ),
        "window_hours": int(summary["window_hours"]),
        "heating_kwh_reference_total": float(summary["heating_kwh_reference_total"]),
        "heating_kwh_cohort_scaled_total": float(summary["heating_kwh_cohort_scaled_total"]),
        "heating_kwh_dh_bus_scaled_total": (
            None if summary["heating_kwh_dh_bus_scaled_total"] is None else float(summary["heating_kwh_dh_bus_scaled_total"])
        ),
        "cooling_kwh_total": float(summary["cooling_kwh_total"]),
        "expected_average_window_space_heat_kwh_cohort": float(summary["expected_average_window_space_heat_kwh_cohort"]),
        "expected_average_window_space_heat_kwh_dh_bus": (
            None
            if summary["expected_average_window_space_heat_kwh_dh_bus"] is None
            else float(summary["expected_average_window_space_heat_kwh_dh_bus"])
        ),
        "window_factor_vs_average_cohort": (
            None if summary["window_factor_vs_average_cohort"] is None else float(summary["window_factor_vs_average_cohort"])
        ),
        "window_factor_vs_average_dh_bus": (
            None if summary["window_factor_vs_average_dh_bus"] is None else float(summary["window_factor_vs_average_dh_bus"])
        ),
        "mean_zone_air_temperature_c": float(summary["mean_zone_air_temperature_c"]),
        "min_zone_air_temperature_c": float(summary["min_zone_air_temperature_c"]),
        "max_zone_air_temperature_c": float(summary["max_zone_air_temperature_c"]),
        "mean_outdoor_air_temperature_c": float(summary["mean_outdoor_air_temperature_c"]),
        "internal_gains_kwh_total": float(summary["internal_gains_kwh_total"]),
        "window_solar_transmitted_kwh_total": float(summary["window_solar_transmitted_kwh_total"]),
        "window_heat_gain_kwh_total": float(summary["window_heat_gain_kwh_total"]),
        "window_heat_loss_kwh_total": float(summary["window_heat_loss_kwh_total"]),
        "window_solar_transmitted_kwh_per_window_m2": float(summary["window_solar_transmitted_kwh_per_window_m2"]),
        "window_heat_gain_kwh_per_window_m2": float(summary["window_heat_gain_kwh_per_window_m2"]),
        "window_heat_loss_kwh_per_window_m2": float(summary["window_heat_loss_kwh_per_window_m2"]),
        "window_solar_to_internal_gains_ratio": (
            None
            if summary["window_solar_to_internal_gains_ratio"] is None
            else float(summary["window_solar_to_internal_gains_ratio"])
        ),
        "window_solar_to_heating_ratio": (
            None if summary["window_solar_to_heating_ratio"] is None else float(summary["window_solar_to_heating_ratio"])
        ),
        "approx_transmission_loss_seed_ua_kwh_total": float(summary["approx_transmission_loss_seed_ua_kwh_total"]),
        "approx_ventilation_loss_kwh_total": float(summary["approx_ventilation_loss_kwh_total"]),
        "approx_infiltration_loss_kwh_total": float(summary["approx_infiltration_loss_kwh_total"]),
        "epw_ghi_wh_m2_total": float(summary["epw_ghi_wh_m2_total"]),
        "epw_dni_wh_m2_total": float(summary["epw_dni_wh_m2_total"]),
        "epw_dhi_wh_m2_total": float(summary["epw_dhi_wh_m2_total"]),
        "seed_ua_reference_w_per_k": float(summary["seed_ua_reference_w_per_k"]),
        "seed_ua_reference_w_per_m2k": float(summary["seed_ua_reference_w_per_m2k"]),
        "heat_capacity_reference_wh_per_m2k": float(summary["heat_capacity_reference_wh_per_m2k"]),
        "window_to_floor_ratio_reference": float(summary["window_to_floor_ratio_reference"]),
        "wall_to_floor_ratio_reference": float(summary["wall_to_floor_ratio_reference"]),
        "roof_to_floor_ratio_reference": float(summary["roof_to_floor_ratio_reference"]),
        "floor_exposed_to_floor_ratio_reference": float(summary["floor_exposed_to_floor_ratio_reference"]),
        "geometry_conditioned_floor_m2": float(geometry.get("conditioned_floor_m2", 0.0)),
        "geometry_window_area_total_m2": float(geometry.get("window_area_total_m2", 0.0)),
        "geometry_roof_area_m2": float(geometry.get("roof_area_m2", 0.0)),
        "geometry_wall_area_m2": float(geometry.get("wall_area_m2", 0.0)),
        "hourly_csv_path": str(result_meta["hourly_csv_path"]),
        "plausibility_hourly_csv_path": str(result_meta["plausibility_hourly_csv_path"]),
        "plausibility_summary_path": str(result_meta["plausibility_summary_path"]),
        "plausibility_plot_path": str(result_meta["plausibility_plot_path"]),
    }


def _build_geometry_solar_review(rows: list[dict]) -> dict:
    if not rows:
        raise RuntimeError("[energyplus_teacher_batch] Cannot build geometry/solar review from an empty row set.")
    reference_rows = [row for row in rows if row["experiment_id"] == "winter_reference_week"]
    free_float_rows = [row for row in rows if row["experiment_id"] == "winter_free_float_72h"]

    def _pick(entries: list[dict], *, key: str, reverse: bool = True, fields: tuple[str, ...]) -> list[dict]:
        ranked = sorted(entries, key=lambda item: float(item[key]), reverse=reverse)
        out: list[dict] = []
        for item in ranked:
            payload = {"cohort_id": str(item["cohort_id"]), "experiment_id": str(item["experiment_id"])}
            for field in fields:
                payload[field] = item[field]
            out.append(payload)
        return out

    return {
        "reference_by_window_solar_per_window_m2_desc": _pick(
            reference_rows,
            key="window_solar_transmitted_kwh_per_window_m2",
            reverse=True,
            fields=(
                "window_solar_transmitted_kwh_per_window_m2",
                "window_solar_to_internal_gains_ratio",
                "window_solar_to_heating_ratio",
                "window_to_floor_ratio_reference",
                "seed_ua_reference_w_per_m2k",
                "mean_zone_air_temperature_c",
            ),
        ),
        "reference_by_seed_ua_per_m2k_desc": _pick(
            reference_rows,
            key="seed_ua_reference_w_per_m2k",
            reverse=True,
            fields=(
                "seed_ua_reference_w_per_m2k",
                "window_to_floor_ratio_reference",
                "window_solar_transmitted_kwh_per_window_m2",
                "heating_kwh_reference_total",
                "window_factor_vs_average_cohort",
            ),
        ),
        "free_float_by_min_zone_temp_asc": _pick(
            free_float_rows,
            key="min_zone_air_temperature_c",
            reverse=False,
            fields=(
                "min_zone_air_temperature_c",
                "mean_zone_air_temperature_c",
                "window_to_floor_ratio_reference",
                "seed_ua_reference_w_per_m2k",
                "heat_capacity_reference_wh_per_m2k",
            ),
        ),
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run EnergyPlus teacher plausibility batch over selected cohorts and experiments."
    )
    parser.add_argument(
        "--cohort-id",
        dest="cohort_ids",
        action="append",
        default=None,
        help="Optional repeated cohort_id. Without this, all cohorts from teacher_inputs_v1.json are used.",
    )
    parser.add_argument(
        "--experiment-id",
        dest="experiment_ids",
        action="append",
        default=None,
        help="Optional repeated experiment_id. Without this, default reference+free_float experiments are used.",
    )
    parser.add_argument(
        "--dh-share",
        dest="dh_share",
        type=float,
        default=None,
        help="Optional explicit DH-connected share for bus-scaled plausibility metrics. Without this no DH scaling is applied unless a cohort override exists.",
    )
    args = parser.parse_args()

    cfg = make_building_calibration_config()
    cohort_ids = _resolve_cohort_ids(args.cohort_ids)
    experiment_ids = _resolve_experiment_ids(args.experiment_ids)

    rows: list[dict] = []
    for cohort_id in cohort_ids:
        for experiment_id in experiment_ids:
            result = run_energyplus_teacher_experiment(
                cohort_id=cohort_id,
                experiment_id=experiment_id,
                dh_connected_share=args.dh_share,
            )
            result_meta = json.loads(result.meta_path.read_text(encoding="utf-8"))
            summary_path = Path(result_meta["plausibility_summary_path"]).resolve()
            summary = json.loads(summary_path.read_text(encoding="utf-8"))
            rows.append(
                _build_row(
                    cohort_id=cohort_id,
                    experiment_id=experiment_id,
                    result_meta=result_meta,
                    summary=summary,
                )
            )
            dh_heat = summary["heating_kwh_dh_bus_scaled_total"]
            dh_heat_str = "unset" if dh_heat is None else f"{float(dh_heat):.2f}"
            print(
                f"[energyplus_teacher_batch] done cohort={cohort_id} experiment={experiment_id} "
                f"heating_kwh_dh_bus_scaled_total={dh_heat_str}",
                flush=True,
            )

    out_dir = Path(cfg.teacher_plausibility_batch_output_dir).resolve()
    out_dir.mkdir(parents=True, exist_ok=True)
    df = pd.DataFrame(rows)
    csv_path = out_dir / str(cfg.teacher_plausibility_batch_summary_csv)
    json_path = out_dir / str(cfg.teacher_plausibility_batch_summary_json)
    review_csv_path = out_dir / str(cfg.teacher_geometry_solar_review_csv)
    review_json_path = out_dir / str(cfg.teacher_geometry_solar_review_json)
    df.to_csv(csv_path, index=False, encoding="utf-8")
    df.to_csv(review_csv_path, index=False, encoding="utf-8")
    geometry_solar_review = _build_geometry_solar_review(rows)
    json_path.write_text(
        json.dumps(
            {
                "cohort_ids": cohort_ids,
                "experiment_ids": experiment_ids,
                "dh_share_argument": args.dh_share,
                "n_runs": len(rows),
                "summary_csv_path": str(csv_path),
                "rows": rows,
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    review_json_path.write_text(
        json.dumps(
            {
                "dh_share_argument": args.dh_share,
                "review_csv_path": str(review_csv_path),
                "review": geometry_solar_review,
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    print(f"[energyplus_teacher_batch] summary csv : {csv_path}", flush=True)
    print(f"[energyplus_teacher_batch] summary json: {json_path}", flush=True)
    print(f"[energyplus_teacher_batch] review csv  : {review_csv_path}", flush=True)
    print(f"[energyplus_teacher_batch] review json : {review_json_path}", flush=True)


if __name__ == "__main__":
    main()
