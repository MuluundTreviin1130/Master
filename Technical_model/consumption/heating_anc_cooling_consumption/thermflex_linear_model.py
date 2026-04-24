from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

from Technical_model.consumption.heating_anc_cooling_consumption.heating_control import (
    active_reference_heating_setpoint_k,
)
from Technical_model.technologies.buildings.runtime_space_heat import (
    derive_runtime_max_heating_power_w_per_m2,
)
from Technical_model.technologies.buildings.runtime_building_params import get_runtime_building_params


def derive_ua_w_per_k(building_params: dict[str, Any]) -> float:
    """Derive aggregate effective loss coefficient UA [W/K] from runtime building params."""
    if "effective_total_loss_coefficient_w_per_k" not in building_params:
        raise KeyError(
            "[thermflex_linear_model] building_params must contain 'effective_total_loss_coefficient_w_per_k'."
        )
    value = float(building_params["effective_total_loss_coefficient_w_per_k"])
    if value <= 0.0:
        raise ValueError(
            f"[thermflex_linear_model] effective_total_loss_coefficient_w_per_k must be > 0, got {value}."
        )
    return value


def build_member_thermflex_linear_inputs(
    member: Any,
    *,
    settings_obj: Any,
    timestamps,
    t_outdoor_k,
    solar_gains_w_m2,
    usage_df: pd.DataFrame,
    q_heat_ref_kwh=None,
    stock_scale: float = 1.0,
) -> dict[str, Any]:
    """Build a linear temperature-state representation for one cohort/member.

    State equation for 1h time steps:
        T_in[t+1] = alpha*T_in[t] + beta_out*T_out[t]
                    + gamma_int*q_int[t] + gamma_sol*q_sol[t]
                    + gamma_heat*q_heat[t]
    with q_heat in kWh_th per step.
    """

    building_params = get_runtime_building_params(member, settings_obj=settings_obj)
    stock_scale = float(stock_scale)
    if stock_scale <= 0.0:
        raise ValueError("[thermflex_linear_model] stock_scale must be > 0.")
    c_th = float(building_params["heat_capacity"]) * stock_scale
    if c_th <= 0.0:
        raise ValueError("[thermflex_linear_model] heat_capacity must be > 0.")
    ua = derive_ua_w_per_k(building_params) * stock_scale
    a_floor = float(building_params["A_floor"]) * stock_scale
    dt_h = 1.0

    alpha = 1.0 - (ua * dt_h) / c_th
    beta_out = (ua * dt_h) / c_th
    gamma_internal = (a_floor * dt_h) / c_th
    gamma_solar = (a_floor * dt_h) / c_th
    gamma_heat = 1000.0 / c_th

    idx = pd.DatetimeIndex(timestamps)
    q_internal_w_m2 = np.where(
        idx.month.isin([10, 11, 12, 1, 2, 3, 4]),
        usage_df["Qi Winter W/m2"].to_numpy(dtype=float),
        usage_df["Qi Sommer W/m2"].to_numpy(dtype=float),
    )
    t_ref_c = np.array(
        [active_reference_heating_setpoint_k(int(ts.hour), settings_obj.heating_control) - 273.15 for ts in idx],
        dtype=float,
    )

    q_heat_max_kwh = float(
        derive_runtime_max_heating_power_w_per_m2(
            building_params=building_params,
            usage_df=usage_df,
            heating_control=settings_obj.heating_control,
        )
        * a_floor
        / 1000.0
    )

    calibration_event_response_v1 = building_params.get("calibration_event_response_v1")
    if calibration_event_response_v1 is not None and not isinstance(calibration_event_response_v1, dict):
        raise TypeError(
            "[thermflex_linear_model] building_params['calibration_event_response_v1'] must be a dict when present."
        )

    result = {
        "member_id": str(getattr(member, "member_id", "")),
        "thermal_archetype_key": str(getattr(member, "thermal_archetype_key", "")),
        "stock_scale": stock_scale,
        "a_floor_m2": a_floor,
        "c_th_wh_per_k": c_th,
        "ua_w_per_k": ua,
        "alpha": float(alpha),
        "beta_out": float(beta_out),
        "gamma_internal": float(gamma_internal),
        "gamma_solar": float(gamma_solar),
        "gamma_heat": float(gamma_heat),
        "initial_t_in_c": float(t_ref_c[0]),
        "t_ref_c": t_ref_c,
        "t_outdoor_c": np.asarray(t_outdoor_k, dtype=float) - 273.15,
        "solar_gains_w_m2": np.asarray(solar_gains_w_m2, dtype=float),
        "internal_gains_w_m2": q_internal_w_m2,
        "q_heat_max_kwh": q_heat_max_kwh,
        "calibration_event_response_v1": dict(calibration_event_response_v1)
        if calibration_event_response_v1 is not None
        else None,
    }
    if q_heat_ref_kwh is not None:
        q_ref = np.asarray(q_heat_ref_kwh, dtype=float) * stock_scale
        result["q_heat_ref_kwh"] = q_ref
        result["q_heat_max_kwh"] = float(max(q_heat_max_kwh, float(np.max(q_ref)) if q_ref.size else 0.0))
        residual = np.zeros_like(q_ref, dtype=float)
        for t in range(len(q_ref) - 1):
            residual[t] = (
                float(t_ref_c[t + 1])
                - (
                    float(alpha) * float(t_ref_c[t])
                    + float(beta_out) * float(result["t_outdoor_c"][t])
                    + float(gamma_internal) * float(q_internal_w_m2[t])
                    + float(gamma_solar) * float(result["solar_gains_w_m2"][t])
                    + float(gamma_heat) * float(q_ref[t])
                )
            )
        result["residual_c"] = residual
    return result
