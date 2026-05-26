from __future__ import annotations

"""Run repeated upper-only subcontract diagnostics across grouped splits."""

import argparse
import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from Learning.thermflex_hourly_mechanism.dataset_builder import _DEFAULT_DATASET_ROOT
from Learning.thermflex_hourly_mechanism.evaluate_upper_only_subcontracts import (
    evaluate_upper_only_subcontracts,
)
from Learning.thermflex_hourly_mechanism.train import (
    _DEFAULT_MODEL_ROOT,
    train_hourly_mechanism_model,
)


DEFAULT_UPPER_ONLY_HASH = "6d058845d59b20453e43f83a1aec191c008683dee567ce9644a90d92d228a7fc"


def evaluate_repeated_upper_only_subcontracts(
    *,
    family_hash: str = DEFAULT_UPPER_ONLY_HASH,
    dataset_root: Path = _DEFAULT_DATASET_ROOT,
    model_root: Path = _DEFAULT_MODEL_ROOT,
    output_dir: Path | None = None,
    first_seed: int = 0,
    n_seeds: int = 5,
    backend: str = "extra_trees",
    activation_threshold_kwh: float = 25_000.0,
    target_profile: str = "mechanism_energy_intensive",
    feature_preset: str = "no_case_label",
    target_transform_profile: str = "mechanism_mass_identity",
    split_strategy: str = "group_shuffle",
    stratify_column: str | None = None,
    test_size: float = 0.25,
) -> dict[str, Any]:
    """Train/evaluate repeated upper-only subcontract checks."""

    if int(n_seeds) <= 0:
        raise ValueError("[upper_only_repeated_subcontracts] n_seeds must be positive.")
    dataset_dir = Path(dataset_root).resolve() / str(family_hash)
    if not (dataset_dir / "truth_dataset.csv").exists():
        raise FileNotFoundError(
            "[upper_only_repeated_subcontracts] dataset missing truth_dataset.csv: "
            f"{dataset_dir}"
        )
    if output_dir is None:
        output_root = (
            Path(model_root).resolve()
            / f"thermflex_hourly_mechanism_upper_only_subcontracts_repeated_{family_hash[:12]}"
        )
    else:
        output_root = Path(output_dir).resolve()
    output_root.mkdir(parents=True, exist_ok=True)

    rows: list[dict[str, Any]] = []
    for seed in range(int(first_seed), int(first_seed) + int(n_seeds)):
        train_result = train_hourly_mechanism_model(
            family_hash=str(family_hash),
            dataset_root=Path(dataset_root).resolve(),
            model_root=Path(model_root).resolve(),
            target_profile=target_profile,
            feature_preset=feature_preset,
            target_transform_profile=target_transform_profile,
            random_state=int(seed),
            split_strategy=split_strategy,
            stratify_column=stratify_column,
            test_size=float(test_size),
        )
        model_dir = Path(train_result["artifact_dir"]).resolve()
        seed_output_dir = output_root / f"seed_{seed:03d}"
        result = evaluate_upper_only_subcontracts(
            model_dir=model_dir,
            dataset_dir=dataset_dir,
            output_dir=seed_output_dir,
            activation_threshold_kwh=float(activation_threshold_kwh),
            backend=backend,
        )
        rows.extend(_rows_from_result(seed=seed, result=result))

    repeated_df = pd.DataFrame(rows)
    summary_df = _summary_by_variant(repeated_df)
    rows_csv = output_root / "repeated_subcontract_rows.csv"
    summary_csv = output_root / "repeated_subcontract_summary.csv"
    summary_json = output_root / "repeated_subcontract_summary.json"
    repeated_df.to_csv(rows_csv, index=False)
    summary_df.to_csv(summary_csv, index=False)
    payload = {
        "family_hash": str(family_hash),
        "backend": str(backend),
        "n_seeds": int(n_seeds),
        "rows_csv": str(rows_csv),
        "summary_csv": str(summary_csv),
        "summary": summary_df.to_dict(orient="records"),
    }
    summary_json.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return payload


def _rows_from_result(*, seed: int, result: dict[str, Any]) -> list[dict[str, Any]]:
    """Normalize one subcontract result payload for repeated summaries."""

    rows: list[dict[str, Any]] = []
    for source_key, metric_rows in (
        ("mass", result["mass_metrics"]),
        ("rebound", result["rebound_metrics"]),
        ("shifted", result["shifted_metrics"]),
        ("combined", result["combined_metrics"]),
    ):
        for metric in metric_rows:
            row = {"seed": int(seed), "source": source_key}
            row.update(metric)
            rows.append(row)
    return rows


def _summary_by_variant(rows: pd.DataFrame) -> pd.DataFrame:
    """Summarize repeated metrics by source and variant."""

    metric_columns = [
        column
        for column in rows.columns
        if column
        not in {
            "seed",
            "source",
            "variant",
        }
        and pd.api.types.is_numeric_dtype(rows[column])
    ]
    summary_rows: list[dict[str, Any]] = []
    for (source, variant), group in rows.groupby(["source", "variant"], sort=True):
        row: dict[str, Any] = {
            "source": str(source),
            "variant": str(variant),
            "n_seeds": int(group["seed"].nunique()),
        }
        for metric in metric_columns:
            values = group[metric].to_numpy(dtype=float)
            if np.all(np.isnan(values)):
                continue
            row[f"{metric}_median"] = float(np.nanmedian(values))
            row[f"{metric}_min"] = float(np.nanmin(values))
            row[f"{metric}_max"] = float(np.nanmax(values))
        summary_rows.append(row)
    return pd.DataFrame(summary_rows)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run repeated upper-only subcontract diagnostics."
    )
    parser.add_argument("--family-hash", default=DEFAULT_UPPER_ONLY_HASH)
    parser.add_argument("--dataset-root", type=Path, default=_DEFAULT_DATASET_ROOT)
    parser.add_argument("--model-root", type=Path, default=_DEFAULT_MODEL_ROOT)
    parser.add_argument("--output-dir", type=Path, default=None)
    parser.add_argument("--first-seed", type=int, default=0)
    parser.add_argument("--n-seeds", type=int, default=5)
    parser.add_argument("--backend", default="extra_trees")
    parser.add_argument("--activation-threshold-kwh", type=float, default=25_000.0)
    parser.add_argument("--target-profile", default="mechanism_energy_intensive")
    parser.add_argument("--feature-preset", default="no_case_label")
    parser.add_argument("--target-transform-profile", default="mechanism_mass_identity")
    parser.add_argument("--split-strategy", default="group_shuffle")
    parser.add_argument("--stratify-column", default=None)
    parser.add_argument("--test-size", type=float, default=0.25)
    args = parser.parse_args()
    result = evaluate_repeated_upper_only_subcontracts(
        family_hash=args.family_hash,
        dataset_root=args.dataset_root,
        model_root=args.model_root,
        output_dir=args.output_dir,
        first_seed=int(args.first_seed),
        n_seeds=int(args.n_seeds),
        backend=args.backend,
        activation_threshold_kwh=float(args.activation_threshold_kwh),
        target_profile=args.target_profile,
        feature_preset=args.feature_preset,
        target_transform_profile=args.target_transform_profile,
        split_strategy=args.split_strategy,
        stratify_column=args.stratify_column,
        test_size=float(args.test_size),
    )
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
