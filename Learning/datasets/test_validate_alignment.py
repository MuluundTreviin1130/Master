from __future__ import annotations

import unittest

import numpy as np
import pandas as pd

from Learning.datasets.validate_alignment import validate_truth_dataset_alignment


class ValidateTruthDatasetAlignmentTest(unittest.TestCase):
    def test_accepts_exported_daily_date_ordinal_contract(self) -> None:
        truth_df = _truth_frame()
        validate_truth_dataset_alignment(
            dataset_bundle=_dataset_bundle(truth_df),
            truth_df=truth_df,
            context_label="unit_test",
        )

    def test_rejects_reordered_truth_rows(self) -> None:
        truth_df = _truth_frame()
        reordered_truth = truth_df.iloc[::-1].reset_index(drop=True)

        with self.assertRaisesRegex(ValueError, "not aligned"):
            validate_truth_dataset_alignment(
                dataset_bundle=_dataset_bundle(truth_df),
                truth_df=reordered_truth,
                context_label="unit_test",
            )

    def test_rejects_npz_row_count_mismatch(self) -> None:
        truth_df = _truth_frame()
        bundle = _dataset_bundle(truth_df)
        bundle["X"] = bundle["X"][:1, :]

        with self.assertRaisesRegex(ValueError, "truth_dataset.csv has 2 rows"):
            validate_truth_dataset_alignment(
                dataset_bundle=bundle,
                truth_df=truth_df,
                context_label="unit_test",
            )


def _truth_frame() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "date": ["2023-01-01", "2023-01-02"],
            "heat_kwh": [10.0, 20.0],
            "target_delta": [1.5, np.nan],
        }
    )


def _dataset_bundle(truth_df: pd.DataFrame) -> dict[str, object]:
    date_ordinals = pd.to_datetime(truth_df["date"], errors="raise").map(pd.Timestamp.toordinal)
    x_design = np.column_stack(
        [
            np.asarray(date_ordinals, dtype=float),
            truth_df["heat_kwh"].to_numpy(dtype=float),
        ]
    )
    y = truth_df[["target_delta"]].to_numpy(dtype=float)
    return {
        "X_design": x_design,
        "X": x_design.copy(),
        "Y": y,
        "meta": {
            "feature_columns": ["date", "heat_kwh"],
            "target_columns": ["target_delta"],
        },
    }


if __name__ == "__main__":
    unittest.main()
