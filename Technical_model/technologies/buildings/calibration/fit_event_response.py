from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

from Settings.technical.building_calibration import make_building_calibration_config
from Technical_model.technologies.buildings.calibration.schemas import CalibrationEventResponseResult


_REQUIRED_HOURLY_COLUMNS = (
    "timestamp_local",
    "zone_mean_air_temperature_c",
    "zone_total_heating_rate_w",
)


def _require_existing_file(path: Path, *, label: str) -> Path:
    resolved = path.resolve()
    if not resolved.exists():
        raise FileNotFoundError(f"[building_calibration.fit_event_response] Missing {label}: {resolved}")
    if not resolved.is_file():
        raise FileNotFoundError(f"[building_calibration.fit_event_response] Expected file for {label}, got: {resolved}")
    return resolved


def _load_json(path: Path, *, label: str) -> dict:
    resolved = _require_existing_file(path, label=label)
    return json.loads(resolved.read_text(encoding="utf-8"))


def _load_experiment_index() -> dict[str, dict]:
    cfg = make_building_calibration_config()
    payload = _load_json(Path(cfg.experiment_library_output_json), label="experiment_library_output_json")
    experiments = payload.get("experiments", [])
    by_id: dict[str, dict] = {}
    for experiment in experiments:
        experiment_id = str(experiment["experiment_id"])
        if experiment_id in by_id:
            raise ValueError(
                f"[building_calibration.fit_event_response] Duplicate experiment_id in experiment library: {experiment_id}"
            )
        by_id[experiment_id] = dict(experiment)
    return by_id


def _load_teacher_hourly(*, cohort_id: str, experiment_id: str) -> pd.DataFrame:
    cfg = make_building_calibration_config()
    run_dir = Path(cfg.teacher_runs_output_dir).resolve() / cohort_id / experiment_id
    path = _require_existing_file(run_dir / str(cfg.teacher_plausibility_hourly_filename), label=f"teacher_hourly[{cohort_id}/{experiment_id}]")
    df = pd.read_csv(path, parse_dates=["timestamp_local"])
    missing = [col for col in _REQUIRED_HOURLY_COLUMNS if col not in df.columns]
    if missing:
        raise KeyError(
            "[building_calibration.fit_event_response] Teacher hourly file is missing columns "
            f"for cohort='{cohort_id}', experiment='{experiment_id}': {missing}"
        )
    return df.sort_values("timestamp_local").reset_index(drop=True)


def _build_event_window_masks(df: pd.DataFrame, experiment: dict) -> tuple[pd.Series, pd.Series, pd.Timestamp, pd.Timestamp, pd.Timestamp]:
    start_local = pd.Timestamp(str(experiment["start_local"]))
    event_start = start_local + pd.Timedelta(hours=int(experiment["event_start_offset_h"]))
    event_end = event_start + pd.Timedelta(hours=int(experiment["event_duration_h"]))
    observation_end = event_end + pd.Timedelta(hours=int(experiment["post_event_observation_h"]))
    ts = pd.to_datetime(df["timestamp_local"])
    event_mask = (ts >= event_start) & (ts < event_end)
    post_mask = (ts >= event_end) & (ts < observation_end)
    if int(event_mask.sum()) != int(experiment["event_duration_h"]):
        raise ValueError(
            "[building_calibration.fit_event_response] Event window coverage mismatch for "
            f"experiment='{experiment['experiment_id']}'."
        )
    if int(experiment["post_event_observation_h"]) > 0 and int(post_mask.sum()) != int(experiment["post_event_observation_h"]):
        raise ValueError(
            "[building_calibration.fit_event_response] Post-event observation coverage mismatch for "
            f"experiment='{experiment['experiment_id']}'."
        )
    return event_mask, post_mask, event_start, event_end, observation_end


def _merge_event_with_reference(reference_df: pd.DataFrame, event_df: pd.DataFrame) -> pd.DataFrame:
    merged = reference_df[["timestamp_local", "zone_mean_air_temperature_c", "zone_total_heating_rate_w"]].merge(
        event_df[["timestamp_local", "zone_mean_air_temperature_c", "zone_total_heating_rate_w"]],
        on="timestamp_local",
        how="inner",
        suffixes=("_ref", "_event"),
    )
    if len(merged) != len(event_df):
        raise ValueError(
            "[building_calibration.fit_event_response] Event run does not align cleanly with the reference timestamps."
        )
    merged["delta_heating_w"] = merged["zone_total_heating_rate_w_event"] - merged["zone_total_heating_rate_w_ref"]
    merged["delta_temperature_c"] = (
        merged["zone_mean_air_temperature_c_event"] - merged["zone_mean_air_temperature_c_ref"]
    )
    return merged


def _safe_last(series: pd.Series) -> float:
    if len(series) == 0:
        raise ValueError("[building_calibration.fit_event_response] Expected non-empty event series.")
    return float(series.iloc[-1])


def fit_event_response_for_cohort(cohort_id: str) -> CalibrationEventResponseResult:
    cfg = make_building_calibration_config()
    resolved_cohort = str(cohort_id).strip()
    if not resolved_cohort:
        raise ValueError("[building_calibration.fit_event_response] cohort_id must be non-empty.")

    experiments = _load_experiment_index()
    preheat_ref_id = str(cfg.event_response_preheat_reference_experiment_id)
    cutback_ref_id = str(cfg.event_response_cutback_reference_experiment_id)
    recovery_ref_id = str(cfg.event_response_recovery_reference_experiment_id)
    preheat_id = str(cfg.event_response_preheat_experiment_id)
    cutback_id = str(cfg.event_response_cutback_experiment_id)
    recovery_id = str(cfg.event_response_recovery_experiment_id)
    required = (
        preheat_ref_id,
        cutback_ref_id,
        recovery_ref_id,
        preheat_id,
        cutback_id,
        recovery_id,
    )
    missing = [exp_id for exp_id in required if exp_id not in experiments]
    if missing:
        raise KeyError(f"[building_calibration.fit_event_response] Missing required experiments: {missing}")

    preheat_reference_df = _load_teacher_hourly(cohort_id=resolved_cohort, experiment_id=preheat_ref_id)
    preheat_df = _load_teacher_hourly(cohort_id=resolved_cohort, experiment_id=preheat_id)
    preheat_merged = _merge_event_with_reference(preheat_reference_df, preheat_df)
    preheat_event_mask, preheat_post_mask, _, _, _ = _build_event_window_masks(preheat_merged, experiments[preheat_id])

    cutback_reference_df = _load_teacher_hourly(cohort_id=resolved_cohort, experiment_id=cutback_ref_id)
    cutback_df = _load_teacher_hourly(cohort_id=resolved_cohort, experiment_id=cutback_id)
    cutback_merged = _merge_event_with_reference(cutback_reference_df, cutback_df)
    cutback_event_mask, _, _, _, _ = _build_event_window_masks(cutback_merged, experiments[cutback_id])

    recovery_reference_df = _load_teacher_hourly(cohort_id=resolved_cohort, experiment_id=recovery_ref_id)
    recovery_df = _load_teacher_hourly(cohort_id=resolved_cohort, experiment_id=recovery_id)
    recovery_merged = _merge_event_with_reference(recovery_reference_df, recovery_df)
    recovery_event_mask, recovery_post_mask, _, _, _ = _build_event_window_masks(recovery_merged, experiments[recovery_id])

    preheat_added_energy_kwh = float(
        preheat_merged.loc[preheat_event_mask, "delta_heating_w"].clip(lower=0.0).sum() / 1000.0
    )
    preheat_peak_excess_kw = float(
        preheat_merged.loc[preheat_event_mask, "delta_heating_w"].max() / 1000.0
    )
    preheat_temperature_uplift_max_c = float(
        preheat_merged.loc[preheat_event_mask, "delta_temperature_c"].max()
    )
    preheat_temperature_uplift_end_c = _safe_last(
        preheat_merged.loc[preheat_event_mask, "delta_temperature_c"]
    )
    preheat_post_event_payback_kwh = float(
        (-preheat_merged.loc[preheat_post_mask, "delta_heating_w"].clip(upper=0.0)).sum() / 1000.0
    )

    cutback_shed_energy_kwh = float(
        (-cutback_merged.loc[cutback_event_mask, "delta_heating_w"].clip(upper=0.0)).sum() / 1000.0
    )
    cutback_peak_shed_kw = float(
        (-cutback_merged.loc[cutback_event_mask, "delta_heating_w"]).max() / 1000.0
    )
    cutback_temperature_drop_max_c = float(
        (-cutback_merged.loc[cutback_event_mask, "delta_temperature_c"]).max()
    )
    cutback_temperature_drop_end_c = float(
        -_safe_last(cutback_merged.loc[cutback_event_mask, "delta_temperature_c"])
    )

    recovery_rebound_energy_kwh = float(
        recovery_merged.loc[recovery_post_mask, "delta_heating_w"].clip(lower=0.0).sum() / 1000.0
    )
    recovery_peak_rebound_kw = float(
        recovery_merged.loc[recovery_post_mask, "delta_heating_w"].max() / 1000.0
    )
    recovery_overshoot_max_c = float(
        recovery_merged.loc[recovery_post_mask, "delta_temperature_c"].max()
    )
    recovery_temperature_gap_at_event_end_c = float(
        -_safe_last(recovery_merged.loc[recovery_event_mask, "delta_temperature_c"])
    )
    recovery_temperature_gap_after_observation_c = float(
        -_safe_last(recovery_merged.loc[recovery_post_mask, "delta_temperature_c"])
    )

    tolerance_c = float(cfg.event_response_temperature_recovery_tolerance_c)
    if tolerance_c < 0.0:
        raise ValueError(
            "[building_calibration.fit_event_response] event_response_temperature_recovery_tolerance_c must be >= 0."
        )
    recovered = recovery_merged.loc[recovery_post_mask, "delta_temperature_c"] >= -tolerance_c
    if bool(recovered.any()):
        first_idx = int(np.argmax(recovered.to_numpy(dtype=bool)))
        recovery_time_to_reference_h = float(first_idx + 1)
    else:
        recovery_time_to_reference_h = float(cfg.event_response_unrecovered_sentinel_h)

    return CalibrationEventResponseResult(
        cohort_id=resolved_cohort,
        preheat_reference_experiment_id=preheat_ref_id,
        cutback_reference_experiment_id=cutback_ref_id,
        recovery_reference_experiment_id=recovery_ref_id,
        preheat_experiment_id=preheat_id,
        cutback_experiment_id=cutback_id,
        recovery_experiment_id=recovery_id,
        preheat_added_energy_kwh=preheat_added_energy_kwh,
        preheat_peak_excess_kw=preheat_peak_excess_kw,
        preheat_temperature_uplift_max_c=preheat_temperature_uplift_max_c,
        preheat_temperature_uplift_end_c=preheat_temperature_uplift_end_c,
        preheat_post_event_payback_kwh=preheat_post_event_payback_kwh,
        cutback_shed_energy_kwh=cutback_shed_energy_kwh,
        cutback_peak_shed_kw=cutback_peak_shed_kw,
        cutback_temperature_drop_max_c=cutback_temperature_drop_max_c,
        cutback_temperature_drop_end_c=cutback_temperature_drop_end_c,
        recovery_rebound_energy_kwh=recovery_rebound_energy_kwh,
        recovery_peak_rebound_kw=recovery_peak_rebound_kw,
        recovery_overshoot_max_c=recovery_overshoot_max_c,
        recovery_temperature_gap_at_event_end_c=recovery_temperature_gap_at_event_end_c,
        recovery_temperature_gap_after_observation_c=recovery_temperature_gap_after_observation_c,
        recovery_time_to_reference_h=recovery_time_to_reference_h,
        notes=[
            "Each event metric is measured against an explicit cold-year baseline run of matching duration and local timestamps.",
            "Rebound energy is the positive post-event heating excess of the recovery run versus the reference run.",
            "Recovery time is the first post-event hour where the event run reaches the reference indoor temperature within the configured tolerance.",
        ],
    )


def write_event_response_fit_result(result: CalibrationEventResponseResult) -> Path:
    cfg = make_building_calibration_config()
    out_dir = Path(cfg.event_response_fit_output_dir).resolve() / result.cohort_id
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / "event_response_fit.json"
    out_path.write_text(json.dumps(result.to_dict(), indent=2), encoding="utf-8")
    return out_path
