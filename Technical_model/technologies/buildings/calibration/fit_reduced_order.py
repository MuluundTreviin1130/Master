from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

from Settings.technical.building_calibration import make_building_calibration_config
from Technical_model.technologies.buildings.calibration.schemas import CalibrationReducedOrderFitResult


_REQUIRED_HOURLY_COLUMNS = (
    "timestamp_local",
    "zone_mean_air_temperature_c",
    "site_outdoor_air_drybulb_c",
    "zone_total_heating_rate_w",
    "internal_gains_total_w",
    "zone_windows_total_heat_gain_rate_w",
    "teacher_outdoor_air_loss_w",
    "teacher_infiltration_sensible_heat_loss_w",
    "approx_infiltration_loss_w",
    "approx_ventilation_loss_w",
)


def _require_existing_file(path: Path, *, label: str) -> Path:
    resolved = path.resolve()
    if not resolved.exists():
        raise FileNotFoundError(f"[building_calibration.fit_reduced_order] Missing {label}: {resolved}")
    if not resolved.is_file():
        raise FileNotFoundError(
            f"[building_calibration.fit_reduced_order] Expected file for {label}, got: {resolved}"
        )
    return resolved


def _load_json(path: Path, *, label: str) -> dict:
    resolved = _require_existing_file(path, label=label)
    return json.loads(resolved.read_text(encoding="utf-8"))


def _load_teacher_bundle_index() -> dict[str, dict]:
    cfg = make_building_calibration_config()
    payload = _load_json(Path(cfg.teacher_input_output_json), label="teacher_input_output_json")
    cohorts = payload.get("cohorts", [])
    by_id: dict[str, dict] = {}
    for cohort in cohorts:
        cohort_id = str(cohort["cohort_id"])
        if cohort_id in by_id:
            raise ValueError(
                f"[building_calibration.fit_reduced_order] Duplicate cohort_id in teacher bundle: {cohort_id}"
            )
        by_id[cohort_id] = dict(cohort)
    return by_id


def _load_run_artifacts(*, cohort_id: str, experiment_id: str) -> tuple[pd.DataFrame, dict]:
    cfg = make_building_calibration_config()
    run_dir = Path(cfg.teacher_runs_output_dir).resolve() / cohort_id / experiment_id
    if not run_dir.exists():
        raise FileNotFoundError(
            "[building_calibration.fit_reduced_order] Missing teacher run directory for "
            f"cohort='{cohort_id}', experiment='{experiment_id}': {run_dir}"
        )

    hourly_path = _require_existing_file(
        run_dir / str(cfg.teacher_plausibility_hourly_filename),
        label=f"plausibility_hourly[{cohort_id}/{experiment_id}]",
    )
    summary_path = _require_existing_file(
        run_dir / str(cfg.teacher_plausibility_summary_filename),
        label=f"plausibility_summary[{cohort_id}/{experiment_id}]",
    )

    hourly = pd.read_csv(hourly_path, parse_dates=["timestamp_local"])
    missing = [col for col in _REQUIRED_HOURLY_COLUMNS if col not in hourly.columns]
    if missing:
        raise KeyError(
            "[building_calibration.fit_reduced_order] Teacher plausibility hourly file is missing columns "
            f"for cohort='{cohort_id}', experiment='{experiment_id}': {missing}"
        )
    hourly = hourly.sort_values("timestamp_local").reset_index(drop=True)
    summary = _load_json(summary_path, label=f"plausibility_summary[{cohort_id}/{experiment_id}]")
    return hourly, summary


def _fit_nonnegative_two_feature_model(x1: np.ndarray, x2: np.ndarray, y: np.ndarray) -> tuple[float, float]:
    if x1.shape != x2.shape or x1.shape != y.shape:
        raise ValueError("[building_calibration.fit_reduced_order] Regression arrays must share the same shape.")
    X = np.column_stack([x1, x2])
    beta, *_ = np.linalg.lstsq(X, y, rcond=None)
    beta = np.asarray(beta, dtype=float)
    if beta.shape != (2,):
        raise ValueError("[building_calibration.fit_reduced_order] Unexpected regression coefficient shape.")
    if (beta >= 0.0).all():
        return float(beta[0]), float(beta[1])

    candidates: list[tuple[float, float]] = []
    denom_1 = float(np.dot(x1, x1))
    denom_2 = float(np.dot(x2, x2))
    a_only = max(0.0, float(np.dot(x1, y) / denom_1)) if denom_1 > 0.0 else 0.0
    b_only = max(0.0, float(np.dot(x2, y) / denom_2)) if denom_2 > 0.0 else 0.0
    candidates.append((a_only, 0.0))
    candidates.append((0.0, b_only))
    candidates.append((0.0, 0.0))

    best = None
    best_sse = None
    for a, b in candidates:
        residual = y - (a * x1 + b * x2)
        sse = float(np.dot(residual, residual))
        if best is None or sse < best_sse:
            best = (a, b)
            best_sse = sse
    if best is None:
        raise RuntimeError("[building_calibration.fit_reduced_order] Could not resolve nonnegative fit candidate.")
    return best


def _fit_loss_decomposition(
    reference_df: pd.DataFrame,
    *,
    seed_ua_w_per_k: float,
) -> tuple[float, float, float, float, float, float, int]:
    delta_t = reference_df["zone_mean_air_temperature_c"] - reference_df["site_outdoor_air_drybulb_c"]
    heating = reference_df["zone_total_heating_rate_w"]
    gains = reference_df["internal_gains_total_w"] + reference_df["zone_windows_total_heat_gain_rate_w"]
    valid = (delta_t > 1e-9) & (heating > 1e-9)
    n_valid = int(valid.sum())
    if n_valid < 24:
        raise ValueError(
            "[building_calibration.fit_reduced_order] Need at least 24 valid heated hours to fit "
            f"the total loss coefficient, got {n_valid}."
        )

    x_trans = reference_df.loc[valid, "approx_transmission_loss_seed_ua_w"].to_numpy(dtype=float)
    x_air_direct = reference_df.loc[valid, "teacher_outdoor_air_loss_w"].to_numpy(dtype=float)
    y = (heating.loc[valid] + gains.loc[valid]).to_numpy(dtype=float)

    if (x_trans <= 0.0).any():
        raise ValueError(
            "[building_calibration.fit_reduced_order] approx_transmission_loss_seed_ua_w must stay > 0 "
            "for the fitted reference hours."
        )
    if (x_air_direct < 0.0).any():
        raise ValueError(
            "[building_calibration.fit_reduced_order] Direct teacher outdoor-air losses must stay >= 0 "
            "for the fitted reference hours."
        )
    y_minus_direct_air = y - x_air_direct
    denom_trans = float(np.dot(x_trans, x_trans))
    if denom_trans <= 0.0:
        raise ValueError(
            "[building_calibration.fit_reduced_order] Degenerate transmission regression denominator."
        )
    transmission_scale = max(0.0, float(np.dot(x_trans, y_minus_direct_air) / denom_trans))
    transmission_coeff = transmission_scale * seed_ua_w_per_k
    if transmission_coeff <= 0.0:
        raise ValueError(
            "[building_calibration.fit_reduced_order] Fitted transmission coefficient must be > 0, "
            f"got {transmission_coeff}."
        )
    direct_outdoor_air_coeff = _mean_loss_coefficient(
        reference_df["teacher_outdoor_air_loss_w"],
        delta_t,
        label="teacher outdoor-air loss coefficient",
    )
    direct_infiltration_coeff = _mean_loss_coefficient(
        reference_df["teacher_infiltration_sensible_heat_loss_w"],
        delta_t,
        label="teacher infiltration loss coefficient",
    )
    if direct_infiltration_coeff > direct_outdoor_air_coeff + 1e-9:
        raise ValueError(
            "[building_calibration.fit_reduced_order] Direct teacher infiltration coefficient cannot exceed "
            "the direct total outdoor-air coefficient."
        )
    infiltration_seed = _mean_loss_coefficient(
        reference_df["approx_infiltration_loss_w"],
        delta_t,
        label="infiltration loss coefficient",
    )
    ventilation_seed = _mean_loss_coefficient(
        reference_df["approx_ventilation_loss_w"],
        delta_t,
        label="ventilation loss coefficient",
    )
    infiltration_coeff = direct_infiltration_coeff
    ventilation_coeff = max(0.0, direct_outdoor_air_coeff - direct_infiltration_coeff)
    seed_air_total_coeff = infiltration_seed + ventilation_seed
    air_scale = direct_outdoor_air_coeff / max(seed_air_total_coeff, 1e-9)
    total_coeff = transmission_coeff + infiltration_coeff + ventilation_coeff
    return transmission_coeff, ventilation_coeff, infiltration_coeff, total_coeff, transmission_scale, air_scale, n_valid


def _mean_loss_coefficient(loss_w: pd.Series, delta_t_c: pd.Series, *, label: str) -> float:
    valid = delta_t_c > 1e-9
    if int(valid.sum()) == 0:
        raise ValueError(
            f"[building_calibration.fit_reduced_order] Cannot estimate {label}; no valid positive delta-T hours."
        )
    coeff = float((loss_w.loc[valid] / delta_t_c.loc[valid]).mean())
    if coeff < 0.0:
        raise ValueError(
            f"[building_calibration.fit_reduced_order] Estimated {label} must be >= 0, got {coeff}."
        )
    return coeff


def _fit_effective_heat_capacity(*, free_float_df: pd.DataFrame, h_total_w_per_k: float) -> tuple[float, int]:
    tin = free_float_df["zone_mean_air_temperature_c"].to_numpy(dtype=float)
    tout = free_float_df["site_outdoor_air_drybulb_c"].to_numpy(dtype=float)
    gains = (
        free_float_df["internal_gains_total_w"] + free_float_df["zone_windows_total_heat_gain_rate_w"]
    ).to_numpy(dtype=float)

    if len(tin) < 2:
        raise ValueError("[building_calibration.fit_reduced_order] Free-float run must contain at least 2 rows.")

    forcing_w = -(h_total_w_per_k * (tin[:-1] - tout[:-1])) + gains[:-1]
    delta_temp_c = tin[1:] - tin[:-1]
    valid = np.abs(forcing_w) > 1e-9
    n_valid = int(valid.sum())
    if n_valid < 12:
        raise ValueError(
            "[building_calibration.fit_reduced_order] Need at least 12 valid free-float transitions to fit "
            f"effective heat capacity, got {n_valid}."
        )

    x = forcing_w[valid]
    y = delta_temp_c[valid]
    denominator = float(np.dot(x, x))
    if denominator <= 0.0:
        raise ValueError("[building_calibration.fit_reduced_order] Degenerate free-float regression denominator.")
    alpha = float(np.dot(x, y) / denominator)
    if alpha <= 0.0:
        raise ValueError(
            "[building_calibration.fit_reduced_order] Fitted inverse heat capacity must be > 0, "
            f"got {alpha}."
        )

    c_eff = 1.0 / alpha
    if c_eff <= 0.0:
        raise ValueError(
            "[building_calibration.fit_reduced_order] Fitted effective heat capacity must be > 0, "
            f"got {c_eff}."
        )
    return c_eff, n_valid


def _compute_error_metrics(actual: np.ndarray, predicted: np.ndarray) -> tuple[float, float]:
    if actual.shape != predicted.shape:
        raise ValueError("[building_calibration.fit_reduced_order] Error metric arrays must share the same shape.")
    error = predicted - actual
    rmse = float(np.sqrt(np.mean(np.square(error))))
    mae = float(np.mean(np.abs(error)))
    return rmse, mae


def _simulate_free_float(
    *,
    free_float_df: pd.DataFrame,
    h_total_w_per_k: float,
    c_eff_wh_per_k: float,
) -> np.ndarray:
    tin_obs = free_float_df["zone_mean_air_temperature_c"].to_numpy(dtype=float)
    tout = free_float_df["site_outdoor_air_drybulb_c"].to_numpy(dtype=float)
    gains = (
        free_float_df["internal_gains_total_w"] + free_float_df["zone_windows_total_heat_gain_rate_w"]
    ).to_numpy(dtype=float)
    predicted = np.empty_like(tin_obs)
    predicted[0] = tin_obs[0]
    for idx in range(len(predicted) - 1):
        net_power_w = -(h_total_w_per_k * (predicted[idx] - tout[idx])) + gains[idx]
        predicted[idx + 1] = predicted[idx] + net_power_w / c_eff_wh_per_k
    return predicted


def fit_reduced_order_for_cohort(
    *,
    cohort_id: str,
    reference_experiment_id: str | None = None,
    free_float_experiment_id: str | None = None,
) -> CalibrationReducedOrderFitResult:
    cfg = make_building_calibration_config()
    resolved_reference = str(
        reference_experiment_id or cfg.reduced_order_fit_default_reference_experiment_id
    ).strip()
    resolved_free_float = str(
        free_float_experiment_id or cfg.reduced_order_fit_default_free_float_experiment_id
    ).strip()
    resolved_cohort = str(cohort_id).strip()
    if not resolved_cohort:
        raise ValueError("[building_calibration.fit_reduced_order] cohort_id must be a non-empty string.")
    if not resolved_reference:
        raise ValueError("[building_calibration.fit_reduced_order] reference_experiment_id must be non-empty.")
    if not resolved_free_float:
        raise ValueError("[building_calibration.fit_reduced_order] free_float_experiment_id must be non-empty.")

    cohorts = _load_teacher_bundle_index()
    if resolved_cohort not in cohorts:
        raise KeyError(f"[building_calibration.fit_reduced_order] Unknown cohort_id='{resolved_cohort}'.")

    reference_df, reference_summary = _load_run_artifacts(
        cohort_id=resolved_cohort,
        experiment_id=resolved_reference,
    )
    free_float_df, free_float_summary = _load_run_artifacts(
        cohort_id=resolved_cohort,
        experiment_id=resolved_free_float,
    )

    reference_area_m2 = float(reference_summary["reference_conditioned_floor_m2"])
    if reference_area_m2 <= 0.0:
        raise ValueError(
            "[building_calibration.fit_reduced_order] reference_conditioned_floor_m2 must be > 0, "
            f"got {reference_area_m2}."
        )

    seed_ua_w_per_k = float(reference_summary["seed_ua_reference_w_per_k"])
    if seed_ua_w_per_k <= 0.0:
        raise ValueError(
            "[building_calibration.fit_reduced_order] seed_ua_reference_w_per_k must be > 0, "
            f"got {seed_ua_w_per_k}."
        )

    (
        transmission_w_per_k,
        vent_coeff,
        infil_coeff,
        h_total_w_per_k,
        transmission_scale,
        air_scale,
        n_reference,
    ) = _fit_loss_decomposition(
        reference_df,
        seed_ua_w_per_k=seed_ua_w_per_k,
    )
    reference_delta_t = reference_df["zone_mean_air_temperature_c"] - reference_df["site_outdoor_air_drybulb_c"]

    c_eff_wh_per_k, n_free_float = _fit_effective_heat_capacity(
        free_float_df=free_float_df,
        h_total_w_per_k=h_total_w_per_k,
    )
    tau_h = c_eff_wh_per_k / h_total_w_per_k

    ref_delta_t_np = reference_delta_t.to_numpy(dtype=float)
    ref_gains_np = (
        reference_df["internal_gains_total_w"] + reference_df["zone_windows_total_heat_gain_rate_w"]
    ).to_numpy(dtype=float)
    ref_heating_pred = np.maximum(0.0, h_total_w_per_k * ref_delta_t_np - ref_gains_np)
    ref_heating_actual = reference_df["zone_total_heating_rate_w"].to_numpy(dtype=float)
    reference_rmse_w, reference_mae_w = _compute_error_metrics(ref_heating_actual, ref_heating_pred)

    free_float_pred = _simulate_free_float(
        free_float_df=free_float_df,
        h_total_w_per_k=h_total_w_per_k,
        c_eff_wh_per_k=c_eff_wh_per_k,
    )
    free_float_actual = free_float_df["zone_mean_air_temperature_c"].to_numpy(dtype=float)
    free_float_rmse_c, free_float_mae_c = _compute_error_metrics(free_float_actual, free_float_pred)

    seed_heat_capacity_wh_per_k = float(reference_summary["heat_capacity_reference_wh_per_m2k"]) * reference_area_m2
    if seed_heat_capacity_wh_per_k <= 0.0:
        raise ValueError(
            "[building_calibration.fit_reduced_order] seed heat capacity must be > 0, "
            f"got {seed_heat_capacity_wh_per_k}."
        )

    return CalibrationReducedOrderFitResult(
        cohort_id=resolved_cohort,
        reference_experiment_id=resolved_reference,
        free_float_experiment_id=resolved_free_float,
        reference_hours_used=n_reference,
        free_float_steps_used=n_free_float,
        fitted_total_loss_coefficient_w_per_k=h_total_w_per_k,
        fitted_transmission_loss_coefficient_w_per_k=transmission_w_per_k,
        fitted_ventilation_loss_coefficient_w_per_k_approx=vent_coeff,
        fitted_infiltration_loss_coefficient_w_per_k_approx=infil_coeff,
        fitted_effective_heat_capacity_wh_per_k=c_eff_wh_per_k,
        fitted_tau_h=tau_h,
        fitted_total_loss_coefficient_w_per_m2k=h_total_w_per_k / reference_area_m2,
        fitted_transmission_loss_coefficient_w_per_m2k=transmission_w_per_k / reference_area_m2,
        fitted_effective_heat_capacity_wh_per_m2k=c_eff_wh_per_k / reference_area_m2,
        fitted_transmission_scale_vs_seed=transmission_scale,
        fitted_air_loss_scale_vs_seed_approx=air_scale,
        seed_ua_reference_w_per_k=seed_ua_w_per_k,
        seed_heat_capacity_wh_per_k=seed_heat_capacity_wh_per_k,
        total_loss_vs_seed_ua_ratio=h_total_w_per_k / seed_ua_w_per_k,
        transmission_vs_seed_ua_ratio=transmission_w_per_k / seed_ua_w_per_k,
        heat_capacity_vs_seed_ratio=c_eff_wh_per_k / seed_heat_capacity_wh_per_k,
        reference_heating_rmse_w=reference_rmse_w,
        reference_heating_mae_w=reference_mae_w,
        free_float_temperature_rmse_c=free_float_rmse_c,
        free_float_temperature_mae_c=free_float_mae_c,
        notes=[
            "Reference heating is decomposed into seed transmission loss and approximate air-side loss, then fitted with a nonnegative two-feature model.",
            "Transmission scale is applied to the seed UA term; air-side scale is applied to the approximate infiltration and ventilation losses.",
            "Effective heat capacity is fitted from the free-float trajectory using the already fitted total loss coefficient and observed gains.",
            "Recovery/Rebound parameters are intentionally not fitted here yet; those need event experiments beyond reference + free_float.",
        ],
    )


def write_reduced_order_fit_result(result: CalibrationReducedOrderFitResult) -> Path:
    cfg = make_building_calibration_config()
    out_dir = Path(cfg.reduced_order_fit_output_dir).resolve() / result.cohort_id
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / (
        f"fit__ref_{result.reference_experiment_id}__free_{result.free_float_experiment_id}.json"
    )
    out_path.write_text(json.dumps(result.to_dict(), indent=2), encoding="utf-8")
    return out_path
