from __future__ import annotations

from pathlib import Path
from typing import Any, Callable

import pandas as pd

from Learning.datasets.row_content_signature import normalized_rows_sha256


def build_selected_bundle_signatures(
    *,
    truth: pd.DataFrame,
    selected: pd.DataFrame,
    read_bundle_failure_summary: Callable[..., dict[str, Any]],
) -> list[dict[str, Any]]:
    """
    Build a compact selected-bundle revision signature for daily family hashing.

    Partial truth bundles evolve by row count and failure manifests, but in-place
    value revisions under the same structure also change training truth. The
    content digest of selected rows closes that identity gap.
    """

    selected_bundle_names = set(selected["source_bundle_name"].astype(str).unique().tolist())
    signatures: list[dict[str, Any]] = []
    for bundle_name, bundle_df in truth.groupby("source_bundle_name", sort=True):
        bundle_name_str = str(bundle_name)
        if bundle_name_str not in selected_bundle_names:
            continue
        bundle_dir = Path(str(bundle_df["source_screen_csv"].iloc[0])).resolve().parent
        failure_summary = read_bundle_failure_summary(bundle_dir=bundle_dir)
        # Hash the selected rows that enter training, not merely the raw screen.
        selected_bundle = selected.loc[
            selected["source_bundle_name"].astype(str) == bundle_name_str
        ].copy()
        signatures.append(
            {
                "bundle_name": bundle_name_str,
                "screen_csv": str(bundle_df["source_screen_csv"].iloc[0]),
                "screen_kind": str(bundle_df["source_screen_kind"].iloc[0]),
                "rows": int(len(bundle_df)),
                "schema_version": str(bundle_df["source_schema_version"].iloc[0]),
                "known_failure_rows": int(failure_summary["known_failure_rows"]),
                "known_failure_dates": list(failure_summary["known_failure_dates"]),
                "selected_rows": int(len(selected_bundle)),
                "normalized_rows_sha256": normalized_rows_sha256(selected_bundle),
            }
        )
    return signatures
