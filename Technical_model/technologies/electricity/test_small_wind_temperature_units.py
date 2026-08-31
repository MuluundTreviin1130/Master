"""Import-light guards for wind air-density temperature units."""

from __future__ import annotations

import unittest

import numpy as np

from Technical_model.technologies.electricity.small_wind import (
    require_temperature_celsius,
    simulate_small_wind_generation,
)


def _rated_kwargs(**overrides):
    payload = dict(
        installed_kw=10.0,
        wind_speed_ms=np.full(4, 12.0),
        reference_height_m=10.0,
        hub_height_m=10.0,
        shear_exponent=0.2,
        cut_in_ms=3.0,
        rated_ms=11.0,
        cut_out_ms=25.0,
        pressure_hpa=np.full(4, 1013.25),
        reference_air_density_kg_per_m3=1.225,
        dt_h=1.0,
    )
    payload.update(overrides)
    return payload


class SmallWindTemperatureUnitTests(unittest.TestCase):
    def test_celsius_ambient_keeps_near_reference_density_yield(self):
        # 15 °C is the ISO air-density reference; rated wind should stay near 10 kWh.
        gen = simulate_small_wind_generation(
            **_rated_kwargs(temperature_c=np.full(4, 15.0))
        )
        np.testing.assert_allclose(gen, np.full(4, 10.0), rtol=0.02)

    def test_kelvin_profile_as_celsius_is_rejected(self):
        # Vienna T_outdoor ≈ 280 K. Passing it as Celsius used to clip density to 0.5.
        with self.assertRaisesRegex(ValueError, "looks like Kelvin"):
            simulate_small_wind_generation(
                **_rated_kwargs(temperature_c=np.full(4, 280.15))
            )

    def test_require_temperature_celsius_accepts_winter_celsius(self):
        arr = require_temperature_celsius(np.array([-8.0, 1.5, 7.0]))
        np.testing.assert_allclose(arr, [-8.0, 1.5, 7.0])


if __name__ == "__main__":
    unittest.main()
