import unittest

import numpy as np

from Data.profiles import loaders


class ProfileLoaderValidationTests(unittest.TestCase):
    def test_numeric_profile_array_rejects_non_numeric_cells(self):
        with self.assertRaisesRegex(ValueError, "non-finite/non-numeric"):
            loaders._numeric_profile_array([1.0, "broken", 3.0], "load-profile column 'A'")

    def test_unit_interval_profile_array_rejects_values_that_would_have_been_clipped(self):
        with self.assertRaisesRegex(ValueError, "outside \\[0, 1\\]"):
            loaders._unit_interval_profile_array([0.2, 1.2], "V2H availability")

    def test_profile_length_mismatch_fails_before_downstream_broadcasting(self):
        with self.assertRaisesRegex(ValueError, "length mismatch"):
            loaders._require_same_length(8760, "PV profile", np.zeros(8759))

    def test_v2h_availability_column_does_not_match_min_soc_header(self):
        columns = [
            "Hour",
            "PROSUMER WEEKDAY 2030 [%]",
            "STREET WEEKDAY 2030 [%]",
            "PASSENGER WEEKDAY [%]",
            "PASSENGER WEEKEND [%]",
            "PROSUMER WEEKDAY [%]",
            "PROSUMER WEEKEND [%]",
        ]

        self.assertEqual(
            loaders._matching_profile_column(columns, "prosumer weekday", exclude_substrs=("2030",)),
            "PROSUMER WEEKDAY [%]",
        )


if __name__ == "__main__":
    unittest.main()
