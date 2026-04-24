from __future__ import annotations

from typing import Any, Dict

import pandas as pd


def _require_config_value(config: Any, attr: str) -> float:
    if config is None or not hasattr(config, attr):
        raise ValueError(f"[district_biomass_chp] Missing required config attribute '{attr}'.")
    value = getattr(config, attr)
    if value is None:
        raise ValueError(f"[district_biomass_chp] Config attribute '{attr}' must not be None.")
    return float(value)


def _is_scheduled_downtime(timestamp: Any, config: Any) -> bool:
    ts = pd.Timestamp(timestamp)
    days = int(_require_config_value(config, "scheduled_downtime_days_per_year"))
    start_day = int(_require_config_value(config, "scheduled_downtime_start_day_of_year"))
    if days <= 0:
        return False
    if not 1 <= start_day <= 366:
        raise ValueError("[district_biomass_chp] scheduled_downtime_start_day_of_year must be within [1, 366].")
    if not 0 <= days <= 366:
        raise ValueError("[district_biomass_chp] scheduled_downtime_days_per_year must be within [0, 366].")
    day = int(ts.dayofyear)
    end_day = start_day + days
    if end_day <= 366:
        return start_day <= day < end_day
    overflow = end_day - 366
    return day >= start_day or day < overflow


def dispatch_district_biomass_chp(
    requested_thermal_kwh: float,
    installed_kw_th: float,
    config: Any,
    timestamp: Any,
    dt_h: float = 1.0,
) -> Dict[str, float]:
    requested_thermal_kwh = float(requested_thermal_kwh)
    installed_kw_th = float(installed_kw_th)
    dt_h = float(dt_h)
    if requested_thermal_kwh < 0.0:
        raise ValueError("[district_biomass_chp] requested_thermal_kwh must be >= 0.")
    if installed_kw_th < 0.0:
        raise ValueError("[district_biomass_chp] installed_kw_th must be >= 0.")
    if dt_h <= 0.0:
        raise ValueError("[district_biomass_chp] dt_h must be > 0.")

    eta_el = _require_config_value(config, "eta_el")
    eta_th = _require_config_value(config, "eta_th")
    min_partload = _require_config_value(config, "min_partload")
    fuel_lhv_kwh_per_kg = _require_config_value(config, "fuel_lhv_kwh_per_kg")
    if not 0.0 < eta_el <= 1.0:
        raise ValueError("[district_biomass_chp] eta_el must be within (0, 1].")
    if not 0.0 < eta_th <= 1.0:
        raise ValueError("[district_biomass_chp] eta_th must be within (0, 1].")
    if not 0.0 <= min_partload <= 1.0:
        raise ValueError("[district_biomass_chp] min_partload must satisfy 0 <= min_partload <= 1.")
    if fuel_lhv_kwh_per_kg <= 0.0:
        raise ValueError("[district_biomass_chp] fuel_lhv_kwh_per_kg must be > 0.")

    thermal_capacity_kwh = installed_kw_th * dt_h
    electric_capacity_kwh = thermal_capacity_kwh * (eta_el / eta_th)
    if _is_scheduled_downtime(timestamp, config):
        return {
            "electric_generation_kwh": 0.0,
            "thermal_kwh": 0.0,
            "fuel_input_kwh": 0.0,
            "fuel_input_kg": 0.0,
            "electric_capacity_kwh": float(electric_capacity_kwh),
            "thermal_capacity_kwh": float(thermal_capacity_kwh),
            "scheduled_downtime": 1.0,
        }
    if thermal_capacity_kwh <= 0.0 or requested_thermal_kwh <= 0.0:
        return {
            "electric_generation_kwh": 0.0,
            "thermal_kwh": 0.0,
            "fuel_input_kwh": 0.0,
            "fuel_input_kg": 0.0,
            "electric_capacity_kwh": float(electric_capacity_kwh),
            "thermal_capacity_kwh": float(thermal_capacity_kwh),
            "scheduled_downtime": 0.0,
        }

    min_thermal_kwh = min_partload * thermal_capacity_kwh
    if requested_thermal_kwh < min_thermal_kwh:
        return {
            "electric_generation_kwh": 0.0,
            "thermal_kwh": 0.0,
            "fuel_input_kwh": 0.0,
            "fuel_input_kg": 0.0,
            "electric_capacity_kwh": float(electric_capacity_kwh),
            "thermal_capacity_kwh": float(thermal_capacity_kwh),
            "scheduled_downtime": 0.0,
        }

    thermal_kwh = min(thermal_capacity_kwh, requested_thermal_kwh)
    fuel_input_kwh = thermal_kwh / eta_th
    electric_generation_kwh = fuel_input_kwh * eta_el
    fuel_input_kg = fuel_input_kwh / fuel_lhv_kwh_per_kg
    return {
        "electric_generation_kwh": float(electric_generation_kwh),
        "thermal_kwh": float(thermal_kwh),
        "fuel_input_kwh": float(fuel_input_kwh),
        "fuel_input_kg": float(fuel_input_kg),
        "electric_capacity_kwh": float(electric_capacity_kwh),
        "thermal_capacity_kwh": float(thermal_capacity_kwh),
        "scheduled_downtime": 0.0,
    }
