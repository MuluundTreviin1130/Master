from __future__ import annotations

from typing import Iterable

import pandas as pd


REQUIRED_HOURLY_MECHANISM_COLUMNS: tuple[str, ...] = (
    "case_label",
    "run_dir",
    "timestamp",
    "cohort_key",
    "cohort_member_count",
    "cohort_floor_area_m2",
    "thermflex_constant_lower_bound_c",
    "thermflex_max_flex_duration_h",
    "thermflex_max_events_per_day",
    "cohort_q_heat_kwh",
    "cohort_q_heat_ref_kwh",
    "cohort_q_delta_kwh",
    "cohort_flex_active_member_count",
    "cohort_flex_active_member_share",
    "cohort_event_start_count",
    "cohort_temperature_violation_degree_h",
    "cohort_t_in_weighted_mean_c",
    "cohort_t_in_member_min_c",
    "cohort_t_in_member_max_c",
    "cohort_preheat_extra_kwh",
    "cohort_cutback_shed_kwh",
)


BUILDER_METADATA_COLUMNS: tuple[str, ...] = (
    "source_bundle_name",
    "source_hourly_csv",
    "hour_of_day",
    "day_of_year",
    "month",
    "split_group_run",
    "split_group_case",
    "split_group_bundle",
)


NUMERIC_FEATURE_COLUMNS: tuple[str, ...] = (
    "cohort_member_count",
    "cohort_floor_area_m2",
    "thermflex_constant_lower_bound_c",
    "thermflex_max_flex_duration_h",
    "thermflex_max_events_per_day",
    "policy_tau_h",
    "policy_dispatch_horizon_h",
    "policy_dispatch_rolling_commit_h",
    "policy_dispatch_lookahead_h",
    "policy_dispatch_is_rolling",
    "constant_setpoint_c",
    "day_setpoint_c",
    "night_setpoint_c",
    "thermflex_day_lower_bound_c",
    "thermflex_night_lower_bound_c",
    "thermflex_use_event_response_bounds",
    "thermflex_enforce_event_peak_bounds",
    "thermflex_enforce_event_energy_bounds",
    "thermflex_enforce_recovery_cooldown",
    "thermflex_constrain_upper_temperature",
    "hour_of_day",
    "day_of_year",
    "month",
    "t_outdoor_c",
    "irradiance_proxy",
    "solargains_proxy",
    "mc_auction_eur_mwh",
    "gas_price_eur_mwh_fuel",
    "co2_price_eur_tco2",
    "space_heat_kwh",
    "hotwater_kwh",
    "dh_space_heat_kwh",
    "dh_total_kwh",
    "cohort_q_heat_ref_kwh",
)


ENGINEERED_FEATURE_COLUMNS: tuple[str, ...] = (
    "hour_of_day_sin",
    "hour_of_day_cos",
    "day_of_year_sin",
    "day_of_year_cos",
    "irradiance_per_dh_space_heat",
    "solargains_per_dh_space_heat",
    "cohort_space_heat_share_of_dh",
    "day_thermflex_temperature_band_k",
    "night_thermflex_temperature_band_k",
)


THERMAL_ARCHETYPE_FEATURE_COLUMNS: tuple[str, ...] = (
    "archetype_is_residential",
    "archetype_construction_period_rank",
    "archetype_u_wall_w_per_m2k",
    "archetype_u_window_w_per_m2k",
    "archetype_u_roof_w_per_m2k",
    "archetype_u_floor_w_per_m2k",
    "archetype_wall_area_per_gfa",
    "archetype_window_area_per_gfa",
    "archetype_roof_area_per_gfa",
    "archetype_floor_exposed_per_gfa",
    "archetype_conditioned_floor_share_of_gfa",
    "archetype_c_th_wh_per_m2k",
    "archetype_t_min_c",
    "archetype_t_max_c",
    "archetype_fitted_total_loss_w_per_k",
    "archetype_fitted_transmission_loss_w_per_k",
    "archetype_fitted_infiltration_loss_w_per_k",
    "archetype_fitted_effective_heat_capacity_wh_per_k",
    "archetype_fitted_tau_h",
    "archetype_fitted_total_loss_w_per_m2k",
    "archetype_fitted_effective_heat_capacity_wh_per_m2k",
    "archetype_preheat_added_energy_kwh",
    "archetype_preheat_peak_excess_kw",
    "archetype_cutback_shed_energy_kwh",
    "archetype_cutback_peak_shed_kw",
    "archetype_recovery_rebound_energy_kwh",
    "archetype_recovery_peak_rebound_kw",
    "archetype_recovery_time_to_reference_h",
)


CATEGORICAL_FEATURE_COLUMNS: tuple[str, ...] = (
    "case_label",
    "cohort_key",
    "control_mode",
    "reference_control_mode",
)


TARGET_COLUMNS: tuple[str, ...] = (
    "cohort_q_delta_kwh",
    "cohort_preheat_extra_kwh",
    "cohort_cutback_shed_kwh",
    "cohort_temperature_violation_degree_h",
    "cohort_flex_active_member_share",
    "cohort_t_in_weighted_mean_c",
)


INTENSIVE_TARGET_COLUMNS: tuple[str, ...] = (
    "cohort_q_delta_wh_per_m2",
    "cohort_preheat_extra_wh_per_m2",
    "cohort_cutback_shed_wh_per_m2",
)


MECHANISM_CORE_TARGET_COLUMNS: tuple[str, ...] = TARGET_COLUMNS


MECHANISM_CORE_EVENT_TARGET_COLUMNS: tuple[str, ...] = (
    *TARGET_COLUMNS,
    "cohort_event_start_count",
)


MECHANISM_ENERGY_TARGET_COLUMNS: tuple[str, ...] = (
    "cohort_q_delta_kwh",
    "cohort_preheat_extra_kwh",
    "cohort_cutback_shed_kwh",
    "cohort_temperature_violation_degree_h",
)


MECHANISM_ENERGY_INTENSIVE_TARGET_COLUMNS: tuple[str, ...] = (
    "cohort_q_delta_wh_per_m2",
    "cohort_preheat_extra_wh_per_m2",
    "cohort_cutback_shed_wh_per_m2",
    "cohort_temperature_violation_degree_h",
)


MECHANISM_ENERGY_STATE_INTENSIVE_TARGET_COLUMNS: tuple[str, ...] = (
    "cohort_q_delta_wh_per_m2",
    "cohort_preheat_extra_wh_per_m2",
    "cohort_cutback_shed_wh_per_m2",
    "cohort_temperature_violation_degree_h",
    "cohort_flex_active_member_share",
    "cohort_event_start_count",
    "cohort_t_in_weighted_mean_c",
)


def validate_hourly_mechanism_frame(frame: pd.DataFrame, *, source_label: str) -> None:
    missing = sorted(set(REQUIRED_HOURLY_MECHANISM_COLUMNS).difference(frame.columns))
    if missing:
        raise ValueError(
            "[thermflex_hourly_mechanism] missing required hourly truth columns in "
            f"{source_label}: {', '.join(missing)}"
        )

    if frame.empty:
        raise ValueError(
            f"[thermflex_hourly_mechanism] hourly truth frame is empty for source {source_label}."
        )

    for numeric_column in REQUIRED_HOURLY_MECHANISM_COLUMNS:
        if numeric_column in {"case_label", "run_dir", "timestamp", "cohort_key"}:
            continue
        pd.to_numeric(frame[numeric_column], errors="raise")


def resolved_numeric_feature_columns() -> tuple[str, ...]:
    return tuple(NUMERIC_FEATURE_COLUMNS) + tuple(ENGINEERED_FEATURE_COLUMNS)


def iter_all_feature_columns() -> Iterable[str]:
    yield from NUMERIC_FEATURE_COLUMNS
    yield from ENGINEERED_FEATURE_COLUMNS
    yield from THERMAL_ARCHETYPE_FEATURE_COLUMNS
    yield from CATEGORICAL_FEATURE_COLUMNS
