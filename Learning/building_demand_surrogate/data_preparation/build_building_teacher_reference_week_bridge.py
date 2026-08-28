from __future__ import annotations

from vienna_teacher_paths import (
    PAPER_MODEL_REVIEW,
    REPOSITORY_ROOT,
    TEACHER_DATASET,
)

import argparse
import json
from pathlib import Path
import sys

import pandas as pd

if str(REPOSITORY_ROOT) not in sys.path:
    sys.path.insert(0, str(REPOSITORY_ROOT))

from Settings.technical.building_calibration import make_building_calibration_config
from Technical_model.technologies.buildings.calibration.from_repo import build_teacher_input_bundle


OUTPUT_DIR = TEACHER_DATASET
TARGET_CONTROL_MODE = "reference"


def _load_selected_runs(*, experiment_id: str) -> list[dict[str, object]]:
    cfg = make_building_calibration_config()
    teacher_runs_dir = Path(cfg.teacher_runs_output_dir).resolve()
    selected: list[dict[str, object]] = []
    for meta_path in sorted(teacher_runs_dir.glob(f"*/{experiment_id}/teacher.meta.json")):
        payload = json.loads(meta_path.read_text(encoding="utf-8"))
        if str(payload.get("experiment_id")) != experiment_id:
            continue
        if str(payload.get("control_mode")) != TARGET_CONTROL_MODE:
            continue
        selected.append(payload)
    if not selected:
        raise FileNotFoundError(
            "[building_teacher_bridge] No source runs found for "
            f"experiment_id='{experiment_id}', control_mode='{TARGET_CONTROL_MODE}'."
        )
    return selected


def _load_cohort_context() -> pd.DataFrame:
    bundle = build_teacher_input_bundle()
    rows: list[dict[str, object]] = []
    for cohort in bundle.cohorts:
        rows.append(
            {
                "cohort_id": str(cohort.cohort_id),
                "sector": str(cohort.sector),
                "construction_period": str(cohort.construction_period),
                "cohort_represented_gfa_m2": float(cohort.represented_gfa_m2),
                "annual_space_heat_target_gwh": float(cohort.annual_space_heat_target_kwh) / 1_000_000.0,
                "annual_hotwater_target_gwh": float(cohort.annual_hotwater_target_kwh) / 1_000_000.0,
            }
        )
    out = pd.DataFrame(rows)
    if out["cohort_id"].duplicated().any():
        raise ValueError("[building_teacher_bridge] Duplicate cohort_id in teacher input bundle.")
    return out


def _build_cohort_hourly_export(selected_runs: list[dict[str, object]], cohort_context: pd.DataFrame) -> pd.DataFrame:
    rows: list[pd.DataFrame] = []
    for item in selected_runs:
        cohort_id = str(item["cohort_id"])
        csv_path = Path(str(item["plausibility_hourly_csv_path"])).resolve()
        if not csv_path.exists():
            raise FileNotFoundError(f"[building_teacher_bridge] Missing teacher CSV: {csv_path}")
        frame = pd.read_csv(
            csv_path,
            usecols=[
                "timestamp_local",
                "zone_total_heating_rate_w_scaled_to_cohort",
                "zone_total_cooling_rate_w_scaled_to_cohort",
                "site_outdoor_air_drybulb_c",
                "heating_setpoint_c",
                "cooling_setpoint_c",
                "internal_gains_w_m2",
                "infiltration_ach",
                "ventilation_ach",
                "epw_ghi_wh_m2",
                "epw_dni_wh_m2",
                "epw_dhi_wh_m2",
            ],
            parse_dates=["timestamp_local"],
        )
        if frame.empty:
            raise ValueError(f"[building_teacher_bridge] Empty teacher CSV: {csv_path}")
        part = pd.DataFrame(
            {
                "timestamp_local": frame["timestamp_local"],
                "cohort_id": cohort_id,
                "source_teacher_run": str(csv_path),
                "source_teacher_experiment": str(item["experiment_id"]),
                "space_heating_kwh": pd.to_numeric(
                    frame["zone_total_heating_rate_w_scaled_to_cohort"], errors="raise"
                )
                / 1000.0,
                "cooling_kwh": pd.to_numeric(
                    frame["zone_total_cooling_rate_w_scaled_to_cohort"], errors="raise"
                )
                / 1000.0,
                "outdoor_temperature_c": pd.to_numeric(frame["site_outdoor_air_drybulb_c"], errors="raise"),
                "heating_setpoint_c": pd.to_numeric(frame["heating_setpoint_c"], errors="raise"),
                "cooling_setpoint_c": pd.to_numeric(frame["cooling_setpoint_c"], errors="raise"),
                "internal_gains_w_m2": pd.to_numeric(frame["internal_gains_w_m2"], errors="raise"),
                "infiltration_ach": pd.to_numeric(frame["infiltration_ach"], errors="raise"),
                "ventilation_ach": pd.to_numeric(frame["ventilation_ach"], errors="raise"),
                "epw_ghi_wh_m2": pd.to_numeric(frame["epw_ghi_wh_m2"], errors="raise"),
                "epw_dni_wh_m2": pd.to_numeric(frame["epw_dni_wh_m2"], errors="raise"),
                "epw_dhi_wh_m2": pd.to_numeric(frame["epw_dhi_wh_m2"], errors="raise"),
            }
        )
        rows.append(part)
    out = pd.concat(rows, ignore_index=True)
    out = out.merge(cohort_context, on="cohort_id", how="left", validate="many_to_one")
    if out[["sector", "construction_period", "cohort_represented_gfa_m2"]].isna().any().any():
        raise ValueError("[building_teacher_bridge] Cohort context merge produced missing values.")
    return out.sort_values(["cohort_id", "timestamp_local"]).reset_index(drop=True)


def _build_city_hourly_export(cohort_hourly: pd.DataFrame) -> pd.DataFrame:
    experiment_id = str(cohort_hourly["source_teacher_experiment"].iloc[0])
    grouped = (
        cohort_hourly.groupby("timestamp_local", as_index=False)
        .agg(
            city_space_heating_kwh=("space_heating_kwh", "sum"),
            city_cooling_kwh=("cooling_kwh", "sum"),
            mean_outdoor_temperature_c=("outdoor_temperature_c", "mean"),
        )
        .sort_values("timestamp_local")
        .reset_index(drop=True)
    )
    grouped["source_teacher_experiment"] = experiment_id
    n_hours = int(len(grouped))
    if n_hours == 8760:
        grouped["time_scope_note"] = (
            f"Full-year raw EnergyPlus teacher output '{experiment_id}'; annual totals remain teacher values and are not yet active MES demand anchors."
        )
    else:
        grouped["time_scope_note"] = (
            f"Representative period '{experiment_id}' only; not a promoted 8760 annual city demand artifact."
        )
    return grouped


def _build_summary(cohort_hourly: pd.DataFrame, city_hourly: pd.DataFrame) -> pd.DataFrame:
    by_cohort = (
        cohort_hourly.groupby(["cohort_id", "sector", "construction_period", "cohort_represented_gfa_m2"], as_index=False)
        .agg(
            reference_week_space_heating_mwh=("space_heating_kwh", lambda s: float(pd.Series(s).sum() / 1000.0)),
            reference_week_cooling_mwh=("cooling_kwh", lambda s: float(pd.Series(s).sum() / 1000.0)),
        )
        .sort_values(["sector", "cohort_id"])
        .reset_index(drop=True)
    )
    by_cohort["reference_week_space_heating_kwh_per_m2"] = (
        by_cohort["reference_week_space_heating_mwh"] * 1000.0 / by_cohort["cohort_represented_gfa_m2"]
    )
    by_cohort["reference_week_cooling_kwh_per_m2"] = (
        by_cohort["reference_week_cooling_mwh"] * 1000.0 / by_cohort["cohort_represented_gfa_m2"]
    )
    city_row = pd.DataFrame(
        [
            {
                "cohort_id": "CITY_TOTAL",
                "sector": "all",
                "construction_period": "all",
                "cohort_represented_gfa_m2": float(cohort_hourly["cohort_represented_gfa_m2"].drop_duplicates().sum()),
                "reference_week_space_heating_mwh": float(city_hourly["city_space_heating_kwh"].sum() / 1000.0),
                "reference_week_cooling_mwh": float(city_hourly["city_cooling_kwh"].sum() / 1000.0),
                "reference_week_space_heating_kwh_per_m2": float(
                    city_hourly["city_space_heating_kwh"].sum()
                    / cohort_hourly["cohort_represented_gfa_m2"].drop_duplicates().sum()
                ),
                "reference_week_cooling_kwh_per_m2": float(
                    city_hourly["city_cooling_kwh"].sum()
                    / cohort_hourly["cohort_represented_gfa_m2"].drop_duplicates().sum()
                ),
            }
        ]
    )
    return pd.concat([by_cohort, city_row], ignore_index=True)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Build processed Vienna MES bridge artifacts from canonical EnergyPlus teacher runs."
    )
    parser.add_argument(
        "--experiment-id",
        default="winter_reference_week",
        help="Teacher experiment_id to export, e.g. winter_reference_week or summer_reference_week.",
    )
    args = parser.parse_args()
    experiment_id = str(args.experiment_id).strip()
    if not experiment_id:
        raise ValueError("[building_teacher_bridge] --experiment-id must be a non-empty string.")

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    selected_runs = _load_selected_runs(experiment_id=experiment_id)
    cohort_context = _load_cohort_context()
    cohort_hourly = _build_cohort_hourly_export(selected_runs, cohort_context)
    city_hourly = _build_city_hourly_export(cohort_hourly)
    summary = _build_summary(cohort_hourly, city_hourly)
    cohort_hourly.to_csv(
        OUTPUT_DIR / f"building_teacher_{experiment_id}_cohort_hourly.csv.gz",
        index=False,
        compression="gzip",
    )
    city_hourly.to_csv(
        OUTPUT_DIR / f"building_teacher_{experiment_id}_city_hourly.csv.gz",
        index=False,
        compression="gzip",
    )
    summary.to_csv(OUTPUT_DIR / f"building_teacher_{experiment_id}_summary.csv", index=False)


if __name__ == "__main__":
    main()
