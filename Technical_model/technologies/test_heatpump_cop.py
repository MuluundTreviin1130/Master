from __future__ import annotations

import unittest

import numpy as np

from Technical_model.technologies.heatpump_cop import resolve_household_heatpump_cop_series


# Mirrors Data/technology_data/heatpump.py without importing Data.
_VIENNA_HP = {
    "T_flow": 303.15,
    "T_flow_cool": 290.15,
    "eta_cop": 0.2,
    "cop_max": 5.0,
    "eer_max": 5.0,
}


class HeatpumpCopContractTests(unittest.TestCase):
    def test_winter_operating_cop_is_below_cop_max(self) -> None:
        # Vienna winter outdoor air is Kelvin (~2 °C).
        t_out_k = np.full(24, 275.15, dtype=float)
        cop_heat, cop_cool = resolve_household_heatpump_cop_series(
            heatpump=_VIENNA_HP,
            t_outdoor_k=t_out_k,
        )
        expected = 0.2 * 303.15 / (303.15 - 275.15)
        self.assertTrue(np.allclose(cop_heat, expected))
        self.assertLess(float(cop_heat[0]), float(_VIENNA_HP["cop_max"]))
        self.assertGreater(float(_VIENNA_HP["cop_max"]) / float(cop_heat[0]), 2.0)
        # Outdoor colder than the cooling setpoint => cooling COP floor.
        self.assertTrue(np.allclose(cop_cool, 1.0))

    def test_celsius_outdoor_fail_fast(self) -> None:
        with self.assertRaises(ValueError) as ctx:
            resolve_household_heatpump_cop_series(
                heatpump=_VIENNA_HP,
                t_outdoor_k=np.full(8, 2.0, dtype=float),
            )
        self.assertIn("Celsius", str(ctx.exception))

    def test_missing_eta_cop_fail_fast(self) -> None:
        hp = dict(_VIENNA_HP)
        del hp["eta_cop"]
        with self.assertRaises(ValueError) as ctx:
            resolve_household_heatpump_cop_series(
                heatpump=hp,
                t_outdoor_k=np.full(4, 280.15, dtype=float),
            )
        self.assertIn("eta_cop", str(ctx.exception))

    def test_cop_max_is_a_cap_not_the_operating_value(self) -> None:
        # Very large temperature lift keeps COP below the cap; a tiny lift
        # saturates at cop_max. Both paths must use eta_cop, not cop_max alone.
        cold = resolve_household_heatpump_cop_series(
            heatpump=_VIENNA_HP,
            t_outdoor_k=np.array([255.15], dtype=float),
        )[0][0]
        mild = resolve_household_heatpump_cop_series(
            heatpump=_VIENNA_HP,
            t_outdoor_k=np.array([301.15], dtype=float),
        )[0][0]
        self.assertLess(float(cold), 5.0)
        self.assertAlmostEqual(float(mild), 5.0)


if __name__ == "__main__":
    unittest.main()
