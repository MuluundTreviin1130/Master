"""Import-light guards for two-stage HDD temperature units.

Loads ``hdd.py`` by file path so the test does not import
``dispatch.scenarios`` (pandas / weather IO).
"""

from __future__ import annotations

import importlib.util
import unittest
from pathlib import Path

import numpy as np


def _load_hdd():
    path = Path(__file__).resolve().parent / "hdd.py"
    spec = importlib.util.spec_from_file_location("dispatch_scenarios_hdd", path)
    if spec is None or spec.loader is None:
        raise ImportError(f"Cannot load HDD helper from {path}")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


_hdd = _load_hdd()


class HistoricalHddTemperatureUnitTests(unittest.TestCase):
    def test_celsius_winter_hours_produce_positive_hdd(self):
        # 0 °C vs a 15 °C base must yield 15 K·h, not a silent 1.0 DH factor.
        hdd = _hdd.heating_degree_hours(np.array([0.0, 5.0, 15.0, 20.0]), ctx="test")
        np.testing.assert_allclose(hdd, [15.0, 10.0, 0.0, 0.0])
        self.assertEqual(_hdd.HEATING_DEGREE_BASE_C, 15.0)

    def test_kelvin_base_series_is_rejected(self):
        # IES used to forward T_outdoor Kelvin as ambient_temperature_c.
        # Then 15 − 280 < 0 for every hour and every scenario DH factor became 1.0.
        with self.assertRaisesRegex(ValueError, "looks like Kelvin"):
            _hdd.require_ambient_temperature_c(np.full(24, 280.15), ctx="base dispatch day")

    def test_colder_scenario_raises_hdd_ratio(self):
        base = _hdd.heating_degree_hours(np.full(4, 5.0), ctx="base")
        colder = _hdd.heating_degree_hours(np.full(4, -5.0), ctx="scenario")
        ratio = colder / base
        np.testing.assert_allclose(ratio, np.full(4, 2.0))


if __name__ == "__main__":
    unittest.main()
