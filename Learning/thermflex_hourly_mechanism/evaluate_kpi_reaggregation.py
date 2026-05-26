from __future__ import annotations

"""Evaluate hourly mechanism models on day-level paper KPIs after re-aggregation.

Why this exists:
- the hourly mechanism path is only useful insofar as it improves the paper-
  relevant figure and KPI quantities,
- internal hourly target metrics alone are not enough to decide whether a new
  family slice, feature mode or truth expansion is actually better,
- the repo therefore needs one explicit, reusable evaluator that turns holdout
  hourly predictions back into day-level thermflex metrics.

This evaluator is intentionally strict:
- it requires both a model artifact dir and the matching curated dataset dir,
- it uses the persisted grouped-holdout test groups from the model artifact,
- it reconstructs predicted hourly cohort heat from predicted `q_delta` plus
  the reference heat that already lives in the curated truth table,
- it computes day-level KPI metrics with the same `compute_thermflex_series_metrics`
  helper used elsewhere in the repo,
- it fails fast if the required target or feature contract is missing.
"""

import argparse
import json
from pathlib import Path
from typing import Any

import joblib
import numpy as np
import pandas as pd
from sklearn.metrics import r2_score

from dispatch.metrics import compute_thermflex_series_metrics


def build_rebound_sequence_feature_payload(diff: np.ndarray) -> dict[str, float]:
    """Return explicit sign-sequence diagnostics for one hourly heat-delta day.

    These features are not a new KPI definition. They expose why the existing
    rebound KPI fires: when the first negative heat deviation appears, how much
    positive mass follows, and how large the positive/negative masses are. The
    upper-only failure diagnosis showed that this is the minimal state needed
    to separate false activation from real rebound underestimation.
    """

    arr = np.asarray(diff, dtype=float).reshape(-1)
    negative_idx = np.where(arr < -1e-9)[0]
    if len(negative_idx) == 0:
        first_negative_hour = -1.0
        positive_after_first_negative = 0.0
        hours_after_first_negative = 0.0
    else:
        first_negative_hour = float(negative_idx[0])
        tail = arr[int(negative_idx[0]) + 1 :]
        positive_after_first_negative = float(np.sum(tail[tail > 1e-9]))
        hours_after_first_negative = float(len(tail))
    positive_values = arr[arr > 1e-9]
    negative_values = arr[arr < -1e-9]
    positive_mass = float(np.sum(positive_values))
    negative_mass = float(-np.sum(negative_values))
    return {
        "seq_positive_mass_kwh": positive_mass,
        "seq_negative_mass_kwh": negative_mass,
        "seq_positive_after_first_negative_kwh": positive_after_first_negative,
        "seq_first_negative_hour": first_negative_hour,
        "seq_hours_after_first_negative": hours_after_first_negative,
        "seq_min_delta_kwh": float(np.min(arr)) if len(arr) else 0.0,
        "seq_max_delta_kwh": float(np.max(arr)) if len(arr) else 0.0,
        "seq_positive_hour_count": float(len(positive_values)),
        "seq_negative_hour_count": float(len(negative_values)),
    }


def evaluate_holdout_daily_reaggregation(
    *,
    model_dir: Path,
    dataset_dir: Path,
    shifted_postprocessor: dict[str, Any] | None = None,
    rebound_postprocessor: dict[str, Any] | None = None,
    peak_postprocessor: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Reconstruct holdout-run day KPIs from one hourly mechanism model.

    The current hourly mechanism models all need the predicted `q_delta` to
    rebuild the hourly cohort heat trajectory. The remaining thermflex day KPIs
    are then derived from the rebuilt heat series and the known reference
    series. This function therefore stays narrowly scoped to that contract.
    """

    model_root = Path(model_dir).resolve()
    dataset_root = Path(dataset_dir).resolve()
    bundle_path = model_root / "thermflex_hourly_mechanism_xgb.joblib"
    split_path = model_root / "holdout_split.json"
    truth_csv_path = dataset_root / "truth_dataset.csv"
    meta_path = dataset_root / "training_data.meta.json"

    if not bundle_path.exists():
        raise FileNotFoundError(
            "[thermflex_hourly_mechanism] model artifact bundle not found: "
            f"{bundle_path}"
        )
    if not split_path.exists():
        raise FileNotFoundError(
            "[thermflex_hourly_mechanism] holdout split json not found: "
            f"{split_path}"
        )
    if not truth_csv_path.exists():
        raise FileNotFoundError(
            "[thermflex_hourly_mechanism] curated hourly truth csv not found: "
            f"{truth_csv_path}"
        )
    if not meta_path.exists():
        raise FileNotFoundError(
            "[thermflex_hourly_mechanism] curated hourly dataset meta not found: "
            f"{meta_path}"
        )

    bundle = joblib.load(bundle_path)
    split_payload = json.loads(split_path.read_text(encoding="utf-8"))
    dataset_meta = json.loads(meta_path.read_text(encoding="utf-8"))
    truth = pd.read_csv(truth_csv_path)
    truth["timestamp"] = pd.to_datetime(truth["timestamp"], errors="raise")

    encoded_feature_columns = [
        str(value)
        for value in bundle.get("feature_columns", dataset_meta["encoded_feature_columns"])
    ]
    numeric_feature_columns = [str(value) for value in dataset_meta["feature_columns"]]
    categorical_feature_columns = [str(value) for value in dataset_meta["categorical_feature_columns"]]
    target_names = [str(value) for value in bundle["target_names"]]
    target_transforms = dict(bundle["target_transforms"])
    has_q_delta_intensive = "cohort_q_delta_wh_per_m2" in target_names
    has_q_delta_absolute = "cohort_q_delta_kwh" in target_names
    if not has_q_delta_intensive and not has_q_delta_absolute:
        raise ValueError(
            "[thermflex_hourly_mechanism] holdout KPI reaggregation requires either "
            "`cohort_q_delta_wh_per_m2` or `cohort_q_delta_kwh` in the model targets, "
            f"got {target_names}"
        )

    test_groups = {str(value) for value in split_payload["test_groups"]}
    holdout = truth.loc[truth["split_group_run"].astype(str).isin(test_groups)].copy()
    if holdout.empty:
        raise ValueError(
            "[thermflex_hourly_mechanism] holdout KPI reaggregation found no rows for persisted test groups in "
            f"{truth_csv_path}"
        )

    raw_feature_frame = holdout.loc[:, numeric_feature_columns + categorical_feature_columns].copy()
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

    q_ref = pd.to_numeric(holdout["cohort_q_heat_ref_kwh"], errors="raise").to_numpy(dtype=float)
    if has_q_delta_intensive:
        q_delta_wh_per_m2 = np.asarray(predictions["cohort_q_delta_wh_per_m2"], dtype=float)
        q_delta_pred_kwh = (
            q_delta_wh_per_m2
            * pd.to_numeric(holdout["cohort_floor_area_m2"], errors="raise").to_numpy(dtype=float)
            / 1000.0
        )
    else:
        q_delta_pred_kwh = np.asarray(predictions["cohort_q_delta_kwh"], dtype=float)
    holdout["cohort_q_heat_pred_kwh"] = q_ref + q_delta_pred_kwh

    daily_rows: list[dict[str, Any]] = []
    for run_dir, run_df in holdout.groupby("run_dir", sort=True):
        for day_ts, day_df in run_df.groupby(run_df["timestamp"].dt.floor("D")):
            q_pred = day_df.groupby("timestamp")["cohort_q_heat_pred_kwh"].sum().sort_index()
            q_ref = day_df.groupby("timestamp")["cohort_q_heat_ref_kwh"].sum().sort_index()
            q_true = day_df.groupby("timestamp")["cohort_q_heat_kwh"].sum().sort_index()
            predicted_metrics = compute_thermflex_series_metrics(q_pred, q_ref)
            true_metrics = compute_thermflex_series_metrics(q_true, q_ref)
            shifted_pred_raw = float(
                predicted_or_true_metric(predicted_metrics, "thermflex_shifted_space_heat_kwh")
            )
            rebound_pred_raw = float(predicted_or_true_metric(predicted_metrics, "thermflex_rebound_kwh"))
            peak_pred_raw = float(predicted_or_true_metric(predicted_metrics, "thermflex_peak_change_kw"))
            daily_feature_payload = _build_daily_postprocessor_feature_payload(
                day_ts=pd.Timestamp(day_ts),
                day_df=day_df,
                shifted_pred_raw=shifted_pred_raw,
                rebound_pred_raw=rebound_pred_raw,
                peak_pred_raw=peak_pred_raw,
            )
            daily_feature_payload.update(
                build_rebound_sequence_feature_payload(q_pred.to_numpy(dtype=float) - q_ref.to_numpy(dtype=float))
            )
            shifted_pred = _resolve_shifted_prediction(
                default_shifted_kwh=shifted_pred_raw,
                shifted_postprocessor=shifted_postprocessor,
                daily_feature_payload=daily_feature_payload,
            )
            rebound_pred = _resolve_rebound_prediction(
                q_pred=q_pred.to_numpy(dtype=float),
                q_ref=q_ref.to_numpy(dtype=float),
                default_rebound_kwh=rebound_pred_raw,
                rebound_postprocessor=rebound_postprocessor,
                daily_feature_payload=daily_feature_payload,
            )
            peak_pred = _resolve_peak_prediction(
                default_peak_change_kw=peak_pred_raw,
                peak_postprocessor=peak_postprocessor,
            )
            daily_rows.append(
                {
                    "run_dir": str(run_dir),
                    "day": pd.Timestamp(day_ts),
                    "thermflex_shifted_space_heat_kwh_true": float(
                        predicted_or_true_metric(true_metrics, "thermflex_shifted_space_heat_kwh")
                    ),
                    "thermflex_shifted_space_heat_kwh_pred_raw": shifted_pred_raw,
                    "thermflex_shifted_space_heat_kwh_pred": shifted_pred,
                    "thermflex_rebound_kwh_true": float(
                        predicted_or_true_metric(true_metrics, "thermflex_rebound_kwh")
                    ),
                    "thermflex_rebound_kwh_pred_raw": rebound_pred_raw,
                    "thermflex_rebound_kwh_pred": rebound_pred,
                    "thermflex_peak_change_kw_true": float(
                        predicted_or_true_metric(true_metrics, "thermflex_peak_change_kw")
                    ),
                    "thermflex_peak_change_kw_pred_raw": peak_pred_raw,
                    "thermflex_peak_change_kw_pred": peak_pred,
                    **daily_feature_payload,
                }
            )

    daily_df = pd.DataFrame(daily_rows)
    metrics_payload = {
        "shifted_r2": _safe_r2(
            daily_df["thermflex_shifted_space_heat_kwh_true"].to_numpy(dtype=float),
            daily_df["thermflex_shifted_space_heat_kwh_pred"].to_numpy(dtype=float),
        ),
        "rebound_r2": _safe_r2(
            daily_df["thermflex_rebound_kwh_true"].to_numpy(dtype=float),
            daily_df["thermflex_rebound_kwh_pred"].to_numpy(dtype=float),
        ),
        "peak_r2": _safe_r2(
            daily_df["thermflex_peak_change_kw_true"].to_numpy(dtype=float),
            daily_df["thermflex_peak_change_kw_pred"].to_numpy(dtype=float),
        ),
        "n_holdout_days": int(len(daily_df)),
        "n_holdout_runs": int(daily_df["run_dir"].nunique()),
    }
    return {
        "metrics": metrics_payload,
        "daily_df": daily_df,
    }


def _build_daily_postprocessor_feature_payload(
    *,
    day_ts: pd.Timestamp,
    day_df: pd.DataFrame,
    shifted_pred_raw: float,
    rebound_pred_raw: float,
    peak_pred_raw: float,
) -> dict[str, float]:
    """Build stable daily features used only by explicit KPI postprocessors.

    The base hourly model remains the source of the reconstructed heat series.
    These aggregate features are deliberately kept out of the low-level metric
    definition; they only support opt-in postprocessors that are persisted next
    to a model artifact.
    """

    q_ref_hourly = (
        day_df.groupby("timestamp")["cohort_q_heat_ref_kwh"].sum().sort_index()
    )
    q_ref_sum_kwh = float(q_ref_hourly.sum())
    if q_ref_sum_kwh <= 0.0:
        raise ValueError(
            "[thermflex_hourly_mechanism] daily postprocessor features require positive reference heat."
        )
    t_outdoor = pd.to_numeric(day_df["t_outdoor_c"], errors="raise")
    dh_space_heat_sum = float(pd.to_numeric(day_df["dh_space_heat_kwh"], errors="raise").sum())
    month = float(pd.Timestamp(day_ts).month)
    return {
        "shifted_raw_kwh": float(shifted_pred_raw),
        "rebound_raw_kwh": float(rebound_pred_raw),
        "peak_raw_kw": float(peak_pred_raw),
        "month": month,
        "day_of_year": float(pd.Timestamp(day_ts).dayofyear),
        "t_outdoor_mean_c": float(t_outdoor.mean()),
        "t_outdoor_min_c": float(t_outdoor.min()),
        "t_outdoor_max_c": float(t_outdoor.max()),
        "t_outdoor_range_c": float(t_outdoor.max() - t_outdoor.min()),
        "dh_space_heat_kwh_sum": dh_space_heat_sum,
        "dh_total_kwh_sum": float(pd.to_numeric(day_df["dh_total_kwh"], errors="raise").sum()),
        "irradiance_proxy_sum": float(pd.to_numeric(day_df["irradiance_proxy"], errors="raise").sum()),
        "solargains_proxy_sum": float(pd.to_numeric(day_df["solargains_proxy"], errors="raise").sum()),
        "q_ref_sum_kwh": q_ref_sum_kwh,
        "q_ref_peak_kw": float(q_ref_hourly.max()),
        "q_ref_min_kw": float(q_ref_hourly.min()),
        "q_ref_range_kw": float(q_ref_hourly.max() - q_ref_hourly.min()),
        "dh_per_q_ref": float(dh_space_heat_sum / q_ref_sum_kwh),
        "dh_space_heat_to_q_ref": float(dh_space_heat_sum / q_ref_sum_kwh),
        "is_winter_month": float(month in {1.0, 2.0, 12.0}),
        "is_spring_month": float(month in {3.0, 4.0}),
        "is_autumn_month": float(month in {10.0, 11.0}),
    }


def predicted_or_true_metric(payload: dict[str, Any], key: str) -> float:
    """Read one scalar thermflex metric from the dispatch metric payload."""

    if key not in payload:
        raise KeyError(f"[thermflex_hourly_mechanism] thermflex metrics payload missing key `{key}`")
    return float(payload[key])


def _resolve_rebound_prediction(
    *,
    q_pred: np.ndarray,
    q_ref: np.ndarray,
    default_rebound_kwh: float,
    rebound_postprocessor: dict[str, Any] | None,
    daily_feature_payload: dict[str, float],
) -> float:
    """Return the rebound KPI, optionally through an explicit postprocessor.

    Why this exists:
    - the base hourly mechanism path is generally useful, but the lower-relax
      `evt24` rebound holdout showed a specific failure mode,
    - tiny early negative prediction noise triggered the KPI rebound logic and
      caused large false-positive daily rebound on otherwise zero-rebound days,
    - we therefore allow one explicit, persisted rebound postprocessor that can
      be activated per model artifact instead of hiding a global metric change.
    """

    if rebound_postprocessor is None:
        return float(default_rebound_kwh)
    post_type = str(rebound_postprocessor.get("type", "")).strip().lower()
    if post_type == "two_stage_daily_rebound_v1":
        import joblib

        feature_columns = [str(value) for value in rebound_postprocessor["feature_columns"]]
        missing = sorted(set(feature_columns).difference(daily_feature_payload))
        if missing:
            raise KeyError(
                "[thermflex_hourly_mechanism] rebound two-stage postprocessor feature payload missing: "
                + ", ".join(missing)
            )
        features = np.asarray([[float(daily_feature_payload[column]) for column in feature_columns]], dtype=float)
        classifier_path = Path(str(rebound_postprocessor["classifier_model_path"])).resolve()
        regressor_path = Path(str(rebound_postprocessor["regressor_model_path"])).resolve()
        if not classifier_path.exists():
            raise FileNotFoundError(
                "[thermflex_hourly_mechanism] rebound classifier model not found: "
                f"{classifier_path}"
            )
        if not regressor_path.exists():
            raise FileNotFoundError(
                "[thermflex_hourly_mechanism] rebound regressor model not found: "
                f"{regressor_path}"
            )
        classifier = joblib.load(classifier_path)
        regressor = joblib.load(regressor_path)
        active_threshold = float(rebound_postprocessor["active_probability_threshold"])
        active_probability = float(classifier.predict_proba(features)[0, 1])
        if active_probability < active_threshold:
            return 0.0
        return float(max(0.0, float(regressor.predict(features)[0])))
    if post_type == "daily_xgb_rebound_v1":
        import joblib

        feature_columns = [str(value) for value in rebound_postprocessor["feature_columns"]]
        model_path = Path(str(rebound_postprocessor["model_path"])).resolve()
        if not model_path.exists():
            raise FileNotFoundError(
                "[thermflex_hourly_mechanism] rebound postprocessor model not found: "
                f"{model_path}"
            )
        missing = sorted(set(feature_columns).difference(daily_feature_payload))
        if missing:
            raise KeyError(
                "[thermflex_hourly_mechanism] rebound postprocessor feature payload missing: "
                + ", ".join(missing)
            )
        model = joblib.load(model_path)
        features = np.asarray([[float(daily_feature_payload[column]) for column in feature_columns]], dtype=float)
        return float(model.predict(features)[0])
    if post_type != "deadband_scaled_rebound_v1":
        raise ValueError(
            "[thermflex_hourly_mechanism] unsupported rebound postprocessor type: "
            f"{rebound_postprocessor.get('type')}"
        )
    negative_trigger_deadband_kwh = float(rebound_postprocessor["negative_trigger_deadband_kwh"])
    positive_accumulation_deadband_kwh = float(rebound_postprocessor["positive_accumulation_deadband_kwh"])
    scale = float(rebound_postprocessor["scale"])
    rebound_raw = _rebound_after_reduction_with_deadbands(
        np.asarray(q_pred, dtype=float) - np.asarray(q_ref, dtype=float),
        negative_trigger_deadband_kwh=negative_trigger_deadband_kwh,
        positive_accumulation_deadband_kwh=positive_accumulation_deadband_kwh,
    )
    return float(scale * rebound_raw)


def _resolve_peak_prediction(
    *,
    default_peak_change_kw: float,
    peak_postprocessor: dict[str, Any] | None,
) -> float:
    """Return the peak KPI, optionally through an explicit postprocessor."""

    if peak_postprocessor is None:
        return float(default_peak_change_kw)
    post_type = str(peak_postprocessor.get("type", "")).strip().lower()
    if post_type != "signed_peak_scale_v1":
        raise ValueError(
            "[thermflex_hourly_mechanism] unsupported peak postprocessor type: "
            f"{peak_postprocessor.get('type')}"
        )
    negative_scale = float(peak_postprocessor["negative_scale"])
    nonnegative_scale = float(peak_postprocessor["nonnegative_scale"])
    if float(default_peak_change_kw) < 0.0:
        return float(negative_scale * float(default_peak_change_kw))
    return float(nonnegative_scale * float(default_peak_change_kw))


def _resolve_shifted_prediction(
    *,
    default_shifted_kwh: float,
    shifted_postprocessor: dict[str, Any] | None,
    daily_feature_payload: dict[str, float],
) -> float:
    """Return shifted heat, optionally through an explicit daily postprocessor."""

    if shifted_postprocessor is None:
        return float(default_shifted_kwh)
    post_type = str(shifted_postprocessor.get("type", "")).strip().lower()
    if post_type != "daily_xgb_shifted_v1":
        raise ValueError(
            "[thermflex_hourly_mechanism] unsupported shifted postprocessor type: "
            f"{shifted_postprocessor.get('type')}"
        )
    import joblib

    feature_columns = [str(value) for value in shifted_postprocessor["feature_columns"]]
    model_path = Path(str(shifted_postprocessor["model_path"])).resolve()
    if not model_path.exists():
        raise FileNotFoundError(
            "[thermflex_hourly_mechanism] shifted postprocessor model not found: "
            f"{model_path}"
        )
    missing = sorted(set(feature_columns).difference(daily_feature_payload))
    if missing:
        raise KeyError(
            "[thermflex_hourly_mechanism] shifted postprocessor feature payload missing: "
            + ", ".join(missing)
        )
    model = joblib.load(model_path)
    features = np.asarray([[float(daily_feature_payload[column]) for column in feature_columns]], dtype=float)
    return float(model.predict(features)[0])


def _rebound_after_reduction_with_deadbands(
    diff: np.ndarray,
    *,
    negative_trigger_deadband_kwh: float,
    positive_accumulation_deadband_kwh: float,
) -> float:
    """Variant of the rebound KPI with explicit deadbands on trigger and mass.

    Why the two thresholds are separate:
    - the lower-relax holdout failure came mainly from small early negative
      noise that incorrectly activated the rebound regime,
    - once that regime is active, later positive heat should still be counted
      with a much smaller threshold than the negative trigger itself.
    """

    negative_seen = False
    rebound = 0.0
    for value in np.asarray(diff, dtype=float).reshape(-1):
        if value < -float(negative_trigger_deadband_kwh):
            negative_seen = True
            continue
        if negative_seen and value > float(positive_accumulation_deadband_kwh):
            rebound += float(value)
    return float(rebound)


def _invert_target_transform(values: np.ndarray, transform_name: str) -> np.ndarray:
    arr = np.asarray(values, dtype=float)
    if transform_name == "identity":
        return arr
    if transform_name == "signed_log1p":
        return np.sign(arr) * np.expm1(np.abs(arr))
    raise ValueError(f"[thermflex_hourly_mechanism] unsupported target transform: {transform_name}")


def _safe_r2(y_true: np.ndarray, y_pred: np.ndarray) -> float:
    values = np.asarray(y_true, dtype=float)
    if len(values) <= 1 or float(np.nanmax(values) - np.nanmin(values)) <= 1e-12:
        return float("nan")
    return float(r2_score(values, np.asarray(y_pred, dtype=float)))


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Evaluate one hourly thermflex mechanism model on holdout daily KPI reaggregation."
    )
    parser.add_argument(
        "--model-dir",
        type=Path,
        required=True,
        help="Model artifact directory under Learning/models/...",
    )
    parser.add_argument(
        "--dataset-dir",
        type=Path,
        required=True,
        help="Matching curated dataset directory under Learning/datasets/...",
    )
    parser.add_argument(
        "--write-daily-csv",
        action="store_true",
        help="Persist the holdout daily reconstruction csv next to the model artifact.",
    )
    parser.add_argument(
        "--rebound-postprocessor-path",
        type=Path,
        default=None,
        help="Optional JSON payload for an explicit rebound postprocessor.",
    )
    parser.add_argument(
        "--peak-postprocessor-path",
        type=Path,
        default=None,
        help="Optional JSON payload for an explicit peak postprocessor.",
    )
    parser.add_argument(
        "--shifted-postprocessor-path",
        type=Path,
        default=None,
        help="Optional JSON payload for an explicit shifted postprocessor.",
    )
    args = parser.parse_args()

    rebound_postprocessor = None
    if args.rebound_postprocessor_path is not None:
        rebound_postprocessor = json.loads(Path(args.rebound_postprocessor_path).read_text(encoding="utf-8"))
    peak_postprocessor = None
    if args.peak_postprocessor_path is not None:
        peak_postprocessor = json.loads(Path(args.peak_postprocessor_path).read_text(encoding="utf-8"))
    shifted_postprocessor = None
    if args.shifted_postprocessor_path is not None:
        shifted_postprocessor = json.loads(Path(args.shifted_postprocessor_path).read_text(encoding="utf-8"))

    result = evaluate_holdout_daily_reaggregation(
        model_dir=args.model_dir,
        dataset_dir=args.dataset_dir,
        shifted_postprocessor=shifted_postprocessor,
        rebound_postprocessor=rebound_postprocessor,
        peak_postprocessor=peak_postprocessor,
    )
    metrics = result["metrics"]
    print(json.dumps(metrics, indent=2))

    if bool(args.write_daily_csv):
        output_path = Path(args.model_dir).resolve() / "holdout_daily_reconstruction.csv"
        result["daily_df"].to_csv(output_path, index=False)
        print(str(output_path))


if __name__ == "__main__":
    main()
