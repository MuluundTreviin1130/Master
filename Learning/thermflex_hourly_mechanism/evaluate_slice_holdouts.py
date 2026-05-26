from __future__ import annotations

"""Evaluate hourly ThermFlex mechanism quality by policy and weather slices.

Why this exists:
- the dispatch surrogate is strong when the true ThermFlex load response is
  supplied as an oracle feature,
- the end-to-end chain is weak when that load response is predicted first,
- we therefore need a focused diagnostic that tells us which mechanism/load
  families cause the error before collecting more truth.

This file is diagnostic-only. It trains repeated grouped holdouts from one
curated `Learning/datasets/` mechanism dataset, re-aggregates hourly cohort heat
predictions to daily ThermFlex KPIs, and writes slice metrics. It does not
register or mark any production model.
"""

import argparse
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from sklearn.model_selection import GroupShuffleSplit
from xgboost import XGBRegressor

from dispatch.metrics import compute_thermflex_series_metrics
from Learning.datasets.load_dataset import load_dataset
from Learning.thermflex_hourly_mechanism.train import (
    _apply_target_transform,
    _invert_target_transform,
    _resolve_model_params,
)

_DEFAULT_DATASET_ROOT = Path(__file__).resolve().parents[2] / "Learning" / "datasets"
_DEFAULT_MODEL_ROOT = Path(__file__).resolve().parents[2] / "Learning" / "models"


@dataclass(frozen=True)
class MechanismSliceHoldoutResult:
    diagnostic_dir: Path
    hourly_metrics_csv: Path
    daily_metrics_csv: Path
    daily_predictions_csv: Path
    summary_json: Path


def evaluate_mechanism_slice_holdouts(
    *,
    family_hash: str,
    dataset_root: Path = _DEFAULT_DATASET_ROOT,
    model_root: Path = _DEFAULT_MODEL_ROOT,
    group_column: str = "split_group_run",
    test_size: float = 0.25,
    first_seed: int = 0,
    n_seeds: int = 5,
    output_name: str | None = None,
) -> MechanismSliceHoldoutResult:
    """Run repeated grouped holdouts and persist hourly/daily slice metrics."""

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
    if group_column not in truth_df.columns:
        raise KeyError(f"[thermflex_hourly_mechanism] group column not found: {group_column}")
    if len(truth_df) != int(np.asarray(dataset_bundle["X"]).shape[0]):
        raise ValueError("[thermflex_hourly_mechanism] truth rows and design matrix rows do not match.")

    target_names = [str(value) for value in dataset_bundle["meta"]["target_columns"]]
    _validate_required_targets(target_names)
    x_all = np.asarray(dataset_bundle["X"], dtype=float)
    y_all = np.asarray(dataset_bundle["Y"], dtype=float)
    groups = truth_df[group_column].astype(str).to_numpy()
    if len(set(groups)) < 3:
        raise ValueError("[thermflex_hourly_mechanism] slice holdouts require at least three split groups.")

    hourly_rows: list[dict[str, Any]] = []
    daily_rows: list[dict[str, Any]] = []
    daily_prediction_rows: list[pd.DataFrame] = []

    for seed in range(int(first_seed), int(first_seed) + int(n_seeds)):
        train_index, test_index = next(
            GroupShuffleSplit(n_splits=1, test_size=float(test_size), random_state=seed).split(
                x_all,
                y_all,
                groups=groups,
            )
        )
        predictions = _fit_predict_targets(
            x_train=x_all[train_index],
            y_train=y_all[train_index],
            x_test=x_all[test_index],
            target_names=target_names,
            random_state=seed,
        )
        holdout = truth_df.iloc[test_index].copy()
        _append_hourly_metrics(
            rows=hourly_rows,
            seed=seed,
            truth_df=holdout,
            target_names=target_names,
            y_true=y_all[test_index],
            y_pred=predictions,
        )
        daily_df = _build_daily_kpi_predictions(
            seed=seed,
            holdout=holdout,
            target_names=target_names,
            y_pred=predictions,
        )
        daily_prediction_rows.append(daily_df)
        _append_daily_metrics(rows=daily_rows, seed=seed, daily_df=daily_df)

    diagnostic_dir = _diagnostic_dir(
        model_root=Path(model_root),
        family_hash=family_hash,
        output_name=output_name,
    )
    diagnostic_dir.mkdir(parents=True, exist_ok=True)
    hourly_metrics_csv = diagnostic_dir / "hourly_slice_metrics.csv"
    daily_metrics_csv = diagnostic_dir / "daily_kpi_slice_metrics.csv"
    daily_predictions_csv = diagnostic_dir / "daily_kpi_predictions.csv"
    summary_json = diagnostic_dir / "summary.json"

    hourly_df = pd.DataFrame(hourly_rows)
    daily_metrics_df = pd.DataFrame(daily_rows)
    daily_predictions_df = pd.concat(daily_prediction_rows, ignore_index=True)
    hourly_df.to_csv(hourly_metrics_csv, index=False)
    daily_metrics_df.to_csv(daily_metrics_csv, index=False)
    daily_predictions_df.to_csv(daily_predictions_csv, index=False)
    summary_payload = {
        "family_hash": str(family_hash),
        "dataset_id": str(dataset_bundle["meta"].get("dataset_id", "")),
        "family_slice": str(dataset_bundle["meta"].get("family_slice", "")),
        "feature_mode": str(dataset_bundle["meta"].get("feature_mode", "")),
        "target_columns": target_names,
        "group_column": str(group_column),
        "test_size": float(test_size),
        "first_seed": int(first_seed),
        "n_seeds": int(n_seeds),
        "hourly_summary": _summarize(hourly_df, group_cols=["slice_scope", "slice_value", "target"]),
        "daily_summary": _summarize(daily_metrics_df, group_cols=["slice_scope", "slice_value", "metric"]),
    }
    summary_json.write_text(json.dumps(summary_payload, indent=2), encoding="utf-8")
    return MechanismSliceHoldoutResult(
        diagnostic_dir=diagnostic_dir,
        hourly_metrics_csv=hourly_metrics_csv,
        daily_metrics_csv=daily_metrics_csv,
        daily_predictions_csv=daily_predictions_csv,
        summary_json=summary_json,
    )


def _fit_predict_targets(
    *,
    x_train: np.ndarray,
    y_train: np.ndarray,
    x_test: np.ndarray,
    target_names: list[str],
    random_state: int,
) -> np.ndarray:
    """Fit one XGB model per target with the established target transform."""

    pred_columns: list[np.ndarray] = []
    for target_index, target_name in enumerate(target_names):
        transform = _resolve_target_transform_for_diagnostic(target_name)
        transformed = _apply_target_transform(y_train[:, target_index], transform)
        model = XGBRegressor(**_resolve_model_params(target_name, random_state=random_state))
        model.fit(x_train, transformed)
        pred_columns.append(_invert_target_transform(model.predict(x_test), transform))
    return np.column_stack(pred_columns)


def _append_hourly_metrics(
    *,
    rows: list[dict[str, Any]],
    seed: int,
    truth_df: pd.DataFrame,
    target_names: list[str],
    y_true: np.ndarray,
    y_pred: np.ndarray,
) -> None:
    """Score raw hourly mechanism targets globally and by diagnostic slices."""

    slice_specs = _hourly_slice_specs(truth_df)
    for slice_scope, labels in slice_specs.items():
        for slice_value in sorted(labels.astype(str).unique()):
            mask = labels.astype(str).to_numpy() == str(slice_value)
            if not np.any(mask):
                continue
            for target_index, target in enumerate(target_names):
                rows.append(
                    {
                        "seed": int(seed),
                        "slice_scope": str(slice_scope),
                        "slice_value": str(slice_value),
                        "target": str(target),
                        **_metric_payload(y_true[mask, target_index], y_pred[mask, target_index]),
                        "n_test_rows": int(np.sum(mask)),
                        "n_test_runs": int(truth_df.loc[mask, "run_dir"].nunique()),
                    }
                )


def _build_daily_kpi_predictions(
    *,
    seed: int,
    holdout: pd.DataFrame,
    target_names: list[str],
    y_pred: np.ndarray,
) -> pd.DataFrame:
    """Rebuild daily heat series and paper-relevant mechanism KPIs."""

    q_delta_pred_kwh = _resolve_predicted_q_delta_kwh(
        holdout=holdout,
        target_names=target_names,
        y_pred=y_pred,
    )
    working = holdout.copy()
    working["cohort_q_delta_pred_kwh"] = q_delta_pred_kwh
    working["cohort_q_heat_pred_kwh"] = (
        pd.to_numeric(working["cohort_q_heat_ref_kwh"], errors="raise").to_numpy(dtype=float)
        + q_delta_pred_kwh
    )

    rows: list[dict[str, Any]] = []
    for run_dir, run_df in working.groupby("run_dir", sort=True):
        for day_ts, day_df in run_df.groupby(working.loc[run_df.index, "timestamp"].dt.floor("D")):
            q_pred = day_df.groupby("timestamp")["cohort_q_heat_pred_kwh"].sum().sort_index()
            q_ref = day_df.groupby("timestamp")["cohort_q_heat_ref_kwh"].sum().sort_index()
            q_true = day_df.groupby("timestamp")["cohort_q_heat_kwh"].sum().sort_index()
            pred_metrics = compute_thermflex_series_metrics(q_pred, q_ref)
            true_metrics = compute_thermflex_series_metrics(q_true, q_ref)
            rows.append(
                {
                    "seed": int(seed),
                    "run_dir": str(run_dir),
                    "day": pd.Timestamp(day_ts).date().isoformat(),
                    "source_bundle_name": str(day_df["source_bundle_name"].iloc[0]),
                    "policy_tau_h": float(pd.to_numeric(day_df["policy_tau_h"], errors="raise").iloc[0]),
                    "duration_h": float(
                        pd.to_numeric(day_df["thermflex_max_flex_duration_h"], errors="raise").iloc[0]
                    ),
                    "lower_band_k": float(_daily_lower_band(day_df)),
                    "policy_family": _policy_family(day_df),
                    "weather_month_regime": _weather_month_regime(pd.Timestamp(day_ts).month),
                    "temperature_bin": _temperature_bin(
                        float(pd.to_numeric(day_df["t_outdoor_c"], errors="raise").mean())
                    ),
                    "t_outdoor_mean_c": float(pd.to_numeric(day_df["t_outdoor_c"], errors="raise").mean()),
                    "true_q_delta_kwh_sum": float(
                        pd.to_numeric(day_df["cohort_q_delta_kwh"], errors="raise").sum()
                    ),
                    "pred_q_delta_kwh_sum": float(day_df["cohort_q_delta_pred_kwh"].sum()),
                    "true_shifted_kwh": _metric_value(true_metrics, "thermflex_shifted_space_heat_kwh"),
                    "pred_shifted_kwh": _metric_value(pred_metrics, "thermflex_shifted_space_heat_kwh"),
                    "true_rebound_kwh": _metric_value(true_metrics, "thermflex_rebound_kwh"),
                    "pred_rebound_kwh": _metric_value(pred_metrics, "thermflex_rebound_kwh"),
                    "true_peak_change_kw": _metric_value(true_metrics, "thermflex_peak_change_kw"),
                    "pred_peak_change_kw": _metric_value(pred_metrics, "thermflex_peak_change_kw"),
                }
            )
    return pd.DataFrame(rows)


def _append_daily_metrics(*, rows: list[dict[str, Any]], seed: int, daily_df: pd.DataFrame) -> None:
    """Score daily mechanism KPIs globally and by policy/weather slices."""

    metric_pairs = {
        "q_delta_sum_kwh": ("true_q_delta_kwh_sum", "pred_q_delta_kwh_sum"),
        "shifted_kwh": ("true_shifted_kwh", "pred_shifted_kwh"),
        "rebound_kwh": ("true_rebound_kwh", "pred_rebound_kwh"),
        "peak_change_kw": ("true_peak_change_kw", "pred_peak_change_kw"),
    }
    slice_specs = _daily_slice_specs(daily_df)
    for slice_scope, labels in slice_specs.items():
        for slice_value in sorted(labels.astype(str).unique()):
            mask = labels.astype(str).to_numpy() == str(slice_value)
            if not np.any(mask):
                continue
            for metric_name, (true_col, pred_col) in metric_pairs.items():
                rows.append(
                    {
                        "seed": int(seed),
                        "slice_scope": str(slice_scope),
                        "slice_value": str(slice_value),
                        "metric": str(metric_name),
                        **_metric_payload(
                            daily_df.loc[mask, true_col].to_numpy(dtype=float),
                            daily_df.loc[mask, pred_col].to_numpy(dtype=float),
                        ),
                        "n_test_days": int(np.sum(mask)),
                        "n_test_runs": int(daily_df.loc[mask, "run_dir"].nunique()),
                    }
                )


def _hourly_slice_specs(frame: pd.DataFrame) -> dict[str, pd.Series]:
    """Return stable per-row labels for mechanism diagnostic slices."""

    tau = pd.to_numeric(frame["policy_tau_h"], errors="raise").round(0).astype(int)
    duration = pd.to_numeric(frame["thermflex_max_flex_duration_h"], errors="raise").round(0).astype(int)
    temp = pd.to_numeric(frame["t_outdoor_c"], errors="raise")
    month = pd.to_numeric(frame["month"], errors="raise").astype(int)
    return {
        "ALL": pd.Series("ALL", index=frame.index),
        "policy_family": frame.apply(lambda row: _policy_family(pd.DataFrame([row])), axis=1),
        "tau": "tau" + tau.astype(str),
        "duration": "dur" + duration.astype(str),
        "tau_duration": "tau" + tau.astype(str) + "_dur" + duration.astype(str),
        "weather_month_regime": month.map(_weather_month_regime),
        "temperature_bin": temp.map(lambda value: _temperature_bin(float(value))),
        "cohort_key": frame["cohort_key"].astype(str),
    }


def _daily_slice_specs(frame: pd.DataFrame) -> dict[str, pd.Series]:
    """Return stable per-day labels for mechanism KPI diagnostics."""

    tau = pd.to_numeric(frame["policy_tau_h"], errors="raise").round(0).astype(int)
    duration = pd.to_numeric(frame["duration_h"], errors="raise").round(0).astype(int)
    return {
        "ALL": pd.Series("ALL", index=frame.index),
        "policy_family": frame["policy_family"].astype(str),
        "tau": "tau" + tau.astype(str),
        "duration": "dur" + duration.astype(str),
        "tau_duration": "tau" + tau.astype(str) + "_dur" + duration.astype(str),
        "weather_month_regime": frame["weather_month_regime"].astype(str),
        "temperature_bin": frame["temperature_bin"].astype(str),
    }


def _resolve_predicted_q_delta_kwh(
    *,
    holdout: pd.DataFrame,
    target_names: list[str],
    y_pred: np.ndarray,
) -> np.ndarray:
    """Resolve predicted absolute heat delta from intensive or absolute target."""

    if "cohort_q_delta_wh_per_m2" in target_names:
        idx = target_names.index("cohort_q_delta_wh_per_m2")
        floor_area = pd.to_numeric(holdout["cohort_floor_area_m2"], errors="raise").to_numpy(dtype=float)
        return np.asarray(y_pred[:, idx], dtype=float) * floor_area / 1000.0
    if "cohort_q_delta_kwh" in target_names:
        return np.asarray(y_pred[:, target_names.index("cohort_q_delta_kwh")], dtype=float)
    raise ValueError("[thermflex_hourly_mechanism] no q_delta target is available.")


def _policy_family(frame: pd.DataFrame) -> str:
    """Classify a policy row/day without relying on ad hoc case-label strings."""

    lower_band = float(_daily_lower_band(frame))
    if abs(lower_band) <= 1e-9:
        return "upper_only"
    return "lower_relax"


def _daily_lower_band(frame: pd.DataFrame) -> float:
    """Return the largest setpoint-to-lower-bound band in kelvin."""

    day_band = pd.to_numeric(frame["day_thermflex_temperature_band_k"], errors="raise").max()
    night_band = pd.to_numeric(frame["night_thermflex_temperature_band_k"], errors="raise").max()
    return float(max(float(day_band), float(night_band)))


def _weather_month_regime(month: int) -> str:
    """Coarse heating-year regime for diagnostics, not model activation."""

    month_int = int(month)
    if month_int in {12, 1, 2}:
        return "winter"
    if month_int in {3, 4, 10, 11}:
        return "shoulder"
    return "summer_other"


def _temperature_bin(t_outdoor_mean_c: float) -> str:
    """Temperature-state bin used only to expose holdout failure modes."""

    value = float(t_outdoor_mean_c)
    if value <= 5.0:
        return "cold_le5c"
    if value <= 15.0:
        return "mild_5_15c"
    return "warm_gt15c"


def _metric_value(payload: dict[str, Any], key: str) -> float:
    if key not in payload:
        raise KeyError(f"[thermflex_hourly_mechanism] thermflex metric missing key `{key}`")
    return float(payload[key])


def _metric_payload(y_true: np.ndarray, y_pred: np.ndarray) -> dict[str, float]:
    """Return R2 plus scale-aware errors so low-variance slices are interpretable."""

    truth = np.asarray(y_true, dtype=float)
    pred = np.asarray(y_pred, dtype=float)
    if truth.shape != pred.shape:
        raise ValueError("[thermflex_hourly_mechanism] metric arrays must have equal shape.")
    finite = np.isfinite(truth) & np.isfinite(pred)
    truth = truth[finite]
    pred = pred[finite]
    if truth.size == 0:
        return {
            "r2": float("nan"),
            "mae": float("nan"),
            "rmse": float("nan"),
            "true_abs_mean": float("nan"),
            "true_std": float("nan"),
        }
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
    if frame.empty:
        return []
    rows: list[dict[str, Any]] = []
    for key, group in frame.groupby(group_cols, sort=True, dropna=False):
        if not isinstance(key, tuple):
            key = (key,)
        row = {column: value for column, value in zip(group_cols, key)}
        for metric in ("r2", "mae", "rmse", "true_abs_mean", "true_std"):
            values = pd.to_numeric(group[metric], errors="coerce").to_numpy(dtype=float)
            row.update(_summary_metric_values(prefix=metric, values=values))
        n_col = "n_test_days" if "n_test_days" in group.columns else "n_test_rows"
        row[f"{n_col}_median"] = float(np.nanmedian(pd.to_numeric(group[n_col], errors="coerce")))
        rows.append(row)
    return rows


def _summary_metric_values(*, prefix: str, values: np.ndarray) -> dict[str, float]:
    """Summarize one metric vector without warning on deliberately NaN R2 slices."""

    finite = np.asarray(values, dtype=float)
    finite = finite[np.isfinite(finite)]
    if finite.size == 0:
        return {
            f"{prefix}_mean": float("nan"),
            f"{prefix}_median": float("nan"),
            f"{prefix}_min": float("nan"),
            f"{prefix}_max": float("nan"),
        }
    return {
        f"{prefix}_mean": float(np.mean(finite)),
        f"{prefix}_median": float(np.median(finite)),
        f"{prefix}_min": float(np.min(finite)),
        f"{prefix}_max": float(np.max(finite)),
    }


def _validate_required_targets(target_names: list[str]) -> None:
    if "cohort_q_delta_wh_per_m2" not in target_names and "cohort_q_delta_kwh" not in target_names:
        raise ValueError(
            "[thermflex_hourly_mechanism] slice holdout requires a q_delta target, got "
            + ", ".join(target_names)
        )


def _resolve_target_transform_for_diagnostic(target_name: str) -> str:
    if target_name in {
        "cohort_q_delta_kwh",
        "cohort_preheat_extra_kwh",
        "cohort_cutback_shed_kwh",
        "cohort_q_delta_wh_per_m2",
        "cohort_preheat_extra_wh_per_m2",
        "cohort_cutback_shed_wh_per_m2",
    }:
        return "signed_log1p"
    return "identity"


def _diagnostic_dir(*, model_root: Path, family_hash: str, output_name: str | None) -> Path:
    suffix = str(output_name).strip() if output_name else "slice_holdouts"
    if not suffix:
        raise ValueError("[thermflex_hourly_mechanism] output_name must not be empty.")
    return Path(model_root).resolve() / f"thermflex_hourly_mechanism_slice_holdouts_{family_hash[:12]}_{suffix}"


def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate hourly ThermFlex mechanism holdouts by slices.")
    parser.add_argument("--family-hash", required=True)
    parser.add_argument("--dataset-root", type=Path, default=_DEFAULT_DATASET_ROOT)
    parser.add_argument("--model-root", type=Path, default=_DEFAULT_MODEL_ROOT)
    parser.add_argument("--group-column", default="split_group_run")
    parser.add_argument("--test-size", type=float, default=0.25)
    parser.add_argument("--first-seed", type=int, default=0)
    parser.add_argument("--n-seeds", type=int, default=5)
    parser.add_argument("--output-name", default=None)
    args = parser.parse_args()
    result = evaluate_mechanism_slice_holdouts(
        family_hash=args.family_hash,
        dataset_root=args.dataset_root,
        model_root=args.model_root,
        group_column=args.group_column,
        test_size=args.test_size,
        first_seed=args.first_seed,
        n_seeds=args.n_seeds,
        output_name=args.output_name,
    )
    print(json.dumps({"diagnostic_dir": str(result.diagnostic_dir)}, indent=2))


if __name__ == "__main__":
    main()
