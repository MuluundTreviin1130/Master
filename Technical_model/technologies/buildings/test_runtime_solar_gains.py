from __future__ import annotations

import unittest

import numpy as np

from Technical_model.technologies.buildings.runtime_space_heat import (
    build_live_hvac_solar_gains_member_2d,
    resolve_runtime_solar_gains_w_per_m2,
)


class _ThermalCfg:
    runtime_solar_gains_mode = "irradiance_window_transmission"
    runtime_solar_frame_fraction = 0.3
    runtime_solar_shading_factor = 0.6
    runtime_solar_non_perpendicular_factor = 0.9


class _LegacyThermalCfg(_ThermalCfg):
    runtime_solar_gains_mode = "legacy_solargains_profile"


def _residential_building_params() -> dict:
    # TABULA-like Vienna residential window/floor ratio used by the default stock.
    window_area = 0.18 * 100.0
    quarter = window_area / 4.0
    return {
        "A_floor": 100.0,
        "window_area_total_m2": window_area,
        "window_g_value": 0.6,
        "g_glazing": 0.6,
        "A_window": {"south": quarter, "east": quarter, "west": quarter, "north": quarter},
        "solar_multipliers": {"south": 1.0, "east": 0.2, "west": 0.2, "north": 0.0},
    }


class RuntimeSolarGainsTests(unittest.TestCase):
    def test_irradiance_mode_is_much_smaller_than_legacy_vienna_scale(self) -> None:
        # Vienna files: legacy solar-gains mean ~9.6 W/m2, global irradiance mean ~171 W/m2.
        # The settings default is irradiance_window_transmission, not the legacy file.
        n = 24
        legacy = np.full(n, 9.6, dtype=float)
        irradiance = np.full(n, 171.5, dtype=float)
        resolved = resolve_runtime_solar_gains_w_per_m2(
            legacy_solar_gains_w_m2=legacy,
            irradiance_w_m2=irradiance,
            building_params=_residential_building_params(),
            thermal_cfg=_ThermalCfg(),
        )
        self.assertEqual(resolved.shape, (n,))
        self.assertTrue(np.all(resolved < 4.0))
        self.assertGreater(float(np.mean(legacy)), 3.0 * float(np.mean(resolved)))

    def test_legacy_mode_keeps_the_explicit_solargains_profile(self) -> None:
        legacy = np.array([0.0, 12.5, 8.0], dtype=float)
        resolved = resolve_runtime_solar_gains_w_per_m2(
            legacy_solar_gains_w_m2=legacy,
            irradiance_w_m2=np.array([0.0, 800.0, 400.0], dtype=float),
            building_params=_residential_building_params(),
            thermal_cfg=_LegacyThermalCfg(),
        )
        np.testing.assert_allclose(resolved, legacy)

    def test_live_hvac_helper_reuses_precompute_member_axis(self) -> None:
        cached = np.array([[1.0, 2.0], [3.0, 4.0]], dtype=float)
        out = build_live_hvac_solar_gains_member_2d(
            profiles={"space_heat_solar_member_2d": cached, "solargains": np.ones(2)},
            members=None,
            settings_obj=None,
            n_steps=2,
            n_members=2,
        )
        np.testing.assert_allclose(out, cached)

    def test_live_hvac_helper_fails_fast_without_members_or_cache(self) -> None:
        with self.assertRaises(ValueError):
            build_live_hvac_solar_gains_member_2d(
                profiles={"solargains": np.ones(4), "irradiance": np.ones(4)},
                members=None,
                settings_obj=type("S", (), {"thermal": _ThermalCfg()})(),
                n_steps=4,
                n_members=1,
            )


if __name__ == "__main__":
    unittest.main()
