from __future__ import annotations

from pathlib import Path
import unittest

import numpy as np

from Learning.datasets.load_dataset import validate_truth_row_alignment


def _bundle_with_rows(row_count: int, *, meta_rows: int | None = None) -> dict[str, object]:
    meta = {}
    if meta_rows is not None:
        meta["n_selected_rows"] = meta_rows
    return {
        "X_design": np.zeros((row_count, 2), dtype=float),
        "X": np.zeros((row_count, 3), dtype=float),
        "Y": np.zeros((row_count, 1), dtype=float),
        "data_path": Path("training_data.npz"),
        "truth_csv_path": Path("truth_dataset.csv"),
        "meta": meta,
    }


class ValidateTruthRowAlignmentTest(unittest.TestCase):
    def test_accepts_matching_contract(self) -> None:
        validate_truth_row_alignment(
            _bundle_with_rows(3, meta_rows=3),
            3,
            context_label="[test] dataset",
        )

    def test_rejects_desynchronized_truth_csv(self) -> None:
        with self.assertRaisesRegex(ValueError, r"truth CSV row count \(2\) does not match"):
            validate_truth_row_alignment(
                _bundle_with_rows(3, meta_rows=3),
                2,
                context_label="[test] dataset",
            )

    def test_rejects_stale_metadata(self) -> None:
        with self.assertRaisesRegex(ValueError, r"metadata `n_selected_rows` row count \(4\)"):
            validate_truth_row_alignment(
                _bundle_with_rows(3, meta_rows=4),
                3,
                context_label="[test] dataset",
            )


if __name__ == "__main__":
    unittest.main()
