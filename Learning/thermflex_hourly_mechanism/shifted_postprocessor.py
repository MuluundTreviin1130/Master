from __future__ import annotations

"""Explicit shifted-heat postprocessors for hourly ThermFlex models.

Why this sublayer exists:
- the hourly mechanism model is useful for shape and regime diagnostics,
- but the `tau4` lower-relax transition tests showed a persistent bias in the
  day-level shifted heat mass after reaggregation,
- a daily calibration layer can correct that mass without changing the hourly
  heat-series metric definition or touching rebound/peak behavior,
- the calibration must be persisted and opt-in, not hidden in the evaluator.
"""

import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from joblib import dump
from sklearn.metrics import mean_absolute_error
from xgboost import XGBRegressor

from Learning.thermflex_hourly_mechanism.evaluate_kpi_reaggregation import (
    evaluate_holdout_daily_reaggregation,
)


DEFAULT_SHIFTED_FEATURE_COLUMNS: tuple[str, ...] = (
    "shifted_raw_kwh",
    "rebound_raw_kwh",
    "peak_raw_kw",
    "dh_space_heat_kwh_sum",
    "dh_total_kwh_sum",
    "t_outdoor_mean_c",
    "t_outdoor_min_c",
    "irradiance_proxy_sum",
    "solargains_proxy_sum",
    "month",
    "day_of_year",
)


TAU4_SHIFTED_STATE_FEATURE_COLUMNS: tuple[str, ...] = (
    "dh_space_heat_kwh_sum",
    "dh_total_kwh_sum",
    "t_outdoor_mean_c",
    "t_outdoor_min_c",
    "t_outdoor_max_c",
    "t_outdoor_range_c",
    "irradiance_proxy_sum",
    "solargains_proxy_sum",
    "month",
    "day_of_year",
    "q_ref_sum_kwh",
    "q_ref_peak_kw",
    "q_ref_min_kw",
    "q_ref_range_kw",
    "dh_per_q_ref",
    "dh_space_heat_to_q_ref",
    "is_winter_month",
    "is_spring_month",
    "is_autumn_month",
)


def fit_daily_xgb_shifted_postprocessor(
    *,
    model_dir: Path,
    dataset_dir: Path,
    profile: str = "tau4_lower_relax_shifted_daily_xgb_v1",
    output_name: str = "shifted_postprocessor.json",
) -> dict[str, Any]:
    """Fit one explicit daily shifted-heat calibrator on train-side days.

    The postprocessor learns only from days that were in the base hourly model's
    train split. Holdout days are therefore still genuinely held out for the
    final KPI reaggregation check.
    """

    model_root = Path(model_dir).resolve()
    dataset_root = Path(dataset_dir).resolve()
    profile_payload = _resolve_profile(profile)
    base_result = evaluate_holdout_daily_reaggregation(model_dir=model_root, dataset_dir=dataset_root)
    holdout_daily = base_result["daily_df"].copy()
    train_daily = _build_all_daily_frame_with_holdout_flag(
        model_dir=model_root,
        dataset_dir=dataset_root,
        holdout_daily=holdout_daily,
    )
    train_side = train_daily.loc[~train_daily["is_holdout_run"]].copy()
    if train_side.empty:
        raise ValueError("[thermflex_hourly_mechanism] shifted postprocessor cannot fit without train-side days.")

    feature_columns = tuple(str(value) for value in profile_payload["feature_columns"])
    missing = sorted(set(feature_columns).difference(train_side.columns))
    if missing:
        raise KeyError(
            "[thermflex_hourly_mechanism] shifted postprocessor train frame missing features: "
            + ", ".join(missing)
        )

    model = XGBRegressor(**profile_payload["model_params"])
    model.fit(
        train_side.loc[:, feature_columns].to_numpy(dtype=float),
        train_side["thermflex_shifted_space_heat_kwh_true"].to_numpy(dtype=float),
    )
    train_pred = model.predict(train_side.loc[:, feature_columns].to_numpy(dtype=float))
    model_path = model_root / "shifted_postprocessor.joblib"
    dump(model, model_path)
    payload = {
        "type": "daily_xgb_shifted_v1",
        "profile": profile,
        "feature_columns": list(feature_columns),
        "model_path": str(model_path),
        "fit_summary": {
            "n_train_days": int(len(train_side)),
            "train_mae_kwh": float(
                mean_absolute_error(
                    train_side["thermflex_shifted_space_heat_kwh_true"].to_numpy(dtype=float),
                    np.asarray(train_pred, dtype=float),
                )
            ),
        },
    }
    output_path = model_root / output_name
    output_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return {"payload": payload, "output_path": output_path, "model_path": model_path}


def evaluate_holdout_with_shifted_postprocessor(
    *,
    model_dir: Path,
    dataset_dir: Path,
    shifted_postprocessor_path: Path,
) -> dict[str, Any]:
    """Evaluate holdout day KPIs with one persisted shifted postprocessor."""

    payload = json.loads(Path(shifted_postprocessor_path).read_text(encoding="utf-8"))
    return evaluate_holdout_daily_reaggregation(
        model_dir=Path(model_dir).resolve(),
        dataset_dir=Path(dataset_dir).resolve(),
        shifted_postprocessor=payload,
    )


def _resolve_profile(profile: str) -> dict[str, Any]:
    """Resolve one named shifted postprocessor profile."""

    key = str(profile).strip().lower()
    if key == "tau4_lower_relax_shifted_daily_xgb_v1":
        return {
            "feature_columns": DEFAULT_SHIFTED_FEATURE_COLUMNS,
            "model_params": {
                "n_estimators": 200,
                "max_depth": 2,
                "learning_rate": 0.05,
                "subsample": 0.9,
                "colsample_bytree": 0.9,
                "reg_lambda": 2.0,
                "objective": "reg:squarederror",
                "random_state": 42,
                "n_jobs": 1,
            },
        }
    if key == "tau4_lower_relax_shifted_daily_state_xgb_v1":
        return {
            "feature_columns": TAU4_SHIFTED_STATE_FEATURE_COLUMNS,
            "model_params": {
                "n_estimators": 200,
                "max_depth": 2,
                "learning_rate": 0.05,
                "subsample": 0.9,
                "colsample_bytree": 0.9,
                "reg_lambda": 2.0,
                "objective": "reg:squarederror",
                "random_state": 42,
                "n_jobs": 1,
            },
        }
    raise ValueError(f"[thermflex_hourly_mechanism] unsupported shifted postprocessor profile: {profile}")


def _build_all_daily_frame_with_holdout_flag(
    *,
    model_dir: Path,
    dataset_dir: Path,
    holdout_daily: pd.DataFrame,
) -> pd.DataFrame:
    """Re-use evaluator feature columns and mark train-vs-holdout days.

    The public evaluator only returns holdout days. For fitting we need the same
    feature construction for all days. The simplest robust path is to run one
    train-side evaluation by temporarily reading the already written holdout
    daily payload for column contract and then rebuilding train rows through the
    private all-day helper embedded in the evaluator output contract.

    This helper keeps the persisted split as the only source of train/test
    membership. It does not create a second split.
    """

    from Learning.thermflex_hourly_mechanism.evaluate_kpi_reaggregation import (
        build_rebound_sequence_feature_payload,
        _build_daily_postprocessor_feature_payload,
        _invert_target_transform,
        predicted_or_true_metric,
    )
    from dispatch.metrics import compute_thermflex_series_metrics
    import joblib

    bundle = joblib.load(model_dir / "thermflex_hourly_mechanism_xgb.joblib")
    split_payload = json.loads((model_dir / "holdout_split.json").read_text(encoding="utf-8"))
    dataset_meta = json.loads((dataset_dir / "training_data.meta.json").read_text(encoding="utf-8"))
    truth = pd.read_csv(dataset_dir / "truth_dataset.csv")
    truth["timestamp"] = pd.to_datetime(truth["timestamp"], errors="raise")

    encoded_feature_columns = [
        str(value)
        for value in bundle.get("feature_columns", dataset_meta["encoded_feature_columns"])
    ]
    encoded = pd.get_dummies(
        truth.loc[:, list(dataset_meta["feature_columns"]) + list(dataset_meta["categorical_feature_columns"])].copy(),
        columns=list(dataset_meta["categorical_feature_columns"]),
        dtype=float,
    )
    encoded = encoded.reindex(columns=encoded_feature_columns, fill_value=0.0)
    predictions: dict[str, np.ndarray] = {}
    for model, target_name in zip(bundle["models"], bundle["target_names"]):
        transformed_pred = np.asarray(model.predict(encoded.to_numpy(dtype=float)), dtype=float)
        predictions[str(target_name)] = _invert_target_transform(
            transformed_pred,
            str(bundle["target_transforms"][target_name]),
        )
    if "cohort_q_delta_wh_per_m2" not in predictions:
        raise ValueError(
            "[thermflex_hourly_mechanism] shifted postprocessor currently requires "
            "`cohort_q_delta_wh_per_m2` in the base model targets."
        )
    q_ref = pd.to_numeric(truth["cohort_q_heat_ref_kwh"], errors="raise").to_numpy(dtype=float)
    q_delta_pred_kwh = (
        predictions["cohort_q_delta_wh_per_m2"]
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
            predicted_metrics = compute_thermflex_series_metrics(q_pred, q_ref_series)
            true_metrics = compute_thermflex_series_metrics(q_true, q_ref_series)
            shifted_raw = float(predicted_or_true_metric(predicted_metrics, "thermflex_shifted_space_heat_kwh"))
            rebound_raw = float(predicted_or_true_metric(predicted_metrics, "thermflex_rebound_kwh"))
            peak_raw = float(predicted_or_true_metric(predicted_metrics, "thermflex_peak_change_kw"))
            rows.append(
                {
                    "run_dir": str(run_dir),
                    "day": pd.Timestamp(day_ts),
                    "is_holdout_run": str(run_dir) in holdout_groups,
                    "thermflex_shifted_space_heat_kwh_true": float(
                        predicted_or_true_metric(true_metrics, "thermflex_shifted_space_heat_kwh")
                    ),
                    "thermflex_rebound_kwh_true": float(
                        predicted_or_true_metric(true_metrics, "thermflex_rebound_kwh")
                    ),
                    "thermflex_peak_change_kw_true": float(
                        predicted_or_true_metric(true_metrics, "thermflex_peak_change_kw")
                    ),
                    **_build_daily_postprocessor_feature_payload(
                        day_ts=pd.Timestamp(day_ts),
                        day_df=day_df,
                        shifted_pred_raw=shifted_raw,
                        rebound_pred_raw=rebound_raw,
                        peak_pred_raw=peak_raw,
                    ),
                    **build_rebound_sequence_feature_payload(
                        q_pred.to_numpy(dtype=float) - q_ref_series.to_numpy(dtype=float)
                    ),
                }
            )
    daily = pd.DataFrame(rows)
    if set(holdout_daily["run_dir"].astype(str)).difference(daily["run_dir"].astype(str)):
        raise ValueError("[thermflex_hourly_mechanism] shifted postprocessor all-day frame lost holdout runs.")
    return daily
