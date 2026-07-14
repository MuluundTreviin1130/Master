from __future__ import annotations

import hashlib
from typing import Any

import pandas as pd


def build_selected_run_signatures(truth: pd.DataFrame) -> list[dict[str, Any]]:
    """
    Describe the exact normalized rows that define each selected source run.

    Gold run directories are appendable, so their folder names alone cannot
    identify immutable training truth. The content digest intentionally covers
    derived context and optional dispatch-KPI targets as they will be persisted,
    not merely the mutable source filenames.
    """

    if "source_run_name" not in truth.columns:
        raise ValueError(
            "[thermflex_system_results] source_run_name is required to build run signatures."
        )
    signatures: list[dict[str, Any]] = []
    for run_name, frame in truth.groupby("source_run_name", dropna=False, sort=True):
        # Sorting columns makes the digest independent of incidental DataFrame
        # construction order while preserving row order, which is part of the
        # persisted X/Y alignment contract.
        canonical = frame.loc[
            :, sorted(str(column) for column in frame.columns)
        ].reset_index(drop=True)
        payload = canonical.to_json(
            orient="records",
            date_format="iso",
            double_precision=15,
            force_ascii=False,
        ).encode("utf-8")
        signatures.append(
            {
                "source_run_name": str(run_name),
                "row_count": int(len(canonical)),
                "normalized_rows_sha256": hashlib.sha256(payload).hexdigest(),
            }
        )
    return signatures
