from __future__ import annotations

"""Evaluate cross-routed upper-only rebound contracts.

The upper-only tau4/dur24 diagnostics showed that no single hourly target
profile currently dominates all subproblems. Core-state models produce the
best rebound-active gate, while alternative target transforms can provide a
slightly better active-day magnitude. This diagnostic makes that contract
explicit and reproducible:

- build daily feature frames from each named model/dataset pair,
- train the active gate on one frame,
- train/select the magnitude signal on another frame,
- choose the gate threshold on train rows only,
- evaluate daily rebound R2 on the persisted grouped holdout.

It is intentionally diagnostic. A production router should later register the
chosen gate and magnitude sources explicitly instead of inferring them from
directory names.
"""

import argparse
import json
import sys
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from sklearn.metrics import accuracy_score, f1_score, mean_absolute_error

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from Learning.thermflex_hourly_mechanism.evaluate_upper_only_subcontracts import (
    _build_daily_frame,
    _build_family_day_frame,
    _evaluate_mass_contract,
    _load_all_predictions,
    _merge_daily_feature_frames,
    _safe_r2,
)
from Learning.thermflex_hourly_mechanism.evaluate_upper_only_trigger_contract import (
    _classifier_candidates,
    _feature_matrix,
    _magnitude_candidates,
    _select_threshold,
)


def evaluate_upper_only_cross_router_contract(
    *,
    model_specs: dict[str, tuple[Path, Path]],
    output_dir: Path,
    activation_threshold_kwh: float = 250_000.0,
    include_model_component_features: bool = True,
) -> dict[str, Any]:
    """Evaluate all gate-source / magnitude-source combinations."""

    if len(model_specs) < 2:
        raise ValueError("[upper_only_cross_router] at least two model specs are required.")
    output_root = Path(output_dir).resolve()
    output_root.mkdir(parents=True, exist_ok=True)

    daily_by_name = {
        str(name): _build_model_daily_frame(
            model_dir=Path(model_dir),
            dataset_dir=Path(dataset_dir),
            include_model_component_features=bool(include_model_component_features),
        )
        for name, (model_dir, dataset_dir) in model_specs.items()
    }
    reference_name = next(iter(daily_by_name))
    reference_daily = daily_by_name[reference_name].copy()
    y = pd.to_numeric(reference_daily["rebound_true_kwh"], errors="raise").to_numpy(dtype=float)
    y_active = (y > float(activation_threshold_kwh)).astype(int)
    train_mask = ~reference_daily["is_test"].astype(bool).to_numpy()
    test_mask = reference_daily["is_test"].astype(bool).to_numpy()

    for name, daily in daily_by_name.items():
        _validate_aligned_daily_frame(
            reference=reference_daily,
            candidate=daily,
            candidate_name=name,
        )

    gate_scores = _build_gate_scores(daily_by_name=daily_by_name, train_mask=train_mask, y_active=y_active)
    magnitudes = _build_magnitudes(
        daily_by_name=daily_by_name,
        train_mask=train_mask,
        y=y,
        y_active=y_active,
    )

    thresholds = np.round(np.arange(0.05, 0.951, 0.05), 2)
    rows: list[dict[str, Any]] = []
    prediction_frames: list[pd.DataFrame] = []
    for gate_name, probability in gate_scores.items():
        for magnitude_name, magnitude in magnitudes.items():
            threshold, train_r2 = _select_threshold(
                y_true=y[train_mask],
                magnitude=magnitude[train_mask],
                active_probability=probability[train_mask],
                thresholds=thresholds,
            )
            active_pred = probability >= float(threshold)
            rebound_pred = np.where(active_pred, magnitude, 0.0)
            rows.append(
                {
                    "gate": gate_name,
                    "magnitude": magnitude_name,
                    "threshold_selected_on_train": float(threshold),
                    "train_rebound_r2": float(train_r2),
                    "test_rebound_r2": _safe_r2(y[test_mask], rebound_pred[test_mask]),
                    "test_rebound_mae": float(mean_absolute_error(y[test_mask], rebound_pred[test_mask])),
                    "test_active_accuracy": float(accuracy_score(y_active[test_mask], active_pred[test_mask])),
                    "test_active_f1": float(f1_score(y_active[test_mask], active_pred[test_mask], zero_division=0)),
                    "test_active_count": int(active_pred[test_mask].sum()),
                    "n_test_days": int(test_mask.sum()),
                }
            )
            prediction_frames.append(
                pd.DataFrame(
                    {
                        "gate": gate_name,
                        "magnitude": magnitude_name,
                        "threshold": float(threshold),
                        "run_dir": reference_daily["run_dir"].astype(str),
                        "day": reference_daily["day"],
                        "is_test": reference_daily["is_test"].astype(bool),
                        "rebound_true_kwh": y,
                        "rebound_pred_kwh": rebound_pred,
                        "active_probability": probability,
                        "active_pred": active_pred,
                        "truth_active": y_active.astype(bool),
                    }
                )
            )

    metrics = pd.DataFrame(rows).sort_values("test_rebound_r2", ascending=False).reset_index(drop=True)
    predictions = pd.concat(prediction_frames, ignore_index=True)
    metrics_csv = output_root / "cross_router_metrics.csv"
    predictions_csv = output_root / "cross_router_predictions.csv"
    summary_json = output_root / "cross_router_summary.json"
    metrics.to_csv(metrics_csv, index=False)
    predictions.to_csv(predictions_csv, index=False)
    summary = {
        "model_specs": {
            name: {"model_dir": str(model_dir), "dataset_dir": str(dataset_dir)}
            for name, (model_dir, dataset_dir) in model_specs.items()
        },
        "activation_threshold_kwh": float(activation_threshold_kwh),
        "include_model_component_features": bool(include_model_component_features),
        "metrics_csv": str(metrics_csv),
        "predictions_csv": str(predictions_csv),
        "best_by_test_rebound_r2": metrics.head(12).to_dict(orient="records"),
    }
    summary_json.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    return summary


def _build_model_daily_frame(
    *,
    model_dir: Path,
    dataset_dir: Path,
    include_model_component_features: bool,
) -> pd.DataFrame:
    """Build one daily feature frame using the model's persisted split."""

    frame, split_payload = _load_all_predictions(model_dir=Path(model_dir), dataset_dir=Path(dataset_dir))
    test_groups = {str(value) for value in split_payload["test_groups"]}
    frame["is_test"] = frame["split_group_run"].astype(str).isin(test_groups)
    family_frame = _build_family_day_frame(frame)
    _mass_summary, _mass_daily, mass_scaled_frame = _evaluate_mass_contract(
        frame=frame,
        family_frame=family_frame,
        backend="extra_trees",
    )
    raw_daily = _build_daily_frame(
        frame=frame,
        delta_column="q_delta_pred_kwh",
        feature_prefix="raw",
        activation_threshold_kwh=25_000.0,
        include_model_component_features=include_model_component_features,
    )
    mass_daily = _build_daily_frame(
        frame=mass_scaled_frame,
        delta_column="q_delta_mass_corrected_kwh",
        feature_prefix="mass_corrected",
        activation_threshold_kwh=25_000.0,
        include_model_component_features=include_model_component_features,
    )
    return _merge_daily_feature_frames(raw_daily_frame=raw_daily, mass_corrected_daily_frame=mass_daily)


def _validate_aligned_daily_frame(
    *,
    reference: pd.DataFrame,
    candidate: pd.DataFrame,
    candidate_name: str,
) -> None:
    """Fail fast if candidate rows do not match the reference holdout rows."""

    key_columns = ["run_dir", "day", "is_test", "rebound_true_kwh"]
    ref = reference[key_columns].reset_index(drop=True).copy()
    cand = candidate[key_columns].reset_index(drop=True).copy()
    ref["day"] = pd.to_datetime(ref["day"], errors="raise")
    cand["day"] = pd.to_datetime(cand["day"], errors="raise")
    if len(ref) != len(cand) or not ref.equals(cand):
        raise ValueError(
            "[upper_only_cross_router] model daily frame is not aligned with reference: "
            f"{candidate_name}"
        )


def _build_gate_scores(
    *,
    daily_by_name: dict[str, pd.DataFrame],
    train_mask: np.ndarray,
    y_active: np.ndarray,
) -> dict[str, np.ndarray]:
    """Train candidate active gates for each source model."""

    scores: dict[str, np.ndarray] = {}
    for source_name, daily in daily_by_name.items():
        x = _feature_matrix(daily)
        for classifier_name, classifier in _classifier_candidates().items():
            classifier.fit(x[train_mask], y_active[train_mask])
            scores[f"{source_name}:{classifier_name}"] = classifier.predict_proba(x)[:, 1]
    return scores


def _build_magnitudes(
    *,
    daily_by_name: dict[str, pd.DataFrame],
    train_mask: np.ndarray,
    y: np.ndarray,
    y_active: np.ndarray,
) -> dict[str, np.ndarray]:
    """Build all candidate magnitude signals for each source model."""

    magnitudes: dict[str, np.ndarray] = {}
    for source_name, daily in daily_by_name.items():
        x = _feature_matrix(daily)
        candidates = _magnitude_candidates(x=x, daily=daily, train_mask=train_mask, y=y, y_active=y_active)
        for magnitude_name, values in candidates.items():
            magnitudes[f"{source_name}:{magnitude_name}"] = values
    return magnitudes


def _load_model_specs(path: Path) -> dict[str, tuple[Path, Path]]:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("[upper_only_cross_router] specs JSON must be an object.")
    specs: dict[str, tuple[Path, Path]] = {}
    for name, spec in payload.items():
        if not isinstance(spec, dict) or "model_dir" not in spec or "dataset_dir" not in spec:
            raise ValueError(f"[upper_only_cross_router] invalid spec for {name}.")
        specs[str(name)] = (Path(spec["model_dir"]), Path(spec["dataset_dir"]))
    return specs


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--specs-json", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--activation-threshold-kwh", type=float, default=250_000.0)
    parser.add_argument("--without-model-component-features", action="store_true")
    args = parser.parse_args()
    summary = evaluate_upper_only_cross_router_contract(
        model_specs=_load_model_specs(args.specs_json),
        output_dir=args.output_dir,
        activation_threshold_kwh=float(args.activation_threshold_kwh),
        include_model_component_features=not bool(args.without_model_component_features),
    )
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
