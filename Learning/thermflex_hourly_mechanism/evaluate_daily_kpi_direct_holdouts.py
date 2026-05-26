from __future__ import annotations

"""Evaluate direct daily ThermFlex mechanism KPI models.

The hourly mechanism model is still needed for profile figures, but the paper
tables mostly need daily KPIs such as shifted energy, rebound and peak change.
The raw hourly re-aggregation diagnostics showed that these daily KPI metrics
can fail even when hourly `q_delta` is partially learned. This diagnostic tests
the complementary path: learn the daily KPIs directly from ex-ante policy,
weather, price, reference-load and cohort-composition features.

No production model is registered here. The output is a persisted diagnostic
used to decide whether daily tables should use a family-aware direct KPI layer
while hourly figures keep using the hourly mechanism path.
"""

import argparse
import json
import re
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from sklearn.ensemble import ExtraTreesClassifier
from sklearn.ensemble import ExtraTreesRegressor
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from xgboost import XGBRegressor

from dispatch.metrics import compute_thermflex_series_metrics
from Learning.datasets.load_dataset import load_dataset
from Learning.thermflex_hourly_mechanism.train import _apply_target_transform, _invert_target_transform
from Learning.thermflex_hourly_mechanism.validate import build_grouped_holdout_split
from Optimization.run.analysis.dh_thermflex_inputs import load_vienna_dh_thermflex_full_year_context

_DEFAULT_DATASET_ROOT = Path(__file__).resolve().parents[2] / "Learning" / "datasets"
_DEFAULT_MODEL_ROOT = Path(__file__).resolve().parents[2] / "Learning" / "models"
_TARGET_COLUMNS = (
    "q_delta_sum_kwh",
    "shifted_kwh",
    "rebound_kwh",
    "peak_change_kw",
)
_COHORT_KEYS = (
    "non_residential_1975_1990",
    "non_residential_1990_2000",
    "non_residential_2000_2014",
    "non_residential_pre1975",
    "residential_1975_1990",
    "residential_1990_2000",
    "residential_2000_2014",
    "residential_pre1975",
)
_ARCHETYPE_RESPONSE_FEATURE_COLUMNS = (
    "archetype_preheat_added_energy_kwh",
    "archetype_preheat_peak_excess_kw",
    "archetype_cutback_shed_energy_kwh",
    "archetype_cutback_peak_shed_kw",
    "archetype_recovery_rebound_energy_kwh",
    "archetype_recovery_peak_rebound_kw",
    "archetype_recovery_time_to_reference_h",
    "archetype_fitted_tau_h",
    "archetype_fitted_total_loss_w_per_m2k",
    "archetype_fitted_effective_heat_capacity_wh_per_m2k",
)


@dataclass(frozen=True)
class DirectDailyKpiResult:
    diagnostic_dir: Path
    metrics_csv: Path
    predictions_csv: Path
    feature_names_json: Path
    summary_json: Path


def evaluate_daily_kpi_direct_holdouts(
    *,
    family_hash: str,
    dataset_root: Path = _DEFAULT_DATASET_ROOT,
    model_root: Path = _DEFAULT_MODEL_ROOT,
    group_column: str = "run_dir",
    test_size: float = 0.25,
    split_strategy: str = "group_shuffle",
    stratify_column: str | None = None,
    first_seed: int = 0,
    n_seeds: int = 10,
    estimator: str = "extra_trees",
    rebound_gate_threshold_kwh: float | None = None,
    rebound_two_stage_threshold_kwh: float | None = None,
    feature_preset: str = "all",
    output_name: str | None = None,
) -> DirectDailyKpiResult:
    """Train repeated direct daily KPI holdouts and persist slice diagnostics."""

    dataset_bundle = load_dataset(Path(dataset_root), family_hash)
    if dataset_bundle is None:
        raise FileNotFoundError(
            "[thermflex_hourly_mechanism] curated dataset not found for family_hash="
            + str(family_hash)
        )
    truth_csv_path = dataset_bundle.get("truth_csv_path")
    if truth_csv_path is None:
        raise FileNotFoundError("[thermflex_hourly_mechanism] curated dataset is missing truth_dataset.csv.")

    truth_df = pd.read_csv(truth_csv_path)
    truth_df["timestamp"] = pd.to_datetime(truth_df["timestamp"], errors="raise")
    daily_df = build_daily_mechanism_kpi_frame(truth_df)
    if group_column not in daily_df.columns:
        raise KeyError(f"[thermflex_hourly_mechanism] group column not found in daily frame: {group_column}")
    if len(set(daily_df[group_column].astype(str))) < 3:
        raise ValueError("[thermflex_hourly_mechanism] direct daily holdouts require at least three split groups.")

    feature_names = _feature_columns(daily_df, preset=feature_preset)
    x_all = daily_df.loc[:, feature_names].to_numpy(dtype=float)
    y_all = daily_df.loc[:, list(_TARGET_COLUMNS)].to_numpy(dtype=float)
    groups = daily_df[group_column].astype(str).to_numpy()

    metric_rows: list[dict[str, Any]] = []
    prediction_frames: list[pd.DataFrame] = []
    for seed in range(int(first_seed), int(first_seed) + int(n_seeds)):
        split = build_grouped_holdout_split(
            truth_df=daily_df,
            group_column=group_column,
            test_size=test_size,
            random_state=seed,
            split_strategy=split_strategy,
            stratify_column=stratify_column,
        )
        train_index = np.asarray(split.train_index, dtype=int)
        test_index = np.asarray(split.test_index, dtype=int)
        y_pred = _fit_predict(
            estimator=estimator,
            x_train=x_all[train_index],
            y_train=y_all[train_index],
            x_test=x_all[test_index],
            random_state=seed,
            rebound_gate_threshold_kwh=rebound_gate_threshold_kwh,
            rebound_two_stage_threshold_kwh=rebound_two_stage_threshold_kwh,
        )
        holdout = daily_df.iloc[test_index].copy()
        pred_df = _prediction_frame(seed=seed, holdout=holdout, y_pred=y_pred)
        prediction_frames.append(pred_df)
        _append_metrics(rows=metric_rows, seed=seed, predictions=pred_df)

    diagnostic_dir = _diagnostic_dir(
        model_root=Path(model_root),
        family_hash=family_hash,
        estimator=estimator,
        output_name=output_name,
    )
    diagnostic_dir.mkdir(parents=True, exist_ok=True)
    metrics_csv = diagnostic_dir / "direct_daily_kpi_metrics.csv"
    predictions_csv = diagnostic_dir / "direct_daily_kpi_predictions.csv"
    feature_names_json = diagnostic_dir / "feature_names.json"
    summary_json = diagnostic_dir / "summary.json"

    metrics_df = pd.DataFrame(metric_rows)
    predictions_df = pd.concat(prediction_frames, ignore_index=True)
    metrics_df.to_csv(metrics_csv, index=False)
    predictions_df.to_csv(predictions_csv, index=False)
    feature_names_json.write_text(json.dumps({"feature_names": feature_names}, indent=2), encoding="utf-8")
    summary_payload = {
        "family_hash": str(family_hash),
        "dataset_id": str(dataset_bundle["meta"].get("dataset_id", "")),
        "family_slice": str(dataset_bundle["meta"].get("family_slice", "")),
        "feature_mode": str(dataset_bundle["meta"].get("feature_mode", "")),
        "estimator": str(estimator),
        "rebound_gate_threshold_kwh": (
            None if rebound_gate_threshold_kwh is None else float(rebound_gate_threshold_kwh)
        ),
        "rebound_two_stage_threshold_kwh": (
            None if rebound_two_stage_threshold_kwh is None else float(rebound_two_stage_threshold_kwh)
        ),
        "feature_preset": str(feature_preset),
        "group_column": str(group_column),
        "split_strategy": str(split_strategy),
        "stratify_column": None if stratify_column is None else str(stratify_column),
        "test_size": float(test_size),
        "first_seed": int(first_seed),
        "n_seeds": int(n_seeds),
        "n_daily_rows": int(len(daily_df)),
        "n_groups": int(daily_df[group_column].nunique()),
        "target_columns": list(_TARGET_COLUMNS),
        "summary": _summarize(metrics_df, group_cols=["slice_scope", "slice_value", "target"]),
    }
    summary_json.write_text(json.dumps(summary_payload, indent=2), encoding="utf-8")
    return DirectDailyKpiResult(
        diagnostic_dir=diagnostic_dir,
        metrics_csv=metrics_csv,
        predictions_csv=predictions_csv,
        feature_names_json=feature_names_json,
        summary_json=summary_json,
    )


def build_daily_mechanism_kpi_frame(hourly_truth: pd.DataFrame) -> pd.DataFrame:
    """Aggregate cohort-hour truth to one ex-ante-feature and KPI row per day."""

    _validate_hourly_truth_columns(hourly_truth)
    df = hourly_truth.copy()
    df["timestamp"] = pd.to_datetime(df["timestamp"], errors="raise")
    df["day"] = df["timestamp"].dt.floor("D")
    rows: list[dict[str, Any]] = []
    for (run_dir, day_ts), day_df in df.groupby(["run_dir", "day"], sort=True):
        q_ref = day_df.groupby("timestamp")["cohort_q_heat_ref_kwh"].sum().sort_index()
        q_true = day_df.groupby("timestamp")["cohort_q_heat_kwh"].sum().sort_index()
        metrics = compute_thermflex_series_metrics(q_true, q_ref)
        row: dict[str, Any] = {
            "run_dir": str(run_dir),
            "day": pd.Timestamp(day_ts).date().isoformat(),
            "source_bundle_name": str(day_df["source_bundle_name"].iloc[0]),
            "case_label": str(day_df["case_label"].iloc[0]),
            "policy_family": _policy_family(day_df),
            "policy_tau_h": _constant_numeric(day_df, "policy_tau_h"),
            "duration_h": _constant_numeric(day_df, "thermflex_max_flex_duration_h"),
            "max_events_per_day": _constant_numeric(day_df, "thermflex_max_events_per_day"),
            "lower_band_k": _lower_band(day_df),
            "upper_constrained": _constant_numeric(day_df, "thermflex_constrain_upper_temperature"),
            "month": float(pd.Timestamp(day_ts).month),
            "day_of_year": float(pd.Timestamp(day_ts).dayofyear),
            "weather_month_regime": _weather_month_regime(pd.Timestamp(day_ts).month),
            "temperature_bin": _temperature_bin(float(pd.to_numeric(day_df["t_outdoor_c"], errors="raise").mean())),
            "q_delta_sum_kwh": float(pd.to_numeric(day_df["cohort_q_delta_kwh"], errors="raise").sum()),
            "shifted_kwh": float(metrics["thermflex_shifted_space_heat_kwh"]),
            "rebound_kwh": float(metrics["thermflex_rebound_kwh"]),
            "peak_change_kw": float(metrics["thermflex_peak_change_kw"]),
        }
        row.update(_daily_context_features(day_ts=pd.Timestamp(day_ts), day_df=day_df, q_ref=q_ref))
        row.update(_hourly_profile_features(day_df=day_df, q_ref=q_ref))
        row.update(_cohort_composition_features(day_df))
        rows.append(row)
    daily = pd.DataFrame(rows).sort_values(["run_dir", "day"]).reset_index(drop=True)
    _validate_daily_feature_frame(daily)
    return daily


def _fit_predict(
    *,
    estimator: str,
    x_train: np.ndarray,
    y_train: np.ndarray,
    x_test: np.ndarray,
    random_state: int,
    rebound_gate_threshold_kwh: float | None,
    rebound_two_stage_threshold_kwh: float | None,
) -> np.ndarray:
    key = str(estimator).strip().lower()
    if key == "extra_trees":
        model = ExtraTreesRegressor(
            n_estimators=600,
            max_features=0.85,
            min_samples_leaf=1,
            random_state=int(random_state),
            n_jobs=1,
        )
        model.fit(x_train, y_train)
        return _postprocess_predictions(
            y_pred=np.asarray(model.predict(x_test), dtype=float),
            x_train=x_train,
            y_train=y_train,
            x_test=x_test,
            random_state=random_state,
            rebound_gate_threshold_kwh=rebound_gate_threshold_kwh,
            rebound_two_stage_threshold_kwh=rebound_two_stage_threshold_kwh,
        )
    if key == "xgb":
        columns: list[np.ndarray] = []
        for target_index, target_name in enumerate(_TARGET_COLUMNS):
            transform = _target_transform(target_name)
            model = XGBRegressor(
                n_estimators=300,
                max_depth=2,
                learning_rate=0.04,
                subsample=0.9,
                colsample_bytree=0.9,
                reg_lambda=2.0,
                objective="reg:squarederror",
                random_state=int(random_state),
                n_jobs=1,
            )
            model.fit(x_train, _apply_target_transform(y_train[:, target_index], transform))
            columns.append(_invert_target_transform(model.predict(x_test), transform))
        return _postprocess_predictions(
            y_pred=np.column_stack(columns),
            x_train=x_train,
            y_train=y_train,
            x_test=x_test,
            random_state=random_state,
            rebound_gate_threshold_kwh=rebound_gate_threshold_kwh,
            rebound_two_stage_threshold_kwh=rebound_two_stage_threshold_kwh,
        )
    raise ValueError(f"[thermflex_hourly_mechanism] unsupported estimator: {estimator}")


def _postprocess_predictions(
    *,
    y_pred: np.ndarray,
    x_train: np.ndarray,
    y_train: np.ndarray,
    x_test: np.ndarray,
    random_state: int,
    rebound_gate_threshold_kwh: float | None,
    rebound_two_stage_threshold_kwh: float | None,
) -> np.ndarray:
    """Apply explicit physical nonnegativity and optional rebound activation gate."""

    pred = np.asarray(y_pred, dtype=float).copy()
    for target_name in ("shifted_kwh", "rebound_kwh"):
        pred[:, _TARGET_COLUMNS.index(target_name)] = np.maximum(0.0, pred[:, _TARGET_COLUMNS.index(target_name)])
    if rebound_two_stage_threshold_kwh is not None:
        return _apply_rebound_two_stage(
            pred=pred,
            x_train=x_train,
            y_train=y_train,
            x_test=x_test,
            random_state=random_state,
            rebound_two_stage_threshold_kwh=rebound_two_stage_threshold_kwh,
        )
    if rebound_gate_threshold_kwh is None:
        return pred
    threshold = float(rebound_gate_threshold_kwh)
    if threshold < 0.0:
        raise ValueError("[thermflex_hourly_mechanism] rebound gate threshold must be nonnegative.")
    rebound_idx = _TARGET_COLUMNS.index("rebound_kwh")
    active = (y_train[:, rebound_idx] > threshold).astype(int)
    if len(set(active.tolist())) < 2:
        return pred
    classifier = ExtraTreesClassifier(
        n_estimators=400,
        max_features=0.85,
        min_samples_leaf=1,
        random_state=int(random_state),
        n_jobs=1,
    )
    classifier.fit(x_train, active)
    active_probability = classifier.predict_proba(x_test)[:, 1]
    pred[active_probability < 0.5, rebound_idx] = 0.0
    return pred


def _apply_rebound_two_stage(
    *,
    pred: np.ndarray,
    x_train: np.ndarray,
    y_train: np.ndarray,
    x_test: np.ndarray,
    random_state: int,
    rebound_two_stage_threshold_kwh: float,
) -> np.ndarray:
    """Replace rebound prediction with an explicit active-classifier + active-regressor.

    Rebound has a different error structure than shifted and peak: false
    positives on true zero-rebound days dominate some holdouts. This optional
    diagnostic therefore treats rebound as a hurdle problem. It is deliberately
    fail-fast when the train split lacks both active and inactive examples,
    because otherwise the result would silently collapse to the baseline path.
    """

    threshold = float(rebound_two_stage_threshold_kwh)
    if threshold < 0.0:
        raise ValueError("[thermflex_hourly_mechanism] rebound two-stage threshold must be nonnegative.")
    rebound_idx = _TARGET_COLUMNS.index("rebound_kwh")
    active = (y_train[:, rebound_idx] > threshold).astype(int)
    active_count = int(active.sum())
    inactive_count = int(active.size - active_count)
    if active_count < 2 or inactive_count < 2:
        raise ValueError(
            "[thermflex_hourly_mechanism] rebound two-stage diagnostic needs at least two active "
            f"and two inactive train days; got active={active_count}, inactive={inactive_count}."
        )
    classifier = ExtraTreesClassifier(
        n_estimators=500,
        max_features=0.85,
        min_samples_leaf=1,
        random_state=int(random_state),
        n_jobs=1,
    )
    classifier.fit(x_train, active)
    regressor = ExtraTreesRegressor(
        n_estimators=500,
        max_features=0.85,
        min_samples_leaf=1,
        random_state=int(random_state),
        n_jobs=1,
    )
    regressor.fit(x_train[active == 1], y_train[active == 1, rebound_idx])
    active_probability = classifier.predict_proba(x_test)[:, 1]
    rebound_pred = np.maximum(0.0, np.asarray(regressor.predict(x_test), dtype=float))
    pred[:, rebound_idx] = np.where(active_probability >= 0.5, rebound_pred, 0.0)
    return pred


def _prediction_frame(*, seed: int, holdout: pd.DataFrame, y_pred: np.ndarray) -> pd.DataFrame:
    pred_df = holdout.loc[
        :,
        [
            "run_dir",
            "day",
            "source_bundle_name",
            "case_label",
            "policy_family",
            "policy_tau_h",
            "duration_h",
            "lower_band_k",
            "weather_month_regime",
            "temperature_bin",
            *_TARGET_COLUMNS,
        ],
    ].copy()
    pred_df.insert(0, "seed", int(seed))
    for target_index, target in enumerate(_TARGET_COLUMNS):
        pred_df[f"{target}_pred"] = y_pred[:, target_index]
    return pred_df


def _append_metrics(*, rows: list[dict[str, Any]], seed: int, predictions: pd.DataFrame) -> None:
    slice_specs = {
        "ALL": pd.Series("ALL", index=predictions.index),
        "policy_family": predictions["policy_family"].astype(str),
        "tau": "tau" + pd.to_numeric(predictions["policy_tau_h"], errors="raise").round(0).astype(int).astype(str),
        "duration": "dur" + pd.to_numeric(predictions["duration_h"], errors="raise").round(0).astype(int).astype(str),
        "tau_duration": (
            "tau"
            + pd.to_numeric(predictions["policy_tau_h"], errors="raise").round(0).astype(int).astype(str)
            + "_dur"
            + pd.to_numeric(predictions["duration_h"], errors="raise").round(0).astype(int).astype(str)
        ),
        "weather_month_regime": predictions["weather_month_regime"].astype(str),
        "temperature_bin": predictions["temperature_bin"].astype(str),
    }
    for slice_scope, labels in slice_specs.items():
        for slice_value in sorted(labels.astype(str).unique()):
            mask = labels.astype(str).to_numpy() == str(slice_value)
            for target in _TARGET_COLUMNS:
                rows.append(
                    {
                        "seed": int(seed),
                        "slice_scope": str(slice_scope),
                        "slice_value": str(slice_value),
                        "target": str(target),
                        **_metric_payload(
                            predictions.loc[mask, target].to_numpy(dtype=float),
                            predictions.loc[mask, f"{target}_pred"].to_numpy(dtype=float),
                        ),
                        "n_test_days": int(np.sum(mask)),
                        "n_test_runs": int(predictions.loc[mask, "run_dir"].nunique()),
                    }
                )


def _daily_context_features(*, day_ts: pd.Timestamp, day_df: pd.DataFrame, q_ref: pd.Series) -> dict[str, float]:
    temp = pd.to_numeric(day_df["t_outdoor_c"], errors="raise")
    q_ref_sum = float(q_ref.sum())
    if q_ref_sum <= 0.0:
        raise ValueError("[thermflex_hourly_mechanism] direct daily features require positive reference heat.")
    dh_space = float(pd.to_numeric(day_df["dh_space_heat_kwh"], errors="raise").sum())
    dh_total = float(pd.to_numeric(day_df["dh_total_kwh"], errors="raise").sum())
    if dh_space <= 0.0 or dh_total <= 0.0:
        raise ValueError("[thermflex_hourly_mechanism] direct daily features require positive DH context.")
    day_of_year = float(day_ts.dayofyear)
    angle = (2.0 * np.pi * day_of_year) / 365.0
    return {
        "day_of_year_sin": float(np.sin(angle)),
        "day_of_year_cos": float(np.cos(angle)),
        "t_outdoor_mean_c": float(temp.mean()),
        "t_outdoor_min_c": float(temp.min()),
        "t_outdoor_max_c": float(temp.max()),
        "t_outdoor_range_c": float(temp.max() - temp.min()),
        "irradiance_proxy_sum": float(pd.to_numeric(day_df["irradiance_proxy"], errors="raise").sum()),
        "solargains_proxy_sum": float(pd.to_numeric(day_df["solargains_proxy"], errors="raise").sum()),
        "mc_auction_eur_mwh_mean": float(pd.to_numeric(day_df["mc_auction_eur_mwh"], errors="raise").mean()),
        "mc_auction_eur_mwh_min": float(pd.to_numeric(day_df["mc_auction_eur_mwh"], errors="raise").min()),
        "mc_auction_eur_mwh_max": float(pd.to_numeric(day_df["mc_auction_eur_mwh"], errors="raise").max()),
        "gas_price_eur_mwh_fuel_mean": float(pd.to_numeric(day_df["gas_price_eur_mwh_fuel"], errors="raise").mean()),
        "co2_price_eur_tco2_mean": float(pd.to_numeric(day_df["co2_price_eur_tco2"], errors="raise").mean()),
        "space_heat_kwh_sum": float(pd.to_numeric(day_df["space_heat_kwh"], errors="raise").sum()),
        "hotwater_kwh_sum": float(pd.to_numeric(day_df["hotwater_kwh"], errors="raise").sum()),
        "dh_space_heat_kwh_sum": dh_space,
        "dh_total_kwh_sum": dh_total,
        "q_ref_sum_kwh": q_ref_sum,
        "q_ref_peak_kw": float(q_ref.max()),
        "q_ref_min_kw": float(q_ref.min()),
        "q_ref_range_kw": float(q_ref.max() - q_ref.min()),
        "dh_per_q_ref": float(dh_space / q_ref_sum),
        "space_heat_per_q_ref": float(pd.to_numeric(day_df["space_heat_kwh"], errors="raise").sum() / q_ref_sum),
        **_prior_context_features(day_ts=pd.Timestamp(day_ts)),
    }


@lru_cache(maxsize=1)
def _full_year_system_context() -> pd.DataFrame:
    """Load canonical Vienna full-year hourly context once for state features."""

    context = load_vienna_dh_thermflex_full_year_context()
    hourly = context.hourly_system_df.copy()
    hourly["timestamp"] = pd.to_datetime(hourly["timestamp"], errors="raise")
    hourly = hourly.sort_values("timestamp").set_index("timestamp")
    required = {
        "t_outdoor_c",
        "irradiance_proxy",
        "solargains_proxy",
        "dh_space_heat_total_kwh",
        "dh_total_kwh",
    }
    missing = sorted(required.difference(hourly.columns))
    if missing:
        raise KeyError("[thermflex_hourly_mechanism] full-year context missing columns: " + ", ".join(missing))
    return hourly


def _prior_context_features(*, day_ts: pd.Timestamp) -> dict[str, float]:
    """Approximate thermal initial state from pre-day weather and load history.

    Upper-only preheat/rebound depends strongly on where the building state is
    at midnight. The selected day itself is not enough to infer that state, so
    this feature block uses only canonical full-year context before the target
    day. Windows are explicit and fail fast if a selected day lacks history.
    """

    hourly = _full_year_system_context()
    day_start = pd.Timestamp(day_ts).floor("D")
    features: dict[str, float] = {}
    for window_h in (6, 12, 24, 48, 72):
        start = day_start - pd.Timedelta(hours=window_h)
        hist = hourly.loc[(hourly.index >= start) & (hourly.index < day_start)].copy()
        prefix = f"prior_{window_h}h"
        features[f"{prefix}_coverage_share"] = float(len(hist) / float(window_h))
        if hist.empty:
            # Boundary days at the start of the canonical weather year have no
            # pre-day context. The coverage feature makes that explicit instead
            # of pretending that the zero values are physical measurements.
            features[f"{prefix}_t_outdoor_mean_c"] = 0.0
            features[f"{prefix}_t_outdoor_min_c"] = 0.0
            features[f"{prefix}_t_outdoor_max_c"] = 0.0
            features[f"{prefix}_dh_space_heat_sum_kwh"] = 0.0
            features[f"{prefix}_dh_total_sum_kwh"] = 0.0
            features[f"{prefix}_irradiance_sum"] = 0.0
            features[f"{prefix}_solargains_sum"] = 0.0
            continue
        temp = pd.to_numeric(hist["t_outdoor_c"], errors="raise")
        features[f"{prefix}_t_outdoor_mean_c"] = float(temp.mean())
        features[f"{prefix}_t_outdoor_min_c"] = float(temp.min())
        features[f"{prefix}_t_outdoor_max_c"] = float(temp.max())
        features[f"{prefix}_dh_space_heat_sum_kwh"] = float(
            pd.to_numeric(hist["dh_space_heat_total_kwh"], errors="raise").sum()
        )
        features[f"{prefix}_dh_total_sum_kwh"] = float(pd.to_numeric(hist["dh_total_kwh"], errors="raise").sum())
        features[f"{prefix}_irradiance_sum"] = float(pd.to_numeric(hist["irradiance_proxy"], errors="raise").sum())
        features[f"{prefix}_solargains_sum"] = float(pd.to_numeric(hist["solargains_proxy"], errors="raise").sum())
    return features


def _hourly_profile_features(*, day_df: pd.DataFrame, q_ref: pd.Series) -> dict[str, float]:
    """Attach ex-ante hourly profile descriptors for sequence-sensitive KPIs.

    Rebound is not a pure daily-mass target; the metric counts positive heat
    only after a prior negative deviation. The model therefore needs the known
    within-day state sequence. These features use only reference/context series
    that are already available before predicting the flexible response.
    """

    q_ref_by_hour = q_ref.copy()
    q_ref_by_hour.index = pd.to_datetime(q_ref_by_hour.index, errors="raise")
    hourly = (
        day_df.sort_values("timestamp")
        .groupby("timestamp", sort=True)
        .agg(
            t_outdoor_c=("t_outdoor_c", "first"),
            dh_space_heat_kwh=("dh_space_heat_kwh", "first"),
            dh_total_kwh=("dh_total_kwh", "first"),
            mc_auction_eur_mwh=("mc_auction_eur_mwh", "first"),
            irradiance_proxy=("irradiance_proxy", "first"),
            solargains_proxy=("solargains_proxy", "first"),
        )
    )
    hourly.index = pd.to_datetime(hourly.index, errors="raise")
    if len(hourly) != 24 or len(q_ref_by_hour) != 24:
        raise ValueError("[thermflex_hourly_mechanism] daily profile features require exactly 24 hourly timestamps.")
    hours = hourly.index.hour.to_numpy(dtype=int)
    if sorted(hours.tolist()) != list(range(24)):
        raise ValueError("[thermflex_hourly_mechanism] daily profile features require one row for each hour 0..23.")
    q_ref_by_hour = q_ref_by_hour.reindex(hourly.index)
    if q_ref_by_hour.isna().any():
        raise ValueError("[thermflex_hourly_mechanism] q_ref profile could not be aligned to hourly context.")
    features: dict[str, float] = {}
    q_ref_sum = float(q_ref_by_hour.sum())
    if q_ref_sum <= 0.0:
        raise ValueError("[thermflex_hourly_mechanism] q_ref profile sum must be positive.")
    for timestamp, context_row in hourly.iterrows():
        hour = int(pd.Timestamp(timestamp).hour)
        prefix = f"h{hour:02d}"
        q_ref_value = float(q_ref_by_hour.loc[timestamp])
        features[f"q_ref_{prefix}_kwh"] = q_ref_value
        features[f"q_ref_{prefix}_share"] = float(q_ref_value / q_ref_sum)
        features[f"t_outdoor_{prefix}_c"] = float(context_row["t_outdoor_c"])
        features[f"dh_space_{prefix}_kwh"] = float(context_row["dh_space_heat_kwh"])
        features[f"dh_total_{prefix}_kwh"] = float(context_row["dh_total_kwh"])
        features[f"mc_auction_{prefix}_eur_mwh"] = float(context_row["mc_auction_eur_mwh"])
        features[f"irradiance_{prefix}"] = float(context_row["irradiance_proxy"])
        features[f"solargains_{prefix}"] = float(context_row["solargains_proxy"])
    return features


def _cohort_composition_features(day_df: pd.DataFrame) -> dict[str, float]:
    first_by_cohort = day_df.sort_values("timestamp").groupby("cohort_key", sort=True).first()
    total_area = float(pd.to_numeric(first_by_cohort["cohort_floor_area_m2"], errors="raise").sum())
    if total_area <= 0.0:
        raise ValueError("[thermflex_hourly_mechanism] cohort floor-area total must be positive.")
    features: dict[str, float] = {"cohort_total_floor_area_m2": total_area}
    area_by_cohort: dict[str, float] = {}
    ref_heat_by_cohort: dict[str, float] = {}
    for cohort_key in _COHORT_KEYS:
        if cohort_key in first_by_cohort.index:
            area = float(pd.to_numeric(first_by_cohort.loc[cohort_key, "cohort_floor_area_m2"], errors="raise"))
            ref_sum = float(
                pd.to_numeric(
                    day_df.loc[day_df["cohort_key"].astype(str) == cohort_key, "cohort_q_heat_ref_kwh"],
                    errors="raise",
                ).sum()
            )
        else:
            area = 0.0
            ref_sum = 0.0
        area_by_cohort[cohort_key] = area
        ref_heat_by_cohort[cohort_key] = ref_sum
        features[f"cohort_area_share_{cohort_key}"] = float(area / total_area)
        features[f"cohort_ref_heat_kwh_{cohort_key}"] = float(ref_sum)
    residential_area = sum(
        features[f"cohort_area_share_{key}"] for key in _COHORT_KEYS if key.startswith("residential")
    )
    features["cohort_area_share_residential_total"] = float(residential_area)
    features["cohort_area_share_non_residential_total"] = float(1.0 - residential_area)
    features.update(
        _archetype_response_features(
            day_df=day_df,
            first_by_cohort=first_by_cohort,
            area_by_cohort=area_by_cohort,
            ref_heat_by_cohort=ref_heat_by_cohort,
            total_area=total_area,
        )
    )
    return features


def _archetype_response_features(
    *,
    day_df: pd.DataFrame,
    first_by_cohort: pd.DataFrame,
    area_by_cohort: dict[str, float],
    ref_heat_by_cohort: dict[str, float],
    total_area: float,
) -> dict[str, float]:
    """Aggregate ex-ante archetype response potentials to daily features.

    Upper-only `shifted` and `rebound` are not driven only by weather and total
    reference heat. They also depend on the thermal response envelope of the
    active cohort mix: how much preheat can be added, how much cutback can be
    shed, how large the recovery rebound is, and how slow the archetypes return
    to reference. Those columns are already part of the curated full-thermal
    hourly truth, but the previous daily KPI diagnostic threw them away during
    the cohort aggregation. This block keeps them as explicit ex-ante features.
    """

    present = [column for column in _ARCHETYPE_RESPONSE_FEATURE_COLUMNS if column in day_df.columns]
    if not present:
        return {}
    missing = sorted(set(_ARCHETYPE_RESPONSE_FEATURE_COLUMNS).difference(day_df.columns))
    if missing:
        raise KeyError(
            "[thermflex_hourly_mechanism] incomplete archetype response feature block; missing: "
            + ", ".join(missing)
        )
    total_ref_heat = float(sum(ref_heat_by_cohort.values()))
    if total_ref_heat <= 0.0:
        raise ValueError("[thermflex_hourly_mechanism] archetype response features require positive ref heat.")

    features: dict[str, float] = {}
    for column in _ARCHETYPE_RESPONSE_FEATURE_COLUMNS:
        values_by_cohort = pd.to_numeric(first_by_cohort[column], errors="raise")
        area_weighted = 0.0
        ref_weighted = 0.0
        for cohort_key, value in values_by_cohort.items():
            key = str(cohort_key)
            area = float(area_by_cohort.get(key, 0.0))
            ref_heat = float(ref_heat_by_cohort.get(key, 0.0))
            numeric_value = float(value)
            area_weighted += numeric_value * area
            ref_weighted += numeric_value * ref_heat
        features[f"{column}_area_weighted_mean"] = float(area_weighted / total_area)
        features[f"{column}_ref_heat_weighted_mean"] = float(ref_weighted / total_ref_heat)

    preheat = features["archetype_preheat_added_energy_kwh_area_weighted_mean"]
    cutback = features["archetype_cutback_shed_energy_kwh_area_weighted_mean"]
    recovery = features["archetype_recovery_rebound_energy_kwh_area_weighted_mean"]
    features["archetype_preheat_to_cutback_ratio"] = float(preheat / max(cutback, 1e-9))
    features["archetype_recovery_to_cutback_ratio"] = float(recovery / max(cutback, 1e-9))
    features["archetype_recovery_to_preheat_ratio"] = float(recovery / max(preheat, 1e-9))
    return features


def _feature_columns(frame: pd.DataFrame, *, preset: str = "all") -> list[str]:
    excluded = {
        "run_dir",
        "day",
        "source_bundle_name",
        "case_label",
        "policy_family",
        "weather_month_regime",
        "temperature_bin",
        *_TARGET_COLUMNS,
    }
    numeric_columns = [
        column
        for column in frame.columns
        if column not in excluded and pd.api.types.is_numeric_dtype(frame[column])
    ]
    if not numeric_columns:
        raise ValueError("[thermflex_hourly_mechanism] no numeric daily features were built.")
    return _apply_feature_preset(numeric_columns, preset=preset)


def _apply_feature_preset(feature_columns: list[str], *, preset: str) -> list[str]:
    """Return one explicit daily-feature subset for small-sample diagnostics.

    The upper-only mechanism slice currently has many fewer independent days
    than hourly profile features. Keeping this as an explicit evaluator option
    makes reduced-feature tests reproducible without changing the default
    training contract.
    """

    key = str(preset).strip().lower()
    include_prior_state = key.endswith("_prior_state")
    base_key = key.removesuffix("_prior_state")
    candidate_columns = [
        column for column in feature_columns if include_prior_state or not column.startswith("prior_")
    ]
    if base_key == "all":
        selected = list(candidate_columns)
    elif base_key == "no_hourly_grid":
        selected = [
            column
            for column in candidate_columns
            if not re.match(
                r"^(q_ref|t_outdoor|dh_space|dh_total|mc_auction|irradiance|solargains)_h\d\d",
                column,
            )
        ]
    elif base_key == "tiny_state":
        keep_exact = {
            "month",
            "day_of_year",
            "duration_h",
            "max_events_per_day",
            "lower_band_k",
            "upper_constrained",
            "t_outdoor_mean_c",
            "t_outdoor_min_c",
            "t_outdoor_max_c",
            "t_outdoor_range_c",
            "irradiance_proxy_sum",
            "solargains_proxy_sum",
            "space_heat_kwh_sum",
            "hotwater_kwh_sum",
            "dh_space_heat_kwh_sum",
            "dh_total_kwh_sum",
            "q_ref_sum_kwh",
            "q_ref_peak_kw",
            "q_ref_range_kw",
            "dh_per_q_ref",
            "space_heat_per_q_ref",
        }
        selected = [
            column
            for column in candidate_columns
            if column in keep_exact
            or column.startswith("prior_")
            or column.startswith("archetype_")
            or column.startswith("cohort_area_share")
        ]
    else:
        raise ValueError(
            "[thermflex_hourly_mechanism] unsupported daily feature preset: "
            f"{preset}; expected one of all, no_hourly_grid, tiny_state, "
            "or the same names suffixed with _prior_state."
        )
    if not selected:
        raise ValueError(
            "[thermflex_hourly_mechanism] daily feature preset produced no columns: "
            + str(preset)
        )
    return selected


def _validate_hourly_truth_columns(frame: pd.DataFrame) -> None:
    required = {
        "run_dir",
        "timestamp",
        "source_bundle_name",
        "case_label",
        "cohort_key",
        "cohort_floor_area_m2",
        "cohort_q_heat_kwh",
        "cohort_q_heat_ref_kwh",
        "cohort_q_delta_kwh",
        "policy_tau_h",
        "thermflex_max_flex_duration_h",
        "thermflex_max_events_per_day",
        "thermflex_constrain_upper_temperature",
        "day_thermflex_temperature_band_k",
        "night_thermflex_temperature_band_k",
        "t_outdoor_c",
        "irradiance_proxy",
        "solargains_proxy",
        "mc_auction_eur_mwh",
        "gas_price_eur_mwh_fuel",
        "co2_price_eur_tco2",
        "space_heat_kwh",
        "hotwater_kwh",
        "dh_space_heat_kwh",
        "dh_total_kwh",
    }
    missing = sorted(required.difference(frame.columns))
    if missing:
        raise KeyError("[thermflex_hourly_mechanism] direct daily KPI truth missing columns: " + ", ".join(missing))


def _validate_daily_feature_frame(frame: pd.DataFrame) -> None:
    null_columns = sorted(column for column in frame.columns if frame[column].isna().any())
    if null_columns:
        raise ValueError("[thermflex_hourly_mechanism] daily KPI frame contains nulls in: " + ", ".join(null_columns))


def _constant_numeric(frame: pd.DataFrame, column: str) -> float:
    values = pd.to_numeric(frame[column], errors="raise").drop_duplicates().to_numpy(dtype=float)
    if values.size != 1:
        raise ValueError(f"[thermflex_hourly_mechanism] expected constant daily value for {column}.")
    return float(values[0])


def _lower_band(frame: pd.DataFrame) -> float:
    return float(
        max(
            pd.to_numeric(frame["day_thermflex_temperature_band_k"], errors="raise").max(),
            pd.to_numeric(frame["night_thermflex_temperature_band_k"], errors="raise").max(),
        )
    )


def _policy_family(frame: pd.DataFrame) -> str:
    return "upper_only" if abs(_lower_band(frame)) <= 1e-9 else "lower_relax"


def _weather_month_regime(month: int) -> str:
    month_int = int(month)
    if month_int in {12, 1, 2}:
        return "winter"
    if month_int in {3, 4, 10, 11}:
        return "shoulder"
    return "summer_other"


def _temperature_bin(t_outdoor_mean_c: float) -> str:
    value = float(t_outdoor_mean_c)
    if value <= 5.0:
        return "cold_le5c"
    if value <= 15.0:
        return "mild_5_15c"
    return "warm_gt15c"


def _target_transform(target_name: str) -> str:
    if target_name in {"q_delta_sum_kwh", "peak_change_kw"}:
        return "signed_log1p"
    return "signed_log1p"


def _metric_payload(y_true: np.ndarray, y_pred: np.ndarray) -> dict[str, float]:
    truth = np.asarray(y_true, dtype=float)
    pred = np.asarray(y_pred, dtype=float)
    finite = np.isfinite(truth) & np.isfinite(pred)
    truth = truth[finite]
    pred = pred[finite]
    if truth.size == 0:
        return {"r2": float("nan"), "mae": float("nan"), "rmse": float("nan"), "true_abs_mean": float("nan"), "true_std": float("nan")}
    return {
        "r2": _safe_r2(truth, pred),
        "mae": float(mean_absolute_error(truth, pred)),
        "rmse": float(np.sqrt(mean_squared_error(truth, pred))),
        "true_abs_mean": float(np.mean(np.abs(truth))),
        "true_std": float(np.std(truth)),
    }


def _safe_r2(y_true: np.ndarray, y_pred: np.ndarray) -> float:
    truth = np.asarray(y_true, dtype=float)
    pred = np.asarray(y_pred, dtype=float)
    finite = np.isfinite(truth) & np.isfinite(pred)
    truth = truth[finite]
    pred = pred[finite]
    if truth.size < 2 or float(np.var(truth)) <= 1e-12:
        return float("nan")
    return float(r2_score(truth, pred))


def _summarize(frame: pd.DataFrame, *, group_cols: list[str]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for key, group in frame.groupby(group_cols, sort=True, dropna=False):
        if not isinstance(key, tuple):
            key = (key,)
        row = {column: value for column, value in zip(group_cols, key)}
        for metric in ("r2", "mae", "rmse", "true_abs_mean", "true_std"):
            row.update(_summary_metric_values(prefix=metric, values=group[metric].to_numpy(dtype=float)))
        row["n_test_days_median"] = float(np.nanmedian(pd.to_numeric(group["n_test_days"], errors="coerce")))
        rows.append(row)
    return rows


def _summary_metric_values(*, prefix: str, values: np.ndarray) -> dict[str, float]:
    finite = np.asarray(values, dtype=float)
    finite = finite[np.isfinite(finite)]
    if finite.size == 0:
        return {f"{prefix}_mean": float("nan"), f"{prefix}_median": float("nan"), f"{prefix}_min": float("nan"), f"{prefix}_max": float("nan")}
    return {
        f"{prefix}_mean": float(np.mean(finite)),
        f"{prefix}_median": float(np.median(finite)),
        f"{prefix}_min": float(np.min(finite)),
        f"{prefix}_max": float(np.max(finite)),
    }


def _diagnostic_dir(*, model_root: Path, family_hash: str, estimator: str, output_name: str | None) -> Path:
    suffix = str(output_name).strip() if output_name else "daily_direct"
    if not suffix:
        raise ValueError("[thermflex_hourly_mechanism] output_name must not be empty.")
    return Path(model_root).resolve() / f"thermflex_hourly_mechanism_daily_direct_{family_hash[:12]}_{estimator}_{suffix}"


def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate direct daily ThermFlex mechanism KPI holdouts.")
    parser.add_argument("--family-hash", required=True)
    parser.add_argument("--dataset-root", type=Path, default=_DEFAULT_DATASET_ROOT)
    parser.add_argument("--model-root", type=Path, default=_DEFAULT_MODEL_ROOT)
    parser.add_argument("--group-column", default="run_dir")
    parser.add_argument("--test-size", type=float, default=0.25)
    parser.add_argument("--split-strategy", default="group_shuffle")
    parser.add_argument("--stratify-column", default=None)
    parser.add_argument("--first-seed", type=int, default=0)
    parser.add_argument("--n-seeds", type=int, default=10)
    parser.add_argument("--estimator", choices=("extra_trees", "xgb"), default="extra_trees")
    parser.add_argument("--rebound-gate-threshold-kwh", type=float, default=None)
    parser.add_argument("--rebound-two-stage-threshold-kwh", type=float, default=None)
    parser.add_argument("--feature-preset", default="all")
    parser.add_argument("--output-name", default=None)
    args = parser.parse_args()
    result = evaluate_daily_kpi_direct_holdouts(
        family_hash=args.family_hash,
        dataset_root=args.dataset_root,
        model_root=args.model_root,
        group_column=args.group_column,
        test_size=args.test_size,
        split_strategy=args.split_strategy,
        stratify_column=args.stratify_column,
        first_seed=args.first_seed,
        n_seeds=args.n_seeds,
        estimator=args.estimator,
        rebound_gate_threshold_kwh=args.rebound_gate_threshold_kwh,
        rebound_two_stage_threshold_kwh=args.rebound_two_stage_threshold_kwh,
        feature_preset=args.feature_preset,
        output_name=args.output_name,
    )
    print(json.dumps({"diagnostic_dir": str(result.diagnostic_dir)}, indent=2))


if __name__ == "__main__":
    main()
