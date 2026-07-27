from __future__ import annotations

import pandas as pd


REQUIRED_HOURLY_DISPATCH_COLUMNS: tuple[str, ...] = (
    "date",
    "hour_index",
    "timestamp",
    "flex_case_label",
    "flex_override_name",
    "dh_bus_load_kwh_ref",
    "dh_bus_load_kwh_flex",
    "dh_bus_load_kwh_delta",
    "dh_total_demand_kwh_ref",
    "dh_total_demand_kwh_flex",
    "dh_total_demand_kwh_delta",
    "district_gas_chp_thermal_generation_kwh_ref",
    "district_gas_chp_electric_generation_kwh_ref",
    "district_gas_boiler_generation_kwh_ref",
    "district_heat_pump_generation_kwh_ref",
    "district_external_heat_generation_kwh_ref",
    "district_waste_incineration_generation_kwh_ref",
    "dispatch_heat_operating_cost_eur_ref",
    "dispatch_operating_cost_eur_ref",
    "co2_emissions_total_t_ref",
    "district_gas_chp_thermal_generation_kwh_delta",
    "district_gas_chp_electric_generation_kwh_delta",
    "district_gas_boiler_generation_kwh_delta",
    "district_gas_chp_fuel_input_kwh_delta",
    "district_gas_boiler_fuel_input_kwh_delta",
    "district_gas_chp_co2_t_delta",
    "district_gas_boiler_co2_t_delta",
    "gas_chp_electric_value_eur_delta",
    "fuel_cost_eur_delta",
    "co2_cost_eur_delta",
    "dispatch_heat_operating_cost_eur_delta",
    "co2_emissions_total_t_delta",
)


POLICY_FEATURE_COLUMNS: tuple[str, ...] = (
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
)


CONTEXT_FEATURE_COLUMNS: tuple[str, ...] = (
    "hour_index",
    "hour_of_day_sin",
    "hour_of_day_cos",
    "day_of_year_sin",
    "day_of_year_cos",
    "t_outdoor_c",
    "irradiance_proxy",
    "solargains_proxy",
    "dh_space_heat_total_kwh",
    "dh_hotwater_total_kwh",
    "dh_total_kwh",
    "mc_auction_eur_mwh",
    "gas_price_eur_mwh_fuel",
    "co2_price_eur_tco2",
)


REF_DISPATCH_FEATURE_COLUMNS: tuple[str, ...] = (
    "dh_bus_load_kwh_ref",
    "dh_total_demand_kwh_ref",
    "district_gas_chp_thermal_generation_kwh_ref",
    "district_gas_chp_electric_generation_kwh_ref",
    "district_gas_boiler_generation_kwh_ref",
    "district_heat_pump_generation_kwh_ref",
    "district_external_heat_generation_kwh_ref",
    "district_waste_incineration_generation_kwh_ref",
    "district_gas_chp_fuel_input_kwh_ref",
    "district_gas_boiler_fuel_input_kwh_ref",
    "district_gas_chp_co2_t_ref",
    "district_gas_boiler_co2_t_ref",
    "fuel_cost_eur_ref",
    "co2_cost_eur_ref",
    "gas_chp_electric_value_eur_ref",
    "dispatch_heat_operating_cost_eur_ref",
    "dispatch_operating_cost_eur_ref",
    "co2_emissions_total_t_ref",
)


THERMFLEX_LOAD_FEATURE_COLUMNS: tuple[str, ...] = (
    "dh_bus_load_kwh_flex",
    "dh_bus_load_kwh_delta",
    "dh_total_demand_kwh_flex",
    "dh_total_demand_kwh_delta",
)


TARGET_COLUMNS: tuple[str, ...] = (
    "district_gas_chp_thermal_generation_kwh_delta",
    "district_gas_chp_electric_generation_kwh_delta",
    "district_gas_boiler_generation_kwh_delta",
    "district_gas_chp_fuel_input_kwh_delta",
    "district_gas_boiler_fuel_input_kwh_delta",
    "district_gas_chp_co2_t_delta",
    "district_gas_boiler_co2_t_delta",
    "gas_chp_electric_value_eur_delta",
    "fuel_cost_eur_delta",
    "co2_cost_eur_delta",
    "dispatch_heat_operating_cost_eur_delta",
    "co2_emissions_total_t_delta",
)


def validate_hourly_dispatch_frame(frame: pd.DataFrame, *, source_label: str) -> None:
    missing = sorted(set(REQUIRED_HOURLY_DISPATCH_COLUMNS).difference(frame.columns))
    if missing:
        raise ValueError(
            "[thermflex_hourly_dispatch] missing required hourly dispatch columns in "
            f"{source_label}: {', '.join(missing)}"
        )
    if frame.empty:
        raise ValueError(f"[thermflex_hourly_dispatch] hourly dispatch frame is empty: {source_label}")
    for column in REQUIRED_HOURLY_DISPATCH_COLUMNS:
        if column in {"date", "timestamp", "flex_case_label", "flex_override_name"}:
            continue
        pd.to_numeric(frame[column], errors="raise")


def validate_hourly_dispatch_time_consistency(frame: pd.DataFrame, *, source_label: str) -> None:
    """
    Fail fast when `date` / `hour_index` disagree with `timestamp`.

    Context enrichment joins weather/price state on `timestamp`, while
    uniqueness, dedupe, split grouping, and daily aggregation key on
    `(date, hour_index)`. A mismatch silently attaches the wrong context
    features to dispatch labels or moves rows into the wrong day bucket.
    """

    required = ("date", "hour_index", "timestamp")
    missing = [column for column in required if column not in frame.columns]
    if missing:
        raise KeyError(
            "[thermflex_hourly_dispatch] missing time-key columns in "
            f"{source_label}: {', '.join(missing)}"
        )

    dates = pd.to_datetime(frame["date"], errors="raise")
    timestamps = pd.to_datetime(frame["timestamp"], errors="raise")
    hours = pd.to_numeric(frame["hour_index"], errors="raise")

    if dates.isna().any() or timestamps.isna().any():
        raise ValueError(
            "[thermflex_hourly_dispatch] null date/timestamp values are not allowed in "
            f"{source_label}"
        )
    # Reject non-integral hour labels before casting; float 6.5 must not become 6.
    if ((hours % 1) != 0).any():
        raise ValueError(
            "[thermflex_hourly_dispatch] hour_index must be integer-valued in "
            f"{source_label}"
        )

    hours_int = hours.astype(int)
    if ((hours_int < 0) | (hours_int > 23)).any():
        raise ValueError(
            "[thermflex_hourly_dispatch] hour_index must be in [0, 23] in "
            f"{source_label}"
        )

    date_mismatch = dates.dt.normalize() != timestamps.dt.normalize()
    hour_mismatch = hours_int.to_numpy() != timestamps.dt.hour.to_numpy()
    bad_mask = date_mismatch | hour_mismatch
    if not bad_mask.any():
        return

    examples = (
        pd.DataFrame(
            {
                "date": dates.loc[bad_mask].dt.strftime("%Y-%m-%d"),
                "hour_index": hours_int.loc[bad_mask],
                "timestamp": timestamps.loc[bad_mask].astype(str),
            }
        )
        .head(10)
        .to_dict(orient="records")
    )
    raise ValueError(
        "[thermflex_hourly_dispatch] date/hour_index disagree with timestamp in "
        f"{source_label}; examples={examples}"
    )


def feature_columns() -> tuple[str, ...]:
    return (
        POLICY_FEATURE_COLUMNS
        + CONTEXT_FEATURE_COLUMNS
        + REF_DISPATCH_FEATURE_COLUMNS
        + THERMFLEX_LOAD_FEATURE_COLUMNS
    )
