from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List

import numpy as np
import pandas as pd


def save_dataset(
    dataset_root: str | Path,
    family_hash: str,
    X_design: np.ndarray,
    X: np.ndarray,
    Y: np.ndarray,
    meta: Dict[str, Any],
    *,
    bounds_names: List[str],
    target_names: List[str],
    family_spec: Dict[str, Any] | None = None,
    source_runs: List[Dict[str, Any]] | None = None,
    teacher_eval_summary: Dict[str, Any] | None = None,
    teacher_failed_points: List[Dict[str, Any]] | None = None,
) -> Dict[str, Any]:
    root = Path(dataset_root) / str(family_hash)
    root.mkdir(parents=True, exist_ok=True)
    data_path = root / "training_data.npz"
    meta_path = root / "training_data.meta.json"
    truth_csv_path = root / "truth_dataset.csv"
    truth_meta_path = root / "truth_dataset.meta.json"
    family_spec_path = root / "family_spec.json"
    source_runs_path = root / "source_runs.json"
    teacher_eval_dir = root / "teacher_eval"
    teacher_eval_summary_path = teacher_eval_dir / "summary.json"
    teacher_eval_failed_path = teacher_eval_dir / "infeasible_points.csv"

    X_design_arr = np.asarray(X_design, dtype=float)
    X_arr = np.asarray(X, dtype=float)
    Y_arr = np.asarray(Y, dtype=float)
    if X_design_arr.ndim != 2:
        raise ValueError("[dataset] X_design muss 2D sein.")
    if X_arr.ndim != 2:
        raise ValueError("[dataset] X muss 2D sein.")
    if Y_arr.ndim != 2:
        raise ValueError("[dataset] Y muss 2D sein.")
    if X_design_arr.shape[0] != X_arr.shape[0] or X_design_arr.shape[0] != Y_arr.shape[0]:
        raise ValueError("[dataset] X_design, X und Y muessen dieselbe Zeilenanzahl haben.")
    if len(bounds_names) != int(X_design_arr.shape[1]):
        raise ValueError(
            f"[dataset] bounds_names hat Laenge {len(bounds_names)}, erwartet {X_design_arr.shape[1]}."
        )
    if len(target_names) != int(Y_arr.shape[1]):
        raise ValueError(
            f"[dataset] target_names hat Laenge {len(target_names)}, erwartet {Y_arr.shape[1]}."
        )

    np.savez_compressed(
        data_path,
        X_design=X_design_arr,
        X=X_arr,
        Y=Y_arr,
    )
    meta_path.write_text(json.dumps(meta, indent=2, ensure_ascii=False), encoding="utf-8")

    truth_df = pd.DataFrame(X_design_arr, columns=list(bounds_names))
    for idx, target in enumerate(target_names):
        truth_df[str(target)] = Y_arr[:, idx]
    truth_df.to_csv(truth_csv_path, index=False)
    truth_meta = {
        "family_hash": str(family_hash),
        "n_samples": int(X_design_arr.shape[0]),
        "bounds_names": list(bounds_names),
        "target_names": list(target_names),
        "feature_count": int(X_arr.shape[1]),
        "meta_path": str(meta_path),
    }
    truth_meta_path.write_text(json.dumps(truth_meta, indent=2, ensure_ascii=False), encoding="utf-8")

    if family_spec is not None:
        family_spec_path.write_text(json.dumps(family_spec, indent=2, ensure_ascii=False), encoding="utf-8")
    if source_runs is not None:
        source_runs_path.write_text(json.dumps(source_runs, indent=2, ensure_ascii=False), encoding="utf-8")
    if teacher_eval_summary is not None or teacher_failed_points is not None:
        teacher_eval_dir.mkdir(parents=True, exist_ok=True)
        if teacher_eval_summary is not None:
            teacher_eval_summary_path.write_text(
                json.dumps(teacher_eval_summary, indent=2, ensure_ascii=False),
                encoding="utf-8",
            )
        if teacher_failed_points is not None:
            pd.DataFrame(list(teacher_failed_points)).to_csv(teacher_eval_failed_path, index=False)

    return {
        "root": root,
        "data_path": data_path,
        "meta_path": meta_path,
        "truth_csv_path": truth_csv_path,
        "truth_meta_path": truth_meta_path,
        "family_spec_path": family_spec_path if family_spec is not None else None,
        "source_runs_path": source_runs_path if source_runs is not None else None,
        "teacher_eval_summary_path": teacher_eval_summary_path if teacher_eval_summary is not None else None,
        "teacher_eval_failed_path": teacher_eval_failed_path if teacher_failed_points is not None else None,
    }
