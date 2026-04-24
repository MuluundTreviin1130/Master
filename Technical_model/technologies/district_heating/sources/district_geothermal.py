from __future__ import annotations

from typing import Any, Dict

import pandas as pd


def _require_config_value(config: Any, attr: str) -> float:
    if config is None or not hasattr(config, attr):
        raise ValueError(f"[district_geothermal] Missing required config attribute '{attr}'.")
    value = getattr(config, attr)
    if value is None:
        raise ValueError(f"[district_geothermal] Config attribute '{attr}' must not be None.")
    return float(value)


def _is_scheduled_downtime(timestamp: Any, config: Any) -> bool:
    ts = pd.Timestamp(timestamp)
    days = int(_require_config_value(config, "scheduled_downtime_days_per_year"))
    start_day = int(_require_config_value(config, "scheduled_downtime_start_day_of_year"))
    if days <= 0:
        return False
    if not 1 <= start_day <= 366:
        raise ValueError("[district_geothermal] scheduled_downtime_start_day_of_year must be within [1, 366].")
    if not 0 <= days <= 366:
        raise ValueError("[district_geothermal] scheduled_downtime_days_per_year must be within [0, 366].")
    day = int(ts.dayofyear)
    end_day = start_day + days
    if end_day <= 366:
        return start_day <= day < end_day
    overflow = end_day - 366
    return day >= start_day or day < overflow


def dispatch_district_geothermal_orc(
    installed_kw_el: float,
    config: Any,
    timestamp: Any,
    dt_h: float = 1.0,
) -> Dict[str, float]:
    installed_kw_el = float(installed_kw_el)
    dt_h = float(dt_h)
    if installed_kw_el < 0.0:
        raise ValueError("[district_geothermal] installed_kw_el must be >= 0.")
    if dt_h <= 0.0:
        raise ValueError("[district_geothermal] dt_h must be > 0.")

    heat_to_power_ratio = _require_config_value(config, "heat_to_power_ratio")
    if heat_to_power_ratio < 0.0:
        raise ValueError("[district_geothermal] heat_to_power_ratio must be >= 0.")

    electric_capacity_kwh = installed_kw_el * dt_h
    if _is_scheduled_downtime(timestamp, config):
        return {
            "electric_generation_kwh": 0.0,
            "thermal_kwh": 0.0,
            "electric_capacity_kwh": float(electric_capacity_kwh),
            "scheduled_downtime": 1.0,
        }

    electric_generation_kwh = max(0.0, electric_capacity_kwh)
    thermal_kwh = electric_generation_kwh * heat_to_power_ratio
    return {
        "electric_generation_kwh": float(electric_generation_kwh),
        "thermal_kwh": float(thermal_kwh),
        "electric_capacity_kwh": float(electric_capacity_kwh),
        "scheduled_downtime": 0.0,
    }
