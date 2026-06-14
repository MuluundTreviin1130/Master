from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

import pandas as pd

from Documentation.Papers.thermflex_paper.tables.build_table_09_heating_season_kpis import (
    build_table_09_heating_season_kpis,
)
from Learning.thermflex_daily_results.dataset_builder import (
    _deduplicate_policy_day_rows,
    _resolve_thermflex_override_path,
)
from Learning.thermflex_hourly_mechanism.dataset_builder import _deduplicate_hourly_truth


class ThermflexLearningCriticalFixTests(unittest.TestCase):
    def test_override_path_traversal_is_rejected_before_file_read(self) -> None:
        with self.assertRaisesRegex(ValueError, "override SSOT directory"):
            _resolve_thermflex_override_path(override_name="../../Settings/technical/heating_control.py")

    def test_daily_policy_day_dedup_prefers_newer_timestamp_before_bundle_size(self) -> None:
        rows = [
            {
                "date": pd.Timestamp("2023-01-01"),
                "policy_case_label_canonical": "upper_only",
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
                "source_bundle_name": "daily_thermflex_screen_dur24_20250101_000000",
                "source_screen_csv": "old/heating_season_day_screen.csv",
                "thermflex_shifted_space_heat_kwh": 100.0,
            },
            {
                "date": pd.Timestamp("2023-01-01"),
                "policy_case_label_canonical": "upper_only",
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
                "bundle_row_count": 30,
                "source_bundle_name": "daily_thermflex_screen_dur24_20260101_000000",
                "source_screen_csv": "new/heating_season_day_screen_checkpoint.csv",
                "thermflex_shifted_space_heat_kwh": 200.0,
            },
        ]
        kept, summary = _deduplicate_policy_day_rows(pd.DataFrame(rows))

        self.assertEqual(summary["dropped_rows"], 1)
        self.assertEqual(len(kept), 1)
        self.assertEqual(str(kept.loc[0, "source_bundle_name"]), "daily_thermflex_screen_dur24_20260101_000000")
        self.assertEqual(float(kept.loc[0, "thermflex_shifted_space_heat_kwh"]), 200.0)

    def test_hourly_dedup_uses_numeric_version_rank(self) -> None:
        rows = [
            {
                "case_label": "upper_only",
                "run_dir": "run_a",
                "cohort_key": "residential_pre1975",
                "timestamp": pd.Timestamp("2023-01-01 00:00:00"),
                "source_bundle_name": "paper_mechanism_bundle_v2",
                "cohort_q_delta_wh_per_m2": 1.0,
            },
            {
                "case_label": "upper_only",
                "run_dir": "run_a",
                "cohort_key": "residential_pre1975",
                "timestamp": pd.Timestamp("2023-01-01 00:00:00"),
                "source_bundle_name": "paper_mechanism_bundle_v10",
                "cohort_q_delta_wh_per_m2": 2.0,
            },
        ]

        kept = _deduplicate_hourly_truth(pd.DataFrame(rows))

        self.assertEqual(len(kept), 1)
        self.assertEqual(str(kept.loc[0, "source_bundle_name"]), "paper_mechanism_bundle_v10")
        self.assertEqual(float(kept.loc[0, "cohort_q_delta_wh_per_m2"]), 2.0)

    def test_table_09_builder_imports_and_writes_outputs(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            screen_csv = tmp_path / "heating_season_day_screen.csv"
            output_md = tmp_path / "table_09.md"
            output_csv = tmp_path / "table_09.csv"
            pd.DataFrame(
                [
                    _screen_row("2023-01-01", 1.0, 8000.0, 1000.0, 990.0, 10.0, 9.8, 500.0, 500.0, 2000.0, 1980.0, 50.0, 20.0),
                    _screen_row("2023-01-02", 5.0, 6000.0, 1000.0, 970.0, 10.0, 9.4, 500.0, 480.0, 2000.0, 1900.0, 70.0, 35.0),
                    _screen_row("2023-01-03", 10.0, 3000.0, 1000.0, 1000.0, 10.0, 10.1, 500.0, 500.0, 2000.0, 2010.0, 90.0, 10.0),
                ]
            ).to_csv(screen_csv, index=False)

            result = build_table_09_heating_season_kpis(
                screen_csv=screen_csv,
                output_md=output_md,
                output_csv=output_csv,
            )

            self.assertEqual(result.output_md, output_md.resolve())
            self.assertEqual(result.output_csv, output_csv.resolve())
            self.assertTrue(output_md.exists())
            self.assertTrue(output_csv.exists())
            summary = pd.read_csv(output_csv)
            self.assertIn("heating_season_total", set(summary["scope"].astype(str)))


def _screen_row(
    date: str,
    t_outdoor_mean_c: float,
    dh_space_heat_total_kwh: float,
    cost_ref: float,
    cost_flex: float,
    co2_ref: float,
    co2_flex: float,
    boiler_peak_ref: float,
    boiler_peak_flex: float,
    boiler_generation_ref: float,
    boiler_generation_flex: float,
    shifted: float,
    rebound: float,
) -> dict[str, object]:
    return {
        "date": date,
        "t_outdoor_mean_c": t_outdoor_mean_c,
        "dh_space_heat_total_kwh": dh_space_heat_total_kwh,
        "dispatch_operating_cost_eur_ref": cost_ref,
        "dispatch_operating_cost_eur_flex": cost_flex,
        "co2_emissions_total_t_ref": co2_ref,
        "co2_emissions_total_t_flex": co2_flex,
        "district_gas_boiler_peak_kw_ref": boiler_peak_ref,
        "district_gas_boiler_peak_kw_flex": boiler_peak_flex,
        "district_gas_boiler_generation_kwh_ref": boiler_generation_ref,
        "district_gas_boiler_generation_kwh_flex": boiler_generation_flex,
        "thermflex_shifted_space_heat_kwh": shifted,
        "thermflex_rebound_kwh": rebound,
        "flex_case_label": "UPPER_24H",
        "flex_override_name": "vienna_upper_only_dur24.json",
    }


if __name__ == "__main__":
    unittest.main()
