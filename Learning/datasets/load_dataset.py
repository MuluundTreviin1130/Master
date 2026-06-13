from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Optional

import numpy as np


def load_dataset(dataset_root: str | Path, family_hash: str) -> Optional[Dict[str, Any]]:
    root = Path(dataset_root) / str(family_hash)
    data_path = root / "training_data.npz"
    meta_path = root / "training_data.meta.json"
    truth_csv_path = root / "truth_dataset.csv"
    truth_meta_path = root / "truth_dataset.meta.json"
    family_spec_path = root / "family_spec.json"
    source_runs_path = root / "source_runs.json"
    teacher_eval_summary_path = root / "teacher_eval" / "summary.json"
    teacher_eval_failed_path = root / "teacher_eval" / "infeasible_points.csv"
    if not data_path.exists() or not meta_path.exists():
        return None
    bundle = np.load(data_path, allow_pickle=False)
    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    return {
        "root": root,
        "data_path": data_path,
        "meta_path": meta_path,
        "truth_csv_path": truth_csv_path if truth_csv_path.exists() else None,
        "truth_meta_path": truth_meta_path if truth_meta_path.exists() else None,
        "family_spec_path": family_spec_path if family_spec_path.exists() else None,
        "source_runs_path": source_runs_path if source_runs_path.exists() else None,
        "teacher_eval_summary_path": teacher_eval_summary_path if teacher_eval_summary_path.exists() else None,
        "teacher_eval_failed_path": teacher_eval_failed_path if teacher_eval_failed_path.exists() else None,
        "X_design": bundle["X_design"],
        "X": bundle["X"],
        "Y": bundle["Y"],
        "meta": meta,
    }


def validate_truth_row_alignment(
    dataset_bundle: Dict[str, Any],
    truth_row_count: int,
    *,
    context_label: str,
) -> None:
    """
    Fail fast when the rich truth CSV no longer matches the saved NPZ rows.

    Several ThermFlex training paths build holdout indices from `truth_dataset.csv`
    but index `X`/`Y` from `training_data.npz`. If those files are partially
    regenerated or manually edited out of sync, training can silently pair the
    wrong labels with the wrong features whenever the CSV still has index values
    that are valid for the array length. The row-count contract is therefore
    checked before any split indices are applied.
    """

    truth_rows = int(truth_row_count)
    if truth_rows < 0:
        raise ValueError(f"{context_label}: truth_row_count must be nonnegative.")

    row_counts: dict[str, int] = {}
    for key in ("X_design", "X", "Y"):
        if key not in dataset_bundle:
            raise KeyError(f"{context_label}: dataset bundle missing `{key}`.")
        row_counts[key] = int(dataset_bundle[key].shape[0])

    expected_rows = set(row_counts.values())
    if len(expected_rows) != 1:
        detail = ", ".join(f"{key}={value}" for key, value in sorted(row_counts.items()))
        raise ValueError(f"{context_label}: NPZ arrays have inconsistent row counts: {detail}.")

    npz_rows = expected_rows.pop()
    if truth_rows != npz_rows:
        data_path = dataset_bundle.get("data_path", "<unknown training_data.npz>")
        truth_csv_path = dataset_bundle.get("truth_csv_path", "<unknown truth_dataset.csv>")
        raise ValueError(
            f"{context_label}: truth CSV row count ({truth_rows}) does not match "
            f"training_data.npz row count ({npz_rows}); refusing to train with "
            f"desynchronized features/labels. truth_csv={truth_csv_path}, data={data_path}"
        )

    meta = dataset_bundle.get("meta", {})
    if isinstance(meta, dict):
        for meta_key in ("n_selected_rows", "n_samples"):
            if meta_key not in meta:
                continue
            meta_rows = int(meta[meta_key])
            if meta_rows != truth_rows:
                raise ValueError(
                    f"{context_label}: metadata `{meta_key}` row count ({meta_rows}) "
                    f"does not match truth CSV row count ({truth_rows})."
                )
