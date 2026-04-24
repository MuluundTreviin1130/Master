from __future__ import annotations


LOCATION_ECONOMICS = {
    "country_code": "PT",
    "finance": {
        "wacc": 0.08,
        "feedin_growth_rate": 0.01,
        "electricity_price_growth": 0.02,
        "ec_price_growth": 0.01,
    },
    "grid": {
        "buy_eur_per_kwh": 0.30,
        "feed_eur_per_kwh": 0.08,
    },
    "community": {
        "buy_eur_per_kwh": 0.29,
        "feed_eur_per_kwh": 0.08,
    },
    "technology": {
        "pv": {"capex_eur_per_kwp": 1100.0, "maintenance_rate": 0.01},
        "bess": {"capex_eur_per_kwh": 600.0, "maintenance_rate": 0.01},
        "ev": {
            "charge_capex_eur_per_unit": 2000.0,
            "v2h_capex_eur_per_unit": 2500.0,
            "maintenance_rate": 0.001,
        },
        "ely": {"capex_eur_per_kw": 3840.0, "maintenance_rate": 0.0},
        "h2_tank": {"capex_eur_per_kwh": 15.4, "maintenance_rate": 0.0},
        "fc": {"capex_eur_per_kw": 3000.0, "maintenance_rate": 0.0},
        "compressor": {"capex_eur_per_kw_ely": 4450.0, "maintenance_rate": 0.0},
        "small_wind": {"capex_eur_per_kw": 3600.0, "maintenance_rate": 0.03},
        "large_wind": {"capex_eur_per_kw": 1900.0, "maintenance_rate": 0.025},
        "biogas_engine": {"capex_eur_per_kw": 2550.0, "maintenance_rate": 0.05},
        "wood_gasifier": {
            "capex_eur_per_kw": 2250.0,
            "maintenance_rate": 0.045,
            "fuel_eur_per_kwh_fuel": 0.047,
        },
        "district_heat_pump": {"capex_eur_per_kw_th": 900.0, "maintenance_rate": 0.02},
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
            "note": "Explicit v1 reference assumption: external low-marginal-cost waste heat.",
        },
        "district_gas_boiler": {
            "capex_eur_per_kw_th": 60.0,
            "maintenance_rate": 0.0325,
            "fuel_eur_per_m3": 0.55,
            "co2_t_per_mwh_fuel": 0.202,
            "variable_opex_eur_per_kwh_th": 0.001,
            "source_note": "Danish Energy Agency Technology Data Catalogue for el and DH, gas-fired district heating boiler, 2020 sheet: 0.06 MEUR/MW_th nominal investment, 1,950 EUR/MW_th/year fixed O&M, 1.0 EUR/MWh_th other variable O&M.",
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
