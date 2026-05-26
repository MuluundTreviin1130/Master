from __future__ import annotations

"""Evaluate explicit upper-only zero/late-trigger rebound contracts.

The full upper-only truth coverage showed that additional generic truth is no
longer the main bottleneck. Rebound errors are dominated by zero/low-rebound
days that are falsely activated. This diagnostic therefore isolates the
classification contract:

- learn whether a day should have relevant rebound at all,
- choose the rebound gate threshold on train data only,
- combine the gate with candidate magnitude signals,
- report holdout KPI quality and oracle ceilings.

It deliberately stays diagnostic. No model is registered as preferred here.
"""

import argparse
import json
import sys
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from sklearn.ensemble import ExtraTreesClassifier, ExtraTreesRegressor, HistGradientBoostingClassifier
from sklearn.ensemble import RandomForestClassifier, RandomForestRegressor
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, f1_score, mean_absolute_error, r2_score
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler
from xgboost import XGBRegressor

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


DEFAULT_OUTPUT_DIR = DEFAULT_MODEL_DIR / "diagnostics" / "upper_only_trigger_contract"


def evaluate_upper_only_trigger_contract(
    *,
    model_dir: Path = DEFAULT_MODEL_DIR,
    dataset_dir: Path = DEFAULT_DATASET_DIR,
    output_dir: Path | None = None,
    activation_threshold_kwh: float = 250_000.0,
    include_model_component_features: bool = False,
    include_exante_profile_features: bool = False,
) -> dict[str, Any]:
    """Evaluate zero-/low-rebound gates on one persisted grouped holdout."""

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
        include_model_component_features=include_model_component_features,
        include_exante_profile_features=include_exante_profile_features,
    )
    mass_daily = _build_daily_frame(
        frame=mass_scaled_frame,
        delta_column="q_delta_mass_corrected_kwh",
        feature_prefix="mass_corrected",
        activation_threshold_kwh=25_000.0,
        include_model_component_features=include_model_component_features,
        include_exante_profile_features=include_exante_profile_features,
    )
    daily = _merge_daily_feature_frames(raw_daily_frame=raw_daily, mass_corrected_daily_frame=mass_daily)
    daily["truth_rebound_active_250k"] = pd.to_numeric(
        daily["rebound_true_kwh"], errors="raise"
    ) > float(activation_threshold_kwh)

    metrics, predictions = _evaluate_trigger_variants(
        daily=daily,
        activation_threshold_kwh=float(activation_threshold_kwh),
    )
    oracle = _oracle_rows(daily=daily, activation_threshold_kwh=float(activation_threshold_kwh))

    metrics_csv = output_root / "trigger_contract_metrics.csv"
    predictions_csv = output_root / "trigger_contract_predictions.csv"
    oracle_csv = output_root / "trigger_contract_oracle_metrics.csv"
    summary_json = output_root / "trigger_contract_summary.json"

    metrics.to_csv(metrics_csv, index=False)
    predictions.to_csv(predictions_csv, index=False)
    oracle.to_csv(oracle_csv, index=False)

    summary = {
        "model_dir": str(model_root),
        "dataset_dir": str(dataset_root),
        "activation_threshold_kwh": float(activation_threshold_kwh),
        "include_model_component_features": bool(include_model_component_features),
        "include_exante_profile_features": bool(include_exante_profile_features),
        "n_days": int(len(daily)),
        "n_test_days": int(daily["is_test"].astype(bool).sum()),
        "metrics_csv": str(metrics_csv),
        "predictions_csv": str(predictions_csv),
        "oracle_csv": str(oracle_csv),
        "best_by_test_rebound_r2": (
            metrics.sort_values("test_rebound_r2", ascending=False).head(8).to_dict(orient="records")
        ),
        "oracle_metrics": oracle.to_dict(orient="records"),
    }
    summary_json.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    return summary


def _evaluate_trigger_variants(
    *,
    daily: pd.DataFrame,
    activation_threshold_kwh: float,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Train candidate gates and choose thresholds on train data only."""

    train_mask = ~daily["is_test"].astype(bool).to_numpy()
    test_mask = daily["is_test"].astype(bool).to_numpy()
    y = pd.to_numeric(daily["rebound_true_kwh"], errors="raise").to_numpy(dtype=float)
    y_active = (y > float(activation_threshold_kwh)).astype(int)
    x = _feature_matrix(daily)

    magnitude_candidates = _magnitude_candidates(
        x=x,
        daily=daily,
        train_mask=train_mask,
        y=y,
        y_active=y_active,
    )
    classifier_candidates = _classifier_candidates()
    thresholds = np.round(np.arange(0.05, 0.951, 0.05), 2)

    metric_rows: list[dict[str, Any]] = []
    prediction_frames: list[pd.DataFrame] = []
    for classifier_name, classifier in classifier_candidates.items():
        classifier.fit(x[train_mask], y_active[train_mask])
        active_probability = classifier.predict_proba(x)[:, 1]
        for magnitude_name, magnitude in magnitude_candidates.items():
            best_threshold, train_r2 = _select_threshold(
                y_true=y[train_mask],
                magnitude=magnitude[train_mask],
                active_probability=active_probability[train_mask],
                thresholds=thresholds,
            )
            active_pred = active_probability >= float(best_threshold)
            rebound_pred = np.where(active_pred, magnitude, 0.0)
            metric_rows.append(
                _metric_row(
                    classifier_name=classifier_name,
                    magnitude_name=magnitude_name,
                    threshold=float(best_threshold),
                    train_rebound_r2=float(train_r2),
                    y_true=y,
                    y_pred=rebound_pred,
                    y_active=y_active,
                    active_pred=active_pred.astype(int),
                    train_mask=train_mask,
                    test_mask=test_mask,
                )
            )
            prediction_frames.append(
                pd.DataFrame(
                    {
                        "classifier": classifier_name,
                        "magnitude": magnitude_name,
                        "threshold": float(best_threshold),
                        "run_dir": daily["run_dir"].astype(str),
                        "day": daily["day"],
                        "is_test": daily["is_test"].astype(bool),
                        "rebound_true_kwh": y,
                        "rebound_pred_kwh": rebound_pred,
                        "active_probability": active_probability,
                        "active_pred": active_pred,
                        "truth_active_250k": y_active.astype(bool),
                    }
                )
            )

    metrics = pd.DataFrame(metric_rows).sort_values("test_rebound_r2", ascending=False).reset_index(drop=True)
    predictions = pd.concat(prediction_frames, ignore_index=True)
    return metrics, predictions


def _feature_matrix(daily: pd.DataFrame) -> np.ndarray:
    """Return numeric gate features without truth, labels, or run identity."""

    excluded = {
        "run_dir",
        "day",
        "split_group_run",
        "is_test",
        "shifted_true_kwh",
        "rebound_true_kwh",
        "peak_true_kw",
        "truth_rebound_active",
        "truth_rebound_active_250k",
        "failure_mode",
    }
    feature_columns = [column for column in daily.columns if column not in excluded]
    features = pd.get_dummies(daily[feature_columns], columns=["season_regime"], dtype=float)
    return features.to_numpy(dtype=float)


def _magnitude_candidates(
    *,
    x: np.ndarray,
    daily: pd.DataFrame,
    train_mask: np.ndarray,
    y: np.ndarray,
    y_active: np.ndarray,
) -> dict[str, np.ndarray]:
    """Build candidate rebound magnitudes independent from the gate threshold."""

    candidates: dict[str, np.ndarray] = {
        "raw_rebound": np.maximum(pd.to_numeric(daily["raw_rebound_kwh"], errors="raise").to_numpy(float), 0.0),
        "mass_corrected_rebound": np.maximum(
            pd.to_numeric(daily["mass_corrected_rebound_kwh"], errors="raise").to_numpy(float),
            0.0,
        ),
    }
    for column, name in (
        ("raw_positive_mass_kwh", "raw_positive_mass"),
        ("mass_corrected_positive_mass_kwh", "mass_corrected_positive_mass"),
    ):
        if column in daily.columns:
            # Upper-only has no lower-temperature recovery phase, so the
            # metric-defined rebound can understate the magnitude signal the
            # model actually learns.  Positive daily mass keeps that mechanism
            # visible as an explicit candidate instead of hiding it inside an
            # opaque regressor.
            candidates[name] = np.maximum(pd.to_numeric(daily[column], errors="raise").to_numpy(float), 0.0)
    active_train = train_mask & (y_active == 1)
    if int(active_train.sum()) < 4:
        raise ValueError("[upper_only_trigger_contract] not enough active train days for magnitude regressors.")

    active_regressor = ExtraTreesRegressor(
        n_estimators=700,
        min_samples_leaf=1,
        random_state=42,
        n_jobs=-1,
    )
    active_regressor.fit(x[active_train], y[active_train])
    candidates["active_regressor"] = np.maximum(active_regressor.predict(x), 0.0)

    # The active rebound target has a long upper tail.  The first diagnostic
    # used a raw ExtraTrees regressor, which is intentionally flexible but can
    # overreact to a few large shoulder-day magnitudes.  Keep the original
    # candidate and add smoother/log-scaled variants so the same gate contract
    # can tell us whether the remaining error is a model-class issue or truly
    # missing regime information.
    active_log_target = np.log1p(np.maximum(y[active_train], 0.0))
    extra_trees_leaf3 = ExtraTreesRegressor(
        n_estimators=900,
        min_samples_leaf=3,
        max_features=0.85,
        random_state=43,
        n_jobs=-1,
    )
    extra_trees_leaf3.fit(x[active_train], active_log_target)
    candidates["active_extra_trees_leaf3_log"] = np.maximum(np.expm1(extra_trees_leaf3.predict(x)), 0.0)

    random_forest_leaf3 = RandomForestRegressor(
        n_estimators=900,
        min_samples_leaf=3,
        max_features=0.85,
        random_state=44,
        n_jobs=-1,
    )
    random_forest_leaf3.fit(x[active_train], active_log_target)
    candidates["active_random_forest_leaf3_log"] = np.maximum(np.expm1(random_forest_leaf3.predict(x)), 0.0)

    xgb_log = XGBRegressor(
        n_estimators=500,
        max_depth=3,
        learning_rate=0.03,
        subsample=0.9,
        colsample_bytree=0.9,
        reg_lambda=2.0,
        objective="reg:squarederror",
        random_state=45,
        n_jobs=1,
    )
    xgb_log.fit(x[active_train], active_log_target)
    candidates["active_xgb_log"] = np.maximum(np.expm1(xgb_log.predict(x)), 0.0)
    return candidates


def _classifier_candidates() -> dict[str, Any]:
    """Candidate active/zero gates; all support predict_proba."""

    return {
        "extra_trees_leaf1": ExtraTreesClassifier(
            n_estimators=700,
            min_samples_leaf=1,
            class_weight="balanced",
            random_state=42,
            n_jobs=-1,
        ),
        "random_forest_leaf3": RandomForestClassifier(
            n_estimators=700,
            min_samples_leaf=3,
            class_weight="balanced",
            random_state=42,
            n_jobs=-1,
        ),
        "random_forest_leaf8": RandomForestClassifier(
            n_estimators=700,
            min_samples_leaf=8,
            class_weight="balanced",
            random_state=42,
            n_jobs=-1,
        ),
        "hist_gradient": HistGradientBoostingClassifier(
            max_iter=250,
            learning_rate=0.04,
            l2_regularization=0.1,
            random_state=42,
        ),
        "logistic_balanced": make_pipeline(
            StandardScaler(),
            LogisticRegression(max_iter=3000, class_weight="balanced", C=0.5),
        ),
    }


def _select_threshold(
    *,
    y_true: np.ndarray,
    magnitude: np.ndarray,
    active_probability: np.ndarray,
    thresholds: np.ndarray,
) -> tuple[float, float]:
    """Choose the threshold that maximizes train rebound R2."""

    best_threshold = float(thresholds[0])
    best_r2 = -np.inf
    for threshold in thresholds:
        pred = np.where(active_probability >= float(threshold), magnitude, 0.0)
        score = _safe_r2(y_true, pred)
        if np.isfinite(score) and score > best_r2:
            best_r2 = float(score)
            best_threshold = float(threshold)
    return best_threshold, best_r2


def _metric_row(
    *,
    classifier_name: str,
    magnitude_name: str,
    threshold: float,
    train_rebound_r2: float,
    y_true: np.ndarray,
    y_pred: np.ndarray,
    y_active: np.ndarray,
    active_pred: np.ndarray,
    train_mask: np.ndarray,
    test_mask: np.ndarray,
) -> dict[str, Any]:
    """One train/test metric row for a gate/magnitude pair."""

    return {
        "classifier": classifier_name,
        "magnitude": magnitude_name,
        "threshold_selected_on_train": float(threshold),
        "train_rebound_r2": float(train_rebound_r2),
        "test_rebound_r2": _safe_r2(y_true[test_mask], y_pred[test_mask]),
        "test_rebound_mae": float(mean_absolute_error(y_true[test_mask], y_pred[test_mask])),
        "test_active_accuracy": float(accuracy_score(y_active[test_mask], active_pred[test_mask])),
        "test_active_f1": float(f1_score(y_active[test_mask], active_pred[test_mask])),
        "test_active_count": int(active_pred[test_mask].sum()),
        "n_test_days": int(test_mask.sum()),
    }


def _oracle_rows(*, daily: pd.DataFrame, activation_threshold_kwh: float) -> pd.DataFrame:
    """Report ceilings for zero-gate and active-magnitude subproblems."""

    test = daily["is_test"].astype(bool).to_numpy()
    y = pd.to_numeric(daily["rebound_true_kwh"], errors="raise").to_numpy(dtype=float)
    mass = np.maximum(pd.to_numeric(daily["mass_corrected_rebound_kwh"], errors="raise").to_numpy(dtype=float), 0.0)
    active = y > float(activation_threshold_kwh)
    rows: list[dict[str, Any]] = []
    for name, pred in {
        "mass_corrected_rebound": mass,
        "oracle_zero_low_to_zero": np.where(active, mass, 0.0),
        "oracle_active_magnitude": np.where(active, y, mass),
        "oracle_zero_and_active_magnitude": y,
    }.items():
        rows.append(
            {
                "variant": name,
                "n_test_days": int(test.sum()),
                "rebound_r2": _safe_r2(y[test], pred[test]),
                "rebound_mae": float(mean_absolute_error(y[test], pred[test])),
            }
        )
    return pd.DataFrame(rows)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model-dir", type=Path, default=DEFAULT_MODEL_DIR)
    parser.add_argument("--dataset-dir", type=Path, default=DEFAULT_DATASET_DIR)
    parser.add_argument("--output-dir", type=Path, default=None)
    parser.add_argument("--activation-threshold-kwh", type=float, default=250_000.0)
    parser.add_argument("--include-model-component-features", action="store_true")
    parser.add_argument("--include-exante-profile-features", action="store_true")
    args = parser.parse_args()
    summary = evaluate_upper_only_trigger_contract(
        model_dir=args.model_dir,
        dataset_dir=args.dataset_dir,
        output_dir=args.output_dir,
        activation_threshold_kwh=args.activation_threshold_kwh,
        include_model_component_features=bool(args.include_model_component_features),
        include_exante_profile_features=bool(args.include_exante_profile_features),
    )
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
