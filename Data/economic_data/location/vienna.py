from __future__ import annotations


# Explicit Vienna v2 fossil peak-boiler proxy.
# The active district_gas_boiler remains the single technical dispatch block for
# "Spitzenkessel + Heizzentralen", but its operational fuel pricing and direct
# CO2 intensity now include an explicit light-fuel-oil share. This keeps the
# runtime structure simple while moving the economics closer to the documented
# Vienna source picture ("Erdgas oder Heizoel extra leicht").
#
# Source anchors for the mixed-fuel proxy:
# - natural-gas benchmark already used in the repo:
#   0.55 EUR/m3 with the active DH benchmark fuel LHV 10.0 kWh/m3 -> 55 EUR/MWh_fuel
# - Austrian BMWET weekly 2023 "Heizoel Extraleicht: ab 2000 Liter" series:
#   annual average 1.2143 EUR/l
# - Statistik Austria goods-input conversion note:
#   Heizoel extra leicht density proxy = 0.841 kg/l
# - Heating-oil lower heating value proxy:
#   42.5 MJ/kg -> 11.8056 kWh/kg -> 9.9285 kWh/l
# - direct combustion CO2 factors:
#   natural gas = 0.202 tCO2/MWh_fuel (existing repo proxy),
#   light fuel oil proxy = 0.268 tCO2/MWh_fuel
#
# The mixed marginal fuel price is still stored in the existing
# `fuel_eur_per_m3` field because the current dispatch/financial path reads the
# fossil peak-boiler fuel cost on a gas-volume-equivalent basis. The explicit
# mix metadata below makes that conversion transparent instead of implicit.
_DISTRICT_GAS_PROXY_LHV_KWH_PER_M3 = 10.0
_DISTRICT_GAS_PROXY_PRICE_EUR_PER_MWH_FUEL = 55.0
_DISTRICT_GAS_PROXY_CO2_T_PER_MWH_FUEL = 0.202
_DISTRICT_PEAK_BOILER_HEL_SHARE = 1.0 / 3.0
_DISTRICT_PEAK_BOILER_GAS_SHARE = 1.0 - _DISTRICT_PEAK_BOILER_HEL_SHARE
_HEL_2023_AVG_PRICE_EUR_PER_L = 1.2143
_HEL_DENSITY_KG_PER_L = 0.841
_HEL_LHV_MJ_PER_KG = 42.5
_HEL_LHV_KWH_PER_L = (_HEL_DENSITY_KG_PER_L * _HEL_LHV_MJ_PER_KG) / 3.6
_HEL_PRICE_EUR_PER_MWH_FUEL = _HEL_2023_AVG_PRICE_EUR_PER_L / (_HEL_LHV_KWH_PER_L / 1000.0)
_HEL_CO2_T_PER_MWH_FUEL = 0.268
_DISTRICT_PEAK_BOILER_MIX_PRICE_EUR_PER_MWH_FUEL = (
    (_DISTRICT_PEAK_BOILER_GAS_SHARE * _DISTRICT_GAS_PROXY_PRICE_EUR_PER_MWH_FUEL)
    + (_DISTRICT_PEAK_BOILER_HEL_SHARE * _HEL_PRICE_EUR_PER_MWH_FUEL)
)
_DISTRICT_PEAK_BOILER_MIX_CO2_T_PER_MWH_FUEL = (
    (_DISTRICT_PEAK_BOILER_GAS_SHARE * _DISTRICT_GAS_PROXY_CO2_T_PER_MWH_FUEL)
    + (_DISTRICT_PEAK_BOILER_HEL_SHARE * _HEL_CO2_T_PER_MWH_FUEL)
)
_DISTRICT_PEAK_BOILER_MIX_PRICE_EUR_PER_M3_GAS_EQ = (
    _DISTRICT_PEAK_BOILER_MIX_PRICE_EUR_PER_MWH_FUEL * (_DISTRICT_GAS_PROXY_LHV_KWH_PER_M3 / 1000.0)
)


LOCATION_ECONOMICS = {
    "country_code": "AT",
    "finance": {
        "wacc": 0.08,
        "feedin_growth_rate": 0.0,
        "electricity_price_growth": 0.01,
        "ec_price_growth": 0.0,
    },
    "grid": {
        "buy_eur_per_kwh": 0.35,
        "feed_eur_per_kwh": 0.10,
    },
    "community": {
        "buy_eur_per_kwh": 0.15,
        "feed_eur_per_kwh": 0.15,
    },
    "technology": {
        "pv": {"capex_eur_per_kwp": 1000.0, "maintenance_rate": 0.01},
        "bess": {"capex_eur_per_kwh": 450.0, "maintenance_rate": 0.01},
        "ev": {
            "charge_capex_eur_per_unit": 0.0,
            "v2h_capex_eur_per_unit": 0.0,
            "maintenance_rate": 0.001,
        },
        "ely": {"capex_eur_per_kw": 3840.0, "maintenance_rate": 0.0},
        "h2_tank": {"capex_eur_per_kwh": 15.4, "maintenance_rate": 0.0},
        "fc": {"capex_eur_per_kw": 3000.0, "maintenance_rate": 0.0},
        "compressor": {"capex_eur_per_kw_ely": 4450.0, "maintenance_rate": 0.0},
        "small_wind": {"capex_eur_per_kw": 3500.0, "maintenance_rate": 0.03},
        "large_wind": {"capex_eur_per_kw": 1800.0, "maintenance_rate": 0.025},
        "biogas_engine": {"capex_eur_per_kw": 2500.0, "maintenance_rate": 0.05},
        "wood_gasifier": {
            "capex_eur_per_kw": 2200.0,
            "maintenance_rate": 0.045,
            "fuel_eur_per_kwh_fuel": 0.045,
        },
        "district_heat_pump": {
            "capex_eur_per_kw_th": 900.0,
            "maintenance_rate": 0.02,
            "note": "Current Vienna DH-HP economics are still a generic proxy. For the Vienna reference case, the source side is interpreted as Danube/seawater and should later be remapped to a dedicated seawater heat-pump catalogue case.",
        },
        "district_thermal_storage": {"capex_eur_per_kwh_th": 40.0, "maintenance_rate": 0.01},
        "district_wood_chip_boiler": {
            "capex_eur_per_kw_th": 550.0,
            "maintenance_rate": 0.03,
            "fuel_eur_per_kg": 0.12,
        },
        "district_biomass_chp": {
            "capex_eur_per_kw_th": 2200.0,
            "maintenance_rate": 0.04,
            "fuel_eur_per_kg": 0.12,
        },
        "district_external_heat": {
            "variable_opex_eur_per_kwh_th": 0.0,
            "note": "Explicit v1 reference assumption: industrial waste heat / Bezug Abwaerme dispatched as must-take low-marginal-cost heat.",
        },
        "district_gas_boiler": {
            "capex_eur_per_kw_th": 60.0,
            "maintenance_rate": 0.0325,
            "fuel_mix_mode": "gas_plus_heating_oil_extra_light_proxy",
            "fuel_mix_gas_share": _DISTRICT_PEAK_BOILER_GAS_SHARE,
            "fuel_mix_heating_oil_extra_light_share": _DISTRICT_PEAK_BOILER_HEL_SHARE,
            "gas_proxy_fuel_eur_per_mwh_fuel": _DISTRICT_GAS_PROXY_PRICE_EUR_PER_MWH_FUEL,
            "gas_proxy_co2_t_per_mwh_fuel": _DISTRICT_GAS_PROXY_CO2_T_PER_MWH_FUEL,
            "heating_oil_extra_light_avg_2023_eur_per_l": _HEL_2023_AVG_PRICE_EUR_PER_L,
            "heating_oil_extra_light_lhv_kwh_per_l": _HEL_LHV_KWH_PER_L,
            "heating_oil_extra_light_fuel_eur_per_mwh_fuel": _HEL_PRICE_EUR_PER_MWH_FUEL,
            "heating_oil_extra_light_co2_t_per_mwh_fuel": _HEL_CO2_T_PER_MWH_FUEL,
            "fuel_eur_per_m3": _DISTRICT_PEAK_BOILER_MIX_PRICE_EUR_PER_M3_GAS_EQ,
            "co2_t_per_mwh_fuel": _DISTRICT_PEAK_BOILER_MIX_CO2_T_PER_MWH_FUEL,
            "variable_opex_eur_per_kwh_th": 0.001,
            "source_note": "Danish Energy Agency Technology Data Catalogue for el and DH, gas-fired district heating boiler, 2020 sheet: 0.06 MEUR/MW_th nominal investment, 1,950 EUR/MW_th/year fixed O&M, 1.0 EUR/MWh_th other variable O&M.",
            "fuel_note": "fuel_eur_per_m3 is now a gas-volume-equivalent proxy for an explicit Vienna fossil peak-boiler fuel mix. Active v2 benchmark uses 2/3 gas + 1/3 Heizoel extra leicht on a fuel-energy basis; see Documentation/Sources/dh_economics_quellen.md.",
            "co2_note": "Direct combustion factor for ETS-style operational CO2 costing, not an LCA factor. Active v2 benchmark uses an explicit gas/oil mix and therefore raises the fossil peak-boiler default above the pure-gas proxy.",
        },
        "district_biogas_chp": {
            "capex_eur_per_kw_el": 2500.0,
            "maintenance_rate": 0.05,
            "fuel_eur_per_nm3": 0.35,
        },
        "district_gas_chp": {
            "capex_eur_per_kw_el": 1400.0,
            "maintenance_rate": 0.04,
            "fuel_eur_per_m3": 0.55,
            "co2_t_per_mwh_fuel": 0.202,
        },
        "district_geothermal": {"capex_eur_per_kw_el": 5000.0, "maintenance_rate": 0.03},
        "district_solar_thermal": {
            "validated": False,
            "note": "Pending validated solar-thermal economics SSOT.",
        },
        "district_waste_incineration": {
            "validated": False,
            "note": "Pending validated waste-incineration economics SSOT.",
        },
    },
    "hydrogen": {
        "sec_kwh_per_kg_h2": 50.0,
        "h2_kwh_per_kg": 33.33,
        "energy_basis": "LHV",
        "fixed_system_eur": 63800.0,
    },
}
