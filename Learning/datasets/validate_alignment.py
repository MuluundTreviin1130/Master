from __future__ import annotations

from typing import Any, Sequence

import numpy as np
import pandas as pd


def validate_truth_dataset_alignment(
    *,
    dataset_bundle: dict[str, Any],
    truth_df: pd.DataFrame,
    context_label: str,
) -> None:
    """
    Fail fast when `truth_dataset.csv` no longer matches `training_data.npz`.

    ThermFlex trainers derive holdout rows and group labels from the rich CSV
    truth table, but train on the compact NumPy arrays. If one artifact is
    replaced, filtered or re-sorted without the other, a model can silently learn
    features from one row against targets from another. This guard keeps that
    row contract explicit at every model-training entry point.
    """

    meta = dataset_bundle.get("meta")
    if not isinstance(meta, dict):
        raise TypeError(f"[{context_label}] dataset bundle meta must be a dict.")

    feature_columns = _required_column_names(
        meta=meta,
        key="feature_columns",
        context_label=context_label,
    )
    target_columns = _required_column_names(
        meta=meta,
        key="target_columns",
        context_label=context_label,
    )

    x_design = _required_2d_matrix(
        dataset_bundle=dataset_bundle,
        key="X_design",
        context_label=context_label,
    )
    x = _required_2d_matrix(
        dataset_bundle=dataset_bundle,
        key="X",
        context_label=context_label,
    )
    y = _required_2d_matrix(
        dataset_bundle=dataset_bundle,
        key="Y",
        context_label=context_label,
    )

    expected_rows = int(len(truth_df))
    for matrix_name, matrix in (("X_design", x_design), ("X", x), ("Y", y)):
        if int(matrix.shape[0]) != expected_rows:
            raise ValueError(
                f"[{context_label}] truth_dataset.csv has {expected_rows} rows, "
                f"but training_data.npz `{matrix_name}` has {matrix.shape[0]} rows."
            )

    if int(x_design.shape[1]) != len(feature_columns):
        raise ValueError(
            f"[{context_label}] X_design has {x_design.shape[1]} columns, "
            f"but metadata lists {len(feature_columns)} feature columns."
        )
    if int(y.shape[1]) != len(target_columns):
        raise ValueError(
            f"[{context_label}] Y has {y.shape[1]} columns, "
            f"but metadata lists {len(target_columns)} target columns."
        )

    truth_x_design = _truth_numeric_matrix(
        truth_df=truth_df,
        columns=feature_columns,
        context_label=context_label,
        matrix_label="X_design",
    )
    truth_y = _truth_numeric_matrix(
        truth_df=truth_df,
        columns=target_columns,
        context_label=context_label,
        matrix_label="Y",
    )

    _assert_matrices_aligned(
        truth_matrix=truth_x_design,
        npz_matrix=x_design,
        columns=feature_columns,
        context_label=context_label,
        matrix_label="X_design",
    )
    _assert_matrices_aligned(
        truth_matrix=truth_y,
        npz_matrix=y,
        columns=target_columns,
        context_label=context_label,
        matrix_label="Y",
    )


def _required_column_names(
    *,
    meta: dict[str, Any],
    key: str,
    context_label: str,
) -> tuple[str, ...]:
    raw = meta.get(key)
    if not isinstance(raw, (list, tuple)) or not raw:
        raise ValueError(f"[{context_label}] dataset metadata must define non-empty `{key}`.")
    names = tuple(str(value) for value in raw)
    duplicate_names = sorted({name for name in names if names.count(name) > 1})
    if duplicate_names:
        raise ValueError(
            f"[{context_label}] dataset metadata `{key}` contains duplicate columns: "
            + ", ".join(duplicate_names)
        )
    return names


def _required_2d_matrix(
    *,
    dataset_bundle: dict[str, Any],
    key: str,
    context_label: str,
) -> np.ndarray:
    if key not in dataset_bundle:
        raise KeyError(f"[{context_label}] dataset bundle missing `{key}` from training_data.npz.")
    matrix = np.asarray(dataset_bundle[key], dtype=float)
    if matrix.ndim != 2:
        raise ValueError(f"[{context_label}] training_data.npz `{key}` must be 2D.")
    return matrix


def _truth_numeric_matrix(
    *,
    truth_df: pd.DataFrame,
    columns: Sequence[str],
    context_label: str,
    matrix_label: str,
) -> np.ndarray:
    missing = [column for column in columns if column not in truth_df.columns]
    if missing:
        raise KeyError(
            f"[{context_label}] truth_dataset.csv is missing `{matrix_label}` contract columns: "
            + ", ".join(missing)
        )

    converted_columns: list[np.ndarray] = []
    for column in columns:
        if column == "date":
            # Daily ThermFlex datasets keep human-readable dates in the truth
            # CSV but persist the design matrix with pandas ordinals. Encoding
            # the same explicit transform here lets the alignment check compare
            # exported artifacts without requiring an extra hidden row id.
            values = pd.to_datetime(truth_df[column], errors="raise").map(pd.Timestamp.toordinal)
        else:
            values = pd.to_numeric(truth_df[column], errors="raise")
        converted_columns.append(np.asarray(values, dtype=float))

    if not converted_columns:
        raise ValueError(f"[{context_label}] `{matrix_label}` contract has no columns.")
    return np.column_stack(converted_columns)


def _assert_matrices_aligned(
    *,
    truth_matrix: np.ndarray,
    npz_matrix: np.ndarray,
    columns: Sequence[str],
    context_label: str,
    matrix_label: str,
) -> None:
    if truth_matrix.shape != npz_matrix.shape:
        raise ValueError(
            f"[{context_label}] truth_dataset.csv `{matrix_label}` shape {truth_matrix.shape} "
            f"does not match training_data.npz shape {npz_matrix.shape}."
        )

    aligned = np.isclose(truth_matrix, npz_matrix, rtol=1e-9, atol=1e-9, equal_nan=True)
    if bool(aligned.all()):
        return

    row_idx, col_idx = np.argwhere(~aligned)[0]
    column_name = str(columns[int(col_idx)])
    raise ValueError(
        f"[{context_label}] truth_dataset.csv is not aligned with training_data.npz `{matrix_label}`; "
        f"first mismatch at row {int(row_idx)}, column `{column_name}` "
        f"(truth={truth_matrix[int(row_idx), int(col_idx)]!r}, "
        f"npz={npz_matrix[int(row_idx), int(col_idx)]!r}). "
        "Re-export the curated dataset instead of training on mixed artifacts."
    )
