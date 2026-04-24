# Optimization/framework/engines/Gold/gold_engine.py
from __future__ import annotations

from typing import Any, Dict, List, Tuple, Optional

import time
from pathlib import Path
import numpy as np

from Technical_model.energy_system.precompute.adapter import prepare_profiles_adapter
from Optimization.framework.engines.kpi import compute_kpis, is_supported_objective_name
from Optimization.framework.engines.Gated.io import append_csv, write_summary_line
from Optimization.framework.engines.profiles_meta import get_profile_id
from Optimization.framework.engines.Surrogat_model.features import resolve_surrogate_targets
from Optimization.framework.engines.signature_utils import build_signature_dict, signature_hash
from Optimization.run.analysis.csv_exports import (
    append_dispatch_kpi_exports,
    append_thermflex_hourly_export,
    build_dispatch_kpi_payload,
)
from Settings.surrogate.train import make_surrogate_train
from Settings.problem.bounds import vector_to_named_dict

def _sum(flows: Dict[str, Any], k: str) -> float:
    v = flows.get(k, 0.0)
    if isinstance(v, (list, tuple, np.ndarray)):
        return float(np.sum(v))
    try:
        return float(v)
    except Exception:
        return 0.0

def _as_1d(v: Any) -> np.ndarray:
    """
    Convert flow to 1D time series.
    If v is scalar -> length-1 array.
    If v is 2D (T, N) -> sum across N to 1D.
    If higher dims -> flatten all non-time dims and sum.
    """
    a = np.asarray(v, float)
    if a.ndim == 0:
        return a.reshape(1)
    if a.ndim == 1:
        return a
    return a.reshape(a.shape[0], -1).sum(axis=1)


def _sum_pos(res: Dict[str, Any], key: str) -> float:
    if key not in res:
        return 0.0
    a = _as_1d(res[key])
    return float(np.sum(np.clip(a, 0.0, None)))


def _sum_neg_as_pos(res: Dict[str, Any], key: str) -> float:
    """Sum negative parts as positive value (e.g., export embedded as negative in net-flow)."""
    if key not in res:
        return 0.0
    a = _as_1d(res[key])
    return float(np.sum(np.clip(-a, 0.0, None)))





class GoldEngine:
    def __init__(self, settings, run_dir: Optional[str] = None):
        self.s = settings
        self.run_dir = run_dir
        self.run_id = Path(run_dir).name if run_dir else "unknown_run"

        prep = prepare_profiles_adapter(settings)
        self.profiles = prep.profiles
        self.params_base = prep.params_base
        self.year_load_kwh = prep.year_load_kwh
        self.lifetime_years = prep.lifetime_years

        self.obj_names: List[str] = list(getattr(settings.objectives, "names", []))
        self.con_names: List[str] = list(getattr(settings.constraints, "names", []))
        self.profile_id = get_profile_id(self.profiles, self.s)

        # SSOT targets for truth_dataset schema
        self._targets = list(resolve_surrogate_targets(settings))
        if not self._targets:
            raise ValueError("[gold] surrogate_train.targets is empty.")

        self.signature_dict = build_signature_dict(
            self.s,
            surrogate_meta_hint={
                "targets": self._targets,
                "profile_id": self.profile_id,
                "system_id": str(getattr(getattr(settings, "engine", None), "system_id", "unknown")),
            },
            system_context={
                "runtime_targets": self._targets,
                "profile_id": self.profile_id,
                "system_id": str(getattr(getattr(settings, "engine", None), "system_id", "unknown")),
            },
        )
        self.signature_hash = signature_hash(self.signature_dict)
        self._timings: List[float] = []

        # System function via registry
        from Technical_model.energy_system.systems.registry_systems import get as get_system  # type: ignore

        system_id = getattr(getattr(settings, "engine", None), "system_id", None)
        if not isinstance(system_id, str) or not system_id.strip():
            raise ValueError("[gold] settings.engine.system_id fehlt oder ist leer.")

        self._run_system = get_system(system_id)

    def _evaluate_one_core(self, x: np.ndarray) -> Tuple[np.ndarray, np.ndarray, Dict[str, float], Dict[str, Any]]:
        x = np.asarray(x, float).reshape(-1)
        x_named = vector_to_named_dict(x, self.s.bounds)
        pv_kwp = float(x_named.get("pv_kwp", 0.0))
        bess_kwh = float(x_named.get("bess_kwh", 0.0))
        ely_kw = float(x_named.get("ely_kw", 0.0))
        h2_tank_kwh = float(x_named.get("h2_tank_kwh", 0.0))
        fc_kw = float(x_named.get("fc_kw", 0.0))
        small_wind_kw = float(x_named.get("small_wind_kw", 0.0))
        large_wind_kw = float(x_named.get("large_wind_kw", 0.0))
        district_heat_pump_kw_th = float(x_named.get("district_heat_pump_kw_th", 0.0))
        district_thermal_storage_kwh_th = float(x_named.get("district_thermal_storage_kwh_th", 0.0))
        district_wood_chip_boiler_kw_th = float(x_named.get("district_wood_chip_boiler_kw_th", 0.0))
        district_biomass_chp_kw_th = float(x_named.get("district_biomass_chp_kw_th", 0.0))
        district_geothermal_kw_el = float(x_named.get("district_geothermal_kw_el", 0.0))
        district_gas_chp_kw_el = float(x_named.get("district_gas_chp_kw_el", 0.0))
        district_biogas_chp_kw_el = float(x_named.get("district_biogas_chp_kw_el", 0.0))
        biogas_engine_kw = float(x_named.get("biogas_engine_kw", 0.0))
        wood_gasifier_kw = float(x_named.get("wood_gasifier_kw", 0.0))

        params = dict(self.params_base)
        params["pv_size"] = pv_kwp
        params["battery_capacity_kWh"] = bess_kwh
        params["ely_kw"] = ely_kw
        params["h2_tank_kwh"] = h2_tank_kwh
        params["fc_kw"] = fc_kw
        params["small_wind_kw"] = small_wind_kw
        params["large_wind_kw"] = large_wind_kw
        params["district_heat_pump_kw_th"] = district_heat_pump_kw_th
        params["district_thermal_storage_kwh_th"] = district_thermal_storage_kwh_th
        params["district_wood_chip_boiler_kw_th"] = district_wood_chip_boiler_kw_th
        params["district_biomass_chp_kw_th"] = district_biomass_chp_kw_th
        params["district_geothermal_kw_el"] = district_geothermal_kw_el
        params["district_gas_chp_kw_el"] = district_gas_chp_kw_el
        params["district_biogas_chp_kw_el"] = district_biogas_chp_kw_el
        params["biogas_engine_kw"] = biogas_engine_kw
        params["wood_gasifier_kw"] = wood_gasifier_kw
        district_external_heat_kw_th = float(params.get("district_external_heat_kw_th", 0.0))
        district_gas_boiler_kw_th = float(params.get("district_gas_boiler_kw_th", 0.0))
        district_solar_thermal_kw_th = float(params.get("district_solar_thermal_kw_th", 0.0))
        district_waste_incineration_kw_th = float(params.get("district_waste_incineration_kw_th", 0.0))
        
        # Ensure N_EC and N_HH are set (from settings.engine)
        eng = getattr(self.s, "engine", None)
        if eng:
            params["N_HH"] = int(eng.N_HH)
            params["N_EC"] = int(eng.N_EC)
            params["rng_seed"] = int(eng.rng_seed)
            params["engine_config"] = eng
        params["settings_obj"] = self.s

        res, _hourly = self._run_system(params, self.profiles, pv_kwp, run_checks=False)

        # -----------------------------
        # Robust: Grid import/export aggregation.
        # -----------------------------
        if "grid_import" in res or "grid_export" in res:
            E_imp_grid_Y = _sum_pos(res, "grid_import")
            E_exp_grid_Y = max(_sum_pos(res, "grid_export"), _sum_neg_as_pos(res, "grid_import"))
        elif "grid_net" in res:
            E_imp_grid_Y = _sum_pos(res, "grid_net")
            E_exp_grid_Y = _sum_neg_as_pos(res, "grid_net")
        else:
            raise KeyError(
                "[gold] No grid flow key found. Expected one of: 'grid_import'/'grid_export' or 'grid_net'. "
                f"Available keys: {sorted(res.keys())}"
            )

        # -----------------------------
        # EC imports (allow missing -> 0)
        # -----------------------------
        E_imp_ec_pv_Y = _sum_pos(res, "ec_import_from_pv")
        E_imp_ec_ev_Y = _sum_pos(res, "ec_import_from_ev")
        E_exp_ec_pv_Y = _sum_pos(res, "ec_export_from_pv")

        # PV / BESS (allow missing -> 0)
        pv_gen_Y = _sum_pos(res, "pv_generation")
        bess_ch_Y = _sum_pos(res, "bess_charged") + _sum_pos(res, "bess_discharged")

        # -----------------------------
        # Total load (fail-fast if missing)
        # -----------------------------
        if "total_load" not in res:
            raise KeyError(
                "[gold] 'total_load' fehlt im Systemresult – Autarkie-Nenner wäre potenziell falsch. "
                f"Available keys: {sorted(res.keys())}"
            )
        total_load_Y = _sum_pos(res, "total_load")

        # EV flows (optional, allow missing -> 0)
        ev_charged_Y = _sum_pos(res, "ev_charge_ac")
        ev_discharged_Y = _sum_pos(res, "ev_discharged")
        h2_charge_Y = _sum_pos(res, "h2_charge_elec")
        h2_discharge_Y = _sum_pos(res, "h2_discharge_elec")
        hp_flex_Y = _sum_pos(res, "hp_flex_elec")
        small_wind_Y = _sum_pos(res, "small_wind_generation")
        large_wind_Y = _sum_pos(res, "large_wind_generation")
        biogas_Y = _sum_pos(res, "biogas_generation")
        wood_gasifier_Y = _sum_pos(res, "wood_gasifier_generation")
        wood_gasifier_fuel_input_Y = _sum_pos(res, "wood_gasifier_fuel_input_kwh")
        district_geothermal_el_Y = _sum_pos(res, "district_geothermal_electric_generation")
        district_geothermal_th_Y = _sum_pos(res, "district_geothermal_thermal_generation")
        district_solar_thermal_Y = _sum_pos(res, "district_solar_thermal_generation")
        district_waste_incineration_Y = _sum_pos(res, "district_waste_incineration_generation")
        district_heat_pump_th_Y = _sum_pos(res, "district_heat_pump_generation")
        district_heat_pump_el_Y = _sum_pos(res, "district_heat_pump_electricity")
        district_storage_charge_Y = _sum_pos(res, "district_thermal_storage_charge")
        district_storage_discharge_Y = _sum_pos(res, "district_thermal_storage_discharge")
        district_storage_losses_Y = _sum_pos(res, "district_thermal_storage_losses")
        district_external_heat_Y = _sum_pos(res, "district_external_heat_generation")
        district_biomass_chp_el_Y = _sum_pos(res, "district_biomass_chp_electric_generation")
        district_biomass_chp_th_Y = _sum_pos(res, "district_biomass_chp_thermal_generation")
        district_biomass_chp_fuel_input_Y = _sum_pos(res, "district_biomass_chp_fuel_input_kwh")
        district_biomass_chp_fuel_input_kg_Y = _sum_pos(res, "district_biomass_chp_fuel_input_kg")
        district_biogas_chp_el_Y = _sum_pos(res, "district_biogas_chp_electric_generation")
        district_biogas_chp_th_Y = _sum_pos(res, "district_biogas_chp_thermal_generation")
        district_biogas_chp_fuel_input_Y = _sum_pos(res, "district_biogas_chp_fuel_input_kwh")
        district_biogas_chp_fuel_input_nm3_Y = _sum_pos(res, "district_biogas_chp_fuel_input_nm3")
        district_gas_chp_el_Y = _sum_pos(res, "district_gas_chp_electric_generation")
        district_gas_chp_th_Y = _sum_pos(res, "district_gas_chp_thermal_generation")
        district_gas_chp_fuel_input_Y = _sum_pos(res, "district_gas_chp_fuel_input_kwh")
        district_gas_chp_fuel_input_m3_Y = _sum_pos(res, "district_gas_chp_fuel_input_m3")
        district_gas_boiler_Y = _sum_pos(res, "district_gas_boiler_generation")
        district_gas_boiler_fuel_input_Y = _sum_pos(res, "district_gas_boiler_fuel_input_kwh")
        district_gas_boiler_fuel_input_m3_Y = _sum_pos(res, "district_gas_boiler_fuel_input_m3")
        district_wood_chip_boiler_Y = _sum_pos(res, "district_wood_chip_boiler_generation")
        district_wood_chip_boiler_fuel_input_Y = _sum_pos(res, "district_wood_chip_boiler_fuel_input_kwh")
        district_wood_chip_boiler_fuel_input_kg_Y = _sum_pos(res, "district_wood_chip_boiler_fuel_input_kg")
        bess_cyclic_violation = float(res.get("bess_cyclic_violation_kwh", 0.0))
        h2_cyclic_violation = float(res.get("h2_cyclic_violation_kwh", 0.0))

        L = int(self.lifetime_years) # Lebensdauer in Jahren  changed from params.get("lifetime", self.lifetime_years)  

        flows_L = {
            "E_import_grid_kWh": float(E_imp_grid_Y * L),
            "E_export_grid_kWh": float(E_exp_grid_Y * L),
            "E_import_ec_pv_kWh": float(E_imp_ec_pv_Y * L),
            "E_import_ec_ev_kWh": float(E_imp_ec_ev_Y * L),
            "E_export_ec_pv_kWh": float(E_exp_ec_pv_Y * L),
            "PV_generation_kWh": float(pv_gen_Y * L),
            "BESS_throughput_kWh": float(bess_ch_Y * L),
            "E_ev_charged_kWh": float(ev_charged_Y * L),
            "E_ev_discharged_kWh": float(ev_discharged_Y * L),
            "E_h2_charge_elec_kWh": float(h2_charge_Y * L),
            "E_h2_discharge_elec_kWh": float(h2_discharge_Y * L),
            "E_hp_flex_elec_kWh": float(hp_flex_Y * L),
            "E_small_wind_generation_kWh": float(small_wind_Y * L),
            "E_large_wind_generation_kWh": float(large_wind_Y * L),
            "E_biogas_generation_kWh": float(biogas_Y * L),
            "E_wood_gasifier_generation_kWh": float(wood_gasifier_Y * L),
            "E_wood_gasifier_fuel_input_kWh": float(wood_gasifier_fuel_input_Y * L),
            "E_district_heat_pump_thermal_generation_kWh": float(district_heat_pump_th_Y * L),
            "E_district_heat_pump_electricity_kWh": float(district_heat_pump_el_Y * L),
            "E_district_thermal_storage_charge_kWh": float(district_storage_charge_Y * L),
            "E_district_thermal_storage_discharge_kWh": float(district_storage_discharge_Y * L),
            "E_district_thermal_storage_losses_kWh": float(district_storage_losses_Y * L),
            "E_district_external_heat_generation_kWh": float(district_external_heat_Y * L),
            "E_district_geothermal_electric_generation_kWh": float(district_geothermal_el_Y * L),
            "E_district_geothermal_thermal_generation_kWh": float(district_geothermal_th_Y * L),
            "E_district_solar_thermal_generation_kWh": float(district_solar_thermal_Y * L),
            "E_district_waste_incineration_generation_kWh": float(district_waste_incineration_Y * L),
            "E_district_biomass_chp_electric_generation_kWh": float(district_biomass_chp_el_Y * L),
            "E_district_biomass_chp_thermal_generation_kWh": float(district_biomass_chp_th_Y * L),
            "E_district_biomass_chp_fuel_input_kWh": float(district_biomass_chp_fuel_input_Y * L),
            "M_district_biomass_chp_fuel_input_kg": float(district_biomass_chp_fuel_input_kg_Y * L),
            "E_district_biogas_chp_electric_generation_kWh": float(district_biogas_chp_el_Y * L),
            "E_district_biogas_chp_thermal_generation_kWh": float(district_biogas_chp_th_Y * L),
            "E_district_biogas_chp_fuel_input_kWh": float(district_biogas_chp_fuel_input_Y * L),
            "V_district_biogas_chp_fuel_input_nm3": float(district_biogas_chp_fuel_input_nm3_Y * L),
            "E_district_gas_chp_electric_generation_kWh": float(district_gas_chp_el_Y * L),
            "E_district_gas_chp_thermal_generation_kWh": float(district_gas_chp_th_Y * L),
            "E_district_gas_chp_fuel_input_kWh": float(district_gas_chp_fuel_input_Y * L),
            "V_district_gas_chp_fuel_input_m3": float(district_gas_chp_fuel_input_m3_Y * L),
            "E_district_gas_boiler_generation_kWh": float(district_gas_boiler_Y * L),
            "E_district_gas_boiler_fuel_input_kWh": float(district_gas_boiler_fuel_input_Y * L),
            "V_district_gas_boiler_fuel_input_m3": float(district_gas_boiler_fuel_input_m3_Y * L),
            "E_district_wood_chip_boiler_generation_kWh": float(district_wood_chip_boiler_Y * L),
            "E_district_wood_chip_boiler_fuel_input_kWh": float(district_wood_chip_boiler_fuel_input_Y * L),
            "M_district_wood_chip_boiler_fuel_input_kg": float(district_wood_chip_boiler_fuel_input_kg_Y * L),
            "E_total_load_kWh": float(total_load_Y * L),
            "dh_unserved_heat": float(_sum_pos(res, "dh_unserved_heat") * L),
            "bess_cyclic_violation_kwh": float(bess_cyclic_violation),
            # Not an energy-through-lifetime sum: terminal-cycle constraint residual [kWh_H2].
            "h2_cyclic_violation_kwh": float(h2_cyclic_violation),
        }
        dispatch_diag = res.get("dispatch_diagnostics", {}) if isinstance(res, dict) else {}
        if isinstance(dispatch_diag, dict) and dispatch_diag:
            if "district_gas_boiler_co2_t_total" not in dispatch_diag or "district_gas_chp_co2_t_total" not in dispatch_diag:
                raise KeyError(
                    "[gold] dispatch_diagnostics fehlen CO2-Totalfelder fuer den Export/Truth-Pfad."
                )
            gas_boiler_co2_t = float(dispatch_diag["district_gas_boiler_co2_t_total"])
            gas_chp_co2_t = float(dispatch_diag["district_gas_chp_co2_t_total"])
            thermflex_enabled = bool(getattr(getattr(self.s.engine, "features", None), "enable_thermflex", False))
            flows_L.update(
                {
                    "district_gas_boiler_co2_t": gas_boiler_co2_t,
                    "district_gas_chp_co2_t": gas_chp_co2_t,
                    "co2_emissions_total_t": gas_boiler_co2_t + gas_chp_co2_t,
                    "district_gas_boiler_peak_kw": float(dispatch_diag["district_gas_boiler_peak_kw"]),
                }
            )
            if thermflex_enabled:
                required_thermflex_keys = (
                    "thermflex_shifted_space_heat_kwh",
                    "thermflex_active_member_hours_total",
                    "thermflex_temperature_violation_degree_hours_total",
                    "thermflex_t_in_min_c",
                    "thermflex_t_in_max_c",
                )
                missing_thermflex = [k for k in required_thermflex_keys if k not in dispatch_diag]
                if missing_thermflex:
                    raise KeyError(
                        "[gold] Thermflex aktiviert, aber dispatch_diagnostics fehlen Pflichtfelder: "
                        + ", ".join(missing_thermflex)
                    )
                flows_L.update(
                    {
                        "thermflex_shifted_space_heat_kwh": float(dispatch_diag["thermflex_shifted_space_heat_kwh"]),
                        "thermflex_additional_space_heat_kwh": float(
                            dispatch_diag["thermflex_additional_space_heat_kwh"]
                        ),
                        "thermflex_rebound_kwh": float(dispatch_diag["thermflex_rebound_kwh"]),
                        "thermflex_peak_change_kw": float(dispatch_diag["thermflex_peak_change_kw"]),
                        "dh_total_peak_change_kw": float(dispatch_diag["dh_total_peak_change_kw"]),
                        "thermflex_heat_up_ramp_kw_per_h": float(
                            dispatch_diag["thermflex_heat_up_ramp_kw_per_h"]
                        ),
                        "thermflex_heat_down_ramp_kw_per_h": float(
                            dispatch_diag["thermflex_heat_down_ramp_kw_per_h"]
                        ),
                        "thermflex_effective_thermal_storage_kwh": float(
                            dispatch_diag["thermflex_effective_thermal_storage_kwh"]
                        ),
                        "thermflex_max_preheat_headroom_kwh": float(
                            dispatch_diag["thermflex_max_preheat_headroom_kwh"]
                        ),
                        "thermflex_active_member_hours_total": float(
                            dispatch_diag["thermflex_active_member_hours_total"]
                        ),
                        "thermflex_temperature_violation_degree_hours_total": float(
                            dispatch_diag["thermflex_temperature_violation_degree_hours_total"]
                        ),
                        "thermflex_t_in_min_c": float(dispatch_diag["thermflex_t_in_min_c"]),
                        "thermflex_t_in_max_c": float(dispatch_diag["thermflex_t_in_max_c"]),
                    }
                )
            else:
                flows_L.update(
                    {
                        "thermflex_shifted_space_heat_kwh": 0.0,
                        "thermflex_additional_space_heat_kwh": 0.0,
                        "thermflex_rebound_kwh": 0.0,
                        "thermflex_peak_change_kw": 0.0,
                        "dh_total_peak_change_kw": 0.0,
                        "thermflex_heat_up_ramp_kw_per_h": 0.0,
                        "thermflex_heat_down_ramp_kw_per_h": 0.0,
                        "thermflex_effective_thermal_storage_kwh": 0.0,
                        "thermflex_max_preheat_headroom_kwh": 0.0,
                        "thermflex_active_member_hours_total": 0.0,
                        "thermflex_temperature_violation_degree_hours_total": 0.0,
                        "thermflex_t_in_min_c": 0.0,
                        "thermflex_t_in_max_c": 0.0,
                    }
                )

        # -----------------------------
        # Objectives + Constraints (single KPI entry-point)
        # -----------------------------
        design_vars = {
            "pv_kwp": float(pv_kwp),
            "bess_kwh": float(bess_kwh),
            "ely_kw": float(ely_kw),
            "h2_tank_kwh": float(h2_tank_kwh),
            "fc_kw": float(fc_kw),
            "small_wind_kw": float(small_wind_kw),
            "large_wind_kw": float(large_wind_kw),
            "district_external_heat_kw_th": float(district_external_heat_kw_th),
            "district_gas_boiler_kw_th": float(district_gas_boiler_kw_th),
            "district_heat_pump_kw_th": float(district_heat_pump_kw_th),
            "district_thermal_storage_kwh_th": float(district_thermal_storage_kwh_th),
            "district_wood_chip_boiler_kw_th": float(district_wood_chip_boiler_kw_th),
            "district_biomass_chp_kw_th": float(district_biomass_chp_kw_th),
            "district_geothermal_kw_el": float(district_geothermal_kw_el),
            "district_gas_chp_kw_el": float(district_gas_chp_kw_el),
            "district_biogas_chp_kw_el": float(district_biogas_chp_kw_el),
            "district_solar_thermal_kw_th": float(district_solar_thermal_kw_th),
            "district_waste_incineration_kw_th": float(district_waste_incineration_kw_th),
            "biogas_engine_kw": float(biogas_engine_kw),
            "wood_gasifier_kw": float(wood_gasifier_kw),
            "params": params,
            "raw_results": res,
            "lifetime_years": int(self.lifetime_years),
        }
        requested_objective_names = [
            t for t in self._targets if is_supported_objective_name(params, t)
        ]
        objectives, constraints, _ctx = compute_kpis(
            flows_L,
            design_vars,
            self.s,
            self.profiles,
            requested_objective_names=requested_objective_names,
        )
        # Keep truth_dataset targets consistent with surrogate targets when objectives
        # are included as explicit target columns (e.g. grid_import_kwh, autarky, npc_eur).
        for name, value in objectives.items():
            flows_L[str(name)] = float(value)

        F = np.array([float(objectives[n]) for n in self.obj_names], dtype=float).reshape(1, -1)
        if self.con_names:
            G = np.array(constraints, dtype=float).reshape(1, -1)
        else:
            G = np.zeros((1, 0), dtype=float)

        return F, G, flows_L, res

    def evaluate_one_with_flows(self, x: np.ndarray) -> Tuple[np.ndarray, np.ndarray, Dict[str, float]]:
        F, G, flows_L, _res = self._evaluate_one_core(x)
        return F, G, flows_L

    def evaluate_one_with_details(self, x: np.ndarray) -> Tuple[np.ndarray, np.ndarray, Dict[str, float], Dict[str, Any]]:
        return self._evaluate_one_core(x)


    def evaluate(self, X: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
        X = np.asarray(X, float)
        if X.ndim == 1:
            X = X.reshape(1, -1)

        F_rows: List[np.ndarray] = []
        G_rows: List[np.ndarray] = []
        n_points = int(X.shape[0])

        for i in range(X.shape[0]):
            print(f"[gold] evaluate point {i + 1}/{n_points}", flush=True)
            t0 = time.perf_counter()
            F, G, flows, _res = self._evaluate_one_core(X[i, :])
            print(
                f"[gold] point {i + 1}/{n_points} done | eval_s={time.perf_counter() - t0:.1f}",
                flush=True,
            )
            self._append_truth_csv(X[i, :], flows, source="gold")
            self._append_dispatch_exports(i, flows, _res)
            self._append_timing(i, time.perf_counter() - t0)
            F_rows.append(F)
            G_rows.append(G)

        F_out = np.vstack(F_rows) if F_rows else np.zeros((0, len(self.obj_names)), float)
        if self.con_names:
            G_out = np.vstack(G_rows) if G_rows else np.zeros((0, len(self.con_names)), float)
        else:
            G_out = np.zeros((F_out.shape[0], 0), float)
        self._flush_timing_summary()
        return F_out, G_out

    def _append_dispatch_exports(self, idx: int, flows: Dict[str, float], raw_results: Dict[str, Any]) -> None:
        if not self.run_dir:
            return
        reporting = getattr(self.s, "reporting", None)
        if reporting is None:
            raise ValueError("[gold] settings.reporting fehlt.")
        if getattr(reporting, "write_dispatch_kpis", None) is None:
            raise ValueError("[gold] settings.reporting.write_dispatch_kpis fehlt.")
        if not bool(reporting.write_dispatch_kpis):
            return
        activation = getattr(self.s, "technology_activation", None)
        features = getattr(getattr(self.s, "engine", None), "features", None)
        requires_dispatch_export = bool(
            getattr(features, "enable_thermflex", False)
            or any(
                bool(getattr(activation, attr, False))
                for attr in (
                    "district_heat_pump",
                    "district_thermal_storage",
                    "district_external_heat",
                    "district_gas_boiler",
                    "district_wood_chip_boiler",
                    "district_geothermal",
                    "district_gas_chp",
                    "district_biogas_chp",
                    "district_solar_thermal",
                    "district_biomass_chp",
                    "district_waste_incineration",
                )
            )
        )
        dispatch_diag = raw_results.get("dispatch_diagnostics")
        if not isinstance(dispatch_diag, dict) or not dispatch_diag:
            if requires_dispatch_export:
                raise KeyError(
                    "[gold] reporting.write_dispatch_kpis=True, aber raw_results['dispatch_diagnostics'] fehlt."
                )
            return
        payload = build_dispatch_kpi_payload(
            settings=self.s,
            flows_L=flows,
            raw_results=raw_results,
            point_idx=int(idx),
        )
        append_dispatch_kpi_exports(
            run_dir=self.run_dir,
            settings=self.s,
            payload=payload,
        )
        if getattr(reporting, "write_thermflex_hourly", None) is None:
            raise ValueError("[gold] settings.reporting.write_thermflex_hourly fehlt.")
        if bool(reporting.write_thermflex_hourly):
            append_thermflex_hourly_export(
                run_dir=self.run_dir,
                settings=self.s,
                raw_results=raw_results,
                point_idx=int(idx),
            )

    def _append_truth_csv(self, x: np.ndarray, flows: Dict[str, float], source: str) -> None:
        if not self.run_dir:
            return
        path = Path(self.run_dir) / "truth_dataset.csv"

        names = list(getattr(getattr(self.s, "bounds", None), "names", []))
        if not names:
            names = [f"x{i}" for i in range(len(x))]

        header = ["run_id", "signature_hash", "source", *names, *self._targets]
        row = {names[i]: float(x[i]) for i in range(len(x))}
        row["run_id"] = self.run_id
        row["signature_hash"] = self.signature_hash
        row["source"] = source
        for t in self._targets:
            if t not in flows:
                raise KeyError(f"[gold] truth target '{t}' fehlt in flows_L.")
            row[t] = float(flows[t])
        append_csv(path, header, row)

    def _append_timing(self, idx: int, elapsed_s: float) -> None:
        if not self.run_dir:
            return
        path = Path(self.run_dir) / "gold_timing.csv"
        header = ["run_id", "point_idx", "eval_s"]
        row = {"run_id": self.run_id, "point_idx": int(idx), "eval_s": float(elapsed_s)}
        append_csv(path, header, row)
        self._timings.append(float(elapsed_s))

    def _flush_timing_summary(self) -> None:
        if not self.run_dir or not self._timings:
            return
        arr = np.asarray(self._timings, float)
        total = float(np.sum(arr))
        mean = float(np.mean(arr))
        median = float(np.median(arr))
        n_eval = int(arr.size)
        write_summary_line(self.run_dir, f"[gold_timing] n_eval={n_eval}")
        write_summary_line(self.run_dir, f"[gold_timing] total_s={total:.6f}")
        write_summary_line(self.run_dir, f"[gold_timing] mean_s={mean:.6f}")
        write_summary_line(self.run_dir, f"[gold_timing] median_s={median:.6f}")

    def run(self, run_dir: str) -> Dict[str, Any]:
        # gold has no artifact – keep interface
        return {"ok": True, "run_dir": str(run_dir)}
