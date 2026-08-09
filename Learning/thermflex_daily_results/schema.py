from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

import pandas as pd


SCHEMA_VERSION = "thermflex_daily_results_v1"


# These columns mirror the current explicit truth export written by
# `screen_vienna_constant_thermflex_heating_season_days.py` into
# `heating_season_day_screen.csv`. The learning layer should stay aligned with
# that export instead of inventing a parallel paper-only schema.
REQUIRED_DAILY_RESULT_COLUMNS: tuple[str, ...] = (
    "date",
    "t_outdoor_mean_c",
    "t_outdoor_min_c",
    "dh_space_heat_total_kwh",
    "dh_total_kwh",
    "irradiance_proxy_sum",
    "solargains_proxy_sum",
    "mc_auction_mean_eur_mwh",
    "gas_price_mean_eur_mwh_fuel",
    "co2_price_mean_eur_tco2",
    "dispatch_operating_cost_eur_ref",
    "dispatch_operating_cost_eur_flex",
    "co2_emissions_total_t_ref",
    "co2_emissions_total_t_flex",
    "district_gas_boiler_peak_kw_ref",
    "district_gas_boiler_peak_kw_flex",
    "district_gas_boiler_generation_kwh_ref",
    "district_gas_boiler_generation_kwh_flex",
    "thermflex_shifted_space_heat_kwh",
    "thermflex_rebound_kwh",
    "dh_total_peak_change_kw",
    "thermflex_peak_change_kw",
    "flex_case_label",
    "flex_override_name",
    "dispatch_operating_cost_eur_delta",
    "dispatch_operating_cost_pct_change",
    "co2_emissions_total_t_delta",
    "co2_emissions_total_pct_change",
    "district_gas_boiler_peak_kw_delta",
    "district_gas_boiler_peak_pct_change",
    "district_gas_boiler_generation_kwh_delta",
    "district_gas_boiler_generation_pct_change",
    "thermflex_rebound_over_shifted_pct",
    "joint_savings_score",
)


# The builder adds these columns so source tracking and grouped validation can
# later operate on complete bundles rather than isolated rows.
BUILDER_METADATA_COLUMNS: tuple[str, ...] = (
    "source_bundle_name",
    "source_bundle_run_slug",
    "source_screen_csv",
    "source_screen_kind",
    "source_snapshot_root",
    "source_schema_version",
    "bundle_row_count",
    "bundle_is_full_heating_season",
    "bundle_is_pilot",
    "split_group_bundle",
    "split_group_case",
    "split_group_month",
)


NUMERIC_DAILY_RESULT_COLUMNS: tuple[str, ...] = (
    "t_outdoor_mean_c",
    "t_outdoor_min_c",
    "dh_space_heat_total_kwh",
    "dh_total_kwh",
    "irradiance_proxy_sum",
    "solargains_proxy_sum",
    "mc_auction_mean_eur_mwh",
    "gas_price_mean_eur_mwh_fuel",
    "co2_price_mean_eur_tco2",
    "dispatch_operating_cost_eur_ref",
    "dispatch_operating_cost_eur_flex",
    "co2_emissions_total_t_ref",
    "co2_emissions_total_t_flex",
    "district_gas_boiler_peak_kw_ref",
    "district_gas_boiler_peak_kw_flex",
    "district_gas_boiler_generation_kwh_ref",
    "district_gas_boiler_generation_kwh_flex",
    "thermflex_shifted_space_heat_kwh",
    "thermflex_rebound_kwh",
    "dh_total_peak_change_kw",
    "thermflex_peak_change_kw",
    "dispatch_operating_cost_eur_delta",
    "dispatch_operating_cost_pct_change",
    "co2_emissions_total_t_delta",
    "co2_emissions_total_pct_change",
    "district_gas_boiler_peak_kw_delta",
    "district_gas_boiler_peak_pct_change",
    "district_gas_boiler_generation_kwh_delta",
    "district_gas_boiler_generation_pct_change",
    "thermflex_rebound_over_shifted_pct",
    "joint_savings_score",
)


POLICY_DESCRIPTOR_COLUMNS: tuple[str, ...] = (
    "flex_case_label",
    "policy_case_label_canonical",
    "policy_case_label_matches_export",
    "flex_override_name",
    "source_bundle_run_slug",
    "policy_duration_h",
    "policy_lower_relaxation_k",
    "policy_tau_h",
    "policy_dispatch_horizon_h",
    "policy_dispatch_rolling_commit_h",
    "policy_dispatch_lookahead_h",
    "policy_dispatch_is_rolling",
    "policy_max_events_per_day",
    "policy_constant_lower_bound_c",
    "policy_upper_only",
    # Live ThermFlex envelope flags (not recoverable from lower_relaxation alone).
    "policy_use_explicit_lower_bounds",
    "policy_constrain_upper_temperature",
)


CONTEXT_FEATURE_COLUMNS: tuple[str, ...] = (
    "date",
    "day_of_year",
    "month",
    "day_of_week",
    "t_outdoor_mean_c",
    "t_outdoor_min_c",
    "t_outdoor_max_c",
    "t_outdoor_range_c",
    "hdd18_kh",
    "t_outdoor_mean_prevday_c",
    "t_outdoor_mean_nextday_c",
    "t_outdoor_mean_prev3d_c",
    "t_outdoor_mean_prev7d_c",
    "t_outdoor_min_prev3d_c",
    "t_outdoor_min_prev7d_c",
    "hdd18_prev3d_kh",
    "hdd18_prev7d_kh",
    "t_outdoor_mean_rolling3d_c",
    "t_outdoor_mean_rolling7d_c",
    "t_outdoor_min_rolling3d_c",
    "t_outdoor_min_rolling7d_c",
    "hdd18_rolling3d_kh",
    "hdd18_rolling7d_kh",
    "t_outdoor_mean_delta_vs_prev3d_c",
    "t_outdoor_mean_delta_vs_prev7d_c",
    "dh_space_heat_total_kwh",
    "dh_total_kwh",
    "irradiance_proxy_sum",
    "solargains_proxy_sum",
    "mc_auction_mean_eur_mwh",
    "mc_auction_min_eur_mwh",
    "mc_auction_peak_eur_mwh",
    "mc_auction_std_eur_mwh",
    "mc_auction_range_eur_mwh",
    "mc_auction_min_hour",
    "mc_auction_peak_hour",
    "mc_auction_peak_above_mean_eur_mwh",
    "mc_auction_mean_above_min_eur_mwh",
    "mc_auction_weighted_dh_total_mean_eur_mwh",
    "mc_auction_weighted_space_heat_mean_eur_mwh",
    "gas_price_mean_eur_mwh_fuel",
    "co2_price_mean_eur_tco2",
    "dh_total_peak_kw",
    "dh_space_heat_peak_kw",
    "dh_total_peak_hour",
    "dh_space_heat_peak_hour",
    "dh_total_load_factor",
    "dh_space_heat_load_factor",
    "dh_total_ramp_abs_max_kwh",
    "dh_space_heat_ramp_abs_max_kwh",
    "dh_total_peak_to_price_min_distance_h",
    "dh_total_peak_to_price_peak_distance_h",
    "dh_space_heat_peak_to_price_min_distance_h",
    "dh_space_heat_peak_to_price_peak_distance_h",
    "price_at_dh_total_peak_eur_mwh",
    "price_at_dh_space_heat_peak_eur_mwh",
    "price_dh_total_corr",
    "price_dh_space_heat_corr",
    "t_outdoor_min_hour",
    "t_outdoor_max_hour",
    "t_outdoor_ramp_abs_max_c_per_h",
    "t_outdoor_ramp_abs_mean_c_per_h",
    "t_outdoor_at_price_min_c",
    "t_outdoor_at_price_peak_c",
    "t_outdoor_at_dh_total_peak_c",
    "t_outdoor_at_dh_space_heat_peak_c",
    "night_t_outdoor_mean_c",
    "morning_t_outdoor_mean_c",
    "midday_t_outdoor_mean_c",
    "evening_t_outdoor_mean_c",
    "night_hdd18_kh",
    "morning_hdd18_kh",
    "midday_hdd18_kh",
    "evening_hdd18_kh",
    "night_dh_total_share",
    "morning_dh_total_share",
    "midday_dh_total_share",
    "evening_dh_total_share",
    "night_dh_space_heat_share",
    "morning_dh_space_heat_share",
    "midday_dh_space_heat_share",
    "evening_dh_space_heat_share",
    "high_price_dh_total_share",
    "low_price_dh_total_share",
    "high_price_dh_space_heat_share",
    "low_price_dh_space_heat_share",
    "top3_price_dh_total_share",
    "bottom3_price_dh_total_share",
    "top3_price_dh_space_heat_share",
    "bottom3_price_dh_space_heat_share",
    "dh_space_heat_share_residential_pre1975",
    "dh_space_heat_share_residential_1975_1990",
    "dh_space_heat_share_residential_1990_2000",
    "dh_space_heat_share_residential_2000_2014",
    "dh_space_heat_share_non_residential_pre1975",
    "dh_space_heat_share_non_residential_1975_1990",
    "dh_space_heat_share_non_residential_1990_2000",
    "dh_space_heat_share_non_residential_2000_2014",
    "dh_space_heat_share_residential_total",
    "dh_space_heat_share_non_residential_total",
)


ENGINEERED_FEATURE_COLUMNS: tuple[str, ...] = (
    "day_of_year_sin",
    "day_of_year_cos",
    "dh_space_heat_share",
    "hdd18_per_space_heat",
    "t_outdoor_prevday_delta_c",
    "t_outdoor_nextday_delta_c",
    "irradiance_per_space_heat",
    "solargains_per_space_heat",
    "dispatch_cost_ref_per_dh_mwh",
    "co2_ref_per_dh_mwh",
    "boiler_generation_ref_share",
    "boiler_peak_ref_per_mean_dh_load",
    "boiler_ref_load_factor",
    "residential_to_non_residential_space_heat_ratio",
    "old_stock_space_heat_share",
    "modern_stock_space_heat_share",
)


REFERENCE_FEATURE_COLUMNS: tuple[str, ...] = (
    "dispatch_operating_cost_eur_ref",
    "co2_emissions_total_t_ref",
    "district_gas_boiler_peak_kw_ref",
    "district_gas_boiler_generation_kwh_ref",
)


DISPATCH_ECONOMICS_REFERENCE_FEATURE_COLUMNS: tuple[str, ...] = (
    "dispatch_heat_operating_cost_eur_ref",
    "fuel_cost_eur_ref",
    "co2_cost_eur_ref",
    "variable_opex_eur_ref",
    "startup_cost_eur_ref",
    "district_gas_boiler_co2_t_ref",
    "district_gas_chp_co2_t_ref",
    "district_gas_chp_thermal_generation_kwh_ref",
    "district_gas_chp_electric_generation_kwh_ref",
    "district_heat_pump_generation_kwh_ref",
    "district_external_heat_generation_kwh_ref",
    "district_waste_incineration_generation_kwh_ref",
    "dh_unserved_heat_kwh_ref",
)


DISPATCH_STATE_REFERENCE_FEATURE_COLUMNS: tuple[str, ...] = (
    "gas_chp_electric_value_eur_ref",
    "district_thermal_storage_charge_kwh_ref",
    "district_thermal_storage_discharge_kwh_ref",
    "district_thermal_storage_losses_kwh_ref",
    "district_thermal_storage_soc_mean_kwh_ref",
    "district_thermal_storage_soc_end_kwh_ref",
)


DISPATCH_ECONOMICS_ENGINEERED_FEATURE_COLUMNS: tuple[str, ...] = (
    "dispatch_heat_cost_ref_per_dh_mwh",
    "fuel_cost_ref_per_dh_mwh",
    "co2_cost_ref_per_dh_mwh",
    "variable_opex_ref_per_dh_mwh",
    "startup_cost_ref_per_dh_mwh",
    "boiler_co2_ref_share",
    "chp_co2_ref_share",
    "chp_thermal_generation_ref_share",
    "chp_electric_generation_ref_per_chp_heat",
    "heat_pump_generation_ref_share",
    "external_heat_generation_ref_share",
    "waste_incineration_generation_ref_share",
    "unserved_heat_ref_share",
)


DISPATCH_STATE_ENGINEERED_FEATURE_COLUMNS: tuple[str, ...] = (
    "gas_chp_electric_value_ref_per_dh_mwh",
    "gas_chp_electric_value_ref_per_chp_electric_mwh",
    "thermal_storage_charge_ref_share",
    "thermal_storage_discharge_ref_share",
    "thermal_storage_losses_ref_share",
    "thermal_storage_soc_mean_ref_per_dh",
    "thermal_storage_soc_end_ref_per_dh",
    "thermal_storage_net_discharge_ref_share",
    "thermal_storage_cycle_ref_share",
)


CATEGORICAL_FEATURE_COLUMNS: tuple[str, ...] = (
    "policy_case_label_canonical",
    "source_schema_version",
)


CORE_TARGET_COLUMNS: tuple[str, ...] = (
    "dispatch_operating_cost_eur_delta",
    "dispatch_operating_cost_pct_change",
    "co2_emissions_total_t_delta",
    "co2_emissions_total_pct_change",
    "district_gas_boiler_peak_kw_delta",
    "district_gas_boiler_peak_pct_change",
    "district_gas_boiler_generation_kwh_delta",
    "district_gas_boiler_generation_pct_change",
    "thermflex_shifted_space_heat_kwh",
    "thermflex_rebound_kwh",
    "thermflex_rebound_over_shifted_pct",
    "dh_total_peak_change_kw",
    "thermflex_peak_change_kw",
    "joint_savings_score",
)


# Newer v3 dispatch screens expose heat-boundary economics beside the older net
# operating-cost KPI. These are optional at the schema level because historic
# learning datasets remain useful, but missing values are kept as NaN and never
# replaced with zeros. Target profiles decide explicitly whether these columns
# are required for a given diagnostic.
OPTIONAL_DISPATCH_ECONOMICS_TARGET_COLUMNS: tuple[str, ...] = (
    "dispatch_heat_operating_cost_eur_delta",
    "dispatch_heat_operating_cost_eur_pct_change",
    "fuel_cost_eur_delta",
    "co2_cost_eur_delta",
    "variable_opex_eur_delta",
    "startup_cost_eur_delta",
    "district_gas_boiler_co2_t_delta",
    "district_gas_chp_co2_t_delta",
    "district_gas_chp_thermal_generation_kwh_delta",
    "district_gas_chp_electric_generation_kwh_delta",
    "district_heat_pump_generation_kwh_delta",
    "district_external_heat_generation_kwh_delta",
    "district_waste_incineration_generation_kwh_delta",
    "dispatch_heat_allocated_co2_t_delta",
    "dispatch_heat_allocated_co2_t_pct_change",
)


TARGET_COLUMNS: tuple[str, ...] = (
    *CORE_TARGET_COLUMNS,
    *OPTIONAL_DISPATCH_ECONOMICS_TARGET_COLUMNS,
)

# The first focused profile keeps only the paper-facing KPI block that should
# be stable enough to judge whether the day-level surrogate is progressing in
# the right direction before more event-shape targets are reintroduced.
ROBUST_KPI_TARGET_COLUMNS: tuple[str, ...] = (
    "dispatch_operating_cost_pct_change",
    "co2_emissions_total_pct_change",
    "district_gas_boiler_peak_kw_delta",
    "district_gas_boiler_generation_kwh_delta",
    "dh_total_peak_change_kw",
    "thermflex_peak_change_kw",
)


# The percentage-based KPI profile above is still useful for direct paper-facing
# reporting, but some day-level KPIs are numerically unstable when the
# reference-day denominator becomes very small. This second profile keeps the
# operational interpretation but switches cost and CO2 to absolute deltas so the
# training path can test whether the weak KPI fit is mainly a target-scaling
# issue rather than a missing-feature issue.
ROBUST_KPI_ABSOLUTE_TARGET_COLUMNS: tuple[str, ...] = (
    "dispatch_operating_cost_eur_delta",
    "co2_emissions_total_t_delta",
    "district_gas_boiler_peak_kw_delta",
    "district_gas_boiler_generation_kwh_delta",
    "dh_total_peak_change_kw",
    "thermflex_peak_change_kw",
)


# Preferred diagnostic profile for the current cost/CO2 surrogate question. It
# avoids the unstable net operating-cost percentage denominator and keeps CO2 on
# the already available total operational-emissions scale until the future
# heat-allocated CO2 truth columns are broadly exported.
HEAT_COST_TOTAL_CO2_ABSOLUTE_TARGET_COLUMNS: tuple[str, ...] = (
    "dispatch_heat_operating_cost_eur_delta",
    "co2_emissions_total_t_delta",
)


# Future-facing profile for screens that carry heat-boundary CO2 directly.
HEAT_COST_ALLOCATED_CO2_ABSOLUTE_TARGET_COLUMNS: tuple[str, ...] = (
    "dispatch_heat_operating_cost_eur_delta",
    "dispatch_heat_allocated_co2_t_delta",
)


# Source-stack diagnostic profile: not a paper KPI by itself, but useful to see
# whether the cost/CO2 residual comes from the boiler or CHP side.
DISPATCH_SOURCE_CO2_TARGET_COLUMNS: tuple[str, ...] = (
    "district_gas_boiler_co2_t_delta",
    "district_gas_chp_co2_t_delta",
)


DISPATCH_COST_COMPONENT_TARGET_COLUMNS: tuple[str, ...] = (
    "fuel_cost_eur_delta",
    "co2_cost_eur_delta",
    "variable_opex_eur_delta",
)


DISPATCH_SOURCE_GENERATION_TARGET_COLUMNS: tuple[str, ...] = (
    "district_gas_boiler_generation_kwh_delta",
    "district_gas_chp_thermal_generation_kwh_delta",
    "district_heat_pump_generation_kwh_delta",
    "district_external_heat_generation_kwh_delta",
    "district_waste_incineration_generation_kwh_delta",
)


# This profile is the minimal day-level block needed to reconstruct a surrogate
# `heating_season_day_screen.csv` that the existing Table-09 builder can read.
# It keeps cost and CO2 on percentage form because the current daily path fits
# those targets better than the absolute deltas, while boiler and ThermFlex
# shift/rebound remain on absolute physical units.
TABLE_09_PAPER_TARGET_COLUMNS: tuple[str, ...] = (
    "dispatch_operating_cost_pct_change",
    "co2_emissions_total_pct_change",
    "district_gas_boiler_peak_kw_delta",
    "district_gas_boiler_generation_kwh_delta",
    "thermflex_shifted_space_heat_kwh",
    "thermflex_rebound_kwh",
)


# This narrow profile exists because the current daily bottleneck is no longer
# the whole Table-09 block. Cost and boiler targets already move in the right
# direction, while the actual ThermFlex mechanism targets remain unstable under
# strict bundle holdout. Keeping those two targets in their own profile makes it
# possible to test whether the limitation comes from joint multi-target framing
# rather than from the truth pool alone.
SHIFTED_REBOUND_ONLY_TARGET_COLUMNS: tuple[str, ...] = (
    "thermflex_shifted_space_heat_kwh",
    "thermflex_rebound_kwh",
)


# Daily CO2 remains weak even after the recent dur8 truth expansion. Keeping it
# in its own profile allows us to test whether the residual error comes from
# target interference inside the broader Table-09 block or from the truth/split
# structure itself.
CO2_ONLY_TARGET_COLUMNS: tuple[str, ...] = (
    "co2_emissions_total_pct_change",
)


@dataclass(frozen=True)
class SchemaCheck:
    required_columns: tuple[str, ...]


def missing_columns(columns: Iterable[str], required: Iterable[str]) -> list[str]:
    available = {str(col) for col in columns}
    return [str(col) for col in required if str(col) not in available]


def validate_daily_results_frame(df: pd.DataFrame, *, source_label: str) -> SchemaCheck:
    """Validate one ThermFlex daily-results truth frame before feature building."""

    missing = missing_columns(df.columns, REQUIRED_DAILY_RESULT_COLUMNS)
    if missing:
        raise ValueError(
            "[thermflex_daily_results] Missing required truth columns in "
            f"{source_label}: {', '.join(missing)}"
        )
    if df.empty:
        raise ValueError(f"[thermflex_daily_results] Empty truth frame: {source_label}")
    for column in NUMERIC_DAILY_RESULT_COLUMNS:
        pd.to_numeric(df[column], errors="raise")
    pd.to_datetime(df["date"], errors="raise")
    return SchemaCheck(required_columns=REQUIRED_DAILY_RESULT_COLUMNS)
