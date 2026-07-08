from __future__ import annotations

import unittest

import pandas as pd

from Learning.thermflex_hourly_mechanism.dataset_builder import _deduplicate_hourly_truth
from Learning.thermflex_hourly_mechanism.schema import REQUIRED_HOURLY_MECHANISM_COLUMNS


def _base_truth_row(*, bundle: str, q_delta: float = 1.5) -> dict[str, object]:
    row: dict[str, object] = {
        "case_label": "case-a",
        "run_dir": "/tmp/run-a",
        "timestamp": pd.Timestamp("2026-01-01T00:00:00"),
        "cohort_key": "res_pre1975",
        "cohort_member_count": 10,
        "cohort_floor_area_m2": 1000.0,
        "thermflex_constant_lower_bound_c": 21.5,
        "thermflex_max_flex_duration_h": 4,
        "thermflex_max_events_per_day": 24,
        "cohort_q_heat_kwh": 100.0,
        "cohort_q_heat_ref_kwh": 98.5,
        "cohort_q_delta_kwh": q_delta,
        "cohort_flex_active_member_count": 8,
        "cohort_flex_active_member_share": 0.8,
        "cohort_event_start_count": 2,
        "cohort_temperature_violation_degree_h": 0.0,
        "cohort_t_in_weighted_mean_c": 21.0,
        "cohort_t_in_member_min_c": 20.5,
        "cohort_t_in_member_max_c": 21.8,
        "cohort_preheat_extra_kwh": 3.0,
        "cohort_cutback_shed_kwh": 1.5,
        "source_bundle_name": bundle,
    }
    missing = set(REQUIRED_HOURLY_MECHANISM_COLUMNS).difference(row)
    if missing:
        raise AssertionError(f"test fixture missing required columns: {sorted(missing)}")
    return row


class DeduplicateHourlyTruthTest(unittest.TestCase):
    def test_identical_duplicate_keeps_latest_bundle(self) -> None:
        frame = pd.DataFrame(
            [
                _base_truth_row(bundle="bundle-old"),
                {**_base_truth_row(bundle="bundle-new"), "case_label": "renamed-case"},
            ]
        )

        deduped = _deduplicate_hourly_truth(frame)

        self.assertEqual(len(deduped), 1)
        self.assertEqual(deduped.loc[0, "source_bundle_name"], "bundle-new")
        self.assertEqual(deduped.loc[0, "case_label"], "renamed-case")

    def test_conflicting_duplicate_truth_values_raise(self) -> None:
        frame = pd.DataFrame(
            [
                _base_truth_row(bundle="bundle-old", q_delta=1.5),
                _base_truth_row(bundle="bundle-new", q_delta=9.5),
            ]
        )

        with self.assertRaisesRegex(ValueError, "duplicate hourly truth rows disagree"):
            _deduplicate_hourly_truth(frame)


if __name__ == "__main__":
    unittest.main()
