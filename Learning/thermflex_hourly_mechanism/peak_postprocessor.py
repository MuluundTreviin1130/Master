from __future__ import annotations

"""Explicit peak postprocessors for hourly ThermFlex mechanism models."""

import json
from pathlib import Path
from typing import Any

import joblib
import numpy as np
import pandas as pd
from sklearn.metrics import mean_absolute_error

from Learning.thermflex_hourly_mechanism.evaluate_kpi_reaggregation import (
    _invert_target_transform,
    evaluate_holdout_daily_reaggregation,
)
from dispatch.metrics import compute_thermflex_series_metrics


def fit_signed_peak_scale_postprocessor(
    *,
    model_dir: Path,
    dataset_dir: Path,
    profile: str = "mixed_evt24_peak_negative_scale_v1",
    output_name: str = "peak_postprocessor.json",
) -> dict[str, Any]:
    """Fit one explicit sign-aware peak scaler on the train-side daily payload."""

    model_root = Path(model_dir).resolve()
    dataset_root = Path(dataset_dir).resolve()
    profile_payload = _resolve_profile(profile)
    daily_df = _build_daily_peak_training_frame(model_dir=model_root, dataset_dir=dataset_root)
    train_daily = daily_df.loc[~daily_df["is_holdout_run"]].copy()
    if train_daily.empty:
        raise ValueError("[thermflex_hourly_mechanism] peak postprocessor cannot fit without train-side days.")

    negative_scale = _fit_scale_through_origin(
        raw_pred=train_daily.loc[train_daily["thermflex_peak_change_kw_pred_raw"] < 0.0, "thermflex_peak_change_kw_pred_raw"],
        true_target=train_daily.loc[train_daily["thermflex_peak_change_kw_pred_raw"] < 0.0, "thermflex_peak_change_kw_true"],
    )
    nonnegative_scale = float(profile_payload["nonnegative_scale"])

    pred_scaled = np.where(
        train_daily["thermflex_peak_change_kw_pred_raw"].to_numpy(dtype=float) < 0.0,
        negative_scale * train_daily["thermflex_peak_change_kw_pred_raw"].to_numpy(dtype=float),
        nonnegative_scale * train_daily["thermflex_peak_change_kw_pred_raw"].to_numpy(dtype=float),
    )
    payload = {
        "type": "signed_peak_scale_v1",
        "profile": profile,
        "negative_scale": float(negative_scale),
        "nonnegative_scale": nonnegative_scale,
        "fit_summary": {
            "n_train_days": int(len(train_daily)),
            "train_mae_kw": float(
                mean_absolute_error(
                    train_daily["thermflex_peak_change_kw_true"].to_numpy(dtype=float),
                    pred_scaled,
                )
            ),
        },
    }
    output_path = model_root / output_name
    output_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return {"payload": payload, "output_path": output_path}


def evaluate_holdout_with_peak_postprocessor(
    *,
    model_dir: Path,
    dataset_dir: Path,
    peak_postprocessor_path: Path,
) -> dict[str, Any]:
    payload = json.loads(Path(peak_postprocessor_path).read_text(encoding="utf-8"))
    return evaluate_holdout_daily_reaggregation(
        model_dir=Path(model_dir).resolve(),
        dataset_dir=Path(dataset_dir).resolve(),
        peak_postprocessor=payload,
    )


def _resolve_profile(profile: str) -> dict[str, Any]:
    key = str(profile).strip().lower()
    if key == "mixed_evt24_peak_negative_scale_v1":
        return {"nonnegative_scale": 1.0}
    raise ValueError(f"[thermflex_hourly_mechanism] unsupported peak postprocessor profile: {profile}")


def _fit_scale_through_origin(*, raw_pred: pd.Series, true_target: pd.Series) -> float:
    x = np.asarray(raw_pred, dtype=float).reshape(-1)
    y = np.asarray(true_target, dtype=float).reshape(-1)
    denominator = float(np.sum(np.square(x)))
    if denominator <= 1e-12:
        return 1.0
    return float(np.sum(x * y) / denominator)


def _build_daily_peak_training_frame(*, model_dir: Path, dataset_dir: Path) -> pd.DataFrame:
    bundle = joblib.load(model_dir / "thermflex_hourly_mechanism_xgb.joblib")
    split_payload = json.loads((model_dir / "holdout_split.json").read_text(encoding="utf-8"))
    dataset_meta = json.loads((dataset_dir / "training_data.meta.json").read_text(encoding="utf-8"))
    truth = pd.read_csv(dataset_dir / "truth_dataset.csv")
    truth["timestamp"] = pd.to_datetime(truth["timestamp"], errors="raise")

    encoded_feature_columns = [
        str(value)
        for value in bundle.get("feature_columns", dataset_meta["encoded_feature_columns"])
    ]
    numeric_feature_columns = [str(value) for value in dataset_meta["feature_columns"]]
    categorical_feature_columns = [str(value) for value in dataset_meta["categorical_feature_columns"]]
    target_names = [str(value) for value in bundle["target_names"]]
    target_transforms = dict(bundle["target_transforms"])

    if "cohort_q_delta_wh_per_m2" not in target_names:
        raise ValueError(
            "[thermflex_hourly_mechanism] peak postprocessor currently requires "
            "`cohort_q_delta_wh_per_m2` in the base model targets."
        )

    raw_feature_frame = truth.loc[:, numeric_feature_columns + categorical_feature_columns].copy()
    encoded = pd.get_dummies(raw_feature_frame, columns=categorical_feature_columns, dtype=float)
    encoded = encoded.reindex(columns=encoded_feature_columns, fill_value=0.0)

    predictions: dict[str, np.ndarray] = {}
    for model, target_name in zip(bundle["models"], target_names):
        transformed_pred = np.asarray(model.predict(encoded.to_numpy(dtype=float)), dtype=float)
        predictions[target_name] = _invert_target_transform(
            transformed_pred,
            str(target_transforms[target_name]),
        )

    q_ref = pd.to_numeric(truth["cohort_q_heat_ref_kwh"], errors="raise").to_numpy(dtype=float)
    q_delta_pred_kwh = (
        np.asarray(predictions["cohort_q_delta_wh_per_m2"], dtype=float)
        * pd.to_numeric(truth["cohort_floor_area_m2"], errors="raise").to_numpy(dtype=float)
        / 1000.0
    )
    truth["cohort_q_heat_pred_kwh"] = q_ref + q_delta_pred_kwh
    holdout_groups = {str(value) for value in split_payload["test_groups"]}

    rows: list[dict[str, Any]] = []
    for run_dir, run_df in truth.groupby("run_dir", sort=True):
        for day_ts, day_df in run_df.groupby(run_df["timestamp"].dt.floor("D")):
            q_pred = day_df.groupby("timestamp")["cohort_q_heat_pred_kwh"].sum().sort_index()
            q_ref_series = day_df.groupby("timestamp")["cohort_q_heat_ref_kwh"].sum().sort_index()
            q_true = day_df.groupby("timestamp")["cohort_q_heat_kwh"].sum().sort_index()
            pred_metrics = compute_thermflex_series_metrics(q_pred, q_ref_series)
            true_metrics = compute_thermflex_series_metrics(q_true, q_ref_series)
            rows.append(
                {
                    "run_dir": str(run_dir),
                    "day": pd.Timestamp(day_ts),
                    "is_holdout_run": str(run_dir) in holdout_groups,
                    "thermflex_peak_change_kw_true": float(true_metrics["thermflex_peak_change_kw"]),
                    "thermflex_peak_change_kw_pred_raw": float(pred_metrics["thermflex_peak_change_kw"]),
                }
            )
    return pd.DataFrame(rows)
