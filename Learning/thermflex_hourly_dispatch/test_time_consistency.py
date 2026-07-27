from __future__ import annotations

import unittest

import pandas as pd

from Learning.thermflex_hourly_dispatch.schema import validate_hourly_dispatch_time_consistency


class HourlyDispatchTimeConsistencyTests(unittest.TestCase):
    def test_date_mismatch_against_timestamp_fails(self) -> None:
        """
        Concrete trigger: a raw hourly CSV keeps date=Jan 15 / hour_index=6
        while timestamp points at Jan 16 06:00.

        Context enrichment would join Jan-16 weather/prices, but uniqueness,
        holdout grouping, and daily aggregation would still treat the row as
        Jan 15 hour 6.
        """

        frame = pd.DataFrame(
            {
                "date": ["2023-01-15"],
                "hour_index": [6],
                "timestamp": ["2023-01-16 06:00:00"],
            }
        )

        with self.assertRaisesRegex(ValueError, "date/hour_index disagree with timestamp"):
            validate_hourly_dispatch_time_consistency(frame, source_label="unit-test.csv")

    def test_hour_mismatch_against_timestamp_fails(self) -> None:
        frame = pd.DataFrame(
            {
                "date": ["2023-01-15"],
                "hour_index": [7],
                "timestamp": ["2023-01-15 06:00:00"],
            }
        )

        with self.assertRaisesRegex(ValueError, "date/hour_index disagree with timestamp"):
            validate_hourly_dispatch_time_consistency(frame, source_label="unit-test.csv")

    def test_out_of_range_hour_index_fails(self) -> None:
        frame = pd.DataFrame(
            {
                "date": ["2023-01-15"],
                "hour_index": [24],
                "timestamp": ["2023-01-15 00:00:00"],
            }
        )

        with self.assertRaisesRegex(ValueError, r"hour_index must be in \[0, 23\]"):
            validate_hourly_dispatch_time_consistency(frame, source_label="unit-test.csv")

    def test_consistent_time_keys_pass(self) -> None:
        frame = pd.DataFrame(
            {
                "date": ["2023-01-15", "2023-01-15"],
                "hour_index": [6, 7],
                "timestamp": ["2023-01-15 06:00:00", "2023-01-15 07:00:00"],
            }
        )

        validate_hourly_dispatch_time_consistency(frame, source_label="unit-test.csv")


if __name__ == "__main__":
    unittest.main()
