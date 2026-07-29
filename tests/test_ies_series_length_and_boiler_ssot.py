"""Regression tests for silent IES series pad/truncate and boiler SSOT gaps."""

from __future__ import annotations

import sys
import types
import unittest
from pathlib import Path

import numpy as np


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def _load_ies_helpers():
    """Load selected IES helpers without importing the full technology stack."""

    source = (ROOT / "Technical_model/energy_system/systems/integrated_energy_system.py").read_text(
        encoding="utf-8"
    )
    ns: dict = {"np": np, "Any": object, "Dict": dict, "List": list}

    def _exec_between(start_marker: str, end_marker: str) -> None:
        start = source.index(start_marker)
        end = source.index(end_marker, start)
        exec(source[start:end], ns)

    _exec_between("def _align_1d_length", "\ndef _to_celsius_if_kelvin")
    _exec_between("def _fuel_price_series_eur_per_mwh", "\ndef _optional_price_series_eur_per_mwh")
    _exec_between("def _require_float_attr", "\ndef _district_gas_chp_piecewise_payload")
    return types.SimpleNamespace(**ns)


class TestSeriesLengthContracts(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from Data.profiles.loaders import _coerce_wind_profile_to_horizon, _require_profile_length

        cls.require_profile_length = staticmethod(_require_profile_length)
        cls.coerce_wind = staticmethod(_coerce_wind_profile_to_horizon)
        cls.ies = _load_ies_helpers()

    def test_align_rejects_short_and_long_series(self):
        with self.assertRaisesRegex(ValueError, "length mismatch"):
            self.ies._align_1d_length(np.linspace(30.0, 80.0, 23), 24)
        with self.assertRaisesRegex(ValueError, "length mismatch"):
            self.ies._align_1d_length(np.linspace(30.0, 100.0, 25), 24)
        exact = np.arange(24, dtype=float)
        np.testing.assert_array_equal(self.ies._align_1d_length(exact, 24), exact)

    def test_wind_allows_only_single_endpoint_extra(self):
        base = np.arange(24, dtype=float)
        np.testing.assert_array_equal(
            self.ies._require_wind_series(np.concatenate([base, [99.0]]), 24, label="wind_speed_ms"),
            base,
        )
        with self.assertRaisesRegex(ValueError, "Wind profile"):
            self.ies._require_wind_series(np.arange(22, dtype=float), 24, label="wind_speed_ms")

    def test_loader_wind_endpoint_and_strict_profiles(self):
        base = np.arange(24, dtype=float)
        np.testing.assert_array_equal(
            self.coerce_wind(np.concatenate([base, [1.0]]), 24, label="wind_speed_ms"),
            base,
        )
        with self.assertRaisesRegex(ValueError, "Profile 'pv_generation'"):
            self.require_profile_length(np.arange(23), 24, label="pv_generation")

    def test_fuel_price_fallback_requires_explicit_lhv(self):
        with self.assertRaisesRegex(ValueError, "fuel LHV is None"):
            self.ies._fuel_price_series_eur_per_mwh(
                {},
                profile_key="district_gas_day_ahead_price_eur_per_mwh_fuel",
                fallback_eur_per_m3=0.55,
                lhv_kwh_per_m3=None,
                n_steps=24,
            )
        series = self.ies._fuel_price_series_eur_per_mwh(
            {},
            profile_key="district_gas_day_ahead_price_eur_per_mwh_fuel",
            fallback_eur_per_m3=0.55,
            lhv_kwh_per_m3=10.0,
            n_steps=4,
        )
        np.testing.assert_allclose(series, np.full(4, 0.55 * 1000.0 / 10.0))

    def test_active_boiler_milp_scalars_fail_on_none(self):
        cfg = types.SimpleNamespace(
            eta_th=None,
            min_partload=0.0,
            max_partload=1.0,
            fuel_lhv_kwh_per_m3=10.0,
        )
        with self.assertRaisesRegex(ValueError, "must not be None"):
            self.ies._active_boiler_milp_scalars(
                cfg,
                active=True,
                tech_name="district_gas_boiler",
                lhv_settings_attr="fuel_lhv_kwh_per_m3",
            )
        inactive = self.ies._active_boiler_milp_scalars(
            cfg,
            active=False,
            tech_name="district_gas_boiler",
            lhv_settings_attr="fuel_lhv_kwh_per_m3",
        )
        self.assertEqual(inactive["eta_th"], 0.0)
        self.assertEqual(inactive["fuel_lhv"], 0.0)


class TestActivatedBoilerSettingsValidation(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        source = (ROOT / "Settings/get_settings.py").read_text(encoding="utf-8")
        ns: dict = {"Settings": object, "Any": object, "Dict": dict}

        def _require_positive_float(value, *, label: str) -> float:
            if value is None:
                raise ValueError(f"[settings] {label} must not be None.")
            value_f = float(value)
            if value_f <= 0.0:
                raise ValueError(f"[settings] {label} must be > 0, got {value_f}.")
            return value_f

        ns["_require_positive_float"] = _require_positive_float
        start = source.index("def _validate_activated_district_boilers")
        end = source.index("\ndef _validate_dispatch_objective_components", start)
        exec(source[start:end], ns)
        cls.validate = staticmethod(ns["_validate_activated_district_boilers"])

    def test_activated_gas_boiler_without_eta_fails_fast(self):
        cfg = types.SimpleNamespace(
            technology_activation=types.SimpleNamespace(district_gas_boiler=True, district_wood_chip_boiler=False),
            district_gas_boiler=types.SimpleNamespace(
                installed_kw_th_fixed=1000.0,
                min_partload=0.0,
                max_partload=1.0,
                eta_th=None,
                fuel_lhv_kwh_per_m3=10.0,
            ),
            district_wood_chip_boiler=None,
        )
        with self.assertRaisesRegex(ValueError, "district_gas_boiler.eta_th"):
            self.validate(cfg)

    def test_activated_gas_boiler_with_complete_ssot_passes(self):
        cfg = types.SimpleNamespace(
            technology_activation=types.SimpleNamespace(district_gas_boiler=True, district_wood_chip_boiler=False),
            district_gas_boiler=types.SimpleNamespace(
                installed_kw_th_fixed=1000.0,
                min_partload=0.0,
                max_partload=1.0,
                eta_th=0.9,
                fuel_lhv_kwh_per_m3=10.0,
            ),
            district_wood_chip_boiler=None,
        )
        self.validate(cfg)
        self.assertEqual(float(cfg.district_gas_boiler.eta_th), 0.9)


if __name__ == "__main__":
    unittest.main()
