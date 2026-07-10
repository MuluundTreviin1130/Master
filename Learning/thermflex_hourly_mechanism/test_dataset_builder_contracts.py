from __future__ import annotations

import unittest

import pandas as pd

from Learning.thermflex_hourly_mechanism.dataset_builder import _deduplicate_hourly_truth


def _truth_row(
    *,
    source_bundle_name: str,
    cohort_q_delta_kwh: float,
    case_label: str = "case_a",
) -> dict[str, object]:
    return {
        "case_label": case_label,
        "run_dir": "run_001",
        "cohort_key": "cohort_a",
        "timestamp": pd.Timestamp("2026-01-01 00:00:00"),
        "source_bundle_name": source_bundle_name,
        "source_hourly_csv": f"/tmp/{source_bundle_name}/thermflex_cohort_utilization_hourly.csv",
        "cohort_q_delta_kwh": cohort_q_delta_kwh,
    }


class HourlyTruthDedupeContractTest(unittest.TestCase):
    def test_keeps_newest_timestamped_bundle_not_lexicographic_last(self) -> None:
        frame = pd.DataFrame(
            [
                _truth_row(
                    source_bundle_name="z_old_prefix_20260101_000000",
                    cohort_q_delta_kwh=1.0,
                ),
                _truth_row(
                    source_bundle_name="a_new_prefix_20260201_000000",
                    cohort_q_delta_kwh=2.0,
                ),
            ]
        )

        deduped = _deduplicate_hourly_truth(frame)

        self.assertEqual(len(deduped), 1)
        self.assertEqual(deduped.loc[0, "source_bundle_name"], "a_new_prefix_20260201_000000")
        self.assertEqual(float(deduped.loc[0, "cohort_q_delta_kwh"]), 2.0)

    def test_rejects_overlapping_unranked_bundles(self) -> None:
        frame = pd.DataFrame(
            [
                _truth_row(source_bundle_name="legacy_bundle_without_timestamp_a", cohort_q_delta_kwh=1.0),
                _truth_row(source_bundle_name="legacy_bundle_without_timestamp_b", cohort_q_delta_kwh=2.0),
            ]
        )

        with self.assertRaisesRegex(ValueError, "timestamped source bundles"):
            _deduplicate_hourly_truth(frame)

    def test_rejects_conflicting_tied_newest_labels(self) -> None:
        frame = pd.DataFrame(
            [
                _truth_row(source_bundle_name="bundle_a_20260201_000000", cohort_q_delta_kwh=1.0),
                _truth_row(source_bundle_name="bundle_b_20260201_000000", cohort_q_delta_kwh=2.0),
            ]
        )

        with self.assertRaisesRegex(ValueError, "conflicting labels"):
            _deduplicate_hourly_truth(frame)


if __name__ == "__main__":
    unittest.main()
