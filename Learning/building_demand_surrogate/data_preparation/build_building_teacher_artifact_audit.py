from __future__ import annotations

from vienna_teacher_paths import (
    PAPER_MODEL_REVIEW,
    REPOSITORY_ROOT,
    TEACHER_DATASET,
)

import json
from pathlib import Path
import sys

import pandas as pd

if str(REPOSITORY_ROOT) not in sys.path:
    sys.path.insert(0, str(REPOSITORY_ROOT))

from Technical_model.technologies.buildings.calibration.from_repo import build_teacher_input_bundle


DATASET_META_PATH = REPOSITORY_ROOT / "Learning" / "datasets" / "building_response_v1" / "building_response_teacher_hourly.meta.json"
REVIEW_DIR = PAPER_MODEL_REVIEW


def _build_cohort_targets() -> pd.DataFrame:
    bundle = build_teacher_input_bundle()
    rows: list[dict[str, object]] = []
    for cohort in bundle.cohorts:
        rows.append(
            {
                "cohort_id": cohort.cohort_id,
                "sector": cohort.sector,
                "construction_period": cohort.construction_period,
                "represented_gfa_m2": float(cohort.represented_gfa_m2),
                "include_hotwater": bool(cohort.include_hotwater),
                "annual_heat_target_gwh": float(cohort.annual_heat_target_kwh) / 1_000_000.0,
                "annual_space_heat_target_gwh": float(cohort.annual_space_heat_target_kwh) / 1_000_000.0,
                "annual_hotwater_target_gwh": float(cohort.annual_hotwater_target_kwh) / 1_000_000.0,
                "annual_electricity_target_gwh": float(cohort.annual_electricity_target_kwh) / 1_000_000.0,
                "source": "Technical_model.technologies.buildings.calibration.from_repo.build_teacher_input_bundle",
            }
        )
    return pd.DataFrame(rows).sort_values(["sector", "construction_period", "cohort_id"]).reset_index(drop=True)


def _build_teacher_run_coverage() -> pd.DataFrame:
    meta = json.loads(DATASET_META_PATH.read_text(encoding="utf-8"))
    rows: list[dict[str, object]] = []
    for item in meta["source_runs"]:
        csv_path = Path(str(item["plausibility_hourly_csv_path"]))
        frame = pd.read_csv(csv_path, nrows=1)
        columns = set(str(col) for col in frame.columns)
        rows.append(
            {
                "cohort_id": str(item["cohort_id"]),
                "experiment_id": str(item["experiment_id"]),
                "control_mode": str(item["control_mode"]),
                "represented_gfa_m2": float(item["cohort_represented_gfa_m2"]),
                "reference_floor_area_m2": float(item["reference_floor_area_m2"]),
                "hours_in_artifact": int(sum(1 for _ in csv_path.open("r", encoding="utf-8")) - 1),
                "has_space_heating_column": "zone_total_heating_kwh" in columns,
                "has_cooling_column": "zone_total_cooling_kwh" in columns,
                "has_timestamp_local": "timestamp_local" in columns,
                "has_event_columns": {"event_type", "event_active", "event_elapsed_h", "event_remaining_h"}.issubset(columns),
                "source_plausibility_hourly_csv": str(csv_path),
            }
        )
    return pd.DataFrame(rows).sort_values(["cohort_id", "experiment_id"]).reset_index(drop=True)


def _build_reference_week_summary(coverage: pd.DataFrame) -> pd.DataFrame:
    week_rows: list[dict[str, object]] = []
    reference_rows = coverage.loc[coverage["experiment_id"] == "winter_reference_week"].copy()
    for row in reference_rows.itertuples(index=False):
        csv_path = Path(str(row.source_plausibility_hourly_csv))
        frame = pd.read_csv(
            csv_path,
            usecols=["zone_total_heating_rate_w_scaled_to_cohort", "zone_total_cooling_rate_w_scaled_to_cohort"],
        )
        heating_kwh = pd.to_numeric(frame["zone_total_heating_rate_w_scaled_to_cohort"], errors="raise") / 1000.0
        cooling_kwh = pd.to_numeric(frame["zone_total_cooling_rate_w_scaled_to_cohort"], errors="raise") / 1000.0
        week_rows.append(
            {
                "cohort_id": str(row.cohort_id),
                "experiment_id": str(row.experiment_id),
                "hours_in_artifact": int(len(frame)),
                "represented_gfa_m2": float(row.represented_gfa_m2),
                "reference_week_space_heating_mwh": float(heating_kwh.sum() / 1000.0),
                "reference_week_cooling_mwh": float(cooling_kwh.sum() / 1000.0),
                "reference_week_space_heating_kwh_per_m2": float(heating_kwh.sum() / float(row.represented_gfa_m2)),
                "reference_week_cooling_kwh_per_m2": float(cooling_kwh.sum() / float(row.represented_gfa_m2)),
                "source_plausibility_hourly_csv": str(csv_path),
            }
        )
    return pd.DataFrame(week_rows).sort_values(["cohort_id"]).reset_index(drop=True)


def _build_bridge_readiness(cohort_targets: pd.DataFrame, coverage: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    for cohort in cohort_targets.itertuples(index=False):
        cohort_coverage = coverage.loc[coverage["cohort_id"] == cohort.cohort_id]
        has_reference_week = bool((cohort_coverage["experiment_id"] == "winter_reference_week").any())
        has_any_cooling = bool(cohort_coverage["has_cooling_column"].all())
        rows.append(
            {
                "cohort_id": str(cohort.cohort_id),
                "sector": str(cohort.sector),
                "has_annual_space_heat_target": float(cohort.annual_space_heat_target_gwh) > 0.0,
                "has_annual_hotwater_target": float(cohort.annual_hotwater_target_gwh) > 0.0,
                "has_reference_week_teacher_artifact": has_reference_week,
                "all_teacher_artifacts_expose_cooling": has_any_cooling,
                "direct_city_scale_8760_export_ready": False,
                "blocking_reason": (
                    "Current teacher family covers representative days, events and reference weeks, "
                    "not a promoted city-scale 8760 demand export; DHW also remains outside the active "
                    "building-response artifact contract."
                ),
            }
        )
    return pd.DataFrame(rows).sort_values(["sector", "cohort_id"]).reset_index(drop=True)


def main() -> None:
    REVIEW_DIR.mkdir(parents=True, exist_ok=True)
    cohort_targets = _build_cohort_targets()
    coverage = _build_teacher_run_coverage()
    reference_week = _build_reference_week_summary(coverage)
    readiness = _build_bridge_readiness(cohort_targets, coverage)
    cohort_targets.to_csv(REVIEW_DIR / "building_teacher_cohort_annual_targets.csv", index=False)
    coverage.to_csv(REVIEW_DIR / "building_teacher_artifact_coverage.csv", index=False)
    reference_week.to_csv(REVIEW_DIR / "building_teacher_reference_week_summary.csv", index=False)
    readiness.to_csv(REVIEW_DIR / "building_teacher_bridge_readiness.csv", index=False)


if __name__ == "__main__":
    main()

