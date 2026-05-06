from __future__ import annotations

import unittest

import numpy as np

from dispatch.modes.series_validation import dispatch_series_array, optional_dispatch_series


class DispatchSeriesValidationTest(unittest.TestCase):
    def test_rejects_short_explicit_series_instead_of_padding(self) -> None:
        with self.assertRaisesRegex(ValueError, "grid_import_price.*expected horizon 24, got 23"):
            dispatch_series_array(np.zeros(23), 24, label="grid_import_price")

    def test_rejects_long_explicit_series_instead_of_truncating(self) -> None:
        with self.assertRaisesRegex(ValueError, "co2_price_eur_per_tco2.*expected horizon 24, got 25"):
            dispatch_series_array(np.zeros(25), 24, label="co2_price_eur_per_tco2")

    def test_missing_optional_series_uses_explicit_length_matched_default(self) -> None:
        series = optional_dispatch_series({}, "district_heat_pump_cop", 4, default=1.0)

        np.testing.assert_allclose(series, np.ones(4))

    def test_present_optional_series_is_validated_before_defaulting(self) -> None:
        with self.assertRaisesRegex(ValueError, "district_heat_pump_cop.*expected horizon 4, got 1"):
            optional_dispatch_series({"district_heat_pump_cop": [2.5]}, "district_heat_pump_cop", 4, default=1.0)


if __name__ == "__main__":
    unittest.main()
