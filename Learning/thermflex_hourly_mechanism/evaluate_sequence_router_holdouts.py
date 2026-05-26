from __future__ import annotations

"""Evaluate routed hourly heat-delta learners for upper-only rebound failures.

Why this exists:
- the normal hourly mechanism XGB learns all cohorts in one target-wise model,
- upper-only holdouts still fail mostly through sequence/timing errors in
  `q_delta`, which then break shifted/rebound/peak KPIs,
- lower-relax diagnostics showed that the KPI reconstruction itself is not the
  main issue,
- this evaluator keeps the routing experiment reproducible before any routed
  model is promoted into the normal training contract.

The script intentionally learns derived positive/negative heat-delta components
instead of MILP slack variables. The slack variables are not guaranteed to equal
the positive/negative parts of the heat deviation, while the KPI reconstruction
depends on the actual hourly `q_heat - q_ref` sequence.
"""

import argparse
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

import numpy as np
import pandas as pd
from sklearn.ensemble import ExtraTreesRegressor, HistGradientBoostingRegressor
from sklearn.metrics import mean_absolute_error, r2_score

from dispatch.metrics import compute_thermflex_series_metrics
from Learning.datasets.load_dataset import load_dataset
from Learning.thermflex_hourly_mechanism.dataset_builder import _DEFAULT_DATASET_ROOT
from Learning.thermflex_hourly_mechanism.train import (
    _DEFAULT_MODEL_ROOT,
    _resolve_feature_preset,
)
from Learning.thermflex_hourly_mechanism.validate import build_grouped_holdout_split


@dataclass(frozen=True)
class RouterSpec:
    """Typed route configuration for one explicit sequence experiment."""

    mode: str
    min_rows: int


def evaluate_sequence_router_holdouts(
    *,
    family_hash: str,
    dataset_root: Path = _DEFAULT_DATASET_ROOT,
    model_root: Path = _DEFAULT_MODEL_ROOT,
    group_column: str = "split_group_run",
    split_strategy: str = "group_shuffle",
    stratify_column: str | None = None,
    test_size: float = 0.25,
    random_state: int = 42,
    feature_preset: str = "no_case_label",
    backend: str = "extra_trees",
    modes: Iterable[str] = ("global", "age_hour"),
    min_rows: Iterable[int] = (250,),
    output_name: str = "sequence_router_holdout_summary.csv",
) -> dict[str, Any]:
    """Run routed positive/negative q-delta holdout diagnostics.

    The output is a diagnostic artifact, not a preferred production model. A
    route-specific learner is used only where its training row count satisfies
    the explicit `min_rows` threshold; otherwise the global learner is used and
    the row-level prediction records that fallback through aggregate counts.
    """

    dataset_bundle = load_dataset(Path(dataset_root).resolve(), family_hash)
    if dataset_bundle is None:
        raise FileNotFoundError(
            "[thermflex_hourly_mechanism] sequence-router dataset not found for family_hash="
            f"{family_hash}"
        )
    truth_csv_path = dataset_bundle.get("truth_csv_path")
    if truth_csv_path is None:
        raise FileNotFoundError("[thermflex_hourly_mechanism] sequence-router dataset has no truth csv path.")
    truth = pd.read_csv(truth_csv_path)
    truth["timestamp"] = pd.to_datetime(truth["timestamp"], errors="raise")

    required_columns = {
        group_column,
        "timestamp",
        "run_dir",
        "cohort_q_heat_kwh",
        "cohort_q_heat_ref_kwh",
    }
    missing = sorted(required_columns.difference(truth.columns))
    if missing:
        raise ValueError(
            "[thermflex_hourly_mechanism] sequence-router truth is missing required columns: "
            f"{missing}"
        )

    encoded_features = _encoded_features_for_preset(dataset_bundle, feature_preset)
    q_delta_true = _true_q_delta_kwh(truth)
    y_pos = np.maximum(q_delta_true, 0.0)
    y_neg = np.maximum(-q_delta_true, 0.0)
    split = build_grouped_holdout_split(
        truth_df=truth,
        group_column=group_column,
        test_size=test_size,
        random_state=random_state,
        split_strategy=split_strategy,
        stratify_column=stratify_column,
    )

    diagnostics_dir = Path(model_root).resolve() / "thermflex_hourly_mechanism_sequence_router_diagnostics"
    diagnostics_dir.mkdir(parents=True, exist_ok=True)

    rows: list[dict[str, Any]] = []
    for mode in modes:
        for threshold in min_rows:
            spec = RouterSpec(mode=str(mode), min_rows=int(threshold))
            prediction = _fit_predict_routed_components(
                x=encoded_features,
                truth=truth,
                y_pos=y_pos,
                y_neg=y_neg,
                train_index=split.train_index,
                test_index=split.test_index,
                backend=backend,
                spec=spec,
                random_state=random_state,
            )
            rows.append(
                _metric_row(
                    truth=truth,
                    test_index=split.test_index,
                    q_delta_true=q_delta_true,
                    prediction=prediction,
                    mode=spec.mode,
                    min_rows=spec.min_rows,
                    backend=backend,
                    feature_preset=feature_preset,
                    split_strategy=split.split_strategy,
                    stratify_column=split.stratify_column,
                )
            )

    summary_df = pd.DataFrame(rows).sort_values(
        ["rebound_r2", "shifted_r2", "peak_r2"],
        ascending=[False, False, False],
    )
    output_csv_path = diagnostics_dir / output_name
    output_json_path = diagnostics_dir / f"{Path(output_name).stem}.json"
    summary_df.to_csv(output_csv_path, index=False)
    payload = {
        "family_hash": str(family_hash),
        "truth_csv_path": str(Path(truth_csv_path).resolve()),
        "output_csv_path": str(output_csv_path),
        "best_by_rebound": summary_df.head(5).to_dict(orient="records"),
    }
    output_json_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return {
        "output_csv_path": output_csv_path,
        "output_json_path": output_json_path,
        "summary": summary_df,
    }


def _encoded_features_for_preset(dataset_bundle: dict[str, Any], feature_preset: str) -> np.ndarray:
    """Return the same encoded-feature subset used by the normal trainer."""

    all_feature_names = [str(value) for value in dataset_bundle["meta"]["encoded_feature_columns"]]
    selected_names = _resolve_feature_preset(all_feature_names, feature_preset)
    selected_indices = [all_feature_names.index(name) for name in selected_names]
    return np.asarray(dataset_bundle["X"], dtype=float)[:, selected_indices]


def _true_q_delta_kwh(truth: pd.DataFrame) -> np.ndarray:
    """Derive the exact hourly heat deviation used by KPI reconstruction."""

    return (
        pd.to_numeric(truth["cohort_q_heat_kwh"], errors="raise").to_numpy(dtype=float)
        - pd.to_numeric(truth["cohort_q_heat_ref_kwh"], errors="raise").to_numpy(dtype=float)
    )


def _fit_predict_routed_components(
    *,
    x: np.ndarray,
    truth: pd.DataFrame,
    y_pos: np.ndarray,
    y_neg: np.ndarray,
    train_index: np.ndarray,
    test_index: np.ndarray,
    backend: str,
    spec: RouterSpec,
    random_state: int,
) -> dict[str, Any]:
    """Fit global plus eligible route models and predict holdout q-delta."""

    global_pos = _new_regressor(backend=backend, random_state=random_state)
    global_neg = _new_regressor(backend=backend, random_state=random_state + 1)
    global_pos.fit(x[train_index, :], y_pos[train_index])
    global_neg.fit(x[train_index, :], y_neg[train_index])

    route_keys = _route_keys(truth, spec.mode)
    train_keys = route_keys.iloc[train_index].reset_index(drop=True)
    test_keys = route_keys.iloc[test_index].reset_index(drop=True)
    x_train = x[train_index, :]
    x_test = x[test_index, :]
    pred_pos = global_pos.predict(x_test)
    pred_neg = global_neg.predict(x_test)

    used_routes = 0
    routed_rows = 0
    if spec.mode != "global":
        train_frame = pd.DataFrame({"route_key": train_keys})
        for route_key, route_train_pos in train_frame.groupby("route_key", sort=True).groups.items():
            train_pos = np.asarray(list(route_train_pos), dtype=int)
            if len(train_pos) < spec.min_rows:
                continue
            route_mask = test_keys.to_numpy(dtype=object) == route_key
            if not np.any(route_mask):
                continue
            route_pos = _new_regressor(backend=backend, random_state=random_state)
            route_neg = _new_regressor(backend=backend, random_state=random_state + 1)
            route_pos.fit(x_train[train_pos, :], y_pos[train_index][train_pos])
            route_neg.fit(x_train[train_pos, :], y_neg[train_index][train_pos])
            pred_pos[route_mask] = route_pos.predict(x_test[route_mask, :])
            pred_neg[route_mask] = route_neg.predict(x_test[route_mask, :])
            used_routes += 1
            routed_rows += int(np.sum(route_mask))

    pred_pos = np.maximum(np.asarray(pred_pos, dtype=float), 0.0)
    pred_neg = np.maximum(np.asarray(pred_neg, dtype=float), 0.0)
    return {
        "q_delta_pred": pred_pos - pred_neg,
        "pos_pred": pred_pos,
        "neg_pred": pred_neg,
        "used_routes": int(used_routes),
        "routed_rows": int(routed_rows),
        "holdout_rows": int(len(test_index)),
    }


def _route_keys(truth: pd.DataFrame, mode: str) -> pd.Series:
    """Build explicit, human-readable route keys for one diagnostic mode."""

    normalized = str(mode).strip().lower()
    age = truth["cohort_key"].astype(str).map(_age_bucket)
    hour_block = truth["timestamp"].dt.hour.map(_hour_block)
    season = truth["timestamp"].dt.month.map(_season_bucket)
    sector = truth["cohort_key"].astype(str).map(_sector_bucket)
    cohort = truth["cohort_key"].astype(str)

    if normalized == "global":
        return pd.Series(["global"] * len(truth), index=truth.index)
    if normalized == "age":
        return age
    if normalized == "age_hour":
        return age + "|" + hour_block
    if normalized == "age_season_hour":
        return age + "|" + season + "|" + hour_block
    if normalized == "sector_age_hour":
        return sector + "|" + age + "|" + hour_block
    if normalized == "cohort_hour":
        return cohort + "|" + hour_block
    raise ValueError(f"[thermflex_hourly_mechanism] unsupported route mode: {mode}")


def _age_bucket(cohort_key: str) -> str:
    """Collapse construction ages into the robust old/modern family split."""

    value = str(cohort_key)
    if "pre1975" in value or "1975_1990" in value:
        return "old"
    return "modern"


def _hour_block(hour: int) -> str:
    """Keep only broad intraday blocks to avoid small routed samples."""

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


def _season_bucket(month: int) -> str:
    """Separate winter from shoulder months for diagnostic routing only."""

    return "winter" if int(month) in {1, 2, 12} else "shoulder"


def _sector_bucket(cohort_key: str) -> str:
    """Extract the sector prefix from the curated cohort key."""

    value = str(cohort_key)
    if value.startswith("non_residential"):
        return "non_residential"
    if value.startswith("residential"):
        return "residential"
    return "other"


def _new_regressor(*, backend: str, random_state: int) -> Any:
    """Construct one explicit regressor backend for the router diagnostic."""

    normalized = str(backend).strip().lower()
    if normalized == "extra_trees":
        return ExtraTreesRegressor(
            n_estimators=360,
            min_samples_leaf=2,
            random_state=int(random_state),
            n_jobs=-1,
        )
    if normalized == "hist_gradient":
        return HistGradientBoostingRegressor(
            learning_rate=0.045,
            max_iter=450,
            l2_regularization=0.05,
            random_state=int(random_state),
        )
    raise ValueError(f"[thermflex_hourly_mechanism] unsupported router backend: {backend}")


def _metric_row(
    *,
    truth: pd.DataFrame,
    test_index: np.ndarray,
    q_delta_true: np.ndarray,
    prediction: dict[str, Any],
    mode: str,
    min_rows: int,
    backend: str,
    feature_preset: str,
    split_strategy: str,
    stratify_column: str | None,
) -> dict[str, Any]:
    """Aggregate hourly q-delta predictions back into daily KPI metrics."""

    holdout = truth.iloc[test_index].copy()
    holdout["q_delta_true"] = q_delta_true[test_index]
    holdout["q_delta_pred"] = np.asarray(prediction["q_delta_pred"], dtype=float)
    holdout["q_heat_pred_kwh"] = (
        pd.to_numeric(holdout["cohort_q_heat_ref_kwh"], errors="raise").to_numpy(dtype=float)
        + holdout["q_delta_pred"].to_numpy(dtype=float)
    )

    daily_rows: list[dict[str, float]] = []
    for run_dir, run_df in holdout.groupby("run_dir", sort=True):
        for day_ts, day_df in run_df.groupby(holdout.loc[run_df.index, "timestamp"].dt.floor("D")):
            q_pred = day_df.groupby("timestamp")["q_heat_pred_kwh"].sum().sort_index()
            q_ref = day_df.groupby("timestamp")["cohort_q_heat_ref_kwh"].sum().sort_index()
            q_true = day_df.groupby("timestamp")["cohort_q_heat_kwh"].sum().sort_index()
            predicted_metrics = compute_thermflex_series_metrics(q_pred, q_ref)
            true_metrics = compute_thermflex_series_metrics(q_true, q_ref)
            daily_rows.append(
                {
                    "shifted_true": float(true_metrics["thermflex_shifted_space_heat_kwh"]),
                    "shifted_pred": float(predicted_metrics["thermflex_shifted_space_heat_kwh"]),
                    "rebound_true": float(true_metrics["thermflex_rebound_kwh"]),
                    "rebound_pred": float(predicted_metrics["thermflex_rebound_kwh"]),
                    "peak_true": float(true_metrics["thermflex_peak_change_kw"]),
                    "peak_pred": float(predicted_metrics["thermflex_peak_change_kw"]),
                }
            )
    daily = pd.DataFrame(daily_rows)
    pos_true = np.maximum(holdout["q_delta_true"].to_numpy(dtype=float), 0.0)
    neg_true = np.maximum(-holdout["q_delta_true"].to_numpy(dtype=float), 0.0)
    return {
        "mode": str(mode),
        "min_rows": int(min_rows),
        "backend": str(backend),
        "feature_preset": str(feature_preset),
        "split_strategy": str(split_strategy),
        "stratify_column": str(stratify_column) if stratify_column is not None else "",
        "used_routes": int(prediction["used_routes"]),
        "routed_rows": int(prediction["routed_rows"]),
        "holdout_rows": int(prediction["holdout_rows"]),
        "holdout_days": int(len(daily)),
        "qdelta_r2": _safe_r2(holdout["q_delta_true"], holdout["q_delta_pred"]),
        "pos_r2": _safe_r2(pos_true, prediction["pos_pred"]),
        "neg_r2": _safe_r2(neg_true, prediction["neg_pred"]),
        "shifted_r2": _safe_r2(daily["shifted_true"], daily["shifted_pred"]),
        "rebound_r2": _safe_r2(daily["rebound_true"], daily["rebound_pred"]),
        "peak_r2": _safe_r2(daily["peak_true"], daily["peak_pred"]),
        "shifted_mae": float(mean_absolute_error(daily["shifted_true"], daily["shifted_pred"])),
        "rebound_mae": float(mean_absolute_error(daily["rebound_true"], daily["rebound_pred"])),
        "peak_mae": float(mean_absolute_error(daily["peak_true"], daily["peak_pred"])),
    }


def _safe_r2(y_true: Any, y_pred: Any) -> float:
    """Return R2 where variance exists, otherwise NaN."""

    true_arr = np.asarray(y_true, dtype=float)
    pred_arr = np.asarray(y_pred, dtype=float)
    if len(true_arr) < 2 or float(np.nanstd(true_arr)) <= 1e-12:
        return float("nan")
    return float(r2_score(true_arr, pred_arr))


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Evaluate routed positive/negative q-delta holdout diagnostics."
    )
    parser.add_argument("--family-hash", required=True)
    parser.add_argument("--dataset-root", type=Path, default=_DEFAULT_DATASET_ROOT)
    parser.add_argument("--model-root", type=Path, default=_DEFAULT_MODEL_ROOT)
    parser.add_argument("--group-column", default="split_group_run")
    parser.add_argument("--split-strategy", default="group_shuffle")
    parser.add_argument("--stratify-column", default=None)
    parser.add_argument("--test-size", type=float, default=0.25)
    parser.add_argument("--random-state", type=int, default=42)
    parser.add_argument("--feature-preset", default="no_case_label")
    parser.add_argument("--backend", default="extra_trees")
    parser.add_argument("--modes", nargs="+", default=["global", "age_hour"])
    parser.add_argument("--min-rows", nargs="+", type=int, default=[250])
    parser.add_argument("--output-name", default="sequence_router_holdout_summary.csv")
    args = parser.parse_args()
    result = evaluate_sequence_router_holdouts(
        family_hash=args.family_hash,
        dataset_root=args.dataset_root,
        model_root=args.model_root,
        group_column=args.group_column,
        split_strategy=args.split_strategy,
        stratify_column=args.stratify_column,
        test_size=float(args.test_size),
        random_state=int(args.random_state),
        feature_preset=args.feature_preset,
        backend=args.backend,
        modes=args.modes,
        min_rows=args.min_rows,
        output_name=args.output_name,
    )
    print(json.dumps({"output_csv_path": str(result["output_csv_path"])}, indent=2))
    print(result["summary"].to_string(index=False))


if __name__ == "__main__":
    main()
