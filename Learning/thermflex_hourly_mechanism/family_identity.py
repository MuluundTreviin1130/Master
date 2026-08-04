from __future__ import annotations

from typing import Any

import pandas as pd

from Learning.datasets.row_content_signature import normalized_rows_sha256


def build_selected_bundle_signatures(selected: pd.DataFrame) -> list[dict[str, Any]]:
    """
    Describe each selected hourly-mechanism bundle for family hashing.

    Structural counts alone are not enough: truth CSVs are revised in place under
    stable paths while keeping the same row/timestamp/case shape. Without a
    content digest, `save_dataset` would reuse the old family hash and overwrite
    incompatible training artifacts.
    """

    signatures: list[dict[str, Any]] = []
    for bundle_name, bundle_df in selected.groupby("source_bundle_name", sort=True):
        signatures.append(
            {
                "bundle_name": str(bundle_name),
                "source_hourly_csv": str(bundle_df["source_hourly_csv"].iloc[0]),
                "rows": int(len(bundle_df)),
                "case_count": int(bundle_df["case_label"].nunique()),
                "cohort_count": int(bundle_df["cohort_key"].nunique()),
                "timestamp_count": int(bundle_df["timestamp"].nunique()),
                # Bind identity to the exact selected cells that become X/Y.
                "normalized_rows_sha256": normalized_rows_sha256(bundle_df),
            }
        )
    return signatures
