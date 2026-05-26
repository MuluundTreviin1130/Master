from __future__ import annotations

"""Evaluate targeted upper-only mass and rebound subcontracts.

This is a diagnostic bridge after the oracle ablation. It tests two explicit
subproblems instead of another monolithic hourly model:

- family-day positive/negative q-delta mass correction,
- daily rebound active-state and magnitude prediction.

The script uses the persisted hourly model predictions as input features and
the persisted grouped holdout as the evaluation split. It is a candidate
diagnostic only; it does not mark any model preferred.
"""

import argparse
import json
from pathlib import Path
from typing import Any

import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import ExtraTreesClassifier, ExtraTreesRegressor, HistGradientBoostingRegressor
from sklearn.metrics import accuracy_score, f1_score, mean_absolute_error, r2_score
from sklearn.multioutput import MultiOutputRegressor

from dispatch.metrics import compute_thermflex_series_metrics
from Learning.thermflex_hourly_mechanism.diagnose_upper_only_sequence_failure import (
    DEFAULT_DATASET_DIR,
    DEFAULT_MODEL_DIR,
    _age_family,
    _hour_block,
    _negative_mass,
    _positive_mass,
    _rebound_failure_mode,
    _safe_r2,
    _scale_components_to_mass,
    _season_regime,
    _sector,
    _sequence_stats,
)
from Learning.thermflex_hourly_mechanism.evaluate_kpi_reaggregation import predicted_or_true_metric
from Learning.thermflex_hourly_mechanism.train import _invert_target_transform


def evaluate_upper_only_subcontracts(
    *,
    model_dir: Path = DEFAULT_MODEL_DIR,
    dataset_dir: Path = DEFAULT_DATASET_DIR,
    output_dir: Path | None = None,
    activation_threshold_kwh: float = 25_000.0,
    backend: str = "extra_trees",
) -> dict[str, Any]:
    """Evaluate mass correction and rebound gate candidates on one holdout."""

    model_root = Path(model_dir).resolve()
    dataset_root = Path(dataset_dir).resolve()
    if output_dir is None:
        output_root = model_root / "diagnostics" / "upper_only_subcontracts"
    else:
        output_root = Path(output_dir).resolve()
    output_root.mkdir(parents=True, exist_ok=True)

    frame, split_payload = _load_all_predictions(model_dir=model_root, dataset_dir=dataset_root)
    test_groups = {str(value) for value in split_payload["test_groups"]}
    frame["is_test"] = frame["split_group_run"].astype(str).isin(test_groups)

    family_frame = _build_family_day_frame(frame)
    mass_summary, mass_scaled_daily, mass_scaled_frame = _evaluate_mass_contract(
        frame=frame,
        family_frame=family_frame,
        backend=backend,
    )
    daily_frame = _build_daily_frame(
        frame=frame,
        delta_column="q_delta_pred_kwh",
        feature_prefix="raw",
        activation_threshold_kwh=float(activation_threshold_kwh),
    )
    mass_corrected_daily_frame = _build_daily_frame(
        frame=mass_scaled_frame,
        delta_column="q_delta_mass_corrected_kwh",
        feature_prefix="mass_corrected",
        activation_threshold_kwh=float(activation_threshold_kwh),
    )
    enhanced_daily_frame = _merge_daily_feature_frames(
        raw_daily_frame=daily_frame,
        mass_corrected_daily_frame=mass_corrected_daily_frame,
    )
    rebound_summary, rebound_predictions = _evaluate_rebound_gate(
        daily_frame=enhanced_daily_frame,
        backend=backend,
        activation_threshold_kwh=float(activation_threshold_kwh),
    )
    shifted_summary, shifted_predictions = _evaluate_shifted_corrector(
        daily_frame=enhanced_daily_frame,
        backend=backend,
    )
    combined_daily = _combine_mass_and_rebound(
        mass_scaled_daily=mass_scaled_daily,
        rebound_predictions=rebound_predictions,
        shifted_predictions=shifted_predictions,
    )

    family_csv = output_root / "family_day_mass_contract_rows.csv"
    mass_csv = output_root / "mass_contract_metrics.csv"
    daily_csv = output_root / "daily_rebound_gate_rows.csv"
    rebound_csv = output_root / "rebound_gate_metrics.csv"
    rebound_predictions_csv = output_root / "rebound_gate_predictions.csv"
    shifted_csv = output_root / "shifted_corrector_metrics.csv"
    shifted_predictions_csv = output_root / "shifted_corrector_predictions.csv"
    combined_csv = output_root / "combined_daily_kpi_metrics.csv"
    summary_json = output_root / "subcontract_summary.json"

    family_frame.to_csv(family_csv, index=False)
    mass_summary.to_csv(mass_csv, index=False)
    enhanced_daily_frame.to_csv(daily_csv, index=False)
    rebound_summary.to_csv(rebound_csv, index=False)
    rebound_predictions.to_csv(rebound_predictions_csv, index=False)
    shifted_summary.to_csv(shifted_csv, index=False)
    shifted_predictions.to_csv(shifted_predictions_csv, index=False)
    combined_daily.to_csv(combined_csv, index=False)

    summary = {
        "model_dir": str(model_root),
        "dataset_dir": str(dataset_root),
        "backend": str(backend),
        "activation_threshold_kwh": float(activation_threshold_kwh),
        "family_rows_csv": str(family_csv),
        "mass_metrics_csv": str(mass_csv),
        "daily_rows_csv": str(daily_csv),
        "rebound_metrics_csv": str(rebound_csv),
        "rebound_predictions_csv": str(rebound_predictions_csv),
        "shifted_metrics_csv": str(shifted_csv),
        "shifted_predictions_csv": str(shifted_predictions_csv),
        "combined_metrics_csv": str(combined_csv),
        "mass_metrics": mass_summary.to_dict(orient="records"),
        "rebound_metrics": rebound_summary.to_dict(orient="records"),
        "shifted_metrics": shifted_summary.to_dict(orient="records"),
        "combined_metrics": combined_daily.to_dict(orient="records"),
    }
    summary_json.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    return summary


def _load_all_predictions(*, model_dir: Path, dataset_dir: Path) -> tuple[pd.DataFrame, dict[str, Any]]:
    """Attach model q-delta predictions to every curated row."""

    bundle_path = model_dir / "thermflex_hourly_mechanism_xgb.joblib"
    split_path = model_dir / "holdout_split.json"
    truth_path = dataset_dir / "truth_dataset.csv"
    meta_path = dataset_dir / "training_data.meta.json"
    for path in (bundle_path, split_path, truth_path, meta_path):
        if not path.exists():
            raise FileNotFoundError(f"[upper_only_subcontracts] missing required artifact: {path}")

    bundle = joblib.load(bundle_path)
    split_payload = json.loads(split_path.read_text(encoding="utf-8"))
    dataset_meta = json.loads(meta_path.read_text(encoding="utf-8"))
    frame = pd.read_csv(truth_path)
    frame["timestamp"] = pd.to_datetime(frame["timestamp"], errors="raise")

    numeric_columns = [str(value) for value in dataset_meta["feature_columns"]]
    categorical_columns = [str(value) for value in dataset_meta["categorical_feature_columns"]]
    encoded_columns = [
        str(value)
        for value in bundle.get("feature_columns", dataset_meta["encoded_feature_columns"])
    ]
    raw_features = frame.loc[:, numeric_columns + categorical_columns].copy()
    encoded = pd.get_dummies(raw_features, columns=categorical_columns, dtype=float)
    encoded = encoded.reindex(columns=encoded_columns, fill_value=0.0)

    predictions: dict[str, np.ndarray] = {}
    for model, target_name in zip(bundle["models"], bundle["target_names"]):
        target_key = str(target_name)
        transformed = np.asarray(model.predict(encoded.to_numpy(dtype=float)), dtype=float)
        predictions[target_key] = _invert_target_transform(
            transformed,
            str(bundle["target_transforms"][target_name]),
        )
        frame[f"pred_{target_key}"] = np.asarray(predictions[target_key], dtype=float)
    if "cohort_q_delta_wh_per_m2" in predictions:
        area = pd.to_numeric(frame["cohort_floor_area_m2"], errors="raise").to_numpy(dtype=float)
        q_delta_pred = predictions["cohort_q_delta_wh_per_m2"] * area / 1000.0
        frame["pred_cohort_q_delta_kwh"] = np.asarray(q_delta_pred, dtype=float)
    elif "cohort_q_delta_kwh" in predictions:
        q_delta_pred = predictions["cohort_q_delta_kwh"]
        frame["pred_cohort_q_delta_kwh"] = np.asarray(q_delta_pred, dtype=float)
    else:
        raise ValueError("[upper_only_subcontracts] q_delta prediction target is missing.")

    frame["q_delta_pred_kwh"] = np.asarray(q_delta_pred, dtype=float)
    frame["q_delta_true_kwh"] = (
        pd.to_numeric(frame["cohort_q_heat_kwh"], errors="raise").to_numpy(dtype=float)
        - pd.to_numeric(frame["cohort_q_heat_ref_kwh"], errors="raise").to_numpy(dtype=float)
    )
    frame["q_heat_pred_kwh"] = (
        pd.to_numeric(frame["cohort_q_heat_ref_kwh"], errors="raise").to_numpy(dtype=float)
        + frame["q_delta_pred_kwh"].to_numpy(dtype=float)
    )
    frame["day"] = frame["timestamp"].dt.floor("D")
    frame["hour"] = frame["timestamp"].dt.hour.astype(int)
    frame["age_family"] = frame["cohort_key"].astype(str).map(_age_family)
    frame["age_bin"] = frame["age_family"].map(
        lambda value: "old" if value in {"pre1975", "1975_1990"} else "modern"
    )
    frame["sector"] = frame["cohort_key"].astype(str).map(_sector)
    frame["season_regime"] = frame["timestamp"].dt.month.map(_season_regime)
    frame["hour_block"] = frame["hour"].map(_hour_block)
    return frame, split_payload


def _build_family_day_frame(frame: pd.DataFrame) -> pd.DataFrame:
    """Build family-day rows for positive/negative mass learning."""

    rows: list[dict[str, Any]] = []
    group_columns = ["run_dir", "day", "split_group_run", "season_regime", "age_bin", "age_family", "sector"]
    for key, group in frame.groupby(group_columns, sort=True):
        row = dict(zip(group_columns, key))
        row.update(_mass_features(group, prefix="family"))
        for block, block_group in group.groupby("hour_block", sort=True):
            row.update(_mass_features(block_group, prefix=f"block_{block}"))
        q_ref = group.groupby("timestamp")["cohort_q_heat_ref_kwh"].sum().sort_index()
        row["q_ref_sum_kwh"] = float(q_ref.sum())
        row["q_ref_peak_kw"] = float(q_ref.max())
        row["t_outdoor_mean_c"] = float(pd.to_numeric(group["t_outdoor_c"], errors="raise").mean())
        row["is_test"] = bool(group["is_test"].iloc[0])
        rows.append(row)
    return pd.DataFrame(rows).fillna(0.0)


def _mass_features(group: pd.DataFrame, *, prefix: str) -> dict[str, float]:
    """Return true and predicted positive/negative mass features."""

    pred = group["q_delta_pred_kwh"].to_numpy(dtype=float)
    true = group["q_delta_true_kwh"].to_numpy(dtype=float)
    return {
        f"{prefix}_pred_pos_kwh": _positive_mass(pred),
        f"{prefix}_pred_neg_kwh": _negative_mass(pred),
        f"{prefix}_pred_abs_kwh": float(np.sum(np.abs(pred))),
        f"{prefix}_true_pos_kwh": _positive_mass(true),
        f"{prefix}_true_neg_kwh": _negative_mass(true),
        f"{prefix}_true_abs_kwh": float(np.sum(np.abs(true))),
    }


def _evaluate_mass_contract(
    *,
    frame: pd.DataFrame,
    family_frame: pd.DataFrame,
    backend: str,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Train family-day mass regressors and reconstruct daily KPIs."""

    feature_frame = pd.get_dummies(
        family_frame.drop(
            columns=[
                "run_dir",
                "day",
                "split_group_run",
                "family_true_pos_kwh",
                "family_true_neg_kwh",
                "family_true_abs_kwh",
                "is_test",
            ],
            errors="ignore",
        ),
        columns=["season_regime", "age_bin", "age_family", "sector"],
        dtype=float,
    )
    target = family_frame[["family_true_pos_kwh", "family_true_neg_kwh"]].to_numpy(dtype=float)
    train_mask = ~family_frame["is_test"].to_numpy(dtype=bool)
    test_mask = family_frame["is_test"].to_numpy(dtype=bool)
    regressor = _new_mass_regressor(backend)
    regressor.fit(feature_frame.to_numpy(dtype=float)[train_mask], target[train_mask])
    pred = np.maximum(regressor.predict(feature_frame.to_numpy(dtype=float)), 0.0)
    family_pred = family_frame[["run_dir", "day", "age_family", "sector", "is_test"]].copy()
    family_pred["mass_pred_pos_kwh"] = pred[:, 0]
    family_pred["mass_pred_neg_kwh"] = pred[:, 1]

    summary_rows = [_mass_metric_row("all_family_day", target[test_mask], pred[test_mask])]
    old_winter = (
        test_mask
        & (family_frame["season_regime"].astype(str).to_numpy() == "winter")
        & (family_frame["age_bin"].astype(str).to_numpy() == "old")
    )
    if np.any(old_winter):
        summary_rows.append(_mass_metric_row("winter_old_family_day", target[old_winter], pred[old_winter]))

    scaled_frame = _apply_family_mass_predictions(frame, family_pred)
    daily_rows = _daily_rows_from_delta(
        frame=scaled_frame,
        delta_column="q_delta_mass_corrected_kwh",
        variant="family_mass_corrected",
    )
    raw_rows = _daily_rows_from_delta(
        frame=scaled_frame,
        delta_column="q_delta_pred_kwh",
        variant="raw_predicted",
    )
    summary = pd.DataFrame(
        summary_rows
        + _daily_metric_summary(raw_rows).to_dict(orient="records")
        + _daily_metric_summary(daily_rows).to_dict(orient="records")
    )
    return summary, pd.concat([raw_rows, daily_rows], ignore_index=True), scaled_frame


def _mass_metric_row(label: str, true: np.ndarray, pred: np.ndarray) -> dict[str, Any]:
    """Summarize positive/negative mass prediction quality."""

    return {
        "variant": label,
        "n_rows": int(len(true)),
        "positive_mass_r2": _safe_r2(true[:, 0], pred[:, 0]),
        "negative_mass_r2": _safe_r2(true[:, 1], pred[:, 1]),
        "positive_mass_mae": float(mean_absolute_error(true[:, 0], pred[:, 0])),
        "negative_mass_mae": float(mean_absolute_error(true[:, 1], pred[:, 1])),
    }


def _apply_family_mass_predictions(frame: pd.DataFrame, family_pred: pd.DataFrame) -> pd.DataFrame:
    """Scale predicted q-delta components within each day/family/sector."""

    out = frame.copy()
    out["q_delta_mass_corrected_kwh"] = out["q_delta_pred_kwh"].to_numpy(dtype=float)
    key_columns = ["run_dir", "day", "age_family", "sector"]
    pred_lookup = {
        tuple(row[key] for key in key_columns): (
            float(row["mass_pred_pos_kwh"]),
            float(row["mass_pred_neg_kwh"]),
        )
        for _, row in family_pred.iterrows()
    }
    for key, idx in out.groupby(key_columns, sort=False).groups.items():
        pred_pos, pred_neg = pred_lookup[key]
        source = out.loc[idx, "q_delta_pred_kwh"].to_numpy(dtype=float)
        out.loc[idx, "q_delta_mass_corrected_kwh"] = _scale_components_to_mass(
            source_diff=source,
            positive_mass=pred_pos,
            negative_mass=pred_neg,
        )
    return out


def _build_daily_frame(
    *,
    frame: pd.DataFrame,
    delta_column: str,
    feature_prefix: str,
    activation_threshold_kwh: float,
    include_model_component_features: bool = False,
    include_model_component_timeblock_features: bool = False,
    include_exante_profile_features: bool = False,
) -> pd.DataFrame:
    """Build daily rows for rebound gate and active magnitude learning."""

    rows: list[dict[str, Any]] = []
    for (run_dir, day), group in frame.groupby(["run_dir", "day"], sort=True):
        q_ref = group.groupby("timestamp")["cohort_q_heat_ref_kwh"].sum().sort_index()
        q_true = group.groupby("timestamp")["cohort_q_heat_kwh"].sum().sort_index()
        q_delta_pred = group.groupby("timestamp")[delta_column].sum().sort_index()
        q_pred = q_ref + q_delta_pred
        d_true = q_true.to_numpy(dtype=float) - q_ref.to_numpy(dtype=float)
        d_pred = q_pred.to_numpy(dtype=float) - q_ref.to_numpy(dtype=float)
        true_metrics = compute_thermflex_series_metrics(q_true, q_ref)
        pred_metrics = compute_thermflex_series_metrics(q_pred, q_ref)
        rebound_true = predicted_or_true_metric(true_metrics, "thermflex_rebound_kwh")
        rebound_pred = predicted_or_true_metric(pred_metrics, "thermflex_rebound_kwh")
        true_stats = _sequence_stats(d_true, activation_threshold_kwh)
        pred_stats = _sequence_stats(d_pred, activation_threshold_kwh)
        row = {
            "run_dir": str(run_dir),
            "day": pd.Timestamp(day),
            "split_group_run": str(group["split_group_run"].iloc[0]),
            "is_test": bool(group["is_test"].iloc[0]),
            "season_regime": _season_regime(int(pd.Timestamp(day).month)),
            "month": int(pd.Timestamp(day).month),
            "day_of_year": int(pd.Timestamp(day).dayofyear),
            f"{feature_prefix}_shifted_kwh": predicted_or_true_metric(pred_metrics, "thermflex_shifted_space_heat_kwh"),
            f"{feature_prefix}_rebound_kwh": rebound_pred,
            f"{feature_prefix}_peak_kw": predicted_or_true_metric(pred_metrics, "thermflex_peak_change_kw"),
            "shifted_true_kwh": predicted_or_true_metric(true_metrics, "thermflex_shifted_space_heat_kwh"),
            "rebound_true_kwh": rebound_true,
            "peak_true_kw": predicted_or_true_metric(true_metrics, "thermflex_peak_change_kw"),
            "q_ref_sum_kwh": float(q_ref.sum()),
            "q_ref_peak_kw": float(q_ref.max()),
            "q_ref_range_kw": float(q_ref.max() - q_ref.min()),
            "t_outdoor_mean_c": float(pd.to_numeric(group["t_outdoor_c"], errors="raise").mean()),
            "t_outdoor_min_c": float(pd.to_numeric(group["t_outdoor_c"], errors="raise").min()),
            "t_outdoor_max_c": float(pd.to_numeric(group["t_outdoor_c"], errors="raise").max()),
            "truth_rebound_active": bool(rebound_true >= activation_threshold_kwh),
            "failure_mode": _rebound_failure_mode(
                rebound_true=rebound_true,
                rebound_pred=rebound_pred,
                activation_threshold_kwh=activation_threshold_kwh,
            ),
        }
        if include_model_component_features:
            _add_optional_model_component_features(
                row=row,
                group=group,
                include_timeblock_features=include_model_component_timeblock_features,
            )
        if include_exante_profile_features:
            _add_optional_exante_profile_features(row=row, group=group)
        row.update({f"{feature_prefix}_{key}": value for key, value in pred_stats.items()})
        for (age_bin, sector, block), block_group in group.groupby(["age_bin", "sector", "hour_block"], sort=True):
            prefix = f"{age_bin}_{sector}_{block}"
            pred = block_group[delta_column].to_numpy(dtype=float)
            row[f"{feature_prefix}_{prefix}_pos_kwh"] = _positive_mass(pred)
            row[f"{feature_prefix}_{prefix}_neg_kwh"] = _negative_mass(pred)
            row[f"{feature_prefix}_{prefix}_abs_kwh"] = float(np.sum(np.abs(pred)))
        rows.append(row)
    return pd.DataFrame(rows).fillna(0.0)


def _add_optional_model_component_features(
    *,
    row: dict[str, Any],
    group: pd.DataFrame,
    include_timeblock_features: bool = False,
) -> None:
    """Add predicted mechanism components when the trained bundle exposes them.

    The hourly model already predicts preheat and cutback component targets.
    Rebound activation depends on whether a real cutback/recovery sequence
    exists, so the daily trigger diagnostics should be able to use these
    predicted components without reading truth-only output columns. Totals
    alone are not enough for upper-only rebound because false-active days often
    have shifted mass but no useful recovery sequence. The explicit time-block
    and ratio features keep the diagnostic tied to the predicted mechanism
    state instead of asking a classifier to infer timing from one daily sum.
    The wider time-block block is deliberately opt-in: with the current small
    upper-only tau4/dur24 sample it overfits the grouped holdout.
    """

    area = pd.to_numeric(group["cohort_floor_area_m2"], errors="raise").to_numpy(dtype=float)
    component_specs = (
        ("pred_cohort_preheat_extra_wh_per_m2", "model_preheat_extra_kwh", True),
        ("pred_cohort_preheat_extra_kwh", "model_preheat_extra_kwh", False),
        ("pred_cohort_cutback_shed_wh_per_m2", "model_cutback_shed_kwh", True),
        ("pred_cohort_cutback_shed_kwh", "model_cutback_shed_kwh", False),
        ("pred_cohort_temperature_violation_degree_h", "model_temperature_violation_degree_h", False),
    )
    component_values_by_name: dict[str, np.ndarray] = {}
    for column, daily_name, scale_by_area in component_specs:
        if column not in group.columns or daily_name in component_values_by_name:
            continue
        values = pd.to_numeric(group[column], errors="raise").to_numpy(dtype=float)
        if scale_by_area:
            component_values = values * area / 1000.0
        else:
            component_values = values
        component_values_by_name[daily_name] = component_values
        row[daily_name] = float(np.sum(component_values))
        if not include_timeblock_features:
            continue
        hourly_component = (
            pd.DataFrame({"timestamp": group["timestamp"].to_numpy(), "value": component_values})
            .groupby("timestamp", sort=True)["value"]
            .sum()
            .to_numpy(dtype=float)
        )
        row[f"{daily_name}_peak_hourly"] = float(np.max(hourly_component)) if hourly_component.size else 0.0

    if not include_timeblock_features or not component_values_by_name:
        _add_optional_predicted_state_features(row=row, group=group)
        return

    hour_blocks = group["hour_block"].astype(str).to_numpy()
    for daily_name, values in component_values_by_name.items():
        for block in sorted(set(hour_blocks.tolist())):
            mask = hour_blocks == block
            row[f"{daily_name}_{block}_sum"] = float(np.sum(values[mask]))

    preheat = float(row.get("model_preheat_extra_kwh", 0.0))
    cutback = float(row.get("model_cutback_shed_kwh", 0.0))
    violation = float(row.get("model_temperature_violation_degree_h", 0.0))
    mechanism_sum = preheat + cutback
    row["model_preheat_to_cutback_ratio"] = float(preheat / max(cutback, 1e-9))
    row["model_violation_per_cutback_kwh"] = float(violation / max(cutback, 1e-9))
    row["model_cutback_share_of_component_sum"] = float(cutback / max(mechanism_sum, 1e-9))
    row["model_preheat_share_of_component_sum"] = float(preheat / max(mechanism_sum, 1e-9))
    _add_optional_predicted_state_features(row=row, group=group)


def _add_optional_predicted_state_features(*, row: dict[str, Any], group: pd.DataFrame) -> None:
    """Attach predicted state targets from richer hourly profiles when present."""

    state_specs = {
        "pred_cohort_flex_active_member_share": "model_flex_active_member_share",
        "pred_cohort_event_start_count": "model_event_start_count",
        "pred_cohort_t_in_weighted_mean_c": "model_t_in_weighted_mean_c",
        "pred_cohort_t_in_member_min_c": "model_t_in_member_min_c",
        "pred_cohort_t_in_member_max_c": "model_t_in_member_max_c",
    }
    for column, prefix in state_specs.items():
        if column not in group.columns:
            continue
        values = pd.to_numeric(group[column], errors="raise").to_numpy(dtype=float)
        row[f"{prefix}_mean"] = float(np.mean(values))
        row[f"{prefix}_min"] = float(np.min(values))
        row[f"{prefix}_max"] = float(np.max(values))


def _add_optional_exante_profile_features(*, row: dict[str, Any], group: pd.DataFrame) -> None:
    """Add compact known-in-advance daily profile descriptors.

    Upper-only rebound around shoulder days depends on the within-day order of
    weather, reference heat, and price. The daily mean/min/max features lose
    that order, while a full 24-hour grid is too wide for the current sample.
    Hour-block aggregates keep the state signal small and explicit.
    """

    block_specs = {
        "t_outdoor_c": "mean",
        "cohort_q_heat_ref_kwh": "sum",
        "dh_space_heat_kwh": "sum",
        "mc_auction_eur_mwh": "mean",
        "irradiance_proxy": "sum",
        "solargains_proxy": "sum",
    }
    required = set(block_specs).union({"hour_block"})
    missing = sorted(required.difference(group.columns))
    if missing:
        raise KeyError("[upper_only_subcontracts] ex-ante profile features missing columns: " + ", ".join(missing))

    for block, block_group in group.groupby("hour_block", sort=True):
        block_name = str(block)
        for column, aggregation in block_specs.items():
            values = pd.to_numeric(block_group[column], errors="raise")
            if aggregation == "sum":
                value = float(values.sum())
            elif aggregation == "mean":
                value = float(values.mean())
            else:
                raise ValueError(f"[upper_only_subcontracts] unsupported aggregation: {aggregation}")
            row[f"exante_{column}_{block_name}_{aggregation}"] = value


def _merge_daily_feature_frames(
    *,
    raw_daily_frame: pd.DataFrame,
    mass_corrected_daily_frame: pd.DataFrame,
) -> pd.DataFrame:
    """Join raw and mass-corrected daily prediction features."""

    key_columns = [
        "run_dir",
        "day",
        "split_group_run",
        "is_test",
        "season_regime",
        "month",
        "day_of_year",
        "shifted_true_kwh",
        "rebound_true_kwh",
        "peak_true_kw",
        "q_ref_sum_kwh",
        "q_ref_peak_kw",
        "q_ref_range_kw",
        "t_outdoor_mean_c",
        "t_outdoor_min_c",
        "t_outdoor_max_c",
        "truth_rebound_active",
        "failure_mode",
    ]
    right_feature_columns = [
        column
        for column in mass_corrected_daily_frame.columns
        if column not in key_columns
    ]
    return raw_daily_frame.merge(
        mass_corrected_daily_frame[key_columns[:4] + right_feature_columns],
        on=key_columns[:4],
        how="inner",
        validate="one_to_one",
    )


def _evaluate_rebound_gate(
    *,
    daily_frame: pd.DataFrame,
    backend: str,
    activation_threshold_kwh: float,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Evaluate explicit rebound active-state plus magnitude models."""

    feature_columns = [
        column
        for column in daily_frame.columns
        if column
        not in {
            "run_dir",
            "day",
            "split_group_run",
            "is_test",
            "shifted_true_kwh",
            "rebound_true_kwh",
            "peak_true_kw",
            "truth_rebound_active",
            "failure_mode",
        }
    ]
    features = pd.get_dummies(daily_frame[feature_columns], columns=["season_regime"], dtype=float)
    train_mask = ~daily_frame["is_test"].to_numpy(dtype=bool)
    test_mask = daily_frame["is_test"].to_numpy(dtype=bool)
    y_active = daily_frame["truth_rebound_active"].astype(int).to_numpy()
    y_rebound = daily_frame["rebound_true_kwh"].to_numpy(dtype=float)

    classifier = ExtraTreesClassifier(
        n_estimators=500,
        min_samples_leaf=1,
        class_weight="balanced",
        random_state=42,
        n_jobs=-1,
    )
    classifier.fit(features.to_numpy(dtype=float)[train_mask], y_active[train_mask])
    active_probability = classifier.predict_proba(features.to_numpy(dtype=float))[:, 1]
    active_pred = active_probability >= 0.5

    regressor = _new_scalar_regressor(backend)
    active_train = train_mask & (y_active == 1)
    if int(np.sum(active_train)) < 4:
        raise ValueError("[upper_only_subcontracts] not enough active rebound train days.")
    regressor.fit(features.to_numpy(dtype=float)[active_train], y_rebound[active_train])
    rebound_pred = np.maximum(regressor.predict(features.to_numpy(dtype=float)), 0.0)
    gated_rebound = np.where(active_pred, rebound_pred, 0.0)
    raw_gated_rebound = np.where(active_pred, daily_frame["raw_rebound_kwh"].to_numpy(dtype=float), 0.0)

    predictions = daily_frame[["run_dir", "day", "is_test", "rebound_true_kwh", "raw_rebound_kwh"]].copy()
    predictions["active_probability"] = active_probability
    predictions["active_pred"] = active_pred
    predictions["rebound_gate_regressor_pred_kwh"] = gated_rebound
    predictions["rebound_gate_raw_pred_kwh"] = raw_gated_rebound

    test = test_mask
    rows = [
        _rebound_metric_row(
            "raw_rebound",
            y_true=y_rebound[test],
            y_pred=daily_frame.loc[test, "raw_rebound_kwh"].to_numpy(dtype=float),
            y_active_true=y_active[test],
            y_active_pred=(daily_frame.loc[test, "raw_rebound_kwh"].to_numpy(dtype=float) >= activation_threshold_kwh).astype(int),
        ),
        _rebound_metric_row(
            "gate_plus_active_regressor",
            y_true=y_rebound[test],
            y_pred=gated_rebound[test],
            y_active_true=y_active[test],
            y_active_pred=active_pred[test].astype(int),
        ),
        _rebound_metric_row(
            "gate_plus_raw_rebound",
            y_true=y_rebound[test],
            y_pred=raw_gated_rebound[test],
            y_active_true=y_active[test],
            y_active_pred=active_pred[test].astype(int),
        ),
    ]
    return pd.DataFrame(rows), predictions


def _evaluate_shifted_corrector(
    *,
    daily_frame: pd.DataFrame,
    backend: str,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Evaluate an explicit shifted corrector after family mass correction."""

    feature_columns = [
        column
        for column in daily_frame.columns
        if column
        not in {
            "run_dir",
            "day",
            "split_group_run",
            "is_test",
            "shifted_true_kwh",
            "rebound_true_kwh",
            "peak_true_kw",
            "truth_rebound_active",
            "failure_mode",
        }
    ]
    features = pd.get_dummies(daily_frame[feature_columns], columns=["season_regime"], dtype=float)
    train_mask = ~daily_frame["is_test"].to_numpy(dtype=bool)
    test_mask = daily_frame["is_test"].to_numpy(dtype=bool)
    y_shifted = daily_frame["shifted_true_kwh"].to_numpy(dtype=float)

    regressor = _new_scalar_regressor(backend)
    regressor.fit(features.to_numpy(dtype=float)[train_mask], y_shifted[train_mask])
    shifted_pred = np.maximum(regressor.predict(features.to_numpy(dtype=float)), 0.0)
    mass_corrected_shifted = daily_frame["mass_corrected_shifted_kwh"].to_numpy(dtype=float)

    predictions = daily_frame[["run_dir", "day", "is_test", "shifted_true_kwh", "mass_corrected_shifted_kwh"]].copy()
    predictions["shifted_corrector_pred_kwh"] = shifted_pred
    rows = [
        _shifted_metric_row(
            "mass_corrected_shifted",
            y_true=y_shifted[test_mask],
            y_pred=mass_corrected_shifted[test_mask],
        ),
        _shifted_metric_row(
            "shifted_corrector",
            y_true=y_shifted[test_mask],
            y_pred=shifted_pred[test_mask],
        ),
    ]
    return pd.DataFrame(rows), predictions


def _shifted_metric_row(variant: str, *, y_true: np.ndarray, y_pred: np.ndarray) -> dict[str, Any]:
    """Summarize shifted KPI correction quality."""

    return {
        "variant": str(variant),
        "n_days": int(len(y_true)),
        "shifted_r2": _safe_r2(y_true, y_pred),
        "shifted_mae": float(mean_absolute_error(y_true, y_pred)),
    }


def _rebound_metric_row(
    variant: str,
    *,
    y_true: np.ndarray,
    y_pred: np.ndarray,
    y_active_true: np.ndarray,
    y_active_pred: np.ndarray,
) -> dict[str, Any]:
    """Summarize rebound magnitude and active-state classification."""

    return {
        "variant": str(variant),
        "n_days": int(len(y_true)),
        "rebound_r2": _safe_r2(y_true, y_pred),
        "rebound_mae": float(mean_absolute_error(y_true, y_pred)),
        "active_accuracy": float(accuracy_score(y_active_true, y_active_pred)),
        "active_f1": float(f1_score(y_active_true, y_active_pred, zero_division=0)),
    }


def _combine_mass_and_rebound(
    *,
    mass_scaled_daily: pd.DataFrame,
    rebound_predictions: pd.DataFrame,
    shifted_predictions: pd.DataFrame,
) -> pd.DataFrame:
    """Combine daily shifted/peak from mass correction with rebound gate output."""

    mass_variant = mass_scaled_daily.loc[mass_scaled_daily["variant"] == "family_mass_corrected"].copy()
    if mass_variant.empty:
        raise ValueError("[upper_only_subcontracts] family mass corrected daily metrics are missing.")
    rebound_test = rebound_predictions.loc[rebound_predictions["is_test"]].copy()
    shifted_test = shifted_predictions.loc[shifted_predictions["is_test"]].copy()
    merged = mass_variant.merge(
        rebound_test[["run_dir", "day", "rebound_gate_regressor_pred_kwh", "rebound_gate_raw_pred_kwh"]],
        on=["run_dir", "day"],
        how="inner",
        validate="one_to_one",
    ).merge(
        shifted_test[["run_dir", "day", "shifted_corrector_pred_kwh"]],
        on=["run_dir", "day"],
        how="inner",
        validate="one_to_one",
    )
    rows = []
    for variant, rebound_column, shifted_column in (
        (
            "family_mass_plus_gate_regressor_rebound",
            "rebound_gate_regressor_pred_kwh",
            "shifted_pred_kwh",
        ),
        (
            "family_mass_plus_gate_raw_rebound",
            "rebound_gate_raw_pred_kwh",
            "shifted_pred_kwh",
        ),
        (
            "shifted_corrector_plus_gate_regressor_rebound",
            "rebound_gate_regressor_pred_kwh",
            "shifted_corrector_pred_kwh",
        ),
    ):
        rows.append(
            {
                "variant": variant,
                "n_days": int(len(merged)),
                "shifted_r2": _safe_r2(merged["shifted_true_kwh"], merged[shifted_column]),
                "rebound_r2": _safe_r2(merged["rebound_true_kwh"], merged[rebound_column]),
                "peak_r2": _safe_r2(merged["peak_true_kw"], merged["peak_pred_kw"]),
                "shifted_mae": float(mean_absolute_error(merged["shifted_true_kwh"], merged[shifted_column])),
                "rebound_mae": float(mean_absolute_error(merged["rebound_true_kwh"], merged[rebound_column])),
                "peak_mae": float(mean_absolute_error(merged["peak_true_kw"], merged["peak_pred_kw"])),
            }
        )
    return pd.DataFrame(rows)


def _daily_rows_from_delta(*, frame: pd.DataFrame, delta_column: str, variant: str) -> pd.DataFrame:
    """Reconstruct per-day KPIs for test rows from one q-delta column."""

    rows: list[dict[str, Any]] = []
    test_frame = frame.loc[frame["is_test"]].copy()
    for (run_dir, day), group in test_frame.groupby(["run_dir", "day"], sort=True):
        q_ref = group.groupby("timestamp")["cohort_q_heat_ref_kwh"].sum().sort_index()
        q_true = group.groupby("timestamp")["cohort_q_heat_kwh"].sum().sort_index()
        q_delta = group.groupby("timestamp")[delta_column].sum().sort_index()
        q_pred = q_ref + q_delta
        true_metrics = compute_thermflex_series_metrics(q_true, q_ref)
        pred_metrics = compute_thermflex_series_metrics(q_pred, q_ref)
        rows.append(
            {
                "run_dir": str(run_dir),
                "day": pd.Timestamp(day),
                "variant": str(variant),
                "shifted_true_kwh": predicted_or_true_metric(true_metrics, "thermflex_shifted_space_heat_kwh"),
                "shifted_pred_kwh": predicted_or_true_metric(pred_metrics, "thermflex_shifted_space_heat_kwh"),
                "rebound_true_kwh": predicted_or_true_metric(true_metrics, "thermflex_rebound_kwh"),
                "rebound_pred_kwh": predicted_or_true_metric(pred_metrics, "thermflex_rebound_kwh"),
                "peak_true_kw": predicted_or_true_metric(true_metrics, "thermflex_peak_change_kw"),
                "peak_pred_kw": predicted_or_true_metric(pred_metrics, "thermflex_peak_change_kw"),
            }
        )
    return pd.DataFrame(rows)


def _daily_metric_summary(daily: pd.DataFrame) -> pd.DataFrame:
    """Summarize one per-day KPI reconstruction table."""

    if daily.empty:
        raise ValueError("[upper_only_subcontracts] daily KPI reconstruction produced no rows.")
    return pd.DataFrame(
        [
            {
                "variant": str(daily["variant"].iloc[0]),
                "n_days": int(len(daily)),
                "shifted_r2": _safe_r2(daily["shifted_true_kwh"], daily["shifted_pred_kwh"]),
                "rebound_r2": _safe_r2(daily["rebound_true_kwh"], daily["rebound_pred_kwh"]),
                "peak_r2": _safe_r2(daily["peak_true_kw"], daily["peak_pred_kw"]),
                "shifted_mae": float(mean_absolute_error(daily["shifted_true_kwh"], daily["shifted_pred_kwh"])),
                "rebound_mae": float(mean_absolute_error(daily["rebound_true_kwh"], daily["rebound_pred_kwh"])),
                "peak_mae": float(mean_absolute_error(daily["peak_true_kw"], daily["peak_pred_kw"])),
            }
        ]
    )


def _new_mass_regressor(backend: str) -> Any:
    """Construct the explicit family-day mass regressor."""

    if str(backend).strip().lower() == "hist_gradient":
        return MultiOutputRegressor(
            HistGradientBoostingRegressor(
                max_iter=450,
                learning_rate=0.035,
                l2_regularization=0.05,
                random_state=42,
            )
        )
    return ExtraTreesRegressor(
        n_estimators=700,
        min_samples_leaf=1,
        random_state=42,
        n_jobs=-1,
    )


def _new_scalar_regressor(backend: str) -> Any:
    """Construct the explicit daily rebound magnitude regressor."""

    if str(backend).strip().lower() == "hist_gradient":
        return HistGradientBoostingRegressor(
            max_iter=450,
            learning_rate=0.035,
            l2_regularization=0.05,
            random_state=42,
        )
    return ExtraTreesRegressor(
        n_estimators=700,
        min_samples_leaf=1,
        random_state=42,
        n_jobs=-1,
    )


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Evaluate targeted upper-only mass and rebound subcontracts."
    )
    parser.add_argument("--model-dir", type=Path, default=DEFAULT_MODEL_DIR)
    parser.add_argument("--dataset-dir", type=Path, default=DEFAULT_DATASET_DIR)
    parser.add_argument("--output-dir", type=Path, default=None)
    parser.add_argument("--activation-threshold-kwh", type=float, default=25_000.0)
    parser.add_argument("--backend", default="extra_trees")
    args = parser.parse_args()
    summary = evaluate_upper_only_subcontracts(
        model_dir=args.model_dir,
        dataset_dir=args.dataset_dir,
        output_dir=args.output_dir,
        activation_threshold_kwh=float(args.activation_threshold_kwh),
        backend=args.backend,
    )
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
