from __future__ import annotations

"""Diagnose why upper-only hourly mechanism predictions miss daily KPIs.

This script deliberately does not train a new model. It loads one persisted
hourly mechanism model, predicts the persisted holdout rows, and then asks a
small set of oracle questions:

- If the predicted timing/sign pattern were kept but the true positive and
  negative masses were injected, would shifted/rebound/peak become good?
- If the true timing/sign pattern were kept but the predicted masses were used,
  would the KPIs become good?
- Which hours and building families explain the remaining mass and timing
  errors?

The goal is to decide between targeted truth, state gating, mass correction, or
sequence-template logic before doing more model sweeps.
"""

import argparse
import json
from pathlib import Path
from typing import Any

import joblib
import numpy as np
import pandas as pd
from sklearn.metrics import mean_absolute_error, r2_score

from dispatch.metrics import compute_thermflex_series_metrics
from Learning.thermflex_hourly_mechanism.evaluate_kpi_reaggregation import (
    predicted_or_true_metric,
)
from Learning.thermflex_hourly_mechanism.train import _invert_target_transform


DEFAULT_DATASET_DIR = (
    Path(__file__).resolve().parents[2]
    / "Learning"
    / "datasets"
    / "6d058845d59b20453e43f83a1aec191c008683dee567ce9644a90d92d228a7fc"
)
DEFAULT_MODEL_DIR = (
    Path(__file__).resolve().parents[2]
    / "Learning"
    / "models"
    / "thermflex_hourly_mechanism_xgb_mechanism_energy_intensive_6d058845d59b_features_no_case_label_transforms_mechanism_mass_identity"
)


def diagnose_upper_only_sequence_failure(
    *,
    model_dir: Path = DEFAULT_MODEL_DIR,
    dataset_dir: Path = DEFAULT_DATASET_DIR,
    output_dir: Path | None = None,
    activation_threshold_kwh: float = 25_000.0,
) -> dict[str, Any]:
    """Run holdout-level sequence diagnosis for one upper-only model."""

    model_root = Path(model_dir).resolve()
    dataset_root = Path(dataset_dir).resolve()
    if output_dir is None:
        output_root = model_root / "diagnostics" / "upper_only_sequence_failure"
    else:
        output_root = Path(output_dir).resolve()
    output_root.mkdir(parents=True, exist_ok=True)

    holdout = _load_holdout_predictions(model_dir=model_root, dataset_dir=dataset_root)
    daily_df, variant_metric_df = _build_daily_oracle_tables(
        holdout=holdout,
        activation_threshold_kwh=float(activation_threshold_kwh),
    )
    hourly_error_df = _build_hourly_error_table(holdout)
    cohort_error_df = _build_cohort_family_error_table(holdout, daily_df)

    daily_csv = output_root / "daily_sequence_oracle_decomposition.csv"
    variants_csv = output_root / "daily_sequence_oracle_variant_metrics.csv"
    hourly_csv = output_root / "hourly_error_by_regime.csv"
    cohort_csv = output_root / "cohort_family_error_contributions.csv"
    summary_json = output_root / "diagnosis_summary.json"

    daily_df.to_csv(daily_csv, index=False)
    variant_metric_df.to_csv(variants_csv, index=False)
    hourly_error_df.to_csv(hourly_csv, index=False)
    cohort_error_df.to_csv(cohort_csv, index=False)

    summary = {
        "model_dir": str(model_root),
        "dataset_dir": str(dataset_root),
        "activation_threshold_kwh": float(activation_threshold_kwh),
        "daily_csv": str(daily_csv),
        "variant_metrics_csv": str(variants_csv),
        "hourly_error_csv": str(hourly_csv),
        "cohort_error_csv": str(cohort_csv),
        "variant_metrics": variant_metric_df.to_dict(orient="records"),
        "top_hour_errors": hourly_error_df.head(12).to_dict(orient="records"),
        "top_family_errors": cohort_error_df.head(12).to_dict(orient="records"),
    }
    summary_json.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    return summary


def _load_holdout_predictions(*, model_dir: Path, dataset_dir: Path) -> pd.DataFrame:
    """Load one model artifact and attach q-delta predictions to holdout rows."""

    bundle_path = model_dir / "thermflex_hourly_mechanism_xgb.joblib"
    split_path = model_dir / "holdout_split.json"
    truth_path = dataset_dir / "truth_dataset.csv"
    meta_path = dataset_dir / "training_data.meta.json"
    for required in (bundle_path, split_path, truth_path, meta_path):
        if not required.exists():
            raise FileNotFoundError(f"[upper_only_sequence_diagnosis] missing required artifact: {required}")

    bundle = joblib.load(bundle_path)
    split_payload = json.loads(split_path.read_text(encoding="utf-8"))
    dataset_meta = json.loads(meta_path.read_text(encoding="utf-8"))
    truth = pd.read_csv(truth_path)
    truth["timestamp"] = pd.to_datetime(truth["timestamp"], errors="raise")

    test_groups = {str(value) for value in split_payload["test_groups"]}
    holdout = truth.loc[truth["split_group_run"].astype(str).isin(test_groups)].copy()
    if holdout.empty:
        raise ValueError("[upper_only_sequence_diagnosis] persisted holdout groups produced no rows.")

    encoded_feature_columns = [
        str(value)
        for value in bundle.get("feature_columns", dataset_meta["encoded_feature_columns"])
    ]
    numeric_feature_columns = [str(value) for value in dataset_meta["feature_columns"]]
    categorical_feature_columns = [str(value) for value in dataset_meta["categorical_feature_columns"]]

    raw_feature_frame = holdout.loc[:, numeric_feature_columns + categorical_feature_columns].copy()
    encoded = pd.get_dummies(raw_feature_frame, columns=categorical_feature_columns, dtype=float)
    encoded = encoded.reindex(columns=encoded_feature_columns, fill_value=0.0)

    target_names = [str(value) for value in bundle["target_names"]]
    target_transforms = dict(bundle["target_transforms"])
    predictions: dict[str, np.ndarray] = {}
    for model, target_name in zip(bundle["models"], target_names):
        transformed = np.asarray(model.predict(encoded.to_numpy(dtype=float)), dtype=float)
        predictions[target_name] = _invert_target_transform(
            transformed,
            str(target_transforms[target_name]),
        )

    if "cohort_q_delta_wh_per_m2" in predictions:
        area = pd.to_numeric(holdout["cohort_floor_area_m2"], errors="raise").to_numpy(dtype=float)
        q_delta_pred = predictions["cohort_q_delta_wh_per_m2"] * area / 1000.0
    elif "cohort_q_delta_kwh" in predictions:
        q_delta_pred = predictions["cohort_q_delta_kwh"]
    else:
        raise ValueError(
            "[upper_only_sequence_diagnosis] model has neither q_delta intensive nor absolute target."
        )

    holdout["q_delta_true_kwh"] = (
        pd.to_numeric(holdout["cohort_q_heat_kwh"], errors="raise").to_numpy(dtype=float)
        - pd.to_numeric(holdout["cohort_q_heat_ref_kwh"], errors="raise").to_numpy(dtype=float)
    )
    holdout["q_delta_pred_kwh"] = np.asarray(q_delta_pred, dtype=float)
    holdout["q_heat_pred_kwh"] = (
        pd.to_numeric(holdout["cohort_q_heat_ref_kwh"], errors="raise").to_numpy(dtype=float)
        + holdout["q_delta_pred_kwh"].to_numpy(dtype=float)
    )
    holdout["day"] = holdout["timestamp"].dt.floor("D")
    holdout["hour"] = holdout["timestamp"].dt.hour.astype(int)
    holdout["age_family"] = holdout["cohort_key"].astype(str).map(_age_family)
    holdout["age_bin"] = holdout["age_family"].map(
        lambda value: "old" if value in {"pre1975", "1975_1990"} else "modern"
    )
    holdout["sector"] = holdout["cohort_key"].astype(str).map(_sector)
    holdout["season_regime"] = holdout["timestamp"].dt.month.map(_season_regime)
    holdout["hour_block"] = holdout["hour"].map(_hour_block)
    return holdout


def _build_daily_oracle_tables(
    *,
    holdout: pd.DataFrame,
    activation_threshold_kwh: float,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Create daily decomposition rows and aggregate oracle variant metrics."""

    daily_rows: list[dict[str, Any]] = []
    variant_rows: list[dict[str, Any]] = []
    for (run_dir, day), day_df in holdout.groupby(["run_dir", "day"], sort=True):
        ordered = day_df.sort_values("timestamp")
        q_ref = ordered.groupby("timestamp")["cohort_q_heat_ref_kwh"].sum().sort_index()
        q_true = ordered.groupby("timestamp")["cohort_q_heat_kwh"].sum().sort_index()
        q_pred = ordered.groupby("timestamp")["q_heat_pred_kwh"].sum().sort_index()
        d_true = q_true.to_numpy(dtype=float) - q_ref.to_numpy(dtype=float)
        d_pred = q_pred.to_numpy(dtype=float) - q_ref.to_numpy(dtype=float)
        variants = {
            "predicted": d_pred,
            "oracle_pred_timing_true_mass": _scale_components_to_mass(
                source_diff=d_pred,
                positive_mass=_positive_mass(d_true),
                negative_mass=_negative_mass(d_true),
            ),
            "oracle_true_timing_pred_mass": _scale_components_to_mass(
                source_diff=d_true,
                positive_mass=_positive_mass(d_pred),
                negative_mass=_negative_mass(d_pred),
            ),
            "truth": d_true,
        }
        true_metrics = compute_thermflex_series_metrics(q_true, q_ref)
        pred_metrics = compute_thermflex_series_metrics(q_pred, q_ref)
        rebound_true = predicted_or_true_metric(true_metrics, "thermflex_rebound_kwh")
        rebound_pred = predicted_or_true_metric(pred_metrics, "thermflex_rebound_kwh")
        true_stats = _sequence_stats(d_true, activation_threshold_kwh)
        pred_stats = _sequence_stats(d_pred, activation_threshold_kwh)
        daily_rows.append(
            {
                "run_dir": str(run_dir),
                "day": pd.Timestamp(day),
                "month": int(pd.Timestamp(day).month),
                "season_regime": _season_regime(int(pd.Timestamp(day).month)),
                "shifted_true_kwh": predicted_or_true_metric(true_metrics, "thermflex_shifted_space_heat_kwh"),
                "shifted_pred_kwh": predicted_or_true_metric(pred_metrics, "thermflex_shifted_space_heat_kwh"),
                "rebound_true_kwh": rebound_true,
                "rebound_pred_kwh": rebound_pred,
                "peak_true_kw": predicted_or_true_metric(true_metrics, "thermflex_peak_change_kw"),
                "peak_pred_kw": predicted_or_true_metric(pred_metrics, "thermflex_peak_change_kw"),
                **{f"true_{key}": value for key, value in true_stats.items()},
                **{f"pred_{key}": value for key, value in pred_stats.items()},
                "positive_mass_error_kwh": pred_stats["positive_mass_kwh"] - true_stats["positive_mass_kwh"],
                "negative_mass_error_kwh": pred_stats["negative_mass_kwh"] - true_stats["negative_mass_kwh"],
                "abs_mass_error_kwh": pred_stats["abs_mass_kwh"] - true_stats["abs_mass_kwh"],
                "first_negative_hour_error": pred_stats["first_negative_hour"] - true_stats["first_negative_hour"],
                "truth_active": bool(true_stats["active_state"]),
                "pred_active": bool(pred_stats["active_state"]),
                "truth_rebound_active": bool(rebound_true >= activation_threshold_kwh),
                "pred_rebound_active": bool(rebound_pred >= activation_threshold_kwh),
                "failure_mode": _rebound_failure_mode(
                    rebound_true=rebound_true,
                    rebound_pred=rebound_pred,
                    activation_threshold_kwh=activation_threshold_kwh,
                ),
            }
        )
        for variant_name, diff in variants.items():
            q_variant = q_ref.to_numpy(dtype=float) + np.asarray(diff, dtype=float)
            metrics = compute_thermflex_series_metrics(q_variant, q_ref.to_numpy(dtype=float))
            variant_rows.append(
                {
                    "run_dir": str(run_dir),
                    "day": pd.Timestamp(day),
                    "variant": variant_name,
                    "shifted_kwh": predicted_or_true_metric(metrics, "thermflex_shifted_space_heat_kwh"),
                    "rebound_kwh": predicted_or_true_metric(metrics, "thermflex_rebound_kwh"),
                    "peak_kw": predicted_or_true_metric(metrics, "thermflex_peak_change_kw"),
                }
            )

    daily_df = pd.DataFrame(daily_rows)
    variant_long = pd.DataFrame(variant_rows)
    variant_metric_df = _summarize_variant_metrics(variant_long)
    return daily_df, variant_metric_df


def _summarize_variant_metrics(variant_long: pd.DataFrame) -> pd.DataFrame:
    """Compare each oracle variant against the truth rows."""

    truth = variant_long.loc[variant_long["variant"] == "truth", ["run_dir", "day", "shifted_kwh", "rebound_kwh", "peak_kw"]]
    truth = truth.rename(
        columns={
            "shifted_kwh": "shifted_true_kwh",
            "rebound_kwh": "rebound_true_kwh",
            "peak_kw": "peak_true_kw",
        }
    )
    rows: list[dict[str, Any]] = []
    for variant, variant_df in variant_long.groupby("variant", sort=True):
        if variant == "truth":
            continue
        merged = variant_df.merge(truth, on=["run_dir", "day"], how="inner", validate="one_to_one")
        rows.append(
            {
                "variant": str(variant),
                "n_days": int(len(merged)),
                "shifted_r2": _safe_r2(merged["shifted_true_kwh"], merged["shifted_kwh"]),
                "rebound_r2": _safe_r2(merged["rebound_true_kwh"], merged["rebound_kwh"]),
                "peak_r2": _safe_r2(merged["peak_true_kw"], merged["peak_kw"]),
                "shifted_mae": float(mean_absolute_error(merged["shifted_true_kwh"], merged["shifted_kwh"])),
                "rebound_mae": float(mean_absolute_error(merged["rebound_true_kwh"], merged["rebound_kwh"])),
                "peak_mae": float(mean_absolute_error(merged["peak_true_kw"], merged["peak_kw"])),
            }
        )
    return pd.DataFrame(rows).sort_values(["rebound_r2", "shifted_r2"], ascending=[False, False])


def _build_hourly_error_table(holdout: pd.DataFrame) -> pd.DataFrame:
    """Summarize q-delta errors by hour, family and coarse regimes."""

    frame = holdout.copy()
    frame["q_delta_error_kwh"] = frame["q_delta_pred_kwh"] - frame["q_delta_true_kwh"]
    frame["abs_error_kwh"] = frame["q_delta_error_kwh"].abs()
    frame["true_positive_kwh"] = np.maximum(frame["q_delta_true_kwh"].to_numpy(dtype=float), 0.0)
    frame["pred_positive_kwh"] = np.maximum(frame["q_delta_pred_kwh"].to_numpy(dtype=float), 0.0)
    frame["true_negative_kwh"] = np.maximum(-frame["q_delta_true_kwh"].to_numpy(dtype=float), 0.0)
    frame["pred_negative_kwh"] = np.maximum(-frame["q_delta_pred_kwh"].to_numpy(dtype=float), 0.0)
    frame["sign_mismatch"] = (
        np.sign(frame["q_delta_true_kwh"].to_numpy(dtype=float))
        != np.sign(frame["q_delta_pred_kwh"].to_numpy(dtype=float))
    )
    grouped = frame.groupby(["season_regime", "age_bin", "sector", "hour_block", "hour"], sort=True)
    out = grouped.agg(
        rows=("q_delta_error_kwh", "size"),
        mean_error_kwh=("q_delta_error_kwh", "mean"),
        mae_kwh=("abs_error_kwh", "mean"),
        true_positive_kwh=("true_positive_kwh", "sum"),
        pred_positive_kwh=("pred_positive_kwh", "sum"),
        true_negative_kwh=("true_negative_kwh", "sum"),
        pred_negative_kwh=("pred_negative_kwh", "sum"),
        sign_mismatch_share=("sign_mismatch", "mean"),
    ).reset_index()
    out["positive_mass_error_kwh"] = out["pred_positive_kwh"] - out["true_positive_kwh"]
    out["negative_mass_error_kwh"] = out["pred_negative_kwh"] - out["true_negative_kwh"]
    return out.sort_values("mae_kwh", ascending=False)


def _build_cohort_family_error_table(holdout: pd.DataFrame, daily_df: pd.DataFrame) -> pd.DataFrame:
    """Approximate family contributions to shifted/rebound failures."""

    first_negative_by_day = daily_df.set_index(["run_dir", "day"])["true_first_negative_hour"].to_dict()
    frame = holdout.copy()
    frame["true_positive_kwh"] = np.maximum(frame["q_delta_true_kwh"].to_numpy(dtype=float), 0.0)
    frame["pred_positive_kwh"] = np.maximum(frame["q_delta_pred_kwh"].to_numpy(dtype=float), 0.0)
    frame["true_negative_kwh"] = np.maximum(-frame["q_delta_true_kwh"].to_numpy(dtype=float), 0.0)
    frame["pred_negative_kwh"] = np.maximum(-frame["q_delta_pred_kwh"].to_numpy(dtype=float), 0.0)
    frame["true_abs_kwh"] = np.abs(frame["q_delta_true_kwh"].to_numpy(dtype=float))
    frame["pred_abs_kwh"] = np.abs(frame["q_delta_pred_kwh"].to_numpy(dtype=float))
    frame["true_first_negative_hour"] = [
        first_negative_by_day.get((row.run_dir, row.day), -1.0)
        for row in frame[["run_dir", "day"]].itertuples(index=False)
    ]
    frame["after_true_first_negative"] = (
        (frame["true_first_negative_hour"] >= 0.0)
        & (frame["hour"].to_numpy(dtype=float) > frame["true_first_negative_hour"].to_numpy(dtype=float))
    )
    frame["true_rebound_tail_kwh"] = np.where(frame["after_true_first_negative"], frame["true_positive_kwh"], 0.0)
    frame["pred_rebound_tail_kwh"] = np.where(frame["after_true_first_negative"], frame["pred_positive_kwh"], 0.0)
    grouped = frame.groupby(["season_regime", "age_bin", "age_family", "sector", "cohort_key"], sort=True)
    out = grouped.agg(
        rows=("q_delta_true_kwh", "size"),
        true_abs_kwh=("true_abs_kwh", "sum"),
        pred_abs_kwh=("pred_abs_kwh", "sum"),
        true_positive_kwh=("true_positive_kwh", "sum"),
        pred_positive_kwh=("pred_positive_kwh", "sum"),
        true_negative_kwh=("true_negative_kwh", "sum"),
        pred_negative_kwh=("pred_negative_kwh", "sum"),
        true_rebound_tail_kwh=("true_rebound_tail_kwh", "sum"),
        pred_rebound_tail_kwh=("pred_rebound_tail_kwh", "sum"),
    ).reset_index()
    out["abs_mass_error_kwh"] = out["pred_abs_kwh"] - out["true_abs_kwh"]
    out["positive_mass_error_kwh"] = out["pred_positive_kwh"] - out["true_positive_kwh"]
    out["negative_mass_error_kwh"] = out["pred_negative_kwh"] - out["true_negative_kwh"]
    out["rebound_tail_error_kwh"] = out["pred_rebound_tail_kwh"] - out["true_rebound_tail_kwh"]
    out["rebound_tail_abs_error_kwh"] = out["rebound_tail_error_kwh"].abs()
    return out.sort_values("rebound_tail_abs_error_kwh", ascending=False)


def _scale_components_to_mass(
    *,
    source_diff: np.ndarray,
    positive_mass: float,
    negative_mass: float,
) -> np.ndarray:
    """Keep source timing/sign and replace only total positive/negative mass."""

    source = np.asarray(source_diff, dtype=float).reshape(-1)
    pos = np.maximum(source, 0.0)
    neg = np.maximum(-source, 0.0)
    if float(np.sum(pos)) > 1e-9:
        pos = pos * (float(positive_mass) / float(np.sum(pos)))
    else:
        pos = np.zeros_like(source)
    if float(np.sum(neg)) > 1e-9:
        neg = neg * (float(negative_mass) / float(np.sum(neg)))
    else:
        neg = np.zeros_like(source)
    return pos - neg


def _sequence_stats(diff: np.ndarray, activation_threshold_kwh: float) -> dict[str, float]:
    """Return sign/mass state for one daily aggregate heat-delta sequence."""

    arr = np.asarray(diff, dtype=float).reshape(-1)
    negative_idx = np.where(arr < -1e-9)[0]
    first_negative = float(negative_idx[0]) if len(negative_idx) else -1.0
    if first_negative >= 0.0:
        tail = arr[int(first_negative) + 1 :]
        positive_after_first_negative = float(np.sum(tail[tail > 1e-9]))
    else:
        positive_after_first_negative = 0.0
    positive_mass = _positive_mass(arr)
    negative_mass = _negative_mass(arr)
    abs_mass = float(np.sum(np.abs(arr)))
    return {
        "positive_mass_kwh": positive_mass,
        "negative_mass_kwh": negative_mass,
        "abs_mass_kwh": abs_mass,
        "shifted_from_abs_kwh": abs_mass / 2.0,
        "first_negative_hour": first_negative,
        "positive_after_first_negative_kwh": positive_after_first_negative,
        "positive_hour_count": float(np.sum(arr > 1e-9)),
        "negative_hour_count": float(np.sum(arr < -1e-9)),
        "active_state": float(max(positive_mass, negative_mass, positive_after_first_negative) >= activation_threshold_kwh),
    }


def _positive_mass(diff: np.ndarray) -> float:
    arr = np.asarray(diff, dtype=float)
    return float(np.sum(arr[arr > 1e-9]))


def _negative_mass(diff: np.ndarray) -> float:
    arr = np.asarray(diff, dtype=float)
    return float(-np.sum(arr[arr < -1e-9]))


def _safe_r2(y_true: Any, y_pred: Any) -> float:
    true = np.asarray(y_true, dtype=float)
    pred = np.asarray(y_pred, dtype=float)
    if len(true) < 2 or float(np.nanstd(true)) <= 1e-12:
        return float("nan")
    return float(r2_score(true, pred))


def _rebound_failure_mode(
    *,
    rebound_true: float,
    rebound_pred: float,
    activation_threshold_kwh: float,
) -> str:
    """Classify the daily rebound error into action-oriented buckets."""

    threshold = float(activation_threshold_kwh)
    true_value = float(rebound_true)
    pred_value = float(rebound_pred)
    if true_value < threshold and pred_value >= threshold:
        return "false_rebound_activation"
    if true_value >= threshold and pred_value < threshold:
        return "missed_rebound_activation"
    if true_value >= threshold and pred_value < 0.75 * true_value:
        return "rebound_underprediction"
    if true_value >= threshold and pred_value > 1.25 * true_value:
        return "rebound_overprediction"
    return "rebound_ok_or_small"


def _age_family(cohort_key: str) -> str:
    value = str(cohort_key)
    for marker in ("pre1975", "1975_1990", "1990_2000", "2000_2014"):
        if marker in value:
            return marker
    return "unknown"


def _sector(cohort_key: str) -> str:
    value = str(cohort_key)
    if value.startswith("non_residential"):
        return "non_residential"
    if value.startswith("residential"):
        return "residential"
    return "other"


def _season_regime(month: int) -> str:
    value = int(month)
    if value in {1, 2, 12}:
        return "winter"
    if value in {3, 4, 10, 11}:
        return "shoulder"
    return "other"


def _hour_block(hour: int) -> str:
    h = int(hour)
    if 0 <= h <= 5:
        return "night"
    if 6 <= h <= 10:
        return "morning"
    if 11 <= h <= 16:
        return "midday"
    if 17 <= h <= 20:
        return "evening"
    return "late"


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Diagnose upper-only sequence failures with oracle ablations."
    )
    parser.add_argument("--model-dir", type=Path, default=DEFAULT_MODEL_DIR)
    parser.add_argument("--dataset-dir", type=Path, default=DEFAULT_DATASET_DIR)
    parser.add_argument("--output-dir", type=Path, default=None)
    parser.add_argument("--activation-threshold-kwh", type=float, default=25_000.0)
    args = parser.parse_args()
    summary = diagnose_upper_only_sequence_failure(
        model_dir=args.model_dir,
        dataset_dir=args.dataset_dir,
        output_dir=args.output_dir,
        activation_threshold_kwh=float(args.activation_threshold_kwh),
    )
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
