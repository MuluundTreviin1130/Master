from __future__ import annotations

from typing import Any

import numpy as np
from pyomo.environ import Binary, ConcreteModel, ConstraintList, NonNegativeReals, Objective, RangeSet, SolverFactory, Var, minimize, value

from dispatch.core import DispatchInput, DispatchResult
from dispatch.metrics import compute_series_peak_change_kw, compute_series_peak_kw, compute_thermflex_series_metrics
from dispatch.modes.series_validation import dispatch_series_array, optional_dispatch_series


def _arr(values: Any, n: int, *, label: str) -> np.ndarray:
    return dispatch_series_array(values, n, label=label)


def _f(mapping: dict[str, Any], key: str, default: float = 0.0) -> float:
    return float(mapping.get(key, default) or default)


def _opt_nonneg(mapping: dict[str, Any], key: str) -> float | None:
    value = mapping.get(key)
    if value is None:
        return None
    return max(0.0, float(value))


def _source_ratio(eta_el: float, eta_th: float) -> float:
    return float(eta_el / eta_th) if eta_el > 0.0 and eta_th > 0.0 else 0.0


def _district_gas_chp_operating_points(params: dict[str, Any]) -> dict[str, Any]:
    """Read the explicit gas-CHP operating region from dispatch params.

    The current repo keeps the fixed-ratio CHP path as the active default. Once
    ``piecewise_power_heat_v1`` is enabled we require the normalized point set
    to be present explicitly in ``DispatchInput.params`` so the MILP can stay
    fully data-driven and fail fast on incomplete CHP mode definitions.
    """

    mode = str(params.get("district_gas_chp_operating_mode_model", "fixed_ratio") or "fixed_ratio").strip().lower()
    names_raw = params.get("district_gas_chp_operating_point_names", ())
    eta_el_raw = params.get("district_gas_chp_operating_point_eta_el", ())
    eta_th_raw = params.get("district_gas_chp_operating_point_eta_th", ())
    names = list(names_raw) if isinstance(names_raw, (list, tuple)) else []
    eta_el = np.asarray(eta_el_raw, dtype=float).reshape(-1) if len(eta_el_raw) else np.zeros(0, dtype=float)
    eta_th = np.asarray(eta_th_raw, dtype=float).reshape(-1) if len(eta_th_raw) else np.zeros(0, dtype=float)
    if mode == "fixed_ratio":
        return {
            "mode": mode,
            "names": [],
            "p_norm": np.zeros(0, dtype=float),
            "q_norm": np.zeros(0, dtype=float),
            "fuel_norm": np.zeros(0, dtype=float),
            "max_q_norm": 0.0,
        }
    if mode != "piecewise_power_heat_v1":
        raise ValueError(
            "[dispatch.milp_day_ahead] district_gas_chp_operating_mode_model must be "
            "'fixed_ratio' or 'piecewise_power_heat_v1'."
        )
    if not names or eta_el.size == 0 or eta_th.size == 0:
        raise ValueError(
            "[dispatch.milp_day_ahead] piecewise gas-CHP mode requires explicit operating point names and eta arrays."
        )
    if not (len(names) == eta_el.size == eta_th.size):
        raise ValueError(
            "[dispatch.milp_day_ahead] district_gas_chp operating point names, eta_el and eta_th must have equal length."
        )
    if np.any(~np.isfinite(eta_el)) or np.any(eta_el <= 0.0):
        raise ValueError("[dispatch.milp_day_ahead] district_gas_chp operating-point eta_el must be finite and > 0.")
    if np.any(~np.isfinite(eta_th)) or np.any(eta_th <= 0.0):
        raise ValueError("[dispatch.milp_day_ahead] district_gas_chp operating-point eta_th must be finite and > 0.")
    if np.any((eta_el + eta_th) > 1.0 + 1e-9):
        raise ValueError(
            "[dispatch.milp_day_ahead] district_gas_chp operating-point total efficiency must not exceed 1.0."
        )
    base_eta_el = float(np.max(eta_el))
    p_norm = eta_el / base_eta_el
    q_norm = eta_th / base_eta_el
    fuel_norm = np.full(eta_el.size, 1.0 / base_eta_el, dtype=float)
    return {
        "mode": mode,
        "names": [str(name) for name in names],
        "p_norm": p_norm,
        "q_norm": q_norm,
        "fuel_norm": fuel_norm,
        "max_q_norm": float(np.max(q_norm)),
    }


def _series(dispatch_input: DispatchInput, key: str, n: int) -> np.ndarray:
    return optional_dispatch_series(dispatch_input.series, key, n, default=0.0, nonnegative=True)


def _matrix(values: Any, rows: int, cols: int) -> np.ndarray:
    arr = np.asarray(values, dtype=float)
    if arr.shape != (rows, cols):
        raise ValueError(
            f"[dispatch.milp_day_ahead] Expected matrix shape {(rows, cols)}, got {arr.shape}."
        )
    return arr


def _string_list(values: Any, expected: int, label: str) -> list[str]:
    """Validate explicit thermflex member labels.

    The cohort-utilization analysis should fail immediately when the coupled
    dispatch input forgets to pass member metadata. Silent empty strings would
    make the later cohort aggregation ambiguous, so this helper is strict on
    both presence and length.
    """

    if values is None:
        raise ValueError(f"[dispatch.milp_day_ahead] Missing required thermflex label list '{label}'.")
    if isinstance(values, np.ndarray):
        flat = values.reshape(-1).tolist()
    elif isinstance(values, (list, tuple)):
        flat = list(values)
    else:
        raise TypeError(f"[dispatch.milp_day_ahead] Thermflex label list '{label}' must be list-like.")
    if len(flat) != expected:
        raise ValueError(
            f"[dispatch.milp_day_ahead] Thermflex label list '{label}' length must equal "
            f"thermflex_member_count={expected}, got {len(flat)}."
        )
    return [str(item) for item in flat]


def run_milp_day_ahead_dispatch(dispatch_input: DispatchInput, **_: Any) -> DispatchResult:
    demand = np.maximum(0.0, np.asarray(dispatch_input.series["electric_non_dispatch_demand"], dtype=float).reshape(-1))
    n = int(demand.size)
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
            diagnostics={"mode": "milp_day_ahead", "solver": "pyomo.highs", "termination_condition": "empty"},
        )

    s = dispatch_input.series
    a = dispatch_input.assets
    p = dispatch_input.params
    st = dispatch_input.initial_state

    pv_av = _series(dispatch_input, "pv_available", n)
    sw_av = _series(dispatch_input, "small_wind_available", n)
    lw_av = _series(dispatch_input, "large_wind_available", n)
    hydro_av = _series(dispatch_input, "run_of_river_hydro_available", n)
    grid_buy = optional_dispatch_series(s, "grid_import_price", n)
    grid_sell = optional_dispatch_series(s, "grid_export_price", n)
    dh_demand = _series(dispatch_input, "district_heat_demand", n)
    dh_space_heat_ref = _series(dispatch_input, "district_space_heat_demand", n)
    dh_hotwater_demand = _series(dispatch_input, "district_hotwater_demand", n)
    hp_cop = np.maximum(1e-9, optional_dispatch_series(s, "district_heat_pump_cop", n, default=1.0))
    geo_el_av = _series(dispatch_input, "district_geothermal_available_el", n)
    geo_th_av = _series(dispatch_input, "district_geothermal_available_th", n)
    solar_direct_av = _series(dispatch_input, "district_solar_thermal_direct_available_th", n)
    solar_total_useful_av = _series(dispatch_input, "district_solar_thermal_total_useful_available_th", n)
    external_heat_th_av = _series(dispatch_input, "district_external_heat_available_th", n)
    waste_th_av = _series(dispatch_input, "district_waste_incineration_available_th", n)
    bio_th_av = _series(dispatch_input, "district_biomass_chp_available_th", n)
    bigas_th_av = _series(dispatch_input, "district_biogas_chp_available_th", n)
    gas_el_av_raw = s.get("district_gas_chp_available_el")
    gas_power_priority_signal = optional_dispatch_series(
        s,
        "district_gas_chp_power_priority_signal",
        n,
        default=1.0,
    )
    gas_th_av = _series(dispatch_input, "district_gas_chp_available_th", n)
    gas_boiler_th_av = _series(dispatch_input, "district_gas_boiler_available_th", n)
    wood_th_av = _series(dispatch_input, "district_wood_chip_boiler_available_th", n)

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
    gas_chp_points = _district_gas_chp_operating_points(p)
    gas_chp_piecewise = gas_chp_points["mode"] == "piecewise_power_heat_v1"
    gas_power_priority_mode = str(
        p.get("district_gas_chp_power_priority_mode", "free") or "free"
    ).strip().lower()
    if gas_chp_piecewise:
        if gas_el_av_raw is None:
            raise ValueError(
                "[dispatch.milp_day_ahead] piecewise gas-CHP mode requires series['district_gas_chp_available_el']."
            )
        gas_el_av = _series(dispatch_input, "district_gas_chp_available_el", n)
    else:
        gas_el_av = np.zeros(n, dtype=float)

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
    co2_price_raw = s.get("co2_price_eur_per_tco2")
    gas_price_raw = s.get("district_gas_day_ahead_price_eur_per_mwh_fuel", s.get("district_gas_price_eur_per_mwh_fuel"))
    if gas_price_raw is None:
        fallback_gas_cost = max(gas_fuel_cost, gas_boiler_fuel_cost)
        if fallback_gas_cost <= 0.0:
            raise ValueError(
                "[dispatch.milp_day_ahead] Missing 'district_gas_day_ahead_price_eur_per_mwh_fuel' "
                "(or legacy alias 'district_gas_price_eur_per_mwh_fuel') and no positive gas-fuel-cost fallback is available."
            )
        gas_price_mwh = np.full(n, fallback_gas_cost * 1000.0 / max(1e-9, gas_lhv), dtype=float)
    else:
        gas_price_mwh = _arr(gas_price_raw, n, label="district_gas_price_eur_per_mwh_fuel")
        if np.any(~np.isfinite(gas_price_mwh)) or np.any(gas_price_mwh <= 0.0):
            raise ValueError(
                "[dispatch.milp_day_ahead] district_gas_day_ahead_price_eur_per_mwh_fuel must be finite and strictly positive."
            )
    co2_price_eur_per_t = None
    if co2_cost_enabled:
        if co2_price_raw is None:
            raise ValueError(
                "[dispatch.milp_day_ahead] CO2 cost model is enabled but 'co2_price_eur_per_tco2' is missing."
            )
        co2_price_eur_per_t = _arr(co2_price_raw, n, label="co2_price_eur_per_tco2")
        if np.any(~np.isfinite(co2_price_eur_per_t)) or np.any(co2_price_eur_per_t <= 0.0):
            raise ValueError(
                "[dispatch.milp_day_ahead] co2_price_eur_per_tco2 must be finite and strictly positive."
            )
    big_m_import = demand + (hp_th_cap / hp_cop) + bess_p + ely_p + 1.0
    gas_export_cap = gas_el_av if gas_chp_piecewise else (gas_th_av * gas_ratio)
    big_m_export = pv_av + sw_av + lw_av + hydro_av + geo_el_av + (bio_th_av * bio_ratio) + (bigas_th_av * bigas_ratio) + gas_export_cap + fc_p + bess_p + 1.0
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
    thermflex_member_ids: list[str] | None = None
    thermflex_member_building_keys: list[str] | None = None
    thermflex_member_archetype_keys: list[str] | None = None
    thermflex_member_floor_area_m2: np.ndarray | None = None
    thermflex_member_stock_scale: np.ndarray | None = None

    if thermflex_enabled:
        if thermflex_member_count <= 0:
            raise ValueError("[dispatch.milp_day_ahead] thermflex_enabled requires thermflex_member_count > 0.")
        # The coupled-dispatch utilization export needs explicit member metadata.
        # Those labels are passed in through params, not inferred here, so later
        # cohort aggregation stays anchored in the same SSOT that built the
        # thermflex inputs upstream.
        thermflex_member_ids = _string_list(
            p.get("thermflex_member_ids"),
            thermflex_member_count,
            "thermflex_member_ids",
        )
        thermflex_member_building_keys = _string_list(
            p.get("thermflex_member_building_keys"),
            thermflex_member_count,
            "thermflex_member_building_keys",
        )
        thermflex_member_archetype_keys = _string_list(
            p.get("thermflex_member_archetype_keys"),
            thermflex_member_count,
            "thermflex_member_archetype_keys",
        )
        thermflex_member_floor_area_m2 = np.asarray(
            p.get("thermflex_member_floor_area_m2"),
            dtype=float,
        ).reshape(-1)
        thermflex_member_stock_scale = np.asarray(
            p.get("thermflex_member_stock_scale"),
            dtype=float,
        ).reshape(-1)
        if thermflex_member_floor_area_m2.size != thermflex_member_count:
            raise ValueError(
                "[dispatch.milp_day_ahead] thermflex_member_floor_area_m2 length must equal "
                f"thermflex_member_count={thermflex_member_count}."
            )
        if thermflex_member_stock_scale.size != thermflex_member_count:
            raise ValueError(
                "[dispatch.milp_day_ahead] thermflex_member_stock_scale length must equal "
                f"thermflex_member_count={thermflex_member_count}."
            )
        if np.any(~np.isfinite(thermflex_member_floor_area_m2)) or np.any(thermflex_member_floor_area_m2 <= 0.0):
            raise ValueError(
                "[dispatch.milp_day_ahead] thermflex_member_floor_area_m2 must be finite and strictly positive."
            )
        if np.any(~np.isfinite(thermflex_member_stock_scale)) or np.any(thermflex_member_stock_scale <= 0.0):
            raise ValueError(
                "[dispatch.milp_day_ahead] thermflex_member_stock_scale must be finite and strictly positive."
            )
        therm_t_ref = _matrix(s.get("thermflex_t_ref_c"), thermflex_member_count, n)
        therm_t_out = _matrix(s.get("thermflex_t_outdoor_c"), thermflex_member_count, n)
        therm_q_int = _matrix(s.get("thermflex_internal_gains_w_m2"), thermflex_member_count, n)
        therm_q_sol = _matrix(s.get("thermflex_solar_gains_w_m2"), thermflex_member_count, n)
        therm_q_ref = _matrix(s.get("thermflex_q_heat_ref_kwh"), thermflex_member_count, n)
        therm_residual = _matrix(s.get("thermflex_residual_c"), thermflex_member_count, n)
        therm_t_lower_bound = (
            _matrix(s.get("thermflex_t_lower_bound_c"), thermflex_member_count, n)
            if thermflex_use_explicit_lower_bounds
            else None
        )
        therm_alpha = np.asarray(p.get("thermflex_alpha"), dtype=float).reshape(-1)
        therm_beta_out = np.asarray(p.get("thermflex_beta_out"), dtype=float).reshape(-1)
        therm_gamma_internal = np.asarray(p.get("thermflex_gamma_internal"), dtype=float).reshape(-1)
        therm_gamma_solar = np.asarray(p.get("thermflex_gamma_solar"), dtype=float).reshape(-1)
        therm_gamma_heat = np.asarray(p.get("thermflex_gamma_heat"), dtype=float).reshape(-1)
        therm_q_heat_max = np.maximum(
            0.0,
            np.asarray(p.get("thermflex_q_heat_max_kwh"), dtype=float).reshape(-1),
        )
        therm_t_in_initial = np.asarray(st.get("thermflex_t_in_initial_c"), dtype=float).reshape(-1)
        therm_preheat_event_energy_limit = None
        therm_preheat_peak_excess = None
        therm_cutback_event_energy_limit = None
        therm_cutback_peak_shed = None
        therm_recovery_time_h = None
        therm_recovery_rebound_energy = None
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
                    f"[dispatch.milp_day_ahead] {name} length must equal thermflex_member_count={thermflex_member_count}."
                )
        if thermflex_use_event_response_bounds:
            for name, arr in {
                "thermflex_preheat_event_energy_limit_kwh": therm_preheat_event_energy_limit,
                "thermflex_preheat_peak_excess_kwh_per_step": therm_preheat_peak_excess,
                "thermflex_cutback_event_energy_limit_kwh": therm_cutback_event_energy_limit,
                "thermflex_cutback_peak_shed_kwh_per_step": therm_cutback_peak_shed,
                "thermflex_recovery_time_to_reference_h": therm_recovery_time_h,
                "thermflex_recovery_rebound_energy_kwh": therm_recovery_rebound_energy,
            }.items():
                if arr is None or arr.size != thermflex_member_count:
                    raise ValueError(
                        f"[dispatch.milp_day_ahead] {name} length must equal thermflex_member_count={thermflex_member_count}."
                    )
                if np.any(~np.isfinite(arr)):
                    raise ValueError(
                        f"[dispatch.milp_day_ahead] {name} must be finite for all thermflex members."
                    )
            if np.any(therm_preheat_event_energy_limit < 0.0):
                raise ValueError("[dispatch.milp_day_ahead] thermflex_preheat_event_energy_limit_kwh must be >= 0.")
            if np.any(therm_preheat_peak_excess < 0.0):
                raise ValueError("[dispatch.milp_day_ahead] thermflex_preheat_peak_excess_kwh_per_step must be >= 0.")
            if np.any(therm_cutback_event_energy_limit < 0.0):
                raise ValueError("[dispatch.milp_day_ahead] thermflex_cutback_event_energy_limit_kwh must be >= 0.")
            if np.any(therm_cutback_peak_shed < 0.0):
                raise ValueError("[dispatch.milp_day_ahead] thermflex_cutback_peak_shed_kwh_per_step must be >= 0.")
            if np.any(therm_recovery_time_h <= 0.0):
                raise ValueError("[dispatch.milp_day_ahead] thermflex_recovery_time_to_reference_h must be > 0.")
            if np.any(therm_recovery_rebound_energy < 0.0):
                raise ValueError("[dispatch.milp_day_ahead] thermflex_recovery_rebound_energy_kwh must be >= 0.")
        dh_space_heat_ref = np.sum(therm_q_ref, axis=0)

    print(
        f"[dispatch.milp_day_ahead] build start | hours={n} | thermflex_members={thermflex_member_count if thermflex_enabled else 0}",
        flush=True,
    )

    m = ConcreteModel()
    m.T = RangeSet(0, n - 1)
    if thermflex_enabled:
        m.M = RangeSet(0, thermflex_member_count - 1)

    def nn():
        return Var(m.T, within=NonNegativeReals)

    m.grid_import = nn()
    m.grid_export = nn()
    m.grid_import_on = Var(m.T, within=Binary)
    m.grid_export_on = Var(m.T, within=Binary)
    m.pv_used = nn()
    m.pv_spill = nn()
    m.small_wind_used = nn()
    m.small_wind_spill = nn()
    m.large_wind_used = nn()
    m.large_wind_spill = nn()
    m.run_of_river_hydro_used = nn()
    m.run_of_river_hydro_spill = nn()
    m.geo_el_used = nn()
    m.geo_el_spill = nn()
    m.geo_th_used = nn()
    m.geo_th_spill = nn()
    m.solar_load = nn()
    m.solar_charge = nn()
    m.solar_spill = nn()
    m.external_heat_th = nn()
    m.external_heat_spill = nn()
    m.external_heat_on = Var(m.T, within=Binary)
    m.waste_th = nn()
    m.waste_spill = nn()
    m.waste_on = Var(m.T, within=Binary)
    m.bess_charge = nn()
    m.bess_discharge = nn()
    m.bess_soc = nn()
    m.bess_charge_on = Var(m.T, within=Binary)
    m.bess_discharge_on = Var(m.T, within=Binary)
    m.h2_charge = nn()
    m.h2_discharge = nn()
    m.h2_soc = nn()
    m.h2_charge_on = Var(m.T, within=Binary)
    m.h2_discharge_on = Var(m.T, within=Binary)
    m.dh_hp_th = nn()
    m.dh_storage_charge = nn()
    m.dh_storage_discharge = nn()
    m.dh_storage_soc = nn()
    m.dh_storage_charge_on = Var(m.T, within=Binary)
    m.dh_storage_discharge_on = Var(m.T, within=Binary)
    m.bio_th = nn()
    m.bio_spill = nn()
    m.bio_on = Var(m.T, within=Binary)
    m.bigas_th = nn()
    m.bigas_spill = nn()
    m.bigas_on = Var(m.T, within=Binary)
    if gas_chp_piecewise:
        m.GAS_CHP_POINTS = RangeSet(0, len(gas_chp_points["names"]) - 1)
        m.gas_mode_share = Var(m.GAS_CHP_POINTS, m.T, within=NonNegativeReals)
    m.gas_th = nn()
    m.gas_el = nn()
    m.gas_fuel_input = nn()
    m.gas_spill = nn()
    m.gas_on = Var(m.T, within=Binary)
    m.gas_boiler_th = nn()
    m.gas_boiler_spill = nn()
    m.gas_boiler_on = Var(m.T, within=Binary)
    m.wood_th = nn()
    m.wood_spill = nn()
    m.wood_on = Var(m.T, within=Binary)
    m.unserved_el = nn()
    m.unserved_dh = nn()
    if thermflex_enabled:
        m.therm_t_in = Var(m.M, RangeSet(0, n), within=NonNegativeReals)
        m.therm_q_heat = Var(m.M, m.T, within=NonNegativeReals)
        m.therm_flex_active = Var(m.M, m.T, within=Binary)
        m.therm_event_start = Var(m.M, m.T, within=Binary)
        m.therm_temp_violation_low = Var(m.M, m.T, within=NonNegativeReals)
        m.therm_temp_violation_high = Var(m.M, m.T, within=NonNegativeReals)
        if thermflex_use_event_response_bounds and thermflex_event_energy_bounds:
            m.therm_event_preheat_extra = Var(m.M, m.T, within=NonNegativeReals)
            m.therm_event_cutback_shed = Var(m.M, m.T, within=NonNegativeReals)

    m.c = ConstraintList()
    if thermflex_enabled:
        for m_idx in range(thermflex_member_count):
            m.c.add(m.therm_t_in[m_idx, 0] == float(therm_t_in_initial[m_idx]))
            for t in range(n):
                m.c.add(m.therm_q_heat[m_idx, t] <= float(therm_q_heat_max[m_idx]))
                q_ref_t = float(therm_q_ref[m_idx, t])
                q_heat_max_t = float(therm_q_heat_max[m_idx])
                m.c.add(
                    m.therm_t_in[m_idx, t + 1]
                    == float(therm_alpha[m_idx]) * m.therm_t_in[m_idx, t]
                    + float(therm_beta_out[m_idx]) * float(therm_t_out[m_idx, t])
                    + float(therm_gamma_internal[m_idx]) * float(therm_q_int[m_idx, t])
                    + float(therm_gamma_solar[m_idx]) * float(therm_q_sol[m_idx, t])
                    + float(therm_gamma_heat[m_idx]) * m.therm_q_heat[m_idx, t]
                    + float(therm_residual[m_idx, t])
                )
                if thermflex_use_explicit_lower_bounds:
                    setpoint_c = float(therm_t_ref[m_idx, t])
                    lower_bound_c = float(therm_t_lower_bound[m_idx, t])
                    if lower_bound_c > setpoint_c + 1e-9:
                        raise ValueError(
                            "[dispatch.milp_day_ahead] thermflex_t_lower_bound_c must not exceed thermflex_t_ref_c."
                        )
                    m.c.add(
                        m.therm_t_in[m_idx, t]
                        >= setpoint_c
                        - (setpoint_c - lower_bound_c) * m.therm_flex_active[m_idx, t]
                        - m.therm_temp_violation_low[m_idx, t]
                    )
                else:
                    allowed_band = float(thermflex_ref_deadband_k) + float(thermflex_band_k) * m.therm_flex_active[m_idx, t]
                    m.c.add(
                        m.therm_t_in[m_idx, t]
                        >= float(therm_t_ref[m_idx, t]) - allowed_band - m.therm_temp_violation_low[m_idx, t]
                    )
                if thermflex_constrain_upper_temperature:
                    if thermflex_use_explicit_lower_bounds:
                        m.c.add(
                            m.therm_t_in[m_idx, t]
                            <= float(therm_t_ref[m_idx, t]) + m.therm_temp_violation_high[m_idx, t]
                        )
                    else:
                        m.c.add(
                            m.therm_t_in[m_idx, t]
                            <= float(therm_t_ref[m_idx, t]) + allowed_band + m.therm_temp_violation_high[m_idx, t]
                        )
                if t == 0:
                    m.c.add(m.therm_event_start[m_idx, t] >= m.therm_flex_active[m_idx, t])
                else:
                    m.c.add(
                        m.therm_event_start[m_idx, t]
                        >= m.therm_flex_active[m_idx, t] - m.therm_flex_active[m_idx, t - 1]
                    )
                # Flex activation is the explicit switch for any deviation from
                # the reference heat trajectory. Without this gate, the optimizer
                # can shift heat while keeping `therm_flex_active = 0`, which
                # bypasses duration/event limits and makes the exported
                # activation diagnostics meaningless.
                m.c.add(
                    m.therm_q_heat[m_idx, t] - q_ref_t
                    <= q_heat_max_t * m.therm_flex_active[m_idx, t]
                )
                m.c.add(
                    q_ref_t - m.therm_q_heat[m_idx, t]
                    <= q_ref_t * m.therm_flex_active[m_idx, t]
                )
                if thermflex_use_event_response_bounds and thermflex_event_peak_bounds:
                    m.c.add(
                        m.therm_q_heat[m_idx, t] - q_ref_t
                        <= float(therm_preheat_peak_excess[m_idx]) * m.therm_flex_active[m_idx, t]
                    )
                    m.c.add(
                        q_ref_t - m.therm_q_heat[m_idx, t]
                        <= float(therm_cutback_peak_shed[m_idx]) * m.therm_flex_active[m_idx, t]
                    )
                if thermflex_use_event_response_bounds and thermflex_event_energy_bounds:
                    m.c.add(
                        m.therm_event_preheat_extra[m_idx, t]
                        >= m.therm_q_heat[m_idx, t] - q_ref_t
                    )
                    m.c.add(
                        m.therm_event_preheat_extra[m_idx, t]
                        <= q_heat_max_t * m.therm_flex_active[m_idx, t]
                    )
                    m.c.add(
                        m.therm_event_cutback_shed[m_idx, t]
                        >= q_ref_t - m.therm_q_heat[m_idx, t]
                    )
                    m.c.add(
                        m.therm_event_cutback_shed[m_idx, t]
                        <= q_ref_t * m.therm_flex_active[m_idx, t]
                    )
            for day_start in range(0, n, 24):
                day_end = min(day_start + 24, n)
                m.c.add(
                    sum(m.therm_flex_active[m_idx, t] for t in range(day_start, day_end))
                    <= thermflex_max_duration_h
                )
                m.c.add(
                    sum(m.therm_event_start[m_idx, t] for t in range(day_start, day_end))
                    <= thermflex_max_events_per_day
                )
            if thermflex_use_event_response_bounds and thermflex_event_energy_bounds:
                m.c.add(
                    sum(m.therm_event_preheat_extra[m_idx, t] for t in range(n))
                    <= float(therm_preheat_event_energy_limit[m_idx])
                    * sum(m.therm_event_start[m_idx, t] for t in range(n))
                )
                m.c.add(
                    sum(m.therm_event_cutback_shed[m_idx, t] for t in range(n))
                    <= float(therm_cutback_event_energy_limit[m_idx])
                    * sum(m.therm_event_start[m_idx, t] for t in range(n))
                )
            if thermflex_use_event_response_bounds and thermflex_event_recovery_cooldown:
                cooldown_steps = thermflex_max_duration_h + int(np.ceil(float(therm_recovery_time_h[m_idx])))
                if cooldown_steps > 1:
                    for t in range(n):
                        window_end = min(n, t + cooldown_steps)
                        m.c.add(
                            sum(m.therm_event_start[m_idx, tau] for tau in range(t, window_end)) <= 1
                        )
            if thermflex_allow_terminal_deviation:
                if thermflex_use_explicit_lower_bounds:
                    m.c.add(m.therm_t_in[m_idx, n] >= float(therm_t_lower_bound[m_idx, n - 1]))
                else:
                    terminal_band = float(thermflex_ref_deadband_k) + float(thermflex_terminal_band_k)
                    m.c.add(m.therm_t_in[m_idx, n] >= float(therm_t_ref[m_idx, n - 1]) - terminal_band)
                if thermflex_constrain_upper_temperature:
                    if thermflex_use_explicit_lower_bounds:
                        m.c.add(m.therm_t_in[m_idx, n] <= float(therm_t_ref[m_idx, n - 1]))
                    else:
                        m.c.add(m.therm_t_in[m_idx, n] <= float(therm_t_ref[m_idx, n - 1]) + terminal_band)
            else:
                m.c.add(m.therm_t_in[m_idx, n] >= float(therm_t_ref[m_idx, n - 1]))
                if thermflex_constrain_upper_temperature:
                    m.c.add(m.therm_t_in[m_idx, n] <= float(therm_t_ref[m_idx, n - 1]))

    for t in range(n):
        prev_bess = st.get("bess_soc_initial", 0.0) if t == 0 else m.bess_soc[t - 1]
        prev_h2 = st.get("h2_soc_initial", 0.0) if t == 0 else m.h2_soc[t - 1]
        prev_dh = st.get("district_thermal_storage_soc_initial", 0.0) if t == 0 else m.dh_storage_soc[t - 1]

        m.c.add(m.pv_used[t] + m.pv_spill[t] == pv_av[t])
        m.c.add(m.small_wind_used[t] + m.small_wind_spill[t] == sw_av[t])
        m.c.add(m.large_wind_used[t] + m.large_wind_spill[t] == lw_av[t])
        m.c.add(m.run_of_river_hydro_used[t] + m.run_of_river_hydro_spill[t] == hydro_av[t])
        m.c.add(m.geo_el_used[t] + m.geo_el_spill[t] == geo_el_av[t])
        m.c.add(m.geo_th_used[t] + m.geo_th_spill[t] == geo_th_av[t])
        m.c.add(m.solar_load[t] + m.solar_charge[t] + m.solar_spill[t] == solar_total_useful_av[t])
        m.c.add(m.external_heat_th[t] + m.external_heat_spill[t] <= external_heat_th_av[t] * m.external_heat_on[t])
        m.c.add(m.external_heat_th[t] + m.external_heat_spill[t] >= external_heat_th_av[t] * external_heat_min * m.external_heat_on[t])
        m.c.add(m.waste_th[t] + m.waste_spill[t] <= waste_th_av[t] * m.waste_on[t])

        m.c.add(m.grid_import[t] <= big_m_import[t] * m.grid_import_on[t])
        m.c.add(m.grid_export[t] <= big_m_export[t] * m.grid_export_on[t])
        m.c.add(m.grid_import_on[t] + m.grid_export_on[t] <= 1)

        m.c.add(m.bess_charge[t] <= bess_p * m.bess_charge_on[t])
        m.c.add(m.bess_discharge[t] <= bess_p * m.bess_discharge_on[t])
        m.c.add(m.bess_charge_on[t] + m.bess_discharge_on[t] <= 1)
        m.c.add(m.bess_soc[t] == prev_bess + (bess_eta_ch * m.bess_charge[t]) - (m.bess_discharge[t] / bess_eta_dis))
        m.c.add(m.bess_soc[t] <= bess_cap)

        m.c.add(m.h2_charge[t] <= ely_p * m.h2_charge_on[t])
        m.c.add(m.h2_discharge[t] <= fc_p * m.h2_discharge_on[t])
        m.c.add(m.h2_charge_on[t] + m.h2_discharge_on[t] <= 1)
        m.c.add(m.h2_soc[t] == prev_h2 + (eta_ely * m.h2_charge[t]) - (m.h2_discharge[t] / eta_fc))
        m.c.add(m.h2_soc[t] <= h2_cap)

        m.c.add(m.dh_hp_th[t] <= hp_th_cap)
        m.c.add(m.dh_storage_charge[t] <= dh_store_cap * m.dh_storage_charge_on[t])
        m.c.add(m.dh_storage_discharge[t] <= dh_store_cap * m.dh_storage_discharge_on[t])
        m.c.add(m.dh_storage_charge_on[t] + m.dh_storage_discharge_on[t] <= 1)
        m.c.add(m.dh_storage_soc[t] == prev_dh - dh_loss + (dh_eta_ch * m.dh_storage_charge[t]) - (m.dh_storage_discharge[t] / dh_eta_dis))
        m.c.add(m.dh_storage_soc[t] <= dh_store_cap)
        m.c.add(m.solar_charge[t] <= m.dh_storage_charge[t])

        m.c.add(m.bio_th[t] + m.bio_spill[t] <= bio_th_av[t] * m.bio_on[t])
        m.c.add(m.bigas_th[t] + m.bigas_spill[t] <= bigas_th_av[t] * m.bigas_on[t])
        m.c.add(m.gas_boiler_th[t] + m.gas_boiler_spill[t] <= gas_boiler_th_av[t] * gas_boiler_max * m.gas_boiler_on[t])
        m.c.add(m.wood_th[t] + m.wood_spill[t] <= wood_th_av[t] * wood_max * m.wood_on[t])
        m.c.add(m.bio_th[t] + m.bio_spill[t] >= bio_th_av[t] * bio_min * m.bio_on[t])
        m.c.add(m.bigas_th[t] + m.bigas_spill[t] >= bigas_th_av[t] * bigas_min * m.bigas_on[t])
        m.c.add(m.gas_boiler_th[t] + m.gas_boiler_spill[t] >= gas_boiler_th_av[t] * gas_boiler_min * m.gas_boiler_on[t])
        m.c.add(m.wood_th[t] + m.wood_spill[t] >= wood_th_av[t] * wood_min * m.wood_on[t])
        if gas_chp_piecewise:
            # Piecewise V1 gas-CHP: the explicit mode shares live on the
            # installed electric-capacity base. This keeps the model anchored
            # in the new settings SSOT instead of reconstructing a hidden
            # electric/thermal ratio from the old fixed CHP point.
            if gas_el_av[t] <= 0.0:
                m.c.add(m.gas_on[t] == 0.0)
            m.c.add(sum(m.gas_mode_share[k, t] for k in m.GAS_CHP_POINTS) <= m.gas_on[t])
            m.c.add(sum(m.gas_mode_share[k, t] for k in m.GAS_CHP_POINTS) >= gas_min * m.gas_on[t])
            if gas_power_priority_mode == "price_spike_gated_v1":
                if "power_led" not in gas_chp_points["names"]:
                    raise ValueError(
                        "[dispatch.milp_day_ahead] price_spike_gated_v1 requires a CHP operating point named 'power_led'."
                    )
                power_led_idx = gas_chp_points["names"].index("power_led")
                m.c.add(m.gas_mode_share[power_led_idx, t] <= float(gas_power_priority_signal[t]))
            m.c.add(
                m.gas_th[t]
                == gas_el_av[t]
                * sum(float(gas_chp_points["q_norm"][k]) * m.gas_mode_share[k, t] for k in m.GAS_CHP_POINTS)
            )
            m.c.add(
                m.gas_el[t]
                == gas_el_av[t]
                * sum(float(gas_chp_points["p_norm"][k]) * m.gas_mode_share[k, t] for k in m.GAS_CHP_POINTS)
            )
            m.c.add(
                m.gas_fuel_input[t]
                == gas_el_av[t]
                * sum(float(gas_chp_points["fuel_norm"][k]) * m.gas_mode_share[k, t] for k in m.GAS_CHP_POINTS)
            )
            # Thermal spill is not used as a hidden capacity dump in the new
            # CHP region. Unused CHP capability is represented simply by not
            # activating a larger mode share.
            m.c.add(m.gas_spill[t] == 0.0)
        else:
            m.c.add(m.gas_th[t] + m.gas_spill[t] <= gas_th_av[t] * m.gas_on[t])
            m.c.add(m.gas_th[t] + m.gas_spill[t] >= gas_th_av[t] * gas_min * m.gas_on[t])
            m.c.add(m.gas_el[t] == m.gas_th[t] * gas_ratio)
            m.c.add(m.gas_fuel_input[t] == m.gas_th[t] / max(1e-9, gas_eta_th))

        hp_el = m.dh_hp_th[t] / hp_cop[t]
        bio_el = m.bio_th[t] * bio_ratio
        bigas_el = m.bigas_th[t] * bigas_ratio

        m.c.add(
            m.pv_used[t]
            + m.small_wind_used[t]
            + m.large_wind_used[t]
            + m.run_of_river_hydro_used[t]
            + m.geo_el_used[t]
            + bio_el
            + bigas_el
            + m.gas_el[t]
            + m.bess_discharge[t]
            + m.h2_discharge[t]
            + m.grid_import[t]
            + m.unserved_el[t]
            == demand[t] + hp_el + m.bess_charge[t] + m.h2_charge[t] + m.grid_export[t]
        )
        dh_effective_demand = (
            sum(m.therm_q_heat[m_idx, t] for m_idx in range(thermflex_member_count)) + float(dh_hotwater_demand[t])
            if thermflex_enabled
            else float(dh_demand[t])
        )
        m.c.add(
            m.geo_th_used[t]
            + m.solar_load[t]
            + m.solar_charge[t]
            + m.external_heat_th[t]
            + m.waste_th[t]
            + m.bio_th[t]
            + m.bigas_th[t]
            + m.gas_th[t]
            + m.gas_boiler_th[t]
            + m.wood_th[t]
            + m.dh_hp_th[t]
            + m.dh_storage_discharge[t]
            + m.unserved_dh[t]
            == dh_effective_demand
            + m.dh_storage_charge[t]
            + m.geo_th_spill[t]
            + m.solar_spill[t]
            + m.external_heat_spill[t]
            + m.waste_spill[t]
            + m.bio_spill[t]
            + m.bigas_spill[t]
            + m.gas_spill[t]
            + m.gas_boiler_spill[t]
            + m.wood_spill[t]
        )

    fuel_cost_expr = sum(
        (m.bio_th[t] / max(1e-9, bio_eta_th)) / bio_lhv * bio_fuel_cost
        + (m.bigas_th[t] / max(1e-9, bigas_eta_th)) / bigas_lhv * bigas_fuel_cost
        + (m.gas_fuel_input[t]) / 1000.0 * gas_price_mwh[t]
        + (m.gas_boiler_th[t] / gas_boiler_eta_th) / 1000.0 * gas_price_mwh[t]
        + (m.wood_th[t] / wood_eta_th) / wood_lhv * wood_fuel_cost
        for t in range(n)
    )
    co2_cost_expr = 0.0
    if co2_cost_enabled:
        co2_cost_expr = sum(
            (m.gas_fuel_input[t]) / 1000.0 * gas_chp_co2_t_per_mwh * co2_price_eur_per_t[t]
            + (m.gas_boiler_th[t] / gas_boiler_eta_th) / 1000.0 * gas_boiler_co2_t_per_mwh * co2_price_eur_per_t[t]
            for t in range(n)
        )
    variable_opex_expr = sum(
        external_heat_var_cost * m.external_heat_th[t] + gas_boiler_var_cost * m.gas_boiler_th[t]
        for t in range(n)
    )
    grid_import_cost_expr = sum(grid_buy[t] * m.grid_import[t] for t in range(n))
    grid_export_revenue_expr = sum(grid_sell[t] * m.grid_export[t] for t in range(n))
    unserved_penalty_expr = unserved_penalty * sum(m.unserved_el[t] + m.unserved_dh[t] for t in range(n))
    spill_penalty_expr = spill_penalty * sum(
        m.pv_spill[t] + m.small_wind_spill[t] + m.large_wind_spill[t] + m.run_of_river_hydro_spill[t] + m.geo_el_spill[t] + m.geo_th_spill[t] + m.solar_spill[t] + m.external_heat_spill[t] + m.waste_spill[t] + m.bio_spill[t] + m.bigas_spill[t] + m.gas_spill[t] + m.gas_boiler_spill[t] + m.wood_spill[t]
        for t in range(n)
    )
    thermflex_activation_expr = 0.0
    thermflex_violation_expr = 0.0
    if thermflex_enabled:
        thermflex_activation_expr = thermflex_activation_penalty * sum(
            m.therm_flex_active[m_idx, t]
            for m_idx in range(thermflex_member_count)
            for t in range(n)
        )
        thermflex_violation_expr = thermflex_temp_violation_penalty * sum(
            m.therm_temp_violation_low[m_idx, t]
            + (m.therm_temp_violation_high[m_idx, t] if thermflex_constrain_upper_temperature else 0.0)
            for m_idx in range(thermflex_member_count)
            for t in range(n)
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
    print("[dispatch.milp_day_ahead] solve start | solver=pyomo.highs", flush=True)
    result = solver.solve(m, tee=False)
    termination = str(result.solver.termination_condition).lower()
    if "optimal" not in termination and "feasible" not in termination:
        raise RuntimeError(f"[dispatch.milp_day_ahead] Solver failed with termination condition '{result.solver.termination_condition}'.")
    print(
        f"[dispatch.milp_day_ahead] solve done | termination={result.solver.termination_condition}",
        flush=True,
    )

    def vals(var: Var) -> np.ndarray:
        return np.array([float(value(var[t])) for t in range(n)], dtype=float)

    pv_used = vals(m.pv_used)
    sw_used = vals(m.small_wind_used)
    lw_used = vals(m.large_wind_used)
    hydro_used = vals(m.run_of_river_hydro_used)
    geo_el_used = vals(m.geo_el_used)
    geo_th_used = vals(m.geo_th_used)
    solar_load = vals(m.solar_load)
    solar_charge = vals(m.solar_charge)
    external_heat_th = vals(m.external_heat_th)
    waste_th = vals(m.waste_th)
    bio_th = vals(m.bio_th)
    bigas_th = vals(m.bigas_th)
    gas_th = vals(m.gas_th)
    gas_el = vals(m.gas_el)
    gas_chp_fuel_input_kwh = vals(m.gas_fuel_input)
    gas_boiler_th = vals(m.gas_boiler_th)
    wood_th = vals(m.wood_th)
    gas_boiler_fuel_input_kwh = gas_boiler_th / gas_boiler_eta_th
    gas_chp_co2_t = (
        (gas_chp_fuel_input_kwh / 1000.0) * gas_chp_co2_t_per_mwh
        if co2_cost_enabled
        else np.zeros(n, dtype=float)
    )
    gas_boiler_co2_t = (
        (gas_boiler_fuel_input_kwh / 1000.0) * gas_boiler_co2_t_per_mwh
        if co2_cost_enabled
        else np.zeros(n, dtype=float)
    )
    dh_hp_th = vals(m.dh_hp_th)
    dh_hp_el = dh_hp_th / hp_cop
    bio_el = bio_th * bio_ratio
    bigas_el = bigas_th * bigas_ratio
    bess_charge = vals(m.bess_charge)
    bess_discharge = vals(m.bess_discharge)
    bess_soc = vals(m.bess_soc)
    h2_charge = vals(m.h2_charge)
    h2_discharge = vals(m.h2_discharge)
    h2_soc = vals(m.h2_soc)
    dh_charge = vals(m.dh_storage_charge)
    dh_discharge = vals(m.dh_storage_discharge)
    dh_soc = vals(m.dh_storage_soc)
    dh_losses = np.full(n, dh_loss, dtype=float)
    grid_import = vals(m.grid_import)
    grid_export = vals(m.grid_export)
    unserved_el = vals(m.unserved_el)
    unserved_dh = vals(m.unserved_dh)
    if thermflex_enabled:
        therm_q_heat = np.array(
            [[float(value(m.therm_q_heat[m_idx, t])) for t in range(n)] for m_idx in range(thermflex_member_count)],
            dtype=float,
        )
        therm_t_in = np.array(
            [[float(value(m.therm_t_in[m_idx, t])) for t in range(n + 1)] for m_idx in range(thermflex_member_count)],
            dtype=float,
        )
        therm_flex_active = np.array(
            [[float(value(m.therm_flex_active[m_idx, t])) for t in range(n)] for m_idx in range(thermflex_member_count)],
            dtype=float,
        )
        therm_temp_violation = np.array(
            [
                [
                    float(value(m.therm_temp_violation_low[m_idx, t]) + value(m.therm_temp_violation_high[m_idx, t]))
                    if thermflex_constrain_upper_temperature
                    else float(value(m.therm_temp_violation_low[m_idx, t]))
                    for t in range(n)
                ]
                for m_idx in range(thermflex_member_count)
            ],
            dtype=float,
        )
        therm_event_preheat_extra = None
        therm_event_cutback_shed = None
        if thermflex_use_event_response_bounds and thermflex_event_energy_bounds:
            therm_event_preheat_extra = np.array(
                [[float(value(m.therm_event_preheat_extra[m_idx, t])) for t in range(n)] for m_idx in range(thermflex_member_count)],
                dtype=float,
            )
            therm_event_cutback_shed = np.array(
                [[float(value(m.therm_event_cutback_shed[m_idx, t])) for t in range(n)] for m_idx in range(thermflex_member_count)],
                dtype=float,
            )
        dh_space_heat = np.sum(therm_q_heat, axis=0)
        dh_demand_effective = dh_space_heat + dh_hotwater_demand
    else:
        dh_space_heat = dh_space_heat_ref
        dh_demand_effective = dh_demand
    dh_total_demand_ref = dh_space_heat_ref + dh_hotwater_demand

    electric_residual = (
        pv_used + sw_used + lw_used + hydro_used + geo_el_used + bio_el + bigas_el + gas_el + bess_discharge + h2_discharge + grid_import + unserved_el
        - (demand + dh_hp_el + bess_charge + h2_charge + grid_export)
    )
    dh_residual = (
        geo_th_used + bio_th + bigas_th + gas_th + wood_th + dh_hp_th + dh_discharge + unserved_dh
        + solar_load + solar_charge + external_heat_th + waste_th + gas_boiler_th
        - (dh_demand_effective + dh_charge + vals(m.geo_th_spill) + vals(m.solar_spill) + vals(m.external_heat_spill) + vals(m.waste_spill) + vals(m.bio_spill) + vals(m.bigas_spill) + vals(m.gas_spill) + vals(m.gas_boiler_spill) + vals(m.wood_spill))
    )

    solar_generation = solar_load + solar_charge
    solar_direct = np.minimum(solar_load, solar_direct_av)
    solar_preheat = np.maximum(0.0, solar_load - solar_direct)

    hourly = {
        "grid_import": grid_import,
        "grid_export": grid_export,
        "bess_charged": bess_charge,
        "bess_discharged": bess_discharge,
        "bess_soc": bess_soc,
        "h2_charge_elec": h2_charge,
        "h2_discharge_elec": h2_discharge,
        "h2_soc": h2_soc,
        "pv_used": pv_used,
        "pv_spillage": vals(m.pv_spill),
        "small_wind_used": sw_used,
        "small_wind_spillage": vals(m.small_wind_spill),
        "large_wind_used": lw_used,
        "large_wind_spillage": vals(m.large_wind_spill),
        "run_of_river_hydro_used": hydro_used,
        "run_of_river_hydro_spillage": vals(m.run_of_river_hydro_spill),
        "district_heat_pump_generation": dh_hp_th,
        "district_heat_pump_electricity": dh_hp_el,
        "district_heat_pump_cop": hp_cop,
        "district_thermal_storage_charge": dh_charge,
        "district_thermal_storage_discharge": dh_discharge,
        "district_thermal_storage_soc": dh_soc,
        "district_thermal_storage_losses": dh_losses,
        "district_geothermal_electric_generation": geo_el_used,
        "district_geothermal_electric_spillage": vals(m.geo_el_spill),
        "district_geothermal_thermal_generation": geo_th_used,
        "district_geothermal_thermal_spillage": vals(m.geo_th_spill),
        "district_solar_thermal_generation": solar_generation,
        "district_solar_thermal_direct_feed": solar_direct,
        "district_solar_thermal_preheat": solar_preheat,
        "district_solar_thermal_storage_charge": solar_charge,
        "district_solar_thermal_thermal_spillage": vals(m.solar_spill),
        "district_external_heat_generation": external_heat_th,
        "district_external_heat_thermal_spillage": vals(m.external_heat_spill),
        "district_waste_incineration_generation": waste_th,
        "district_waste_incineration_thermal_spillage": vals(m.waste_spill),
        "district_biomass_chp_electric_generation": bio_el,
        "district_biomass_chp_thermal_generation": bio_th,
        "district_biomass_chp_thermal_spillage": vals(m.bio_spill),
        "district_biomass_chp_fuel_input_kwh": bio_th / max(1e-9, bio_eta_th),
        "district_biomass_chp_fuel_input_kg": (bio_th / max(1e-9, bio_eta_th)) / bio_lhv,
        "district_biogas_chp_electric_generation": bigas_el,
        "district_biogas_chp_thermal_generation": bigas_th,
        "district_biogas_chp_thermal_spillage": vals(m.bigas_spill),
        "district_biogas_chp_fuel_input_kwh": bigas_th / max(1e-9, bigas_eta_th),
        "district_biogas_chp_fuel_input_nm3": (bigas_th / max(1e-9, bigas_eta_th)) / bigas_lhv,
        "district_gas_chp_electric_generation": gas_el,
        "district_gas_chp_thermal_generation": gas_th,
        "district_gas_chp_thermal_spillage": vals(m.gas_spill),
        "district_gas_chp_fuel_input_kwh": gas_chp_fuel_input_kwh,
        "district_gas_chp_fuel_input_m3": gas_chp_fuel_input_kwh / gas_lhv,
        "district_gas_chp_co2_t": gas_chp_co2_t,
        "district_gas_boiler_generation": gas_boiler_th,
        "district_gas_boiler_thermal_spillage": vals(m.gas_boiler_spill),
        "district_gas_boiler_fuel_input_kwh": gas_boiler_fuel_input_kwh,
        "district_gas_boiler_fuel_input_m3": gas_boiler_fuel_input_kwh / gas_boiler_lhv,
        "district_gas_boiler_co2_t": gas_boiler_co2_t,
        "district_wood_chip_boiler_generation": wood_th,
        "district_wood_chip_boiler_thermal_spillage": vals(m.wood_spill),
        "district_wood_chip_boiler_fuel_input_kwh": wood_th / wood_eta_th,
        "district_wood_chip_boiler_fuel_input_kg": (wood_th / wood_eta_th) / wood_lhv,
        "district_space_heat_demand": dh_space_heat,
        "district_space_heat_demand_ref": dh_space_heat_ref,
        "district_hotwater_demand": dh_hotwater_demand,
        "dh_total_demand": dh_demand_effective,
        "dh_total_demand_ref": dh_total_demand_ref,
        "dh_total_delivered": np.maximum(0.0, dh_demand_effective - unserved_dh),
        "dh_unserved_heat": unserved_dh,
        "unserved_el": unserved_el,
    }
    if gas_chp_piecewise:
        # Exporting the realized mode shares keeps the new CHP flexibility
        # transparent for later paper analysis and debugging. This avoids
        # having the MILP choose an opaque internal CHP mode mix.
        gas_mode_share = np.array(
            [[float(value(m.gas_mode_share[k, t])) for t in range(n)] for k in m.GAS_CHP_POINTS],
            dtype=float,
        )
        hourly["district_gas_chp_mode_share"] = gas_mode_share
        hourly["district_gas_chp_mode_names"] = list(gas_chp_points["names"])
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
        "mode": "milp_day_ahead",
        "solver": "pyomo.highs",
        "termination_condition": str(result.solver.termination_condition),
        "used_solar_thermal_kwh_day": float(np.sum(hourly["district_solar_thermal_generation"])),
        "used_external_heat_kwh_day": float(np.sum(hourly["district_external_heat_generation"])),
        "used_waste_incineration_kwh_day": float(np.sum(hourly["district_waste_incineration_generation"])),
        "used_biomass_feedstock_kwh_day": float(np.sum(hourly["district_biomass_chp_fuel_input_kwh"] + hourly["district_wood_chip_boiler_fuel_input_kwh"])),
        "used_biogas_feedstock_kwh_day": float(np.sum(hourly["district_biogas_chp_fuel_input_kwh"])),
        "bess_simultaneous_steps": int(np.sum((bess_charge > 1e-9) & (bess_discharge > 1e-9))),
        "h2_simultaneous_steps": int(np.sum((h2_charge > 1e-9) & (h2_discharge > 1e-9))),
        "dh_storage_simultaneous_steps": int(np.sum((dh_charge > 1e-9) & (dh_discharge > 1e-9))),
        "grid_simultaneous_steps": int(np.sum((grid_import > 1e-9) & (grid_export > 1e-9))),
        "max_electric_balance_residual": float(np.max(np.abs(electric_residual))) if n else 0.0,
        "max_dh_balance_residual": float(np.max(np.abs(dh_residual))) if n else 0.0,
        "district_biomass_chp_on_steps": int(np.sum(vals(m.bio_on) > 0.5)),
        "district_biogas_chp_on_steps": int(np.sum(vals(m.bigas_on) > 0.5)),
        "district_external_heat_on_steps": int(np.sum(vals(m.external_heat_on) > 0.5)),
        "district_gas_chp_on_steps": int(np.sum(vals(m.gas_on) > 0.5)),
        "district_gas_boiler_on_steps": int(np.sum(vals(m.gas_boiler_on) > 0.5)),
        "district_wood_chip_boiler_on_steps": int(np.sum(vals(m.wood_on) > 0.5)),
        "district_gas_chp_co2_t_total": float(np.sum(gas_chp_co2_t)),
        "district_gas_boiler_co2_t_total": float(np.sum(gas_boiler_co2_t)),
        "district_gas_boiler_peak_kw": compute_series_peak_kw(gas_boiler_th),
        "district_gas_chp_operating_mode_model": gas_chp_points["mode"],
        "district_gas_chp_power_priority_mode": gas_power_priority_mode,
    }
    if gas_chp_piecewise:
        diagnostics["district_gas_chp_operating_point_names"] = list(gas_chp_points["names"])
    if thermflex_enabled:
        hourly["thermflex_active_total"] = np.sum(therm_flex_active, axis=0)
        hourly["thermflex_temperature_violation_degree_h"] = np.sum(therm_temp_violation, axis=0)
        thermflex_metrics = compute_thermflex_series_metrics(dh_space_heat, dh_space_heat_ref)
        hourly["thermflex_space_heat_delta_kwh"] = np.asarray(
            thermflex_metrics["thermflex_space_heat_delta_kwh"], dtype=float
        )
        hourly["thermflex_virtual_storage_inventory_kwh"] = np.asarray(
            thermflex_metrics["thermflex_virtual_storage_inventory_kwh"], dtype=float
        )
        # These member-level arrays are exported explicitly for downstream
        # cohort-utilization studies. They do not replace the existing system
        # KPIs; they only expose the already-solved thermflex detail so later
        # analyses can aggregate by cohort without rerunning hidden logic.
        hourly["thermflex_member_ids"] = list(thermflex_member_ids or [])
        hourly["thermflex_member_building_keys"] = list(thermflex_member_building_keys or [])
        hourly["thermflex_member_archetype_keys"] = list(thermflex_member_archetype_keys or [])
        hourly["thermflex_member_floor_area_m2"] = np.asarray(thermflex_member_floor_area_m2, dtype=float)
        hourly["thermflex_member_stock_scale"] = np.asarray(thermflex_member_stock_scale, dtype=float)
        hourly["thermflex_member_q_heat_kwh"] = np.asarray(therm_q_heat, dtype=float)
        hourly["thermflex_member_q_heat_ref_kwh"] = np.asarray(therm_q_ref, dtype=float)
        hourly["thermflex_member_flex_active"] = np.asarray(therm_flex_active, dtype=float)
        hourly["thermflex_member_event_start"] = np.array(
            [[float(value(m.therm_event_start[m_idx, t])) for t in range(n)] for m_idx in range(thermflex_member_count)],
            dtype=float,
        )
        hourly["thermflex_member_temp_violation_degree_h"] = np.asarray(therm_temp_violation, dtype=float)
        hourly["thermflex_member_t_in_c"] = np.asarray(therm_t_in[:, :-1], dtype=float)
        diagnostics["thermflex_member_count"] = thermflex_member_count
        diagnostics["thermflex_active_member_hours_total"] = int(np.sum(therm_flex_active))
        diagnostics["thermflex_temperature_violation_degree_hours_total"] = float(np.sum(therm_temp_violation))
        diagnostics["thermflex_shifted_space_heat_kwh"] = float(thermflex_metrics["thermflex_shifted_space_heat_kwh"])
        diagnostics["thermflex_additional_space_heat_kwh"] = float(
            thermflex_metrics["thermflex_additional_space_heat_kwh"]
        )
        diagnostics["thermflex_rebound_kwh"] = float(thermflex_metrics["thermflex_rebound_kwh"])
        diagnostics["thermflex_peak_change_kw"] = float(thermflex_metrics["thermflex_peak_change_kw"])
        diagnostics["dh_total_peak_change_kw"] = compute_series_peak_change_kw(
            dh_demand_effective,
            dh_total_demand_ref,
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
        diagnostics["thermflex_t_in_terminal_c"] = therm_t_in[:, -1].tolist()
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
                np.sum(therm_event_preheat_extra) if therm_event_preheat_extra is not None else 0.0
            )
            diagnostics["thermflex_event_cutback_shed_realized_kwh"] = float(
                np.sum(therm_event_cutback_shed) if therm_event_cutback_shed is not None else 0.0
            )
            hourly["thermflex_member_event_preheat_extra_kwh"] = (
                np.asarray(therm_event_preheat_extra, dtype=float)
                if therm_event_preheat_extra is not None
                else np.zeros_like(therm_q_heat, dtype=float)
            )
            hourly["thermflex_member_event_cutback_shed_kwh"] = (
                np.asarray(therm_event_cutback_shed, dtype=float)
                if therm_event_cutback_shed is not None
                else np.zeros_like(therm_q_heat, dtype=float)
            )
    else:
        diagnostics["dh_total_peak_change_kw"] = 0.0
    diagnostics["district_gas_boiler_peak_kw"] = compute_series_peak_kw(gas_boiler_th)
    return DispatchResult(hourly=hourly, objective_terms=objective_terms, diagnostics=diagnostics)
