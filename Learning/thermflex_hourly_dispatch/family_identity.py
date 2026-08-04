from __future__ import annotations

from typing import Any

import pandas as pd

from Learning.datasets.row_content_signature import normalized_rows_sha256


def build_selected_bundle_signatures(frame: pd.DataFrame) -> list[dict[str, Any]]:
    """
    Describe each selected hourly-dispatch bundle for family hashing.

    Date spans and row counts miss in-place label/feature revisions under the
    same bundle path. Include a content digest so a re-export cannot overwrite a
    different training truth under the same family hash.
    """

    signatures: list[dict[str, Any]] = []
    for bundle_name, group in frame.groupby("source_bundle_name", sort=True):
        signatures.append(
            {
                "source_bundle_name": str(bundle_name),
                "source_hourly_csv": str(group["source_hourly_csv"].iloc[0]),
                "source_hourly_kind": str(group["source_hourly_kind"].iloc[0]),
                "flex_case_label": str(group["flex_case_label"].iloc[0]),
                "flex_override_name": str(group["flex_override_name"].iloc[0]),
                "row_count": int(len(group)),
                "date_count": int(group["date"].dt.strftime("%Y-%m-%d").nunique()),
                "first_date": str(group["date"].min().date()),
                "last_date": str(group["date"].max().date()),
                # Bind identity to the exact selected cells that become X/Y.
                "normalized_rows_sha256": normalized_rows_sha256(group),
            }
        )
    return signatures
