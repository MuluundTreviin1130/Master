from __future__ import annotations

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
from sklearn.multioutput import MultiOutputRegressor

from Learning.datasets.load_dataset import load_dataset

_DEFAULT_DATASET_ROOT = Path(__file__).resolve().parents[2] / "Learning" / "datasets"
_DEFAULT_MODEL_ROOT = Path(__file__).resolve().parents[2] / "Learning" / "models"


@dataclass(frozen=True)
class HoldoutEvaluationResult:
    diagnostic_dir: Path
    hourly_metrics_csv: Path
    daily_metrics_csv: Path
    summary_json: Path


def evaluate_repeated_holdouts(
    *,
    family_hash: str,
    dataset_root: Path = _DEFAULT_DATASET_ROOT,
    model_root: Path = _DEFAULT_MODEL_ROOT,
    group_column: str = "split_group_date",
    test_size: float = 0.3,
    first_seed: int = 0,
    n_seeds: int = 10,
    estimator: str = "extra_trees",
    output_name: str | None = None,
) -> HoldoutEvaluationResult:
    dataset_bundle = load_dataset(Path(dataset_root), family_hash)
    if dataset_bundle is None:
        raise FileNotFoundError(
            "[thermflex_hourly_dispatch] curated dataset not found for family_hash=" + str(family_hash)
        )
    truth_csv_path = dataset_bundle.get("truth_csv_path")
    if truth_csv_path is None:
        raise FileNotFoundError("[thermflex_hourly_dispatch] curated dataset is missing `truth_dataset.csv`.")

    truth_df = pd.read_csv(truth_csv_path)
    truth_df["date"] = pd.to_datetime(truth_df["date"], errors="raise")
    if group_column not in truth_df.columns:
        raise KeyError(f"[thermflex_hourly_dispatch] group column not found in truth table: {group_column}")

    x = np.asarray(dataset_bundle["X"], dtype=float)
    y = np.asarray(dataset_bundle["Y"], dtype=float)
    target_names = list(dataset_bundle["meta"]["target_columns"])
    groups = truth_df[group_column].astype(str).to_numpy()
    if len(set(groups)) < 3:
        raise ValueError("[thermflex_hourly_dispatch] repeated holdouts require at least three split groups.")

    hourly_rows: list[dict[str, Any]] = []
    daily_rows: list[dict[str, Any]] = []
    for seed in range(int(first_seed), int(first_seed) + int(n_seeds)):
        splitter = GroupShuffleSplit(n_splits=1, test_size=float(test_size), random_state=seed)
        train_index, test_index = next(splitter.split(x, y, groups=groups))
        model = _build_estimator(estimator=estimator, random_state=seed)
        model.fit(x[train_index], y[train_index])
        pred = model.predict(x[test_index])
        for target_idx, target_name in enumerate(target_names):
            hourly_rows.append(
                {
                    "seed": int(seed),
                    "metric_scope": "hourly",
                    "target": target_name,
                    "r2": _safe_r2(y[test_index, target_idx], pred[:, target_idx]),
                    "n_test_rows": int(len(test_index)),
                    "n_test_groups": int(len(set(groups[test_index]))),
                }
            )

        daily_truth, daily_pred = _aggregate_daily_predictions(
            truth_df=truth_df.iloc[test_index].copy(),
            y_true=y[test_index],
            y_pred=pred,
            target_names=target_names,
        )
        for target_name in target_names:
            daily_rows.append(
                {
                    "seed": int(seed),
                    "metric_scope": "daily_sum",
                    "target": target_name,
                    "r2": _safe_r2(daily_truth[target_name].to_numpy(), daily_pred[target_name].to_numpy()),
                    "n_test_policy_days": int(len(daily_truth)),
                    "n_test_dates": int(daily_truth["date"].nunique()),
                }
            )

    hourly_df = pd.DataFrame(hourly_rows)
    daily_df = pd.DataFrame(daily_rows)
    diagnostic_dir = _diagnostic_dir(model_root=Path(model_root), family_hash=family_hash, output_name=output_name)
    diagnostic_dir.mkdir(parents=True, exist_ok=True)
    hourly_metrics_csv = diagnostic_dir / "hourly_holdout_metrics.csv"
    daily_metrics_csv = diagnostic_dir / "daily_sum_holdout_metrics.csv"
    summary_json = diagnostic_dir / "holdout_summary.json"
    hourly_df.to_csv(hourly_metrics_csv, index=False)
    daily_df.to_csv(daily_metrics_csv, index=False)
    summary_payload = {
        "family_hash": family_hash,
        "group_column": group_column,
        "test_size": float(test_size),
        "first_seed": int(first_seed),
        "n_seeds": int(n_seeds),
        "estimator": estimator,
        "n_rows": int(len(truth_df)),
        "n_groups": int(truth_df[group_column].astype(str).nunique()),
        "hourly_summary": _summarize(hourly_df),
        "daily_sum_summary": _summarize(daily_df),
    }
    summary_json.write_text(json.dumps(summary_payload, indent=2), encoding="utf-8")
    return HoldoutEvaluationResult(
        diagnostic_dir=diagnostic_dir,
        hourly_metrics_csv=hourly_metrics_csv,
        daily_metrics_csv=daily_metrics_csv,
        summary_json=summary_json,
    )


def _aggregate_daily_predictions(
    *,
    truth_df: pd.DataFrame,
    y_true: np.ndarray,
    y_pred: np.ndarray,
    target_names: list[str],
) -> tuple[pd.DataFrame, pd.DataFrame]:
    index_cols = ["flex_override_name", "flex_case_label", "date"]
    true_df = truth_df.loc[:, index_cols].reset_index(drop=True).copy()
    pred_df = true_df.copy()
    for target_idx, target_name in enumerate(target_names):
        true_df[target_name] = y_true[:, target_idx]
        pred_df[target_name] = y_pred[:, target_idx]
    daily_true = true_df.groupby(index_cols, as_index=False)[target_names].sum()
    daily_pred = pred_df.groupby(index_cols, as_index=False)[target_names].sum()
    return daily_true, daily_pred


def _safe_r2(y_true: np.ndarray, y_pred: np.ndarray) -> float:
    values = np.asarray(y_true, dtype=float)
    if values.size < 2 or float(np.nanmax(values) - np.nanmin(values)) <= 1e-12:
        return float("nan")
    return float(r2_score(values, np.asarray(y_pred, dtype=float)))


def _build_estimator(*, estimator: str, random_state: int):
    normalized = str(estimator).strip().lower()
    if normalized == "extra_trees":
        return ExtraTreesRegressor(
            n_estimators=500,
            min_samples_leaf=1,
            max_features=1.0,
            random_state=random_state,
            n_jobs=-1,
        )
    if normalized == "xgboost":
        from xgboost import XGBRegressor

        return MultiOutputRegressor(
            XGBRegressor(
                n_estimators=450,
                max_depth=4,
                learning_rate=0.04,
                subsample=0.9,
                colsample_bytree=0.9,
                reg_lambda=2.0,
                objective="reg:squarederror",
                random_state=random_state,
                n_jobs=-1,
            )
        )
    raise ValueError(
        "[thermflex_hourly_dispatch] unsupported estimator "
        f"'{estimator}'. Expected one of: extra_trees, xgboost."
    )


def _summarize(metrics_df: pd.DataFrame) -> list[dict[str, Any]]:
    if metrics_df.empty:
        return []
    grouped = metrics_df.groupby("target", sort=True)["r2"]
    summary = grouped.agg(["mean", "median", "min", "max"]).reset_index()
    summary = summary.rename(
        columns={
            "mean": "r2_mean",
            "median": "r2_median",
            "min": "r2_min",
            "max": "r2_max",
        }
    )
    return summary.to_dict(orient="records")


def _diagnostic_dir(*, model_root: Path, family_hash: str, output_name: str | None) -> Path:
    suffix = output_name if output_name else family_hash[:12]
    return model_root / f"thermflex_hourly_dispatch_holdouts_{suffix}"


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--family-hash", required=True)
    parser.add_argument("--dataset-root", type=Path, default=_DEFAULT_DATASET_ROOT)
    parser.add_argument("--model-root", type=Path, default=_DEFAULT_MODEL_ROOT)
    parser.add_argument("--group-column", default="split_group_date")
    parser.add_argument("--test-size", type=float, default=0.3)
    parser.add_argument("--first-seed", type=int, default=0)
    parser.add_argument("--n-seeds", type=int, default=10)
    parser.add_argument("--estimator", default="extra_trees", choices=["extra_trees", "xgboost"])
    parser.add_argument("--output-name", default=None)
    return parser


def main() -> None:
    args = _build_parser().parse_args()
    result = evaluate_repeated_holdouts(
        family_hash=args.family_hash,
        dataset_root=args.dataset_root,
        model_root=args.model_root,
        group_column=args.group_column,
        test_size=args.test_size,
        first_seed=args.first_seed,
        n_seeds=args.n_seeds,
        estimator=args.estimator,
        output_name=args.output_name,
    )
    print(
        json.dumps(
            {
                "diagnostic_dir": str(result.diagnostic_dir),
                "hourly_metrics_csv": str(result.hourly_metrics_csv),
                "daily_metrics_csv": str(result.daily_metrics_csv),
                "summary_json": str(result.summary_json),
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
