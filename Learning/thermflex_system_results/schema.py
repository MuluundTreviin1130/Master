from __future__ import annotations

from typing import Iterable

import pandas as pd

# The first stable system-level contract uses the non-smoke ThermFlex truth
# family only. These columns were verified as the common core across the
# historic non-smoke schemas and therefore form the explicit V1 contract.
REQUIRED_COMMON_COLUMNS: tuple[str, ...] = (
    "run_id",
    "signature_hash",
    "source",
    "pv_kwp",
    "bess_kwh",
    "ely_kw",
    "h2_tank_kwh",
    "fc_kw",
    "small_wind_kw",
    "large_wind_kw",
    "district_heat_pump_kw_th",
    "district_thermal_storage_kwh_th",
    "district_wood_chip_boiler_kw_th",
    "district_biomass_chp_kw_th",
    "district_geothermal_kw_el",
    "district_gas_chp_kw_el",
    "district_biogas_chp_kw_el",
    "biogas_engine_kw",
    "wood_gasifier_kw",
    "E_import_grid_kWh",
    "E_export_grid_kWh",
    "E_total_load_kWh",
    "E_district_heat_pump_thermal_generation_kWh",
    "E_district_heat_pump_electricity_kWh",
    "E_district_thermal_storage_charge_kWh",
    "E_district_thermal_storage_discharge_kWh",
    "E_district_thermal_storage_losses_kWh",
    "E_district_external_heat_generation_kWh",
    "E_district_biomass_chp_electric_generation_kWh",
    "E_district_biomass_chp_thermal_generation_kWh",
    "E_district_biomass_chp_fuel_input_kWh",
    "E_district_gas_chp_electric_generation_kWh",
    "E_district_gas_chp_thermal_generation_kWh",
    "E_district_gas_chp_fuel_input_kWh",
    "E_district_gas_boiler_generation_kWh",
    "E_district_gas_boiler_fuel_input_kWh",
    "bess_cyclic_violation_kwh",
    "h2_cyclic_violation_kwh",
    "M_district_biomass_chp_fuel_input_kg",
    "V_district_gas_chp_fuel_input_m3",
    "V_district_gas_boiler_fuel_input_m3",
    "dispatch_cost_eur",
)

DESIGN_FEATURE_COLUMNS: tuple[str, ...] = (
    "pv_kwp",
    "bess_kwh",
    "ely_kw",
    "h2_tank_kwh",
    "fc_kw",
    "small_wind_kw",
    "large_wind_kw",
    "district_heat_pump_kw_th",
    "district_thermal_storage_kwh_th",
    "district_wood_chip_boiler_kw_th",
    "district_biomass_chp_kw_th",
    "district_geothermal_kw_el",
    "district_gas_chp_kw_el",
    "district_biogas_chp_kw_el",
    "biogas_engine_kw",
    "wood_gasifier_kw",
)

DERIVED_NUMERIC_FEATURE_COLUMNS: tuple[str, ...] = (
    "policy_thermflex_enabled",
    "policy_no_thermflex",
    "policy_lower_bound_c",
    "policy_duration_h",
    "policy_max_events_per_day",
    "scenario_is_baseline_constant",
    "scenario_is_day_night",
    "scenario_is_peak_window",
    "scenario_is_price_window",
    "scenario_is_sunny_window",
    "scenario_is_wintertyp_window",
    "scenario_is_shouldertyp_window",
    "scenario_anchor_month",
    "scenario_anchor_day_of_year",
    "scenario_t_outdoor_mean_c",
    "scenario_t_outdoor_min_c",
    "scenario_dh_total_kwh",
    "scenario_dh_space_heat_total_kwh",
    "scenario_solargains_proxy_sum",
    "scenario_irradiance_proxy_sum",
    "scenario_mc_auction_mean_eur_mwh",
    "scenario_mc_auction_peak_eur_mwh",
    "scenario_gas_price_mean_eur_mwh_fuel",
    "scenario_co2_price_mean_eur_tco2",
)

CATEGORICAL_FEATURE_COLUMNS: tuple[str, ...] = (
    "dispatch_formulation_tag",
    "thermflex_case_slug",
    "source_schema_version",
    "scenario_slice_tag",
)

TARGET_COLUMNS: tuple[str, ...] = (
    "E_import_grid_kWh",
    "E_export_grid_kWh",
    "E_total_load_kWh",
    "E_district_heat_pump_thermal_generation_kWh",
    "E_district_heat_pump_electricity_kWh",
    "E_district_thermal_storage_charge_kWh",
    "E_district_thermal_storage_discharge_kWh",
    "E_district_thermal_storage_losses_kWh",
    "E_district_external_heat_generation_kWh",
    "E_district_biomass_chp_electric_generation_kWh",
    "E_district_biomass_chp_thermal_generation_kWh",
    "E_district_biomass_chp_fuel_input_kWh",
    "E_district_gas_chp_electric_generation_kWh",
    "E_district_gas_chp_thermal_generation_kWh",
    "E_district_gas_chp_fuel_input_kWh",
    "E_district_gas_boiler_generation_kWh",
    "E_district_gas_boiler_fuel_input_kWh",
    "bess_cyclic_violation_kwh",
    "h2_cyclic_violation_kwh",
    "M_district_biomass_chp_fuel_input_kg",
    "V_district_gas_chp_fuel_input_m3",
    "V_district_gas_boiler_fuel_input_m3",
    "dispatch_cost_eur",
)

# These additional targets come from `dispatch_kpis.json` / `latest_point` and
# describe post-processed dispatch economics, carbon and ThermFlex behavior more
# directly than the older run-level truth core. They are intentionally kept out
# of the V1 base contract because not every historic run folder carries the
# dispatch-KPI export.
DISPATCH_KPI_TARGET_COLUMNS: tuple[str, ...] = (
    "dispatch_operating_cost_eur",
    "dispatch_heat_operating_cost_eur",
    "dispatch_objective_eur",
    "dispatch_penalty_total_eur",
    "grid_import_cost_eur",
    "grid_export_revenue_eur",
    "fuel_cost_eur",
    "co2_cost_eur",
    "variable_opex_eur",
    "unserved_penalty_eur",
    "temperature_violation_penalty_eur",
    "thermflex_activation_penalty_eur",
    "spill_penalty_eur",
    "co2_emissions_total_t",
    "district_gas_boiler_co2_t",
    "district_gas_chp_co2_t",
    "thermflex_shifted_space_heat_kwh",
    "thermflex_additional_space_heat_kwh",
    "thermflex_rebound_kwh",
    "thermflex_peak_change_kw",
    "thermflex_active_member_hours_total",
    "thermflex_temperature_violation_degree_hours_total",
)

# The first focused profile keeps the core district-heat system quantities that
# matter most for system-level ThermFlex interpretation and that are structurally
# better behaved than the full mixed target block.
ROBUST_HEAT_SYSTEM_TARGET_COLUMNS: tuple[str, ...] = (
    "E_district_gas_chp_electric_generation_kWh",
    "E_district_gas_chp_thermal_generation_kWh",
    "E_district_gas_chp_fuel_input_kWh",
    "E_district_gas_boiler_generation_kWh",
    "E_district_gas_boiler_fuel_input_kWh",
    "E_district_thermal_storage_charge_kWh",
    "E_district_thermal_storage_discharge_kWh",
    "dispatch_cost_eur",
)


# This profile isolates the paper-facing dispatch KPI block that is currently
# missing from the older V1 truth contract. It should only be trained on the
# explicit dispatch-KPI-enriched family, not on the legacy core-only family.
DISPATCH_KPI_CORE_TARGET_COLUMNS: tuple[str, ...] = (
    "dispatch_operating_cost_eur",
    "dispatch_heat_operating_cost_eur",
    "fuel_cost_eur",
    "co2_cost_eur",
    "variable_opex_eur",
    "co2_emissions_total_t",
    "district_gas_boiler_co2_t",
    "district_gas_chp_co2_t",
    "thermflex_shifted_space_heat_kwh",
    "thermflex_additional_space_heat_kwh",
    "thermflex_rebound_kwh",
    "thermflex_peak_change_kw",
    "thermflex_active_member_hours_total",
    "thermflex_temperature_violation_degree_hours_total",
)

# This is the paper-facing KPI subset. It intentionally excludes the older
# grid-tainted `dispatch_operating_cost_eur` and the auxiliary
# `district_gas_chp_co2_t` split because the current paper story is built on
# heat-only cost and total heat-system CO2, not on the broader dispatch-cost
# proxy or on an internal gas-CHP-only carbon split.
DISPATCH_KPI_PAPER_TARGET_COLUMNS: tuple[str, ...] = (
    "dispatch_heat_operating_cost_eur",
    "fuel_cost_eur",
    "co2_cost_eur",
    "variable_opex_eur",
    "co2_emissions_total_t",
    "district_gas_boiler_co2_t",
    "thermflex_shifted_space_heat_kwh",
    "thermflex_additional_space_heat_kwh",
    "thermflex_rebound_kwh",
    "thermflex_peak_change_kw",
    "thermflex_active_member_hours_total",
    "thermflex_temperature_violation_degree_hours_total",
)

BUILDER_METADATA_COLUMNS: tuple[str, ...] = (
    "source_run_name",
    "source_run_slug",
    "source_truth_csv",
    "source_schema_version",
    "dispatch_formulation_tag",
    "scenario_profile_tag",
    "scenario_slice_tag",
    "thermflex_case_slug",
    "policy_thermflex_enabled",
    "policy_no_thermflex",
    "policy_lower_bound_c",
    "policy_duration_h",
    "policy_max_events_per_day",
    "scenario_is_baseline_constant",
    "scenario_is_day_night",
    "scenario_is_peak_window",
    "scenario_is_price_window",
    "scenario_is_sunny_window",
    "scenario_is_wintertyp_window",
    "scenario_is_shouldertyp_window",
    "scenario_anchor_month",
    "scenario_anchor_day_of_year",
    "scenario_t_outdoor_mean_c",
    "scenario_t_outdoor_min_c",
    "scenario_dh_total_kwh",
    "scenario_dh_space_heat_total_kwh",
    "scenario_solargains_proxy_sum",
    "scenario_irradiance_proxy_sum",
    "scenario_mc_auction_mean_eur_mwh",
    "scenario_mc_auction_peak_eur_mwh",
    "scenario_gas_price_mean_eur_mwh_fuel",
    "scenario_co2_price_mean_eur_tco2",
    "split_group_run",
    "split_group_case",
    "split_group_dispatch",
)


def validate_system_results_frame(frame: pd.DataFrame, *, source_label: str) -> None:
    """Fail fast if a loaded system truth frame violates the explicit V1 contract."""

    missing = [column for column in REQUIRED_COMMON_COLUMNS if column not in frame.columns]
    if missing:
        raise ValueError(
            "[thermflex_system_results] missing required columns in "
            f"{source_label}: {', '.join(missing)}"
        )
    if frame.empty:
        raise ValueError(f"[thermflex_system_results] empty truth frame loaded from {source_label}.")
    numeric_columns: Iterable[str] = (
        set(REQUIRED_COMMON_COLUMNS).difference({"run_id", "signature_hash", "source"})
    )
    for column in sorted(numeric_columns):
        pd.to_numeric(frame[column], errors="raise")
