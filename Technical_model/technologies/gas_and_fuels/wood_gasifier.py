from __future__ import annotations

import numpy as np


def dispatch_wood_gasifier(
    *,
    capacity_kw: float,
    deficit_kwh: float,
    min_partload: float,
    max_partload: float,
    dispatch_mode: str,
    eta_el: float,
    fuel_lhv_kwh_per_kg: float,
    dt_h: float = 1.0,
) -> dict:
    cap = max(0.0, float(capacity_kw)) * float(dt_h)
    if cap <= 0.0:
        return {"electric_output_kwh": 0.0, "fuel_input_kwh": 0.0, "fuel_input_kg": 0.0}
    min_load = np.clip(float(min_partload), 0.0, 1.0) * cap
    max_load = np.clip(float(max_partload), 0.0, 1.0) * cap
    mode = str(dispatch_mode or "demand_following").strip().lower()
    if mode == "fixed_band":
        electric_output_kwh = float(min_load)
    else:
        target = max(0.0, float(deficit_kwh))
        if target <= 0.0:
            electric_output_kwh = float(min_load)
        else:
            electric_output_kwh = float(np.clip(target, min_load, max_load))

    eta = max(1e-9, float(eta_el))
    fuel_input_kwh = electric_output_kwh / eta
    fuel_lhv = max(1e-9, float(fuel_lhv_kwh_per_kg))
    fuel_input_kg = fuel_input_kwh / fuel_lhv
    return {
        "electric_output_kwh": float(electric_output_kwh),
        "fuel_input_kwh": float(fuel_input_kwh),
        "fuel_input_kg": float(fuel_input_kg),
    }
