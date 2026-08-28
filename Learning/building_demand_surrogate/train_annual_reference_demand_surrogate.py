"""Train the active, non-flexibility EnergyPlus demand surrogate for Vienna."""

from __future__ import annotations

import json
from pathlib import Path
import sys

import numpy as np
import pandas as pd
from joblib import dump
from sklearn.ensemble import HistGradientBoostingClassifier, HistGradientBoostingRegressor
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from sklearn.model_selection import GroupKFold


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
if str(REPOSITORY_ROOT) not in sys.path:
    sys.path.insert(0, str(REPOSITORY_ROOT))

from Settings.technical.building_demand_surrogate import (
    BuildingDemandSurrogateConfig,
    make_building_demand_surrogate_config,
)
from Technical_model.technologies.buildings.calibration.from_repo import build_teacher_input_bundle


TARGETS = {
    "useful_space_heating_kwh_per_m2": "space_heating_kwh",
    "useful_cooling_kwh_per_m2": "cooling_kwh",
}


def _config() -> BuildingDemandSurrogateConfig:
    return make_building_demand_surrogate_config()


def _model_dir(cfg: BuildingDemandSurrogateConfig) -> Path:
    return REPOSITORY_ROOT / "Learning" / "models" / cfg.model_bundle_name


def _dataset_dir() -> Path:
    return REPOSITORY_ROOT / "Learning" / "datasets" / "vienna_building_energyplus_teacher"


# Benchmark and paper runners import these names.
EXPERIMENT_ID = _config().experiment_id
MODEL_DIR = _model_dir(_config())


def _cohort_features() -> pd.DataFrame:
    """Expose only physical cohort descriptors; identifiers must not become ML features."""
    rows: list[dict[str, float | str]] = []
    for item in build_teacher_input_bundle().cohorts:
        floor = float(item.conditioned_floor_m2)
        if floor <= 0.0:
            raise ValueError(f"[annual_demand_surrogate] Non-positive floor area for '{item.cohort_id}'.")
        rows.append(
            {
                "cohort_id": str(item.cohort_id),
                "is_residential": float(str(item.sector) == "residential"),
                "u_wall": float(item.u_wall),
                "u_window": float(item.u_window),
                "u_roof": float(item.u_roof),
                "u_floor": float(item.u_floor),
                "wall_area_per_m2": float(item.wall_area_m2) / floor,
                "window_area_per_m2": float(item.window_area_total_m2) / floor,
                "roof_area_per_m2": float(item.roof_area_m2) / floor,
                "floor_exposed_per_m2": float(item.floor_exposed_area_m2) / floor,
                "heat_capacity_wh_per_m2k": float(item.heat_capacity_wh_per_k) / floor,
            }
        )
    return pd.DataFrame(rows)


def _add_drive_features(data: pd.DataFrame, cfg: BuildingDemandSurrogateConfig) -> list[str]:
    """Setpoint and UA drives make the heating/cooling switch an explicit split, not a learned smear."""
    extra: list[str] = []
    if cfg.use_setpoint_drive_features:
        data["heating_setpoint_minus_outdoor_k"] = data["heating_setpoint_c"] - data["outdoor_temperature_c"]
        data["outdoor_minus_cooling_setpoint_k"] = data["outdoor_temperature_c"] - data["cooling_setpoint_c"]
        extra.extend(["heating_setpoint_minus_outdoor_k", "outdoor_minus_cooling_setpoint_k"])
    if cfg.use_ua_drive_features:
        ua_proxy = (
            data["u_wall"] * data["wall_area_per_m2"]
            + data["u_window"] * data["window_area_per_m2"]
            + data["u_roof"] * data["roof_area_per_m2"]
            + data["u_floor"] * data["floor_exposed_per_m2"]
        )
        if (ua_proxy <= 0.0).any():
            raise ValueError("[annual_demand_surrogate] UA proxy must be > 0 for every cohort hour.")
        data["ua_proxy_w_per_m2k"] = ua_proxy
        extra.append("ua_proxy_w_per_m2k")
        if cfg.use_setpoint_drive_features:
            data["heating_ua_drive_w_per_m2"] = ua_proxy * data["heating_setpoint_minus_outdoor_k"]
            data["cooling_ua_drive_w_per_m2"] = ua_proxy * data["outdoor_minus_cooling_setpoint_k"]
            extra.extend(["heating_ua_drive_w_per_m2", "cooling_ua_drive_w_per_m2"])
    return extra


def _monotonic_cst(features: list[str], target: str, cfg: BuildingDemandSurrogateConfig) -> list[int] | None:
    """Heating falls as outdoor temperature rises; cooling does the opposite."""
    if not cfg.use_monotonic_constraints:
        return None
    heating = target == "useful_space_heating_kwh_per_m2"
    mapping: dict[str, int] = {
        "outdoor_temperature_c": -1 if heating else 1,
        "heating_setpoint_minus_outdoor_k": 1 if heating else 0,
        "outdoor_minus_cooling_setpoint_k": 0 if heating else 1,
        "heating_ua_drive_w_per_m2": 1 if heating else 0,
        "cooling_ua_drive_w_per_m2": 0 if heating else 1,
    }
    return [int(mapping.get(name, 0)) for name in features]


def _load_dataset() -> tuple[pd.DataFrame, list[str]]:
    """Read registered teacher output and derive calendar features without target leakage."""
    cfg = _config()
    path = _dataset_dir() / f"building_teacher_{cfg.experiment_id}_cohort_hourly.csv.gz"
    data = pd.read_csv(path, parse_dates=["timestamp_local"])
    required = {
        "cohort_id",
        "cohort_represented_gfa_m2",
        "space_heating_kwh",
        "cooling_kwh",
        "outdoor_temperature_c",
        "heating_setpoint_c",
        "cooling_setpoint_c",
        "internal_gains_w_m2",
        "infiltration_ach",
        "ventilation_ach",
        "epw_ghi_wh_m2",
        "epw_dni_wh_m2",
        "epw_dhi_wh_m2",
    }
    missing = sorted(required - set(data.columns))
    if missing:
        raise KeyError(f"[annual_demand_surrogate] Teacher bridge is missing columns: {missing}")
    if data["cohort_id"].nunique() < 4 or len(data) != 8 * 8760:
        raise ValueError("[annual_demand_surrogate] Expected eight complete annual cohort teacher runs.")
    if data.duplicated(["cohort_id", "timestamp_local"]).any():
        raise ValueError("[annual_demand_surrogate] Duplicate cohort/timestamp teacher rows.")
    data = data.merge(_cohort_features(), on="cohort_id", how="left", validate="many_to_one")
    if data.isna().any().any():
        raise ValueError("[annual_demand_surrogate] Missing values after cohort-context merge.")
    data["calendar_week"] = data["timestamp_local"].dt.isocalendar().week.astype(int)
    data["hour_sin"] = np.sin(2.0 * np.pi * data["timestamp_local"].dt.hour / 24.0)
    data["hour_cos"] = np.cos(2.0 * np.pi * data["timestamp_local"].dt.hour / 24.0)
    data["day_sin"] = np.sin(2.0 * np.pi * (data["timestamp_local"].dt.dayofyear - 1) / 365.0)
    data["day_cos"] = np.cos(2.0 * np.pi * (data["timestamp_local"].dt.dayofyear - 1) / 365.0)
    for target, raw_column in TARGETS.items():
        data[target] = pd.to_numeric(data[raw_column], errors="raise") / pd.to_numeric(
            data["cohort_represented_gfa_m2"], errors="raise"
        )
    extra = _add_drive_features(data, cfg)
    cohort_columns = list(pd.get_dummies(data["cohort_id"], prefix="cohort", dtype=float).columns)
    data = pd.concat([data, pd.get_dummies(data["cohort_id"], prefix="cohort", dtype=float)], axis=1)
    features = [
        "outdoor_temperature_c",
        "heating_setpoint_c",
        "cooling_setpoint_c",
        "internal_gains_w_m2",
        "infiltration_ach",
        "ventilation_ach",
        "epw_ghi_wh_m2",
        "epw_dni_wh_m2",
        "epw_dhi_wh_m2",
        "hour_sin",
        "hour_cos",
        "day_sin",
        "day_cos",
        "is_residential",
        "u_wall",
        "u_window",
        "u_roof",
        "u_floor",
        "wall_area_per_m2",
        "window_area_per_m2",
        "roof_area_per_m2",
        "floor_exposed_per_m2",
        "heat_capacity_wh_per_m2k",
        *extra,
        *cohort_columns,
    ]
    missing_features = [name for name in features if name not in data.columns]
    if missing_features:
        raise KeyError(f"[annual_demand_surrogate] Derived feature columns missing: {missing_features}")
    return data.sort_values(["cohort_id", "timestamp_local"]).reset_index(drop=True), features


def _make_model(*, monotonic_cst: list[int] | None = None) -> HistGradientBoostingRegressor:
    """Magnitude emulator. Optional monotonic_cst is aligned with `features` order."""
    cfg = _config()
    kwargs: dict[str, object] = {
        "max_iter": cfg.max_iter,
        "learning_rate": cfg.learning_rate,
        "max_leaf_nodes": cfg.max_leaf_nodes,
        "l2_regularization": cfg.l2_regularization,
        "random_state": cfg.random_state,
    }
    if monotonic_cst is not None:
        kwargs["monotonic_cst"] = monotonic_cst
    return HistGradientBoostingRegressor(**kwargs)


def _make_gate(*, monotonic_cst: list[int] | None = None) -> HistGradientBoostingClassifier:
    cfg = _config()
    kwargs: dict[str, object] = {
        "max_iter": cfg.classifier_max_iter,
        "learning_rate": cfg.classifier_learning_rate,
        "max_leaf_nodes": cfg.classifier_max_leaf_nodes,
        "l2_regularization": cfg.classifier_l2_regularization,
        "random_state": cfg.random_state,
    }
    if monotonic_cst is not None:
        kwargs["monotonic_cst"] = monotonic_cst
    return HistGradientBoostingClassifier(**kwargs)


def _metric_block(y_true: np.ndarray, y_pred: np.ndarray) -> dict[str, float]:
    return {
        "mae_kwh_per_m2": float(mean_absolute_error(y_true, y_pred)),
        "rmse_kwh_per_m2": float(mean_squared_error(y_true, y_pred) ** 0.5),
        "r2": float(r2_score(y_true, y_pred)),
    }


def _balanced_class_weights(on: np.ndarray) -> np.ndarray:
    n = int(len(on))
    n_on = int(on.sum())
    n_off = n - n_on
    if n_on <= 0 or n_off <= 0:
        raise ValueError("[annual_demand_surrogate] A train fold has no on-hours or no off-hours; cannot fit the gate.")
    weights = np.empty(n, dtype=float)
    weights[on] = n / (2.0 * n_on)
    weights[~on] = n / (2.0 * n_off)
    return weights


def _magnitude_sample_weights(y: np.ndarray, cfg: BuildingDemandSurrogateConfig) -> np.ndarray:
    """Upweight cold peaks and small-positive shoulder hours. Zeros stay at 1.0.

    v2 first used only a shoulder boost, so winter peaks kept weight 1 and were
    under-fit. Peak hours are the top quantile of on-hours in the train fold.
    """
    if cfg.peak_quantile <= 0.0 or cfg.peak_quantile >= 1.0:
        raise ValueError("[annual_demand_surrogate] peak_quantile must lie in (0, 1).")
    weights = np.ones(len(y), dtype=float)
    on = y > cfg.on_threshold_kwh_per_m2
    if int(on.sum()) == 0:
        raise ValueError("[annual_demand_surrogate] Train fold has no positive demand hours.")
    median_positive = float(np.median(y[on]))
    peak_cut = float(np.quantile(y[on], cfg.peak_quantile))
    if cfg.shoulder_weight_boost > 0.0:
        small = on & (y <= median_positive)
        weights[small] = 1.0 + float(cfg.shoulder_weight_boost)
    if cfg.peak_weight_boost > 0.0:
        peak = on & (y >= peak_cut)
        if int(peak.sum()) == 0:
            raise ValueError("[annual_demand_surrogate] Peak mask is empty despite positive demand.")
        weights[peak] = 1.0 + float(cfg.peak_weight_boost)
    return weights


def _physical_off_leak_mask(frame: pd.DataFrame, target: str, cfg: BuildingDemandSurrogateConfig) -> np.ndarray:
    """True-off hours that are also on the physically off side of the setpoint drive.

    Heating leak is only penalised when outdoor air is already at or above the
    heating setpoint. Cooling leak is only penalised when outdoor air is at or
    below the heating setpoint. That cuts June heating without forcing the gate
    to zero genuine April/October hours near the switch.
    """
    y = frame[target].to_numpy(dtype=float)
    zero = y <= cfg.on_threshold_kwh_per_m2
    if target == "useful_space_heating_kwh_per_m2":
        drive_off = frame["heating_setpoint_minus_outdoor_k"].to_numpy(dtype=float) <= 0.0
    elif target == "useful_cooling_kwh_per_m2":
        drive_off = frame["heating_setpoint_minus_outdoor_k"].to_numpy(dtype=float) >= 0.0
    else:
        raise KeyError(f"[annual_demand_surrogate] No physical-off rule for target '{target}'.")
    return zero & drive_off


def _select_gate_threshold(
    *,
    y_true: np.ndarray,
    magnitude: np.ndarray,
    on_probability: np.ndarray,
    leak_mask: np.ndarray,
    cfg: BuildingDemandSurrogateConfig,
) -> float:
    """Pick the train-fold gate that keeps true-on energy while cutting physically-off leak."""
    if not cfg.gate_threshold_grid:
        raise ValueError("[annual_demand_surrogate] gate_threshold_grid must not be empty.")
    if leak_mask.shape != y_true.shape:
        raise ValueError("[annual_demand_surrogate] leak_mask length does not match y_true.")
    annual_truth = float(y_true.sum())
    if annual_truth <= 0.0:
        raise ValueError("[annual_demand_surrogate] Train fold annual truth is not > 0.")
    on = y_true > cfg.on_threshold_kwh_per_m2
    on_energy = float(y_true[on].sum())
    if on_energy <= 0.0:
        raise ValueError("[annual_demand_surrogate] Train fold has no on-hour energy.")
    best_threshold: float | None = None
    best_score = -np.inf
    for threshold in cfg.gate_threshold_grid:
        pred = np.where(on_probability >= float(threshold), magnitude, 0.0)
        recall = float(pred[on].sum()) / on_energy
        leak_fraction = float(pred[leak_mask].sum()) / annual_truth
        score = recall - float(cfg.gate_offseason_leak_penalty) * leak_fraction
        if score > best_score:
            best_score = score
            best_threshold = float(threshold)
    if best_threshold is None:
        raise RuntimeError("[annual_demand_surrogate] Gate threshold selection produced no candidate.")
    return best_threshold


def _apply_hurdle(magnitude: np.ndarray, on_probability: np.ndarray, threshold: float) -> np.ndarray:
    return np.where(on_probability >= threshold, np.maximum(magnitude, 0.0), 0.0)


def _cross_validate(data: pd.DataFrame, features: list[str], target: str) -> tuple[np.ndarray, dict[str, object]]:
    """Hold out full calendar weeks while retaining the fixed registered Vienna cohort set."""
    cfg = _config()
    x = data.loc[:, features].to_numpy(dtype=float)
    y = data[target].to_numpy(dtype=float)
    groups = data["calendar_week"].to_numpy()
    prediction = np.zeros(len(data), dtype=float)
    monotonic = _monotonic_cst(features, target, cfg)
    fold_thresholds: list[float] = []
    n_fold = 0
    for train_idx, test_idx in GroupKFold(n_splits=cfg.n_splits).split(x, y, groups):
        n_fold += 1
        print(f"[annual_demand_surrogate] {target} fold {n_fold}/{cfg.n_splits}", flush=True)
        x_train, y_train = x[train_idx], y[train_idx]
        magnitude_model = _make_model(monotonic_cst=monotonic)
        magnitude_model.fit(x_train, y_train, sample_weight=_magnitude_sample_weights(y_train, cfg))
        magnitude_test = magnitude_model.predict(x[test_idx])
        if cfg.use_on_off_gate:
            on_train = y_train > cfg.on_threshold_kwh_per_m2
            gate = _make_gate(monotonic_cst=monotonic)
            gate.fit(x_train, on_train.astype(int), sample_weight=_balanced_class_weights(on_train))
            proba_train = gate.predict_proba(x_train)[:, 1]
            magnitude_train = np.maximum(magnitude_model.predict(x_train), 0.0)
            leak_mask = _physical_off_leak_mask(data.iloc[train_idx], target, cfg)
            threshold = _select_gate_threshold(
                y_true=y_train,
                magnitude=magnitude_train,
                on_probability=proba_train,
                leak_mask=leak_mask,
                cfg=cfg,
            )
            fold_thresholds.append(threshold)
            print(f"[annual_demand_surrogate] {target} fold {n_fold} gate_threshold={threshold:.2f}", flush=True)
            proba_test = gate.predict_proba(x[test_idx])[:, 1]
            prediction[test_idx] = _apply_hurdle(magnitude_test, proba_test, threshold)
        else:
            prediction[test_idx] = np.maximum(magnitude_test, 0.0)
    by_cohort: list[dict[str, object]] = []
    for cohort_id, group in data.assign(prediction=prediction).groupby("cohort_id", sort=True):
        true_total = float(group[target].sum())
        predicted_total = float(group["prediction"].sum())
        by_cohort.append(
            {
                "cohort_id": str(cohort_id),
                "truth_annual_kwh_per_m2": true_total,
                "predicted_annual_kwh_per_m2": predicted_total,
                "annual_relative_error": (predicted_total - true_total) / true_total if true_total > 0.0 else None,
            }
        )
    extra: dict[str, object] = {"hourly": _metric_block(y, prediction), "annual_by_cohort": by_cohort}
    if fold_thresholds:
        extra["gate_thresholds_by_fold"] = fold_thresholds
    return prediction, extra


def _fit_deployed_bundle(x: np.ndarray, y: np.ndarray, features: list[str], target: str) -> dict[str, object]:
    """Full-data hurdle used at inference. Threshold is selected on the same full-data fit."""
    cfg = _config()
    monotonic = _monotonic_cst(features, target, cfg)
    magnitude_model = _make_model(monotonic_cst=monotonic)
    magnitude_model.fit(x, y, sample_weight=_magnitude_sample_weights(y, cfg))
    bundle: dict[str, object] = {
        "schema": cfg.schema_version,
        "model": magnitude_model,
        "feature_columns": features,
        "target": target,
        "use_on_off_gate": cfg.use_on_off_gate,
        "on_threshold_kwh_per_m2": cfg.on_threshold_kwh_per_m2,
    }
    if cfg.use_on_off_gate:
        on = y > cfg.on_threshold_kwh_per_m2
        gate = _make_gate(monotonic_cst=monotonic)
        gate.fit(x, on.astype(int), sample_weight=_balanced_class_weights(on))
        magnitude = np.maximum(magnitude_model.predict(x), 0.0)
        leak_frame = pd.DataFrame({target: y, "heating_setpoint_minus_outdoor_k": x[:, features.index("heating_setpoint_minus_outdoor_k")]})
        threshold = _select_gate_threshold(
            y_true=y,
            magnitude=magnitude,
            on_probability=gate.predict_proba(x)[:, 1],
            leak_mask=_physical_off_leak_mask(leak_frame, target, cfg),
            cfg=cfg,
        )
        bundle["gate"] = gate
        bundle["gate_threshold"] = threshold
    return bundle


def predict_demand_bundle(bundle: dict[str, object], x: np.ndarray) -> np.ndarray:
    """Apply a dumped v2 hurdle bundle. Missing gate keys are an error when the flag is on."""
    magnitude = np.asarray(bundle["model"].predict(x), dtype=float)
    if not bool(bundle.get("use_on_off_gate", False)):
        return np.maximum(magnitude, 0.0)
    if "gate" not in bundle or "gate_threshold" not in bundle:
        raise KeyError("[annual_demand_surrogate] Hurdle bundle is missing gate or gate_threshold.")
    proba = np.asarray(bundle["gate"].predict_proba(x)[:, 1], dtype=float)
    return _apply_hurdle(magnitude, proba, float(bundle["gate_threshold"]))


def _city_profile_validation(oof: pd.DataFrame) -> tuple[dict[str, object], pd.DataFrame]:
    """Report city energy and peak fidelity, which matters more than per-row fit in PyPSA."""
    summaries: dict[str, object] = {}
    monthly_rows: list[pd.DataFrame] = []
    for target in TARGETS:
        truth = f"truth__{target}"
        prediction = f"prediction__{target}"
        frame = oof.loc[:, ["timestamp_local", "cohort_represented_gfa_m2", truth, prediction]].copy()
        frame["truth_kwh"] = frame[truth] * frame["cohort_represented_gfa_m2"]
        frame["prediction_kwh"] = frame[prediction] * frame["cohort_represented_gfa_m2"]
        city = frame.groupby("timestamp_local", as_index=False)[["truth_kwh", "prediction_kwh"]].sum()
        truth_total = float(city["truth_kwh"].sum())
        predicted_total = float(city["prediction_kwh"].sum())
        month = city["timestamp_local"].dt.month
        # Off-season for heating is JJA; for cooling is DJF. Leak is predicted energy while truth is ~0.
        if target == "useful_space_heating_kwh_per_m2":
            off_mask = month.isin([6, 7, 8])
        else:
            off_mask = month.isin([12, 1, 2])
        off_truth = float(city.loc[off_mask, "truth_kwh"].sum())
        off_pred = float(city.loc[off_mask, "prediction_kwh"].sum())
        summaries[target] = {
            "annual_relative_error": (predicted_total - truth_total) / truth_total,
            "peak_relative_error": (float(city["prediction_kwh"].max()) - float(city["truth_kwh"].max()))
            / float(city["truth_kwh"].max()),
            "hourly_correlation": float(city["truth_kwh"].corr(city["prediction_kwh"])),
            "offseason_truth_kwh": off_truth,
            "offseason_prediction_kwh": off_pred,
        }
        city["month"] = month
        monthly = city.groupby("month", as_index=False)[["truth_kwh", "prediction_kwh"]].sum()
        monthly["target"] = target
        monthly_rows.append(monthly)
    return summaries, pd.concat(monthly_rows, ignore_index=True)


def main() -> None:
    cfg = _config()
    if cfg.on_threshold_kwh_per_m2 < 0.0:
        raise ValueError("[annual_demand_surrogate] on_threshold_kwh_per_m2 must be >= 0.")
    if cfg.n_splits < 2:
        raise ValueError("[annual_demand_surrogate] n_splits must be >= 2.")
    if cfg.peak_weight_boost < 0.0 or cfg.shoulder_weight_boost < 0.0:
        raise ValueError("[annual_demand_surrogate] sample-weight boosts must be >= 0.")
    data, features = _load_dataset()
    out_dir = _model_dir(cfg)
    out_dir.mkdir(parents=True, exist_ok=True)
    validation: dict[str, object] = {}
    oof = data.loc[:, ["timestamp_local", "cohort_id", "cohort_represented_gfa_m2"]].copy()
    x_all = data.loc[:, features].to_numpy(dtype=float)
    for target in TARGETS:
        print(f"[annual_demand_surrogate] {target}: start holdout", flush=True)
        prediction, result = _cross_validate(data, features, target)
        validation[target] = result
        oof[f"truth__{target}"] = data[target]
        oof[f"prediction__{target}"] = prediction
        print(f"[annual_demand_surrogate] {target}: fit deployed bundle", flush=True)
        bundle = _fit_deployed_bundle(x_all, data[target].to_numpy(dtype=float), features, target)
        dump(bundle, out_dir / f"{target}.joblib")
    oof.to_csv(out_dir / "holdout_predictions.csv.gz", index=False, compression="gzip")
    city_validation, monthly_validation = _city_profile_validation(oof)
    monthly_validation.to_csv(out_dir / "city_monthly_profile_validation.csv", index=False)
    manifest = {
        "schema_version": cfg.schema_version,
        "compatibility_family": "vienna_building_demand_surrogate_v2",
        "teacher_experiment": cfg.experiment_id,
        "source_dataset": str(_dataset_dir() / f"building_teacher_{cfg.experiment_id}_cohort_hourly.csv.gz"),
        "n_rows": int(len(data)),
        "n_cohorts": int(data["cohort_id"].nunique()),
        "feature_columns": features,
        "targets": list(TARGETS),
        "training": {
            "use_on_off_gate": cfg.use_on_off_gate,
            "use_setpoint_drive_features": cfg.use_setpoint_drive_features,
            "use_ua_drive_features": cfg.use_ua_drive_features,
            "use_monotonic_constraints": cfg.use_monotonic_constraints,
            "shoulder_weight_boost": cfg.shoulder_weight_boost,
            "peak_weight_boost": cfg.peak_weight_boost,
            "peak_quantile": cfg.peak_quantile,
            "gate_offseason_leak_penalty": cfg.gate_offseason_leak_penalty,
            "max_iter": cfg.max_iter,
            "max_leaf_nodes": cfg.max_leaf_nodes,
        },
        "scope": (
            "EnergyPlus-emulating useful heat/cooling profile surrogate for the fixed registered "
            "Vienna cohort set; no building flexibility or load shifting."
        ),
        "annual_anchor_rule": "Predicted raw profiles must be normalized before applying scenario-owned annual demand anchors.",
        "validation": {"scheme": "four-fold full-calendar-week holdout", "city_profile": city_validation, **validation},
        "status": "active_demand_path_for_mes_profile_emulation",
    }
    (out_dir / "model_manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(out_dir / "model_manifest.json")
    for target, block in city_validation.items():
        print(target, json.dumps(block))


if __name__ == "__main__":
    main()
