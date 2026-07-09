from __future__ import annotations

import unittest

import pandas as pd

from Learning.thermflex_hourly_mechanism.dataset_builder import _deduplicate_hourly_truth
from Learning.thermflex_hourly_mechanism.schema import TARGET_COLUMNS


def _row(bundle_name: str, *, q_delta: float) -> dict[str, object]:
    row: dict[str, object] = {
        "case_label": "display-label",
        "run_dir": "run-a",
        "cohort_key": "cohort-1",
        "timestamp": pd.Timestamp("2026-01-01 00:00:00"),
        "source_bundle_name": bundle_name,
        "source_hourly_csv": f"/tmp/{bundle_name}/hourly.csv",
    }
    for target in TARGET_COLUMNS:
        row[target] = 0.0
    row["cohort_q_delta_kwh"] = q_delta
    return row


class HourlyMechanismDedupTest(unittest.TestCase):
    def test_duplicate_truth_keeps_newest_bundle_timestamp_not_lexicographic_name(self) -> None:
        frame = pd.DataFrame(
            [
                _row("zz_old_20260101_000000", q_delta=1.0),
                _row("aa_new_20260201_000000", q_delta=2.0),
            ]
        )

        deduped = _deduplicate_hourly_truth(frame)

        self.assertEqual(len(deduped), 1)
        self.assertEqual(deduped["source_bundle_name"].iloc[0], "aa_new_20260201_000000")
        self.assertEqual(float(deduped["cohort_q_delta_kwh"].iloc[0]), 2.0)

    def test_duplicate_truth_without_timestamped_bundle_name_fails_fast(self) -> None:
        frame = pd.DataFrame(
            [
                _row("bundle_without_timestamp_a", q_delta=1.0),
                _row("bundle_without_timestamp_b", q_delta=2.0),
            ]
        )

        with self.assertRaises(ValueError):
            _deduplicate_hourly_truth(frame)

    def test_duplicate_truth_with_conflicting_newest_tie_fails_fast(self) -> None:
        frame = pd.DataFrame(
            [
                _row("newest_a_20260201_000000", q_delta=1.0),
                _row("newest_b_20260201_000000", q_delta=2.0),
            ]
        )

        with self.assertRaises(ValueError):
            _deduplicate_hourly_truth(frame)


if __name__ == "__main__":
    unittest.main()

