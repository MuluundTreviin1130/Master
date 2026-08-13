# Optimization/framework/engines/Surrogat_model/teacher/evaluate_teacher.py
from __future__ import annotations

from typing import Any, Dict, List, Tuple

import numpy as np
from tqdm.auto import tqdm

from Data.assembly.replacements import annual_bess_throughput_kwh
from Optimization.framework.engines.kpi import compute_kpis, is_supported_objective_name
from Optimization.framework.engines.Surrogat_model.features import resolve_surrogate_targets
from Settings.problem.bounds import vector_to_named_dict
from Technical_model.energy_system.precompute.adapter import prepare_profiles_adapter
from Technical_model.energy_system.systems.registry_systems import get as get_system


def _sum(result: Dict[str, Any], key: str) -> float:
    arr = result.get(key, None)
    if arr is None:
        return 0.0
    a = np.asarray(arr)
    return float(np.sum(a))


def _sum_nonneg(result: Dict[str, Any], key: str) -> float:
    """Sum the nonnegative part of a flow series.

    Gold clips BESS charge/discharge the same way before adding them into
    throughput. The teacher must use that clipped sum, not a raw ``np.sum``,
    so a sign convention change cannot silently cancel charge against discharge.
    """
    arr = result.get(key, None)
    if arr is None:
        return 0.0
    return float(np.sum(np.clip(np.asarray(arr, dtype=float), 0.0, None)))


_THERMFLEX_DIAG_TARGETS: Dict[str, str] = {
    "thermflex_shifted_space_heat_kwh": "thermflex_shifted_space_heat_kwh",
    "thermflex_additional_space_heat_kwh": "thermflex_additional_space_heat_kwh",
    "thermflex_rebound_kwh": "thermflex_rebound_kwh",
    "thermflex_peak_change_kw": "thermflex_peak_change_kw",
    "dh_total_peak_change_kw": "dh_total_peak_change_kw",
    "district_gas_boiler_peak_kw": "district_gas_boiler_peak_kw",
    "thermflex_heat_up_ramp_kw_per_h": "thermflex_heat_up_ramp_kw_per_h",
    "thermflex_heat_down_ramp_kw_per_h": "thermflex_heat_down_ramp_kw_per_h",
    "thermflex_effective_thermal_storage_kwh": "thermflex_effective_thermal_storage_kwh",
    "thermflex_max_preheat_headroom_kwh": "thermflex_max_preheat_headroom_kwh",
    "thermflex_active_member_hours_total": "thermflex_active_member_hours_total",
    "thermflex_temperature_violation_degree_hours_total": "thermflex_temperature_violation_degree_hours_total",
    "thermflex_t_in_min_c": "thermflex_t_in_min_c",
    "thermflex_t_in_max_c": "thermflex_t_in_max_c",
}

_NON_LIFETIME_SCALED_TARGETS = {
    "district_gas_boiler_co2_t",
    "district_gas_chp_co2_t",
    "co2_emissions_total_t",
    *_THERMFLEX_DIAG_TARGETS.keys(),
}


def _year_flows(
    params: Dict[str, Any],
    profiles: Dict[str, Any],
    run_system,
    x_named: Dict[str, float],
    target_names: List[str],
) -> Tuple[Dict[str, float], Dict[str, Any]]:
    """Simulate one year and return yearly flow sums plus raw hourly results."""
    p = dict(params)
    p["pv_size"] = float(x_named.get("pv_kwp", 0.0))
    p["battery_capacity_kWh"] = float(x_named.get("bess_kwh", 0.0))
    p["ely_kw"] = float(x_named.get("ely_kw", 0.0))
    p["h2_tank_kwh"] = float(x_named.get("h2_tank_kwh", 0.0))
    p["fc_kw"] = float(x_named.get("fc_kw", 0.0))
    p["small_wind_kw"] = float(x_named.get("small_wind_kw", 0.0))
    p["large_wind_kw"] = float(x_named.get("large_wind_kw", 0.0))
    p["district_heat_pump_kw_th"] = float(x_named.get("district_heat_pump_kw_th", 0.0))
    p["district_thermal_storage_kwh_th"] = float(x_named.get("district_thermal_storage_kwh_th", 0.0))
    p["district_wood_chip_boiler_kw_th"] = float(x_named.get("district_wood_chip_boiler_kw_th", 0.0))
    p["district_biomass_chp_kw_th"] = float(x_named.get("district_biomass_chp_kw_th", 0.0))
    p["district_geothermal_kw_el"] = float(x_named.get("district_geothermal_kw_el", 0.0))
    p["district_gas_chp_kw_el"] = float(x_named.get("district_gas_chp_kw_el", 0.0))
    p["district_biogas_chp_kw_el"] = float(x_named.get("district_biogas_chp_kw_el", 0.0))
    p["biogas_engine_kw"] = float(x_named.get("biogas_engine_kw", 0.0))
    p["wood_gasifier_kw"] = float(x_named.get("wood_gasifier_kw", 0.0))

    res, _hourly = run_system(p, profiles, float(x_named.get("pv_kwp", 0.0)), run_checks=False)
    settings = p.get("settings_obj")

    flows_year = {
        "E_import_grid_kWh": _sum(res, "grid_import"),
        "E_export_grid_kWh": _sum(res, "grid_export"),
        "E_import_ec_pv_kWh": _sum(res, "ec_import_from_pv"),
        "E_import_ec_ev_kWh": _sum(res, "ec_import_from_ev"),
        "E_export_ec_pv_kWh": _sum(res, "ec_export_from_pv"),
        "BESS_throughput_kWh": annual_bess_throughput_kwh(
            charged_kwh=_sum_nonneg(res, "bess_charged"),
            discharged_kwh=_sum_nonneg(res, "bess_discharged"),
        ),
        "E_ev_charged_kWh": _sum(res, "ev_charge_ac"),
        "E_ev_discharged_kWh": _sum(res, "ev_discharged"),
        "E_h2_charge_elec_kWh": _sum(res, "h2_charge_elec"),
        "E_h2_discharge_elec_kWh": _sum(res, "h2_discharge_elec"),
        "E_hp_flex_elec_kWh": _sum(res, "hp_flex_elec"),
        "E_small_wind_generation_kWh": _sum(res, "small_wind_generation"),
        "E_large_wind_generation_kWh": _sum(res, "large_wind_generation"),
        "E_biogas_generation_kWh": _sum(res, "biogas_generation"),
        "E_wood_gasifier_generation_kWh": _sum(res, "wood_gasifier_generation"),
        "E_wood_gasifier_fuel_input_kWh": _sum(res, "wood_gasifier_fuel_input_kwh"),
        "E_district_heat_pump_thermal_generation_kWh": _sum(res, "district_heat_pump_generation"),
        "E_district_heat_pump_electricity_kWh": _sum(res, "district_heat_pump_electricity"),
        "E_district_thermal_storage_charge_kWh": _sum(res, "district_thermal_storage_charge"),
        "E_district_thermal_storage_discharge_kWh": _sum(res, "district_thermal_storage_discharge"),
        "E_district_thermal_storage_losses_kWh": _sum(res, "district_thermal_storage_losses"),
        "E_district_external_heat_generation_kWh": _sum(res, "district_external_heat_generation"),
        "E_district_geothermal_electric_generation_kWh": _sum(res, "district_geothermal_electric_generation"),
        "E_district_geothermal_thermal_generation_kWh": _sum(res, "district_geothermal_thermal_generation"),
        "E_district_solar_thermal_generation_kWh": _sum(res, "district_solar_thermal_generation"),
        "E_district_waste_incineration_generation_kWh": _sum(res, "district_waste_incineration_generation"),
        "E_district_biomass_chp_electric_generation_kWh": _sum(res, "district_biomass_chp_electric_generation"),
        "E_district_biomass_chp_thermal_generation_kWh": _sum(res, "district_biomass_chp_thermal_generation"),
        "E_district_biomass_chp_fuel_input_kWh": _sum(res, "district_biomass_chp_fuel_input_kwh"),
        "M_district_biomass_chp_fuel_input_kg": _sum(res, "district_biomass_chp_fuel_input_kg"),
        "E_district_biogas_chp_electric_generation_kWh": _sum(res, "district_biogas_chp_electric_generation"),
        "E_district_biogas_chp_thermal_generation_kWh": _sum(res, "district_biogas_chp_thermal_generation"),
        "E_district_biogas_chp_fuel_input_kWh": _sum(res, "district_biogas_chp_fuel_input_kwh"),
        "V_district_biogas_chp_fuel_input_nm3": _sum(res, "district_biogas_chp_fuel_input_nm3"),
        "E_district_gas_chp_electric_generation_kWh": _sum(res, "district_gas_chp_electric_generation"),
        "E_district_gas_chp_thermal_generation_kWh": _sum(res, "district_gas_chp_thermal_generation"),
        "E_district_gas_chp_fuel_input_kWh": _sum(res, "district_gas_chp_fuel_input_kwh"),
        "V_district_gas_chp_fuel_input_m3": _sum(res, "district_gas_chp_fuel_input_m3"),
        "E_district_gas_boiler_generation_kWh": _sum(res, "district_gas_boiler_generation"),
        "E_district_gas_boiler_fuel_input_kWh": _sum(res, "district_gas_boiler_fuel_input_kwh"),
        "V_district_gas_boiler_fuel_input_m3": _sum(res, "district_gas_boiler_fuel_input_m3"),
        "E_district_wood_chip_boiler_generation_kWh": _sum(res, "district_wood_chip_boiler_generation"),
        "E_district_wood_chip_boiler_fuel_input_kWh": _sum(res, "district_wood_chip_boiler_fuel_input_kwh"),
        "M_district_wood_chip_boiler_fuel_input_kg": _sum(res, "district_wood_chip_boiler_fuel_input_kg"),
        "PV_generation_kWh": _sum(res, "pv_generation"),
        "E_total_load_kWh": _sum(res, "total_load"),
        "dh_unserved_heat": _sum(res, "dh_unserved_heat"),
        "bess_cyclic_violation_kwh": float(res.get("bess_cyclic_violation_kwh", 0.0)),
        "h2_cyclic_violation_kwh": float(res.get("h2_cyclic_violation_kwh", 0.0)),
    }
    dispatch_diag = res.get("dispatch_diagnostics", {}) if isinstance(res, dict) else {}
    if isinstance(dispatch_diag, dict) and dispatch_diag:
        required_co2_keys = ("district_gas_boiler_co2_t_total", "district_gas_chp_co2_t_total")
        missing_co2_keys = [k for k in required_co2_keys if k not in dispatch_diag]
        if missing_co2_keys:
            raise KeyError(
                "[teacher] dispatch_diagnostics missing CO2 total fields: "
                + ", ".join(missing_co2_keys)
            )
        gas_boiler_co2_t = float(dispatch_diag["district_gas_boiler_co2_t_total"])
        gas_chp_co2_t = float(dispatch_diag["district_gas_chp_co2_t_total"])
        flows_year.update(
            {
                "district_gas_boiler_co2_t": gas_boiler_co2_t,
                "district_gas_chp_co2_t": gas_chp_co2_t,
                "co2_emissions_total_t": gas_boiler_co2_t + gas_chp_co2_t,
            }
        )
        thermflex_enabled = bool(
            getattr(getattr(getattr(settings, "engine", None), "features", None), "enable_thermflex", False)
        )
        requested_thermflex_targets = [name for name in target_names if name in _THERMFLEX_DIAG_TARGETS]
        if thermflex_enabled:
            # We only require the thermflex diagnostics that are actually part of the
            # active surrogate target slice. This keeps the teacher strict without
            # inventing dependencies on unused export fields.
            required_thermflex_keys = [
                _THERMFLEX_DIAG_TARGETS[name] for name in requested_thermflex_targets
            ]
            missing_thermflex = [k for k in required_thermflex_keys if k not in dispatch_diag]
            if missing_thermflex:
                raise KeyError(
                    "[teacher] Thermflex active, but dispatch_diagnostics miss required scalar fields: "
                    + ", ".join(missing_thermflex)
                )
            flows_year.update(
                {
                    name: float(dispatch_diag[_THERMFLEX_DIAG_TARGETS[name]])
                    for name in requested_thermflex_targets
                }
            )
        else:
            flows_year.update(
                {
                    name: 0.0
                    for name in requested_thermflex_targets
                }
            )
    return flows_year, res


def evaluate_teacher_dataset(
    settings,
    X: np.ndarray,
    targets: List[str] | None = None,
    batch_size: int | None = None,
    row_offset: int = 0,
) -> Tuple[np.ndarray, np.ndarray, Dict[str, Any]]:
    """Return lifetime target matrix for the requested teacher targets."""
    eng = settings.engine
    loc = eng.location
    system_id = eng.system_id

    prep = prepare_profiles_adapter(settings)
    base_params = dict(prep.params_base)
    profiles = prep.profiles
    base_params["location"] = loc

    if "EC" not in base_params:
        base_params["EC"] = {}
    base_params["EC"]["share"] = float(eng.ec_share_import)
    base_params["EC"]["export_share"] = float(eng.ec_share_export)

    base_params["N_HH"] = int(eng.N_HH)
    base_params["N_EC"] = int(eng.N_EC)
    base_params["N_EV"] = int(eng.N_EV_total)
    base_params["N_EV_bidirectional"] = int(eng.N_EV_bidirectional)

    ev_cfg = base_params.setdefault("EV", {})
    ev_cfg["N_EV_total"] = int(eng.N_EV_total)
    ev_cfg["N_EV_bidirectional"] = int(eng.N_EV_bidirectional)
    base_params["engine_config"] = eng
    base_params["settings_obj"] = settings

    run_system = get_system(system_id)
    lifetime_years = int(base_params["lifetime"])
    tnames = list(targets or resolve_surrogate_targets(settings))

    X = np.asarray(X, float)
    if X.ndim == 1:
        X = X.reshape(1, -1)

    requested_objectives = {
        t
        for t in tnames
        if is_supported_objective_name(base_params, t)
    }
    YF_rows: List[List[float]] = []
    feasible_indices: List[int] = []
    failed_points: List[Dict[str, Any]] = []

    for i, x_row in enumerate(tqdm(X, desc="[teacher] sim", unit="pt")):
        global_row_index = int(row_offset + i)
        x_named = vector_to_named_dict(x_row, settings.bounds)
        eval_stage = "teacher_system"
        try:
            year, raw_results = _year_flows(
                base_params,
                profiles,
                run_system,
                x_named=x_named,
                target_names=tnames,
            )

            # GoldEngine treats dispatch diagnostics as slice-level truth, not
            # lifetime-accumulated quantities. The surrogate teacher must mirror
            # that exactly, otherwise temperatures, peaks, rebound, active hours,
            # and CO2 are inflated by `lifetime_years` and become physically wrong.
            life = {
                k: float(v) if k in _NON_LIFETIME_SCALED_TARGETS else float(v) * lifetime_years
                for k, v in year.items()
            }
            if requested_objectives:
                eval_stage = "teacher_kpi"
                design_vars = {
                    "pv_kwp": float(x_named.get("pv_kwp", 0.0)),
                    "bess_kwh": float(x_named.get("bess_kwh", 0.0)),
                    "ely_kw": float(x_named.get("ely_kw", 0.0)),
                    "h2_tank_kwh": float(x_named.get("h2_tank_kwh", 0.0)),
                    "fc_kw": float(x_named.get("fc_kw", 0.0)),
                    "small_wind_kw": float(x_named.get("small_wind_kw", 0.0)),
                    "large_wind_kw": float(x_named.get("large_wind_kw", 0.0)),
                    "district_heat_pump_kw_th": float(x_named.get("district_heat_pump_kw_th", 0.0)),
                    "district_thermal_storage_kwh_th": float(x_named.get("district_thermal_storage_kwh_th", 0.0)),
                    "district_wood_chip_boiler_kw_th": float(x_named.get("district_wood_chip_boiler_kw_th", 0.0)),
                    "district_biomass_chp_kw_th": float(x_named.get("district_biomass_chp_kw_th", 0.0)),
                    "district_geothermal_kw_el": float(x_named.get("district_geothermal_kw_el", 0.0)),
                    "district_gas_chp_kw_el": float(x_named.get("district_gas_chp_kw_el", 0.0)),
                    "district_biogas_chp_kw_el": float(x_named.get("district_biogas_chp_kw_el", 0.0)),
                    "district_solar_thermal_kw_th": float(base_params.get("district_solar_thermal_kw_th", 0.0)),
                    "district_waste_incineration_kw_th": float(base_params.get("district_waste_incineration_kw_th", 0.0)),
                    "biogas_engine_kw": float(x_named.get("biogas_engine_kw", 0.0)),
                    "wood_gasifier_kw": float(x_named.get("wood_gasifier_kw", 0.0)),
                    "params": base_params,
                    "raw_results": raw_results,
                    "lifetime_years": lifetime_years,
                }
                objectives, _constraints, _ctx = compute_kpis(
                    life,
                    design_vars,
                    settings,
                    profiles,
                    requested_objective_names=sorted(requested_objectives),
                )
                for obj_name in requested_objectives:
                    life[obj_name] = float(objectives[obj_name])

            eval_stage = "teacher_targets"
            missing_targets = [t for t in tnames if t not in life]
            if missing_targets:
                raise KeyError(
                    "[teacher] missing required surrogate targets after evaluation: "
                    + ", ".join(sorted(missing_targets))
                )

            YF_rows.append([float(life[t]) for t in tnames])
            feasible_indices.append(global_row_index)
        except Exception as exc:
            failure_row: Dict[str, Any] = {
                "row_index": global_row_index,
                "stage": eval_stage,
                "error_type": exc.__class__.__name__,
                "error_message": str(exc),
            }
            for bound_name in list(settings.bounds.names):
                failure_row[bound_name] = float(x_named[bound_name])
            failed_points.append(failure_row)

    n_feasible = len(YF_rows)
    YF = np.asarray(YF_rows, dtype=float).reshape((n_feasible, len(tnames))) if n_feasible else np.zeros((0, len(tnames)), dtype=float)
    YG = np.zeros((n_feasible, 0), dtype=float)
    audit = {
        "n_requested": int(X.shape[0]),
        "n_feasible": int(n_feasible),
        "n_infeasible": int(len(failed_points)),
        "feasible_indices": feasible_indices,
        "failed_points": failed_points,
    }
    return YF, YG, audit
