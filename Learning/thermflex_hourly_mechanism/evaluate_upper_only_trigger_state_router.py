from __future__ import annotations

"""Evaluate a small Upper-only trigger-state router from persisted labels.

This diagnostic consumes `daily_trigger_state_labels.csv` from
`build_upper_only_trigger_state_labels.py`.  It tests whether the explicit state
contract can separate the problematic Upper-only cases better than direct
`rebound_kwh` regression:

- shifted-without-rebound days should be gated to zero,
- rebound-active days should receive a positive-tail magnitude,
- thresholds are selected only on the persisted train groups.

The output is diagnostic only and is not registered as a preferred model.
"""

import argparse
import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from sklearn.ensemble import ExtraTreesClassifier, ExtraTreesRegressor, RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, f1_score, mean_absolute_error, r2_score
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler


def evaluate_upper_only_trigger_state_router(
    *,
    daily_labels_csv: Path,
    output_dir: Path | None = None,
) -> dict[str, Any]:
    """Train/evaluate state-gate variants on the persisted grouped holdout."""

    labels_path = Path(daily_labels_csv).resolve()
    if not labels_path.exists():
        raise FileNotFoundError(f"[upper_only_trigger_state_router] daily label CSV missing: {labels_path}")
    daily = pd.read_csv(labels_path)
    _validate_daily_labels(daily)
    output_root = (
        Path(output_dir).resolve()
        if output_dir is not None
        else labels_path.parent / "state_router"
    )
    output_root.mkdir(parents=True, exist_ok=True)

    metrics, predictions = _evaluate_variants(daily)
    metrics_csv = output_root / "state_router_metrics.csv"
    predictions_csv = output_root / "state_router_predictions.csv"
    summary_json = output_root / "state_router_summary.json"
    metrics.to_csv(metrics_csv, index=False)
    predictions.to_csv(predictions_csv, index=False)
    summary = {
        "daily_labels_csv": str(labels_path),
        "n_days": int(len(daily)),
        "n_test_days": int(daily["is_test"].astype(bool).sum()),
        "metrics_csv": str(metrics_csv),
        "predictions_csv": str(predictions_csv),
        "best_by_test_rebound_r2": (
            metrics.sort_values("test_rebound_r2", ascending=False).head(10).to_dict(orient="records")
        ),
    }
    summary_json.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    return summary


def _evaluate_variants(daily: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Evaluate classifier/magnitude combinations using train-only thresholds."""

    train = ~daily["is_test"].astype(bool).to_numpy()
    test = daily["is_test"].astype(bool).to_numpy()
    y_rebound = pd.to_numeric(daily["rebound_true_kwh"], errors="raise").to_numpy(dtype=float)
    y_active = daily["true_rebound_active"].astype(bool).to_numpy()
    y_veto = daily["true_shifted_without_rebound"].astype(bool).to_numpy()
    feature_matrices = _feature_matrices(daily)
    thresholds = np.round(np.arange(0.05, 0.951, 0.05), 2)

    metric_rows: list[dict[str, Any]] = []
    prediction_frames: list[pd.DataFrame] = []
    for feature_profile, x in feature_matrices.items():
        classifiers = _classifier_candidates()
        veto_classifiers = _classifier_candidates()
        magnitudes = _magnitude_candidates(x=x, daily=daily, train=train, y_rebound=y_rebound, y_active=y_active)
        for clf_name, clf in classifiers.items():
            clf.fit(x[train], y_active[train])
            active_probability = clf.predict_proba(x)[:, 1]
            for magnitude_name, magnitude in magnitudes.items():
                threshold, train_r2 = _select_threshold(
                    y_true=y_rebound[train],
                    magnitude=magnitude[train],
                    active_probability=active_probability[train],
                    thresholds=thresholds,
                )
                active_pred = active_probability >= threshold
                rebound_pred = np.where(active_pred, magnitude, 0.0)
                metric_rows.append(
                    _metric_row(
                        feature_profile=feature_profile,
                        classifier=clf_name,
                        magnitude=magnitude_name,
                        threshold=threshold,
                        train_rebound_r2=train_r2,
                        y_rebound=y_rebound,
                        rebound_pred=rebound_pred,
                        y_active=y_active,
                        active_pred=active_pred,
                        train=train,
                        test=test,
                        router_variant="active_only",
                    )
                )
                prediction_frames.append(
                    pd.DataFrame(
                        {
                            "feature_profile": feature_profile,
                            "router_variant": "active_only",
                            "classifier": clf_name,
                            "veto_classifier": "",
                            "magnitude": magnitude_name,
                            "threshold": float(threshold),
                            "veto_threshold": np.nan,
                            "day": daily["day"].astype(str),
                            "is_test": daily["is_test"].astype(bool),
                            "rebound_true_kwh": y_rebound,
                            "rebound_pred_kwh": rebound_pred,
                            "active_probability": active_probability,
                            "active_pred": active_pred,
                            "veto_probability": np.nan,
                            "veto_pred": False,
                            "true_rebound_active": y_active,
                            "true_shifted_without_rebound": y_veto,
                        }
                    )
                )
            for veto_name, veto_clf in veto_classifiers.items():
                veto_clf.fit(x[train], y_veto[train])
                veto_probability = veto_clf.predict_proba(x)[:, 1]
                for magnitude_name, magnitude in magnitudes.items():
                    threshold, veto_threshold, train_r2 = _select_veto_thresholds(
                        y_true=y_rebound[train],
                        magnitude=magnitude[train],
                        active_probability=active_probability[train],
                        veto_probability=veto_probability[train],
                        thresholds=thresholds,
                    )
                    active_pred_raw = active_probability >= threshold
                    veto_pred = veto_probability >= veto_threshold
                    active_pred = active_pred_raw & ~veto_pred
                    rebound_pred = np.where(active_pred, magnitude, 0.0)
                    metric_rows.append(
                        _metric_row(
                            feature_profile=feature_profile,
                            classifier=clf_name,
                            magnitude=magnitude_name,
                            threshold=threshold,
                            train_rebound_r2=train_r2,
                            y_rebound=y_rebound,
                            rebound_pred=rebound_pred,
                            y_active=y_active,
                            active_pred=active_pred,
                            train=train,
                            test=test,
                            router_variant="shifted_without_rebound_veto",
                            veto_classifier=veto_name,
                            veto_threshold=veto_threshold,
                            y_veto=y_veto,
                            veto_pred=veto_pred,
                        )
                    )
                    prediction_frames.append(
                        pd.DataFrame(
                            {
                                "feature_profile": feature_profile,
                                "router_variant": "shifted_without_rebound_veto",
                                "classifier": clf_name,
                                "veto_classifier": veto_name,
                                "magnitude": magnitude_name,
                                "threshold": float(threshold),
                                "veto_threshold": float(veto_threshold),
                                "day": daily["day"].astype(str),
                                "is_test": daily["is_test"].astype(bool),
                                "rebound_true_kwh": y_rebound,
                                "rebound_pred_kwh": rebound_pred,
                                "active_probability": active_probability,
                                "active_pred": active_pred,
                                "veto_probability": veto_probability,
                                "veto_pred": veto_pred,
                                "true_rebound_active": y_active,
                                "true_shifted_without_rebound": y_veto,
                            }
                        )
                    )
    return (
        pd.DataFrame(metric_rows).sort_values("test_rebound_r2", ascending=False).reset_index(drop=True),
        pd.concat(prediction_frames, ignore_index=True),
    )


def _feature_matrices(daily: pd.DataFrame) -> dict[str, np.ndarray]:
    """Return compact baseline and optional context-rich feature profiles."""

    return {
        "compact_state": _feature_matrix(daily, include_extended_context=False, include_lagged_context=False),
        "state_plus_daily_context": _feature_matrix(daily, include_extended_context=True, include_lagged_context=False),
        "state_plus_lagged_context": _feature_matrix(daily, include_extended_context=True, include_lagged_context=True),
    }


def _feature_matrix(
    daily: pd.DataFrame,
    *,
    include_extended_context: bool,
    include_lagged_context: bool,
) -> np.ndarray:
    """Use predicted state, ex-ante context, and coarse regimes without truth leakage."""

    excluded_exact = {
        "run_dir",
        "day",
        "split_group_run",
        "is_test",
        "trigger_state_mismatch",
        "true_rebound_active",
        "pred_rebound_active",
        "true_shifted_without_rebound",
        "pred_shifted_without_rebound",
    }
    excluded_prefixes = ("true_",)
    excluded_suffixes = ("_true_kwh", "_true_kw")
    feature_columns = []
    for column in daily.columns:
        if column in excluded_exact:
            continue
        if column.startswith(excluded_prefixes):
            continue
        if column.endswith(excluded_suffixes):
            continue
        if column in {"shifted_true_kwh", "rebound_true_kwh", "peak_true_kw"}:
            continue
        if not include_lagged_context and _is_lagged_context_feature(column):
            continue
        if not include_extended_context and _is_extended_context_feature(column):
            continue
        feature_columns.append(column)
    if "season_regime" not in feature_columns:
        raise KeyError("[upper_only_trigger_state_router] season_regime feature missing.")
    features = pd.get_dummies(daily.loc[:, feature_columns], columns=["season_regime"], dtype=float)
    numeric = features.apply(pd.to_numeric, errors="raise")
    return numeric.to_numpy(dtype=float)


def _is_extended_context_feature(column: str) -> bool:
    """Identify context features added after the original compact state contract."""

    extended_exact = {
        "q_ref_peak_hour",
        "price_peak_hour",
        "price_low_hour",
        "t_outdoor_min_c",
        "t_outdoor_max_c",
        "t_outdoor_std_c",
        "heating_degree_hours_15c",
        "gas_price_mean_eur_mwh_fuel",
        "co2_price_mean_eur_tco2",
        "irradiance_sum",
        "solargains_sum",
        "price_late_minus_midday_eur_mwh",
        "price_evening_minus_morning_eur_mwh",
        "t_late_minus_morning_c",
    }
    extended_prefixes = (
        "prev1_",
        "prev2_",
        "prev3_",
        "prev3_mean_",
        "current_minus_prev3_mean_",
        "q_ref_night_",
        "q_ref_morning_",
        "q_ref_midday_",
        "q_ref_evening_",
        "q_ref_late_",
        "price_",
        "t_outdoor_night_",
        "t_outdoor_morning_",
        "t_outdoor_midday_",
        "t_outdoor_evening_",
        "t_outdoor_late_",
    )
    return column in extended_exact or column.startswith(extended_prefixes)


def _is_lagged_context_feature(column: str) -> bool:
    """Identify explicit previous-day thermal-state proxy features."""

    return str(column).startswith(
        (
            "prev1_",
            "prev2_",
            "prev3_",
            "prev3_mean_",
            "current_minus_prev3_mean_",
        )
    )


def _magnitude_candidates(
    *,
    x: np.ndarray,
    daily: pd.DataFrame,
    train: np.ndarray,
    y_rebound: np.ndarray,
    y_active: np.ndarray,
) -> dict[str, np.ndarray]:
    """Build explicit positive-tail magnitudes and active-only regressors."""

    candidates = {
        "pred_rebound": np.maximum(pd.to_numeric(daily["rebound_pred_kwh"], errors="raise").to_numpy(float), 0.0),
        "pred_positive_after_cutback": np.maximum(
            pd.to_numeric(daily["pred_positive_after_cutback_kwh"], errors="raise").to_numpy(float),
            0.0,
        ),
        "pred_positive_mass": np.maximum(
            pd.to_numeric(daily["pred_positive_mass_kwh"], errors="raise").to_numpy(float),
            0.0,
        ),
    }
    active_train = train & y_active
    if int(active_train.sum()) < 4:
        raise ValueError("[upper_only_trigger_state_router] not enough active train rows.")
    active_target = np.log1p(np.maximum(y_rebound[active_train], 0.0))
    reg = ExtraTreesRegressor(
        n_estimators=900,
        min_samples_leaf=2,
        max_features=0.85,
        random_state=118,
        n_jobs=-1,
    )
    reg.fit(x[active_train], active_target)
    candidates["active_extra_trees_log"] = np.maximum(np.expm1(reg.predict(x)), 0.0)
    return candidates


def _classifier_candidates() -> dict[str, Any]:
    """Return small candidate set for the explicit active-state gate."""

    return {
        "extra_trees_leaf2": ExtraTreesClassifier(
            n_estimators=800,
            min_samples_leaf=2,
            class_weight="balanced",
            random_state=115,
            n_jobs=-1,
        ),
        "random_forest_leaf4": RandomForestClassifier(
            n_estimators=800,
            min_samples_leaf=4,
            class_weight="balanced",
            random_state=116,
            n_jobs=-1,
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
    """Choose the active threshold using train-side rebound R2 only."""

    best_threshold = float(thresholds[0])
    best_r2 = -np.inf
    for threshold in thresholds:
        pred = np.where(active_probability >= float(threshold), magnitude, 0.0)
        score = _safe_r2(y_true, pred)
        if np.isfinite(score) and score > best_r2:
            best_threshold = float(threshold)
            best_r2 = float(score)
    return best_threshold, best_r2


def _select_veto_thresholds(
    *,
    y_true: np.ndarray,
    magnitude: np.ndarray,
    active_probability: np.ndarray,
    veto_probability: np.ndarray,
    thresholds: np.ndarray,
) -> tuple[float, float, float]:
    """Choose active and veto thresholds jointly on train-side rebound R2."""

    best_active_threshold = float(thresholds[0])
    best_veto_threshold = float(thresholds[0])
    best_r2 = -np.inf
    for active_threshold in thresholds:
        active_pred = active_probability >= float(active_threshold)
        for veto_threshold in thresholds:
            veto_pred = veto_probability >= float(veto_threshold)
            pred = np.where(active_pred & ~veto_pred, magnitude, 0.0)
            score = _safe_r2(y_true, pred)
            if np.isfinite(score) and score > best_r2:
                best_active_threshold = float(active_threshold)
                best_veto_threshold = float(veto_threshold)
                best_r2 = float(score)
    return best_active_threshold, best_veto_threshold, best_r2


def _metric_row(
    *,
    feature_profile: str,
    classifier: str,
    magnitude: str,
    threshold: float,
    train_rebound_r2: float,
    y_rebound: np.ndarray,
    rebound_pred: np.ndarray,
    y_active: np.ndarray,
    active_pred: np.ndarray,
    train: np.ndarray,
    test: np.ndarray,
    router_variant: str,
    veto_classifier: str | None = None,
    veto_threshold: float | None = None,
    y_veto: np.ndarray | None = None,
    veto_pred: np.ndarray | None = None,
) -> dict[str, Any]:
    """Build one compact metric row."""

    row = {
        "feature_profile": str(feature_profile),
        "router_variant": str(router_variant),
        "classifier": str(classifier),
        "veto_classifier": "" if veto_classifier is None else str(veto_classifier),
        "magnitude": str(magnitude),
        "threshold_selected_on_train": float(threshold),
        "veto_threshold_selected_on_train": np.nan if veto_threshold is None else float(veto_threshold),
        "train_rebound_r2": float(train_rebound_r2),
        "test_rebound_r2": _safe_r2(y_rebound[test], rebound_pred[test]),
        "test_rebound_mae": float(mean_absolute_error(y_rebound[test], rebound_pred[test])),
        "test_active_accuracy": float(accuracy_score(y_active[test], active_pred[test])),
        "test_active_f1": float(f1_score(y_active[test], active_pred[test], zero_division=0)),
        "test_active_count": int(active_pred[test].sum()),
        "n_train_days": int(train.sum()),
        "n_test_days": int(test.sum()),
    }
    if y_veto is not None and veto_pred is not None:
        row.update(
            {
                "test_veto_accuracy": float(accuracy_score(y_veto[test], veto_pred[test])),
                "test_veto_f1": float(f1_score(y_veto[test], veto_pred[test], zero_division=0)),
                "test_veto_count": int(veto_pred[test].sum()),
            }
        )
    else:
        row.update(
            {
                "test_veto_accuracy": np.nan,
                "test_veto_f1": np.nan,
                "test_veto_count": 0,
            }
        )
    return row


def _safe_r2(y_true: np.ndarray, y_pred: np.ndarray) -> float:
    """Return R2 or NaN for degenerate slices."""

    truth = np.asarray(y_true, dtype=float)
    pred = np.asarray(y_pred, dtype=float)
    finite = np.isfinite(truth) & np.isfinite(pred)
    truth = truth[finite]
    pred = pred[finite]
    if truth.size < 2 or float(np.var(truth)) <= 1e-12:
        return float("nan")
    return float(r2_score(truth, pred))


def _validate_daily_labels(frame: pd.DataFrame) -> None:
    """Validate the explicit label artifact before training a router."""

    required = {
        "day",
        "is_test",
        "season_regime",
        "rebound_true_kwh",
        "rebound_pred_kwh",
        "true_rebound_active",
        "true_shifted_without_rebound",
        "pred_positive_after_cutback_kwh",
        "pred_positive_mass_kwh",
    }
    missing = sorted(required.difference(frame.columns))
    if missing:
        raise KeyError("[upper_only_trigger_state_router] daily labels missing columns: " + ", ".join(missing))
    if not frame["is_test"].astype(bool).any():
        raise ValueError("[upper_only_trigger_state_router] label frame contains no persisted test rows.")
    if frame["is_test"].astype(bool).all():
        raise ValueError("[upper_only_trigger_state_router] label frame contains no train rows.")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--daily-labels-csv", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, default=None)
    args = parser.parse_args()
    summary = evaluate_upper_only_trigger_state_router(
        daily_labels_csv=args.daily_labels_csv,
        output_dir=args.output_dir,
    )
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
