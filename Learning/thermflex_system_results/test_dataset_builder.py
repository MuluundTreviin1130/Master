from __future__ import annotations

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


def _write_synthetic_run(root: Path, *, row_count: int) -> Path:
    run_dir = root / "20260601_000000_vienna_baseline_constant_thermflex_lb20p0_dur4_evt1_paper_day_ahead"
    run_dir.mkdir(parents=True, exist_ok=True)

    columns: dict[str, list[object]] = {}
    for column in REQUIRED_COMMON_COLUMNS:
        if column == "run_id":
            columns[column] = [f"run-{idx}" for idx in range(row_count)]
        elif column == "signature_hash":
            columns[column] = [f"signature-{idx}" for idx in range(row_count)]
        elif column == "source":
            columns[column] = ["synthetic"] * row_count
        else:
            columns[column] = [float(idx + 1) for idx in range(row_count)]
    pd.DataFrame(columns).to_csv(run_dir / "truth_dataset.csv", index=False)

    latest_point = {
        key: float(idx + 10)
        for idx, key in enumerate(DISPATCH_KPI_TARGET_COLUMNS)
    }
    (run_dir / "dispatch_kpis.json").write_text(
        json.dumps({"latest_point": latest_point}),
        encoding="utf-8",
    )
    return run_dir / "truth_dataset.csv"


class SystemResultsDatasetBuilderTest(unittest.TestCase):
    def test_latest_point_dispatch_kpis_reject_multi_row_truth(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            truth_csv = _write_synthetic_run(Path(tmp), row_count=2)

            with self.assertRaisesRegex(ValueError, "requires exactly one truth row"):
                load_system_results_truth_table(
                    truth_csv_paths=[truth_csv],
                    dispatch_kpi_mode="latest_point",
                )

    def test_latest_point_dispatch_kpis_accept_single_row_truth(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            truth_csv = _write_synthetic_run(Path(tmp), row_count=1)

            truth = load_system_results_truth_table(
                truth_csv_paths=[truth_csv],
                dispatch_kpi_mode="latest_point",
            )

        self.assertEqual(len(truth), 1)
        self.assertEqual(
            float(truth["dispatch_heat_operating_cost_eur"].iloc[0]),
            float(list(DISPATCH_KPI_TARGET_COLUMNS).index("dispatch_heat_operating_cost_eur") + 10),
        )


if __name__ == "__main__":
    unittest.main()
