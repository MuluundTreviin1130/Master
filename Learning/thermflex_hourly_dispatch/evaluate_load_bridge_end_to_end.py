from __future__ import annotations

"""Evaluate dispatch quality when ThermFlex load features are predicted first.

This diagnostic answers one narrow question: how much of the current dispatch
surrogate quality depends on oracle ThermFlex load features.  The curated
hourly-dispatch dataset already contains the downstream load features
(`dh_bus_load_*` and `dh_total_demand_*`) because they are emitted by the MILP
truth run.  That is correct for testing the dispatch mapping, but it is too
optimistic for an end-to-end surrogate chain.

The evaluator therefore uses the same grouped holdout split for three variants:

- `oracle_load`: dispatch model sees the true ThermFlex load features.
- `predicted_load`: a first model predicts the load features from non-oracle
  policy/context/reference-dispatch features, then the dispatch model uses only
  those predicted load features.
- `no_load`: dispatch model sees no ThermFlex load features at all.

No production model is registered here.  The output is a persisted diagnostic
that tells us whether the next work should focus on load/mechanism learning,
dispatch routing, or more truth.
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
from Learning.thermflex_hourly_dispatch.schema import THERMFLEX_LOAD_FEATURE_COLUMNS


_DEFAULT_DATASET_ROOT = Path(__file__).resolve().parents[2] / "Learning" / "datasets"
_DEFAULT_MODEL_ROOT = Path(__file__).resolve().parents[2] / "Learning" / "models"


@dataclass(frozen=True)
class EndToEndLoadBridgeResult:
    diagnostic_dir: Path
    hourly_metrics_csv: Path
    daily_metrics_csv: Path
    family_daily_metrics_csv: Path
    load_metrics_csv: Path
    summary_json: Path


def evaluate_load_bridge_end_to_end(
    *,
    family_hash: str,
    dataset_root: Path = _DEFAULT_DATASET_ROOT,
    model_root: Path = _DEFAULT_MODEL_ROOT,
    group_column: str = "split_group_date",
    test_size: float = 0.3,
    first_seed: int = 0,
    n_seeds: int = 10,
    output_name: str | None = None,
) -> EndToEndLoadBridgeResult:
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

    feature_names = [str(value) for value in dataset_bundle["meta"]["encoded_feature_columns"]]
    target_names = [str(value) for value in dataset_bundle["meta"]["target_columns"]]
    load_feature_names = [name for name in THERMFLEX_LOAD_FEATURE_COLUMNS if name in feature_names]
    if len(load_feature_names) != len(THERMFLEX_LOAD_FEATURE_COLUMNS):
        missing = sorted(set(THERMFLEX_LOAD_FEATURE_COLUMNS).difference(load_feature_names))
        raise KeyError("[thermflex_hourly_dispatch] missing load bridge features: " + ", ".join(missing))

    x_all = np.asarray(dataset_bundle["X"], dtype=float)
    y_all = np.asarray(dataset_bundle["Y"], dtype=float)
    load_indices = [feature_names.index(name) for name in load_feature_names]
    base_indices = [idx for idx, name in enumerate(feature_names) if name not in set(load_feature_names)]
    x_base = x_all[:, base_indices]
    x_load = x_all[:, load_indices]
    groups = truth_df[group_column].astype(str).to_numpy()
    if len(set(groups)) < 3:
        raise ValueError("[thermflex_hourly_dispatch] load bridge evaluation requires at least three split groups.")

    hourly_rows: list[dict[str, Any]] = []
    daily_rows: list[dict[str, Any]] = []
    family_rows: list[dict[str, Any]] = []
    load_rows: list[dict[str, Any]] = []

    for seed in range(int(first_seed), int(first_seed) + int(n_seeds)):
        train_index, test_index = next(
            GroupShuffleSplit(n_splits=1, test_size=float(test_size), random_state=seed).split(
                x_all,
                y_all,
                groups=groups,
            )
        )

        load_model = _build_extra_trees(seed)
        load_model.fit(x_base[train_index], x_load[train_index])
        load_pred_train = np.asarray(load_model.predict(x_base[train_index]), dtype=float)
        load_pred_test = np.asarray(load_model.predict(x_base[test_index]), dtype=float)
        _append_load_metrics(
            rows=load_rows,
            seed=seed,
            truth_df=truth_df.iloc[test_index].copy(),
            load_feature_names=load_feature_names,
            y_true=x_load[test_index],
            y_pred=load_pred_test,
        )

        variant_matrices = {
            "oracle_load": (x_all[train_index], x_all[test_index]),
            "predicted_load": (
                np.column_stack([x_base[train_index], load_pred_train]),
                np.column_stack([x_base[test_index], load_pred_test]),
            ),
            "no_load": (x_base[train_index], x_base[test_index]),
        }
        for variant, (x_train, x_test) in variant_matrices.items():
            dispatch_model = _build_extra_trees(seed)
            dispatch_model.fit(x_train, y_all[train_index])
            pred = np.asarray(dispatch_model.predict(x_test), dtype=float)
            _append_dispatch_metrics(
                hourly_rows=hourly_rows,
                daily_rows=daily_rows,
                family_rows=family_rows,
                seed=seed,
                variant=variant,
                truth_df=truth_df.iloc[test_index].copy(),
                target_names=target_names,
                y_true=y_all[test_index],
                y_pred=pred,
            )

    diagnostic_dir = _diagnostic_dir(model_root=Path(model_root), family_hash=family_hash, output_name=output_name)
    diagnostic_dir.mkdir(parents=True, exist_ok=True)
    hourly_metrics_csv = diagnostic_dir / "hourly_metrics.csv"
    daily_metrics_csv = diagnostic_dir / "daily_sum_metrics.csv"
    family_daily_metrics_csv = diagnostic_dir / "family_daily_metrics.csv"
    load_metrics_csv = diagnostic_dir / "load_bridge_metrics.csv"
    summary_json = diagnostic_dir / "summary.json"

    hourly_df = pd.DataFrame(hourly_rows)
    daily_df = pd.DataFrame(daily_rows)
    family_df = pd.DataFrame(family_rows)
    load_df = pd.DataFrame(load_rows)
    hourly_df.to_csv(hourly_metrics_csv, index=False)
    daily_df.to_csv(daily_metrics_csv, index=False)
    family_df.to_csv(family_daily_metrics_csv, index=False)
    load_df.to_csv(load_metrics_csv, index=False)
    summary_payload = {
        "family_hash": str(family_hash),
        "group_column": str(group_column),
        "test_size": float(test_size),
        "first_seed": int(first_seed),
        "n_seeds": int(n_seeds),
        "feature_count_oracle_load": int(x_all.shape[1]),
        "feature_count_no_load": int(x_base.shape[1]),
        "load_feature_names": load_feature_names,
        "hourly_summary": _summarize(hourly_df, group_cols=["variant", "target"]),
        "daily_sum_summary": _summarize(daily_df, group_cols=["variant", "target"]),
        "load_bridge_summary": _summarize(load_df, group_cols=["target"]),
        "family_daily_summary": _summarize(family_df, group_cols=["variant", "family", "target"]),
    }
    summary_json.write_text(json.dumps(summary_payload, indent=2), encoding="utf-8")
    return EndToEndLoadBridgeResult(
        diagnostic_dir=diagnostic_dir,
        hourly_metrics_csv=hourly_metrics_csv,
        daily_metrics_csv=daily_metrics_csv,
        family_daily_metrics_csv=family_daily_metrics_csv,
        load_metrics_csv=load_metrics_csv,
        summary_json=summary_json,
    )


def _append_load_metrics(
    *,
    rows: list[dict[str, Any]],
    seed: int,
    truth_df: pd.DataFrame,
    load_feature_names: list[str],
    y_true: np.ndarray,
    y_pred: np.ndarray,
) -> None:
    for idx, name in enumerate(load_feature_names):
        rows.append(
            {
                "seed": int(seed),
                "scope": "hourly",
                "target": name,
                "r2": _safe_r2(y_true[:, idx], y_pred[:, idx]),
                "n_test_rows": int(y_true.shape[0]),
                "n_test_dates": int(truth_df["date"].nunique()),
            }
        )
    true_daily, pred_daily = _aggregate_daily(
        truth_df=truth_df,
        y_true=y_true,
        y_pred=y_pred,
        target_names=load_feature_names,
    )
    for name in load_feature_names:
        rows.append(
            {
                "seed": int(seed),
                "scope": "daily_sum",
                "target": name,
                "r2": _safe_r2(true_daily[name].to_numpy(), pred_daily[name].to_numpy()),
                "n_test_rows": int(len(true_daily)),
                "n_test_dates": int(true_daily["date"].nunique()),
            }
        )


def _append_dispatch_metrics(
    *,
    hourly_rows: list[dict[str, Any]],
    daily_rows: list[dict[str, Any]],
    family_rows: list[dict[str, Any]],
    seed: int,
    variant: str,
    truth_df: pd.DataFrame,
    target_names: list[str],
    y_true: np.ndarray,
    y_pred: np.ndarray,
) -> None:
    for idx, target in enumerate(target_names):
        hourly_rows.append(
            {
                "seed": int(seed),
                "variant": str(variant),
                "target": target,
                "r2": _safe_r2(y_true[:, idx], y_pred[:, idx]),
                "n_test_rows": int(y_true.shape[0]),
                "n_test_dates": int(truth_df["date"].nunique()),
            }
        )

    daily_true, daily_pred = _aggregate_daily(
        truth_df=truth_df,
        y_true=y_true,
        y_pred=y_pred,
        target_names=target_names,
    )
    for target in target_names:
        daily_rows.append(
            {
                "seed": int(seed),
                "variant": str(variant),
                "target": target,
                "r2": _safe_r2(daily_true[target].to_numpy(), daily_pred[target].to_numpy()),
                "n_test_policy_days": int(len(daily_true)),
                "n_test_dates": int(daily_true["date"].nunique()),
            }
        )
    merged_true = daily_true.rename(columns={target: f"{target}_true" for target in target_names})
    merged_pred = daily_pred.rename(columns={target: f"{target}_pred" for target in target_names})
    merged = merged_true.merge(
        merged_pred,
        on=["flex_override_name", "flex_case_label", "date"],
        how="inner",
        validate="one_to_one",
    )
    for family, family_df in merged.groupby("flex_case_label", sort=True):
        for target in target_names:
            family_rows.append(
                {
                    "seed": int(seed),
                    "variant": str(variant),
                    "family": str(family),
                    "target": target,
                    "r2": _safe_r2(
                        family_df[f"{target}_true"].to_numpy(),
                        family_df[f"{target}_pred"].to_numpy(),
                    ),
                    "n_test_policy_days": int(len(family_df)),
                    "n_test_dates": int(family_df["date"].nunique()),
                }
            )


def _aggregate_daily(
    *,
    truth_df: pd.DataFrame,
    y_true: np.ndarray,
    y_pred: np.ndarray,
    target_names: list[str],
) -> tuple[pd.DataFrame, pd.DataFrame]:
    index_cols = ["flex_override_name", "flex_case_label", "date"]
    true_df = truth_df.loc[:, index_cols].reset_index(drop=True).copy()
    pred_df = true_df.copy()
    for idx, name in enumerate(target_names):
        true_df[name] = y_true[:, idx]
        pred_df[name] = y_pred[:, idx]
    return (
        true_df.groupby(index_cols, as_index=False)[target_names].sum(),
        pred_df.groupby(index_cols, as_index=False)[target_names].sum(),
    )


def _build_extra_trees(seed: int) -> ExtraTreesRegressor:
    return ExtraTreesRegressor(
        n_estimators=500,
        min_samples_leaf=1,
        max_features=1.0,
        random_state=int(seed),
        n_jobs=-1,
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
    return summary.to_dict(orient="records")


def _diagnostic_dir(*, model_root: Path, family_hash: str, output_name: str | None) -> Path:
    suffix = str(output_name) if output_name else str(family_hash)[:12]
    return Path(model_root).resolve() / f"thermflex_hourly_dispatch_load_bridge_{suffix}"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--family-hash", required=True)
    parser.add_argument("--dataset-root", type=Path, default=_DEFAULT_DATASET_ROOT)
    parser.add_argument("--model-root", type=Path, default=_DEFAULT_MODEL_ROOT)
    parser.add_argument("--group-column", default="split_group_date")
    parser.add_argument("--test-size", type=float, default=0.3)
    parser.add_argument("--first-seed", type=int, default=0)
    parser.add_argument("--n-seeds", type=int, default=10)
    parser.add_argument("--output-name", default=None)
    args = parser.parse_args()
    result = evaluate_load_bridge_end_to_end(
        family_hash=args.family_hash,
        dataset_root=args.dataset_root,
        model_root=args.model_root,
        group_column=args.group_column,
        test_size=args.test_size,
        first_seed=args.first_seed,
        n_seeds=args.n_seeds,
        output_name=args.output_name,
    )
    print(
        json.dumps(
            {
                "diagnostic_dir": str(result.diagnostic_dir),
                "hourly_metrics_csv": str(result.hourly_metrics_csv),
                "daily_metrics_csv": str(result.daily_metrics_csv),
                "family_daily_metrics_csv": str(result.family_daily_metrics_csv),
                "load_metrics_csv": str(result.load_metrics_csv),
                "summary_json": str(result.summary_json),
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
