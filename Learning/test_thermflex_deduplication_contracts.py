from __future__ import annotations

import importlib
import sys
import types
import unittest

import pandas as pd


def _install_external_import_stubs() -> None:
    """Keep these unit tests focused on deduplication contracts, not data loaders."""

    def package(name: str) -> types.ModuleType:
        module = sys.modules.get(name)
        if module is None:
            module = types.ModuleType(name)
            module.__path__ = []  # type: ignore[attr-defined]
            sys.modules[name] = module
        return module

    def module(name: str, **attrs: object) -> None:
        current = types.ModuleType(name)
        for attr_name, attr_value in attrs.items():
            setattr(current, attr_name, attr_value)
        sys.modules[name] = current

    package("Data")
    package("Data.thermal_archetypes")
    package("Data.thermal_archetypes.Vienna")
    module(
        "Data.thermal_archetypes.Vienna.calibrated_v1",
        build_calibrated_v1_values=lambda: {},
    )
    package("dispatch")
    module(
        "dispatch.metrics",
        compute_thermflex_series_metrics=lambda *args, **kwargs: {},
    )
    module("Settings", get_settings=lambda *args, **kwargs: None)
    module(
        "Optimization.run.analysis.dh_thermflex_inputs",
        load_vienna_dh_thermflex_full_year_context=lambda: None,
    )
    module(
        "Optimization.run.analysis.select_vienna_dh_thermflex_representative_days",
        _build_daily_features=lambda *args, **kwargs: None,
    )


class ThermflexDeduplicationContractTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        _install_external_import_stubs()
        cls.daily = importlib.import_module("Learning.thermflex_daily_results.dataset_builder")
        cls.hourly = importlib.import_module("Learning.thermflex_hourly_mechanism.dataset_builder")

    def _daily_policy_day_row(self, *, bundle_name: str, target_value: float) -> dict[str, object]:
        row: dict[str, object] = {
            "date": pd.Timestamp("2023-01-05"),
            "policy_case_label_canonical": "upper_lower_1k_dur4_evt24",
            "policy_duration_h": 4.0,
            "policy_lower_relaxation_k": 1.0,
            "policy_tau_h": 4.0,
            "policy_dispatch_horizon_h": 24.0,
            "policy_dispatch_rolling_commit_h": 1.0,
            "policy_max_events_per_day": 24.0,
            "policy_constant_lower_bound_c": 19.0,
            "policy_case_label_matches_export": True,
            "source_schema_version": "screen_v2_current",
            "source_screen_kind": "final",
            "bundle_row_count": 212,
            "source_bundle_name": bundle_name,
            "source_screen_csv": f"{bundle_name}/heating_season_day_screen.csv",
        }
        for target in self.daily.TARGET_COLUMNS:
            row[target] = float(target_value)
        return row

    def test_daily_policy_day_duplicates_must_not_disagree_on_targets(self) -> None:
        first = self._daily_policy_day_row(bundle_name="daily_thermflex_screen_a_20260501_000000", target_value=1.0)
        second = self._daily_policy_day_row(bundle_name="daily_thermflex_screen_b_20260502_000000", target_value=2.0)

        with self.assertRaisesRegex(ValueError, "duplicate policy-day rows disagree"):
            self.daily._deduplicate_policy_day_rows(pd.DataFrame([first, second]))

    def test_daily_policy_day_exact_duplicate_can_be_deduplicated(self) -> None:
        first = self._daily_policy_day_row(bundle_name="daily_thermflex_screen_a_20260501_000000", target_value=1.0)
        second = self._daily_policy_day_row(bundle_name="daily_thermflex_screen_b_20260502_000000", target_value=1.0)

        deduped, metadata = self.daily._deduplicate_policy_day_rows(pd.DataFrame([first, second]))

        self.assertEqual(len(deduped), 1)
        self.assertEqual(metadata["dropped_rows"], 1)

    def _hourly_truth_row(self, *, bundle_name: str, case_label: str, target_value: float) -> dict[str, object]:
        row: dict[str, object] = {
            "case_label": case_label,
            "run_dir": "run-a",
            "timestamp": pd.Timestamp("2023-01-05 08:00:00"),
            "cohort_key": "residential_1970",
            "source_bundle_name": bundle_name,
        }
        for column in self.hourly.REQUIRED_HOURLY_MECHANISM_COLUMNS:
            if column in row:
                continue
            row[column] = 1.0
        row["cohort_q_delta_kwh"] = float(target_value)
        return row

    def test_hourly_truth_duplicates_must_not_disagree_on_numeric_truth(self) -> None:
        first = self._hourly_truth_row(bundle_name="old_bundle", case_label="legacy label", target_value=1.0)
        second = self._hourly_truth_row(bundle_name="new_bundle", case_label="current label", target_value=2.0)

        with self.assertRaisesRegex(ValueError, "duplicate hourly truth rows disagree"):
            self.hourly._deduplicate_hourly_truth(pd.DataFrame([first, second]))

    def test_hourly_truth_exact_duplicate_can_be_deduplicated(self) -> None:
        first = self._hourly_truth_row(bundle_name="old_bundle", case_label="legacy label", target_value=1.0)
        second = self._hourly_truth_row(bundle_name="new_bundle", case_label="current label", target_value=1.0)

        deduped = self.hourly._deduplicate_hourly_truth(pd.DataFrame([first, second]))

        self.assertEqual(len(deduped), 1)


if __name__ == "__main__":
    unittest.main()
