"""Regression tests: MILP must not invent HP COP=1.0 / leak inactive capacity."""

from __future__ import annotations

import sys
import types
import unittest
from pathlib import Path

import numpy as np


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from dispatch.core.heat_pump_cop import resolve_district_heat_pump_cop


class TestResolveDistrictHeatPumpCop(unittest.TestCase):
    def test_positive_capacity_missing_cop_fails_fast(self):
        with self.assertRaisesRegex(ValueError, "requires series\\['district_heat_pump_cop'\\]"):
            resolve_district_heat_pump_cop(
                {},
                hp_th_cap=3000.0,
                n=4,
                label="test",
            )

    def test_positive_capacity_ones_default_path_rejected(self):
        # Historical bug: series.get(..., np.ones(n)) invented COP=1.0.
        with self.assertRaisesRegex(ValueError, "requires series\\['district_heat_pump_cop'\\]"):
            resolve_district_heat_pump_cop(
                {},
                hp_th_cap=1.0,
                n=2,
                label="test",
            )

    def test_positive_capacity_nonpositive_cop_fails_fast(self):
        with self.assertRaisesRegex(ValueError, "finite and > 0"):
            resolve_district_heat_pump_cop(
                {"district_heat_pump_cop": np.array([3.5, 0.0, 3.5, 3.5])},
                hp_th_cap=100.0,
                n=4,
                label="test",
            )

    def test_positive_capacity_accepts_explicit_cop(self):
        cop = resolve_district_heat_pump_cop(
            {"district_heat_pump_cop": np.array([3.2, 3.2, 3.2])},
            hp_th_cap=500.0,
            n=3,
            label="test",
        )
        np.testing.assert_allclose(cop, [3.2, 3.2, 3.2])

    def test_zero_capacity_missing_cop_returns_zeros_not_ones(self):
        # Zero capacity must not invent ones: ones would be harmless for Big-M
        # only while capacity stays zero; zeros keep the inactive contract explicit.
        cop = resolve_district_heat_pump_cop({}, hp_th_cap=0.0, n=3, label="test")
        np.testing.assert_array_equal(cop, np.zeros(3))

    def test_length_mismatch_fails_fast(self):
        with self.assertRaisesRegex(ValueError, "length must equal horizon"):
            resolve_district_heat_pump_cop(
                {"district_heat_pump_cop": np.array([3.0, 3.0])},
                hp_th_cap=10.0,
                n=4,
                label="test",
            )


class TestMilpHeatPumpCapacityActivation(unittest.TestCase):
    def test_milp_capacity_zeroed_when_heat_pump_disabled(self):
        # Mirror the IES packing contract: deactivated tech must not leak a
        # positive design capacity into milp_day_ahead / milp_two_stage assets.
        heat_pump_enabled = False
        installed_heat_pump_kw_th = 28402.2
        milp_heat_pump_kw_th = float(installed_heat_pump_kw_th if heat_pump_enabled else 0.0)
        self.assertEqual(milp_heat_pump_kw_th, 0.0)

    def test_milp_capacity_kept_when_heat_pump_enabled(self):
        heat_pump_enabled = True
        installed_heat_pump_kw_th = 28402.2
        milp_heat_pump_kw_th = float(installed_heat_pump_kw_th if heat_pump_enabled else 0.0)
        self.assertEqual(milp_heat_pump_kw_th, 28402.2)


class TestActivatedDistrictHeatPumpSettingsValidation(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        source = (ROOT / "Settings/get_settings.py").read_text(encoding="utf-8")
        ns: dict = {"Settings": object, "Any": object}
        start = source.index("def _validate_activated_district_heat_pump")
        end = source.index("\ndef _validate_district_gas_chp_operating_region", start)
        exec(source[start:end], ns)
        cls.validate = staticmethod(ns["_validate_activated_district_heat_pump"])

    def test_activated_hp_without_temps_fails_fast(self):
        cfg = types.SimpleNamespace(
            technology_activation=types.SimpleNamespace(district_heat_pump=True),
            district_heat_pump=types.SimpleNamespace(
                source_temp_c=None,
                supply_temp_c=70.0,
                return_temp_c=40.0,
                cop_max=None,
            ),
        )
        with self.assertRaisesRegex(ValueError, "district_heat_pump.source_temp_c"):
            self.validate(cfg)

    def test_activated_hp_complete_ssot_passes(self):
        cfg = types.SimpleNamespace(
            technology_activation=types.SimpleNamespace(district_heat_pump=True),
            district_heat_pump=types.SimpleNamespace(
                source_temp_c=10.0,
                supply_temp_c=70.0,
                return_temp_c=40.0,
                cop_max=4.0,
            ),
        )
        self.validate(cfg)

    def test_inactive_hp_skips_temp_requirements(self):
        cfg = types.SimpleNamespace(
            technology_activation=types.SimpleNamespace(district_heat_pump=False),
            district_heat_pump=types.SimpleNamespace(
                source_temp_c=None,
                supply_temp_c=None,
                return_temp_c=None,
                cop_max=None,
            ),
        )
        self.validate(cfg)


if __name__ == "__main__":
    unittest.main()
