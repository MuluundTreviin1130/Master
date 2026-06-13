from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

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


def test_validate_truth_row_alignment_accepts_matching_contract() -> None:
    validate_truth_row_alignment(
        _bundle_with_rows(3, meta_rows=3),
        3,
        context_label="[test] dataset",
    )


def test_validate_truth_row_alignment_rejects_desynchronized_truth_csv() -> None:
    with pytest.raises(ValueError, match="truth CSV row count \\(2\\) does not match"):
        validate_truth_row_alignment(
            _bundle_with_rows(3, meta_rows=3),
            2,
            context_label="[test] dataset",
        )


def test_validate_truth_row_alignment_rejects_stale_metadata() -> None:
    with pytest.raises(ValueError, match="metadata `n_selected_rows` row count \\(4\\)"):
        validate_truth_row_alignment(
            _bundle_with_rows(3, meta_rows=4),
            3,
            context_label="[test] dataset",
        )
