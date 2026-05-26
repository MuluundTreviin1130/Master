from __future__ import annotations

"""Evaluate explicit upper-only rebound state contracts.

Upper-only rebound is no longer mainly a mass-learning problem. The latest
tau4/dur24 diagnostics show good family positive/negative masses, while daily
rebound still fails when shifted energy is falsely interpreted as recovery
rebound. This diagnostic therefore treats the problem as a state contract:

- decide whether a day is rebound-active,
- choose thresholds on train rows only,
- test global and regime-specific gates,
- combine those gates with explicit magnitude candidates.

The output is diagnostic only. It deliberately does not register a preferred
model, because the goal is to decide the next production contract.
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
from Learning.thermflex_hourly_mechanism.evaluate_upper_only_timing_contract import (
    _build_truth_timing_frame,
)
from Learning.thermflex_hourly_mechanism.evaluate_upper_only_trigger_contract import (
    _classifier_candidates,
    _select_threshold,
)


DEFAULT_OUTPUT_DIR = DEFAULT_MODEL_DIR / "diagnostics" / "upper_only_state_contract"


def evaluate_upper_only_state_contract(
    *,
    model_dir: Path = DEFAULT_MODEL_DIR,
    dataset_dir: Path = DEFAULT_DATASET_DIR,
    output_dir: Path | None = None,
    activation_threshold_kwh: float = 250_000.0,
) -> dict[str, Any]:
    """Evaluate global, seasonal, and score-based rebound-state gates."""

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
    daily = daily.merge(_build_truth_timing_frame(frame), on=["run_dir", "day"], how="inner", validate="one_to_one")
    if daily.empty:
        raise ValueError("[upper_only_state_contract] no daily rows available.")

    feature_frame = _feature_frame(daily)
    y = pd.to_numeric(daily["rebound_true_kwh"], errors="raise").to_numpy(dtype=float)
    y_active = (y > float(activation_threshold_kwh)).astype(int)
    train_mask = ~daily["is_test"].astype(bool).to_numpy()
    test_mask = daily["is_test"].astype(bool).to_numpy()

    magnitude_candidates = _magnitude_candidates(
        daily=daily,
        feature_frame=feature_frame,
        train_mask=train_mask,
        y=y,
        y_active=y_active,
    )
    gate_scores = _gate_scores(
        daily=daily,
        feature_frame=feature_frame,
        train_mask=train_mask,
        y_active=y_active,
    )
    metrics, predictions = _evaluate_gate_score_grid(
        daily=daily,
        y=y,
        y_active=y_active,
        train_mask=train_mask,
        test_mask=test_mask,
        gate_scores=gate_scores,
        magnitude_candidates=magnitude_candidates,
    )
    oracle = _oracle_rows(daily=daily, y=y, test_mask=test_mask, threshold=float(activation_threshold_kwh))

    metrics_csv = output_root / "state_contract_metrics.csv"
    predictions_csv = output_root / "state_contract_predictions.csv"
    daily_csv = output_root / "state_contract_daily_rows.csv"
    oracle_csv = output_root / "state_contract_oracle_metrics.csv"
    summary_json = output_root / "state_contract_summary.json"
    metrics.to_csv(metrics_csv, index=False)
    predictions.to_csv(predictions_csv, index=False)
    daily.to_csv(daily_csv, index=False)
    oracle.to_csv(oracle_csv, index=False)

    summary = {
        "model_dir": str(model_root),
        "dataset_dir": str(dataset_root),
        "activation_threshold_kwh": float(activation_threshold_kwh),
        "n_days": int(len(daily)),
        "n_test_days": int(test_mask.sum()),
        "metrics_csv": str(metrics_csv),
        "predictions_csv": str(predictions_csv),
        "daily_csv": str(daily_csv),
        "oracle_csv": str(oracle_csv),
        "best_by_test_rebound_r2": metrics.head(12).to_dict(orient="records"),
        "oracle_metrics": oracle.to_dict(orient="records"),
    }
    summary_json.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    return summary


def _feature_frame(daily: pd.DataFrame) -> pd.DataFrame:
    """Return numeric ex-ante and predicted-state features, no truth labels."""

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
    features = daily[[column for column in daily.columns if column not in excluded]].copy()
    return pd.get_dummies(features, columns=["season_regime"], dtype=float)


def _magnitude_candidates(
    *,
    daily: pd.DataFrame,
    feature_frame: pd.DataFrame,
    train_mask: np.ndarray,
    y: np.ndarray,
    y_active: np.ndarray,
) -> dict[str, np.ndarray]:
    """Build candidate rebound magnitudes for active-state gates."""

    candidates: dict[str, np.ndarray] = {
        "raw_rebound": np.maximum(pd.to_numeric(daily["raw_rebound_kwh"], errors="raise").to_numpy(float), 0.0),
        "mass_rebound": np.maximum(
            pd.to_numeric(daily["mass_corrected_rebound_kwh"], errors="raise").to_numpy(float),
            0.0,
        ),
        "raw_positive_after_trigger": np.maximum(
            pd.to_numeric(daily["raw_positive_after_first_negative_kwh"], errors="raise").to_numpy(float),
            0.0,
        ),
        "mass_positive_after_trigger": np.maximum(
            pd.to_numeric(daily["mass_corrected_positive_after_first_negative_kwh"], errors="raise").to_numpy(float),
            0.0,
        ),
    }
    active_train = train_mask & (y_active == 1)
    if int(active_train.sum()) < 4:
        raise ValueError("[upper_only_state_contract] not enough active train days for magnitude regressors.")
    regressor = ExtraTreesRegressor(n_estimators=700, min_samples_leaf=1, random_state=42, n_jobs=-1)
    regressor.fit(feature_frame.to_numpy(dtype=float)[active_train], y[active_train])
    candidates["active_regressor"] = np.maximum(regressor.predict(feature_frame.to_numpy(dtype=float)), 0.0)
    return candidates


def _gate_scores(
    *,
    daily: pd.DataFrame,
    feature_frame: pd.DataFrame,
    train_mask: np.ndarray,
    y_active: np.ndarray,
) -> dict[str, np.ndarray]:
    """Return gate scores where larger means more likely rebound-active."""

    x = feature_frame.to_numpy(dtype=float)
    scores: dict[str, np.ndarray] = {}
    for name, classifier in _classifier_candidates().items():
        classifier.fit(x[train_mask], y_active[train_mask])
        scores[f"classifier_{name}"] = classifier.predict_proba(x)[:, 1]

    # Score gates test whether the model's own sequence strength is already a
    # better state indicator than a learned classifier. Thresholds are still
    # selected only on train rows in `_evaluate_gate_score_grid`.
    score_columns = {
        "score_raw_rebound": "raw_rebound_kwh",
        "score_mass_rebound": "mass_corrected_rebound_kwh",
        "score_raw_pos_after_trigger": "raw_positive_after_first_negative_kwh",
        "score_mass_pos_after_trigger": "mass_corrected_positive_after_first_negative_kwh",
        "score_raw_neg_mass": "raw_negative_mass_kwh",
        "score_mass_neg_mass": "mass_corrected_negative_mass_kwh",
    }
    for score_name, column in score_columns.items():
        if column not in daily.columns:
            continue
        values = pd.to_numeric(daily[column], errors="raise").to_numpy(dtype=float)
        scores[score_name] = np.maximum(values, 0.0)
    return scores


def _evaluate_gate_score_grid(
    *,
    daily: pd.DataFrame,
    y: np.ndarray,
    y_active: np.ndarray,
    train_mask: np.ndarray,
    test_mask: np.ndarray,
    gate_scores: dict[str, np.ndarray],
    magnitude_candidates: dict[str, np.ndarray],
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Select train thresholds for every gate/magnitude pair."""

    metric_rows: list[dict[str, Any]] = []
    prediction_frames: list[pd.DataFrame] = []
    for gate_name, score in gate_scores.items():
        thresholds = _threshold_grid(score)
        for magnitude_name, magnitude in magnitude_candidates.items():
            threshold, train_r2 = _select_threshold(
                y_true=y[train_mask],
                magnitude=magnitude[train_mask],
                active_probability=score[train_mask],
                thresholds=thresholds,
            )
            active_pred = score >= float(threshold)
            rebound_pred = np.where(active_pred, magnitude, 0.0)
            metric_rows.append(
                {
                    "gate": str(gate_name),
                    "magnitude": str(magnitude_name),
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
                        "gate": str(gate_name),
                        "magnitude": str(magnitude_name),
                        "threshold": float(threshold),
                        "run_dir": daily["run_dir"].astype(str),
                        "day": daily["day"],
                        "season_regime": daily["season_regime"].astype(str),
                        "is_test": daily["is_test"].astype(bool),
                        "rebound_true_kwh": y,
                        "rebound_pred_kwh": rebound_pred,
                        "gate_score": score,
                        "active_pred": active_pred,
                        "truth_active": y_active.astype(bool),
                    }
                )
            )
            seasonal_thresholds, seasonal_active_pred, seasonal_train_r2 = _select_seasonal_thresholds(
                daily=daily,
                y=y,
                magnitude=magnitude,
                score=score,
                train_mask=train_mask,
                thresholds=thresholds,
            )
            seasonal_rebound_pred = np.where(seasonal_active_pred, magnitude, 0.0)
            metric_rows.append(
                {
                    "gate": f"seasonal_threshold_{gate_name}",
                    "magnitude": str(magnitude_name),
                    "threshold_selected_on_train": np.nan,
                    "thresholds_by_season": json.dumps(seasonal_thresholds, sort_keys=True),
                    "train_rebound_r2": float(seasonal_train_r2),
                    "test_rebound_r2": _safe_r2(y[test_mask], seasonal_rebound_pred[test_mask]),
                    "test_rebound_mae": float(mean_absolute_error(y[test_mask], seasonal_rebound_pred[test_mask])),
                    "test_active_accuracy": float(accuracy_score(y_active[test_mask], seasonal_active_pred[test_mask])),
                    "test_active_f1": float(
                        f1_score(y_active[test_mask], seasonal_active_pred[test_mask], zero_division=0)
                    ),
                    "test_active_count": int(seasonal_active_pred[test_mask].sum()),
                    "n_test_days": int(test_mask.sum()),
                }
            )
            prediction_frames.append(
                pd.DataFrame(
                    {
                        "gate": f"seasonal_threshold_{gate_name}",
                        "magnitude": str(magnitude_name),
                        "threshold": json.dumps(seasonal_thresholds, sort_keys=True),
                        "run_dir": daily["run_dir"].astype(str),
                        "day": daily["day"],
                        "season_regime": daily["season_regime"].astype(str),
                        "is_test": daily["is_test"].astype(bool),
                        "rebound_true_kwh": y,
                        "rebound_pred_kwh": seasonal_rebound_pred,
                        "gate_score": score,
                        "active_pred": seasonal_active_pred,
                        "truth_active": y_active.astype(bool),
                    }
                )
            )
    metrics = pd.DataFrame(metric_rows).sort_values("test_rebound_r2", ascending=False).reset_index(drop=True)
    predictions = pd.concat(prediction_frames, ignore_index=True)
    return metrics, predictions


def _select_seasonal_thresholds(
    *,
    daily: pd.DataFrame,
    y: np.ndarray,
    magnitude: np.ndarray,
    score: np.ndarray,
    train_mask: np.ndarray,
    thresholds: np.ndarray,
) -> tuple[dict[str, float], np.ndarray, float]:
    """Select one gate threshold per season on train rows only."""

    seasons = daily["season_regime"].astype(str).to_numpy()
    selected: dict[str, float] = {}
    active_pred = np.zeros(len(daily), dtype=bool)
    for season in sorted(set(seasons.tolist())):
        season_mask = seasons == season
        season_train = train_mask & season_mask
        if int(season_train.sum()) < 4:
            # Keep fail-fast behavior for missing whole data, but do not make a
            # sparse season unusable if the global threshold can still be
            # learned from all train rows.
            threshold, _score = _select_threshold(
                y_true=y[train_mask],
                magnitude=magnitude[train_mask],
                active_probability=score[train_mask],
                thresholds=thresholds,
            )
        else:
            threshold, _score = _select_threshold(
                y_true=y[season_train],
                magnitude=magnitude[season_train],
                active_probability=score[season_train],
                thresholds=thresholds,
            )
        selected[str(season)] = float(threshold)
        active_pred[season_mask] = score[season_mask] >= float(threshold)
    rebound_pred = np.where(active_pred, magnitude, 0.0)
    return selected, active_pred, _safe_r2(y[train_mask], rebound_pred[train_mask])


def _threshold_grid(score: np.ndarray) -> np.ndarray:
    """Return deterministic threshold candidates for probability or score gates."""

    values = np.asarray(score, dtype=float)
    finite = values[np.isfinite(values)]
    if finite.size == 0:
        raise ValueError("[upper_only_state_contract] gate score contains no finite values.")
    if float(finite.max()) <= 1.0 and float(finite.min()) >= 0.0:
        return np.round(np.arange(0.05, 0.951, 0.05), 2)
    quantiles = np.unique(np.quantile(finite, np.linspace(0.05, 0.95, 19)))
    return np.asarray(sorted(float(value) for value in quantiles), dtype=float)


def _oracle_rows(*, daily: pd.DataFrame, y: np.ndarray, test_mask: np.ndarray, threshold: float) -> pd.DataFrame:
    """Report ceilings for state and magnitude subproblems."""

    raw = np.maximum(pd.to_numeric(daily["raw_rebound_kwh"], errors="raise").to_numpy(float), 0.0)
    mass = np.maximum(pd.to_numeric(daily["mass_corrected_rebound_kwh"], errors="raise").to_numpy(float), 0.0)
    active = y > float(threshold)
    rows: list[dict[str, Any]] = []
    for variant, pred in {
        "raw_rebound": raw,
        "mass_rebound": mass,
        "oracle_zero_raw": np.where(active, raw, 0.0),
        "oracle_zero_mass": np.where(active, mass, 0.0),
        "oracle_active_magnitude": np.where(active, y, mass),
        "oracle_zero_and_active_magnitude": y,
    }.items():
        rows.append(
            {
                "variant": variant,
                "n_test_days": int(test_mask.sum()),
                "rebound_r2": _safe_r2(y[test_mask], pred[test_mask]),
                "rebound_mae": float(mean_absolute_error(y[test_mask], pred[test_mask])),
            }
        )
    return pd.DataFrame(rows)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model-dir", type=Path, default=DEFAULT_MODEL_DIR)
    parser.add_argument("--dataset-dir", type=Path, default=DEFAULT_DATASET_DIR)
    parser.add_argument("--output-dir", type=Path, default=None)
    parser.add_argument("--activation-threshold-kwh", type=float, default=250_000.0)
    args = parser.parse_args()
    summary = evaluate_upper_only_state_contract(
        model_dir=args.model_dir,
        dataset_dir=args.dataset_dir,
        output_dir=args.output_dir,
        activation_threshold_kwh=float(args.activation_threshold_kwh),
    )
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
