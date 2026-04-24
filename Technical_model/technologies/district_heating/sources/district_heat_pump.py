from __future__ import annotations

from typing import Any, Dict


def _require_config_value(config: Any, attr: str) -> float:
    if config is None or not hasattr(config, attr):
        raise ValueError(f"[district_heat_pump] Missing required config attribute '{attr}'.")
    value = getattr(config, attr)
    if value is None:
        raise ValueError(f"[district_heat_pump] Config attribute '{attr}' must not be None.")
    return float(value)


def calculate_constant_dh_heat_pump_cop(config: Any) -> float:
    """
    Calculate a constant COP for the configured DH heat pump.

    The COP is constant over time, but not arbitrary:
    it is derived once from the configured source and supply temperatures.
    """

    source_temp_c = _require_config_value(config, "source_temp_c")
    supply_temp_c = _require_config_value(config, "supply_temp_c")
    cop_max = getattr(config, "cop_max", None)
    t_cold_k = source_temp_c + 273.15
    t_hot_k = supply_temp_c + 273.15
    if t_hot_k <= t_cold_k:
        raise ValueError(
            "[district_heat_pump] supply_temp_c must be greater than source_temp_c "
            "to derive a physically meaningful COP."
        )

    cop_real = t_hot_k / (t_hot_k - t_cold_k)
    if cop_max is not None:
        cop_real = min(cop_real, float(cop_max))
    if cop_real <= 0.0:
        raise ValueError("[district_heat_pump] Derived COP must be > 0.")
    return float(cop_real)


def dispatch_district_heat_pump(
    requested_thermal_kwh: float,
    installed_kw_th: float,
    config: Any,
    dt_h: float = 1.0,
) -> Dict[str, float]:
    """
    Technical dispatch mapping for one timestep.

    This is intentionally not a system-level dispatch policy. The function only
    answers the local device question:
    - how much requested thermal energy can this DH heat pump provide this step?
    - how much electricity does that require?
    """

    requested_thermal_kwh = float(requested_thermal_kwh)
    installed_kw_th = float(installed_kw_th)
    dt_h = float(dt_h)
    if requested_thermal_kwh < 0.0:
        raise ValueError("[district_heat_pump] requested_thermal_kwh must be >= 0.")
    if installed_kw_th < 0.0:
        raise ValueError("[district_heat_pump] installed_kw_th must be >= 0.")
    if dt_h <= 0.0:
        raise ValueError("[district_heat_pump] dt_h must be > 0.")

    source_temp_c = _require_config_value(config, "source_temp_c")
    supply_temp_c = _require_config_value(config, "supply_temp_c")
    return_temp_c = _require_config_value(config, "return_temp_c")
    if supply_temp_c <= return_temp_c:
        raise ValueError("[district_heat_pump] supply_temp_c must be greater than return_temp_c.")

    cop = calculate_constant_dh_heat_pump_cop(config)
    thermal_capacity_kwh = installed_kw_th * dt_h
    thermal_kwh = min(requested_thermal_kwh, thermal_capacity_kwh)
    electric_kwh = thermal_kwh / cop if thermal_kwh > 0.0 else 0.0

    return {
        "thermal_kwh": float(thermal_kwh),
        "electric_kwh": float(electric_kwh),
        "cop": float(cop),
        "source_temp_c": float(source_temp_c),
        "supply_temp_c": float(supply_temp_c),
        "return_temp_c": float(return_temp_c),
        "delta_t_network_c": float(supply_temp_c - return_temp_c),
        "thermal_capacity_kwh": float(thermal_capacity_kwh),
    }
