from __future__ import annotations

"""Evaluate daily cost/CO2 reconstruction from learned dispatch source flows.

This diagnostic is deliberately narrower than the generic repeated-holdout
runner. The current daily cost/CO2 blocker is not the accounting identity:
`dispatch_heat_operating_cost_eur_delta` is exactly the sum of its exported
cost components. The weak point is the learned source-stack response,
especially gas CHP. This module therefore evaluates:

- an oracle linear cost/CO2 map from true source-flow deltas,
- a direct learned source-flow surrogate followed by that same map,
- a two-stage CHP-regime surrogate followed by that same map,
- an oracle-regime upper bound for the two-stage CHP surrogate.
"""

import argparse
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from sklearn.ensemble import ExtraTreesClassifier, ExtraTreesRegressor
from sklearn.linear_model import Ridge
from sklearn.metrics import accuracy_score, balanced_accuracy_score, r2_score

from Learning.datasets.load_dataset import load_dataset
from Learning.thermflex_daily_results.dataset_builder import _DEFAULT_DATASET_ROOT
from Learning.thermflex_daily_results.evaluate_repeated_holdouts import _fit_predict_targets
from Learning.thermflex_daily_results.train import _apply_target_transform, _invert_target_transform
from Learning.thermflex_daily_results.validate import build_grouped_holdout_split

_DEFAULT_MODEL_ROOT = Path(__file__).resolve().parents[2] / "Learning" / "models"

_FLOW_TARGETS = (
    "district_gas_chp_thermal_generation_kwh_delta",
    "district_gas_chp_electric_generation_kwh_delta",
    "district_gas_boiler_generation_kwh_delta",
    "district_heat_pump_generation_kwh_delta",
    "district_external_heat_generation_kwh_delta",
    "district_waste_incineration_generation_kwh_delta",
)
_CHP_REGIME_FLOW_TARGETS = {
    "district_gas_chp_thermal_generation_kwh_delta",
    "district_gas_chp_electric_generation_kwh_delta",
}
_RECONSTRUCTED_TARGETS = (
    "dispatch_heat_operating_cost_eur_delta",
    "co2_emissions_total_t_delta",
)


@dataclass(frozen=True)
class FlowReconstructionResult:
    diagnostic_dir: Path
    metrics_csv: Path
    summary_csv: Path
    summary_json: Path
    config_json: Path


def evaluate_flow_reconstruction(
    *,
    family_hash: str,
    dataset_root: Path = _DEFAULT_DATASET_ROOT,
    model_root: Path = _DEFAULT_MODEL_ROOT,
    group_column: str = "split_group_date",
    test_size: float = 0.25,
    first_seed: int = 0,
    n_seeds: int = 5,
    chp_regime_mode: str = "threshold3",
    chp_regime_threshold_kwh: float = 250_000.0,
    chp_regime_strong_threshold_kwh: float = 1_250_000.0,
    output_name: str | None = None,
) -> FlowReconstructionResult:
    """Run grouped holdouts for source-flow-based daily cost/CO2 reconstruction."""

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
    if group_column not in truth_df.columns:
        raise KeyError(f"[thermflex_daily_results] group column not found in truth table: {group_column}")

    x = np.asarray(dataset_bundle["X"], dtype=float)
    all_target_names = list(dataset_bundle["meta"]["target_columns"])
    _require_targets(all_target_names, (*_FLOW_TARGETS, *_RECONSTRUCTED_TARGETS))
    y_all = np.asarray(dataset_bundle["Y"], dtype=float)
    flow_indices = [all_target_names.index(target) for target in _FLOW_TARGETS]
    final_indices = [all_target_names.index(target) for target in _RECONSTRUCTED_TARGETS]
    y_flow = y_all[:, flow_indices]
    y_final = y_all[:, final_indices]

    chp_thermal = y_flow[:, _FLOW_TARGETS.index("district_gas_chp_thermal_generation_kwh_delta")]
    chp_regime_labels = _chp_regime_labels(
        chp_thermal_delta=chp_thermal,
        mode=chp_regime_mode,
        threshold_kwh=chp_regime_threshold_kwh,
        strong_threshold_kwh=chp_regime_strong_threshold_kwh,
    )

    metric_rows: list[dict[str, Any]] = []
    classification_rows: list[dict[str, Any]] = []
    for seed in range(int(first_seed), int(first_seed) + int(n_seeds)):
        split = build_grouped_holdout_split(
            truth_df=truth_df,
            group_column=group_column,
            test_size=test_size,
            random_state=seed,
        )
        train_index = split.train_index
        test_index = split.test_index

        # This map is trained only on training rows. When it receives true test
        # flows, it measures whether source-flow accounting is sufficient. When
        # it receives predicted flows, it measures the actual surrogate chain.
        flow_to_kpi = Ridge(alpha=1.0)
        flow_to_kpi.fit(y_flow[train_index], y_final[train_index])
        oracle_from_true_flows = flow_to_kpi.predict(y_flow[test_index])

        direct_predicted_flows = _fit_predict_targets(
            x_train=x[train_index],
            x_test=x[test_index],
            y_train=y_flow[train_index],
            target_names=list(_FLOW_TARGETS),
            random_state=seed,
            estimator="extra_trees_smooth",
        )
        direct_reconstruction = flow_to_kpi.predict(direct_predicted_flows)

        classifier = _fit_chp_regime_classifier(
            x_train=x[train_index],
            labels_train=chp_regime_labels[train_index],
            random_state=seed,
        )
        predicted_regime_labels = classifier.predict(x[test_index])
        classification_rows.append(
            {
                "seed": int(seed),
                "accuracy": float(accuracy_score(chp_regime_labels[test_index], predicted_regime_labels)),
                "balanced_accuracy": float(
                    balanced_accuracy_score(chp_regime_labels[test_index], predicted_regime_labels)
                ),
            }
        )

        regime_predicted_flows = direct_predicted_flows.copy()
        oracle_regime_predicted_flows = direct_predicted_flows.copy()
        for flow_idx, target_name in enumerate(_FLOW_TARGETS):
            if target_name not in _CHP_REGIME_FLOW_TARGETS:
                continue
            regime_predicted_flows[:, flow_idx] = _predict_by_chp_regime(
                x_train=x[train_index],
                x_test=x[test_index],
                y_train=y_flow[train_index, flow_idx],
                labels_train=chp_regime_labels[train_index],
                labels_for_test_rows=predicted_regime_labels,
                random_state=seed + flow_idx,
            )
            oracle_regime_predicted_flows[:, flow_idx] = _predict_by_chp_regime(
                x_train=x[train_index],
                x_test=x[test_index],
                y_train=y_flow[train_index, flow_idx],
                labels_train=chp_regime_labels[train_index],
                labels_for_test_rows=chp_regime_labels[test_index],
                random_state=seed + flow_idx,
            )
        regime_reconstruction = flow_to_kpi.predict(regime_predicted_flows)
        oracle_regime_reconstruction = flow_to_kpi.predict(oracle_regime_predicted_flows)

        _append_reconstruction_metrics(
            rows=metric_rows,
            seed=seed,
            y_true=y_final[test_index],
            predictions_by_method={
                "oracle_true_flows_linear_recon": oracle_from_true_flows,
                "direct_flow_recon": direct_reconstruction,
                "regime_chp_flow_recon": regime_reconstruction,
                "oracle_regime_chp_flow_recon": oracle_regime_reconstruction,
            },
        )

    metrics_df = pd.DataFrame(metric_rows)
    classification_df = pd.DataFrame(classification_rows)
    summary_df = _summarize(metrics_df)
    diagnostic_dir = _diagnostic_dir(
        model_root=Path(model_root),
        family_hash=family_hash,
        output_name=output_name,
    )
    diagnostic_dir.mkdir(parents=True, exist_ok=True)
    metrics_csv = diagnostic_dir / "flow_reconstruction_metrics.csv"
    summary_csv = diagnostic_dir / "flow_reconstruction_summary.csv"
    summary_json = diagnostic_dir / "flow_reconstruction_summary.json"
    config_json = diagnostic_dir / "flow_reconstruction_config.json"
    classification_csv = diagnostic_dir / "chp_regime_classification_metrics.csv"

    metrics_df.to_csv(metrics_csv, index=False)
    summary_df.to_csv(summary_csv, index=False)
    classification_df.to_csv(classification_csv, index=False)
    payload = {
        "family_hash": family_hash,
        "group_column": group_column,
        "test_size": float(test_size),
        "first_seed": int(first_seed),
        "n_seeds": int(n_seeds),
        "chp_regime_mode": chp_regime_mode,
        "chp_regime_threshold_kwh": float(chp_regime_threshold_kwh),
        "chp_regime_strong_threshold_kwh": float(chp_regime_strong_threshold_kwh),
        "flow_targets": list(_FLOW_TARGETS),
        "reconstructed_targets": list(_RECONSTRUCTED_TARGETS),
        "n_rows": int(len(truth_df)),
        "n_groups": int(truth_df[group_column].astype(str).nunique()),
        "chp_regime_counts": {
            str(key): int(value)
            for key, value in pd.Series(chp_regime_labels).value_counts().sort_index().items()
        },
        "classification_summary": classification_df.agg(["mean", "median", "min", "max"]).to_dict(),
        "summary": summary_df.to_dict(orient="records"),
    }
    summary_json.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    config_json.write_text(
        json.dumps({key: value for key, value in payload.items() if key != "summary"}, indent=2),
        encoding="utf-8",
    )
    return FlowReconstructionResult(
        diagnostic_dir=diagnostic_dir,
        metrics_csv=metrics_csv,
        summary_csv=summary_csv,
        summary_json=summary_json,
        config_json=config_json,
    )


def _require_targets(all_target_names: list[str], required_targets: tuple[str, ...]) -> None:
    missing = sorted(set(required_targets).difference(all_target_names))
    if missing:
        raise KeyError("[thermflex_daily_results] flow reconstruction missing targets: " + ", ".join(missing))


def _chp_regime_labels(
    *,
    chp_thermal_delta: np.ndarray,
    mode: str,
    threshold_kwh: float,
    strong_threshold_kwh: float,
) -> np.ndarray:
    values = np.asarray(chp_thermal_delta, dtype=float)
    threshold = float(threshold_kwh)
    if threshold <= 0.0:
        raise ValueError("[thermflex_daily_results] CHP regime threshold must be positive.")
    normalized_mode = str(mode).strip().lower()
    if normalized_mode == "threshold3":
        return np.where(values > threshold, "up", np.where(values < -threshold, "down", "neutral"))
    if normalized_mode == "threshold5":
        strong_threshold = float(strong_threshold_kwh)
        if strong_threshold <= threshold:
            raise ValueError(
                "[thermflex_daily_results] CHP strong-regime threshold must be larger than the base threshold."
            )
        return np.select(
            [
                values < -strong_threshold,
                values < -threshold,
                values > strong_threshold,
                values > threshold,
            ],
            ["strong_down", "down", "strong_up", "up"],
            default="neutral",
        )
    if normalized_mode == "sign3":
        return np.where(values > 0.0, "up", np.where(values < 0.0, "down", "neutral"))
    raise ValueError(
        "[thermflex_daily_results] unsupported CHP regime mode "
        f"'{mode}'. Expected one of: threshold3, threshold5, sign3."
    )


def _fit_chp_regime_classifier(
    *,
    x_train: np.ndarray,
    labels_train: np.ndarray,
    random_state: int,
) -> ExtraTreesClassifier:
    classifier = ExtraTreesClassifier(
        n_estimators=700,
        max_features=0.85,
        min_samples_leaf=1,
        random_state=random_state,
        n_jobs=1,
    )
    classifier.fit(x_train, labels_train)
    return classifier


def _predict_by_chp_regime(
    *,
    x_train: np.ndarray,
    x_test: np.ndarray,
    y_train: np.ndarray,
    labels_train: np.ndarray,
    labels_for_test_rows: np.ndarray,
    random_state: int,
) -> np.ndarray:
    """Fit one regression model per CHP regime and predict with supplied labels."""

    prediction = np.zeros(x_test.shape[0], dtype=float)
    fallback_model = _fit_flow_regressor(x_train=x_train, y_train=y_train, random_state=random_state)
    labels = sorted(str(value) for value in np.unique(np.concatenate([labels_train, labels_for_test_rows])))
    for offset, label in enumerate(labels):
        train_mask = labels_train == label
        if int(np.sum(train_mask)) < 8:
            model = fallback_model
        else:
            model = _fit_flow_regressor(
                x_train=x_train[train_mask],
                y_train=y_train[train_mask],
                random_state=random_state + offset + 17,
            )
        test_mask = labels_for_test_rows == label
        if np.any(test_mask):
            transformed = model.predict(x_test[test_mask])
            prediction[test_mask] = _invert_target_transform(transformed, "signed_log1p")
    return prediction


def _fit_flow_regressor(*, x_train: np.ndarray, y_train: np.ndarray, random_state: int) -> ExtraTreesRegressor:
    model = ExtraTreesRegressor(
        n_estimators=900,
        max_features=0.75,
        min_samples_leaf=2,
        bootstrap=False,
        random_state=random_state,
        n_jobs=1,
    )
    model.fit(x_train, _apply_target_transform(y_train, "signed_log1p"))
    return model


def _append_reconstruction_metrics(
    *,
    rows: list[dict[str, Any]],
    seed: int,
    y_true: np.ndarray,
    predictions_by_method: dict[str, np.ndarray],
) -> None:
    for method, y_pred in predictions_by_method.items():
        for target_idx, target_name in enumerate(_RECONSTRUCTED_TARGETS):
            rows.append(
                {
                    "seed": int(seed),
                    "method": method,
                    "target": target_name,
                    "r2": float(r2_score(y_true[:, target_idx], y_pred[:, target_idx])),
                }
            )


def _summarize(metrics_df: pd.DataFrame) -> pd.DataFrame:
    return (
        metrics_df.groupby(["method", "target"], sort=True)["r2"]
        .agg(n_seeds="count", r2_mean="mean", r2_median="median", r2_min="min", r2_max="max")
        .reset_index()
    )


def _diagnostic_dir(*, model_root: Path, family_hash: str, output_name: str | None) -> Path:
    suffix = output_name if output_name else f"flow_reconstruction_{family_hash[:12]}"
    return Path(model_root).resolve() / f"thermflex_daily_results_{suffix}"


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--family-hash", required=True)
    parser.add_argument("--dataset-root", type=Path, default=_DEFAULT_DATASET_ROOT)
    parser.add_argument("--model-root", type=Path, default=_DEFAULT_MODEL_ROOT)
    parser.add_argument("--group-column", default="split_group_date")
    parser.add_argument("--test-size", type=float, default=0.25)
    parser.add_argument("--first-seed", type=int, default=0)
    parser.add_argument("--n-seeds", type=int, default=5)
    parser.add_argument(
        "--chp-regime-mode",
        choices=("threshold3", "threshold5", "sign3"),
        default="threshold3",
    )
    parser.add_argument("--chp-regime-threshold-kwh", type=float, default=250_000.0)
    parser.add_argument("--chp-regime-strong-threshold-kwh", type=float, default=1_250_000.0)
    parser.add_argument("--output-name", default=None)
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    result = evaluate_flow_reconstruction(
        family_hash=args.family_hash,
        dataset_root=args.dataset_root,
        model_root=args.model_root,
        group_column=args.group_column,
        test_size=args.test_size,
        first_seed=args.first_seed,
        n_seeds=args.n_seeds,
        chp_regime_mode=args.chp_regime_mode,
        chp_regime_threshold_kwh=args.chp_regime_threshold_kwh,
        chp_regime_strong_threshold_kwh=args.chp_regime_strong_threshold_kwh,
        output_name=args.output_name,
    )
    print(json.dumps({key: str(value) for key, value in result.__dict__.items()}, indent=2))


if __name__ == "__main__":
    main()
