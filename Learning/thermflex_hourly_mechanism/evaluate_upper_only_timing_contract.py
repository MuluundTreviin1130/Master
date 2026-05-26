from __future__ import annotations

"""Evaluate explicit upper-only rebound timing contracts.

The previous gate diagnostic showed that Upper-only rebound is limited by
false activation on days with no useful negative trigger. This script therefore
uses a timing label instead of a KPI label:

- true first negative hour exists,
- the first negative hour is not too late,
- positive mass after that trigger is large enough to count as rebound.

The timing gate is still evaluated on the KPI that matters: daily rebound R2 on
the persisted grouped holdout. Thresholds are selected on train rows only.
"""

import argparse
import json
import sys
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from sklearn.ensemble import ExtraTreesRegressor
from sklearn.metrics import accuracy_score, f1_score, mean_absolute_error

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from Learning.thermflex_hourly_mechanism.diagnose_upper_only_sequence_failure import _sequence_stats
from Learning.thermflex_hourly_mechanism.evaluate_upper_only_subcontracts import (
    DEFAULT_DATASET_DIR,
    DEFAULT_MODEL_DIR,
    _build_daily_frame,
    _build_family_day_frame,
    _evaluate_mass_contract,
    _load_all_predictions,
    _merge_daily_feature_frames,
    _safe_r2,
)
from Learning.thermflex_hourly_mechanism.evaluate_upper_only_trigger_contract import (
    _classifier_candidates,
    _select_threshold,
)


DEFAULT_OUTPUT_DIR = DEFAULT_MODEL_DIR / "diagnostics" / "upper_only_timing_contract"


def evaluate_upper_only_timing_contract(
    *,
    model_dir: Path = DEFAULT_MODEL_DIR,
    dataset_dir: Path = DEFAULT_DATASET_DIR,
    output_dir: Path | None = None,
    activation_threshold_kwh: float = 250_000.0,
    late_trigger_hour: int = 18,
) -> dict[str, Any]:
    """Evaluate explicit true-timing labels on one persisted grouped split."""

    model_root = Path(model_dir).resolve()
    dataset_root = Path(dataset_dir).resolve()
    output_root = Path(output_dir).resolve() if output_dir is not None else DEFAULT_OUTPUT_DIR.resolve()
    output_root.mkdir(parents=True, exist_ok=True)

    frame, split_payload = _load_all_predictions(model_dir=model_root, dataset_dir=dataset_root)
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
    )
    mass_daily = _build_daily_frame(
        frame=mass_scaled_frame,
        delta_column="q_delta_mass_corrected_kwh",
        feature_prefix="mass_corrected",
        activation_threshold_kwh=25_000.0,
    )
    daily = _merge_daily_feature_frames(raw_daily_frame=raw_daily, mass_corrected_daily_frame=mass_daily)
    daily = daily.merge(
        _build_truth_timing_frame(frame),
        on=["run_dir", "day"],
        how="inner",
        validate="one_to_one",
    )
    if len(daily) == 0:
        raise ValueError("[upper_only_timing_contract] daily timing frame is empty.")

    metrics, predictions = _evaluate_timing_variants(
        daily=daily,
        activation_threshold_kwh=float(activation_threshold_kwh),
        late_trigger_hour=int(late_trigger_hour),
    )
    metrics_csv = output_root / "timing_contract_metrics.csv"
    predictions_csv = output_root / "timing_contract_predictions.csv"
    summary_json = output_root / "timing_contract_summary.json"
    metrics.to_csv(metrics_csv, index=False)
    predictions.to_csv(predictions_csv, index=False)

    summary = {
        "model_dir": str(model_root),
        "dataset_dir": str(dataset_root),
        "activation_threshold_kwh": float(activation_threshold_kwh),
        "late_trigger_hour": int(late_trigger_hour),
        "n_days": int(len(daily)),
        "n_test_days": int(daily["is_test"].astype(bool).sum()),
        "metrics_csv": str(metrics_csv),
        "predictions_csv": str(predictions_csv),
        "best_by_test_rebound_r2": metrics.head(10).to_dict(orient="records"),
    }
    summary_json.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    return summary


def _build_truth_timing_frame(frame: pd.DataFrame) -> pd.DataFrame:
    """Aggregate true daily sign-run timing labels without using predictions."""

    rows: list[dict[str, Any]] = []
    for (run_dir, day), group in frame.groupby(["run_dir", "day"], sort=True):
        q_ref = group.groupby("timestamp")["cohort_q_heat_ref_kwh"].sum().sort_index()
        q_true = group.groupby("timestamp")["cohort_q_heat_kwh"].sum().sort_index()
        diff = q_true.to_numpy(dtype=float) - q_ref.to_numpy(dtype=float)
        stats = _sequence_stats(diff, activation_threshold_kwh=25_000.0)
        rows.append(
            {
                "run_dir": str(run_dir),
                "day": pd.Timestamp(day),
                **{f"true_{key}": value for key, value in stats.items()},
            }
        )
    return pd.DataFrame(rows)


def _evaluate_timing_variants(
    *,
    daily: pd.DataFrame,
    activation_threshold_kwh: float,
    late_trigger_hour: int,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Compare learned timing gates and simple timing rules."""

    y_rebound = pd.to_numeric(daily["rebound_true_kwh"], errors="raise").to_numpy(dtype=float)
    y_timing_active = _truth_timing_active(
        daily=daily,
        activation_threshold_kwh=float(activation_threshold_kwh),
        late_trigger_hour=int(late_trigger_hour),
    )
    train_mask = ~daily["is_test"].astype(bool).to_numpy()
    test_mask = daily["is_test"].astype(bool).to_numpy()

    features = _feature_matrix(daily)
    magnitude_candidates = _magnitude_candidates(
        features=features,
        daily=daily,
        train_mask=train_mask,
        y_rebound=y_rebound,
        y_timing_active=y_timing_active,
    )
    metric_rows: list[dict[str, Any]] = []
    prediction_rows: list[pd.DataFrame] = []

    thresholds = np.round(np.arange(0.05, 0.951, 0.05), 2)
    for gate_name, probability in _learned_gate_probabilities(
        features=features,
        y_timing_active=y_timing_active,
        train_mask=train_mask,
    ).items():
        _append_gate_results(
            metric_rows=metric_rows,
            prediction_rows=prediction_rows,
            daily=daily,
            gate_name=gate_name,
            active_probability=probability,
            thresholds=thresholds,
            magnitude_candidates=magnitude_candidates,
            y_rebound=y_rebound,
            y_timing_active=y_timing_active,
            train_mask=train_mask,
            test_mask=test_mask,
        )

    for rule_name, probability in _timing_rule_probabilities(daily).items():
        _append_gate_results(
            metric_rows=metric_rows,
            prediction_rows=prediction_rows,
            daily=daily,
            gate_name=rule_name,
            active_probability=probability,
            thresholds=np.array([0.5]),
            magnitude_candidates=magnitude_candidates,
            y_rebound=y_rebound,
            y_timing_active=y_timing_active,
            train_mask=train_mask,
            test_mask=test_mask,
        )

    metrics = pd.DataFrame(metric_rows).sort_values("test_rebound_r2", ascending=False).reset_index(drop=True)
    predictions = pd.concat(prediction_rows, ignore_index=True)
    return metrics, predictions


def _truth_timing_active(
    *,
    daily: pd.DataFrame,
    activation_threshold_kwh: float,
    late_trigger_hour: int,
) -> np.ndarray:
    """Label days whose true sequence has a usable early negative trigger."""

    first_negative = pd.to_numeric(daily["true_first_negative_hour"], errors="raise").to_numpy(dtype=float)
    pos_after = pd.to_numeric(
        daily["true_positive_after_first_negative_kwh"],
        errors="raise",
    ).to_numpy(dtype=float)
    return (
        (first_negative >= 0.0)
        & (first_negative <= float(late_trigger_hour))
        & (pos_after >= float(activation_threshold_kwh))
    ).astype(int)


def _feature_matrix(daily: pd.DataFrame) -> np.ndarray:
    """Return candidate timing features without true timing or KPI labels."""

    excluded = {
        "run_dir",
        "day",
        "split_group_run",
        "is_test",
        "shifted_true_kwh",
        "rebound_true_kwh",
        "peak_true_kw",
        "truth_rebound_active",
        "failure_mode",
    }
    excluded.update(column for column in daily.columns if column.startswith("true_"))
    features = pd.get_dummies(
        daily[[column for column in daily.columns if column not in excluded]],
        columns=["season_regime"],
        dtype=float,
    )
    return features.to_numpy(dtype=float)


def _magnitude_candidates(
    *,
    features: np.ndarray,
    daily: pd.DataFrame,
    train_mask: np.ndarray,
    y_rebound: np.ndarray,
    y_timing_active: np.ndarray,
) -> dict[str, np.ndarray]:
    """Build rebound magnitudes to combine with timing gates."""

    candidates: dict[str, np.ndarray] = {
        "raw_positive_after_trigger": np.maximum(
            pd.to_numeric(daily["raw_positive_after_first_negative_kwh"], errors="raise").to_numpy(float),
            0.0,
        ),
        "mass_positive_after_trigger": np.maximum(
            pd.to_numeric(
                daily["mass_corrected_positive_after_first_negative_kwh"],
                errors="raise",
            ).to_numpy(float),
            0.0,
        ),
        "raw_rebound": np.maximum(pd.to_numeric(daily["raw_rebound_kwh"], errors="raise").to_numpy(float), 0.0),
        "mass_rebound": np.maximum(
            pd.to_numeric(daily["mass_corrected_rebound_kwh"], errors="raise").to_numpy(float),
            0.0,
        ),
    }
    active_train = train_mask & (y_timing_active == 1)
    if int(active_train.sum()) < 4:
        raise ValueError("[upper_only_timing_contract] not enough active timing rows for magnitude regressor.")
    regressor = ExtraTreesRegressor(n_estimators=700, min_samples_leaf=1, random_state=42, n_jobs=-1)
    regressor.fit(features[active_train], y_rebound[active_train])
    candidates["active_timing_regressor"] = np.maximum(regressor.predict(features), 0.0)
    return candidates


def _learned_gate_probabilities(
    *,
    features: np.ndarray,
    y_timing_active: np.ndarray,
    train_mask: np.ndarray,
) -> dict[str, np.ndarray]:
    """Fit candidate classifiers for the timing-active label."""

    probabilities: dict[str, np.ndarray] = {}
    for name, classifier in _classifier_candidates().items():
        classifier.fit(features[train_mask], y_timing_active[train_mask])
        probabilities[f"timing_label_{name}"] = classifier.predict_proba(features)[:, 1]
    return probabilities


def _timing_rule_probabilities(daily: pd.DataFrame) -> dict[str, np.ndarray]:
    """Convert simple predicted-sequence trigger rules into 0/1 probabilities."""

    raw_first = pd.to_numeric(daily["raw_first_negative_hour"], errors="raise").to_numpy(dtype=float)
    mass_first = pd.to_numeric(daily["mass_corrected_first_negative_hour"], errors="raise").to_numpy(dtype=float)
    raw_pos_after = pd.to_numeric(
        daily["raw_positive_after_first_negative_kwh"],
        errors="raise",
    ).to_numpy(dtype=float)
    mass_pos_after = pd.to_numeric(
        daily["mass_corrected_positive_after_first_negative_kwh"],
        errors="raise",
    ).to_numpy(dtype=float)
    return {
        "raw_predicted_early_trigger": ((raw_first >= 0.0) & (raw_first <= 18.0) & (raw_pos_after > 0.0)).astype(float),
        "mass_predicted_early_trigger": (
            (mass_first >= 0.0) & (mass_first <= 18.0) & (mass_pos_after > 0.0)
        ).astype(float),
        "raw_predicted_strong_trigger": (
            (raw_first >= 0.0) & (raw_first <= 18.0) & (raw_pos_after >= 250_000.0)
        ).astype(float),
        "mass_predicted_strong_trigger": (
            (mass_first >= 0.0) & (mass_first <= 18.0) & (mass_pos_after >= 250_000.0)
        ).astype(float),
    }


def _append_gate_results(
    *,
    metric_rows: list[dict[str, Any]],
    prediction_rows: list[pd.DataFrame],
    daily: pd.DataFrame,
    gate_name: str,
    active_probability: np.ndarray,
    thresholds: np.ndarray,
    magnitude_candidates: dict[str, np.ndarray],
    y_rebound: np.ndarray,
    y_timing_active: np.ndarray,
    train_mask: np.ndarray,
    test_mask: np.ndarray,
) -> None:
    """Select train threshold and append KPI rows for one gate."""

    for magnitude_name, magnitude in magnitude_candidates.items():
        threshold, train_r2 = _select_threshold(
            y_true=y_rebound[train_mask],
            magnitude=magnitude[train_mask],
            active_probability=active_probability[train_mask],
            thresholds=thresholds,
        )
        active_pred = active_probability >= float(threshold)
        rebound_pred = np.where(active_pred, magnitude, 0.0)
        metric_rows.append(
            {
                "gate": str(gate_name),
                "magnitude": str(magnitude_name),
                "threshold_selected_on_train": float(threshold),
                "train_rebound_r2": float(train_r2),
                "test_rebound_r2": _safe_r2(y_rebound[test_mask], rebound_pred[test_mask]),
                "test_rebound_mae": float(mean_absolute_error(y_rebound[test_mask], rebound_pred[test_mask])),
                "test_timing_accuracy": float(accuracy_score(y_timing_active[test_mask], active_pred[test_mask])),
                "test_timing_f1": float(f1_score(y_timing_active[test_mask], active_pred[test_mask], zero_division=0)),
                "test_active_count": int(active_pred[test_mask].sum()),
                "n_test_days": int(test_mask.sum()),
            }
        )
        prediction_rows.append(
            pd.DataFrame(
                {
                    "gate": str(gate_name),
                    "magnitude": str(magnitude_name),
                    "threshold": float(threshold),
                    "run_dir": daily["run_dir"].astype(str),
                    "day": daily["day"],
                    "is_test": daily["is_test"].astype(bool),
                    "rebound_true_kwh": y_rebound,
                    "rebound_pred_kwh": rebound_pred,
                    "timing_active_probability": active_probability,
                    "timing_active_pred": active_pred,
                    "truth_timing_active": y_timing_active.astype(bool),
                    "true_first_negative_hour": daily["true_first_negative_hour"],
                    "raw_first_negative_hour": daily["raw_first_negative_hour"],
                    "mass_corrected_first_negative_hour": daily["mass_corrected_first_negative_hour"],
                }
            )
        )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model-dir", type=Path, default=DEFAULT_MODEL_DIR)
    parser.add_argument("--dataset-dir", type=Path, default=DEFAULT_DATASET_DIR)
    parser.add_argument("--output-dir", type=Path, default=None)
    parser.add_argument("--activation-threshold-kwh", type=float, default=250_000.0)
    parser.add_argument("--late-trigger-hour", type=int, default=18)
    args = parser.parse_args()
    summary = evaluate_upper_only_timing_contract(
        model_dir=args.model_dir,
        dataset_dir=args.dataset_dir,
        output_dir=args.output_dir,
        activation_threshold_kwh=float(args.activation_threshold_kwh),
        late_trigger_hour=int(args.late_trigger_hour),
    )
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
