"""Regression: hydrogen.fixed_system_eur must not pollute inactive/zero H2 NPC."""

from __future__ import annotations

import importlib.util
import sys
import types
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]


def _load_financial_model():
    """Import-light loader: avoid Data package __init__ (pandas) for unit tests."""

    if "Data" not in sys.modules:
        data_pkg = types.ModuleType("Data")
        data_pkg.__path__ = [str(REPO_ROOT / "Data")]
        sys.modules["Data"] = data_pkg
    if "Data.economic_data" not in sys.modules:
        econ_pkg = types.ModuleType("Data.economic_data")
        econ_pkg.__path__ = [str(REPO_ROOT / "Data" / "economic_data")]
        sys.modules["Data.economic_data"] = econ_pkg

    # financial_model imports replacement helpers; stub the assembly package.
    if "Data.assembly" not in sys.modules:
        assembly_pkg = types.ModuleType("Data.assembly")
        assembly_pkg.__path__ = [str(REPO_ROOT / "Data" / "assembly")]
        sys.modules["Data.assembly"] = assembly_pkg
    if "Data.assembly.replacements" not in sys.modules:
        replacements = types.ModuleType("Data.assembly.replacements")

        class _Repl:
            replacement_years = ()

        def _noop_repl(*_args, **_kwargs):
            return _Repl()

        replacements.compute_bess_replacement = _noop_repl
        replacements.compute_fc_replacement = _noop_repl
        replacements.compute_pv_replacement = _noop_repl
        sys.modules["Data.assembly.replacements"] = replacements

    if "Data.economic_data.replacement_costs" not in sys.modules:
        spec_rc = importlib.util.spec_from_file_location(
            "Data.economic_data.replacement_costs",
            REPO_ROOT / "Data" / "economic_data" / "replacement_costs.py",
        )
        assert spec_rc is not None and spec_rc.loader is not None
        rc = importlib.util.module_from_spec(spec_rc)
        sys.modules[spec_rc.name] = rc
        spec_rc.loader.exec_module(rc)

    spec = importlib.util.spec_from_file_location(
        "cost_model_financial_model",
        REPO_ROOT / "Cost_model" / "financial_model.py",
    )
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


def _minimal_economics(*, fixed_system_eur: float) -> dict:
    """Minimal economics block with required technology keys for CAPEX calc."""

    tech = {
        "pv": {"capex_eur_per_kwp": 1000.0, "maintenance_rate": 0.01},
        "bess": {"capex_eur_per_kwh": 500.0, "maintenance_rate": 0.01},
        "ev": {"charge_capex_eur_per_unit": 1000.0, "v2h_capex_eur_per_unit": 2000.0, "maintenance_rate": 0.01},
        "ely": {"capex_eur_per_kw": 1000.0, "maintenance_rate": 0.01},
        "h2_tank": {"capex_eur_per_kwh": 100.0, "maintenance_rate": 0.01},
        "fc": {"capex_eur_per_kw": 1000.0, "maintenance_rate": 0.01},
        "compressor": {"capex_eur_per_kw_ely": 100.0, "maintenance_rate": 0.01},
        "small_wind": {"capex_eur_per_kw": 1000.0, "maintenance_rate": 0.01},
        "large_wind": {"capex_eur_per_kw": 1000.0, "maintenance_rate": 0.01},
        "biogas_engine": {"capex_eur_per_kw": 1000.0, "maintenance_rate": 0.01},
        "wood_gasifier": {"capex_eur_per_kw": 1000.0, "maintenance_rate": 0.01, "fuel_eur_per_kwh_fuel": 0.05},
        "district_heat_pump": {"capex_eur_per_kw_th": 1000.0, "maintenance_rate": 0.01},
        "district_thermal_storage": {"capex_eur_per_kwh_th": 100.0, "maintenance_rate": 0.01},
        "district_wood_chip_boiler": {"capex_eur_per_kw_th": 100.0, "maintenance_rate": 0.01, "fuel_eur_per_kg": 0.1},
        "district_biomass_chp": {"capex_eur_per_kw_th": 1000.0, "maintenance_rate": 0.01, "fuel_eur_per_kg": 0.1},
        "district_external_heat": {"variable_opex_eur_per_kwh_th": 0.0},
        "district_gas_boiler": {
            "capex_eur_per_kw_th": 60.0,
            "maintenance_rate": 0.03,
            "fuel_eur_per_m3": 0.55,
            "variable_opex_eur_per_kwh_th": 0.0,
        },
        "district_biogas_chp": {"capex_eur_per_kw_el": 1000.0, "maintenance_rate": 0.01, "fuel_eur_per_nm3": 0.3},
        "district_gas_chp": {"capex_eur_per_kw_el": 1000.0, "maintenance_rate": 0.01, "fuel_eur_per_m3": 0.55},
        "district_geothermal": {"capex_eur_per_kw_el": 1000.0, "maintenance_rate": 0.01},
    }
    return {
        "technology": tech,
        "hydrogen": {
            "sec_kwh_per_kg_h2": 50.0,
            "h2_kwh_per_kg": 33.33,
            "energy_basis": "LHV",
            "fixed_system_eur": float(fixed_system_eur),
        },
        "finance": {
            "wacc": 0.05,
            "electricity_price_growth": 0.0,
            "feedin_growth_rate": 0.0,
            "ec_price_growth": 0.0,
        },
        "grid": {"buy_eur_per_kwh": 0.3, "feed_eur_per_kwh": 0.05},
        "community": {"buy_eur_per_kwh": 0.2, "feed_eur_per_kwh": 0.1},
    }


def _zero_capacity_params(*, fixed_system_eur: float) -> dict:
    return {
        "lifetime": 25,
        "economics": _minimal_economics(fixed_system_eur=fixed_system_eur),
        "pv_size": 0.0,
        "battery_capacity_kWh": 0.0,
        "ely_kw": 0.0,
        "h2_tank_kwh": 0.0,
        "fc_kw": 0.0,
        "small_wind_kw": 0.0,
        "large_wind_kw": 0.0,
        "biogas_engine_kw": 0.0,
        "wood_gasifier_kw": 0.0,
        "district_heat_pump_kw_th": 0.0,
        "district_thermal_storage_kwh_th": 0.0,
        "district_wood_chip_boiler_kw_th": 0.0,
        "district_biomass_chp_kw_th": 0.0,
        "district_gas_boiler_kw_th": 0.0,
        "district_geothermal_kw_el": 0.0,
        "district_gas_chp_kw_el": 0.0,
        "district_biogas_chp_kw_el": 0.0,
        "district_solar_thermal_kw_th": 0.0,
        "district_waste_incineration_kw_th": 0.0,
        "EV": {"N_EV_total": 0, "N_EV_bidirectional": 0},
    }


class TestH2FixedCapexActivation(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.fm = _load_financial_model()

    def test_zero_h2_capacity_does_not_charge_fixed_system_eur(self):
        fixed = 63800.0
        cost = self.fm._annualized_capex_and_opex(_zero_capacity_params(fixed_system_eur=fixed))
        self.assertEqual(cost["total_capex"], 0.0)

    def test_positive_h2_capacity_charges_fixed_system_eur(self):
        fixed = 63800.0
        params = _zero_capacity_params(fixed_system_eur=fixed)
        params["ely_kw"] = 1.0
        cost = self.fm._annualized_capex_and_opex(params)
        # 1 kW ely + compressor + fixed system
        expected_variable = (
            1000.0  # ely
            + 100.0  # compressor per kW_ely
        )
        self.assertEqual(cost["total_capex"], expected_variable + fixed)


if __name__ == "__main__":
    unittest.main()
