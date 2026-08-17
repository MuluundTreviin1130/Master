from __future__ import annotations

from typing import Any, Dict, List, Tuple

from Data.assembly.replacements import compute_bess_replacement, compute_fc_replacement, compute_pv_replacement
from Cost_model.dispatch_cost_model import build_dispatch_cost_breakdown
from Optimization.framework.Constraints.dispatch import evaluate_constraints
from market import build_market_bundle

SUPPORTED_BASE_OBJECTIVE_NAMES = {
    "npc_eur",
    "autarky",
    "grid_import_kwh",
    "grid_export_kwh",
    "grid_interaction_kwh",
    "dispatch_cost_eur",
    "dispatch_objective_eur",
    "dispatch_operating_cost_eur",
    "dispatch_penalty_total_eur",
    "fuel_cost_eur",
    "co2_cost_eur",
    "variable_opex_eur",
    "unserved_penalty_eur",
    "temperature_violation_penalty_eur",
    "thermflex_activation_penalty_eur",
    "spill_penalty_eur",
    "grid_import_cost_eur",
    "mc_auction_import_cost_proxy_eur",
    "grid_export_revenue_eur",
    "co2_emissions_total_t",
    "dh_total_peak_change_kw",
    "district_gas_boiler_peak_kw",
}


def _lca_metric_exists(params: Dict[str, Any], metric: str) -> bool:
    for value in params.values():
        if not isinstance(value, dict):
            continue
        lca = value.get("LCA", {})
        if not isinstance(lca, dict):
            continue
        if metric in lca.get("infra", {}) or metric in lca.get("op", {}):
            return True
    return False


def _has_lca_metric_for_param_key(params: Dict[str, Any], param_key: str, metric: str) -> bool:
    block = params.get(param_key, {})
    if not isinstance(block, dict):
        return False
    lca = block.get("LCA", {})
    if not isinstance(lca, dict):
        return False
    return metric in lca.get("infra", {}) or metric in lca.get("op", {})


def _require_dh_lca_coverage(params: Dict[str, Any], design_vars: Dict[str, Any], metric: str) -> None:
    active_dh_assets = [
        ("district_external_heat", float(design_vars.get("district_external_heat_kw_th", params.get("district_external_heat_kw_th", 0.0))), "DISTRICT_EXTERNAL_HEAT"),
        ("district_gas_boiler", float(design_vars.get("district_gas_boiler_kw_th", params.get("district_gas_boiler_kw_th", 0.0))), "DISTRICT_GAS_BOILER"),
        ("district_heat_pump", float(design_vars.get("district_heat_pump_kw_th", params.get("district_heat_pump_kw_th", 0.0))), "DISTRICT_HEAT_PUMP"),
        ("district_thermal_storage", float(design_vars.get("district_thermal_storage_kwh_th", params.get("district_thermal_storage_kwh_th", 0.0))), "DISTRICT_THERMAL_STORAGE"),
        ("district_wood_chip_boiler", float(design_vars.get("district_wood_chip_boiler_kw_th", params.get("district_wood_chip_boiler_kw_th", 0.0))), "DISTRICT_WOOD_CHIP_BOILER"),
        ("district_biomass_chp", float(design_vars.get("district_biomass_chp_kw_th", params.get("district_biomass_chp_kw_th", 0.0))), "DISTRICT_BIOMASS_CHP"),
        ("district_biogas_chp", float(design_vars.get("district_biogas_chp_kw_el", params.get("district_biogas_chp_kw_el", 0.0))), "DISTRICT_BIOGAS_CHP"),
        ("district_gas_chp", float(design_vars.get("district_gas_chp_kw_el", params.get("district_gas_chp_kw_el", 0.0))), "DISTRICT_GAS_CHP"),
        ("district_geothermal", float(design_vars.get("district_geothermal_kw_el", params.get("district_geothermal_kw_el", 0.0))), "DISTRICT_GEOTHERMAL"),
        ("district_solar_thermal", float(design_vars.get("district_solar_thermal_kw_th", params.get("district_solar_thermal_kw_th", 0.0))), "DISTRICT_SOLAR_THERMAL"),
        ("district_waste_incineration", float(design_vars.get("district_waste_incineration_kw_th", params.get("district_waste_incineration_kw_th", 0.0))), "DISTRICT_WASTE_INCINERATION"),
    ]
    missing = [
        tech_name
        for tech_name, activity_level, param_key in active_dh_assets
        if activity_level > 0.0 and not _has_lca_metric_for_param_key(params, param_key, metric)
    ]
    if missing:
        raise ValueError(
            f"[kpi] objective '{metric}' requested, but LCA SSOT is missing for active DH technologies: {', '.join(missing)}. "
            "Add validated LCA data first instead of silently undercounting these technologies."
        )


def _total_lca_metric(
    params: Dict[str, Any],
    metric: str,
    pv_kwp: float,
    bess_kwh: float,
    fc_kw: float,
    ely_kw: float,
    h2_tank_kwh: float,
    E_import_grid_L: float,
    E_h2_discharge_elec_L: float = 0.0,
    pv_generation_L: float = 0.0,
    bess_throughput_L: float = 0.0,
) -> float:
    pv = params.get("PV", {}).get("LCA", {})
    bs = params.get("BESS", {}).get("LCA", {})
    gr = params.get("Grid", {}).get("LCA", {})
    fc = params.get("FC", {}).get("LCA", {})
    ely = params.get("ELY", {}).get("LCA", {})
    h2_tank = params.get("H2_TANK", {}).get("LCA", {})

    lifetime = float(params.get("lifetime"))
    annual_bess_throughput = bess_throughput_L / lifetime if lifetime > 0 else 0.0
    annual_fc_output = E_h2_discharge_elec_L / lifetime if lifetime > 0 else 0.0

    pv_rep = compute_pv_replacement(params).n_total_units
    bs_rep = compute_bess_replacement(
        params,
        bess_kwh=bess_kwh,
        annual_bess_throughput_kwh=annual_bess_throughput,
    ).n_total_units
    fc_rep = compute_fc_replacement(
        params,
        fc_kw=fc_kw,
        annual_fc_output_kwh=annual_fc_output,
    ).n_total_units

    pv_infra = float(pv.get("infra", {}).get(metric, 0.0))
    pv_op = float(pv.get("op", {}).get(metric, 0.0))

    bs_infra = float(bs.get("infra", {}).get(metric, 0.0))
    bs_op = float(bs.get("op", {}).get(metric, 0.0))

    gr_infra = float(gr.get("infra", {}).get(metric, 0.0))
    gr_op = float(gr.get("op", {}).get(metric, 0.0))

    fc_infra = float(fc.get("infra", {}).get(metric, 0.0))
    ely_infra = float(ely.get("infra", {}).get(metric, 0.0))
    h2_tank_infra = float(h2_tank.get("infra", {}).get(metric, 0.0))

    return float(
        pv_infra * pv_kwp * pv_rep
        + bs_infra * bess_kwh * bs_rep
        + gr_infra * 0.0
        + gr_op * E_import_grid_L
        + pv_op * pv_generation_L
        + bs_op * bess_throughput_L
        + fc_infra * fc_kw * fc_rep
        + ely_infra * ely_kw
        + h2_tank_infra * h2_tank_kwh
    )


def _year_from_lifetime(flows_L: Dict[str, float], key: str, lifetime: int) -> float:
    return float(flows_L.get(key, 0.0)) / float(lifetime) if lifetime > 0 else 0.0


def _dispatch_objective_terms(design_vars: Dict[str, Any]) -> Dict[str, float] | None:
    raw_results = design_vars.get("raw_results")
    if not isinstance(raw_results, dict):
        return None
    dispatch_diag = raw_results.get("dispatch_diagnostics")
    if not isinstance(dispatch_diag, dict):
        return None
    objective_terms = dispatch_diag.get("objective_terms")
    if not isinstance(objective_terms, dict):
        return None
    return {str(k): float(v) for k, v in objective_terms.items()}


def is_supported_objective_name(params: Dict[str, Any], name: str) -> bool:
    return str(name) in SUPPORTED_BASE_OBJECTIVE_NAMES or _lca_metric_exists(params, str(name))


def _resolve_objective_names(
    settings: Any,
    requested_objective_names: List[str] | None = None,
) -> List[str]:
    selected = list(getattr(getattr(settings, "objectives", None), "names", []) or [])
    for name in list(requested_objective_names or []):
        normalized = str(name)
        if normalized not in selected:
            selected.append(normalized)
    return selected


def compute_objectives(
    flows_L: Dict[str, float],
    design_vars: Dict[str, Any],
    settings: Any,
    profiles: Dict[str, Any] | None = None,
    requested_objective_names: List[str] | None = None,
) -> Dict[str, float]:
    params = dict(design_vars.get("params", {}))
    lifetime_years = int(design_vars.get("lifetime_years", params.get("lifetime", params.get("lifetime_years", 25))))
    L = int(params.get("lifetime", lifetime_years))

    pv_kwp = float(design_vars.get("pv_kwp", 0.0))
    bess_kwh = float(design_vars.get("bess_kwh", 0.0))
    fc_kw = float(design_vars.get("fc_kw", 0.0))
    ely_kw = float(design_vars.get("ely_kw", 0.0))
    h2_tank_kwh = float(design_vars.get("h2_tank_kwh", 0.0))

    def Y(k: str) -> float:
        return float(flows_L.get(k, 0.0)) / float(L)

    e_import_grid_Y = Y("E_import_grid_kWh")
    e_export_grid_Y = Y("E_export_grid_kWh")
    e_import_ec_pv_Y = Y("E_import_ec_pv_kWh")
    e_import_ec_ev_Y = Y("E_import_ec_ev_kWh")
    e_export_ec_pv_Y = Y("E_export_ec_pv_kWh")
    e_export_ec_ev_Y = Y("E_export_ec_ev_kWh")

    E_import_grid_L = float(flows_L.get("E_import_grid_kWh", 0.0))
    E_export_grid_L = float(flows_L.get("E_export_grid_kWh", 0.0))
    E_load_L = float(flows_L.get("E_total_load_kWh", 0.0))
    gas_boiler_co2_t = float(flows_L.get("district_gas_boiler_co2_t", 0.0))
    gas_chp_co2_t = float(flows_L.get("district_gas_chp_co2_t", 0.0))
    obj_names = _resolve_objective_names(settings, requested_objective_names)
    needs_dispatch_cost_terms = any(
        name in {
            "dispatch_cost_eur",
            "dispatch_objective_eur",
            "dispatch_operating_cost_eur",
            "dispatch_penalty_total_eur",
            "fuel_cost_eur",
            "co2_cost_eur",
            "variable_opex_eur",
            "unserved_penalty_eur",
            "temperature_violation_penalty_eur",
            "thermflex_activation_penalty_eur",
            "spill_penalty_eur",
            "grid_import_cost_eur",
            "mc_auction_import_cost_proxy_eur",
            "grid_export_revenue_eur",
        }
        for name in obj_names
    )
    dispatch_terms = _dispatch_objective_terms(design_vars)
    dispatch_costs = build_dispatch_cost_breakdown(
        dispatch_terms,
        strict=needs_dispatch_cost_terms,
    )
    out: Dict[str, float] = {}

    npc_val = None
    if "npc_eur" in obj_names:
        from Cost_model.financial_model import calculate_npc_tariff_aware, calculate_npc_yearly

        params_fin = dict(params)
        params_fin["pv_size"] = float(pv_kwp)
        params_fin["battery_capacity_kWh"] = float(bess_kwh)
        params_fin["ely_kw"] = float(design_vars.get("ely_kw", 0.0))
        params_fin["h2_tank_kwh"] = float(design_vars.get("h2_tank_kwh", 0.0))
        params_fin["fc_kw"] = float(design_vars.get("fc_kw", 0.0))
        params_fin["small_wind_kw"] = float(design_vars.get("small_wind_kw", params.get("small_wind_kw", 0.0)))
        params_fin["large_wind_kw"] = float(design_vars.get("large_wind_kw", params.get("large_wind_kw", 0.0)))
        params_fin["biogas_engine_kw"] = float(design_vars.get("biogas_engine_kw", params.get("biogas_engine_kw", 0.0)))
        params_fin["wood_gasifier_kw"] = float(design_vars.get("wood_gasifier_kw", params.get("wood_gasifier_kw", 0.0)))
        params_fin["district_external_heat_kw_th"] = float(design_vars.get("district_external_heat_kw_th", params.get("district_external_heat_kw_th", 0.0)))
        params_fin["district_gas_boiler_kw_th"] = float(design_vars.get("district_gas_boiler_kw_th", params.get("district_gas_boiler_kw_th", 0.0)))
        params_fin["district_heat_pump_kw_th"] = float(design_vars.get("district_heat_pump_kw_th", params.get("district_heat_pump_kw_th", 0.0)))
        params_fin["district_thermal_storage_kwh_th"] = float(design_vars.get("district_thermal_storage_kwh_th", params.get("district_thermal_storage_kwh_th", 0.0)))
        params_fin["district_wood_chip_boiler_kw_th"] = float(design_vars.get("district_wood_chip_boiler_kw_th", params.get("district_wood_chip_boiler_kw_th", 0.0)))
        params_fin["district_biomass_chp_kw_th"] = float(design_vars.get("district_biomass_chp_kw_th", params.get("district_biomass_chp_kw_th", 0.0)))
        params_fin["district_geothermal_kw_el"] = float(design_vars.get("district_geothermal_kw_el", params.get("district_geothermal_kw_el", 0.0)))
        params_fin["district_gas_chp_kw_el"] = float(design_vars.get("district_gas_chp_kw_el", params.get("district_gas_chp_kw_el", 0.0)))
        params_fin["district_biogas_chp_kw_el"] = float(design_vars.get("district_biogas_chp_kw_el", params.get("district_biogas_chp_kw_el", 0.0)))

        eng = getattr(settings, "engine", None)
        features = getattr(eng, "features", None) if eng is not None else None
        enable_v2h = bool(getattr(features, "enable_v2h", False))
        enable_h2 = bool(getattr(features, "enable_h2", False))
        # Mirror the V2H gate: when H2 is feature-disabled, force capacities to
        # zero before NPC so financial_model cannot charge H2 CAPEX (including
        # ``hydrogen.fixed_system_eur``) for an inactive technology.
        if not enable_h2:
            params_fin["ely_kw"] = 0.0
            params_fin["h2_tank_kwh"] = 0.0
            params_fin["fc_kw"] = 0.0
        params_fin.setdefault("EV", {})
        params_fin["EV"]["N_EV_total"] = int(getattr(eng, "N_EV_total", 0))
        params_fin["EV"]["N_EV_bidirectional"] = int(getattr(eng, "N_EV_bidirectional", 0)) if enable_v2h else 0
        if "npc_eur" in flows_L:
            npc_val = float(flows_L["npc_eur"])
        else:
            active_tariff_arm = str(getattr(getattr(settings, "market", None), "active_tariff_arm", "flat") or "flat").strip().lower()
            if active_tariff_arm == "flat":
                npc_val = float(
                    calculate_npc_yearly(
                        params_fin,
                        e_import_grid_year=e_import_grid_Y,
                        e_import_ec_pv_year=e_import_ec_pv_Y,
                        e_import_ec_ev_year=e_import_ec_ev_Y,
                        e_export_grid_year=e_export_grid_Y,
                        e_export_pv_ec_year=e_export_ec_pv_Y,
                        e_export_ev_ec_year=e_export_ec_ev_Y,
                        bess_throughput_year=Y("BESS_throughput_kWh"),
                        fc_output_year=Y("E_h2_discharge_elec_kWh"),
                        wood_gasifier_fuel_input_year=Y("E_wood_gasifier_fuel_input_kWh"),
                        district_external_heat_generation_year_kwh=Y("E_district_external_heat_generation_kWh"),
                        district_gas_boiler_generation_year_kwh=Y("E_district_gas_boiler_generation_kWh"),
                        district_gas_boiler_fuel_input_year_m3=Y("V_district_gas_boiler_fuel_input_m3"),
                        district_wood_chip_boiler_fuel_input_year_kg=Y("M_district_wood_chip_boiler_fuel_input_kg"),
                        district_biomass_chp_fuel_input_year_kg=Y("M_district_biomass_chp_fuel_input_kg"),
                        district_biogas_chp_fuel_input_year_nm3=Y("V_district_biogas_chp_fuel_input_nm3"),
                        district_gas_chp_fuel_input_year_m3=Y("V_district_gas_chp_fuel_input_m3"),
                    )
                )
            else:
                raw_results = design_vars.get("raw_results")
                if raw_results is None:
                    raise ValueError(
                        f"[kpi] active_tariff_arm='{active_tariff_arm}' requires raw hourly results for tariff-aware NPC. "
                        "For surrogate-based runs, include 'npc_eur' as a direct surrogate target."
                    )
                if profiles is None:
                    raise ValueError(f"[kpi] active_tariff_arm='{active_tariff_arm}' requires profiles for tariff-aware NPC.")
                market_bundle = build_market_bundle(settings, params_fin, profiles)
                npc_val = float(
                    calculate_npc_tariff_aware(
                        params_fin,
                        flows_hourly=raw_results,
                        market_bundle=market_bundle,
                        bess_throughput_year=Y("BESS_throughput_kWh"),
                        fc_output_year=Y("E_h2_discharge_elec_kWh"),
                        wood_gasifier_fuel_input_year=Y("E_wood_gasifier_fuel_input_kWh"),
                        district_external_heat_generation_year_kwh=Y("E_district_external_heat_generation_kWh"),
                        district_gas_boiler_generation_year_kwh=Y("E_district_gas_boiler_generation_kWh"),
                        district_gas_boiler_fuel_input_year_m3=Y("V_district_gas_boiler_fuel_input_m3"),
                        district_wood_chip_boiler_fuel_input_year_kg=Y("M_district_wood_chip_boiler_fuel_input_kg"),
                        district_biomass_chp_fuel_input_year_kg=Y("M_district_biomass_chp_fuel_input_kg"),
                        district_biogas_chp_fuel_input_year_nm3=Y("V_district_biogas_chp_fuel_input_nm3"),
                        district_gas_chp_fuel_input_year_m3=Y("V_district_gas_chp_fuel_input_m3"),
                    )
                )

    autarky_val = None
    if "autarky" in obj_names:
        autarky = 1.0 - (E_import_grid_L / E_load_L) if E_load_L > 0 else 0.0
        autarky_val = float(max(0.0, min(1.0, autarky)))

    for name in obj_names:
        if name == "npc_eur":
            out[name] = float(npc_val or 0.0)
        elif name == "autarky":
            out[name] = float(autarky_val or 0.0)
        elif name == "grid_import_kwh":
            out[name] = float(E_import_grid_L)
        elif name == "grid_export_kwh":
            out[name] = float(E_export_grid_L)
        elif name == "grid_interaction_kwh":
            out[name] = float(E_import_grid_L + E_export_grid_L)
        elif name == "dispatch_cost_eur":
            out[name] = float(dispatch_costs.dispatch_cost_eur)
        elif name == "dispatch_objective_eur":
            out[name] = float(dispatch_costs.dispatch_objective_eur)
        elif name == "dispatch_operating_cost_eur":
            out[name] = float(dispatch_costs.dispatch_operating_cost_eur)
        elif name == "dispatch_penalty_total_eur":
            out[name] = float(dispatch_costs.dispatch_penalty_total_eur)
        elif name == "fuel_cost_eur":
            out[name] = float(dispatch_costs.fuel_cost_eur)
        elif name == "co2_cost_eur":
            out[name] = float(dispatch_costs.co2_cost_eur)
        elif name == "variable_opex_eur":
            out[name] = float(dispatch_costs.variable_opex_eur)
        elif name == "unserved_penalty_eur":
            out[name] = float(dispatch_costs.unserved_penalty_eur)
        elif name == "temperature_violation_penalty_eur":
            out[name] = float(dispatch_costs.temperature_violation_penalty_eur)
        elif name == "thermflex_activation_penalty_eur":
            out[name] = float(dispatch_costs.thermflex_activation_penalty_eur)
        elif name == "spill_penalty_eur":
            out[name] = float(dispatch_costs.spill_penalty_eur)
        elif name == "grid_import_cost_eur":
            out[name] = float(dispatch_costs.mc_auction_import_cost_proxy_eur)
        elif name == "mc_auction_import_cost_proxy_eur":
            out[name] = float(dispatch_costs.mc_auction_import_cost_proxy_eur)
        elif name == "grid_export_revenue_eur":
            out[name] = float(dispatch_costs.grid_export_revenue_eur)
        elif name == "co2_emissions_total_t":
            # The dispatch paper/surrogate layer uses operational fossil CO2 as a
            # first-class KPI. We therefore expose the same quantity as an
            # explicit optimization objective instead of forcing callers to
            # rename it to an unrelated LCA category.
            if "co2_emissions_total_t" in flows_L:
                out[name] = float(flows_L["co2_emissions_total_t"])
            elif "district_gas_boiler_co2_t" in flows_L or "district_gas_chp_co2_t" in flows_L:
                out[name] = float(gas_boiler_co2_t + gas_chp_co2_t)
            else:
                raise ValueError(
                    "[kpi] objective 'co2_emissions_total_t' requested, but neither "
                    "'co2_emissions_total_t' nor the required gas CO2 components are present in flows_L."
                )
        elif name == "dh_total_peak_change_kw":
            if "dh_total_peak_change_kw" in flows_L:
                out[name] = float(flows_L["dh_total_peak_change_kw"])
            else:
                raise ValueError(
                    "[kpi] objective 'dh_total_peak_change_kw' requested, but the dispatch path did not "
                    "export this KPI into flows_L."
                )
        elif name == "district_gas_boiler_peak_kw":
            if "district_gas_boiler_peak_kw" in flows_L:
                out[name] = float(flows_L["district_gas_boiler_peak_kw"])
            else:
                raise ValueError(
                    "[kpi] objective 'district_gas_boiler_peak_kw' requested, but the dispatch path did not "
                    "export this KPI into flows_L."
                )
        elif _lca_metric_exists(params, name):
            _require_dh_lca_coverage(params, design_vars, name)
            out[name] = _total_lca_metric(
                params,
                name,
                pv_kwp,
                bess_kwh,
                fc_kw,
                ely_kw,
                h2_tank_kwh,
                E_import_grid_L,
                E_h2_discharge_elec_L=float(flows_L.get("E_h2_discharge_elec_kWh", 0.0)),
                pv_generation_L=float(flows_L.get("PV_generation_kWh", 0.0)),
                bess_throughput_L=float(flows_L.get("BESS_throughput_kWh", 0.0)),
            )
        else:
            raise ValueError(
                f"[kpi] unknown objective '{name}'. "
                f"Supported: npc_eur, autarky, grid_import_kwh, grid_export_kwh, grid_interaction_kwh, "
                f"dispatch_cost_eur, dispatch_objective_eur, dispatch_operating_cost_eur, dispatch_penalty_total_eur, "
                f"fuel_cost_eur, co2_cost_eur, variable_opex_eur, unserved_penalty_eur, "
                f"temperature_violation_penalty_eur, thermflex_activation_penalty_eur, spill_penalty_eur, "
                f"grid_import_cost_eur, mc_auction_import_cost_proxy_eur, grid_export_revenue_eur, "
                f"co2_emissions_total_t, dh_total_peak_change_kw, district_gas_boiler_peak_kw, climate_change, "
                f"or any LCA metric present in params[tech]['LCA']."
            )
    return out


def get_selected_objective_names(
    settings: Any,
    requested_objective_names: List[str] | None = None,
) -> List[str]:
    return _resolve_objective_names(settings, requested_objective_names)


def compute_constraints(
    flows_L: Dict[str, float],
    design_vars: Dict[str, Any],
    settings: Any,
    profiles: Dict[str, Any] | None = None,
) -> Tuple[List[float], Dict[str, Any]]:
    con_names = list(getattr(settings.constraints, "names", []) or [])
    if not con_names:
        return [], {}

    ctx = {
        "params": dict(design_vars.get("params", {})),
        "settings": settings,
        "E_import_grid_L": float(flows_L.get("E_import_grid_kWh", 0.0)),
        "E_load_L": float(flows_L.get("E_total_load_kWh", 0.0)),
        "E_export_grid_L": float(flows_L.get("E_export_grid_kWh", 0.0)),
        "PV_generation_L": float(flows_L.get("PV_generation_kWh", 0.0)),
        "pv_kwp": float(design_vars.get("pv_kwp", 0.0)),
        "bess_kwh": float(design_vars.get("bess_kwh", 0.0)),
        "ely_kw": float(design_vars.get("ely_kw", 0.0)),
        "h2_tank_kwh": float(design_vars.get("h2_tank_kwh", 0.0)),
        "fc_kw": float(design_vars.get("fc_kw", 0.0)),
        "district_wood_chip_boiler_kw_th": float(
            design_vars.get("district_wood_chip_boiler_kw_th", design_vars.get("params", {}).get("district_wood_chip_boiler_kw_th", 0.0))
        ),
        "district_biomass_chp_kw_th": float(
            design_vars.get("district_biomass_chp_kw_th", design_vars.get("params", {}).get("district_biomass_chp_kw_th", 0.0))
        ),
        "district_biogas_chp_kw_el": float(
            design_vars.get("district_biogas_chp_kw_el", design_vars.get("params", {}).get("district_biogas_chp_kw_el", 0.0))
        ),
        "bess_cyclic_violation_kwh": float(flows_L.get("bess_cyclic_violation_kwh", 0.0)),
        "h2_cyclic_violation_kwh": float(flows_L.get("h2_cyclic_violation_kwh", 0.0)),
    }
    return evaluate_constraints(settings.constraints, ctx), ctx


def compute_kpis(
    flows_L: Dict[str, float],
    design_vars: Dict[str, Any],
    settings: Any,
    profiles: Dict[str, Any] | None = None,
    requested_objective_names: List[str] | None = None,
) -> Tuple[Dict[str, float], List[float], Dict[str, Any]]:
    objectives = compute_objectives(
        flows_L,
        design_vars,
        settings,
        profiles,
        requested_objective_names=requested_objective_names,
    )
    constraints, ctx = compute_constraints(flows_L, design_vars, settings, profiles)
    return objectives, constraints, ctx
