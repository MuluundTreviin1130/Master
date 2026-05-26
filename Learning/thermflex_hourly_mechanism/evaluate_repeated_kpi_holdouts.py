from __future__ import annotations

"""Run repeated grouped KPI holdout checks for hourly ThermFlex models.

Why this exists:
- single grouped holdouts are too brittle for small tau/family slices,
- KPI-level R2 is especially unstable when the holdout has little true variance,
- repeated checks should be persisted as diagnostics instead of remaining
  one-off notebook or shell snippets,
- after diagnostics, the caller can restore one chosen final seed as the active
  artifact in the normal model directory.
"""

import argparse
import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from Learning.thermflex_hourly_mechanism.evaluate_kpi_reaggregation import (
    evaluate_holdout_daily_reaggregation,
)
from Learning.thermflex_hourly_mechanism.rebound_postprocessor import (
    fit_rebound_postprocessor as fit_named_rebound_postprocessor,
)
from Learning.thermflex_hourly_mechanism.shifted_postprocessor import (
    fit_daily_xgb_shifted_postprocessor,
)
from Learning.thermflex_hourly_mechanism.train import (
    _DEFAULT_MODEL_ROOT,
    train_hourly_mechanism_model,
)

_DEFAULT_DATASET_ROOT = Path(__file__).resolve().parents[2] / "Learning" / "datasets"


def run_repeated_kpi_holdout_check(
    *,
    family_hash: str,
    dataset_root: Path = _DEFAULT_DATASET_ROOT,
    model_root: Path = _DEFAULT_MODEL_ROOT,
    target_profile: str = "mechanism_energy_intensive",
    group_column: str = "split_group_run",
    test_size: float = 0.25,
    split_strategy: str = "group_shuffle",
    stratify_column: str | None = None,
    feature_preset: str = "all",
    target_transform_profile: str = "default",
    first_seed: int = 0,
    n_seeds: int = 10,
    fit_shifted_postprocessor: bool = False,
    shifted_postprocessor_profile: str = "tau4_lower_relax_shifted_daily_xgb_v1",
    fit_rebound_postprocessor: bool = False,
    rebound_postprocessor_profile: str = "lower_relax_evt24_conservative_v1",
    final_seed: int | None = None,
    output_name: str = "repeated_kpi_holdout_summary.csv",
) -> dict[str, Any]:
    """Train/evaluate a sequence of seeds and persist KPI diagnostics.

    Each seed writes the normal model artifact path, matching the existing
    training contract. If `final_seed` is supplied, the artifact is restored to
    that seed after the diagnostics loop so downstream users know which model is
    currently represented by the directory.
    """

    if int(n_seeds) <= 0:
        raise ValueError("[thermflex_hourly_mechanism] n_seeds must be positive.")
    dataset_dir = Path(dataset_root).resolve() / str(family_hash)
    if not (dataset_dir / "truth_dataset.csv").exists():
        raise FileNotFoundError(
            "[thermflex_hourly_mechanism] repeated KPI check dataset is missing truth_dataset.csv: "
            f"{dataset_dir}"
        )

    rows: list[dict[str, Any]] = []
    last_model_dir: Path | None = None
    for seed in range(int(first_seed), int(first_seed) + int(n_seeds)):
        train_result = train_hourly_mechanism_model(
            family_hash=str(family_hash),
            dataset_root=Path(dataset_root).resolve(),
            model_root=Path(model_root).resolve(),
            group_column=group_column,
            test_size=test_size,
            random_state=int(seed),
            split_strategy=split_strategy,
            stratify_column=stratify_column,
            target_profile=target_profile,
            feature_preset=feature_preset,
            target_transform_profile=target_transform_profile,
        )
        model_dir = Path(train_result["artifact_dir"]).resolve()
        last_model_dir = model_dir
        raw_result = evaluate_holdout_daily_reaggregation(
            model_dir=model_dir,
            dataset_dir=dataset_dir,
        )
        rows.append(
            _metric_row(
                seed=seed,
                variant="raw",
                metrics=raw_result["metrics"],
                split_strategy=split_strategy,
                stratify_column=stratify_column,
            )
            )
        if bool(fit_shifted_postprocessor):
            shifted = fit_daily_xgb_shifted_postprocessor(
                model_dir=model_dir,
                dataset_dir=dataset_dir,
                profile=shifted_postprocessor_profile,
            )
            shifted_payload = shifted["payload"]
            shifted_result = evaluate_holdout_daily_reaggregation(
                model_dir=model_dir,
                dataset_dir=dataset_dir,
                shifted_postprocessor=shifted_payload,
            )
            rows.append(
                _metric_row(
                    seed=seed,
                    variant=str(shifted["payload"]["profile"]),
                    metrics=shifted_result["metrics"],
                    split_strategy=split_strategy,
                    stratify_column=stratify_column,
                )
            )
        else:
            shifted_payload = None
        if bool(fit_rebound_postprocessor):
            rebound = fit_named_rebound_postprocessor(
                model_dir=model_dir,
                dataset_dir=dataset_dir,
                profile=rebound_postprocessor_profile,
            )
            rebound_payload = rebound["payload"]
            rebound_result = evaluate_holdout_daily_reaggregation(
                model_dir=model_dir,
                dataset_dir=dataset_dir,
                rebound_postprocessor=rebound_payload,
            )
            rows.append(
                _metric_row(
                    seed=seed,
                    variant=str(rebound["payload"]["profile"]),
                    metrics=rebound_result["metrics"],
                    split_strategy=split_strategy,
                    stratify_column=stratify_column,
                )
            )
        else:
            rebound_payload = None
        if shifted_payload is not None and rebound_payload is not None:
            combined_result = evaluate_holdout_daily_reaggregation(
                model_dir=model_dir,
                dataset_dir=dataset_dir,
                shifted_postprocessor=shifted_payload,
                rebound_postprocessor=rebound_payload,
            )
            rows.append(
                _metric_row(
                    seed=seed,
                    variant=f"{shifted_payload['profile']}+{rebound_payload['profile']}",
                    metrics=combined_result["metrics"],
                    split_strategy=split_strategy,
                    stratify_column=stratify_column,
                )
            )
    if last_model_dir is None:
        raise RuntimeError("[thermflex_hourly_mechanism] repeated KPI check did not train any model.")

    diagnostics_dir = last_model_dir / "diagnostics"
    diagnostics_dir.mkdir(parents=True, exist_ok=True)
    summary_csv_path = diagnostics_dir / output_name
    diagnostics_df = pd.DataFrame(rows)
    diagnostics_df.to_csv(summary_csv_path, index=False)
    summary_payload = _summary_payload(diagnostics_df)
    summary_json_path = diagnostics_dir / f"{summary_csv_path.stem}.json"
    summary_json_path.write_text(json.dumps(summary_payload, indent=2), encoding="utf-8")

    final_payload: dict[str, Any] | None = None
    if final_seed is not None:
        final_payload = _restore_final_seed(
            family_hash=str(family_hash),
            dataset_root=Path(dataset_root).resolve(),
            dataset_dir=dataset_dir,
            model_root=Path(model_root).resolve(),
            target_profile=target_profile,
            group_column=group_column,
            test_size=test_size,
            split_strategy=split_strategy,
            stratify_column=stratify_column,
            feature_preset=feature_preset,
            target_transform_profile=target_transform_profile,
            final_seed=int(final_seed),
            fit_shifted_postprocessor=bool(fit_shifted_postprocessor),
            shifted_postprocessor_profile=shifted_postprocessor_profile,
            fit_rebound_postprocessor=bool(fit_rebound_postprocessor),
            rebound_postprocessor_profile=rebound_postprocessor_profile,
        )
        (last_model_dir / "diagnostics" / "final_seed.json").write_text(
            json.dumps(final_payload, indent=2),
            encoding="utf-8",
        )

    return {
        "summary_csv_path": summary_csv_path,
        "summary_json_path": summary_json_path,
        "summary": summary_payload,
        "final_seed": final_payload,
    }


def _restore_final_seed(
    *,
    family_hash: str,
    dataset_root: Path,
    dataset_dir: Path,
    model_root: Path,
    target_profile: str,
    group_column: str,
    test_size: float,
    split_strategy: str,
    stratify_column: str | None,
    feature_preset: str,
    target_transform_profile: str,
    final_seed: int,
    fit_shifted_postprocessor: bool,
    shifted_postprocessor_profile: str,
    fit_rebound_postprocessor: bool,
    rebound_postprocessor_profile: str,
) -> dict[str, Any]:
    """Retrain one selected seed after diagnostics overwrite the artifact."""

    train_result = train_hourly_mechanism_model(
        family_hash=family_hash,
        dataset_root=dataset_root,
        model_root=model_root,
        group_column=group_column,
        test_size=test_size,
        random_state=final_seed,
        split_strategy=split_strategy,
        stratify_column=stratify_column,
        target_profile=target_profile,
        feature_preset=feature_preset,
        target_transform_profile=target_transform_profile,
    )
    model_dir = Path(train_result["artifact_dir"]).resolve()
    shifted_payload = None
    if fit_shifted_postprocessor:
        shifted_payload = fit_daily_xgb_shifted_postprocessor(
            model_dir=model_dir,
            dataset_dir=dataset_dir,
            profile=shifted_postprocessor_profile,
        )["payload"]
    rebound_payload = None
    if fit_rebound_postprocessor:
        rebound_payload = fit_named_rebound_postprocessor(
            model_dir=model_dir,
            dataset_dir=dataset_dir,
            profile=rebound_postprocessor_profile,
        )["payload"]
    metrics = evaluate_holdout_daily_reaggregation(
        model_dir=model_dir,
        dataset_dir=dataset_dir,
        shifted_postprocessor=shifted_payload,
        rebound_postprocessor=rebound_payload,
    )["metrics"]
    return {
        "final_seed": int(final_seed),
        "model_dir": str(model_dir),
        "fit_shifted_postprocessor": bool(fit_shifted_postprocessor),
        "shifted_postprocessor_profile": str(shifted_postprocessor_profile),
        "fit_rebound_postprocessor": bool(fit_rebound_postprocessor),
        "rebound_postprocessor_profile": str(rebound_postprocessor_profile),
        "feature_preset": str(feature_preset),
        "target_transform_profile": str(target_transform_profile),
        "metrics": metrics,
    }


def _metric_row(
    *,
    seed: int,
    variant: str,
    metrics: dict[str, Any],
    split_strategy: str,
    stratify_column: str | None,
) -> dict[str, Any]:
    """Normalize one evaluator metric payload for CSV diagnostics."""

    return {
        "seed": int(seed),
        "variant": str(variant),
        "split_strategy": str(split_strategy),
        "stratify_column": str(stratify_column) if stratify_column is not None else "",
        "shifted_r2": float(metrics["shifted_r2"]),
        "rebound_r2": float(metrics["rebound_r2"]),
        "peak_r2": float(metrics["peak_r2"]),
        "n_holdout_days": int(metrics["n_holdout_days"]),
        "n_holdout_runs": int(metrics["n_holdout_runs"]),
    }


def _summary_payload(diagnostics_df: pd.DataFrame) -> dict[str, Any]:
    """Summarize repeated KPI checks by variant and metric."""

    payload: dict[str, Any] = {}
    for variant, variant_df in diagnostics_df.groupby("variant", sort=True):
        payload[str(variant)] = {
            metric: _numeric_summary(variant_df[metric].to_numpy(dtype=float))
            for metric in ("shifted_r2", "rebound_r2", "peak_r2")
        }
    return payload


def _numeric_summary(values: np.ndarray) -> dict[str, float]:
    """Return compact NaN-aware summary statistics for one metric vector."""

    arr = np.asarray(values, dtype=float)
    return {
        "mean": float(np.nanmean(arr)),
        "median": float(np.nanmedian(arr)),
        "min": float(np.nanmin(arr)),
        "max": float(np.nanmax(arr)),
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run repeated hourly ThermFlex KPI holdout checks."
    )
    parser.add_argument("--family-hash", required=True)
    parser.add_argument("--dataset-root", type=Path, default=_DEFAULT_DATASET_ROOT)
    parser.add_argument("--model-root", type=Path, default=_DEFAULT_MODEL_ROOT)
    parser.add_argument("--target-profile", default="mechanism_energy_intensive")
    parser.add_argument("--group-column", default="split_group_run")
    parser.add_argument("--test-size", type=float, default=0.25)
    parser.add_argument("--split-strategy", default="group_shuffle")
    parser.add_argument("--stratify-column", default=None)
    parser.add_argument("--feature-preset", default="all")
    parser.add_argument("--target-transform-profile", default="default")
    parser.add_argument("--first-seed", type=int, default=0)
    parser.add_argument("--n-seeds", type=int, default=10)
    parser.add_argument("--fit-shifted-postprocessor", action="store_true")
    parser.add_argument(
        "--shifted-postprocessor-profile",
        default="tau4_lower_relax_shifted_daily_xgb_v1",
    )
    parser.add_argument("--fit-rebound-postprocessor", action="store_true")
    parser.add_argument(
        "--rebound-postprocessor-profile",
        default="lower_relax_evt24_conservative_v1",
    )
    parser.add_argument("--final-seed", type=int, default=None)
    parser.add_argument("--output-name", default="repeated_kpi_holdout_summary.csv")
    args = parser.parse_args()
    result = run_repeated_kpi_holdout_check(
        family_hash=args.family_hash,
        dataset_root=args.dataset_root,
        model_root=args.model_root,
        target_profile=args.target_profile,
        group_column=args.group_column,
        test_size=args.test_size,
        split_strategy=args.split_strategy,
        stratify_column=args.stratify_column,
        feature_preset=args.feature_preset,
        target_transform_profile=args.target_transform_profile,
        first_seed=args.first_seed,
        n_seeds=args.n_seeds,
        fit_shifted_postprocessor=bool(args.fit_shifted_postprocessor),
        shifted_postprocessor_profile=args.shifted_postprocessor_profile,
        fit_rebound_postprocessor=bool(args.fit_rebound_postprocessor),
        rebound_postprocessor_profile=args.rebound_postprocessor_profile,
        final_seed=args.final_seed,
        output_name=args.output_name,
    )
    print(json.dumps({key: str(value) for key, value in result.items() if key.endswith("_path")}, indent=2))
    print(json.dumps(result["summary"], indent=2))
    if result["final_seed"] is not None:
        print(json.dumps(result["final_seed"], indent=2))


if __name__ == "__main__":
    main()
