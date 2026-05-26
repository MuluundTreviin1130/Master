from __future__ import annotations

"""Evaluate daily peak and contiguous rolling-window KPIs from hourly predictions.

Hourly target R2 does not directly answer paper questions such as "does the
surrogate preserve the peak-boiler maximum?" or "does a weekly KPI table remain
accurate after aggregation?".  This diagnostic trains the same hourly dispatch
surrogate used elsewhere, reconstructs REF/FLEX hourly series for the holdout
policy-days, and evaluates:

- daily peak changes from reconstructed FLEX-vs-REF series,
- daily sums for the main targets, and
- contiguous rolling-window sums where the sparse truth basis actually contains
  complete windows.
"""

import argparse
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from sklearn.ensemble import ExtraTreesRegressor
from sklearn.metrics import r2_score
from sklearn.model_selection import GroupShuffleSplit

from Learning.datasets.load_dataset import load_dataset


_DEFAULT_DATASET_ROOT = Path(__file__).resolve().parents[2] / "Learning" / "datasets"
_DEFAULT_MODEL_ROOT = Path(__file__).resolve().parents[2] / "Learning" / "models"


@dataclass(frozen=True)
class PeakRollingEvaluationResult:
    diagnostic_dir: Path
    daily_peak_metrics_csv: Path
    rolling_metrics_csv: Path
    summary_json: Path


def evaluate_peak_rolling_holdouts(
    *,
    family_hash: str,
    dataset_root: Path = _DEFAULT_DATASET_ROOT,
    model_root: Path = _DEFAULT_MODEL_ROOT,
    group_column: str = "split_group_date",
    test_size: float = 0.3,
    first_seed: int = 0,
    n_seeds: int = 8,
    rolling_window_days: int = 7,
    output_name: str | None = None,
) -> PeakRollingEvaluationResult:
    dataset_bundle = load_dataset(Path(dataset_root), family_hash)
    if dataset_bundle is None:
        raise FileNotFoundError(
            "[thermflex_hourly_dispatch] curated dataset not found for family_hash="
            + str(family_hash)
        )
    truth_csv_path = dataset_bundle.get("truth_csv_path")
    if truth_csv_path is None:
        raise FileNotFoundError("[thermflex_hourly_dispatch] curated dataset is missing `truth_dataset.csv`.")
    truth_df = pd.read_csv(truth_csv_path)
    truth_df["date"] = pd.to_datetime(truth_df["date"], errors="raise")
    if group_column not in truth_df.columns:
        raise KeyError(f"[thermflex_hourly_dispatch] group column not found in truth table: {group_column}")

    x_all = np.asarray(dataset_bundle["X"], dtype=float)
    y_all = np.asarray(dataset_bundle["Y"], dtype=float)
    target_names = [str(value) for value in dataset_bundle["meta"]["target_columns"]]
    target_index = {target: idx for idx, target in enumerate(target_names)}
    groups = truth_df[group_column].astype(str).to_numpy()

    daily_peak_rows: list[dict[str, Any]] = []
    rolling_rows: list[dict[str, Any]] = []
    for seed in range(int(first_seed), int(first_seed) + int(n_seeds)):
        train_index, test_index = next(
            GroupShuffleSplit(n_splits=1, test_size=float(test_size), random_state=seed).split(
                x_all,
                y_all,
                groups=groups,
            )
        )
        model = ExtraTreesRegressor(
            n_estimators=500,
            min_samples_leaf=1,
            max_features=1.0,
            random_state=int(seed),
            n_jobs=-1,
        )
        model.fit(x_all[train_index], y_all[train_index])
        pred = np.asarray(model.predict(x_all[test_index]), dtype=float)
        test_truth = truth_df.iloc[test_index].copy().reset_index(drop=True)
        _append_daily_peak_metrics(
            rows=daily_peak_rows,
            seed=seed,
            truth_df=test_truth,
            target_index=target_index,
            y_true=y_all[test_index],
            y_pred=pred,
        )
        _append_rolling_sum_metrics(
            rows=rolling_rows,
            seed=seed,
            truth_df=test_truth,
            target_names=target_names,
            y_true=y_all[test_index],
            y_pred=pred,
            rolling_window_days=int(rolling_window_days),
        )

    diagnostic_dir = _diagnostic_dir(model_root=Path(model_root), family_hash=family_hash, output_name=output_name)
    diagnostic_dir.mkdir(parents=True, exist_ok=True)
    daily_peak_metrics_csv = diagnostic_dir / "daily_peak_metrics.csv"
    rolling_metrics_csv = diagnostic_dir / "rolling_window_metrics.csv"
    summary_json = diagnostic_dir / "summary.json"
    daily_peak_df = pd.DataFrame(daily_peak_rows)
    rolling_df = pd.DataFrame(rolling_rows)
    daily_peak_df.to_csv(daily_peak_metrics_csv, index=False)
    rolling_df.to_csv(rolling_metrics_csv, index=False)
    summary_payload = {
        "family_hash": str(family_hash),
        "group_column": str(group_column),
        "test_size": float(test_size),
        "first_seed": int(first_seed),
        "n_seeds": int(n_seeds),
        "rolling_window_days": int(rolling_window_days),
        "daily_peak_summary": _summarize(daily_peak_df, group_cols=["metric"]),
        "family_daily_peak_summary": _summarize(daily_peak_df, group_cols=["family", "metric"]),
        "rolling_summary": _summarize(rolling_df, group_cols=["target"]),
        "family_rolling_summary": _summarize(rolling_df, group_cols=["family", "target"]),
    }
    summary_json.write_text(json.dumps(summary_payload, indent=2), encoding="utf-8")
    return PeakRollingEvaluationResult(
        diagnostic_dir=diagnostic_dir,
        daily_peak_metrics_csv=daily_peak_metrics_csv,
        rolling_metrics_csv=rolling_metrics_csv,
        summary_json=summary_json,
    )


def _append_daily_peak_metrics(
    *,
    rows: list[dict[str, Any]],
    seed: int,
    truth_df: pd.DataFrame,
    target_index: dict[str, int],
    y_true: np.ndarray,
    y_pred: np.ndarray,
) -> None:
    required_targets = {
        "district_gas_boiler_generation_kwh_delta": "district_gas_boiler_generation_kwh_ref",
        "district_gas_chp_thermal_generation_kwh_delta": "district_gas_chp_thermal_generation_kwh_ref",
    }
    day_rows: list[dict[str, Any]] = []
    work = truth_df.loc[:, ["flex_override_name", "flex_case_label", "date", "hour_index", *required_targets.values()]].copy()
    for target, ref_column in required_targets.items():
        if target not in target_index:
            raise KeyError(f"[thermflex_hourly_dispatch] target missing for peak evaluation: {target}")
        work[f"{target}_true_delta"] = y_true[:, target_index[target]]
        work[f"{target}_pred_delta"] = y_pred[:, target_index[target]]
        work[f"{target}_true_flex"] = pd.to_numeric(work[ref_column], errors="raise") + work[f"{target}_true_delta"]
        work[f"{target}_pred_flex"] = pd.to_numeric(work[ref_column], errors="raise") + work[f"{target}_pred_delta"]
    for key, group in work.groupby(["flex_override_name", "flex_case_label", "date"], sort=True):
        payload: dict[str, Any] = {
            "flex_override_name": str(key[0]),
            "family": str(key[1]),
            "date": pd.Timestamp(key[2]),
        }
        for target, ref_column in required_targets.items():
            ref_peak = float(pd.to_numeric(group[ref_column], errors="raise").max())
            payload[f"{target}_peak_change_true"] = float(group[f"{target}_true_flex"].max() - ref_peak)
            payload[f"{target}_peak_change_pred"] = float(group[f"{target}_pred_flex"].max() - ref_peak)
        day_rows.append(payload)
    daily = pd.DataFrame(day_rows)
    for metric_prefix in required_targets:
        metric_name = f"{metric_prefix}_peak_change"
        rows.append(
            {
                "seed": int(seed),
                "family": "ALL",
                "metric": metric_name,
                "r2": _safe_r2(
                    daily[f"{metric_prefix}_peak_change_true"].to_numpy(),
                    daily[f"{metric_prefix}_peak_change_pred"].to_numpy(),
                ),
                "n_policy_days": int(len(daily)),
                "n_dates": int(daily["date"].nunique()),
            }
        )
        for family, family_df in daily.groupby("family", sort=True):
            rows.append(
                {
                    "seed": int(seed),
                    "family": str(family),
                    "metric": metric_name,
                    "r2": _safe_r2(
                        family_df[f"{metric_prefix}_peak_change_true"].to_numpy(),
                        family_df[f"{metric_prefix}_peak_change_pred"].to_numpy(),
                    ),
                    "n_policy_days": int(len(family_df)),
                    "n_dates": int(family_df["date"].nunique()),
                }
            )


def _append_rolling_sum_metrics(
    *,
    rows: list[dict[str, Any]],
    seed: int,
    truth_df: pd.DataFrame,
    target_names: list[str],
    y_true: np.ndarray,
    y_pred: np.ndarray,
    rolling_window_days: int,
) -> None:
    focus_targets = [
        "dispatch_heat_operating_cost_eur_delta",
        "co2_emissions_total_t_delta",
        "district_gas_boiler_generation_kwh_delta",
        "district_gas_chp_thermal_generation_kwh_delta",
    ]
    available_targets = [target for target in focus_targets if target in target_names]
    index_cols = ["flex_override_name", "flex_case_label", "date"]
    true_df = truth_df.loc[:, index_cols].reset_index(drop=True).copy()
    pred_df = true_df.copy()
    for idx, target in enumerate(target_names):
        if target in available_targets:
            true_df[target] = y_true[:, idx]
            pred_df[target] = y_pred[:, idx]
    daily_true = true_df.groupby(index_cols, as_index=False)[available_targets].sum()
    daily_pred = pred_df.groupby(index_cols, as_index=False)[available_targets].sum()
    merged = daily_true.merge(
        daily_pred,
        on=index_cols,
        suffixes=("_true", "_pred"),
        how="inner",
        validate="one_to_one",
    )
    window_rows: list[dict[str, Any]] = []
    for (override_name, family), group in merged.groupby(["flex_override_name", "flex_case_label"], sort=True):
        group = group.sort_values("date").reset_index(drop=True)
        for start_idx in range(0, len(group) - int(rolling_window_days) + 1):
            window = group.iloc[start_idx : start_idx + int(rolling_window_days)]
            expected = pd.date_range(window["date"].iloc[0], periods=int(rolling_window_days), freq="D")
            if list(window["date"]) != list(expected):
                continue
            payload: dict[str, Any] = {
                "flex_override_name": str(override_name),
                "family": str(family),
                "window_start": pd.Timestamp(window["date"].iloc[0]),
            }
            for target in available_targets:
                payload[f"{target}_true"] = float(window[f"{target}_true"].sum())
                payload[f"{target}_pred"] = float(window[f"{target}_pred"].sum())
            window_rows.append(payload)
    windows = pd.DataFrame(window_rows)
    for target in available_targets:
        if windows.empty:
            rows.append(
                {
                    "seed": int(seed),
                    "family": "ALL",
                    "target": target,
                    "r2": float("nan"),
                    "n_windows": 0,
                }
            )
            continue
        rows.append(
            {
                "seed": int(seed),
                "family": "ALL",
                "target": target,
                "r2": _safe_r2(windows[f"{target}_true"].to_numpy(), windows[f"{target}_pred"].to_numpy()),
                "n_windows": int(len(windows)),
            }
        )
        for family, family_df in windows.groupby("family", sort=True):
            rows.append(
                {
                    "seed": int(seed),
                    "family": str(family),
                    "target": target,
                    "r2": _safe_r2(
                        family_df[f"{target}_true"].to_numpy(),
                        family_df[f"{target}_pred"].to_numpy(),
                    ),
                    "n_windows": int(len(family_df)),
                }
            )


def _safe_r2(y_true: np.ndarray, y_pred: np.ndarray) -> float:
    values = np.asarray(y_true, dtype=float)
    if values.size < 2 or float(np.nanmax(values) - np.nanmin(values)) <= 1e-12:
        return float("nan")
    return float(r2_score(values, np.asarray(y_pred, dtype=float)))


def _summarize(metrics_df: pd.DataFrame, *, group_cols: list[str]) -> list[dict[str, Any]]:
    if metrics_df.empty:
        return []
    grouped = metrics_df.groupby(group_cols, sort=True)["r2"]
    summary = grouped.agg(["mean", "median", "min", "max"]).reset_index()
    summary = summary.rename(
        columns={"mean": "r2_mean", "median": "r2_median", "min": "r2_min", "max": "r2_max"}
    )
    count_cols = [column for column in ("n_policy_days", "n_windows") if column in metrics_df.columns]
    for column in count_cols:
        counts = metrics_df.groupby(group_cols, sort=True)[column].median().reset_index()
        counts = counts.rename(columns={column: f"{column}_median"})
        summary = summary.merge(counts, on=group_cols, how="left")
    return summary.to_dict(orient="records")


def _diagnostic_dir(*, model_root: Path, family_hash: str, output_name: str | None) -> Path:
    suffix = str(output_name) if output_name else str(family_hash)[:12]
    return Path(model_root).resolve() / f"thermflex_hourly_dispatch_peak_rolling_{suffix}"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--family-hash", required=True)
    parser.add_argument("--dataset-root", type=Path, default=_DEFAULT_DATASET_ROOT)
    parser.add_argument("--model-root", type=Path, default=_DEFAULT_MODEL_ROOT)
    parser.add_argument("--group-column", default="split_group_date")
    parser.add_argument("--test-size", type=float, default=0.3)
    parser.add_argument("--first-seed", type=int, default=0)
    parser.add_argument("--n-seeds", type=int, default=8)
    parser.add_argument("--rolling-window-days", type=int, default=7)
    parser.add_argument("--output-name", default=None)
    args = parser.parse_args()
    result = evaluate_peak_rolling_holdouts(
        family_hash=args.family_hash,
        dataset_root=args.dataset_root,
        model_root=args.model_root,
        group_column=args.group_column,
        test_size=args.test_size,
        first_seed=args.first_seed,
        n_seeds=args.n_seeds,
        rolling_window_days=args.rolling_window_days,
        output_name=args.output_name,
    )
    print(
        json.dumps(
            {
                "diagnostic_dir": str(result.diagnostic_dir),
                "daily_peak_metrics_csv": str(result.daily_peak_metrics_csv),
                "rolling_metrics_csv": str(result.rolling_metrics_csv),
                "summary_json": str(result.summary_json),
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
