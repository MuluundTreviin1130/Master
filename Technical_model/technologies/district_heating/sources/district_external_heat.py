from __future__ import annotations

from typing import Any, Dict


def _require_config_value(config: Any, attr: str) -> float:
    if config is None or not hasattr(config, attr):
        raise ValueError(f"[district_external_heat] Missing required config attribute '{attr}'.")
    value = getattr(config, attr)
    if value is None:
        raise ValueError(f"[district_external_heat] Config attribute '{attr}' must not be None.")
    return float(value)


def dispatch_district_external_heat(
    requested_thermal_kwh: float,
    installed_kw_th: float,
    config: Any,
    dt_h: float = 1.0,
) -> Dict[str, float]:
    requested_thermal_kwh = float(requested_thermal_kwh)
    installed_kw_th = float(installed_kw_th)
    dt_h = float(dt_h)
    if requested_thermal_kwh < 0.0:
        raise ValueError("[district_external_heat] requested_thermal_kwh must be >= 0.")
    if installed_kw_th < 0.0:
        raise ValueError("[district_external_heat] installed_kw_th must be >= 0.")
    if dt_h <= 0.0:
        raise ValueError("[district_external_heat] dt_h must be > 0.")

    thermal_availability = _require_config_value(config, "thermal_availability")
    min_partload = _require_config_value(config, "min_partload")
    if not 0.0 <= thermal_availability <= 1.0:
        raise ValueError("[district_external_heat] thermal_availability must be within [0, 1].")
    if not 0.0 <= min_partload <= 1.0:
        raise ValueError("[district_external_heat] min_partload must be within [0, 1].")

    thermal_capacity_kwh = installed_kw_th * dt_h * thermal_availability
    if thermal_capacity_kwh <= 0.0 or requested_thermal_kwh <= 0.0:
        return {
            "thermal_kwh": 0.0,
            "thermal_capacity_kwh": float(thermal_capacity_kwh),
        }
    if requested_thermal_kwh < min_partload * thermal_capacity_kwh:
        return {
            "thermal_kwh": 0.0,
            "thermal_capacity_kwh": float(thermal_capacity_kwh),
        }
    return {
        "thermal_kwh": float(min(requested_thermal_kwh, thermal_capacity_kwh)),
        "thermal_capacity_kwh": float(thermal_capacity_kwh),
    }
