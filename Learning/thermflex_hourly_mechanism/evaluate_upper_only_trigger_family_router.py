from __future__ import annotations

"""Evaluate route-family trigger routers for Upper-only rebound.

This diagnostic is deliberately separate from the existing pooled state router.
The Upper-only rebound error is concentrated in a small number of daily
families, so this script tests whether the active gate and positive magnitude
should be fitted per ex-ante family instead of one pooled contract.

The routes are built only from persisted context features, never from true KPI
values.  A route variant is skipped with an explicit status row when one of its
families has too little train signal to fit the requested local model.
"""

import argparse
import json
import sys
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from sklearn.ensemble import ExtraTreesClassifier, ExtraTreesRegressor, RandomForestClassifier
from sklearn.metrics import accuracy_score, f1_score, mean_absolute_error

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from Learning.thermflex_hourly_mechanism.evaluate_upper_only_trigger_state_router import (
    _feature_matrices,
    _safe_r2,
    _select_threshold,
    _select_veto_thresholds,
    _validate_daily_labels,
)


def evaluate_upper_only_trigger_family_router(
    *,
    daily_labels_csv: Path,
    output_dir: Path | None = None,
) -> dict[str, Any]:
    """Train/evaluate route-local state routers on the persisted holdout."""

    labels_path = Path(daily_labels_csv).resolve()
    if not labels_path.exists():
        raise FileNotFoundError(f"[upper_only_trigger_family_router] daily label CSV missing: {labels_path}")
    daily = pd.read_csv(labels_path)
    _validate_daily_labels(daily)
    output_root = (
        Path(output_dir).resolve()
        if output_dir is not None
        else labels_path.parent / "family_router"
    )
    output_root.mkdir(parents=True, exist_ok=True)

    metrics, predictions, route_status = _evaluate_family_variants(daily)
    metrics_csv = output_root / "family_router_metrics.csv"
    predictions_csv = output_root / "family_router_predictions.csv"
    route_status_csv = output_root / "family_router_route_status.csv"
    summary_json = output_root / "family_router_summary.json"
    metrics.to_csv(metrics_csv, index=False)
    predictions.to_csv(predictions_csv, index=False)
    route_status.to_csv(route_status_csv, index=False)
    summary = {
        "daily_labels_csv": str(labels_path),
        "n_days": int(len(daily)),
        "n_test_days": int(daily["is_test"].astype(bool).sum()),
        "metrics_csv": str(metrics_csv),
        "predictions_csv": str(predictions_csv),
        "route_status_csv": str(route_status_csv),
        "best_by_test_rebound_r2": (
            metrics.sort_values("test_rebound_r2", ascending=False).head(10).to_dict(orient="records")
        ),
        "skipped_route_variants": int((route_status["status"] != "ok").sum()),
    }
    summary_json.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    return summary


def _evaluate_family_variants(daily: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Evaluate route-local classifier/magnitude combinations."""

    train = ~daily["is_test"].astype(bool).to_numpy()
    test = daily["is_test"].astype(bool).to_numpy()
    y_rebound = pd.to_numeric(daily["rebound_true_kwh"], errors="raise").to_numpy(dtype=float)
    y_active = daily["true_rebound_active"].astype(bool).to_numpy()
    y_veto = daily["true_shifted_without_rebound"].astype(bool).to_numpy()
    thresholds = np.round(np.arange(0.05, 0.951, 0.05), 2)

    metric_rows: list[dict[str, Any]] = []
    prediction_frames: list[pd.DataFrame] = []
    status_rows: list[dict[str, Any]] = []
    route_maps = _route_assignments(daily)
    # The pooled diagnostic already showed that the extended state/context
    # profile dominates.  The family test therefore keeps the grid focused and
    # spends the compute budget on route splits instead of re-testing weak
    # feature profiles.
    feature_profiles = ("state_plus_daily_context",)

    for route_mode, routes in route_maps.items():
        route_names = tuple(pd.Series(routes).drop_duplicates().astype(str))
        for feature_profile in feature_profiles:
            for classifier_name in _family_classifier_candidates().keys():
                for magnitude_name in (
                    "pred_rebound",
                    "pred_positive_after_cutback",
                    "pred_positive_mass",
                    "active_extra_trees_log",
                ):
                    row = _evaluate_one_family_variant(
                        daily=daily,
                        routes=routes,
                        route_names=route_names,
                        route_mode=route_mode,
                        feature_profile=feature_profile,
                        classifier_name=classifier_name,
                        magnitude_name=magnitude_name,
                        veto_classifier_name=None,
                        train=train,
                        test=test,
                        y_rebound=y_rebound,
                        y_active=y_active,
                        y_veto=y_veto,
                        thresholds=thresholds,
                    )
                    status_rows.extend(row["status_rows"])
                    if row["status"] == "ok":
                        metric_rows.append(row["metric"])
                        prediction_frames.append(row["predictions"])
                    for veto_classifier_name in ("random_forest_leaf4",):
                        veto_row = _evaluate_one_family_variant(
                            daily=daily,
                            routes=routes,
                            route_names=route_names,
                            route_mode=route_mode,
                            feature_profile=feature_profile,
                            classifier_name=classifier_name,
                            magnitude_name=magnitude_name,
                            veto_classifier_name=veto_classifier_name,
                            train=train,
                            test=test,
                            y_rebound=y_rebound,
                            y_active=y_active,
                            y_veto=y_veto,
                            thresholds=thresholds,
                        )
                        status_rows.extend(veto_row["status_rows"])
                        if veto_row["status"] == "ok":
                            metric_rows.append(veto_row["metric"])
                            prediction_frames.append(veto_row["predictions"])

    if not metric_rows:
        raise ValueError("[upper_only_trigger_family_router] no route-family variant was evaluable.")
    return (
        pd.DataFrame(metric_rows).sort_values("test_rebound_r2", ascending=False).reset_index(drop=True),
        pd.concat(prediction_frames, ignore_index=True),
        pd.DataFrame(status_rows),
    )


def _evaluate_one_family_variant(
    *,
    daily: pd.DataFrame,
    routes: np.ndarray,
    route_names: tuple[str, ...],
    route_mode: str,
    feature_profile: str,
    classifier_name: str,
    magnitude_name: str,
    veto_classifier_name: str | None,
    train: np.ndarray,
    test: np.ndarray,
    y_rebound: np.ndarray,
    y_active: np.ndarray,
    y_veto: np.ndarray,
    thresholds: np.ndarray,
) -> dict[str, Any]:
    """Fit one requested model family independently inside every route."""

    rebound_pred = np.zeros(len(daily), dtype=float)
    active_probability = np.zeros(len(daily), dtype=float)
    active_pred = np.zeros(len(daily), dtype=bool)
    veto_probability = np.full(len(daily), np.nan, dtype=float)
    veto_pred = np.zeros(len(daily), dtype=bool)
    route_thresholds: dict[str, float] = {}
    route_veto_thresholds: dict[str, float] = {}
    status_rows: list[dict[str, Any]] = []

    for route_name in route_names:
        route_mask = routes == route_name
        route_index = np.flatnonzero(route_mask)
        train_local = train[route_index]
        test_local = test[route_index]
        y_active_local = y_active[route_index]
        y_veto_local = y_veto[route_index]
        y_rebound_local = y_rebound[route_index]
        status = _route_fit_status(
            route_name=route_name,
            train_local=train_local,
            test_local=test_local,
            y_active_local=y_active_local,
            y_veto_local=y_veto_local,
            veto_enabled=veto_classifier_name is not None,
            magnitude_name=magnitude_name,
        )
        status_rows.append(
            {
                "route_mode": route_mode,
                "route_family": route_name,
                "feature_profile": feature_profile,
                "router_variant": _router_variant(veto_classifier_name),
                "classifier": classifier_name,
                "veto_classifier": "" if veto_classifier_name is None else veto_classifier_name,
                "magnitude": magnitude_name,
                **status,
            }
        )
        if status["status"] != "ok":
            return {"status": "skipped", "status_rows": status_rows}

        route_daily = daily.iloc[route_index].reset_index(drop=True)
        x_local = _feature_matrices(route_daily)[feature_profile]
        clf = _family_classifier_candidates()[classifier_name]
        clf.fit(x_local[train_local], y_active_local[train_local])
        active_probability_local = clf.predict_proba(x_local)[:, 1]
        magnitude_local = _family_magnitude_candidate(
            x=x_local,
            daily=route_daily,
            train=train_local,
            y_rebound=y_rebound_local,
            y_active=y_active_local,
            magnitude_name=magnitude_name,
        )
        if veto_classifier_name is None:
            threshold, _train_r2 = _select_threshold(
                y_true=y_rebound_local[train_local],
                magnitude=magnitude_local[train_local],
                active_probability=active_probability_local[train_local],
                thresholds=thresholds,
            )
            active_pred_local = active_probability_local >= threshold
            veto_probability_local = np.full(len(route_index), np.nan, dtype=float)
            veto_pred_local = np.zeros(len(route_index), dtype=bool)
        else:
            veto_clf = _family_classifier_candidates()[veto_classifier_name]
            veto_clf.fit(x_local[train_local], y_veto_local[train_local])
            veto_probability_local = veto_clf.predict_proba(x_local)[:, 1]
            threshold, veto_threshold, _train_r2 = _select_veto_thresholds(
                y_true=y_rebound_local[train_local],
                magnitude=magnitude_local[train_local],
                active_probability=active_probability_local[train_local],
                veto_probability=veto_probability_local[train_local],
                thresholds=thresholds,
            )
            active_pred_raw = active_probability_local >= threshold
            veto_pred_local = veto_probability_local >= veto_threshold
            active_pred_local = active_pred_raw & ~veto_pred_local
            route_veto_thresholds[route_name] = float(veto_threshold)
        rebound_pred_local = np.where(active_pred_local, magnitude_local, 0.0)

        rebound_pred[route_index] = rebound_pred_local
        active_probability[route_index] = active_probability_local
        active_pred[route_index] = active_pred_local
        veto_probability[route_index] = veto_probability_local
        veto_pred[route_index] = veto_pred_local
        route_thresholds[route_name] = float(threshold)

    router_variant = _router_variant(veto_classifier_name)
    metric = {
        "route_mode": route_mode,
        "feature_profile": feature_profile,
        "router_variant": router_variant,
        "classifier": classifier_name,
        "veto_classifier": "" if veto_classifier_name is None else veto_classifier_name,
        "magnitude": magnitude_name,
        "route_thresholds_json": json.dumps(route_thresholds, sort_keys=True),
        "route_veto_thresholds_json": json.dumps(route_veto_thresholds, sort_keys=True),
        "train_rebound_r2": _safe_r2(y_rebound[train], rebound_pred[train]),
        "test_rebound_r2": _safe_r2(y_rebound[test], rebound_pred[test]),
        "test_rebound_mae": float(mean_absolute_error(y_rebound[test], rebound_pred[test])),
        "test_active_accuracy": float(accuracy_score(y_active[test], active_pred[test])),
        "test_active_f1": float(f1_score(y_active[test], active_pred[test], zero_division=0)),
        "test_active_count": int(active_pred[test].sum()),
        "test_veto_accuracy": (
            np.nan if veto_classifier_name is None else float(accuracy_score(y_veto[test], veto_pred[test]))
        ),
        "test_veto_f1": (
            np.nan if veto_classifier_name is None else float(f1_score(y_veto[test], veto_pred[test], zero_division=0))
        ),
        "test_veto_count": int(veto_pred[test].sum()),
        "n_train_days": int(train.sum()),
        "n_test_days": int(test.sum()),
    }
    predictions = pd.DataFrame(
        {
            "route_mode": route_mode,
            "route_family": routes.astype(str),
            "feature_profile": feature_profile,
            "router_variant": router_variant,
            "classifier": classifier_name,
            "veto_classifier": "" if veto_classifier_name is None else veto_classifier_name,
            "magnitude": magnitude_name,
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
    return {"status": "ok", "metric": metric, "predictions": predictions, "status_rows": status_rows}


def _route_assignments(daily: pd.DataFrame) -> dict[str, np.ndarray]:
    """Build ex-ante route labels from persisted state/context columns."""

    required = {"season_regime", "t_outdoor_mean_c", "q_ref_peak_kw"}
    missing = sorted(required.difference(daily.columns))
    if missing:
        raise KeyError("[upper_only_trigger_family_router] route feature columns missing: " + ", ".join(missing))
    season = daily["season_regime"].astype(str).to_numpy()
    outdoor = pd.to_numeric(daily["t_outdoor_mean_c"], errors="raise").to_numpy(dtype=float)
    q_peak = pd.to_numeric(daily["q_ref_peak_kw"], errors="raise").to_numpy(dtype=float)
    q_peak_median = float(np.median(q_peak))
    return {
        "season_2way": season,
        "season_temp_3way": np.where(
            season == "winter",
            "winter",
            np.where(outdoor < 12.0, "shoulder_cool", "shoulder_mild"),
        ),
        "season_ref_peak_3way": np.where(
            season == "winter",
            "winter",
            np.where(q_peak >= q_peak_median, "shoulder_high_ref_peak", "shoulder_low_ref_peak"),
        ),
    }


def _family_classifier_candidates() -> dict[str, Any]:
    """Return focused tree gates for the route-family diagnostic."""

    return {
        "extra_trees_leaf2": ExtraTreesClassifier(
            n_estimators=350,
            min_samples_leaf=2,
            class_weight="balanced",
            random_state=215,
            n_jobs=-1,
        ),
        "random_forest_leaf4": RandomForestClassifier(
            n_estimators=350,
            min_samples_leaf=4,
            class_weight="balanced",
            random_state=216,
            n_jobs=-1,
        ),
    }


def _family_magnitude_candidate(
    *,
    x: np.ndarray,
    daily: pd.DataFrame,
    train: np.ndarray,
    y_rebound: np.ndarray,
    y_active: np.ndarray,
    magnitude_name: str,
) -> np.ndarray:
    """Build exactly one local positive-tail magnitude for one route family."""

    raw_columns = {
        "pred_rebound": "rebound_pred_kwh",
        "pred_positive_after_cutback": "pred_positive_after_cutback_kwh",
        "pred_positive_mass": "pred_positive_mass_kwh",
    }
    if magnitude_name in raw_columns:
        return np.maximum(pd.to_numeric(daily[raw_columns[magnitude_name]], errors="raise").to_numpy(float), 0.0)
    if magnitude_name != "active_extra_trees_log":
        raise KeyError(f"[upper_only_trigger_family_router] unknown magnitude: {magnitude_name}")
    active_train = train & y_active
    if int(active_train.sum()) < 4:
        raise ValueError("[upper_only_trigger_family_router] not enough active train rows.")
    active_target = np.log1p(np.maximum(y_rebound[active_train], 0.0))
    reg = ExtraTreesRegressor(
        n_estimators=450,
        min_samples_leaf=2,
        max_features=0.85,
        random_state=218,
        n_jobs=-1,
    )
    reg.fit(x[active_train], active_target)
    return np.maximum(np.expm1(reg.predict(x)), 0.0)


def _route_fit_status(
    *,
    route_name: str,
    train_local: np.ndarray,
    test_local: np.ndarray,
    y_active_local: np.ndarray,
    y_veto_local: np.ndarray,
    veto_enabled: bool,
    magnitude_name: str,
) -> dict[str, Any]:
    """Return explicit route fit feasibility diagnostics."""

    n_train = int(train_local.sum())
    n_test = int(test_local.sum())
    n_active_train = int((train_local & y_active_local).sum())
    n_active_test = int((test_local & y_active_local).sum())
    n_veto_train = int((train_local & y_veto_local).sum())
    status = "ok"
    reason = ""
    if n_train < 8 or n_test < 1:
        status = "skipped_insufficient_route_rows"
        reason = f"route={route_name} n_train={n_train} n_test={n_test}"
    elif np.unique(y_active_local[train_local]).size < 2:
        status = "skipped_single_active_class"
        reason = f"route={route_name} active_train={n_active_train}"
    elif magnitude_name == "active_extra_trees_log" and n_active_train < 4:
        status = "skipped_insufficient_active_magnitude_rows"
        reason = f"route={route_name} active_train={n_active_train}"
    elif veto_enabled and np.unique(y_veto_local[train_local]).size < 2:
        status = "skipped_single_veto_class"
        reason = f"route={route_name} veto_train={n_veto_train}"
    return {
        "status": status,
        "reason": reason,
        "n_train": n_train,
        "n_test": n_test,
        "n_active_train": n_active_train,
        "n_active_test": n_active_test,
        "n_veto_train": n_veto_train,
    }


def _router_variant(veto_classifier_name: str | None) -> str:
    """Name the router variant consistently with the pooled state router."""

    return "active_only" if veto_classifier_name is None else "shifted_without_rebound_veto"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--daily-labels-csv", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, default=None)
    args = parser.parse_args()
    summary = evaluate_upper_only_trigger_family_router(
        daily_labels_csv=args.daily_labels_csv,
        output_dir=args.output_dir,
    )
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
