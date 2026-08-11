"""Import-light tests for technology_activation → DH design-bound gating.

Concrete bug locked here:
- Default ``technology_activation.*=False`` previously left central DH scaffold
  uppers open (e.g. heat pump ``0..7500``).
- Gold/teacher sampling could therefore write positive inactive capacities into
  ``params``, so ``financial_model`` charged CAPEX while IES never dispatched
  those assets → corrupted NPC / truth labels.
"""

from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace


def _load_bounds_module():
    """Load ``Settings/problem/bounds.py`` without importing the Settings package."""
    path = Path(__file__).resolve().parents[1] / "Settings" / "problem" / "bounds.py"
    name = "test_bounds_technology_activation_mod"
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Unable to load bounds module from {path}")
    mod = importlib.util.module_from_spec(spec)
    # dataclasses need the module registered before exec_module.
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


BOUNDS = _load_bounds_module()

_DH_BOUND_NAMES = (
    "district_heat_pump_kw_th",
    "district_thermal_storage_kwh_th",
    "district_wood_chip_boiler_kw_th",
    "district_biomass_chp_kw_th",
    "district_geothermal_kw_el",
    "district_gas_chp_kw_el",
    "district_biogas_chp_kw_el",
)


def _engine_with_default_features():
    return SimpleNamespace(
        N_EC=10,
        features=SimpleNamespace(
            enable_bess=True,
            enable_h2=False,
            enable_small_wind=False,
            enable_large_wind=False,
            enable_biogas_engine=False,
            enable_wood_gasifier=False,
        ),
    )


def _activation(**overrides):
    base = {
        "district_heat_pump": False,
        "district_thermal_storage": False,
        "district_wood_chip_boiler": False,
        "district_biomass_chp": False,
        "district_geothermal": False,
        "district_gas_chp": False,
        "district_biogas_chp": False,
    }
    base.update(overrides)
    return SimpleNamespace(**base)


def _upper(bounds, name: str) -> float:
    return float(bounds.upper[bounds.names.index(name)])


class TechnologyActivationBoundsTests(unittest.TestCase):
    def test_make_bounds_still_opens_dh_scaffold_before_activation_clamp(self):
        """Scaffold remains positive so activation ON can size assets later."""
        bounds = BOUNDS.make_bounds(_engine_with_default_features())
        self.assertGreater(_upper(bounds, "district_heat_pump_kw_th"), 0.0)
        self.assertGreater(_upper(bounds, "district_thermal_storage_kwh_th"), 0.0)

    def test_default_inactive_activation_collapses_all_central_dh_bounds(self):
        """Default False activation must zero every central DH decision variable."""
        bounds = BOUNDS.make_bounds(_engine_with_default_features())
        BOUNDS.apply_technology_activation_bounds(_activation(), bounds)
        for name in _DH_BOUND_NAMES:
            with self.subTest(name=name):
                i = bounds.names.index(name)
                self.assertEqual(float(bounds.lower[i]), 0.0)
                self.assertEqual(float(bounds.upper[i]), 0.0)

    def test_active_heat_pump_keeps_upper_while_siblings_collapse(self):
        """Only the activated technology may keep a positive design upper."""
        bounds = BOUNDS.make_bounds(_engine_with_default_features())
        scaffold_hp = _upper(bounds, "district_heat_pump_kw_th")
        BOUNDS.apply_technology_activation_bounds(
            _activation(district_heat_pump=True),
            bounds,
        )
        self.assertEqual(_upper(bounds, "district_heat_pump_kw_th"), scaffold_hp)
        self.assertEqual(_upper(bounds, "district_thermal_storage_kwh_th"), 0.0)
        self.assertEqual(_upper(bounds, "district_gas_chp_kw_el"), 0.0)

    def test_activation_clamp_overrides_positive_manual_upper(self):
        """Inactive clamp must win after manual/potential/override reopen attempts."""
        bounds = BOUNDS.make_bounds(_engine_with_default_features())
        i = bounds.names.index("district_heat_pump_kw_th")
        bounds.upper[i] = 1234.0
        BOUNDS.apply_technology_activation_bounds(
            _activation(district_heat_pump=False),
            bounds,
        )
        self.assertEqual(float(bounds.upper[i]), 0.0)


if __name__ == "__main__":
    unittest.main()
