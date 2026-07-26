from __future__ import annotations

"""Repeated holdout diagnostics for the ThermFlex daily-results surrogate.

The normal daily trainer persists one candidate model for one grouped split.
This diagnostic runner answers a different question: which policy families,
time groupings, and KPI targets are actually learnable with the existing truth?

It is intentionally explicit:
- policy filters are named CLI arguments,
- split grouping and optional stratification are recorded,
- no model is registered as preferred from this diagnostic path.
"""

import argparse
import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from sklearn.ensemble import ExtraTreesRegressor
from sklearn.ensemble import RandomForestRegressor
from sklearn.neighbors import KNeighborsRegressor
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler
from xgboost import XGBClassifier
from xgboost import XGBRegressor

from Learning.datasets.load_dataset import load_dataset
from Learning.thermflex_daily_results.dataset_builder import _DEFAULT_DATASET_ROOT
from Learning.thermflex_daily_results.target_completeness import require_complete_requested_targets
from Learning.thermflex_daily_results.train import (
    _apply_target_transform,
    _invert_target_transform,
    _metric_block,
    _resolve_model_params,
    _resolve_target_profile,
    _resolve_target_transform,
)
from Learning.thermflex_daily_results.validate import build_grouped_holdout_split

_DEFAULT_MODEL_ROOT = Path(__file__).resolve().parents[2] / "Learning" / "models"


def evaluate_repeated_holdouts(
    *,
    family_hash: str,
    dataset_root: Path = _DEFAULT_DATASET_ROOT,
    model_root: Path = _DEFAULT_MODEL_ROOT,
    target_profile: str = "table_09_paper",
    group_column: str = "split_group_date",
    test_size: float = 0.25,
    split_strategy: str = "group_shuffle",
    stratify_column: str | None = None,
    first_seed: int = 0,
    n_seeds: int = 20,
    policy_case_labels: tuple[str, ...] = (),
    min_date: str | None = None,
    max_date: str | None = None,
    estimator: str = "xgb",
    output_name: str | None = None,
) -> dict[str, Any]:
    dataset_bundle = load_dataset(Path(dataset_root), family_hash)
    if dataset_bundle is None:
        raise FileNotFoundError(
            "[thermflex_daily_results] curated dataset not found under Learning/datasets for family_hash="
            f"{family_hash}"
        )
    truth_csv_path = dataset_bundle.get("truth_csv_path")
    if truth_csv_path is None:
        raise FileNotFoundError("[thermflex_daily_results] curated dataset is missing `truth_dataset.csv`.")

    truth_df = pd.read_csv(truth_csv_path)
    truth_df["date"] = pd.to_datetime(truth_df["date"], errors="raise")
    truth_df["split_group_date"] = truth_df["date"].dt.strftime("%Y-%m-%d")
    truth_df["season_bucket"] = truth_df["month"].map(_season_bucket).astype(str)
    truth_df["policy_family_bucket"] = truth_df["policy_case_label_canonical"].astype(str)
    mask = _build_filter_mask(
        truth_df=truth_df,
        policy_case_labels=policy_case_labels,
        min_date=min_date,
        max_date=max_date,
    )
    filtered_truth = truth_df.loc[mask].reset_index(drop=True)
    if filtered_truth.empty:
        raise ValueError("[thermflex_daily_results] selected repeated-holdout subset is empty.")

    raw_x = np.asarray(dataset_bundle["X"], dtype=float)
    selected_positions = np.flatnonzero(mask.to_numpy())
    x = raw_x[selected_positions, :]

    all_target_names = list(dataset_bundle["meta"]["target_columns"])
    requested_target_names = _resolve_target_profile(target_profile)
    missing_requested = [target for target in requested_target_names if target not in all_target_names]
    if missing_requested:
        raise ValueError(
            "[thermflex_daily_results] requested target profile contains unknown targets: "
            + ", ".join(missing_requested)
        )
    # Same contract as train_daily_results_model: a named profile must not
    # silently shrink when curated truth still has NaNs in optional columns.
    require_complete_requested_targets(
        truth_df=filtered_truth,
        requested_target_names=requested_target_names,
        target_profile=target_profile,
    )
    target_indices = [all_target_names.index(target) for target in requested_target_names]
    y = np.asarray(dataset_bundle["Y"], dtype=float)[selected_positions, :][:, target_indices]

    rows: list[dict[str, Any]] = []
    split_rows: list[dict[str, Any]] = []
    for seed in range(int(first_seed), int(first_seed) + int(n_seeds)):
        split = build_grouped_holdout_split(
            truth_df=filtered_truth,
            group_column=group_column,
            test_size=test_size,
            random_state=seed,
            split_strategy=split_strategy,
            stratify_column=stratify_column,
        )
        x_train = x[split.train_index, :]
        x_test = x[split.test_index, :]
        y_train = y[split.train_index, :]
        y_test = y[split.test_index, :]
        y_pred = _fit_predict_targets(
            x_train=x_train,
            x_test=x_test,
            y_train=y_train,
            target_names=requested_target_names,
            random_state=seed,
            estimator=estimator,
        )
        metrics = _metric_block(y_true=y_test, y_pred=y_pred, target_names=requested_target_names)
        for row in metrics.to_dict(orient="records"):
            row.update(
                {
                    "seed": seed,
                    "n_train_rows": int(len(split.train_index)),
                    "n_test_rows": int(len(split.test_index)),
                    "n_train_groups": int(len(split.train_groups)),
                    "n_test_groups": int(len(split.test_groups)),
                }
            )
            rows.append(row)
        split_rows.append(
            {
                "seed": seed,
                "train_groups": split.train_groups,
                "test_groups": split.test_groups,
            }
        )

    metrics_df = pd.DataFrame(rows)
    summary_df = _summarize_metrics(metrics_df)
    diagnostic_dir = _diagnostic_dir(
        model_root=Path(model_root),
        family_hash=family_hash,
        target_profile=target_profile,
        output_name=output_name,
    )
    diagnostic_dir.mkdir(parents=True, exist_ok=True)
    metrics_csv = diagnostic_dir / "repeated_holdout_metrics.csv"
    summary_csv = diagnostic_dir / "repeated_holdout_summary.csv"
    summary_json = diagnostic_dir / "repeated_holdout_summary.json"
    split_json = diagnostic_dir / "repeated_holdout_splits.json"
    config_json = diagnostic_dir / "repeated_holdout_config.json"

    metrics_df.to_csv(metrics_csv, index=False)
    summary_df.to_csv(summary_csv, index=False)
    payload = {
        "family_hash": family_hash,
        "target_profile": target_profile,
        "group_column": group_column,
        "test_size": float(test_size),
        "split_strategy": split_strategy,
        "stratify_column": stratify_column,
        "first_seed": int(first_seed),
        "n_seeds": int(n_seeds),
        "policy_case_labels": list(policy_case_labels),
        "min_date": min_date,
        "max_date": max_date,
        "estimator": estimator,
        "n_rows": int(len(filtered_truth)),
        "n_groups": int(filtered_truth[group_column].astype(str).nunique()),
        "summary": summary_df.to_dict(orient="records"),
    }
    summary_json.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    split_json.write_text(json.dumps(split_rows, indent=2), encoding="utf-8")
    config_json.write_text(json.dumps({k: v for k, v in payload.items() if k != "summary"}, indent=2), encoding="utf-8")
    return {
        "diagnostic_dir": diagnostic_dir,
        "metrics_csv": metrics_csv,
        "summary_csv": summary_csv,
        "summary_json": summary_json,
        "summary": payload,
    }


def _fit_predict_targets(
    *,
    x_train: np.ndarray,
    x_test: np.ndarray,
    y_train: np.ndarray,
    target_names: list[str],
    random_state: int,
    estimator: str,
) -> np.ndarray:
    predictions: list[np.ndarray] = []
    for target_idx, target_name in enumerate(target_names):
        if str(estimator).strip().lower() == "hurdle_xgb":
            predictions.append(
                _fit_predict_hurdle_xgb(
                    x_train=x_train,
                    x_test=x_test,
                    y_train=y_train[:, target_idx],
                    target_name=target_name,
                    random_state=random_state,
                )
            )
            continue
        transform = _resolve_target_transform(target_name)
        model = _build_estimator(
            estimator=estimator,
            target_name=target_name,
            random_state=random_state,
        )
        model.fit(x_train, _apply_target_transform(y_train[:, target_idx], transform))
        predictions.append(_invert_target_transform(model.predict(x_test), transform))
    return np.column_stack(predictions)


def _fit_predict_hurdle_xgb(
    *,
    x_train: np.ndarray,
    x_test: np.ndarray,
    y_train: np.ndarray,
    target_name: str,
    random_state: int,
) -> np.ndarray:
    zero_eps = _target_zero_eps(target_name)
    active = np.abs(np.asarray(y_train, dtype=float)) > zero_eps
    active_count = int(np.sum(active))
    inactive_count = int(len(active) - active_count)
    if active_count == 0:
        return np.zeros(x_test.shape[0], dtype=float)
    if inactive_count == 0 or target_name not in _HURDLE_TARGETS:
        transform = _hurdle_regression_transform(target_name)
        regressor = XGBRegressor(**_resolve_model_params(target_name, random_state=random_state))
        regressor.fit(x_train, _apply_target_transform(y_train, transform))
        return _invert_target_transform(regressor.predict(x_test), transform)

    classifier = XGBClassifier(
        n_estimators=350,
        max_depth=3,
        learning_rate=0.04,
        subsample=0.9,
        colsample_bytree=0.85,
        reg_lambda=1.0,
        objective="binary:logistic",
        eval_metric="logloss",
        random_state=random_state,
        n_jobs=1,
    )
    classifier.fit(x_train, active.astype(int))
    transform = _hurdle_regression_transform(target_name)
    regressor = XGBRegressor(**_resolve_model_params(target_name, random_state=random_state))
    regressor.fit(x_train[active, :], _apply_target_transform(y_train[active], transform))
    active_probability = classifier.predict_proba(x_test)[:, 1]
    raw_prediction = _invert_target_transform(regressor.predict(x_test), transform)
    prediction = np.where(active_probability >= 0.5, raw_prediction, 0.0)
    return prediction.astype(float)


_HURDLE_TARGETS = {
    "district_gas_boiler_peak_kw_delta",
    "dh_total_peak_change_kw",
    "thermflex_peak_change_kw",
    "thermflex_rebound_kwh",
}


def _target_zero_eps(target_name: str) -> float:
    if target_name.endswith("_kw_delta") or target_name.endswith("_change_kw"):
        return 1e-6
    if target_name.endswith("_kwh"):
        return 1e-6
    return 1e-9


def _hurdle_regression_transform(target_name: str) -> str:
    if target_name in _HURDLE_TARGETS:
        return "signed_log1p"
    return _resolve_target_transform(target_name)


def _build_estimator(*, estimator: str, target_name: str, random_state: int) -> Any:
    name = str(estimator).strip().lower()
    if name == "xgb_cost_extra_trees_smooth_rest":
        # The daily training contract is target-wise, so this diagnostic checks
        # the simplest explicit hybrid suggested by the current holdouts:
        # XGB keeps the cost target, while smoother ExtraTrees handles the
        # physical mechanism and boiler targets that profit from averaging.
        if target_name in {
            "dispatch_operating_cost_eur_delta",
            "dispatch_operating_cost_pct_change",
            "dispatch_heat_operating_cost_eur_delta",
        }:
            return XGBRegressor(**_resolve_model_params(target_name, random_state=random_state))
        return ExtraTreesRegressor(
            n_estimators=900,
            max_features=0.75,
            min_samples_leaf=2,
            bootstrap=False,
            random_state=random_state,
            n_jobs=1,
        )
    if name == "xgb":
        return XGBRegressor(**_resolve_model_params(target_name, random_state=random_state))
    if name == "extra_trees":
        return ExtraTreesRegressor(
            n_estimators=700,
            max_features=0.85,
            min_samples_leaf=1,
            bootstrap=False,
            random_state=random_state,
            n_jobs=1,
        )
    if name == "extra_trees_smooth":
        return ExtraTreesRegressor(
            n_estimators=900,
            max_features=0.75,
            min_samples_leaf=2,
            bootstrap=False,
            random_state=random_state,
            n_jobs=1,
        )
    if name == "random_forest":
        return RandomForestRegressor(
            n_estimators=700,
            max_features=0.85,
            min_samples_leaf=1,
            bootstrap=True,
            random_state=random_state,
            n_jobs=1,
        )
    if name == "knn_distance":
        return make_pipeline(
            StandardScaler(),
            KNeighborsRegressor(n_neighbors=5, weights="distance"),
        )
    if name == "hurdle_xgb":
        return XGBRegressor(**_resolve_model_params(target_name, random_state=random_state))
    raise ValueError(f"[thermflex_daily_results] unsupported estimator: {estimator}")


def _build_filter_mask(
    *,
    truth_df: pd.DataFrame,
    policy_case_labels: tuple[str, ...],
    min_date: str | None,
    max_date: str | None,
) -> pd.Series:
    mask = pd.Series(True, index=truth_df.index)
    if policy_case_labels:
        labels = {str(label) for label in policy_case_labels}
        mask &= truth_df["policy_case_label_canonical"].astype(str).isin(labels)
    if min_date is not None:
        mask &= truth_df["date"] >= pd.Timestamp(min_date)
    if max_date is not None:
        mask &= truth_df["date"] <= pd.Timestamp(max_date)
    return mask


def _season_bucket(month: int) -> str:
    month_int = int(month)
    if month_int in {12, 1, 2}:
        return "winter"
    if month_int in {3, 4, 10, 11}:
        return "shoulder"
    return "other"


def _summarize_metrics(metrics_df: pd.DataFrame) -> pd.DataFrame:
    grouped = metrics_df.groupby("target", sort=True)["r2"]
    return grouped.agg(
        n_seeds="count",
        r2_mean="mean",
        r2_median="median",
        r2_min="min",
        r2_max="max",
    ).reset_index()


def _diagnostic_dir(
    *,
    model_root: Path,
    family_hash: str,
    target_profile: str,
    output_name: str | None,
) -> Path:
    if output_name:
        suffix = output_name
    else:
        suffix = f"{target_profile}_{family_hash[:12]}"
    return Path(model_root).resolve() / f"thermflex_daily_results_repeated_{suffix}"


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--family-hash", required=True)
    parser.add_argument("--dataset-root", type=Path, default=_DEFAULT_DATASET_ROOT)
    parser.add_argument("--model-root", type=Path, default=_DEFAULT_MODEL_ROOT)
    parser.add_argument("--target-profile", default="table_09_paper")
    parser.add_argument("--group-column", default="split_group_date")
    parser.add_argument("--test-size", type=float, default=0.25)
    parser.add_argument("--split-strategy", default="group_shuffle")
    parser.add_argument("--stratify-column", default=None)
    parser.add_argument("--first-seed", type=int, default=0)
    parser.add_argument("--n-seeds", type=int, default=20)
    parser.add_argument("--policy-case-label", dest="policy_case_labels", action="append", default=[])
    parser.add_argument("--min-date", default=None)
    parser.add_argument("--max-date", default=None)
    parser.add_argument(
        "--estimator",
        default="xgb",
        choices=(
            "xgb",
            "extra_trees",
            "extra_trees_smooth",
            "random_forest",
            "knn_distance",
            "hurdle_xgb",
            "xgb_cost_extra_trees_smooth_rest",
        ),
    )
    parser.add_argument("--output-name", default=None)
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    result = evaluate_repeated_holdouts(
        family_hash=args.family_hash,
        dataset_root=args.dataset_root,
        model_root=args.model_root,
        target_profile=args.target_profile,
        group_column=args.group_column,
        test_size=args.test_size,
        split_strategy=args.split_strategy,
        stratify_column=args.stratify_column,
        first_seed=args.first_seed,
        n_seeds=args.n_seeds,
        policy_case_labels=tuple(args.policy_case_labels),
        min_date=args.min_date,
        max_date=args.max_date,
        estimator=args.estimator,
        output_name=args.output_name,
    )
    print(json.dumps({key: str(value) for key, value in result.items() if key != "summary"}, indent=2))
    print(json.dumps(result["summary"], indent=2))


if __name__ == "__main__":
    main()
