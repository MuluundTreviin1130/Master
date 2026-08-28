from __future__ import annotations

from vienna_teacher_paths import (
    PAPER_MODEL_REVIEW,
    REPOSITORY_ROOT,
    TEACHER_DATASET,
)

import json
from pathlib import Path

import pandas as pd


REVIEW_DIR = PAPER_MODEL_REVIEW
MODEL_DIR = REPOSITORY_ROOT / "Learning" / "models" / "building_response_v1_reference"
DATASET_META_PATH = REPOSITORY_ROOT / "Learning" / "datasets" / "building_response_v1" / "building_response_teacher_hourly.meta.json"
TEACHER_COVERAGE_PATH = REVIEW_DIR / "building_teacher_artifact_coverage.csv"


def _load_metrics() -> tuple[dict, pd.DataFrame, pd.DataFrame]:
    metrics = json.loads((MODEL_DIR / "metrics.json").read_text(encoding="utf-8"))
    grouped = pd.read_csv(MODEL_DIR / "aggregate_kpi_metrics_by_group.csv")
    rollout = pd.read_csv(MODEL_DIR / "rollout_metrics_by_group.csv")
    return metrics, grouped, rollout


def _load_teacher_coverage() -> pd.DataFrame:
    return pd.read_csv(TEACHER_COVERAGE_PATH)


def _build_target_status(metrics: dict, teacher_coverage: pd.DataFrame) -> pd.DataFrame:
    trained_targets = {str(row["target"]) for row in metrics["one_step"]}
    meta = json.loads(DATASET_META_PATH.read_text(encoding="utf-8"))
    output_columns = {str(col) for col in meta["output_columns"]}
    has_heating_teacher_column = bool(teacher_coverage["has_space_heating_column"].astype(bool).all())
    has_cooling_teacher_column = bool(teacher_coverage["has_cooling_column"].astype(bool).all())
    rows = []
    for target_name, source_column, status_note in [
        ("space_heating_surrogate_target", "zone_total_heating_kwh", "Directly trained target in the active building-response model."),
        ("cooling_surrogate_target", "zone_total_cooling_kwh", "Present in teacher artifacts but not currently promoted as trained target in the active building-response model."),
        ("dhw_surrogate_target", "domestic_hot_water_kwh", "Not present as promoted teacher-output target in the active building-response model."),
    ]:
        teacher_column_present = source_column in output_columns
        if target_name == "space_heating_surrogate_target":
            teacher_column_present = has_heating_teacher_column
        elif target_name == "cooling_surrogate_target":
            teacher_column_present = has_cooling_teacher_column
        rows.append(
            {
                "target_family": target_name,
                "teacher_column_present": teacher_column_present,
                "active_model_trained": source_column in trained_targets,
                "status_note": status_note,
            }
        )
    return pd.DataFrame(rows)


def _build_cohort_readiness(grouped: pd.DataFrame, rollout: pd.DataFrame) -> pd.DataFrame:
    heat_rows = grouped.loc[
        (grouped["group_column"] == "cohort_id") & (grouped["kpi"] == "total__zone_total_heating_kwh"),
        ["group_value", "mae", "rmse", "r2", "n_teacher_runs"],
    ].rename(
        columns={
            "group_value": "cohort_id",
            "mae": "aggregate_heat_mae_kwh",
            "rmse": "aggregate_heat_rmse_kwh",
            "r2": "aggregate_heat_r2",
            "n_teacher_runs": "aggregate_heat_teacher_runs",
        }
    )
    rollout_rows = rollout.loc[
        rollout["group_column"] == "cohort_id",
        ["group_value", "t_in_mae_c", "q_heat_mae_kwh", "comfort_false_negative_lower", "comfort_false_negative_upper", "rows"],
    ].rename(
        columns={
            "group_value": "cohort_id",
            "rows": "rollout_rows",
        }
    )
    merged = heat_rows.merge(rollout_rows, on="cohort_id", how="outer", validate="one_to_one")
    merged["heating_surrogate_ready_for_city_export"] = False
    merged["blocking_reason"] = (
        "Current model is still trained on representative-day / event teacher families and does not yet provide "
        "a promoted annual demand-export contract, even where heating metrics are strong."
    )
    return merged.sort_values("cohort_id").reset_index(drop=True)


def _build_summary(target_status: pd.DataFrame, cohort_status: pd.DataFrame) -> pd.DataFrame:
    cooling_trained = bool(target_status.loc[target_status["target_family"] == "cooling_surrogate_target", "active_model_trained"].iloc[0])
    dhw_trained = bool(target_status.loc[target_status["target_family"] == "dhw_surrogate_target", "active_model_trained"].iloc[0])
    rows = [
        {
            "question": "heating_target_trained",
            "value": True,
            "note": "Heating is an active trained target in the current building-response model.",
        },
        {
            "question": "cooling_target_trained",
            "value": cooling_trained,
            "note": "Cooling exists in teacher artifacts but is not currently part of the trained target set.",
        },
        {
            "question": "dhw_target_trained",
            "value": dhw_trained,
            "note": "DHW is not currently part of the active teacher/surrogate target contract.",
        },
        {
            "question": "city_scale_annual_export_ready",
            "value": False,
            "note": "Even strong heating metrics do not yet imply a promoted annual city-scale export path.",
        },
        {
            "question": "weakest_heating_cohort_by_rollout_q_heat_mae",
            "value": str(cohort_status.sort_values("q_heat_mae_kwh", ascending=False).iloc[0]["cohort_id"]),
            "note": "Use this cohort as one of the first focal points when broadening heating/cooling surrogate coverage.",
        },
    ]
    return pd.DataFrame(rows)


def main() -> None:
    REVIEW_DIR.mkdir(parents=True, exist_ok=True)
    metrics, grouped, rollout = _load_metrics()
    teacher_coverage = _load_teacher_coverage()
    target_status = _build_target_status(metrics, teacher_coverage)
    cohort_status = _build_cohort_readiness(grouped, rollout)
    summary = _build_summary(target_status, cohort_status)
    target_status.to_csv(REVIEW_DIR / "building_surrogate_target_status.csv", index=False)
    cohort_status.to_csv(REVIEW_DIR / "building_surrogate_cohort_training_readiness.csv", index=False)
    summary.to_csv(REVIEW_DIR / "building_surrogate_training_summary.csv", index=False)


if __name__ == "__main__":
    main()

