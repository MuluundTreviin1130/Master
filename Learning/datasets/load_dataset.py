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
