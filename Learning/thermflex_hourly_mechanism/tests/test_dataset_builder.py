from __future__ import annotations

import unittest

import pandas as pd

from Learning.thermflex_hourly_mechanism.dataset_builder import _deduplicate_hourly_truth


class HourlyMechanismDeduplicationTest(unittest.TestCase):
    def test_keeps_newest_timestamped_bundle_not_lexicographically_largest_name(self) -> None:
        timestamp = pd.Timestamp("2026-01-15 12:00:00")
        frame = pd.DataFrame(
            [
                {
                    "case_label": "same_case",
                    "run_dir": "same_run",
                    "cohort_key": "cohort_a",
                    "timestamp": timestamp,
                    "source_bundle_name": "z_older_bundle_20260101_000000",
                    "kept_value": "older",
                },
                {
                    "case_label": "same_case",
                    "run_dir": "same_run",
                    "cohort_key": "cohort_a",
                    "timestamp": timestamp,
                    "source_bundle_name": "a_newer_bundle_20260201_000000",
                    "kept_value": "newer",
                },
            ]
        )

        deduped = _deduplicate_hourly_truth(frame)

        self.assertEqual(len(deduped), 1)
        self.assertEqual(str(deduped["kept_value"].iloc[0]), "newer")


if __name__ == "__main__":
    unittest.main()
