import json
import tempfile
import unittest
from pathlib import Path

import pandas as pd

from Learning.thermflex_system_results.dataset_builder import load_system_results_truth_table
from Learning.thermflex_system_results.schema import (
    DISPATCH_KPI_TARGET_COLUMNS,
    REQUIRED_COMMON_COLUMNS,
)


def _write_truth_csv(run_dir, *, row_count: int):
    numeric_columns = set(REQUIRED_COMMON_COLUMNS).difference({"run_id", "signature_hash", "source"})
    rows = []
    for row_idx in range(row_count):
        row = {
            "run_id": f"run-{row_idx}",
            "signature_hash": f"signature-{row_idx}",
            "source": "gold",
        }
        for column in numeric_columns:
            row[column] = float(row_idx + 1)
        rows.append(row)
    truth_path = run_dir / "truth_dataset.csv"
    pd.DataFrame(rows, columns=list(REQUIRED_COMMON_COLUMNS)).to_csv(truth_path, index=False)
    return truth_path


def _dispatch_point(*, point_idx: int, marker: float) -> dict[str, float]:
    point = {key: float(marker) for key in DISPATCH_KPI_TARGET_COLUMNS}
    point["point_idx"] = float(point_idx)
    point["dispatch_operating_cost_eur"] = float(marker)
    point["dispatch_heat_operating_cost_eur"] = float(marker + 0.5)
    return point


class DispatchKpiDatasetBuilderTests(unittest.TestCase):
    def test_dispatch_kpi_points_are_aligned_per_truth_row(self):
        with tempfile.TemporaryDirectory() as tmp:
            run_dir = (
                Path(tmp)
                / "20260616_110000_vienna_ref2023_dh_baseline_constant_lb21p0_dur8_evt1_paper_day_ahead"
            )
            run_dir.mkdir()
            truth_path = _write_truth_csv(run_dir, row_count=2)
            points = [
                _dispatch_point(point_idx=0, marker=100.0),
                _dispatch_point(point_idx=1, marker=200.0),
            ]
            stale_latest_point = _dispatch_point(point_idx=1, marker=999.0)
            (run_dir / "dispatch_kpis.json").write_text(
                json.dumps({"points": points, "latest_point": stale_latest_point}),
                encoding="utf-8",
            )

            loaded = load_system_results_truth_table(
                truth_csv_paths=[truth_path],
                dispatch_kpi_mode="latest_point",
            )

            self.assertEqual(loaded["dispatch_operating_cost_eur"].tolist(), [100.0, 200.0])
            self.assertEqual(loaded["dispatch_heat_operating_cost_eur"].tolist(), [100.5, 200.5])

    def test_dispatch_kpi_point_count_must_match_truth_rows(self):
        with tempfile.TemporaryDirectory() as tmp:
            run_dir = (
                Path(tmp)
                / "20260616_110000_vienna_ref2023_dh_baseline_constant_lb21p0_dur8_evt1_paper_day_ahead"
            )
            run_dir.mkdir()
            truth_path = _write_truth_csv(run_dir, row_count=2)
            (run_dir / "dispatch_kpis.json").write_text(
                json.dumps(
                    {
                        "points": [_dispatch_point(point_idx=0, marker=100.0)],
                        "latest_point": _dispatch_point(point_idx=0, marker=100.0),
                    }
                ),
                encoding="utf-8",
            )

            with self.assertRaisesRegex(ValueError, "point count does not match truth rows"):
                load_system_results_truth_table(
                    truth_csv_paths=[truth_path],
                    dispatch_kpi_mode="latest_point",
                )


if __name__ == "__main__":
    unittest.main()
