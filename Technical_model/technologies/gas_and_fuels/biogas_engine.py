from __future__ import annotations

import numpy as np


def dispatch_biogas_engine(
    *,
    capacity_kw: float,
    deficit_kwh: float,
    min_partload: float,
    max_partload: float,
    fixed_output_fraction: float,
    dispatch_mode: str,
    dt_h: float = 1.0,
) -> float:
    cap = max(0.0, float(capacity_kw)) * float(dt_h)
    if cap <= 0.0:
        return 0.0
    min_load = np.clip(float(min_partload), 0.0, 1.0) * cap
    max_load = np.clip(float(max_partload), 0.0, 1.0) * cap
    mode = str(dispatch_mode or "fixed_band").strip().lower()
    if mode == "demand_following":
        target = max(0.0, float(deficit_kwh))
        if target <= 0.0:
            return min_load
        return float(np.clip(target, min_load, max_load))
    fixed = np.clip(float(fixed_output_fraction), 0.0, 1.0) * cap
    return float(np.clip(fixed, min_load, max_load))
