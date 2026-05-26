from __future__ import annotations

"""Explicit rebound postprocessors for hourly ThermFlex mechanism models.

Why this sublayer exists:
- the `constant_evt24_lower_relax_only` family already fits `shifted` and
  `peak` well enough on holdout,
- the remaining failure is isolated in daily `rebound`,
- the failure mode is specific:
  - small early negative hourly prediction noise activates the rebound regime,
  - later positive heat is then counted as rebound even on true zero-rebound
    days,
- this should not silently change the global KPI definition,
- therefore the repo uses one explicit, persisted postprocessor payload that can
  be attached to one specific model artifact.
"""

import json
from pathlib import Path
from typing import Any

import joblib
import numpy as np
import pandas as pd
from joblib import dump
from sklearn.ensemble import ExtraTreesClassifier, ExtraTreesRegressor
from sklearn.metrics import mean_absolute_error
from xgboost import XGBRegressor

from Learning.thermflex_hourly_mechanism.evaluate_kpi_reaggregation import (
    _invert_target_transform,
    _rebound_after_reduction_with_deadbands,
    evaluate_holdout_daily_reaggregation,
)
from Learning.thermflex_hourly_mechanism.shifted_postprocessor import (
    TAU4_SHIFTED_STATE_FEATURE_COLUMNS,
    _build_all_daily_frame_with_holdout_flag,
)


UPPER_ONLY_REBOUND_FEATURE_COLUMNS: tuple[str, ...] = (
    "shifted_raw_kwh",
    "rebound_raw_kwh",
    "peak_raw_kw",
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


UPPER_ONLY_REBOUND_SEQUENCE_FEATURE_COLUMNS: tuple[str, ...] = (
    *UPPER_ONLY_REBOUND_FEATURE_COLUMNS,
    "seq_positive_mass_kwh",
    "seq_negative_mass_kwh",
    "seq_positive_after_first_negative_kwh",
    "seq_first_negative_hour",
    "seq_hours_after_first_negative",
    "seq_min_delta_kwh",
    "seq_max_delta_kwh",
    "seq_positive_hour_count",
    "seq_negative_hour_count",
)


def fit_deadband_scaled_rebound_postprocessor(
    *,
    model_dir: Path,
    dataset_dir: Path,
    profile: str = "lower_relax_evt24_conservative_v1",
    output_name: str = "rebound_postprocessor.json",
) -> dict[str, Any]:
    """Fit one explicit rebound postprocessor on the train-side daily payload.

    The profile is deliberately explicit. We do not search an unconstrained
    space here, because the user asked for a robust path, not another hidden
    optimizer. The chosen profile name documents why the behavior exists and
    where it is meant to be used.
    """

    model_root = Path(model_dir).resolve()
    dataset_root = Path(dataset_dir).resolve()
    profile_payload = _resolve_profile(profile)
    daily_df = _build_daily_rebound_training_frame(model_dir=model_root, dataset_dir=dataset_root)

    train_daily = daily_df.loc[~daily_df["is_holdout_run"]].copy()
    if train_daily.empty:
        raise ValueError("[thermflex_hourly_mechanism] rebound postprocessor cannot fit without train-side days.")

    neg_deadband = float(profile_payload["negative_trigger_deadband_kwh"])
    pos_deadband = float(profile_payload["positive_accumulation_deadband_kwh"])
    train_daily["rebound_postprocessed_raw_kwh"] = train_daily["predicted_diff_series"].apply(
        lambda diff: _rebound_after_reduction_with_deadbands(
            np.asarray(diff, dtype=float),
            negative_trigger_deadband_kwh=neg_deadband,
            positive_accumulation_deadband_kwh=pos_deadband,
        )
    )
    scale = _fit_scale_through_origin(
        raw_pred=train_daily["rebound_postprocessed_raw_kwh"].to_numpy(dtype=float),
        true_rebound=train_daily["thermflex_rebound_kwh_true"].to_numpy(dtype=float),
    )
    train_daily["rebound_postprocessed_scaled_kwh"] = scale * train_daily["rebound_postprocessed_raw_kwh"]

    payload = {
        "type": "deadband_scaled_rebound_v1",
        "profile": profile,
        "negative_trigger_deadband_kwh": neg_deadband,
        "positive_accumulation_deadband_kwh": pos_deadband,
        "scale": float(scale),
        "fit_summary": {
            "n_train_days": int(len(train_daily)),
            "train_mae_kwh": float(
                mean_absolute_error(
                    train_daily["thermflex_rebound_kwh_true"].to_numpy(dtype=float),
                    train_daily["rebound_postprocessed_scaled_kwh"].to_numpy(dtype=float),
                )
            ),
        },
    }
    output_path = model_root / output_name
    output_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return {
        "payload": payload,
        "output_path": output_path,
    }


def fit_daily_xgb_rebound_postprocessor(
    *,
    model_dir: Path,
    dataset_dir: Path,
    profile: str = "upper_only_rebound_daily_state_xgb_v1",
    output_name: str = "rebound_postprocessor.json",
) -> dict[str, Any]:
    """Fit an explicit daily rebound calibrator for real-positive rebound regimes.

    This is intentionally separate from the lower-relax deadband profile. The
    upper-only failure observed in the dense truth slice is not false activation
    of a zero-rebound day; the raw hourly reconstruction instead keeps too
    little positive rebound mass. A daily model on the persisted train split is
    therefore the closer analogue to the successful shifted-heat postprocessor.
    """

    model_root = Path(model_dir).resolve()
    dataset_root = Path(dataset_dir).resolve()
    profile_payload = _resolve_profile(profile)
    base_result = evaluate_holdout_daily_reaggregation(model_dir=model_root, dataset_dir=dataset_root)
    daily_df = _build_all_daily_frame_with_holdout_flag(
        model_dir=model_root,
        dataset_dir=dataset_root,
        holdout_daily=base_result["daily_df"],
    )
    train_side = daily_df.loc[~daily_df["is_holdout_run"]].copy()
    if train_side.empty:
        raise ValueError("[thermflex_hourly_mechanism] rebound postprocessor cannot fit without train-side days.")

    feature_columns = tuple(str(value) for value in profile_payload["feature_columns"])
    missing = sorted(set(feature_columns).difference(train_side.columns))
    if missing:
        raise KeyError(
            "[thermflex_hourly_mechanism] rebound postprocessor train frame missing features: "
            + ", ".join(missing)
        )
    if "thermflex_rebound_kwh_true" not in train_side.columns:
        raise KeyError("[thermflex_hourly_mechanism] rebound postprocessor train frame missing true rebound target.")

    model = XGBRegressor(**profile_payload["model_params"])
    model.fit(
        train_side.loc[:, feature_columns].to_numpy(dtype=float),
        train_side["thermflex_rebound_kwh_true"].to_numpy(dtype=float),
    )
    train_pred = model.predict(train_side.loc[:, feature_columns].to_numpy(dtype=float))
    model_path = model_root / "rebound_postprocessor.joblib"
    dump(model, model_path)
    payload = {
        "type": "daily_xgb_rebound_v1",
        "profile": profile,
        "feature_columns": list(feature_columns),
        "model_path": str(model_path),
        "fit_summary": {
            "n_train_days": int(len(train_side)),
            "train_mae_kwh": float(
                mean_absolute_error(
                    train_side["thermflex_rebound_kwh_true"].to_numpy(dtype=float),
                    np.asarray(train_pred, dtype=float),
                )
            ),
        },
    }
    output_path = model_root / output_name
    output_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return {"payload": payload, "output_path": output_path, "model_path": model_path}


def fit_two_stage_daily_rebound_postprocessor(
    *,
    model_dir: Path,
    dataset_dir: Path,
    profile: str = "upper_only_rebound_twostage_sequence_et_v1",
    output_name: str = "rebound_postprocessor.json",
) -> dict[str, Any]:
    """Fit an explicit active-vs-zero plus active-mass rebound postprocessor.

    Upper-only has two observed rebound errors:
    - false-active zero-rebound days caused by an early predicted negative
      trigger, and
    - real active-rebound days where the positive mass after the trigger is too
      small or shifted.

    This postprocessor keeps those two decisions separate. It fits only on the
    persisted train side of the hourly model split and remains opt-in through
    the saved payload.
    """

    model_root = Path(model_dir).resolve()
    dataset_root = Path(dataset_dir).resolve()
    profile_payload = _resolve_profile(profile)
    base_result = evaluate_holdout_daily_reaggregation(model_dir=model_root, dataset_dir=dataset_root)
    daily_df = _build_all_daily_frame_with_holdout_flag(
        model_dir=model_root,
        dataset_dir=dataset_root,
        holdout_daily=base_result["daily_df"],
    )
    train_side = daily_df.loc[~daily_df["is_holdout_run"]].copy()
    if train_side.empty:
        raise ValueError("[thermflex_hourly_mechanism] rebound two-stage postprocessor needs train-side days.")
    feature_columns = tuple(str(value) for value in profile_payload["feature_columns"])
    missing = sorted(set(feature_columns).difference(train_side.columns))
    if missing:
        raise KeyError(
            "[thermflex_hourly_mechanism] rebound two-stage train frame missing features: "
            + ", ".join(missing)
        )
    y_active = (train_side["thermflex_rebound_kwh_true"].to_numpy(dtype=float) >= 1.0).astype(int)
    if len(set(y_active.tolist())) < 2:
        raise ValueError(
            "[thermflex_hourly_mechanism] rebound two-stage classifier needs both active and zero train days."
        )
    x_train = train_side.loc[:, feature_columns].to_numpy(dtype=float)
    classifier = ExtraTreesClassifier(**profile_payload["classifier_params"])
    classifier.fit(x_train, y_active)

    active_train = train_side.loc[y_active == 1].copy()
    if active_train.empty:
        raise ValueError("[thermflex_hourly_mechanism] rebound two-stage regressor needs active train days.")
    regressor = ExtraTreesRegressor(**profile_payload["regressor_params"])
    regressor.fit(
        active_train.loc[:, feature_columns].to_numpy(dtype=float),
        active_train["thermflex_rebound_kwh_true"].to_numpy(dtype=float),
    )
    classifier_path = model_root / "rebound_active_classifier.joblib"
    regressor_path = model_root / "rebound_active_regressor.joblib"
    dump(classifier, classifier_path)
    dump(regressor, regressor_path)

    train_active_probability = classifier.predict_proba(x_train)[:, 1]
    train_pred = np.where(
        train_active_probability >= float(profile_payload["active_probability_threshold"]),
        np.maximum(0.0, regressor.predict(x_train)),
        0.0,
    )
    payload = {
        "type": "two_stage_daily_rebound_v1",
        "profile": profile,
        "feature_columns": list(feature_columns),
        "classifier_model_path": str(classifier_path),
        "regressor_model_path": str(regressor_path),
        "active_probability_threshold": float(profile_payload["active_probability_threshold"]),
        "fit_summary": {
            "n_train_days": int(len(train_side)),
            "n_train_active_days": int(np.sum(y_active)),
            "train_mae_kwh": float(
                mean_absolute_error(
                    train_side["thermflex_rebound_kwh_true"].to_numpy(dtype=float),
                    train_pred,
                )
            ),
        },
    }
    output_path = model_root / output_name
    output_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return {
        "payload": payload,
        "output_path": output_path,
        "classifier_model_path": classifier_path,
        "regressor_model_path": regressor_path,
    }


def fit_rebound_postprocessor(
    *,
    model_dir: Path,
    dataset_dir: Path,
    profile: str,
    output_name: str = "rebound_postprocessor.json",
) -> dict[str, Any]:
    """Fit one named rebound postprocessor without silently changing semantics."""

    profile_type = _resolve_profile(profile)["type"]
    if profile_type == "deadband_scaled_rebound_v1":
        return fit_deadband_scaled_rebound_postprocessor(
            model_dir=model_dir,
            dataset_dir=dataset_dir,
            profile=profile,
            output_name=output_name,
        )
    if profile_type == "daily_xgb_rebound_v1":
        return fit_daily_xgb_rebound_postprocessor(
            model_dir=model_dir,
            dataset_dir=dataset_dir,
            profile=profile,
            output_name=output_name,
        )
    if profile_type == "two_stage_daily_rebound_v1":
        return fit_two_stage_daily_rebound_postprocessor(
            model_dir=model_dir,
            dataset_dir=dataset_dir,
            profile=profile,
            output_name=output_name,
        )
    raise ValueError(f"[thermflex_hourly_mechanism] unsupported rebound postprocessor type: {profile_type}")


def evaluate_holdout_with_rebound_postprocessor(
    *,
    model_dir: Path,
    dataset_dir: Path,
    rebound_postprocessor_path: Path,
) -> dict[str, Any]:
    payload = json.loads(Path(rebound_postprocessor_path).read_text(encoding="utf-8"))
    return evaluate_holdout_daily_reaggregation(
        model_dir=Path(model_dir).resolve(),
        dataset_dir=Path(dataset_dir).resolve(),
        rebound_postprocessor=payload,
    )


def _resolve_profile(profile: str) -> dict[str, Any]:
    key = str(profile).strip().lower()
    if key == "lower_relax_evt24_conservative_v1":
        return {
            "type": "deadband_scaled_rebound_v1",
            "negative_trigger_deadband_kwh": 25_000.0,
            "positive_accumulation_deadband_kwh": 0.0,
        }
    if key == "upper_only_rebound_daily_state_xgb_v1":
        return {
            "type": "daily_xgb_rebound_v1",
            "feature_columns": UPPER_ONLY_REBOUND_FEATURE_COLUMNS,
            "model_params": {
                "n_estimators": 300,
                "max_depth": 2,
                "learning_rate": 0.04,
                "subsample": 0.9,
                "colsample_bytree": 0.8,
                "min_child_weight": 3,
                "reg_lambda": 2.0,
                "objective": "reg:squarederror",
                "random_state": 42,
                "n_jobs": 1,
            },
        }
    if key == "upper_only_rebound_daily_tau4_state_xgb_v1":
        return {
            "type": "daily_xgb_rebound_v1",
            "feature_columns": tuple(TAU4_SHIFTED_STATE_FEATURE_COLUMNS),
            "model_params": {
                "n_estimators": 300,
                "max_depth": 2,
                "learning_rate": 0.04,
                "subsample": 0.9,
                "colsample_bytree": 0.8,
                "min_child_weight": 3,
                "reg_lambda": 2.0,
                "objective": "reg:squarederror",
                "random_state": 42,
                "n_jobs": 1,
            },
        }
    if key == "upper_only_rebound_twostage_sequence_et_v1":
        return {
            "type": "two_stage_daily_rebound_v1",
            "feature_columns": UPPER_ONLY_REBOUND_SEQUENCE_FEATURE_COLUMNS,
            "active_probability_threshold": 0.50,
            "classifier_params": {
                "n_estimators": 300,
                "max_depth": 4,
                "min_samples_leaf": 2,
                "random_state": 42,
                "n_jobs": 1,
                "class_weight": "balanced",
            },
            "regressor_params": {
                "n_estimators": 500,
                "max_depth": 5,
                "min_samples_leaf": 2,
                "random_state": 42,
                "n_jobs": 1,
            },
        }
    raise ValueError(f"[thermflex_hourly_mechanism] unsupported rebound postprocessor profile: {profile}")


def _fit_scale_through_origin(*, raw_pred: np.ndarray, true_rebound: np.ndarray) -> float:
    """Fit one conservative scalar on the train-side daily rebound payload.

    Why through-origin:
    - a rebound postprocessor that predicts nonzero rebound for a zero raw
      signal would defeat the entire purpose of the conservative gate,
    - therefore only multiplicative scaling is allowed.
    """

    x = np.asarray(raw_pred, dtype=float).reshape(-1)
    y = np.asarray(true_rebound, dtype=float).reshape(-1)
    denominator = float(np.sum(np.square(x)))
    if denominator <= 1e-12:
        return 1.0
    return float(np.sum(x * y) / denominator)


def _build_daily_rebound_training_frame(*, model_dir: Path, dataset_dir: Path) -> pd.DataFrame:
    """Build one per-day rebound frame from the persisted hourly base model.

    The frame keeps both the train/test run membership and the per-day predicted
    difference series so the postprocessor can be fit only on the train side and
    later re-applied on holdout.
    """

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
            "[thermflex_hourly_mechanism] rebound postprocessor currently requires "
            "`cohort_q_delta_wh_per_m2` in the base model targets."
        )

    raw_feature_frame = truth.loc[:, numeric_feature_columns + categorical_feature_columns].copy()
    encoded = pd.get_dummies(
        raw_feature_frame,
        columns=categorical_feature_columns,
        dtype=float,
    )
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
            true_diff = q_true.to_numpy(dtype=float) - q_ref_series.to_numpy(dtype=float)
            pred_diff = q_pred.to_numpy(dtype=float) - q_ref_series.to_numpy(dtype=float)
            rows.append(
                {
                    "run_dir": str(run_dir),
                    "day": pd.Timestamp(day_ts),
                    "is_holdout_run": str(run_dir) in holdout_groups,
                    "thermflex_rebound_kwh_true": _rebound_after_reduction_with_deadbands(
                        true_diff,
                        negative_trigger_deadband_kwh=1e-9,
                        positive_accumulation_deadband_kwh=1e-9,
                    ),
                    "thermflex_rebound_kwh_pred_raw": _rebound_after_reduction_with_deadbands(
                        pred_diff,
                        negative_trigger_deadband_kwh=1e-9,
                        positive_accumulation_deadband_kwh=1e-9,
                    ),
                    "predicted_diff_series": pred_diff.tolist(),
                }
            )
    return pd.DataFrame(rows)
