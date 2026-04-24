from __future__ import annotations

from typing import Any

import numpy as np
from pyomo.environ import (
    Binary,
    ConcreteModel,
    ConstraintList,
    NonNegativeReals,
    Objective,
    RangeSet,
    SolverFactory,
    Var,
    minimize,
    value,
)

from dispatch.scenarios.historical import build_historical_scenario_bundle
from dispatch.core import DispatchInput, DispatchResult
from dispatch.metrics import compute_series_peak_change_kw, compute_series_peak_kw, compute_thermflex_series_metrics


def _arr(values: Any, n: int) -> np.ndarray:
    arr = np.asarray(values, dtype=float).reshape(-1)
    if arr.size == n:
        return arr
    if arr.size == 0:
        return np.zeros(n, dtype=float)
    if arr.size > n:
        return arr[:n]
    return np.pad(arr, (0, n - arr.size), constant_values=float(arr[-1]))


def _f(mapping: dict[str, Any], key: str, default: float = 0.0) -> float:
    return float(mapping.get(key, default) or default)


def _opt_nonneg(mapping: dict[str, Any], key: str) -> float | None:
    value = mapping.get(key)
    if value is None:
        return None
    return max(0.0, float(value))


def _series(dispatch_input: DispatchInput, key: str, n: int) -> np.ndarray:
    return np.maximum(0.0, _arr(dispatch_input.series.get(key, np.zeros(n)), n))


def _matrix(values: Any, rows: int, cols: int) -> np.ndarray:
    arr = np.asarray(values, dtype=float)
    if arr.shape != (rows, cols):
        raise ValueError(
            f"[dispatch.milp_two_stage] Expected matrix shape {(rows, cols)}, got {arr.shape}."
        )
    return arr


def _source_ratio(eta_el: float, eta_th: float) -> float:
    return float(eta_el / eta_th) if eta_el > 0.0 and eta_th > 0.0 else 0.0


def _weighted_average(matrix: np.ndarray, probabilities: np.ndarray) -> np.ndarray:
    if matrix.ndim != 2:
        raise ValueError("[dispatch.milp_two_stage] expected 2D scenario matrix.")
    return np.sum(matrix * probabilities.reshape(-1, 1), axis=0)


def run_milp_two_stage_dispatch(dispatch_input: DispatchInput, **_: Any) -> DispatchResult:
    bundle = build_historical_scenario_bundle(dispatch_input)
    probabilities = np.asarray(bundle.probabilities, dtype=float).reshape(-1)
    if probabilities.size == 0:
        raise ValueError("[dispatch.milp_two_stage] No scenario probabilities available.")
    probabilities = probabilities / np.sum(probabilities)

    scenario_inputs = bundle.inputs
    n_scen = len(scenario_inputs)
    demand0 = np.maximum(
        0.0,
        np.asarray(scenario_inputs[0].series["electric_non_dispatch_demand"], dtype=float).reshape(-1),
    )
    n = int(demand0.size)
    if n == 0:
        return DispatchResult(
            hourly={},
            objective_terms={
                "grid_import_cost": 0.0,
                "grid_export_revenue": 0.0,
                "fuel_cost": 0.0,
                "co2_cost": 0.0,
                "variable_opex": 0.0,
                "unserved_penalty": 0.0,
                "spill_penalty": 0.0,
                "thermflex_activation_penalty": 0.0,
                "temperature_violation_penalty": 0.0,
            },
            diagnostics={"mode": "milp_two_stage", "solver": "pyomo.highs", "termination_condition": "empty"},
        )

    s0 = scenario_inputs[0].series
    a = dispatch_input.assets
    p = dispatch_input.params
    st = dispatch_input.initial_state
    base_gas_day_ahead_price_raw = dispatch_input.series.get(
        "district_gas_day_ahead_price_eur_per_mwh_fuel",
        dispatch_input.series.get("district_gas_price_eur_per_mwh_fuel"),
    )
    base_gas_balance_price_raw = dispatch_input.series.get("district_gas_balance_price_eur_per_mwh_fuel")

    demand = np.zeros((n_scen, n), dtype=float)
    pv_av = np.zeros((n_scen, n), dtype=float)
    sw_av = np.zeros((n_scen, n), dtype=float)
    lw_av = np.zeros((n_scen, n), dtype=float)
    hydro_av = np.zeros((n_scen, n), dtype=float)
    grid_buy = np.zeros((n_scen, n), dtype=float)
    grid_sell = np.zeros((n_scen, n), dtype=float)
    gas_price_mwh = np.empty((n_scen, n), dtype=float)
    gas_balance_price_mwh = np.empty((n_scen, n), dtype=float)
    co2_price_eur_per_t = np.empty((n_scen, n), dtype=float)
    dh_demand = np.zeros((n_scen, n), dtype=float)
    dh_space_heat_ref = np.zeros((n_scen, n), dtype=float)
    dh_hotwater_demand = np.zeros((n_scen, n), dtype=float)
    hp_cop = np.zeros((n_scen, n), dtype=float)
    geo_el_av = np.zeros((n_scen, n), dtype=float)
    geo_th_av = np.zeros((n_scen, n), dtype=float)
    solar_direct_av = np.zeros((n_scen, n), dtype=float)
    solar_total_useful_av = np.zeros((n_scen, n), dtype=float)
    external_heat_th_av = np.zeros((n_scen, n), dtype=float)
    waste_th_av = np.zeros((n_scen, n), dtype=float)
    bio_th_av = np.zeros((n_scen, n), dtype=float)
    bigas_th_av = np.zeros((n_scen, n), dtype=float)
    gas_th_av = np.zeros((n_scen, n), dtype=float)
    gas_boiler_th_av = np.zeros((n_scen, n), dtype=float)
    wood_th_av = np.zeros((n_scen, n), dtype=float)

    for s_idx, scenario in enumerate(scenario_inputs):
        demand[s_idx] = np.maximum(0.0, np.asarray(scenario.series["electric_non_dispatch_demand"], dtype=float).reshape(-1))
        if demand[s_idx].size != n:
            raise ValueError("[dispatch.milp_two_stage] Scenario horizon mismatch in electric_non_dispatch_demand.")
        pv_av[s_idx] = _series(scenario, "pv_available", n)
        sw_av[s_idx] = _series(scenario, "small_wind_available", n)
        lw_av[s_idx] = _series(scenario, "large_wind_available", n)
        hydro_av[s_idx] = _series(scenario, "run_of_river_hydro_available", n)
        grid_buy[s_idx] = _arr(scenario.series.get("grid_import_price", np.zeros(n)), n)
        grid_sell[s_idx] = _arr(scenario.series.get("grid_export_price", np.zeros(n)), n)
        gas_price_raw = scenario.series.get(
            "district_gas_day_ahead_price_eur_per_mwh_fuel",
            scenario.series.get("district_gas_price_eur_per_mwh_fuel"),
        )
        if gas_price_raw is None:
            gas_price_mwh[s_idx] = np.nan
        else:
            gas_price_mwh[s_idx] = _arr(gas_price_raw, n)
        gas_balance_price_raw = scenario.series.get("district_gas_balance_price_eur_per_mwh_fuel")
        if gas_balance_price_raw is None:
            gas_balance_price_mwh[s_idx] = np.nan
        else:
            gas_balance_price_mwh[s_idx] = _arr(gas_balance_price_raw, n)
        co2_price_raw = scenario.series.get("co2_price_eur_per_tco2")
        if co2_price_raw is None:
            co2_price_eur_per_t[s_idx] = np.nan
        else:
            co2_price_eur_per_t[s_idx] = _arr(co2_price_raw, n)
        dh_demand[s_idx] = _series(scenario, "district_heat_demand", n)
        dh_space_heat_ref[s_idx] = _series(scenario, "district_space_heat_demand", n)
        dh_hotwater_demand[s_idx] = _series(scenario, "district_hotwater_demand", n)
        hp_cop[s_idx] = np.maximum(1e-9, _arr(scenario.series.get("district_heat_pump_cop", np.ones(n)), n))
        geo_el_av[s_idx] = _series(scenario, "district_geothermal_available_el", n)
        geo_th_av[s_idx] = _series(scenario, "district_geothermal_available_th", n)
        solar_direct_av[s_idx] = _series(scenario, "district_solar_thermal_direct_available_th", n)
        solar_total_useful_av[s_idx] = _series(scenario, "district_solar_thermal_total_useful_available_th", n)
        external_heat_th_av[s_idx] = _series(scenario, "district_external_heat_available_th", n)
        waste_th_av[s_idx] = _series(scenario, "district_waste_incineration_available_th", n)
        bio_th_av[s_idx] = _series(scenario, "district_biomass_chp_available_th", n)
        bigas_th_av[s_idx] = _series(scenario, "district_biogas_chp_available_th", n)
        gas_th_av[s_idx] = _series(scenario, "district_gas_chp_available_th", n)
        gas_boiler_th_av[s_idx] = _series(scenario, "district_gas_boiler_available_th", n)
        wood_th_av[s_idx] = _series(scenario, "district_wood_chip_boiler_available_th", n)

    bess_cap = max(0.0, _f(a, "battery_capacity_kwh"))
    bess_p = max(0.0, _f(a, "battery_power_kwh_per_step"))
    h2_cap = max(0.0, _f(a, "h2_tank_kwh"))
    ely_p = max(0.0, _f(a, "ely_power_kwh_per_step"))
    fc_p = max(0.0, _f(a, "fc_power_kwh_per_step"))
    hp_th_cap = max(0.0, _f(a, "district_heat_pump_kw_th"))
    dh_store_cap = max(0.0, _f(a, "district_thermal_storage_kwh_th"))

    bess_eta_ch = max(1e-9, _f(p, "bess_eta_charge", 1.0))
    bess_eta_dis = max(1e-9, _f(p, "bess_eta_discharge", 1.0))
    eta_ely = max(1e-9, _f(p, "eta_ely", 1.0))
    eta_fc = max(1e-9, _f(p, "eta_fc", 1.0))
    dh_eta_ch = max(1e-9, _f(p, "dh_storage_eta_charge", 1.0))
    dh_eta_dis = max(1e-9, _f(p, "dh_storage_eta_discharge", 1.0))
    dh_loss = max(0.0, _f(p, "dh_storage_loss_kwh_per_h", 0.0))

    bio_eta_el = _f(p, "district_biomass_chp_eta_el")
    bio_eta_th = _f(p, "district_biomass_chp_eta_th")
    bigas_eta_el = _f(p, "district_biogas_chp_eta_el")
    bigas_eta_th = _f(p, "district_biogas_chp_eta_th")
    gas_eta_el = _f(p, "district_gas_chp_eta_el")
    gas_eta_th = _f(p, "district_gas_chp_eta_th")
    gas_boiler_eta_th = max(1e-9, _f(p, "district_gas_boiler_eta_th", 1.0))
    wood_eta_th = max(1e-9, _f(p, "district_wood_chip_boiler_eta_th", 1.0))

    bio_ratio = _source_ratio(bio_eta_el, bio_eta_th)
    bigas_ratio = _source_ratio(bigas_eta_el, bigas_eta_th)
    gas_ratio = _source_ratio(gas_eta_el, gas_eta_th)

    bio_min = np.clip(_f(p, "district_biomass_chp_min_partload"), 0.0, 1.0)
    bigas_min = np.clip(_f(p, "district_biogas_chp_min_partload"), 0.0, 1.0)
    gas_min = np.clip(_f(p, "district_gas_chp_min_partload"), 0.0, 1.0)
    external_heat_min = np.clip(_f(p, "district_external_heat_min_partload"), 0.0, 1.0)
    gas_boiler_min = np.clip(_f(p, "district_gas_boiler_min_partload"), 0.0, 1.0)
    gas_boiler_max = np.clip(_f(p, "district_gas_boiler_max_partload", 1.0), 0.0, 1.0)
    wood_min = np.clip(_f(p, "district_wood_chip_boiler_min_partload"), 0.0, 1.0)
    wood_max = np.clip(_f(p, "district_wood_chip_boiler_max_partload", 1.0), 0.0, 1.0)
    if gas_boiler_max <= 0.0:
        gas_boiler_max = 1.0
    if wood_max <= 0.0:
        wood_max = 1.0

    bio_lhv = max(1e-9, _f(p, "district_biomass_chp_fuel_lhv_kwh_per_kg", 1.0))
    bigas_lhv = max(1e-9, _f(p, "district_biogas_chp_fuel_lhv_kwh_per_nm3", 1.0))
    gas_lhv = max(1e-9, _f(p, "district_gas_chp_fuel_lhv_kwh_per_m3", 1.0))
    gas_boiler_lhv = max(1e-9, _f(p, "district_gas_boiler_fuel_lhv_kwh_per_m3", 1.0))
    wood_lhv = max(1e-9, _f(p, "district_wood_chip_boiler_fuel_lhv_kwh_per_kg", 1.0))

    bio_fuel_cost = _f(p, "district_biomass_chp_fuel_cost_eur_per_kg")
    bigas_fuel_cost = _f(p, "district_biogas_chp_fuel_cost_eur_per_nm3")
    gas_fuel_cost = _f(p, "district_gas_chp_fuel_cost_eur_per_m3")
    gas_boiler_fuel_cost = _f(p, "district_gas_boiler_fuel_cost_eur_per_m3")
    gas_boiler_var_cost = _f(p, "district_gas_boiler_variable_cost_eur_per_kwh_th")
    external_heat_var_cost = _f(p, "district_external_heat_variable_cost_eur_per_kwh_th")
    wood_fuel_cost = _f(p, "district_wood_chip_boiler_fuel_cost_eur_per_kg")
    co2_cost_enabled = bool(p.get("dispatch_enable_co2_cost_model", True))
    objective_components_raw = p.get(
        "dispatch_objective_components",
        ["grid_import_cost", "grid_export_revenue", "fuel_cost", "co2_cost", "variable_opex"],
    )
    objective_components = {str(name) for name in objective_components_raw}
    gas_chp_co2_t_per_mwh = max(0.0, _f(p, "district_gas_chp_co2_t_per_mwh_fuel"))
    gas_boiler_co2_t_per_mwh = max(0.0, _f(p, "district_gas_boiler_co2_t_per_mwh_fuel"))
    gas_procurement_enabled = bool(p.get("dispatch_enable_gas_procurement_model", False))
    base_gas_price_mwh = None
    gas_day_ahead_price_day = None
    day_idx_of_t = np.array([t // 24 for t in range(n)], dtype=int)
    n_days = int(day_idx_of_t.max()) + 1 if n > 0 else 0
    fallback_gas_cost = max(gas_fuel_cost, gas_boiler_fuel_cost)
    fallback_gas_price_mwh = (
        fallback_gas_cost * 1000.0 / max(1e-9, gas_lhv) if fallback_gas_cost > 0.0 else None
    )
    if gas_procurement_enabled:
        if base_gas_day_ahead_price_raw is None:
            raise ValueError(
                "[dispatch.milp_two_stage] Gas procurement model requires dispatch_input.series['district_gas_day_ahead_price_eur_per_mwh_fuel'] "
                "(or legacy alias 'district_gas_price_eur_per_mwh_fuel') as known first-stage path."
            )
        if base_gas_balance_price_raw is None:
            raise ValueError(
                "[dispatch.milp_two_stage] Gas procurement model requires dispatch_input.series['district_gas_balance_price_eur_per_mwh_fuel']."
            )
        base_gas_price_mwh = _arr(base_gas_day_ahead_price_raw, n)
        if np.any(~np.isfinite(base_gas_price_mwh)) or np.any(base_gas_price_mwh <= 0.0):
            raise ValueError(
                "[dispatch.milp_two_stage] dispatch_input.series['district_gas_day_ahead_price_eur_per_mwh_fuel'] must be finite and strictly positive."
            )
        base_gas_balance_price_mwh = _arr(base_gas_balance_price_raw, n)
        if np.any(~np.isfinite(base_gas_balance_price_mwh)) or np.any(base_gas_balance_price_mwh <= 0.0):
            raise ValueError(
                "[dispatch.milp_two_stage] dispatch_input.series['district_gas_balance_price_eur_per_mwh_fuel'] must be finite and strictly positive."
            )
        gas_day_ahead_price_day = np.zeros(n_days, dtype=float)
        for d in range(n_days):
            mask = day_idx_of_t == d
            gas_day_ahead_price_day[d] = float(np.mean(base_gas_price_mwh[mask]))
        if np.any(~np.isfinite(gas_balance_price_mwh)):
            gas_balance_price_mwh = np.where(
                np.isfinite(gas_balance_price_mwh),
                gas_balance_price_mwh,
                np.tile(base_gas_balance_price_mwh.reshape(1, -1), (n_scen, 1)),
            )
        if np.any(gas_balance_price_mwh <= 0.0):
            raise ValueError(
                "[dispatch.milp_two_stage] district_gas_balance_price_eur_per_mwh_fuel must be strictly positive."
            )
    else:
        if np.any(~np.isfinite(gas_price_mwh)):
            if fallback_gas_price_mwh is None:
                raise ValueError(
                    "[dispatch.milp_two_stage] Missing 'district_gas_day_ahead_price_eur_per_mwh_fuel' "
                    "(or legacy alias 'district_gas_price_eur_per_mwh_fuel') in one or more scenarios and no positive gas-fuel-cost fallback is available."
                )
            gas_price_mwh = np.where(
                np.isfinite(gas_price_mwh),
                gas_price_mwh,
                np.full((n_scen, n), fallback_gas_price_mwh, dtype=float),
            )
        if np.any(gas_price_mwh <= 0.0):
            raise ValueError(
                "[dispatch.milp_two_stage] district_gas_day_ahead_price_eur_per_mwh_fuel must be strictly positive."
            )
    if co2_cost_enabled and (np.any(~np.isfinite(co2_price_eur_per_t)) or np.any(co2_price_eur_per_t <= 0.0)):
        raise ValueError(
            "[dispatch.milp_two_stage] co2_price_eur_per_tco2 must be finite and strictly positive in all scenarios."
        )
    big_m_import = demand + (hp_th_cap / np.maximum(hp_cop, 1e-9)) + bess_p + ely_p + 1.0
    big_m_export = pv_av + sw_av + lw_av + hydro_av + geo_el_av + (bio_th_av * bio_ratio) + (bigas_th_av * bigas_ratio) + (gas_th_av * gas_ratio) + fc_p + bess_p + 1.0
    unserved_penalty = float(p.get("dispatch_unserved_penalty_eur_per_kwh", 1e6) or 0.0)
    spill_penalty = float(p.get("dispatch_spill_penalty_eur_per_kwh", 1e-6) or 0.0)
    thermflex_enabled = bool(p.get("thermflex_enabled", False))
    thermflex_member_count = int(p.get("thermflex_member_count", 0) or 0)
    thermflex_use_explicit_lower_bounds = bool(p.get("thermflex_use_explicit_lower_bounds", False))
    thermflex_band_k = max(0.0, float(p.get("thermflex_comfort_band_k", 0.0) or 0.0))
    thermflex_ref_deadband_k = max(0.0, float(p.get("thermflex_reference_deadband_k", 0.0) or 0.0))
    thermflex_constrain_upper_temperature = bool(p.get("thermflex_constrain_upper_temperature", False))
    thermflex_max_duration_h = max(0, int(p.get("thermflex_max_duration_h", 0) or 0))
    thermflex_max_events_per_day = max(0, int(p.get("thermflex_max_events_per_day", 0) or 0))
    thermflex_activation_penalty = float(p.get("thermflex_activation_penalty_eur_per_member_h", 0.0) or 0.0)
    thermflex_temp_violation_penalty = float(
        p.get("thermflex_temp_violation_penalty_eur_per_degree_h", 0.0) or 0.0
    )
    thermflex_allow_terminal_deviation = bool(p.get("thermflex_allow_terminal_deviation", True))
    thermflex_terminal_band_k = max(0.0, float(p.get("thermflex_terminal_band_k", thermflex_band_k) or 0.0))
    thermflex_use_event_response_bounds = bool(p.get("thermflex_use_event_response_bounds", False))
    thermflex_event_peak_bounds = bool(p.get("thermflex_event_response_enforce_peak_bounds", False))
    thermflex_event_energy_bounds = bool(p.get("thermflex_event_response_enforce_energy_bounds", False))
    thermflex_event_recovery_cooldown = bool(
        p.get("thermflex_event_response_enforce_recovery_cooldown", False)
    )

    if thermflex_enabled:
        if thermflex_member_count <= 0:
            raise ValueError("[dispatch.milp_two_stage] thermflex_enabled requires thermflex_member_count > 0.")
        therm_alpha = np.asarray(p.get("thermflex_alpha"), dtype=float).reshape(-1)
        therm_beta_out = np.asarray(p.get("thermflex_beta_out"), dtype=float).reshape(-1)
        therm_gamma_internal = np.asarray(p.get("thermflex_gamma_internal"), dtype=float).reshape(-1)
        therm_gamma_solar = np.asarray(p.get("thermflex_gamma_solar"), dtype=float).reshape(-1)
        therm_gamma_heat = np.asarray(p.get("thermflex_gamma_heat"), dtype=float).reshape(-1)
        therm_q_heat_max = np.maximum(0.0, np.asarray(p.get("thermflex_q_heat_max_kwh"), dtype=float).reshape(-1))
        therm_t_in_initial = np.asarray(st.get("thermflex_t_in_initial_c"), dtype=float).reshape(-1)
        therm_preheat_event_energy_limit = None
        therm_preheat_peak_excess = None
        therm_cutback_event_energy_limit = None
        therm_cutback_peak_shed = None
        therm_recovery_time_h = None
        therm_recovery_rebound_energy = None
        for name, arr in {
            "thermflex_alpha": therm_alpha,
            "thermflex_beta_out": therm_beta_out,
            "thermflex_gamma_internal": therm_gamma_internal,
            "thermflex_gamma_solar": therm_gamma_solar,
            "thermflex_gamma_heat": therm_gamma_heat,
            "thermflex_q_heat_max_kwh": therm_q_heat_max,
            "thermflex_t_in_initial_c": therm_t_in_initial,
        }.items():
            if arr.size != thermflex_member_count:
                raise ValueError(
                    f"[dispatch.milp_two_stage] {name} length must equal thermflex_member_count={thermflex_member_count}."
                )
        if thermflex_use_event_response_bounds:
            therm_preheat_event_energy_limit = np.asarray(
                p.get("thermflex_preheat_event_energy_limit_kwh"),
                dtype=float,
            ).reshape(-1)
            therm_preheat_peak_excess = np.asarray(
                p.get("thermflex_preheat_peak_excess_kwh_per_step"),
                dtype=float,
            ).reshape(-1)
            therm_cutback_event_energy_limit = np.asarray(
                p.get("thermflex_cutback_event_energy_limit_kwh"),
                dtype=float,
            ).reshape(-1)
            therm_cutback_peak_shed = np.asarray(
                p.get("thermflex_cutback_peak_shed_kwh_per_step"),
                dtype=float,
            ).reshape(-1)
            therm_recovery_time_h = np.asarray(
                p.get("thermflex_recovery_time_to_reference_h"),
                dtype=float,
            ).reshape(-1)
            therm_recovery_rebound_energy = np.asarray(
                p.get("thermflex_recovery_rebound_energy_kwh"),
                dtype=float,
            ).reshape(-1)
            for name, arr in {
                "thermflex_preheat_event_energy_limit_kwh": therm_preheat_event_energy_limit,
                "thermflex_preheat_peak_excess_kwh_per_step": therm_preheat_peak_excess,
                "thermflex_cutback_event_energy_limit_kwh": therm_cutback_event_energy_limit,
                "thermflex_cutback_peak_shed_kwh_per_step": therm_cutback_peak_shed,
                "thermflex_recovery_time_to_reference_h": therm_recovery_time_h,
                "thermflex_recovery_rebound_energy_kwh": therm_recovery_rebound_energy,
            }.items():
                if arr.size != thermflex_member_count:
                    raise ValueError(
                        f"[dispatch.milp_two_stage] {name} length must equal thermflex_member_count={thermflex_member_count}."
                    )
                if np.any(~np.isfinite(arr)):
                    raise ValueError(
                        f"[dispatch.milp_two_stage] {name} must be finite for all thermflex members."
                    )
            if np.any(therm_preheat_event_energy_limit < 0.0):
                raise ValueError("[dispatch.milp_two_stage] thermflex_preheat_event_energy_limit_kwh must be >= 0.")
            if np.any(therm_preheat_peak_excess < 0.0):
                raise ValueError("[dispatch.milp_two_stage] thermflex_preheat_peak_excess_kwh_per_step must be >= 0.")
            if np.any(therm_cutback_event_energy_limit < 0.0):
                raise ValueError("[dispatch.milp_two_stage] thermflex_cutback_event_energy_limit_kwh must be >= 0.")
            if np.any(therm_cutback_peak_shed < 0.0):
                raise ValueError("[dispatch.milp_two_stage] thermflex_cutback_peak_shed_kwh_per_step must be >= 0.")
            if np.any(therm_recovery_time_h <= 0.0):
                raise ValueError("[dispatch.milp_two_stage] thermflex_recovery_time_to_reference_h must be > 0.")
            if np.any(therm_recovery_rebound_energy < 0.0):
                raise ValueError("[dispatch.milp_two_stage] thermflex_recovery_rebound_energy_kwh must be >= 0.")

        therm_t_ref = np.zeros((n_scen, thermflex_member_count, n), dtype=float)
        therm_t_out = np.zeros((n_scen, thermflex_member_count, n), dtype=float)
        therm_q_int = np.zeros((n_scen, thermflex_member_count, n), dtype=float)
        therm_q_sol = np.zeros((n_scen, thermflex_member_count, n), dtype=float)
        therm_q_ref = np.zeros((n_scen, thermflex_member_count, n), dtype=float)
        therm_residual = np.zeros((n_scen, thermflex_member_count, n), dtype=float)
        therm_t_lower_bound = np.zeros((n_scen, thermflex_member_count, n), dtype=float)
        for s_idx, scenario in enumerate(scenario_inputs):
            therm_t_ref[s_idx] = _matrix(scenario.series.get("thermflex_t_ref_c"), thermflex_member_count, n)
            therm_t_out[s_idx] = _matrix(scenario.series.get("thermflex_t_outdoor_c"), thermflex_member_count, n)
            therm_q_int[s_idx] = _matrix(
                scenario.series.get("thermflex_internal_gains_w_m2"), thermflex_member_count, n
            )
            therm_q_sol[s_idx] = _matrix(
                scenario.series.get("thermflex_solar_gains_w_m2"), thermflex_member_count, n
            )
            therm_q_ref[s_idx] = _matrix(scenario.series.get("thermflex_q_heat_ref_kwh"), thermflex_member_count, n)
            therm_residual[s_idx] = _matrix(scenario.series.get("thermflex_residual_c"), thermflex_member_count, n)
            if thermflex_use_explicit_lower_bounds:
                therm_t_lower_bound[s_idx] = _matrix(
                    scenario.series.get("thermflex_t_lower_bound_c"), thermflex_member_count, n
                )
            dh_space_heat_ref[s_idx] = np.sum(therm_q_ref[s_idx], axis=0)
            dh_demand[s_idx] = dh_space_heat_ref[s_idx] + dh_hotwater_demand[s_idx]

    print(
        "[dispatch.milp_two_stage] build start | "
        f"hours={n} | scenarios={n_scen} | procurement={'on' if gas_procurement_enabled else 'off'} | "
        f"thermflex_members={thermflex_member_count if thermflex_enabled else 0}",
        flush=True,
    )

    m = ConcreteModel()
    m.S = RangeSet(0, n_scen - 1)
    m.T = RangeSet(0, n - 1)
    if gas_procurement_enabled:
        m.D = RangeSet(0, n_days - 1)
    if thermflex_enabled:
        m.M = RangeSet(0, thermflex_member_count - 1)

    def nn2():
        return Var(m.S, m.T, within=NonNegativeReals)

    def nn1():
        return Var(m.T, within=NonNegativeReals)

    m.bio_on = Var(m.T, within=Binary)
    m.bigas_on = Var(m.T, within=Binary)
    m.gas_on = Var(m.T, within=Binary)
    m.wood_on = Var(m.T, within=Binary)
    m.dh_hp_plan = nn1()
    if gas_procurement_enabled:
        m.gas_day_ahead_base_mwh_per_h = Var(m.D, within=NonNegativeReals)
        m.gas_balance_mwh = nn2()

    m.grid_import = nn2()
    m.grid_export = nn2()
    m.grid_import_on = Var(m.S, m.T, within=Binary)
    m.grid_export_on = Var(m.S, m.T, within=Binary)
    m.pv_used = nn2()
    m.pv_spill = nn2()
    m.small_wind_used = nn2()
    m.small_wind_spill = nn2()
    m.large_wind_used = nn2()
    m.large_wind_spill = nn2()
    m.run_of_river_hydro_used = nn2()
    m.run_of_river_hydro_spill = nn2()
    m.geo_el_used = nn2()
    m.geo_el_spill = nn2()
    m.geo_th_used = nn2()
    m.geo_th_spill = nn2()
    m.solar_load = nn2()
    m.solar_charge = nn2()
    m.solar_spill = nn2()
    m.external_heat_th = nn2()
    m.external_heat_spill = nn2()
    m.external_heat_on = Var(m.T, within=Binary)
    m.waste_th = nn2()
    m.waste_spill = nn2()
    m.waste_on = Var(m.S, m.T, within=Binary)
    m.bess_charge = nn2()
    m.bess_discharge = nn2()
    m.bess_soc = nn2()
    m.bess_charge_on = Var(m.S, m.T, within=Binary)
    m.bess_discharge_on = Var(m.S, m.T, within=Binary)
    m.h2_charge = nn2()
    m.h2_discharge = nn2()
    m.h2_soc = nn2()
    m.h2_charge_on = Var(m.S, m.T, within=Binary)
    m.h2_discharge_on = Var(m.S, m.T, within=Binary)
    m.dh_hp_th = nn2()
    m.dh_storage_charge = nn2()
    m.dh_storage_discharge = nn2()
    m.dh_storage_soc = nn2()
    m.dh_storage_charge_on = Var(m.S, m.T, within=Binary)
    m.dh_storage_discharge_on = Var(m.S, m.T, within=Binary)
    m.bio_th = nn2()
    m.bio_spill = nn2()
    m.bigas_th = nn2()
    m.bigas_spill = nn2()
    m.gas_th = nn2()
    m.gas_spill = nn2()
    m.gas_boiler_th = nn2()
    m.gas_boiler_spill = nn2()
    m.gas_boiler_on = Var(m.T, within=Binary)
    m.wood_th = nn2()
    m.wood_spill = nn2()
    m.unserved_el = nn2()
    m.unserved_dh = nn2()
    if thermflex_enabled:
        m.therm_t_in = Var(m.S, m.M, RangeSet(0, n), within=NonNegativeReals)
        m.therm_q_heat = Var(m.S, m.M, m.T, within=NonNegativeReals)
        m.therm_flex_active = Var(m.S, m.M, m.T, within=Binary)
        m.therm_event_start = Var(m.S, m.M, m.T, within=Binary)
        m.therm_temp_violation_low = Var(m.S, m.M, m.T, within=NonNegativeReals)
        m.therm_temp_violation_high = Var(m.S, m.M, m.T, within=NonNegativeReals)
        if thermflex_use_event_response_bounds and thermflex_event_energy_bounds:
            m.therm_event_preheat_extra = Var(m.S, m.M, m.T, within=NonNegativeReals)
            m.therm_event_cutback_shed = Var(m.S, m.M, m.T, within=NonNegativeReals)

    m.c = ConstraintList()
    for t in range(n):
        m.c.add(m.dh_hp_plan[t] <= hp_th_cap)
        for s_idx in range(n_scen):
            if thermflex_enabled:
                for m_idx in range(thermflex_member_count):
                    if t == 0:
                        m.c.add(m.therm_t_in[s_idx, m_idx, 0] == float(therm_t_in_initial[m_idx]))
                    m.c.add(m.therm_q_heat[s_idx, m_idx, t] <= float(therm_q_heat_max[m_idx]))
                    q_ref_t = float(therm_q_ref[s_idx, m_idx, t])
                    q_heat_max_t = float(therm_q_heat_max[m_idx])
                    m.c.add(
                        m.therm_t_in[s_idx, m_idx, t + 1]
                        == float(therm_alpha[m_idx]) * m.therm_t_in[s_idx, m_idx, t]
                        + float(therm_beta_out[m_idx]) * float(therm_t_out[s_idx, m_idx, t])
                        + float(therm_gamma_internal[m_idx]) * float(therm_q_int[s_idx, m_idx, t])
                        + float(therm_gamma_solar[m_idx]) * float(therm_q_sol[s_idx, m_idx, t])
                        + float(therm_gamma_heat[m_idx]) * m.therm_q_heat[s_idx, m_idx, t]
                        + float(therm_residual[s_idx, m_idx, t])
                    )
                    if thermflex_use_explicit_lower_bounds:
                        setpoint_c = float(therm_t_ref[s_idx, m_idx, t])
                        lower_bound_c = float(therm_t_lower_bound[s_idx, m_idx, t])
                        if lower_bound_c > setpoint_c + 1e-9:
                            raise ValueError(
                                "[dispatch.milp_two_stage] thermflex_t_lower_bound_c must not exceed thermflex_t_ref_c."
                            )
                        m.c.add(
                            m.therm_t_in[s_idx, m_idx, t]
                            >= setpoint_c
                            - (setpoint_c - lower_bound_c) * m.therm_flex_active[s_idx, m_idx, t]
                            - m.therm_temp_violation_low[s_idx, m_idx, t]
                        )
                    else:
                        allowed_band = float(thermflex_ref_deadband_k) + float(thermflex_band_k) * m.therm_flex_active[
                            s_idx, m_idx, t
                        ]
                        m.c.add(
                            m.therm_t_in[s_idx, m_idx, t]
                            >= float(therm_t_ref[s_idx, m_idx, t]) - allowed_band - m.therm_temp_violation_low[s_idx, m_idx, t]
                        )
                    if thermflex_constrain_upper_temperature:
                        if thermflex_use_explicit_lower_bounds:
                            m.c.add(
                                m.therm_t_in[s_idx, m_idx, t]
                                <= float(therm_t_ref[s_idx, m_idx, t]) + m.therm_temp_violation_high[s_idx, m_idx, t]
                            )
                        else:
                            m.c.add(
                                m.therm_t_in[s_idx, m_idx, t]
                                <= float(therm_t_ref[s_idx, m_idx, t]) + allowed_band + m.therm_temp_violation_high[s_idx, m_idx, t]
                            )
                    if t == 0:
                        m.c.add(m.therm_event_start[s_idx, m_idx, t] >= m.therm_flex_active[s_idx, m_idx, t])
                    else:
                        m.c.add(
                            m.therm_event_start[s_idx, m_idx, t]
                            >= m.therm_flex_active[s_idx, m_idx, t] - m.therm_flex_active[s_idx, m_idx, t - 1]
                        )
                    # Flex activation is the explicit switch for any deviation
                    # from the reference heat trajectory. Without this gate,
                    # heat can be shifted while `therm_flex_active = 0`, which
                    # bypasses duration/event limits and invalidates the
                    # exported activation diagnostics.
                    m.c.add(
                        m.therm_q_heat[s_idx, m_idx, t] - q_ref_t
                        <= q_heat_max_t * m.therm_flex_active[s_idx, m_idx, t]
                    )
                    m.c.add(
                        q_ref_t - m.therm_q_heat[s_idx, m_idx, t]
                        <= q_ref_t * m.therm_flex_active[s_idx, m_idx, t]
                    )
                    if thermflex_use_event_response_bounds and thermflex_event_peak_bounds:
                        m.c.add(
                            m.therm_q_heat[s_idx, m_idx, t] - q_ref_t
                            <= float(therm_preheat_peak_excess[m_idx])
                            * m.therm_flex_active[s_idx, m_idx, t]
                        )
                        m.c.add(
                            q_ref_t - m.therm_q_heat[s_idx, m_idx, t]
                            <= float(therm_cutback_peak_shed[m_idx])
                            * m.therm_flex_active[s_idx, m_idx, t]
                        )
                    if thermflex_use_event_response_bounds and thermflex_event_energy_bounds:
                        m.c.add(
                            m.therm_event_preheat_extra[s_idx, m_idx, t]
                            >= m.therm_q_heat[s_idx, m_idx, t]
                            - q_ref_t
                        )
                        m.c.add(
                            m.therm_event_preheat_extra[s_idx, m_idx, t]
                            <= q_heat_max_t * m.therm_flex_active[s_idx, m_idx, t]
                        )
                        m.c.add(
                            m.therm_event_cutback_shed[s_idx, m_idx, t]
                            >= q_ref_t
                            - m.therm_q_heat[s_idx, m_idx, t]
                        )
                        m.c.add(
                            m.therm_event_cutback_shed[s_idx, m_idx, t]
                            <= q_ref_t * m.therm_flex_active[s_idx, m_idx, t]
                        )
            prev_bess = st.get("bess_soc_initial", 0.0) if t == 0 else m.bess_soc[s_idx, t - 1]
            prev_h2 = st.get("h2_soc_initial", 0.0) if t == 0 else m.h2_soc[s_idx, t - 1]
            prev_dh = st.get("district_thermal_storage_soc_initial", 0.0) if t == 0 else m.dh_storage_soc[s_idx, t - 1]

            m.c.add(m.pv_used[s_idx, t] + m.pv_spill[s_idx, t] == pv_av[s_idx, t])
            m.c.add(m.small_wind_used[s_idx, t] + m.small_wind_spill[s_idx, t] == sw_av[s_idx, t])
            m.c.add(m.large_wind_used[s_idx, t] + m.large_wind_spill[s_idx, t] == lw_av[s_idx, t])
            m.c.add(m.run_of_river_hydro_used[s_idx, t] + m.run_of_river_hydro_spill[s_idx, t] == hydro_av[s_idx, t])
            m.c.add(m.geo_el_used[s_idx, t] + m.geo_el_spill[s_idx, t] == geo_el_av[s_idx, t])
            m.c.add(m.geo_th_used[s_idx, t] + m.geo_th_spill[s_idx, t] == geo_th_av[s_idx, t])
            m.c.add(
                m.solar_load[s_idx, t] + m.solar_charge[s_idx, t] + m.solar_spill[s_idx, t]
                == solar_total_useful_av[s_idx, t]
            )
            m.c.add(
                m.external_heat_th[s_idx, t] + m.external_heat_spill[s_idx, t]
                <= external_heat_th_av[s_idx, t] * m.external_heat_on[t]
            )
            m.c.add(
                m.external_heat_th[s_idx, t] + m.external_heat_spill[s_idx, t]
                >= external_heat_th_av[s_idx, t] * external_heat_min * m.external_heat_on[t]
            )
            m.c.add(m.waste_th[s_idx, t] + m.waste_spill[s_idx, t] <= waste_th_av[s_idx, t] * m.waste_on[s_idx, t])

            m.c.add(m.grid_import[s_idx, t] <= big_m_import[s_idx, t] * m.grid_import_on[s_idx, t])
            m.c.add(m.grid_export[s_idx, t] <= big_m_export[s_idx, t] * m.grid_export_on[s_idx, t])
            m.c.add(m.grid_import_on[s_idx, t] + m.grid_export_on[s_idx, t] <= 1)

            m.c.add(m.bess_charge[s_idx, t] <= bess_p * m.bess_charge_on[s_idx, t])
            m.c.add(m.bess_discharge[s_idx, t] <= bess_p * m.bess_discharge_on[s_idx, t])
            m.c.add(m.bess_charge_on[s_idx, t] + m.bess_discharge_on[s_idx, t] <= 1)
            m.c.add(
                m.bess_soc[s_idx, t]
                == prev_bess + (bess_eta_ch * m.bess_charge[s_idx, t]) - (m.bess_discharge[s_idx, t] / bess_eta_dis)
            )
            m.c.add(m.bess_soc[s_idx, t] <= bess_cap)

            m.c.add(m.h2_charge[s_idx, t] <= ely_p * m.h2_charge_on[s_idx, t])
            m.c.add(m.h2_discharge[s_idx, t] <= fc_p * m.h2_discharge_on[s_idx, t])
            m.c.add(m.h2_charge_on[s_idx, t] + m.h2_discharge_on[s_idx, t] <= 1)
            m.c.add(m.h2_soc[s_idx, t] == prev_h2 + (eta_ely * m.h2_charge[s_idx, t]) - (m.h2_discharge[s_idx, t] / eta_fc))
            m.c.add(m.h2_soc[s_idx, t] <= h2_cap)

            m.c.add(m.dh_hp_th[s_idx, t] <= m.dh_hp_plan[t])
            m.c.add(m.dh_storage_charge[s_idx, t] <= dh_store_cap * m.dh_storage_charge_on[s_idx, t])
            m.c.add(m.dh_storage_discharge[s_idx, t] <= dh_store_cap * m.dh_storage_discharge_on[s_idx, t])
            m.c.add(m.dh_storage_charge_on[s_idx, t] + m.dh_storage_discharge_on[s_idx, t] <= 1)
            m.c.add(
                m.dh_storage_soc[s_idx, t]
                == prev_dh - dh_loss + (dh_eta_ch * m.dh_storage_charge[s_idx, t]) - (m.dh_storage_discharge[s_idx, t] / dh_eta_dis)
            )
            m.c.add(m.dh_storage_soc[s_idx, t] <= dh_store_cap)
            m.c.add(m.solar_charge[s_idx, t] <= m.dh_storage_charge[s_idx, t])

            m.c.add(m.bio_th[s_idx, t] + m.bio_spill[s_idx, t] <= bio_th_av[s_idx, t] * m.bio_on[t])
            m.c.add(m.bigas_th[s_idx, t] + m.bigas_spill[s_idx, t] <= bigas_th_av[s_idx, t] * m.bigas_on[t])
            m.c.add(m.gas_th[s_idx, t] + m.gas_spill[s_idx, t] <= gas_th_av[s_idx, t] * m.gas_on[t])
            m.c.add(
                m.gas_boiler_th[s_idx, t] + m.gas_boiler_spill[s_idx, t]
                <= gas_boiler_th_av[s_idx, t] * gas_boiler_max * m.gas_boiler_on[t]
            )
            m.c.add(m.wood_th[s_idx, t] + m.wood_spill[s_idx, t] <= wood_th_av[s_idx, t] * wood_max * m.wood_on[t])
            m.c.add(m.bio_th[s_idx, t] + m.bio_spill[s_idx, t] >= bio_th_av[s_idx, t] * bio_min * m.bio_on[t])
            m.c.add(m.bigas_th[s_idx, t] + m.bigas_spill[s_idx, t] >= bigas_th_av[s_idx, t] * bigas_min * m.bigas_on[t])
            m.c.add(m.gas_th[s_idx, t] + m.gas_spill[s_idx, t] >= gas_th_av[s_idx, t] * gas_min * m.gas_on[t])
            m.c.add(
                m.gas_boiler_th[s_idx, t] + m.gas_boiler_spill[s_idx, t]
                >= gas_boiler_th_av[s_idx, t] * gas_boiler_min * m.gas_boiler_on[t]
            )
            m.c.add(m.wood_th[s_idx, t] + m.wood_spill[s_idx, t] >= wood_th_av[s_idx, t] * wood_min * m.wood_on[t])
            if gas_procurement_enabled:
                gas_use_mwh = (
                    (m.gas_th[s_idx, t] / max(1e-9, gas_eta_th))
                    + (m.gas_boiler_th[s_idx, t] / gas_boiler_eta_th)
                ) / 1000.0
                m.c.add(
                    gas_use_mwh
                    <= m.gas_day_ahead_base_mwh_per_h[int(day_idx_of_t[t])] + m.gas_balance_mwh[s_idx, t]
                )

            hp_el = m.dh_hp_th[s_idx, t] / hp_cop[s_idx, t]
            bio_el = m.bio_th[s_idx, t] * bio_ratio
            bigas_el = m.bigas_th[s_idx, t] * bigas_ratio
            gas_el = m.gas_th[s_idx, t] * gas_ratio
            dh_effective_demand = (
                sum(m.therm_q_heat[s_idx, m_idx, t] for m_idx in range(thermflex_member_count))
                + float(dh_hotwater_demand[s_idx, t])
                if thermflex_enabled
                else float(dh_demand[s_idx, t])
            )

            m.c.add(
                m.pv_used[s_idx, t]
                + m.small_wind_used[s_idx, t]
                + m.large_wind_used[s_idx, t]
                + m.run_of_river_hydro_used[s_idx, t]
                + m.geo_el_used[s_idx, t]
                + bio_el
                + bigas_el
                + gas_el
                + m.bess_discharge[s_idx, t]
                + m.h2_discharge[s_idx, t]
                + m.grid_import[s_idx, t]
                + m.unserved_el[s_idx, t]
                == demand[s_idx, t] + hp_el + m.bess_charge[s_idx, t] + m.h2_charge[s_idx, t] + m.grid_export[s_idx, t]
            )
            m.c.add(
                m.geo_th_used[s_idx, t]
                + m.solar_load[s_idx, t]
                + m.solar_charge[s_idx, t]
                + m.external_heat_th[s_idx, t]
                + m.waste_th[s_idx, t]
                + m.bio_th[s_idx, t]
                + m.bigas_th[s_idx, t]
                + m.gas_th[s_idx, t]
                + m.gas_boiler_th[s_idx, t]
                + m.wood_th[s_idx, t]
                + m.dh_hp_th[s_idx, t]
                + m.dh_storage_discharge[s_idx, t]
                + m.unserved_dh[s_idx, t]
                == dh_effective_demand
                + m.dh_storage_charge[s_idx, t]
                + m.geo_th_spill[s_idx, t]
                + m.solar_spill[s_idx, t]
                + m.external_heat_spill[s_idx, t]
                + m.waste_spill[s_idx, t]
                + m.bio_spill[s_idx, t]
                + m.bigas_spill[s_idx, t]
                + m.gas_spill[s_idx, t]
                + m.gas_boiler_spill[s_idx, t]
                + m.wood_spill[s_idx, t]
            )
    if thermflex_enabled:
        for s_idx in range(n_scen):
            for m_idx in range(thermflex_member_count):
                for day_start in range(0, n, 24):
                    day_end = min(day_start + 24, n)
                    m.c.add(
                        sum(m.therm_flex_active[s_idx, m_idx, t] for t in range(day_start, day_end))
                        <= thermflex_max_duration_h
                    )
                    m.c.add(
                        sum(m.therm_event_start[s_idx, m_idx, t] for t in range(day_start, day_end))
                        <= thermflex_max_events_per_day
                    )
                if thermflex_use_event_response_bounds and thermflex_event_energy_bounds:
                    m.c.add(
                        sum(m.therm_event_preheat_extra[s_idx, m_idx, t] for t in range(n))
                        <= float(therm_preheat_event_energy_limit[m_idx])
                        * sum(m.therm_event_start[s_idx, m_idx, t] for t in range(n))
                    )
                    m.c.add(
                        sum(m.therm_event_cutback_shed[s_idx, m_idx, t] for t in range(n))
                        <= float(therm_cutback_event_energy_limit[m_idx])
                        * sum(m.therm_event_start[s_idx, m_idx, t] for t in range(n))
                    )
                if thermflex_use_event_response_bounds and thermflex_event_recovery_cooldown:
                    cooldown_steps = thermflex_max_duration_h + int(np.ceil(float(therm_recovery_time_h[m_idx])))
                    if cooldown_steps > 1:
                        for t in range(n):
                            window_end = min(n, t + cooldown_steps)
                            m.c.add(
                                sum(m.therm_event_start[s_idx, m_idx, tau] for tau in range(t, window_end)) <= 1
                            )
                if thermflex_allow_terminal_deviation:
                    if thermflex_use_explicit_lower_bounds:
                        m.c.add(
                            m.therm_t_in[s_idx, m_idx, n] >= float(therm_t_lower_bound[s_idx, m_idx, n - 1])
                        )
                    else:
                        terminal_band = float(thermflex_ref_deadband_k) + float(thermflex_terminal_band_k)
                        m.c.add(
                            m.therm_t_in[s_idx, m_idx, n] >= float(therm_t_ref[s_idx, m_idx, n - 1]) - terminal_band
                        )
                    if thermflex_constrain_upper_temperature:
                        if thermflex_use_explicit_lower_bounds:
                            m.c.add(
                                m.therm_t_in[s_idx, m_idx, n] <= float(therm_t_ref[s_idx, m_idx, n - 1])
                            )
                        else:
                            m.c.add(
                                m.therm_t_in[s_idx, m_idx, n] <= float(therm_t_ref[s_idx, m_idx, n - 1]) + terminal_band
                            )
                else:
                    m.c.add(m.therm_t_in[s_idx, m_idx, n] >= float(therm_t_ref[s_idx, m_idx, n - 1]))
                    if thermflex_constrain_upper_temperature:
                        m.c.add(m.therm_t_in[s_idx, m_idx, n] <= float(therm_t_ref[s_idx, m_idx, n - 1]))

    grid_import_cost_expr = sum(
        probabilities[s_idx] * sum(grid_buy[s_idx, t] * m.grid_import[s_idx, t] for t in range(n))
        for s_idx in range(n_scen)
    )
    grid_export_revenue_expr = sum(
        probabilities[s_idx] * sum(grid_sell[s_idx, t] * m.grid_export[s_idx, t] for t in range(n))
        for s_idx in range(n_scen)
    )
    non_gas_fuel_cost_expr = sum(
        probabilities[s_idx]
        * sum(
            (m.bio_th[s_idx, t] / max(1e-9, bio_eta_th)) / bio_lhv * bio_fuel_cost
            + (m.bigas_th[s_idx, t] / max(1e-9, bigas_eta_th)) / bigas_lhv * bigas_fuel_cost
            + (m.wood_th[s_idx, t] / wood_eta_th) / wood_lhv * wood_fuel_cost
            for t in range(n)
        )
        for s_idx in range(n_scen)
    )
    if gas_procurement_enabled:
        gas_procurement_day_ahead_cost_expr = sum(
            24.0 * gas_day_ahead_price_day[d] * m.gas_day_ahead_base_mwh_per_h[d]
            for d in range(n_days)
        )
        gas_procurement_balance_cost_expr = sum(
            probabilities[s_idx]
            * sum(gas_balance_price_mwh[s_idx, t] * m.gas_balance_mwh[s_idx, t] for t in range(n))
            for s_idx in range(n_scen)
        )
        gas_fuel_cost_expr = gas_procurement_day_ahead_cost_expr + gas_procurement_balance_cost_expr
    else:
        gas_fuel_cost_expr = sum(
            probabilities[s_idx]
            * sum(
                (m.gas_th[s_idx, t] / max(1e-9, gas_eta_th)) / 1000.0 * gas_price_mwh[s_idx, t]
                + (m.gas_boiler_th[s_idx, t] / gas_boiler_eta_th) / 1000.0 * gas_price_mwh[s_idx, t]
                for t in range(n)
            )
            for s_idx in range(n_scen)
        )
    fuel_cost_expr = non_gas_fuel_cost_expr + gas_fuel_cost_expr
    co2_cost_expr = 0.0
    if co2_cost_enabled:
        co2_cost_expr = sum(
            probabilities[s_idx]
            * sum(
                (m.gas_th[s_idx, t] / max(1e-9, gas_eta_th)) / 1000.0 * gas_chp_co2_t_per_mwh * co2_price_eur_per_t[s_idx, t]
                + (m.gas_boiler_th[s_idx, t] / gas_boiler_eta_th) / 1000.0 * gas_boiler_co2_t_per_mwh * co2_price_eur_per_t[s_idx, t]
                for t in range(n)
            )
            for s_idx in range(n_scen)
        )
    variable_opex_expr = sum(
        probabilities[s_idx]
        * sum(
            external_heat_var_cost * m.external_heat_th[s_idx, t]
            + gas_boiler_var_cost * m.gas_boiler_th[s_idx, t]
            for t in range(n)
        )
        for s_idx in range(n_scen)
    )
    unserved_penalty_expr = unserved_penalty * sum(
        probabilities[s_idx] * sum(m.unserved_el[s_idx, t] + m.unserved_dh[s_idx, t] for t in range(n))
        for s_idx in range(n_scen)
    )
    spill_penalty_expr = spill_penalty * sum(
        probabilities[s_idx]
        * sum(
            m.pv_spill[s_idx, t]
            + m.small_wind_spill[s_idx, t]
            + m.large_wind_spill[s_idx, t]
            + m.run_of_river_hydro_spill[s_idx, t]
            + m.geo_el_spill[s_idx, t]
            + m.geo_th_spill[s_idx, t]
            + m.solar_spill[s_idx, t]
            + m.external_heat_spill[s_idx, t]
            + m.waste_spill[s_idx, t]
            + m.bio_spill[s_idx, t]
            + m.bigas_spill[s_idx, t]
            + m.gas_spill[s_idx, t]
            + m.gas_boiler_spill[s_idx, t]
            + m.wood_spill[s_idx, t]
            for t in range(n)
        )
        for s_idx in range(n_scen)
    )
    thermflex_activation_expr = 0.0
    thermflex_violation_expr = 0.0
    if thermflex_enabled:
        thermflex_activation_expr = thermflex_activation_penalty * sum(
            probabilities[s_idx]
            * sum(
                m.therm_flex_active[s_idx, m_idx, t]
                for m_idx in range(thermflex_member_count)
                for t in range(n)
            )
            for s_idx in range(n_scen)
        )
        thermflex_violation_expr = thermflex_temp_violation_penalty * sum(
            probabilities[s_idx]
            * sum(
                m.therm_temp_violation_low[s_idx, m_idx, t]
                + (m.therm_temp_violation_high[s_idx, m_idx, t] if thermflex_constrain_upper_temperature else 0.0)
                for m_idx in range(thermflex_member_count)
                for t in range(n)
            )
            for s_idx in range(n_scen)
        )

    m.obj = Objective(
        expr=(grid_import_cost_expr if "grid_import_cost" in objective_components else 0.0)
        - (grid_export_revenue_expr if "grid_export_revenue" in objective_components else 0.0)
        + (fuel_cost_expr if "fuel_cost" in objective_components else 0.0)
        + (co2_cost_expr if "co2_cost" in objective_components else 0.0)
        + (variable_opex_expr if "variable_opex" in objective_components else 0.0)
        + unserved_penalty_expr
        + spill_penalty_expr
        + thermflex_activation_expr
        + thermflex_violation_expr,
        sense=minimize,
    )

    solver = SolverFactory("highs")
    print("[dispatch.milp_two_stage] solve start | solver=pyomo.highs", flush=True)
    result = solver.solve(m, tee=False)
    termination = str(result.solver.termination_condition).lower()
    if "optimal" not in termination and "feasible" not in termination:
        raise RuntimeError(
            f"[dispatch.milp_two_stage] Solver failed with termination condition '{result.solver.termination_condition}'."
        )
    print(
        f"[dispatch.milp_two_stage] solve done | termination={result.solver.termination_condition}",
        flush=True,
    )

    def vals2(var: Var) -> np.ndarray:
        out = np.zeros((n_scen, n), dtype=float)
        for s_idx in range(n_scen):
            for t in range(n):
                out[s_idx, t] = float(value(var[s_idx, t]))
        return out

    def vals1(var: Var) -> np.ndarray:
        return np.array([float(value(var[t])) for t in range(n)], dtype=float)

    pv_used = vals2(m.pv_used)
    sw_used = vals2(m.small_wind_used)
    lw_used = vals2(m.large_wind_used)
    hydro_used = vals2(m.run_of_river_hydro_used)
    geo_el_used = vals2(m.geo_el_used)
    geo_th_used = vals2(m.geo_th_used)
    solar_load = vals2(m.solar_load)
    solar_charge = vals2(m.solar_charge)
    external_heat_th = vals2(m.external_heat_th)
    waste_th = vals2(m.waste_th)
    bio_th = vals2(m.bio_th)
    bigas_th = vals2(m.bigas_th)
    gas_th = vals2(m.gas_th)
    gas_boiler_th = vals2(m.gas_boiler_th)
    wood_th = vals2(m.wood_th)
    gas_chp_fuel_input_kwh = gas_th / max(1e-9, gas_eta_th)
    gas_boiler_fuel_input_kwh = gas_boiler_th / gas_boiler_eta_th
    gas_chp_co2_t = (
        (gas_chp_fuel_input_kwh / 1000.0) * gas_chp_co2_t_per_mwh
        if co2_cost_enabled
        else np.zeros((n_scen, n), dtype=float)
    )
    gas_boiler_co2_t = (
        (gas_boiler_fuel_input_kwh / 1000.0) * gas_boiler_co2_t_per_mwh
        if co2_cost_enabled
        else np.zeros((n_scen, n), dtype=float)
    )
    dh_hp_th = vals2(m.dh_hp_th)
    dh_hp_el = dh_hp_th / np.maximum(hp_cop, 1e-9)
    bio_el = bio_th * bio_ratio
    bigas_el = bigas_th * bigas_ratio
    gas_el = gas_th * gas_ratio
    bess_charge = vals2(m.bess_charge)
    bess_discharge = vals2(m.bess_discharge)
    bess_soc = vals2(m.bess_soc)
    h2_charge = vals2(m.h2_charge)
    h2_discharge = vals2(m.h2_discharge)
    h2_soc = vals2(m.h2_soc)
    dh_charge = vals2(m.dh_storage_charge)
    dh_discharge = vals2(m.dh_storage_discharge)
    dh_soc = vals2(m.dh_storage_soc)
    dh_losses = np.full((n_scen, n), dh_loss, dtype=float)
    grid_import = vals2(m.grid_import)
    grid_export = vals2(m.grid_export)
    unserved_el = vals2(m.unserved_el)
    unserved_dh = vals2(m.unserved_dh)
    pv_spill = vals2(m.pv_spill)
    sw_spill = vals2(m.small_wind_spill)
    lw_spill = vals2(m.large_wind_spill)
    hydro_spill = vals2(m.run_of_river_hydro_spill)
    geo_el_spill = vals2(m.geo_el_spill)
    geo_th_spill = vals2(m.geo_th_spill)
    solar_spill = vals2(m.solar_spill)
    external_heat_spill = vals2(m.external_heat_spill)
    waste_spill = vals2(m.waste_spill)
    bio_spill = vals2(m.bio_spill)
    bigas_spill = vals2(m.bigas_spill)
    gas_spill = vals2(m.gas_spill)
    gas_boiler_spill = vals2(m.gas_boiler_spill)
    wood_spill = vals2(m.wood_spill)
    dh_hp_plan = vals1(m.dh_hp_plan)
    gas_day_ahead_procurement = np.zeros((n_scen, n), dtype=float)
    gas_balance_procurement = np.zeros((n_scen, n), dtype=float)
    if gas_procurement_enabled:
        gas_day_ahead_base_day = np.array(
            [float(value(m.gas_day_ahead_base_mwh_per_h[d])) for d in range(n_days)],
            dtype=float,
        )
        gas_day_ahead_procurement[:] = gas_day_ahead_base_day[day_idx_of_t].reshape(1, -1)
        gas_balance_procurement = vals2(m.gas_balance_mwh)
    if thermflex_enabled:
        therm_q_heat = np.zeros((n_scen, thermflex_member_count, n), dtype=float)
        therm_t_in = np.zeros((n_scen, thermflex_member_count, n + 1), dtype=float)
        therm_flex_active = np.zeros((n_scen, thermflex_member_count, n), dtype=float)
        therm_temp_violation = np.zeros((n_scen, thermflex_member_count, n), dtype=float)
        therm_event_preheat_extra = None
        therm_event_cutback_shed = None
        if thermflex_use_event_response_bounds and thermflex_event_energy_bounds:
            therm_event_preheat_extra = np.zeros((n_scen, thermflex_member_count, n), dtype=float)
            therm_event_cutback_shed = np.zeros((n_scen, thermflex_member_count, n), dtype=float)
        for s_idx in range(n_scen):
            for m_idx in range(thermflex_member_count):
                for t in range(n):
                    therm_q_heat[s_idx, m_idx, t] = float(value(m.therm_q_heat[s_idx, m_idx, t]))
                    therm_t_in[s_idx, m_idx, t] = float(value(m.therm_t_in[s_idx, m_idx, t]))
                    therm_flex_active[s_idx, m_idx, t] = float(value(m.therm_flex_active[s_idx, m_idx, t]))
                    if therm_event_preheat_extra is not None:
                        therm_event_preheat_extra[s_idx, m_idx, t] = float(
                            value(m.therm_event_preheat_extra[s_idx, m_idx, t])
                        )
                        therm_event_cutback_shed[s_idx, m_idx, t] = float(
                            value(m.therm_event_cutback_shed[s_idx, m_idx, t])
                        )
                    therm_temp_violation[s_idx, m_idx, t] = float(
                        value(m.therm_temp_violation_low[s_idx, m_idx, t])
                        + (
                            value(m.therm_temp_violation_high[s_idx, m_idx, t])
                            if thermflex_constrain_upper_temperature
                            else 0.0
                        )
                    )
                therm_t_in[s_idx, m_idx, n] = float(value(m.therm_t_in[s_idx, m_idx, n]))
        dh_space_heat = np.sum(therm_q_heat, axis=1)
        dh_demand_effective = dh_space_heat + dh_hotwater_demand
    else:
        dh_space_heat = dh_space_heat_ref
        dh_demand_effective = dh_demand
    dh_total_demand_ref = dh_space_heat_ref + dh_hotwater_demand

    electric_residual = (
        pv_used
        + sw_used
        + lw_used
        + hydro_used
        + geo_el_used
        + bio_el
        + bigas_el
        + gas_el
        + bess_discharge
        + h2_discharge
        + grid_import
        + unserved_el
        - (demand + dh_hp_el + bess_charge + h2_charge + grid_export)
    )
    dh_residual = (
        geo_th_used
        + solar_load
        + solar_charge
        + external_heat_th
        + waste_th
        + bio_th
        + bigas_th
        + gas_th
        + gas_boiler_th
        + wood_th
        + dh_hp_th
        + dh_discharge
        + unserved_dh
        - (
            dh_demand_effective
            + dh_charge
            + geo_th_spill
            + solar_spill
            + external_heat_spill
            + waste_spill
            + bio_spill
            + bigas_spill
            + gas_spill
            + gas_boiler_spill
            + wood_spill
        )
    )

    solar_generation = solar_load + solar_charge
    solar_direct = np.minimum(solar_load, solar_direct_av)
    solar_preheat = np.maximum(0.0, solar_load - solar_direct)

    hourly = {
        "grid_import": _weighted_average(grid_import, probabilities),
        "grid_export": _weighted_average(grid_export, probabilities),
        "bess_charged": _weighted_average(bess_charge, probabilities),
        "bess_discharged": _weighted_average(bess_discharge, probabilities),
        "bess_soc": _weighted_average(bess_soc, probabilities),
        "h2_charge_elec": _weighted_average(h2_charge, probabilities),
        "h2_discharge_elec": _weighted_average(h2_discharge, probabilities),
        "h2_soc": _weighted_average(h2_soc, probabilities),
        "pv_used": _weighted_average(pv_used, probabilities),
        "pv_spillage": _weighted_average(pv_spill, probabilities),
        "small_wind_used": _weighted_average(sw_used, probabilities),
        "small_wind_spillage": _weighted_average(sw_spill, probabilities),
        "large_wind_used": _weighted_average(lw_used, probabilities),
        "large_wind_spillage": _weighted_average(lw_spill, probabilities),
        "run_of_river_hydro_used": _weighted_average(hydro_used, probabilities),
        "run_of_river_hydro_spillage": _weighted_average(hydro_spill, probabilities),
        "district_heat_pump_plan": dh_hp_plan,
        "district_heat_pump_generation": _weighted_average(dh_hp_th, probabilities),
        "district_heat_pump_electricity": _weighted_average(dh_hp_el, probabilities),
        "district_heat_pump_cop": _weighted_average(hp_cop, probabilities),
        "district_thermal_storage_charge": _weighted_average(dh_charge, probabilities),
        "district_thermal_storage_discharge": _weighted_average(dh_discharge, probabilities),
        "district_thermal_storage_soc": _weighted_average(dh_soc, probabilities),
        "district_thermal_storage_losses": _weighted_average(dh_losses, probabilities),
        "district_geothermal_electric_generation": _weighted_average(geo_el_used, probabilities),
        "district_geothermal_electric_spillage": _weighted_average(geo_el_spill, probabilities),
        "district_geothermal_thermal_generation": _weighted_average(geo_th_used, probabilities),
        "district_geothermal_thermal_spillage": _weighted_average(geo_th_spill, probabilities),
        "district_solar_thermal_generation": _weighted_average(solar_generation, probabilities),
        "district_solar_thermal_direct_feed": _weighted_average(solar_direct, probabilities),
        "district_solar_thermal_preheat": _weighted_average(solar_preheat, probabilities),
        "district_solar_thermal_storage_charge": _weighted_average(solar_charge, probabilities),
        "district_solar_thermal_thermal_spillage": _weighted_average(solar_spill, probabilities),
        "district_external_heat_generation": _weighted_average(external_heat_th, probabilities),
        "district_external_heat_thermal_spillage": _weighted_average(external_heat_spill, probabilities),
        "district_waste_incineration_generation": _weighted_average(waste_th, probabilities),
        "district_waste_incineration_thermal_spillage": _weighted_average(waste_spill, probabilities),
        "district_biomass_chp_electric_generation": _weighted_average(bio_el, probabilities),
        "district_biomass_chp_thermal_generation": _weighted_average(bio_th, probabilities),
        "district_biomass_chp_thermal_spillage": _weighted_average(bio_spill, probabilities),
        "district_biomass_chp_fuel_input_kwh": _weighted_average(bio_th / max(1e-9, bio_eta_th), probabilities),
        "district_biomass_chp_fuel_input_kg": _weighted_average((bio_th / max(1e-9, bio_eta_th)) / bio_lhv, probabilities),
        "district_biogas_chp_electric_generation": _weighted_average(bigas_el, probabilities),
        "district_biogas_chp_thermal_generation": _weighted_average(bigas_th, probabilities),
        "district_biogas_chp_thermal_spillage": _weighted_average(bigas_spill, probabilities),
        "district_biogas_chp_fuel_input_kwh": _weighted_average(bigas_th / max(1e-9, bigas_eta_th), probabilities),
        "district_biogas_chp_fuel_input_nm3": _weighted_average((bigas_th / max(1e-9, bigas_eta_th)) / bigas_lhv, probabilities),
        "district_gas_chp_electric_generation": _weighted_average(gas_el, probabilities),
        "district_gas_chp_thermal_generation": _weighted_average(gas_th, probabilities),
        "district_gas_chp_thermal_spillage": _weighted_average(gas_spill, probabilities),
        "district_gas_chp_fuel_input_kwh": _weighted_average(gas_chp_fuel_input_kwh, probabilities),
        "district_gas_chp_fuel_input_m3": _weighted_average(gas_chp_fuel_input_kwh / gas_lhv, probabilities),
        "district_gas_chp_co2_t": _weighted_average(gas_chp_co2_t, probabilities),
        "district_gas_boiler_generation": _weighted_average(gas_boiler_th, probabilities),
        "district_gas_boiler_thermal_spillage": _weighted_average(gas_boiler_spill, probabilities),
        "district_gas_boiler_fuel_input_kwh": _weighted_average(gas_boiler_fuel_input_kwh, probabilities),
        "district_gas_boiler_fuel_input_m3": _weighted_average(gas_boiler_fuel_input_kwh / gas_boiler_lhv, probabilities),
        "district_gas_boiler_co2_t": _weighted_average(gas_boiler_co2_t, probabilities),
        "district_gas_day_ahead_procurement_mwh_fuel": _weighted_average(gas_day_ahead_procurement, probabilities),
        "district_gas_balance_procurement_mwh_fuel": _weighted_average(gas_balance_procurement, probabilities),
        "district_wood_chip_boiler_generation": _weighted_average(wood_th, probabilities),
        "district_wood_chip_boiler_thermal_spillage": _weighted_average(wood_spill, probabilities),
        "district_wood_chip_boiler_fuel_input_kwh": _weighted_average(wood_th / wood_eta_th, probabilities),
        "district_wood_chip_boiler_fuel_input_kg": _weighted_average((wood_th / wood_eta_th) / wood_lhv, probabilities),
        "district_space_heat_demand": _weighted_average(dh_space_heat, probabilities),
        "district_space_heat_demand_ref": _weighted_average(dh_space_heat_ref, probabilities),
        "district_hotwater_demand": _weighted_average(dh_hotwater_demand, probabilities),
        "dh_total_demand": _weighted_average(dh_demand_effective, probabilities),
        "dh_total_demand_ref": _weighted_average(dh_total_demand_ref, probabilities),
        "dh_total_delivered": _weighted_average(np.maximum(0.0, dh_demand_effective - unserved_dh), probabilities),
        "dh_unserved_heat": _weighted_average(unserved_dh, probabilities),
        "unserved_el": _weighted_average(unserved_el, probabilities),
    }
    objective_terms = {
        "grid_import_cost": float(value(grid_import_cost_expr)),
        "grid_export_revenue": float(value(grid_export_revenue_expr)),
        "fuel_cost": float(value(fuel_cost_expr)),
        "co2_cost": float(value(co2_cost_expr)) if co2_cost_enabled else 0.0,
        "variable_opex": float(value(variable_opex_expr)),
        "unserved_penalty": float(value(unserved_penalty_expr)),
        "spill_penalty": float(value(spill_penalty_expr)),
        "thermflex_activation_penalty": float(value(thermflex_activation_expr)),
        "temperature_violation_penalty": float(value(thermflex_violation_expr)),
    }
    diagnostics = {
        "mode": "milp_two_stage",
        "solver": "pyomo.highs",
        "scenario_source": bundle.source,
        "reduction_method": bundle.reduction_method,
        "n_scenarios_used": int(n_scen),
        "gas_procurement_enabled": bool(gas_procurement_enabled),
        "used_solar_thermal_kwh_day": float(np.sum(hourly["district_solar_thermal_generation"])),
        "used_external_heat_kwh_day": float(np.sum(hourly["district_external_heat_generation"])),
        "used_waste_incineration_kwh_day": float(np.sum(hourly["district_waste_incineration_generation"])),
        "used_biomass_feedstock_kwh_day": float(np.sum(hourly["district_biomass_chp_fuel_input_kwh"] + hourly["district_wood_chip_boiler_fuel_input_kwh"])),
        "used_biogas_feedstock_kwh_day": float(np.sum(hourly["district_biogas_chp_fuel_input_kwh"])),
        "scenario_labels": list(bundle.labels),
        "scenario_probabilities": probabilities.tolist(),
        "implementation_note": "extensive-form two-stage MILP with shared first-stage commitments and DH heat-pump plan",
        "max_electric_balance_residual": float(np.max(np.abs(electric_residual))) if n_scen and n else 0.0,
        "max_dh_balance_residual": float(np.max(np.abs(dh_residual))) if n_scen and n else 0.0,
        "bess_simultaneous_steps": int(np.sum((bess_charge > 1e-9) & (bess_discharge > 1e-9))),
        "h2_simultaneous_steps": int(np.sum((h2_charge > 1e-9) & (h2_discharge > 1e-9))),
        "dh_storage_simultaneous_steps": int(np.sum((dh_charge > 1e-9) & (dh_discharge > 1e-9))),
        "grid_simultaneous_steps": int(np.sum((grid_import > 1e-9) & (grid_export > 1e-9))),
        "district_biomass_chp_on_steps": int(np.sum(vals1(m.bio_on) > 0.5)),
        "district_biogas_chp_on_steps": int(np.sum(vals1(m.bigas_on) > 0.5)),
        "district_external_heat_on_steps": int(np.sum(vals1(m.external_heat_on) > 0.5)),
        "district_gas_chp_on_steps": int(np.sum(vals1(m.gas_on) > 0.5)),
        "district_gas_boiler_on_steps": int(np.sum(vals1(m.gas_boiler_on) > 0.5)),
        "district_wood_chip_boiler_on_steps": int(np.sum(vals1(m.wood_on) > 0.5)),
        "district_gas_chp_co2_t_total": float(np.sum(hourly["district_gas_chp_co2_t"])),
        "district_gas_boiler_co2_t_total": float(np.sum(hourly["district_gas_boiler_co2_t"])),
        "district_gas_boiler_peak_kw": compute_series_peak_kw(gas_boiler_th, probabilities=probabilities),
    }
    if gas_procurement_enabled:
        diagnostics["gas_day_ahead_procurement_total_mwh_fuel"] = float(np.sum(hourly["district_gas_day_ahead_procurement_mwh_fuel"]))
        diagnostics["gas_balance_procurement_total_mwh_fuel"] = float(np.sum(hourly["district_gas_balance_procurement_mwh_fuel"]))
    if thermflex_enabled:
        hourly["thermflex_active_total"] = _weighted_average(np.sum(therm_flex_active, axis=1), probabilities)
        hourly["thermflex_temperature_violation_degree_h"] = _weighted_average(
            np.sum(therm_temp_violation, axis=1), probabilities
        )
        # The coupled integrated-energy-system path expects the same member-level
        # hourly contract from `milp_two_stage` as from `milp_day_ahead`.
        #
        # We therefore export probability-weighted member trajectories here instead
        # of silently dropping them. This keeps the downstream cohort-utilization
        # analysis and terminal-state handover identical across deterministic and
        # stochastic dispatch modes.
        scenario_weights_3d = probabilities.reshape(-1, 1, 1)
        hourly["thermflex_member_q_heat_kwh"] = np.sum(
            scenario_weights_3d * therm_q_heat,
            axis=0,
        )
        hourly["thermflex_member_q_heat_ref_kwh"] = np.sum(
            scenario_weights_3d * therm_q_ref,
            axis=0,
        )
        hourly["thermflex_member_flex_active"] = np.sum(
            scenario_weights_3d * therm_flex_active,
            axis=0,
        )
        hourly["thermflex_member_event_start"] = np.array(
            [
                [
                    float(
                        np.sum(
                            probabilities
                            * np.array(
                                [value(m.therm_event_start[s_idx, m_idx, t]) for s_idx in range(n_scen)],
                                dtype=float,
                            )
                        )
                    )
                    for t in range(n)
                ]
                for m_idx in range(thermflex_member_count)
            ],
            dtype=float,
        )
        hourly["thermflex_member_temp_violation_degree_h"] = np.sum(
            scenario_weights_3d * therm_temp_violation,
            axis=0,
        )
        hourly["thermflex_member_t_in_c"] = np.sum(
            scenario_weights_3d * therm_t_in[:, :, :-1],
            axis=0,
        )
        # The coupled caller always requires explicit member-level event-energy
        # arrays. When the event-energy bound layer is inactive we return strict
        # zero matrices instead of omitting the keys, so the disabled behavior is
        # explicit and shape-stable.
        hourly["thermflex_member_event_preheat_extra_kwh"] = (
            np.sum(scenario_weights_3d * therm_event_preheat_extra, axis=0)
            if therm_event_preheat_extra is not None
            else np.zeros((thermflex_member_count, n), dtype=float)
        )
        hourly["thermflex_member_event_cutback_shed_kwh"] = (
            np.sum(scenario_weights_3d * therm_event_cutback_shed, axis=0)
            if therm_event_cutback_shed is not None
            else np.zeros((thermflex_member_count, n), dtype=float)
        )
        thermflex_metrics = compute_thermflex_series_metrics(
            dh_space_heat,
            dh_space_heat_ref,
            probabilities=probabilities,
        )
        hourly["thermflex_space_heat_delta_kwh"] = np.asarray(
            thermflex_metrics["thermflex_space_heat_delta_kwh"], dtype=float
        )
        hourly["thermflex_virtual_storage_inventory_kwh"] = np.asarray(
            thermflex_metrics["thermflex_virtual_storage_inventory_kwh"], dtype=float
        )
        diagnostics["thermflex_member_count"] = thermflex_member_count
        diagnostics["thermflex_active_member_hours_total"] = float(
            np.sum(probabilities.reshape(-1, 1, 1) * therm_flex_active)
        )
        diagnostics["thermflex_temperature_violation_degree_hours_total"] = float(
            np.sum(probabilities.reshape(-1, 1, 1) * therm_temp_violation)
        )
        diagnostics["thermflex_shifted_space_heat_kwh"] = float(
            thermflex_metrics["thermflex_shifted_space_heat_kwh"]
        )
        diagnostics["thermflex_additional_space_heat_kwh"] = float(
            thermflex_metrics["thermflex_additional_space_heat_kwh"]
        )
        diagnostics["thermflex_rebound_kwh"] = float(thermflex_metrics["thermflex_rebound_kwh"])
        diagnostics["thermflex_peak_change_kw"] = float(thermflex_metrics["thermflex_peak_change_kw"])
        diagnostics["dh_total_peak_change_kw"] = compute_series_peak_change_kw(
            dh_demand_effective,
            dh_total_demand_ref,
            probabilities=probabilities,
        )
        diagnostics["thermflex_heat_up_ramp_kw_per_h"] = float(
            thermflex_metrics["thermflex_heat_up_ramp_kw_per_h"]
        )
        diagnostics["thermflex_heat_down_ramp_kw_per_h"] = float(
            thermflex_metrics["thermflex_heat_down_ramp_kw_per_h"]
        )
        diagnostics["thermflex_effective_thermal_storage_kwh"] = float(
            thermflex_metrics["thermflex_effective_thermal_storage_kwh"]
        )
        diagnostics["thermflex_max_preheat_headroom_kwh"] = float(
            thermflex_metrics["thermflex_max_preheat_headroom_kwh"]
        )
        diagnostics["thermflex_t_in_max_c"] = float(np.max(therm_t_in))
        diagnostics["thermflex_t_in_min_c"] = float(np.min(therm_t_in))
        diagnostics["thermflex_t_in_terminal_c"] = (
            np.sum(probabilities.reshape(-1, 1) * therm_t_in[:, :, -1], axis=0).tolist()
        )
        diagnostics["thermflex_event_response_bounds_active"] = bool(thermflex_use_event_response_bounds)
        diagnostics["thermflex_event_peak_bounds_active"] = bool(
            thermflex_use_event_response_bounds and thermflex_event_peak_bounds
        )
        diagnostics["thermflex_event_energy_bounds_active"] = bool(
            thermflex_use_event_response_bounds and thermflex_event_energy_bounds
        )
        diagnostics["thermflex_event_recovery_cooldown_active"] = bool(
            thermflex_use_event_response_bounds and thermflex_event_recovery_cooldown
        )
        if thermflex_use_event_response_bounds:
            diagnostics["thermflex_preheat_event_energy_limit_kwh_total"] = float(
                np.sum(therm_preheat_event_energy_limit)
            )
            diagnostics["thermflex_cutback_event_energy_limit_kwh_total"] = float(
                np.sum(therm_cutback_event_energy_limit)
            )
            diagnostics["thermflex_recovery_rebound_energy_kwh_total"] = float(
                np.sum(therm_recovery_rebound_energy)
            )
            diagnostics["thermflex_recovery_time_to_reference_h_mean"] = float(
                np.mean(therm_recovery_time_h)
            )
            diagnostics["thermflex_recovery_time_to_reference_h_max"] = float(
                np.max(therm_recovery_time_h)
            )
            diagnostics["thermflex_preheat_peak_excess_kwh_per_step_max"] = float(
                np.max(therm_preheat_peak_excess)
            )
            diagnostics["thermflex_cutback_peak_shed_kwh_per_step_max"] = float(
                np.max(therm_cutback_peak_shed)
            )
            diagnostics["thermflex_event_preheat_extra_realized_kwh"] = float(
                np.sum(probabilities.reshape(-1, 1, 1) * therm_event_preheat_extra)
                if therm_event_preheat_extra is not None
                else 0.0
            )
            diagnostics["thermflex_event_cutback_shed_realized_kwh"] = float(
                np.sum(probabilities.reshape(-1, 1, 1) * therm_event_cutback_shed)
                if therm_event_cutback_shed is not None
                else 0.0
            )
    else:
        diagnostics["dh_total_peak_change_kw"] = 0.0
    diagnostics["district_gas_boiler_peak_kw"] = compute_series_peak_kw(
        gas_boiler_th,
        probabilities=probabilities,
    )
    return DispatchResult(hourly=hourly, objective_terms=objective_terms, diagnostics=diagnostics)
