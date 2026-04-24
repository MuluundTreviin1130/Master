from __future__ import annotations

from copy import deepcopy

from .location import LOCATION_ECONOMICS


def _build_legacy_flat(location_cfg: dict) -> dict:
    economics = deepcopy(location_cfg)
    tech = economics["technology"]
    finance = economics["finance"]
    grid = economics["grid"]
    community = economics["community"]
    hydrogen = economics["hydrogen"]

    return {
        "country_code": economics["country_code"],
        "economics": economics,
        "CPV": tech["pv"]["capex_eur_per_kwp"],
        "CBESS": tech["bess"]["capex_eur_per_kwh"],
        "CEV": tech["ev"]["charge_capex_eur_per_unit"],
        "CEV_V2H": tech["ev"]["v2h_capex_eur_per_unit"],
        "Cbuy_grid": grid["buy_eur_per_kwh"],
        "Cfeed_grid": grid["feed_eur_per_kwh"],
        "Cbuy_community": community["buy_eur_per_kwh"],
        "Cfeed_community": community["feed_eur_per_kwh"],
        "Cbuy_community_PV": community["buy_eur_per_kwh"],
        "Cbuy_community_EV": community["buy_eur_per_kwh"],
        "Cfeed_community_PV": community["feed_eur_per_kwh"],
        "Cfeed_community_EV": community["feed_eur_per_kwh"],
        "C_ELY_EUR_PER_KW": tech["ely"]["capex_eur_per_kw"],
        "C_H2_TANK_EUR_PER_KWH": tech["h2_tank"]["capex_eur_per_kwh"],
        "C_FC_EUR_PER_KW": tech["fc"]["capex_eur_per_kw"],
        "C_COMP_EUR_PER_KW_ELY": tech["compressor"]["capex_eur_per_kw_ely"],
        "C_H2_FIXED_EUR": hydrogen["fixed_system_eur"],
        "C_SMALL_WIND_EUR_PER_KW": tech["small_wind"]["capex_eur_per_kw"],
        "C_LARGE_WIND_EUR_PER_KW": tech["large_wind"]["capex_eur_per_kw"],
        "C_BIOGAS_ENGINE_EUR_PER_KW": tech["biogas_engine"]["capex_eur_per_kw"],
        "C_WOOD_GASIFIER_EUR_PER_KW": tech["wood_gasifier"]["capex_eur_per_kw"],
        "C_WOOD_GASIFIER_FUEL_EUR_PER_KWH_FUEL": tech["wood_gasifier"]["fuel_eur_per_kwh_fuel"],
        "CHP": tech["district_gas_chp"]["capex_eur_per_kw_el"],
        "WACC": finance["wacc"],
        "feedin_growth_rate": finance["feedin_growth_rate"],
        "electricity_price_growth": finance["electricity_price_growth"],
        "ec_price_growth": finance["ec_price_growth"],
        "SEC_KWH_PER_KG_H2": hydrogen["sec_kwh_per_kg_h2"],
        "H2_KWH_PER_KG": hydrogen["h2_kwh_per_kg"],
        "H2_ENERGY_BASIS": hydrogen["energy_basis"],
    }


technologies_local = {
    location: _build_legacy_flat(cfg)
    for location, cfg in LOCATION_ECONOMICS.items()
}
