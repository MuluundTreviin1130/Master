from __future__ import annotations

"""Evaluate route-specific dispatch surrogates for weak ThermFlex families.

The global hourly-dispatch model is strong for many daily KPIs, but the
family-sliced diagnostics show weak pockets: short-duration cases, some tau
families and CHP/electric-value sensitive cases.  This script tests whether a
simple explicit router improves those pockets before we add more truth.

The router is deliberately diagnostic-only.  It writes every fallback count and
does not register a production model.
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
_DEFAULT_ROUTE_MODES = ("duration_bucket", "policy_family", "tau_bucket", "duration_policy_tau")


@dataclass(frozen=True)
class RouterEvaluationResult:
    diagnostic_dir: Path
    daily_metrics_csv: Path
    family_metrics_csv: Path
    summary_json: Path


def evaluate_family_router(
    *,
    family_hash: str,
    dataset_root: Path = _DEFAULT_DATASET_ROOT,
    model_root: Path = _DEFAULT_MODEL_ROOT,
    group_column: str = "split_group_date",
    test_size: float = 0.3,
    first_seed: int = 0,
    n_seeds: int = 8,
    route_modes: tuple[str, ...] = _DEFAULT_ROUTE_MODES,
    load_modes: tuple[str, ...] = ("oracle_load", "predicted_load_routed"),
    min_train_rows: int = 96,
    min_train_groups: int = 4,
    output_name: str | None = None,
) -> RouterEvaluationResult:
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
        raise KeyError("[thermflex_hourly_dispatch] missing load features: " + ", ".join(missing))

    x_all = np.asarray(dataset_bundle["X"], dtype=float)
    y_all = np.asarray(dataset_bundle["Y"], dtype=float)
    load_indices = [feature_names.index(name) for name in load_feature_names]
    base_indices = [idx for idx, name in enumerate(feature_names) if name not in set(load_feature_names)]
    x_base = x_all[:, base_indices]
    x_load = x_all[:, load_indices]
    groups = truth_df[group_column].astype(str).to_numpy()

    route_by_mode = {mode: _route_labels(truth_df, mode=mode) for mode in route_modes}
    daily_rows: list[dict[str, Any]] = []
    family_rows: list[dict[str, Any]] = []

    for seed in range(int(first_seed), int(first_seed) + int(n_seeds)):
        train_index, test_index = next(
            GroupShuffleSplit(n_splits=1, test_size=float(test_size), random_state=seed).split(
                x_all,
                y_all,
                groups=groups,
            )
        )
        for load_mode in load_modes:
            x_train_load_mode, x_test_load_mode = _resolve_load_mode_features(
                load_mode=str(load_mode),
                seed=seed,
                x_all=x_all,
                x_base=x_base,
                x_load=x_load,
                train_index=train_index,
                test_index=test_index,
                groups=groups,
                routes_by_mode=route_by_mode,
                min_train_rows=int(min_train_rows),
                min_train_groups=int(min_train_groups),
            )
            _evaluate_model_variant(
                daily_rows=daily_rows,
                family_rows=family_rows,
                seed=seed,
                variant="global",
                route_mode="none",
                load_mode=str(load_mode),
                x_train=x_train_load_mode,
                x_test=x_test_load_mode,
                y_train=y_all[train_index],
                y_test=y_all[test_index],
                truth_test=truth_df.iloc[test_index].copy(),
                target_names=target_names,
                fallback_count=0,
            )
            for route_mode, routes in route_by_mode.items():
                pred, fallback_count = _predict_with_routed_models(
                    seed=seed,
                    x_train=x_train_load_mode,
                    y_train=y_all[train_index],
                    x_test=x_test_load_mode,
                    train_routes=routes[train_index],
                    test_routes=routes[test_index],
                    train_groups=groups[train_index],
                    min_train_rows=int(min_train_rows),
                    min_train_groups=int(min_train_groups),
                )
                _append_prediction_metrics(
                    daily_rows=daily_rows,
                    family_rows=family_rows,
                    seed=seed,
                    variant="routed",
                    route_mode=str(route_mode),
                    load_mode=str(load_mode),
                    y_true=y_all[test_index],
                    y_pred=pred,
                    truth_test=truth_df.iloc[test_index].copy(),
                    target_names=target_names,
                    fallback_count=fallback_count,
                )

    diagnostic_dir = _diagnostic_dir(model_root=Path(model_root), family_hash=family_hash, output_name=output_name)
    diagnostic_dir.mkdir(parents=True, exist_ok=True)
    daily_metrics_csv = diagnostic_dir / "daily_metrics.csv"
    family_metrics_csv = diagnostic_dir / "family_daily_metrics.csv"
    summary_json = diagnostic_dir / "summary.json"
    daily_df = pd.DataFrame(daily_rows)
    family_df = pd.DataFrame(family_rows)
    daily_df.to_csv(daily_metrics_csv, index=False)
    family_df.to_csv(family_metrics_csv, index=False)
    summary_payload = {
        "family_hash": str(family_hash),
        "group_column": str(group_column),
        "test_size": float(test_size),
        "first_seed": int(first_seed),
        "n_seeds": int(n_seeds),
        "route_modes": list(route_modes),
        "load_modes": list(load_modes),
        "min_train_rows": int(min_train_rows),
        "min_train_groups": int(min_train_groups),
        "daily_summary": _summarize(daily_df, group_cols=["variant", "route_mode", "load_mode", "target"]),
        "family_summary": _summarize(
            family_df,
            group_cols=["variant", "route_mode", "load_mode", "family", "target"],
        ),
    }
    summary_json.write_text(json.dumps(summary_payload, indent=2), encoding="utf-8")
    return RouterEvaluationResult(
        diagnostic_dir=diagnostic_dir,
        daily_metrics_csv=daily_metrics_csv,
        family_metrics_csv=family_metrics_csv,
        summary_json=summary_json,
    )


def _resolve_load_mode_features(
    *,
    load_mode: str,
    seed: int,
    x_all: np.ndarray,
    x_base: np.ndarray,
    x_load: np.ndarray,
    train_index: np.ndarray,
    test_index: np.ndarray,
    groups: np.ndarray,
    routes_by_mode: dict[str, np.ndarray],
    min_train_rows: int,
    min_train_groups: int,
) -> tuple[np.ndarray, np.ndarray]:
    normalized = str(load_mode).strip().lower()
    if normalized == "oracle_load":
        return x_all[train_index], x_all[test_index]
    if normalized == "no_load":
        return x_base[train_index], x_base[test_index]
    if normalized == "predicted_load_global":
        load_model = _build_extra_trees(seed)
        load_model.fit(x_base[train_index], x_load[train_index])
        return (
            np.column_stack([x_base[train_index], load_model.predict(x_base[train_index])]),
            np.column_stack([x_base[test_index], load_model.predict(x_base[test_index])]),
        )
    if normalized == "predicted_load_routed":
        # The tau router is the most direct split for the load-shape problem.
        routes = routes_by_mode.get("duration_policy_tau")
        if routes is None:
            raise KeyError("[thermflex_hourly_dispatch] duration_policy_tau routes are required for routed load mode.")
        pred_train, _ = _predict_with_routed_models(
            seed=seed,
            x_train=x_base[train_index],
            y_train=x_load[train_index],
            x_test=x_base[train_index],
            train_routes=routes[train_index],
            test_routes=routes[train_index],
            train_groups=groups[train_index],
            min_train_rows=min_train_rows,
            min_train_groups=min_train_groups,
        )
        pred_test, _ = _predict_with_routed_models(
            seed=seed,
            x_train=x_base[train_index],
            y_train=x_load[train_index],
            x_test=x_base[test_index],
            train_routes=routes[train_index],
            test_routes=routes[test_index],
            train_groups=groups[train_index],
            min_train_rows=min_train_rows,
            min_train_groups=min_train_groups,
        )
        return np.column_stack([x_base[train_index], pred_train]), np.column_stack([x_base[test_index], pred_test])
    raise ValueError(
        "[thermflex_hourly_dispatch] unsupported load_mode "
        f"'{load_mode}'. Expected oracle_load, no_load, predicted_load_global, predicted_load_routed."
    )


def _evaluate_model_variant(
    *,
    daily_rows: list[dict[str, Any]],
    family_rows: list[dict[str, Any]],
    seed: int,
    variant: str,
    route_mode: str,
    load_mode: str,
    x_train: np.ndarray,
    x_test: np.ndarray,
    y_train: np.ndarray,
    y_test: np.ndarray,
    truth_test: pd.DataFrame,
    target_names: list[str],
    fallback_count: int,
) -> None:
    model = _build_extra_trees(seed)
    model.fit(x_train, y_train)
    pred = np.asarray(model.predict(x_test), dtype=float)
    _append_prediction_metrics(
        daily_rows=daily_rows,
        family_rows=family_rows,
        seed=seed,
        variant=variant,
        route_mode=route_mode,
        load_mode=load_mode,
        y_true=y_test,
        y_pred=pred,
        truth_test=truth_test,
        target_names=target_names,
        fallback_count=fallback_count,
    )


def _predict_with_routed_models(
    *,
    seed: int,
    x_train: np.ndarray,
    y_train: np.ndarray,
    x_test: np.ndarray,
    train_routes: np.ndarray,
    test_routes: np.ndarray,
    train_groups: np.ndarray,
    min_train_rows: int,
    min_train_groups: int,
) -> tuple[np.ndarray, int]:
    global_model = _build_extra_trees(seed)
    global_model.fit(x_train, y_train)
    pred = np.asarray(global_model.predict(x_test), dtype=float)
    fallback_count = 0
    for route in sorted(set(test_routes.astype(str))):
        test_mask = test_routes.astype(str) == str(route)
        train_mask = train_routes.astype(str) == str(route)
        enough_rows = int(np.sum(train_mask)) >= int(min_train_rows)
        enough_groups = len(set(train_groups[train_mask].astype(str))) >= int(min_train_groups)
        if not enough_rows or not enough_groups:
            fallback_count += int(np.sum(test_mask))
            continue
        route_model = _build_extra_trees(seed)
        route_model.fit(x_train[train_mask], y_train[train_mask])
        pred[test_mask] = np.asarray(route_model.predict(x_test[test_mask]), dtype=float)
    return pred, fallback_count


def _append_prediction_metrics(
    *,
    daily_rows: list[dict[str, Any]],
    family_rows: list[dict[str, Any]],
    seed: int,
    variant: str,
    route_mode: str,
    load_mode: str,
    y_true: np.ndarray,
    y_pred: np.ndarray,
    truth_test: pd.DataFrame,
    target_names: list[str],
    fallback_count: int,
) -> None:
    daily_true, daily_pred = _aggregate_daily(
        truth_df=truth_test,
        y_true=y_true,
        y_pred=y_pred,
        target_names=target_names,
    )
    for target in target_names:
        daily_rows.append(
            {
                "seed": int(seed),
                "variant": str(variant),
                "route_mode": str(route_mode),
                "load_mode": str(load_mode),
                "target": target,
                "r2": _safe_r2(daily_true[target].to_numpy(), daily_pred[target].to_numpy()),
                "fallback_test_rows": int(fallback_count),
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
                    "route_mode": str(route_mode),
                    "load_mode": str(load_mode),
                    "family": str(family),
                    "target": target,
                    "r2": _safe_r2(
                        family_df[f"{target}_true"].to_numpy(),
                        family_df[f"{target}_pred"].to_numpy(),
                    ),
                    "fallback_test_rows": int(fallback_count),
                    "n_test_policy_days": int(len(family_df)),
                    "n_test_dates": int(family_df["date"].nunique()),
                }
            )


def _route_labels(truth_df: pd.DataFrame, *, mode: str) -> np.ndarray:
    policy_duration = pd.to_numeric(truth_df["policy_duration_h"], errors="raise").to_numpy(dtype=float)
    policy_tau = pd.to_numeric(truth_df["policy_tau_h"], errors="raise").to_numpy(dtype=float)
    upper_only = pd.to_numeric(truth_df["policy_upper_only"], errors="raise").to_numpy(dtype=float) >= 0.5
    duration_bucket = np.where(policy_duration <= 1.5, "dur1", "dur_ge4")
    policy_bucket = np.where(upper_only, "upper_only", "lower_upper")
    tau_bucket = np.asarray([_tau_bucket(value) for value in policy_tau], dtype=object)
    normalized = str(mode).strip().lower()
    if normalized == "duration_bucket":
        return duration_bucket.astype(str)
    if normalized == "policy_family":
        return policy_bucket.astype(str)
    if normalized == "tau_bucket":
        return tau_bucket.astype(str)
    if normalized == "duration_policy_tau":
        return np.asarray(
            [f"{d}::{p}::{t}" for d, p, t in zip(duration_bucket, policy_bucket, tau_bucket)],
            dtype=object,
        )
    raise ValueError(f"[thermflex_hourly_dispatch] unsupported route mode: {mode}")


def _tau_bucket(value: float) -> str:
    tau = float(value)
    if tau <= 2.5:
        return "tau2"
    if tau <= 4.5:
        return "tau3_4"
    if tau <= 7.5:
        return "tau5_7"
    if tau <= 10.0:
        return "tau8"
    return "tau12plus"


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
    for idx, target in enumerate(target_names):
        true_df[target] = y_true[:, idx]
        pred_df[target] = y_pred[:, idx]
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
    return Path(model_root).resolve() / f"thermflex_hourly_dispatch_family_router_{suffix}"


def _parse_csv_list(value: str) -> tuple[str, ...]:
    return tuple(item.strip() for item in str(value).split(",") if item.strip())


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--family-hash", required=True)
    parser.add_argument("--dataset-root", type=Path, default=_DEFAULT_DATASET_ROOT)
    parser.add_argument("--model-root", type=Path, default=_DEFAULT_MODEL_ROOT)
    parser.add_argument("--group-column", default="split_group_date")
    parser.add_argument("--test-size", type=float, default=0.3)
    parser.add_argument("--first-seed", type=int, default=0)
    parser.add_argument("--n-seeds", type=int, default=8)
    parser.add_argument("--route-modes", default=",".join(_DEFAULT_ROUTE_MODES))
    parser.add_argument("--load-modes", default="oracle_load,predicted_load_routed")
    parser.add_argument("--min-train-rows", type=int, default=96)
    parser.add_argument("--min-train-groups", type=int, default=4)
    parser.add_argument("--output-name", default=None)
    args = parser.parse_args()
    result = evaluate_family_router(
        family_hash=args.family_hash,
        dataset_root=args.dataset_root,
        model_root=args.model_root,
        group_column=args.group_column,
        test_size=args.test_size,
        first_seed=args.first_seed,
        n_seeds=args.n_seeds,
        route_modes=_parse_csv_list(args.route_modes),
        load_modes=_parse_csv_list(args.load_modes),
        min_train_rows=args.min_train_rows,
        min_train_groups=args.min_train_groups,
        output_name=args.output_name,
    )
    print(
        json.dumps(
            {
                "diagnostic_dir": str(result.diagnostic_dir),
                "daily_metrics_csv": str(result.daily_metrics_csv),
                "family_metrics_csv": str(result.family_metrics_csv),
                "summary_json": str(result.summary_json),
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
