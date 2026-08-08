from __future__ import annotations

import unittest

import numpy as np

from dispatch.core.gas_boiler_fuel_price import (
    constant_fuel_price_eur_per_mwh_from_m3,
    resolve_gas_boiler_fuel_price_eur_per_mwh,
)


def _align(values, n: int) -> np.ndarray:
    arr = np.asarray(values, dtype=float).reshape(-1)
    if arr.size == n:
        return arr
    if arr.size == 1:
        return np.full(n, float(arr[0]), dtype=float)
    raise AssertionError(f"unexpected align size {arr.size} for n={n}")


class GasBoilerFuelPriceTests(unittest.TestCase):
    def test_vienna_mix_converts_from_gas_volume_equivalent_m3_price(self) -> None:
        # Mirror Data/economic_data/location/vienna.py active v2 mix:
        # 2/3 gas @ 55 EUR/MWh + 1/3 HEL @ BMWET 2023 average.
        gas_share = 2.0 / 3.0
        hel_share = 1.0 / 3.0
        hel_lhv_kwh_per_l = (0.841 * 42.5) / 3.6
        hel_eur_per_mwh = 1.2143 / (hel_lhv_kwh_per_l / 1000.0)
        mix_eur_per_mwh = (gas_share * 55.0) + (hel_share * hel_eur_per_mwh)
        mix_eur_per_m3 = mix_eur_per_mwh * (10.0 / 1000.0)
        price = constant_fuel_price_eur_per_mwh_from_m3(
            fuel_eur_per_m3=mix_eur_per_m3,
            fuel_lhv_kwh_per_m3=10.0,
            error_label="test",
        )
        self.assertAlmostEqual(price, mix_eur_per_mwh, places=9)
        self.assertGreater(price, 70.0)
        self.assertLess(price, 85.0)

    def test_resolve_prefers_explicit_boiler_series_over_gas_chp_series(self) -> None:
        series = {
            "district_gas_day_ahead_price_eur_per_mwh_fuel": np.array([55.0, 60.0]),
            "district_gas_boiler_day_ahead_price_eur_per_mwh_fuel": np.array([77.4, 77.4]),
        }
        params = {
            "district_gas_boiler_fuel_cost_eur_per_m3": 0.55,
            "district_gas_boiler_fuel_lhv_kwh_per_m3": 10.0,
        }
        resolved = resolve_gas_boiler_fuel_price_eur_per_mwh(
            series,
            params,
            n_steps=2,
            align_arr=_align,
            error_label="test",
        )
        np.testing.assert_allclose(resolved, np.array([77.4, 77.4]))

    def test_resolve_does_not_fall_back_to_gas_chp_day_ahead_price(self) -> None:
        series = {
            "district_gas_day_ahead_price_eur_per_mwh_fuel": np.array([55.0, 55.0]),
        }
        params = {
            "district_gas_boiler_fuel_cost_eur_per_m3": 0.774,
            "district_gas_boiler_fuel_lhv_kwh_per_m3": 10.0,
        }
        resolved = resolve_gas_boiler_fuel_price_eur_per_mwh(
            series,
            params,
            n_steps=2,
            align_arr=_align,
            error_label="test",
        )
        np.testing.assert_allclose(resolved, np.array([77.4, 77.4]))

    def test_resolve_fails_when_boiler_economics_missing(self) -> None:
        with self.assertRaises(ValueError):
            resolve_gas_boiler_fuel_price_eur_per_mwh(
                {"district_gas_day_ahead_price_eur_per_mwh_fuel": np.array([55.0])},
                {},
                n_steps=1,
                align_arr=_align,
                error_label="test",
            )


if __name__ == "__main__":
    unittest.main()
