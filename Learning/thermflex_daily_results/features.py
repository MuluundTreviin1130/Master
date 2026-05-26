from __future__ import annotations

import numpy as np
import pandas as pd

from Learning.thermflex_daily_results.schema import (
    CONTEXT_FEATURE_COLUMNS,
    DISPATCH_ECONOMICS_ENGINEERED_FEATURE_COLUMNS,
    DISPATCH_ECONOMICS_REFERENCE_FEATURE_COLUMNS,
    DISPATCH_STATE_ENGINEERED_FEATURE_COLUMNS,
    DISPATCH_STATE_REFERENCE_FEATURE_COLUMNS,
    ENGINEERED_FEATURE_COLUMNS,
    POLICY_DESCRIPTOR_COLUMNS,
    REFERENCE_FEATURE_COLUMNS,
)

# The feature vocabulary stays explicit here so later training scripts do not
# hide schema drift or silently depend on incidental columns.
FEATURE_GROUPS: dict[str, tuple[str, ...]] = {
    "policy": POLICY_DESCRIPTOR_COLUMNS,
    "context": CONTEXT_FEATURE_COLUMNS,
    "reference_day": REFERENCE_FEATURE_COLUMNS,
    "engineered": ENGINEERED_FEATURE_COLUMNS,
    "dispatch_economics_reference": DISPATCH_ECONOMICS_REFERENCE_FEATURE_COLUMNS,
    "dispatch_economics_engineered": DISPATCH_ECONOMICS_ENGINEERED_FEATURE_COLUMNS,
    "dispatch_state_reference": DISPATCH_STATE_REFERENCE_FEATURE_COLUMNS,
    "dispatch_state_engineered": DISPATCH_STATE_ENGINEERED_FEATURE_COLUMNS,
}


def add_engineered_feature_columns(
    frame: pd.DataFrame,
    *,
    include_dispatch_economics: bool = False,
    include_dispatch_state: bool = False,
) -> pd.DataFrame:
    """
    Add the explicit engineered feature block used by the daily surrogate path.

    These features stay intentionally simple and interpretable:
    - seasonal position in cyclical form
    - heat / solar intensity ratios
    - reference-day cost and CO2 intensity
    - reference-day boiler pressure / utilization proxies
    - compact cohort-composition indicators for the daily DH space-heat mix

    No silent denominator fallback is allowed here. The heating-season day
    contract must carry physically meaningful positive DH demand and nonnegative
    reference boiler quantities.
    """

    df = frame.copy()
    required = {
        "day_of_year",
        "dh_space_heat_total_kwh",
        "dh_total_kwh",
        "hdd18_kh",
        "t_outdoor_mean_c",
        "t_outdoor_mean_prevday_c",
        "t_outdoor_mean_nextday_c",
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
        "irradiance_proxy_sum",
        "solargains_proxy_sum",
        "dispatch_operating_cost_eur_ref",
        "co2_emissions_total_t_ref",
        "district_gas_boiler_peak_kw_ref",
        "district_gas_boiler_generation_kwh_ref",
    }
    missing = sorted(required.difference(df.columns))
    if missing:
        raise KeyError(
            "[thermflex_daily_results] engineered features missing required source columns: "
            + ", ".join(missing)
        )

    dh_total = pd.to_numeric(df["dh_total_kwh"], errors="raise").to_numpy(dtype=float)
    dh_space = pd.to_numeric(df["dh_space_heat_total_kwh"], errors="raise").to_numpy(dtype=float)
    boiler_peak = pd.to_numeric(df["district_gas_boiler_peak_kw_ref"], errors="raise").to_numpy(dtype=float)
    if np.any(dh_total <= 0.0):
        raise ValueError("[thermflex_daily_results] engineered features require positive `dh_total_kwh`.")
    if np.any(dh_space <= 0.0):
        raise ValueError("[thermflex_daily_results] engineered features require positive `dh_space_heat_total_kwh`.")
    if np.any(boiler_peak < 0.0):
        raise ValueError("[thermflex_daily_results] engineered features require nonnegative boiler peak.")

    day_of_year = pd.to_numeric(df["day_of_year"], errors="raise").to_numpy(dtype=float)
    angle = (2.0 * np.pi * day_of_year) / 365.0
    hdd18 = pd.to_numeric(df["hdd18_kh"], errors="raise").to_numpy(dtype=float)
    t_mean = pd.to_numeric(df["t_outdoor_mean_c"], errors="raise").to_numpy(dtype=float)
    t_prev = pd.to_numeric(df["t_outdoor_mean_prevday_c"], errors="raise").to_numpy(dtype=float)
    t_next = pd.to_numeric(df["t_outdoor_mean_nextday_c"], errors="raise").to_numpy(dtype=float)
    cost_ref = pd.to_numeric(df["dispatch_operating_cost_eur_ref"], errors="raise").to_numpy(dtype=float)
    co2_ref = pd.to_numeric(df["co2_emissions_total_t_ref"], errors="raise").to_numpy(dtype=float)
    irradiance = pd.to_numeric(df["irradiance_proxy_sum"], errors="raise").to_numpy(dtype=float)
    solargains = pd.to_numeric(df["solargains_proxy_sum"], errors="raise").to_numpy(dtype=float)
    boiler_generation = pd.to_numeric(df["district_gas_boiler_generation_kwh_ref"], errors="raise").to_numpy(dtype=float)
    mean_dh_load_kw = dh_total / 24.0
    residential_total_share = pd.to_numeric(
        df["dh_space_heat_share_residential_total"], errors="raise"
    ).to_numpy(dtype=float)
    non_residential_total_share = pd.to_numeric(
        df["dh_space_heat_share_non_residential_total"], errors="raise"
    ).to_numpy(dtype=float)
    residential_old_share = (
        pd.to_numeric(df["dh_space_heat_share_residential_pre1975"], errors="raise").to_numpy(dtype=float)
        + pd.to_numeric(df["dh_space_heat_share_residential_1975_1990"], errors="raise").to_numpy(dtype=float)
        + pd.to_numeric(df["dh_space_heat_share_non_residential_pre1975"], errors="raise").to_numpy(dtype=float)
        + pd.to_numeric(df["dh_space_heat_share_non_residential_1975_1990"], errors="raise").to_numpy(dtype=float)
    )
    residential_modern_share = (
        pd.to_numeric(df["dh_space_heat_share_residential_1990_2000"], errors="raise").to_numpy(dtype=float)
        + pd.to_numeric(df["dh_space_heat_share_residential_2000_2014"], errors="raise").to_numpy(dtype=float)
        + pd.to_numeric(df["dh_space_heat_share_non_residential_1990_2000"], errors="raise").to_numpy(dtype=float)
        + pd.to_numeric(df["dh_space_heat_share_non_residential_2000_2014"], errors="raise").to_numpy(dtype=float)
    )

    df["day_of_year_sin"] = np.sin(angle)
    df["day_of_year_cos"] = np.cos(angle)
    df["dh_space_heat_share"] = dh_space / dh_total
    df["hdd18_per_space_heat"] = hdd18 / dh_space
    df["t_outdoor_prevday_delta_c"] = t_mean - t_prev
    df["t_outdoor_nextday_delta_c"] = t_next - t_mean
    df["irradiance_per_space_heat"] = irradiance / dh_space
    df["solargains_per_space_heat"] = solargains / dh_space
    df["dispatch_cost_ref_per_dh_mwh"] = 1e3 * cost_ref / dh_total
    df["co2_ref_per_dh_mwh"] = 1e3 * co2_ref / dh_total
    df["boiler_generation_ref_share"] = boiler_generation / dh_total
    df["boiler_peak_ref_per_mean_dh_load"] = boiler_peak / mean_dh_load_kw
    df["boiler_ref_load_factor"] = boiler_generation / np.maximum(boiler_peak * 24.0, 1e-9)
    df["residential_to_non_residential_space_heat_ratio"] = residential_total_share / np.maximum(
        non_residential_total_share, 1e-9
    )
    df["old_stock_space_heat_share"] = residential_old_share
    df["modern_stock_space_heat_share"] = residential_modern_share
    if include_dispatch_economics:
        df = _add_dispatch_economics_feature_columns(df)
    if include_dispatch_state:
        df = _add_dispatch_state_feature_columns(df)
    return df


def _add_dispatch_economics_feature_columns(frame: pd.DataFrame) -> pd.DataFrame:
    """
    Add dispatch-economics features for the explicit v3 daily truth contract.

    This block is intentionally opt-in because older daily screens do not carry
    CHP/source-stack cost components. Missing values are data-contract failures
    here: using zeros would make "not exported" indistinguishable from a real
    zero-cost or zero-generation source state.
    """

    df = frame.copy()
    required = {
        "dh_total_kwh",
        "co2_emissions_total_t_ref",
        *DISPATCH_ECONOMICS_REFERENCE_FEATURE_COLUMNS,
    }
    missing = sorted(required.difference(df.columns))
    if missing:
        raise KeyError(
            "[thermflex_daily_results] dispatch-economics features missing required source columns: "
            + ", ".join(missing)
        )
    null_columns = sorted(column for column in required if df[column].isna().any())
    if null_columns:
        raise ValueError(
            "[thermflex_daily_results] dispatch-economics features require complete v3 screen exports; "
            "missing values in: "
            + ", ".join(null_columns)
        )

    dh_total = pd.to_numeric(df["dh_total_kwh"], errors="raise").to_numpy(dtype=float)
    co2_total = pd.to_numeric(df["co2_emissions_total_t_ref"], errors="raise").to_numpy(dtype=float)
    if np.any(dh_total <= 0.0):
        raise ValueError("[thermflex_daily_results] dispatch-economics features require positive `dh_total_kwh`.")
    if np.any(co2_total <= 0.0):
        raise ValueError("[thermflex_daily_results] dispatch-economics features require positive reference CO2.")

    heat_cost = pd.to_numeric(df["dispatch_heat_operating_cost_eur_ref"], errors="raise").to_numpy(dtype=float)
    fuel_cost = pd.to_numeric(df["fuel_cost_eur_ref"], errors="raise").to_numpy(dtype=float)
    co2_cost = pd.to_numeric(df["co2_cost_eur_ref"], errors="raise").to_numpy(dtype=float)
    variable_opex = pd.to_numeric(df["variable_opex_eur_ref"], errors="raise").to_numpy(dtype=float)
    startup_cost = pd.to_numeric(df["startup_cost_eur_ref"], errors="raise").to_numpy(dtype=float)
    boiler_co2 = pd.to_numeric(df["district_gas_boiler_co2_t_ref"], errors="raise").to_numpy(dtype=float)
    chp_co2 = pd.to_numeric(df["district_gas_chp_co2_t_ref"], errors="raise").to_numpy(dtype=float)
    chp_heat = pd.to_numeric(df["district_gas_chp_thermal_generation_kwh_ref"], errors="raise").to_numpy(dtype=float)
    chp_power = pd.to_numeric(df["district_gas_chp_electric_generation_kwh_ref"], errors="raise").to_numpy(dtype=float)
    heat_pump = pd.to_numeric(df["district_heat_pump_generation_kwh_ref"], errors="raise").to_numpy(dtype=float)
    external_heat = pd.to_numeric(df["district_external_heat_generation_kwh_ref"], errors="raise").to_numpy(dtype=float)
    waste_heat = pd.to_numeric(df["district_waste_incineration_generation_kwh_ref"], errors="raise").to_numpy(dtype=float)
    unserved_heat = pd.to_numeric(df["dh_unserved_heat_kwh_ref"], errors="raise").to_numpy(dtype=float)

    nonnegative_arrays = {
        "fuel_cost_eur_ref": fuel_cost,
        "co2_cost_eur_ref": co2_cost,
        "variable_opex_eur_ref": variable_opex,
        "startup_cost_eur_ref": startup_cost,
        "district_gas_boiler_co2_t_ref": boiler_co2,
        "district_gas_chp_co2_t_ref": chp_co2,
        "district_gas_chp_thermal_generation_kwh_ref": chp_heat,
        "district_gas_chp_electric_generation_kwh_ref": chp_power,
        "district_heat_pump_generation_kwh_ref": heat_pump,
        "district_external_heat_generation_kwh_ref": external_heat,
        "district_waste_incineration_generation_kwh_ref": waste_heat,
        "dh_unserved_heat_kwh_ref": unserved_heat,
    }
    negative_columns = [name for name, values in nonnegative_arrays.items() if np.any(values < 0.0)]
    if negative_columns:
        raise ValueError(
            "[thermflex_daily_results] dispatch-economics features require nonnegative source components: "
            + ", ".join(sorted(negative_columns))
        )

    df["dispatch_heat_cost_ref_per_dh_mwh"] = 1e3 * heat_cost / dh_total
    df["fuel_cost_ref_per_dh_mwh"] = 1e3 * fuel_cost / dh_total
    df["co2_cost_ref_per_dh_mwh"] = 1e3 * co2_cost / dh_total
    df["variable_opex_ref_per_dh_mwh"] = 1e3 * variable_opex / dh_total
    df["startup_cost_ref_per_dh_mwh"] = 1e3 * startup_cost / dh_total
    df["boiler_co2_ref_share"] = boiler_co2 / np.maximum(co2_total, 1e-9)
    df["chp_co2_ref_share"] = chp_co2 / np.maximum(co2_total, 1e-9)
    df["chp_thermal_generation_ref_share"] = chp_heat / dh_total
    df["chp_electric_generation_ref_per_chp_heat"] = chp_power / np.maximum(chp_heat, 1e-9)
    df["heat_pump_generation_ref_share"] = heat_pump / dh_total
    df["external_heat_generation_ref_share"] = external_heat / dh_total
    df["waste_incineration_generation_ref_share"] = waste_heat / dh_total
    df["unserved_heat_ref_share"] = unserved_heat / dh_total
    return df


def _add_dispatch_state_feature_columns(frame: pd.DataFrame) -> pd.DataFrame:
    """
    Add REF dispatch-state features for CHP/storage-sensitive cost and CO2 targets.

    These columns are deliberately separate from the older dispatch-economics
    mode because only the newer screen contract exports thermal-storage state.
    Rows without this state should be excluded explicitly by the dataset builder,
    not padded with zeros.
    """

    df = frame.copy()
    required = {
        "dh_total_kwh",
        "district_gas_chp_electric_generation_kwh_ref",
        *DISPATCH_STATE_REFERENCE_FEATURE_COLUMNS,
    }
    missing = sorted(required.difference(df.columns))
    if missing:
        raise KeyError(
            "[thermflex_daily_results] dispatch-state features missing required source columns: "
            + ", ".join(missing)
        )
    null_columns = sorted(column for column in required if df[column].isna().any())
    if null_columns:
        raise ValueError(
            "[thermflex_daily_results] dispatch-state features require complete storage/CHP state exports; "
            "missing values in: "
            + ", ".join(null_columns)
        )

    dh_total = pd.to_numeric(df["dh_total_kwh"], errors="raise").to_numpy(dtype=float)
    chp_power = pd.to_numeric(df["district_gas_chp_electric_generation_kwh_ref"], errors="raise").to_numpy(dtype=float)
    electric_value = pd.to_numeric(df["gas_chp_electric_value_eur_ref"], errors="raise").to_numpy(dtype=float)
    storage_charge = pd.to_numeric(df["district_thermal_storage_charge_kwh_ref"], errors="raise").to_numpy(dtype=float)
    storage_discharge = pd.to_numeric(df["district_thermal_storage_discharge_kwh_ref"], errors="raise").to_numpy(dtype=float)
    storage_losses = pd.to_numeric(df["district_thermal_storage_losses_kwh_ref"], errors="raise").to_numpy(dtype=float)
    storage_soc_mean = pd.to_numeric(df["district_thermal_storage_soc_mean_kwh_ref"], errors="raise").to_numpy(dtype=float)
    storage_soc_end = pd.to_numeric(df["district_thermal_storage_soc_end_kwh_ref"], errors="raise").to_numpy(dtype=float)

    if np.any(dh_total <= 0.0):
        raise ValueError("[thermflex_daily_results] dispatch-state features require positive `dh_total_kwh`.")
    nonnegative_arrays = {
        "district_gas_chp_electric_generation_kwh_ref": chp_power,
        "district_thermal_storage_charge_kwh_ref": storage_charge,
        "district_thermal_storage_discharge_kwh_ref": storage_discharge,
        "district_thermal_storage_losses_kwh_ref": storage_losses,
        "district_thermal_storage_soc_mean_kwh_ref": storage_soc_mean,
        "district_thermal_storage_soc_end_kwh_ref": storage_soc_end,
    }
    negative_columns = [name for name, values in nonnegative_arrays.items() if np.any(values < 0.0)]
    if negative_columns:
        raise ValueError(
            "[thermflex_daily_results] dispatch-state features require nonnegative storage/CHP state columns: "
            + ", ".join(sorted(negative_columns))
        )

    df["gas_chp_electric_value_ref_per_dh_mwh"] = 1e3 * electric_value / dh_total
    df["gas_chp_electric_value_ref_per_chp_electric_mwh"] = 1e3 * electric_value / np.maximum(chp_power, 1e-9)
    df["thermal_storage_charge_ref_share"] = storage_charge / dh_total
    df["thermal_storage_discharge_ref_share"] = storage_discharge / dh_total
    df["thermal_storage_losses_ref_share"] = storage_losses / dh_total
    df["thermal_storage_soc_mean_ref_per_dh"] = storage_soc_mean / dh_total
    df["thermal_storage_soc_end_ref_per_dh"] = storage_soc_end / dh_total
    df["thermal_storage_net_discharge_ref_share"] = (storage_discharge - storage_charge) / dh_total
    df["thermal_storage_cycle_ref_share"] = (storage_charge + storage_discharge) / dh_total
    return df
