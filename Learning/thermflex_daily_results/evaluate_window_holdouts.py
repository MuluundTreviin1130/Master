from __future__ import annotations

"""Repeated holdout diagnostics for 1- to 3-day daily cost/CO2 windows.

The daily surrogate still predicts day rows. This diagnostic evaluates the
paper-relevant cost and CO2 KPIs on short windows by reconstructing predicted
flex costs/emissions from predicted daily percentage changes and aggregating
against the exported reference totals.
"""

import argparse
import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from Learning.datasets.load_dataset import load_dataset
from Learning.thermflex_daily_results.dataset_builder import _DEFAULT_DATASET_ROOT
from Learning.thermflex_daily_results.evaluate_repeated_holdouts import _fit_predict_targets
from Learning.thermflex_daily_results.train import _metric_block
from Learning.thermflex_daily_results.validate import build_grouped_holdout_split

_DEFAULT_MODEL_ROOT = Path(__file__).resolve().parents[2] / "Learning" / "models"
_PCT_WINDOW_TARGETS = (
    "dispatch_operating_cost_pct_change",
    "co2_emissions_total_pct_change",
)
_NET_ABSOLUTE_WINDOW_TARGETS = (
    "dispatch_operating_cost_eur_delta",
    "co2_emissions_total_t_delta",
)
_HEAT_TOTAL_CO2_WINDOW_TARGETS = (
    "dispatch_heat_operating_cost_eur_delta",
    "co2_emissions_total_t_delta",
)
_HEAT_ALLOCATED_CO2_WINDOW_TARGETS = (
    "dispatch_heat_operating_cost_eur_delta",
    "dispatch_heat_allocated_co2_t_delta",
)


def evaluate_window_holdouts(
    *,
    family_hash: str,
    dataset_root: Path = _DEFAULT_DATASET_ROOT,
    model_root: Path = _DEFAULT_MODEL_ROOT,
    window_days: tuple[int, ...] = (1, 2, 3),
    test_size: float = 0.25,
    first_seed: int = 0,
    n_seeds: int = 5,
    estimator: str = "xgb",
    target_scale: str = "pct",
    policy_case_labels: tuple[str, ...] = (),
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
    truth_df["date_ordinal"] = truth_df["date"].map(pd.Timestamp.toordinal).astype(int)
    target_scale_normalized = _normalize_target_scale(target_scale)
    _validate_window_truth_columns(truth_df, target_scale=target_scale_normalized)
    mask = _build_filter_mask(truth_df=truth_df, policy_case_labels=policy_case_labels)
    if not mask.any():
        raise ValueError("[thermflex_daily_results] selected window-holdout subset is empty.")
    truth_df = truth_df.loc[mask].reset_index(drop=True)

    all_target_names = list(dataset_bundle["meta"]["target_columns"])
    window_targets = _window_targets_for_scale(target_scale_normalized)
    missing_targets = [target for target in window_targets if target not in all_target_names]
    if missing_targets:
        raise ValueError(
            "[thermflex_daily_results] window diagnostics missing required prediction targets: "
            + ", ".join(missing_targets)
        )
    target_indices = [all_target_names.index(target) for target in window_targets]
    selected_positions = np.flatnonzero(mask.to_numpy())
    x = np.asarray(dataset_bundle["X"], dtype=float)[selected_positions, :]
    y = np.asarray(dataset_bundle["Y"], dtype=float)[selected_positions, :][:, target_indices]

    all_rows: list[dict[str, Any]] = []
    for window_day_count in tuple(int(value) for value in window_days):
        if window_day_count <= 0:
            raise ValueError("[thermflex_daily_results] window_days values must be positive.")
        group_column = f"split_group_{window_day_count}d_window"
        truth_df[group_column] = (
            (truth_df["date_ordinal"] - int(truth_df["date_ordinal"].min())) // window_day_count
        ).astype(str)
        for seed in range(int(first_seed), int(first_seed) + int(n_seeds)):
            split = build_grouped_holdout_split(
                truth_df=truth_df,
                group_column=group_column,
                test_size=test_size,
                random_state=seed,
            )
            y_pred = _fit_predict_targets(
                x_train=x[split.train_index, :],
                x_test=x[split.test_index, :],
                y_train=y[split.train_index, :],
                target_names=list(window_targets),
                random_state=seed,
                estimator=estimator,
            )
            daily_metrics = _metric_block(
                y_true=y[split.test_index, :],
                y_pred=y_pred,
                target_names=list(window_targets),
            )
            for metric_row in daily_metrics.to_dict(orient="records"):
                metric_row.update(
                    {
                        "seed": seed,
                        "window_days": window_day_count,
                        "aggregation": "daily_rows",
                        "n_eval_rows": int(len(split.test_index)),
                    }
                )
                all_rows.append(metric_row)

            window_metrics = _window_metric_block(
                truth_df=truth_df.iloc[split.test_index].copy(),
                y_pred=y_pred,
                window_days=window_day_count,
                group_column=group_column,
                target_scale=target_scale_normalized,
            )
            for metric_row in window_metrics.to_dict(orient="records"):
                metric_row.update(
                    {
                        "seed": seed,
                        "window_days": window_day_count,
                        "aggregation": "short_windows",
                    }
                )
                all_rows.append(metric_row)

    metrics_df = pd.DataFrame(all_rows)
    summary_df = _summarize_window_metrics(metrics_df)
    diagnostic_dir = Path(model_root).resolve() / (
        f"thermflex_daily_results_window_{output_name}"
        if output_name
        else f"thermflex_daily_results_window_{family_hash[:12]}"
    )
    diagnostic_dir.mkdir(parents=True, exist_ok=True)
    metrics_csv = diagnostic_dir / "window_holdout_metrics.csv"
    summary_csv = diagnostic_dir / "window_holdout_summary.csv"
    summary_json = diagnostic_dir / "window_holdout_summary.json"
    metrics_df.to_csv(metrics_csv, index=False)
    summary_df.to_csv(summary_csv, index=False)
    payload = {
        "family_hash": family_hash,
        "window_days": list(window_days),
        "test_size": float(test_size),
        "first_seed": int(first_seed),
        "n_seeds": int(n_seeds),
        "estimator": estimator,
        "target_scale": target_scale_normalized,
        "policy_case_labels": list(policy_case_labels),
        "n_rows": int(len(truth_df)),
        "summary": summary_df.to_dict(orient="records"),
    }
    summary_json.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return {
        "diagnostic_dir": diagnostic_dir,
        "metrics_csv": metrics_csv,
        "summary_csv": summary_csv,
        "summary_json": summary_json,
        "summary": payload,
    }


def _validate_window_truth_columns(truth_df: pd.DataFrame, *, target_scale: str) -> None:
    target_scale_normalized = _normalize_target_scale(target_scale)
    required = {"source_bundle_name"}
    if target_scale_normalized == "pct":
        required.update(
            {
                "dispatch_operating_cost_eur_ref",
                "dispatch_operating_cost_eur_flex",
                "co2_emissions_total_t_ref",
                "co2_emissions_total_t_flex",
            }
        )
    elif target_scale_normalized == "absolute":
        required.update(
            {
                "dispatch_operating_cost_eur_ref",
                "dispatch_operating_cost_eur_flex",
                "co2_emissions_total_t_ref",
                "co2_emissions_total_t_flex",
            }
        )
    elif target_scale_normalized == "heat_absolute":
        required.update(
            {
                "dispatch_heat_operating_cost_eur_ref",
                "dispatch_heat_operating_cost_eur_flex",
                "co2_emissions_total_t_ref",
                "co2_emissions_total_t_flex",
            }
        )
    elif target_scale_normalized == "heat_allocated_absolute":
        required.update(
            {
                "dispatch_heat_operating_cost_eur_ref",
                "dispatch_heat_operating_cost_eur_flex",
                "dispatch_heat_allocated_co2_t_ref",
                "dispatch_heat_allocated_co2_t_flex",
            }
        )
    else:
        raise ValueError(f"[thermflex_daily_results] unsupported target_scale: {target_scale}")
    missing = sorted(required.difference(truth_df.columns))
    if missing:
        raise KeyError(
            "[thermflex_daily_results] window diagnostics missing truth columns: "
            + ", ".join(missing)
        )
    null_columns = sorted(column for column in required if truth_df[column].isna().any())
    if null_columns:
        raise ValueError(
            "[thermflex_daily_results] window diagnostics require complete cost/CO2 truth columns: "
            + ", ".join(null_columns)
        )


def _build_filter_mask(*, truth_df: pd.DataFrame, policy_case_labels: tuple[str, ...]) -> pd.Series:
    mask = pd.Series(True, index=truth_df.index)
    if policy_case_labels:
        labels = {str(label) for label in policy_case_labels}
        mask &= truth_df["policy_case_label_canonical"].astype(str).isin(labels)
    return mask


def _window_metric_block(
    *,
    truth_df: pd.DataFrame,
    y_pred: np.ndarray,
    window_days: int,
    group_column: str,
    target_scale: str,
) -> pd.DataFrame:
    eval_df = truth_df.copy()
    target_scale_normalized = _normalize_target_scale(target_scale)
    if target_scale_normalized == "pct":
        eval_df["pred_dispatch_operating_cost_pct_change"] = y_pred[:, 0]
        eval_df["pred_co2_emissions_total_pct_change"] = y_pred[:, 1]
        eval_df["pred_dispatch_operating_cost_eur_flex"] = (
            pd.to_numeric(eval_df["dispatch_operating_cost_eur_ref"], errors="raise")
            * (1.0 + eval_df["pred_dispatch_operating_cost_pct_change"] / 100.0)
        )
        eval_df["pred_co2_emissions_total_t_flex"] = (
            pd.to_numeric(eval_df["co2_emissions_total_t_ref"], errors="raise")
            * (1.0 + eval_df["pred_co2_emissions_total_pct_change"] / 100.0)
        )
    elif target_scale_normalized == "absolute":
        eval_df["pred_dispatch_operating_cost_eur_delta"] = y_pred[:, 0]
        eval_df["pred_co2_emissions_total_t_delta"] = y_pred[:, 1]
        eval_df["pred_dispatch_operating_cost_eur_flex"] = (
            pd.to_numeric(eval_df["dispatch_operating_cost_eur_ref"], errors="raise")
            + eval_df["pred_dispatch_operating_cost_eur_delta"]
        )
        eval_df["pred_co2_emissions_total_t_flex"] = (
            pd.to_numeric(eval_df["co2_emissions_total_t_ref"], errors="raise")
            + eval_df["pred_co2_emissions_total_t_delta"]
        )
    elif target_scale_normalized == "heat_absolute":
        eval_df["pred_dispatch_heat_operating_cost_eur_delta"] = y_pred[:, 0]
        eval_df["pred_co2_emissions_total_t_delta"] = y_pred[:, 1]
        eval_df["pred_dispatch_heat_operating_cost_eur_flex"] = (
            pd.to_numeric(eval_df["dispatch_heat_operating_cost_eur_ref"], errors="raise")
            + eval_df["pred_dispatch_heat_operating_cost_eur_delta"]
        )
        eval_df["pred_co2_emissions_total_t_flex"] = (
            pd.to_numeric(eval_df["co2_emissions_total_t_ref"], errors="raise")
            + eval_df["pred_co2_emissions_total_t_delta"]
        )
    elif target_scale_normalized == "heat_allocated_absolute":
        eval_df["pred_dispatch_heat_operating_cost_eur_delta"] = y_pred[:, 0]
        eval_df["pred_dispatch_heat_allocated_co2_t_delta"] = y_pred[:, 1]
        eval_df["pred_dispatch_heat_operating_cost_eur_flex"] = (
            pd.to_numeric(eval_df["dispatch_heat_operating_cost_eur_ref"], errors="raise")
            + eval_df["pred_dispatch_heat_operating_cost_eur_delta"]
        )
        eval_df["pred_dispatch_heat_allocated_co2_t_flex"] = (
            pd.to_numeric(eval_df["dispatch_heat_allocated_co2_t_ref"], errors="raise")
            + eval_df["pred_dispatch_heat_allocated_co2_t_delta"]
        )
    else:
        raise ValueError(f"[thermflex_daily_results] unsupported target_scale: {target_scale}")
    grouped_rows: list[dict[str, float]] = []
    for (_bundle, _window), group in eval_df.groupby(["source_bundle_name", group_column], sort=True):
        if len(group) != int(window_days):
            continue
        if target_scale_normalized == "pct":
            cost_ref = float(pd.to_numeric(group["dispatch_operating_cost_eur_ref"], errors="raise").sum())
            co2_ref = float(pd.to_numeric(group["co2_emissions_total_t_ref"], errors="raise").sum())
            if abs(cost_ref) < 1e-12 or co2_ref <= 0.0:
                raise ValueError(
                    "[thermflex_daily_results] window diagnostics require nonzero cost and positive CO2 references."
                )
            true_cost_flex = float(pd.to_numeric(group["dispatch_operating_cost_eur_flex"], errors="raise").sum())
            pred_cost_flex = float(group["pred_dispatch_operating_cost_eur_flex"].sum())
            true_co2_flex = float(pd.to_numeric(group["co2_emissions_total_t_flex"], errors="raise").sum())
            pred_co2_flex = float(group["pred_co2_emissions_total_t_flex"].sum())
            grouped_rows.append(
                {
                    "true_dispatch_operating_cost_pct_change": _pct_delta(true_cost_flex, cost_ref),
                    "pred_dispatch_operating_cost_pct_change": _pct_delta(pred_cost_flex, cost_ref),
                    "true_co2_emissions_total_pct_change": _pct_delta(true_co2_flex, co2_ref),
                    "pred_co2_emissions_total_pct_change": _pct_delta(pred_co2_flex, co2_ref),
                }
            )
        elif target_scale_normalized == "absolute":
            cost_ref = float(pd.to_numeric(group["dispatch_operating_cost_eur_ref"], errors="raise").sum())
            co2_ref = float(pd.to_numeric(group["co2_emissions_total_t_ref"], errors="raise").sum())
            true_cost_flex = float(pd.to_numeric(group["dispatch_operating_cost_eur_flex"], errors="raise").sum())
            pred_cost_flex = float(group["pred_dispatch_operating_cost_eur_flex"].sum())
            true_co2_flex = float(pd.to_numeric(group["co2_emissions_total_t_flex"], errors="raise").sum())
            pred_co2_flex = float(group["pred_co2_emissions_total_t_flex"].sum())
            grouped_rows.append(
                {
                    "true_dispatch_operating_cost_eur_delta": true_cost_flex - cost_ref,
                    "pred_dispatch_operating_cost_eur_delta": pred_cost_flex - cost_ref,
                    "true_co2_emissions_total_t_delta": true_co2_flex - co2_ref,
                    "pred_co2_emissions_total_t_delta": pred_co2_flex - co2_ref,
                }
            )
        elif target_scale_normalized == "heat_absolute":
            heat_cost_ref = float(pd.to_numeric(group["dispatch_heat_operating_cost_eur_ref"], errors="raise").sum())
            co2_ref = float(pd.to_numeric(group["co2_emissions_total_t_ref"], errors="raise").sum())
            true_heat_cost_flex = float(pd.to_numeric(group["dispatch_heat_operating_cost_eur_flex"], errors="raise").sum())
            pred_heat_cost_flex = float(group["pred_dispatch_heat_operating_cost_eur_flex"].sum())
            true_co2_flex = float(pd.to_numeric(group["co2_emissions_total_t_flex"], errors="raise").sum())
            pred_co2_flex = float(group["pred_co2_emissions_total_t_flex"].sum())
            grouped_rows.append(
                {
                    "true_dispatch_heat_operating_cost_eur_delta": true_heat_cost_flex - heat_cost_ref,
                    "pred_dispatch_heat_operating_cost_eur_delta": pred_heat_cost_flex - heat_cost_ref,
                    "true_co2_emissions_total_t_delta": true_co2_flex - co2_ref,
                    "pred_co2_emissions_total_t_delta": pred_co2_flex - co2_ref,
                }
            )
        elif target_scale_normalized == "heat_allocated_absolute":
            heat_cost_ref = float(pd.to_numeric(group["dispatch_heat_operating_cost_eur_ref"], errors="raise").sum())
            heat_co2_ref = float(pd.to_numeric(group["dispatch_heat_allocated_co2_t_ref"], errors="raise").sum())
            true_heat_cost_flex = float(pd.to_numeric(group["dispatch_heat_operating_cost_eur_flex"], errors="raise").sum())
            pred_heat_cost_flex = float(group["pred_dispatch_heat_operating_cost_eur_flex"].sum())
            true_heat_co2_flex = float(pd.to_numeric(group["dispatch_heat_allocated_co2_t_flex"], errors="raise").sum())
            pred_heat_co2_flex = float(group["pred_dispatch_heat_allocated_co2_t_flex"].sum())
            grouped_rows.append(
                {
                    "true_dispatch_heat_operating_cost_eur_delta": true_heat_cost_flex - heat_cost_ref,
                    "pred_dispatch_heat_operating_cost_eur_delta": pred_heat_cost_flex - heat_cost_ref,
                    "true_dispatch_heat_allocated_co2_t_delta": true_heat_co2_flex - heat_co2_ref,
                    "pred_dispatch_heat_allocated_co2_t_delta": pred_heat_co2_flex - heat_co2_ref,
                }
            )
    if not grouped_rows:
        raise ValueError(
            "[thermflex_daily_results] no complete evaluation windows available for "
            f"window_days={window_days}."
        )
    frame = pd.DataFrame(grouped_rows)
    if target_scale_normalized == "pct":
        true_columns = [
            "true_dispatch_operating_cost_pct_change",
            "true_co2_emissions_total_pct_change",
        ]
        pred_columns = [
            "pred_dispatch_operating_cost_pct_change",
            "pred_co2_emissions_total_pct_change",
        ]
    elif target_scale_normalized == "absolute":
        true_columns = [
            "true_dispatch_operating_cost_eur_delta",
            "true_co2_emissions_total_t_delta",
        ]
        pred_columns = [
            "pred_dispatch_operating_cost_eur_delta",
            "pred_co2_emissions_total_t_delta",
        ]
    elif target_scale_normalized == "heat_absolute":
        true_columns = [
            "true_dispatch_heat_operating_cost_eur_delta",
            "true_co2_emissions_total_t_delta",
        ]
        pred_columns = [
            "pred_dispatch_heat_operating_cost_eur_delta",
            "pred_co2_emissions_total_t_delta",
        ]
    elif target_scale_normalized == "heat_allocated_absolute":
        true_columns = [
            "true_dispatch_heat_operating_cost_eur_delta",
            "true_dispatch_heat_allocated_co2_t_delta",
        ]
        pred_columns = [
            "pred_dispatch_heat_operating_cost_eur_delta",
            "pred_dispatch_heat_allocated_co2_t_delta",
        ]
    else:
        raise ValueError(f"[thermflex_daily_results] unsupported target_scale: {target_scale}")
    return _metric_block(
        y_true=frame[true_columns].to_numpy(dtype=float),
        y_pred=frame[pred_columns].to_numpy(dtype=float),
        target_names=list(_window_targets_for_scale(target_scale_normalized)),
    ).assign(n_eval_rows=int(len(frame)))


def _normalize_target_scale(target_scale: str) -> str:
    normalized = str(target_scale).strip().lower()
    allowed = {"pct", "absolute", "heat_absolute", "heat_allocated_absolute"}
    if normalized not in allowed:
        raise ValueError(
            "[thermflex_daily_results] unsupported window target_scale "
            f"'{target_scale}'. Expected one of: {', '.join(sorted(allowed))}."
        )
    return normalized


def _window_targets_for_scale(target_scale: str) -> tuple[str, str]:
    normalized = _normalize_target_scale(target_scale)
    if normalized == "pct":
        return _PCT_WINDOW_TARGETS
    if normalized == "absolute":
        return _NET_ABSOLUTE_WINDOW_TARGETS
    if normalized == "heat_absolute":
        return _HEAT_TOTAL_CO2_WINDOW_TARGETS
    if normalized == "heat_allocated_absolute":
        return _HEAT_ALLOCATED_CO2_WINDOW_TARGETS
    raise ValueError(f"[thermflex_daily_results] unsupported target_scale: {target_scale}")


def _pct_delta(value: float, reference: float) -> float:
    if abs(reference) < 1e-12:
        raise ValueError("[thermflex_daily_results] percentage delta reference must be nonzero.")
    return float(100.0 * (float(value) - float(reference)) / float(reference))


def _summarize_window_metrics(metrics_df: pd.DataFrame) -> pd.DataFrame:
    return (
        metrics_df.groupby(["aggregation", "window_days", "target"], sort=True)
        .agg(
            n_seeds=("r2", "count"),
            n_eval_rows_median=("n_eval_rows", "median"),
            r2_mean=("r2", "mean"),
            r2_median=("r2", "median"),
            r2_min=("r2", "min"),
            r2_max=("r2", "max"),
        )
        .reset_index()
    )


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--family-hash", required=True)
    parser.add_argument("--dataset-root", type=Path, default=_DEFAULT_DATASET_ROOT)
    parser.add_argument("--model-root", type=Path, default=_DEFAULT_MODEL_ROOT)
    parser.add_argument("--window-days", type=int, action="append", default=None)
    parser.add_argument("--test-size", type=float, default=0.25)
    parser.add_argument("--first-seed", type=int, default=0)
    parser.add_argument("--n-seeds", type=int, default=5)
    parser.add_argument("--estimator", default="xgb")
    parser.add_argument(
        "--target-scale",
        choices=("pct", "absolute", "heat_absolute", "heat_allocated_absolute"),
        default="pct",
    )
    parser.add_argument("--policy-case-label", dest="policy_case_labels", action="append", default=[])
    parser.add_argument("--output-name", default=None)
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    result = evaluate_window_holdouts(
        family_hash=args.family_hash,
        dataset_root=args.dataset_root,
        model_root=args.model_root,
        window_days=tuple(args.window_days or [1, 2, 3]),
        test_size=args.test_size,
        first_seed=args.first_seed,
        n_seeds=args.n_seeds,
        estimator=args.estimator,
        target_scale=args.target_scale,
        policy_case_labels=tuple(args.policy_case_labels),
        output_name=args.output_name,
    )
    print(json.dumps({key: str(value) for key, value in result.items() if key != "summary"}, indent=2))
    print(json.dumps(result["summary"], indent=2))


if __name__ == "__main__":
    main()
