from __future__ import annotations

import numpy as np

from Data.economic_data.replacement_costs import REPLACEMENT_COST_FACTORS
from Data.assembly.replacements import compute_bess_replacement, compute_fc_replacement, compute_pv_replacement


def _require_key(params, key: str):
    if key not in params:
        raise ValueError(f"[financial_model] Missing required key '{key}'.")
    return params[key]


def _require_dict(value, name: str):
    if not isinstance(value, dict):
        raise ValueError(f"[financial_model] Required block '{name}' must be a dict.")
    return value


def _require_path(root, *path: str):
    current = root
    traversed = []
    for key in path:
        traversed.append(str(key))
        current = _require_dict(current, ".".join(traversed[:-1]) or "root")
        if key not in current:
            raise ValueError(f"[financial_model] Missing required key '{'.'.join(traversed)}'.")
        current = current[key]
    return current


def _require_repl_factor(tech: str) -> float:
    if tech not in REPLACEMENT_COST_FACTORS:
        raise ValueError(f"[financial_model] Missing replacement cost factor for tech '{tech}'.")
    f = float(REPLACEMENT_COST_FACTORS[tech])
    if f <= 0.0:
        raise ValueError(f"[financial_model] Replacement cost factor for tech '{tech}' must be > 0, got {f}.")
    return f


def _economics_blocks(params):
    economics = _require_dict(_require_key(params, "economics"), "economics")
    return {
        "economics": economics,
        "finance": _require_dict(_require_path(economics, "finance"), "economics.finance"),
        "grid": _require_dict(_require_path(economics, "grid"), "economics.grid"),
        "community": _require_dict(_require_path(economics, "community"), "economics.community"),
        "technology": _require_dict(_require_path(economics, "technology"), "economics.technology"),
        "hydrogen": _require_dict(_require_path(economics, "hydrogen"), "economics.hydrogen"),
    }


def _tech_cost(technology_costs, name: str):
    if name not in technology_costs:
        raise ValueError(f"[financial_model] Missing required technology cost block '{name}'.")
    value = technology_costs[name]
    if not isinstance(value, dict):
        raise ValueError(f"[financial_model] Technology cost block '{name}' must be a dict.")
    return value


def _validated_optional_tech_cost(technology_costs, name: str, required_keys: list[str]):
    if name not in technology_costs:
        raise ValueError(
            f"[financial_model] Technology cost block '{name}' is required for this run but missing in params['economics']['technology']."
        )
    value = technology_costs[name]
    if not isinstance(value, dict):
        raise ValueError(f"[financial_model] Technology cost block '{name}' must be a dict.")
    if not bool(value.get("validated", False)):
        raise ValueError(
            f"[financial_model] {name} is active, but its economics block is not validated yet. "
            f"Set params['economics']['technology']['{name}']['validated']=True and provide the required cost keys first."
        )
    for key in required_keys:
        if key not in value or value[key] is None:
            raise ValueError(
                f"[financial_model] Technology cost block '{name}' is validated, but required key '{key}' is missing."
            )
    return value


def _annualized_capex_and_opex(
    params,
    *,
    bess_throughput_year=0.0,
    fc_output_year=0.0,
    wood_gasifier_fuel_input_year=0.0,
    district_external_heat_generation_year_kwh=0.0,
    district_gas_boiler_generation_year_kwh=0.0,
    district_gas_boiler_fuel_input_year_m3=0.0,
    district_wood_chip_boiler_fuel_input_year_kg=0.0,
    district_biomass_chp_fuel_input_year_kg=0.0,
    district_biogas_chp_fuel_input_year_nm3=0.0,
    district_gas_chp_fuel_input_year_m3=0.0,
):
    float_ = float
    econ = _economics_blocks(params)
    tech = econ["technology"]

    pv_cost = _tech_cost(tech, "pv")
    bess_cost = _tech_cost(tech, "bess")
    ev_cost = _tech_cost(tech, "ev")
    ely_cost = _tech_cost(tech, "ely")
    h2_tank_cost = _tech_cost(tech, "h2_tank")
    fc_cost = _tech_cost(tech, "fc")
    comp_cost = _tech_cost(tech, "compressor")
    small_wind_cost = _tech_cost(tech, "small_wind")
    large_wind_cost = _tech_cost(tech, "large_wind")
    biogas_engine_cost = _tech_cost(tech, "biogas_engine")
    wood_gasifier_cost = _tech_cost(tech, "wood_gasifier")
    district_hp_cost = _tech_cost(tech, "district_heat_pump")
    district_storage_cost = _tech_cost(tech, "district_thermal_storage")
    district_wood_boiler_cost = _tech_cost(tech, "district_wood_chip_boiler")
    district_biomass_chp_cost = _tech_cost(tech, "district_biomass_chp")
    district_external_heat_cost = _tech_cost(tech, "district_external_heat")
    district_gas_boiler_cost = _tech_cost(tech, "district_gas_boiler")
    district_biogas_chp_cost = _tech_cost(tech, "district_biogas_chp")
    district_gas_chp_cost = _tech_cost(tech, "district_gas_chp")
    district_geothermal_cost = _tech_cost(tech, "district_geothermal")

    pv_kwp = float_(params.get("pv_size", 0.0))
    bess_kwh = float_(params.get("battery_capacity_kWh", 0.0))
    ely_kw = float_(params.get("ely_kw", 0.0))
    h2_tank_kwh = float_(params.get("h2_tank_kwh", 0.0))
    fc_kw = float_(params.get("fc_kw", 0.0))
    small_wind_kw = float_(params.get("small_wind_kw", 0.0))
    large_wind_kw = float_(params.get("large_wind_kw", 0.0))
    biogas_engine_kw = float_(params.get("biogas_engine_kw", 0.0))
    wood_gasifier_kw = float_(params.get("wood_gasifier_kw", 0.0))
    district_heat_pump_kw_th = float_(params.get("district_heat_pump_kw_th", 0.0))
    district_thermal_storage_kwh_th = float_(params.get("district_thermal_storage_kwh_th", 0.0))
    district_solar_thermal_kw_th = float_(params.get("district_solar_thermal_kw_th", 0.0))
    district_waste_incineration_kw_th = float_(params.get("district_waste_incineration_kw_th", 0.0))
    district_wood_chip_boiler_kw_th = float_(params.get("district_wood_chip_boiler_kw_th", 0.0))
    district_biomass_chp_kw_th = float_(params.get("district_biomass_chp_kw_th", 0.0))
    district_gas_boiler_kw_th = float_(params.get("district_gas_boiler_kw_th", 0.0))
    district_geothermal_kw_el = float_(params.get("district_geothermal_kw_el", 0.0))
    district_gas_chp_kw_el = float_(params.get("district_gas_chp_kw_el", 0.0))
    district_biogas_chp_kw_el = float_(params.get("district_biogas_chp_kw_el", 0.0))
    district_solar_thermal_cost = None
    district_waste_incineration_cost = None
    if district_solar_thermal_kw_th > 0.0:
        district_solar_thermal_cost = _validated_optional_tech_cost(
            tech,
            "district_solar_thermal",
            ["capex_eur_per_kw_th", "maintenance_rate"],
        )
    if district_waste_incineration_kw_th > 0.0:
        district_waste_incineration_cost = _validated_optional_tech_cost(
            tech,
            "district_waste_incineration",
            ["capex_eur_per_kw_th", "maintenance_rate"],
        )

    ev = params.setdefault("EV", {})
    n_ev_bidir = int(ev.get("N_EV_bidirectional", 0))
    n_ev_total = int(ev.get("N_EV_total", 0))
    n_ev_charge = max(0, n_ev_total - n_ev_bidir)

    capex_pv = float_(pv_cost["capex_eur_per_kwp"]) * pv_kwp
    capex_batt = float_(bess_cost["capex_eur_per_kwh"]) * bess_kwh
    capex_ev_charge = float_(ev_cost["charge_capex_eur_per_unit"]) * n_ev_charge
    capex_ev_bidir = float_(ev_cost["v2h_capex_eur_per_unit"]) * n_ev_bidir
    capex_ev = capex_ev_charge + capex_ev_bidir
    capex_ely = float_(ely_cost["capex_eur_per_kw"]) * ely_kw
    capex_h2_tank = float_(h2_tank_cost["capex_eur_per_kwh"]) * h2_tank_kwh
    capex_fc = float_(fc_cost["capex_eur_per_kw"]) * fc_kw
    capex_comp = float_(comp_cost["capex_eur_per_kw_ely"]) * ely_kw
    capex_h2_fixed = float_(econ["hydrogen"]["fixed_system_eur"])
    capex_h2 = capex_h2_fixed + capex_ely + capex_h2_tank + capex_fc + capex_comp
    capex_small_wind = float_(small_wind_cost["capex_eur_per_kw"]) * small_wind_kw
    capex_large_wind = float_(large_wind_cost["capex_eur_per_kw"]) * large_wind_kw
    capex_biogas_engine = float_(biogas_engine_cost["capex_eur_per_kw"]) * biogas_engine_kw
    capex_wood_gasifier = float_(wood_gasifier_cost["capex_eur_per_kw"]) * wood_gasifier_kw
    capex_district_heat_pump = float_(district_hp_cost["capex_eur_per_kw_th"]) * district_heat_pump_kw_th
    capex_district_storage = float_(district_storage_cost["capex_eur_per_kwh_th"]) * district_thermal_storage_kwh_th
    capex_district_solar_thermal = (
        float_(district_solar_thermal_cost["capex_eur_per_kw_th"]) * district_solar_thermal_kw_th
        if district_solar_thermal_cost is not None
        else 0.0
    )
    capex_district_waste_incineration = (
        float_(district_waste_incineration_cost["capex_eur_per_kw_th"]) * district_waste_incineration_kw_th
        if district_waste_incineration_cost is not None
        else 0.0
    )
    capex_district_gas_boiler = float_(district_gas_boiler_cost.get("capex_eur_per_kw_th", 0.0)) * district_gas_boiler_kw_th
    capex_district_wood_boiler = float_(district_wood_boiler_cost["capex_eur_per_kw_th"]) * district_wood_chip_boiler_kw_th
    capex_district_biomass_chp = float_(district_biomass_chp_cost["capex_eur_per_kw_th"]) * district_biomass_chp_kw_th
    capex_district_biogas_chp = float_(district_biogas_chp_cost["capex_eur_per_kw_el"]) * district_biogas_chp_kw_el
    capex_district_gas_chp = float_(district_gas_chp_cost["capex_eur_per_kw_el"]) * district_gas_chp_kw_el
    capex_district_geothermal = float_(district_geothermal_cost["capex_eur_per_kw_el"]) * district_geothermal_kw_el

    total_capex = (
        capex_pv
        + capex_batt
        + capex_ev
        + capex_h2
        + capex_small_wind
        + capex_large_wind
        + capex_biogas_engine
        + capex_wood_gasifier
        + capex_district_heat_pump
        + capex_district_storage
        + capex_district_solar_thermal
        + capex_district_waste_incineration
        + capex_district_gas_boiler
        + capex_district_wood_boiler
        + capex_district_biomass_chp
        + capex_district_biogas_chp
        + capex_district_gas_chp
        + capex_district_geothermal
    )

    opex_annual = (
        capex_pv * float_(pv_cost["maintenance_rate"])
        + capex_batt * float_(bess_cost["maintenance_rate"])
        + capex_ev * float_(ev_cost["maintenance_rate"])
        + capex_ely * float_(ely_cost["maintenance_rate"])
        + capex_h2_tank * float_(h2_tank_cost["maintenance_rate"])
        + capex_fc * float_(fc_cost["maintenance_rate"])
        + capex_comp * float_(comp_cost["maintenance_rate"])
        + capex_small_wind * float_(small_wind_cost["maintenance_rate"])
        + capex_large_wind * float_(large_wind_cost["maintenance_rate"])
        + capex_biogas_engine * float_(biogas_engine_cost["maintenance_rate"])
        + capex_wood_gasifier * float_(wood_gasifier_cost["maintenance_rate"])
        + capex_district_heat_pump * float_(district_hp_cost["maintenance_rate"])
        + capex_district_storage * float_(district_storage_cost["maintenance_rate"])
        + (
            capex_district_solar_thermal * float_(district_solar_thermal_cost["maintenance_rate"])
            if district_solar_thermal_cost is not None
            else 0.0
        )
        + (
            capex_district_waste_incineration * float_(district_waste_incineration_cost["maintenance_rate"])
            if district_waste_incineration_cost is not None
            else 0.0
        )
        + capex_district_gas_boiler * float_(district_gas_boiler_cost.get("maintenance_rate", 0.0))
        + capex_district_wood_boiler * float_(district_wood_boiler_cost["maintenance_rate"])
        + capex_district_biomass_chp * float_(district_biomass_chp_cost["maintenance_rate"])
        + capex_district_biogas_chp * float_(district_biogas_chp_cost["maintenance_rate"])
        + capex_district_gas_chp * float_(district_gas_chp_cost["maintenance_rate"])
        + capex_district_geothermal * float_(district_geothermal_cost["maintenance_rate"])
        + float_(wood_gasifier_cost["fuel_eur_per_kwh_fuel"]) * float_(wood_gasifier_fuel_input_year)
        + float_(district_external_heat_cost["variable_opex_eur_per_kwh_th"]) * float_(district_external_heat_generation_year_kwh)
        + float_(district_gas_boiler_cost.get("variable_opex_eur_per_kwh_th", 0.0)) * float_(district_gas_boiler_generation_year_kwh)
        + float_(district_gas_boiler_cost["fuel_eur_per_m3"]) * float_(district_gas_boiler_fuel_input_year_m3)
        + float_(district_wood_boiler_cost["fuel_eur_per_kg"]) * float_(district_wood_chip_boiler_fuel_input_year_kg)
        + float_(district_biomass_chp_cost["fuel_eur_per_kg"]) * float_(district_biomass_chp_fuel_input_year_kg)
        + float_(district_biogas_chp_cost["fuel_eur_per_nm3"]) * float_(district_biogas_chp_fuel_input_year_nm3)
        + float_(district_gas_chp_cost["fuel_eur_per_m3"]) * float_(district_gas_chp_fuel_input_year_m3)
    )

    return {
        "total_capex": float(total_capex),
        "opex_annual": float(opex_annual),
        "capex_pv": float(capex_pv),
        "capex_batt": float(capex_batt),
        "capex_ely": float(capex_ely),
        "capex_h2_tank": float(capex_h2_tank),
        "capex_fc": float(capex_fc),
        "capex_comp": float(capex_comp),
        "capex_district_solar_thermal": float(capex_district_solar_thermal),
        "capex_district_waste_incineration": float(capex_district_waste_incineration),
    }


def calculate_npc_yearly(
    params,
    e_import_grid_year,
    e_import_ec_pv_year=0.0,
    e_import_ec_ev_year=0.0,
    e_export_grid_year=0.0,
    e_export_pv_ec_year=0.0,
    e_export_ev_ec_year=0.0,
    bess_throughput_year=0.0,
    fc_output_year=0.0,
    wood_gasifier_fuel_input_year=0.0,
    district_external_heat_generation_year_kwh=0.0,
    district_gas_boiler_generation_year_kwh=0.0,
    district_gas_boiler_fuel_input_year_m3=0.0,
    district_wood_chip_boiler_fuel_input_year_kg=0.0,
    district_biomass_chp_fuel_input_year_kg=0.0,
    district_biogas_chp_fuel_input_year_nm3=0.0,
    district_gas_chp_fuel_input_year_m3=0.0,
) -> float:
    float_ = float
    econ = _economics_blocks(params)
    cost = _annualized_capex_and_opex(
        params,
        bess_throughput_year=bess_throughput_year,
        fc_output_year=fc_output_year,
        wood_gasifier_fuel_input_year=wood_gasifier_fuel_input_year,
        district_external_heat_generation_year_kwh=district_external_heat_generation_year_kwh,
        district_gas_boiler_generation_year_kwh=district_gas_boiler_generation_year_kwh,
        district_gas_boiler_fuel_input_year_m3=district_gas_boiler_fuel_input_year_m3,
        district_wood_chip_boiler_fuel_input_year_kg=district_wood_chip_boiler_fuel_input_year_kg,
        district_biomass_chp_fuel_input_year_kg=district_biomass_chp_fuel_input_year_kg,
        district_biogas_chp_fuel_input_year_nm3=district_biogas_chp_fuel_input_year_nm3,
        district_gas_chp_fuel_input_year_m3=district_gas_chp_fuel_input_year_m3,
    )

    lifetime = int(_require_key(params, "lifetime"))
    wacc = float_(econ["finance"]["wacc"])
    r_grid = float_(econ["finance"]["electricity_price_growth"])
    r_feed = float_(econ["finance"]["feedin_growth_rate"])
    r_ec = float_(econ["finance"]["ec_price_growth"])
    c_buy_grid = float_(econ["grid"]["buy_eur_per_kwh"])
    c_feed_grid = float_(econ["grid"]["feed_eur_per_kwh"])
    c_buy_ec = float_(econ["community"]["buy_eur_per_kwh"])
    c_feed_ec = float_(econ["community"]["feed_eur_per_kwh"])

    pv_repl = compute_pv_replacement(params)
    bess_repl = compute_bess_replacement(
        params,
        bess_kwh=float_(params.get("battery_capacity_kWh", 0.0)),
        annual_bess_throughput_kwh=float_(bess_throughput_year),
    )
    h2_trigger_repl = compute_fc_replacement(
        params,
        fc_kw=float_(params.get("fc_kw", 0.0)),
        annual_fc_output_kwh=float_(fc_output_year),
    )

    pv_repl_cost = _require_repl_factor("PV") * cost["capex_pv"]
    bess_repl_cost = _require_repl_factor("BESS") * cost["capex_batt"]
    h2_repl_bundle = cost["capex_ely"] + cost["capex_h2_tank"] + cost["capex_fc"] + cost["capex_comp"]
    h2_repl_cost = _require_repl_factor("H2_SYSTEM") * h2_repl_bundle

    npc = cost["total_capex"]
    for y in pv_repl.replacement_years:
        npc += pv_repl_cost / ((1 + wacc) ** float_(y))
    for y in bess_repl.replacement_years:
        npc += bess_repl_cost / ((1 + wacc) ** float_(y))
    for y in h2_trigger_repl.replacement_years:
        npc += h2_repl_cost / ((1 + wacc) ** float_(y))

    for y in range(1, lifetime + 1):
        price_buy_grid = c_buy_grid * ((1 + r_grid) ** (y - 1))
        price_feed_grid = c_feed_grid * ((1 + r_feed) ** (y - 1))
        price_buy_ec = c_buy_ec * ((1 + r_ec) ** (y - 1))
        price_feed_ec = c_feed_ec * ((1 + r_ec) ** (y - 1))

        annual_net = (
            float_(e_import_grid_year) * price_buy_grid
            + (float_(e_import_ec_pv_year) + float_(e_import_ec_ev_year)) * price_buy_ec
            - float_(e_export_grid_year) * price_feed_grid
            - (float_(e_export_pv_ec_year) + float_(e_export_ev_ec_year)) * price_feed_ec
            + cost["opex_annual"]
        )
        npc += annual_net / ((1 + wacc) ** y)

    return float(npc)


def calculate_npc_tariff_aware(
    params,
    *,
    flows_hourly: dict,
    market_bundle,
    bess_throughput_year=0.0,
    fc_output_year=0.0,
    wood_gasifier_fuel_input_year=0.0,
    district_external_heat_generation_year_kwh=0.0,
    district_gas_boiler_generation_year_kwh=0.0,
    district_gas_boiler_fuel_input_year_m3=0.0,
    district_wood_chip_boiler_fuel_input_year_kg=0.0,
    district_biomass_chp_fuel_input_year_kg=0.0,
    district_biogas_chp_fuel_input_year_nm3=0.0,
    district_gas_chp_fuel_input_year_m3=0.0,
) -> float:
    float_ = float
    econ = _economics_blocks(params)
    cost = _annualized_capex_and_opex(
        params,
        bess_throughput_year=bess_throughput_year,
        fc_output_year=fc_output_year,
        wood_gasifier_fuel_input_year=wood_gasifier_fuel_input_year,
        district_external_heat_generation_year_kwh=district_external_heat_generation_year_kwh,
        district_gas_boiler_generation_year_kwh=district_gas_boiler_generation_year_kwh,
        district_gas_boiler_fuel_input_year_m3=district_gas_boiler_fuel_input_year_m3,
        district_wood_chip_boiler_fuel_input_year_kg=district_wood_chip_boiler_fuel_input_year_kg,
        district_biomass_chp_fuel_input_year_kg=district_biomass_chp_fuel_input_year_kg,
        district_biogas_chp_fuel_input_year_nm3=district_biogas_chp_fuel_input_year_nm3,
        district_gas_chp_fuel_input_year_m3=district_gas_chp_fuel_input_year_m3,
    )

    lifetime = int(_require_key(params, "lifetime"))
    wacc = float_(econ["finance"]["wacc"])
    r_grid = float_(econ["finance"]["electricity_price_growth"])
    r_feed = float_(econ["finance"]["feedin_growth_rate"])
    r_ec = float_(econ["finance"]["ec_price_growth"])

    pv_repl = compute_pv_replacement(params)
    bess_repl = compute_bess_replacement(
        params,
        bess_kwh=float_(params.get("battery_capacity_kWh", 0.0)),
        annual_bess_throughput_kwh=float_(bess_throughput_year),
    )
    h2_trigger_repl = compute_fc_replacement(
        params,
        fc_kw=float_(params.get("fc_kw", 0.0)),
        annual_fc_output_kwh=float_(fc_output_year),
    )

    pv_repl_cost = _require_repl_factor("PV") * cost["capex_pv"]
    bess_repl_cost = _require_repl_factor("BESS") * cost["capex_batt"]
    h2_repl_bundle = cost["capex_ely"] + cost["capex_h2_tank"] + cost["capex_fc"] + cost["capex_comp"]
    h2_repl_cost = _require_repl_factor("H2_SYSTEM") * h2_repl_bundle

    npc = cost["total_capex"]
    for y in pv_repl.replacement_years:
        npc += pv_repl_cost / ((1 + wacc) ** float_(y))
    for y in bess_repl.replacement_years:
        npc += bess_repl_cost / ((1 + wacc) ** float_(y))
    for y in h2_trigger_repl.replacement_years:
        npc += h2_repl_cost / ((1 + wacc) ** float_(y))

    def _arr(key: str) -> np.ndarray:
        return np.asarray(flows_hourly.get(key, 0.0), dtype=float).reshape(-1)

    grid_import = _arr("grid_import")
    grid_export = _arr("grid_export")
    ec_import_pv = _arr("ec_import_from_pv")
    ec_import_ev = _arr("ec_import_from_ev")
    ec_export_pv = _arr("ec_export_from_pv")

    tariffs = market_bundle.tariffs
    p_imp_g = np.asarray(tariffs.grid_import_price, dtype=float).reshape(-1)
    p_exp_g = np.asarray(tariffs.grid_export_price, dtype=float).reshape(-1)
    p_imp_ec = np.asarray(tariffs.community_buy_price, dtype=float).reshape(-1)
    p_exp_ec = np.asarray(tariffs.community_sell_price, dtype=float).reshape(-1)

    n = len(grid_import)
    expected = (
        len(grid_export),
        len(ec_import_pv),
        len(ec_import_ev),
        len(ec_export_pv),
        len(p_imp_g),
        len(p_exp_g),
        len(p_imp_ec),
        len(p_exp_ec),
    )
    if any(v != n for v in expected):
        raise ValueError(f"[financial_model] Non-flat tariff calculation requires aligned hourly series; got lengths {(n, *expected)}.")

    annual_cost_import_grid = float(np.sum(grid_import * p_imp_g))
    annual_revenue_export_grid = float(np.sum(grid_export * p_exp_g))
    annual_cost_import_ec = float(np.sum((ec_import_pv + ec_import_ev) * p_imp_ec))
    annual_revenue_export_ec = float(np.sum(ec_export_pv * p_exp_ec))

    for y in range(1, lifetime + 1):
        annual_net = (
            annual_cost_import_grid * ((1 + r_grid) ** (y - 1))
            + annual_cost_import_ec * ((1 + r_ec) ** (y - 1))
            - annual_revenue_export_grid * ((1 + r_feed) ** (y - 1))
            - annual_revenue_export_ec * ((1 + r_ec) ** (y - 1))
            + cost["opex_annual"]
        )
        npc += annual_net / ((1 + wacc) ** y)

    return float(npc)
