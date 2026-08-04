from __future__ import annotations

import hashlib
from typing import Any

import pandas as pd


def normalized_rows_sha256(frame: pd.DataFrame) -> str:
    """
    Digest the exact normalized rows that define one curated truth slice.

    Bundle names, paths, and row counts alone cannot identify immutable training
    truth: source CSVs are revised in place under stable paths. The digest covers
    cell values as they will be persisted, with sorted columns so incidental
    DataFrame construction order does not change identity while row order remains
    part of the X/Y alignment contract.
    """

    # Sorting columns removes builder-side column-order noise; row order is kept
    # because it is part of the persisted sample alignment.
    canonical = frame.loc[:, sorted(str(column) for column in frame.columns)].reset_index(drop=True)
    payload = canonical.to_json(
        orient="records",
        date_format="iso",
        double_precision=15,
        force_ascii=False,
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def build_selected_bundle_content_signatures(
    selected: pd.DataFrame,
    *,
    bundle_column: str = "source_bundle_name",
) -> list[dict[str, Any]]:
    """
    Build per-bundle content digests for curated ThermFlex family hashing.

    Callers may attach additional structural fields for audit; this helper only
    returns the identity-critical content revision facts.
    """

    if bundle_column not in selected.columns:
        raise ValueError(
            f"[learning.datasets] '{bundle_column}' is required to build bundle content signatures."
        )
    signatures: list[dict[str, Any]] = []
    for bundle_name, bundle_df in selected.groupby(bundle_column, dropna=False, sort=True):
        signatures.append(
            {
                "source_bundle_name": str(bundle_name),
                "row_count": int(len(bundle_df)),
                "normalized_rows_sha256": normalized_rows_sha256(bundle_df),
            }
        )
    return signatures
