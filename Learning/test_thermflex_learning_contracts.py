from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

import pandas as pd

from Learning.thermflex_daily_results.dataset_builder import _deduplicate_policy_day_rows
from Learning.thermflex_daily_results.predict import _resolve_model_feature_mode
from Learning.thermflex_daily_results.predict import _template_required_columns
from Learning.thermflex_daily_results.schema import (
    DISPATCH_STATE_REFERENCE_FEATURE_COLUMNS,
    TARGET_COLUMNS as DAILY_TARGET_COLUMNS,
)
from Learning.thermflex_hourly_mechanism.dataset_builder import _deduplicate_hourly_truth
from Learning.thermflex_system_results.dataset_builder import load_system_results_truth_table
from Learning.thermflex_system_results.schema import REQUIRED_COMMON_COLUMNS


class ThermflexLearningContractTests(unittest.TestCase):
    def test_daily_policy_day_conflicting_targets_fail_fast(self) -> None:
        row = {
            "date": "2023-01-01",
            "policy_case_label_canonical": "UPPER_24H",
            "policy_duration_h": 24.0,
            "policy_lower_relaxation_k": 0.0,
            "policy_tau_h": 4.0,
            "policy_dispatch_horizon_h": 24.0,
            "policy_dispatch_rolling_commit_h": 24.0,
            "policy_max_events_per_day": 24.0,
            "policy_constant_lower_bound_c": 22.5,
            "policy_case_label_matches_export": True,
            "source_schema_version": "screen_v2_current",
            "source_screen_kind": "final",
            "bundle_row_count": 212,
            "source_bundle_name": "daily_thermflex_screen_case_20260101_000000",
            "source_screen_csv": "/tmp/final.csv",
        }
        for target in DAILY_TARGET_COLUMNS:
            row[target] = 0.0
        conflicting = dict(row)
        conflicting["source_bundle_name"] = "daily_thermflex_screen_case_20260102_000000"
        conflicting["dispatch_operating_cost_eur_delta"] = 42.0

        with self.assertRaisesRegex(ValueError, "duplicate policy-day rows disagree"):
            _deduplicate_policy_day_rows(pd.DataFrame([row, conflicting]))

    def test_hourly_mechanism_duplicate_truth_conflicts_fail_fast(self) -> None:
        row = {
            "case_label": "CASE_A",
            "run_dir": "run-1",
            "timestamp": pd.Timestamp("2023-01-01 00:00:00"),
            "cohort_key": "residential_pre1975",
            "source_bundle_name": "bundle_a",
            "source_hourly_csv": "/tmp/a.csv",
            "cohort_q_delta_kwh": 1.0,
            "cohort_preheat_extra_kwh": 2.0,
        }
        conflicting = dict(row)
        conflicting["case_label"] = "CASE_A_DISPLAY_RENAMED"
        conflicting["source_bundle_name"] = "bundle_b"
        conflicting["source_hourly_csv"] = "/tmp/b.csv"
        conflicting["cohort_q_delta_kwh"] = 9.0

        with self.assertRaisesRegex(ValueError, "duplicate hourly truth rows disagree"):
            _deduplicate_hourly_truth(pd.DataFrame([row, conflicting]))

    def test_system_latest_point_rejects_multirow_truth_csv(self) -> None:
        rows = []
        for idx in range(2):
            row = {
                column: 1.0
                for column in REQUIRED_COMMON_COLUMNS
                if column not in {"run_id", "signature_hash", "source"}
            }
            row["run_id"] = f"run-{idx}"
            row["signature_hash"] = f"sig-{idx}"
            row["source"] = "unit-test"
            rows.append(row)

        with tempfile.TemporaryDirectory() as tmp:
            run_dir = Path(tmp) / "20260101_000000_thermflex_lb22p5_dur24_evt24"
            run_dir.mkdir(parents=True)
            truth_path = run_dir / "truth_dataset.csv"
            pd.DataFrame(rows).to_csv(truth_path, index=False)

            with self.assertRaisesRegex(ValueError, "latest_point.*multi-row"):
                load_system_results_truth_table(
                    truth_csv_paths=[truth_path],
                    dispatch_kpi_mode="latest_point",
                )

    def test_daily_inference_feature_mode_controls_template_contract(self) -> None:
        feature_mode = _resolve_model_feature_mode(
            model_bundle={
                "feature_columns": [
                    "date",
                    "policy_case_label_canonical_UPPER_24H",
                    "district_thermal_storage_soc_mean_ref_per_dh",
                ]
            },
            meta={},
        )

        self.assertEqual(feature_mode, "dispatch_economics_stateful")
        required = set(_template_required_columns(feature_mode=feature_mode))
        self.assertTrue(set(DISPATCH_STATE_REFERENCE_FEATURE_COLUMNS).issubset(required))


if __name__ == "__main__":
    unittest.main()
