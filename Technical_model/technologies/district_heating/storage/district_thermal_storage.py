from __future__ import annotations

from typing import Any, Dict


def _require_config_value(config: Any, attr: str) -> float:
    if config is None or not hasattr(config, attr):
        raise ValueError(f"[district_thermal_storage] Missing required config attribute '{attr}'.")
    value = getattr(config, attr)
    if value is None:
        raise ValueError(f"[district_thermal_storage] Config attribute '{attr}' must not be None.")
    return float(value)


def initialize_district_thermal_storage_soc(installed_capacity_kwh_th: float, config: Any) -> float:
    installed_capacity_kwh_th = float(installed_capacity_kwh_th)
    if installed_capacity_kwh_th < 0.0:
        raise ValueError("[district_thermal_storage] installed_capacity_kwh_th must be >= 0.")

    initial_soc_fraction = _require_config_value(config, "initial_soc_fraction")
    min_temp_c = _require_config_value(config, "min_temp_c")
    max_temp_c = _require_config_value(config, "max_temp_c")
    if not 0.0 <= initial_soc_fraction <= 1.0:
        raise ValueError("[district_thermal_storage] initial_soc_fraction must be within [0, 1].")
    if max_temp_c <= min_temp_c:
        raise ValueError("[district_thermal_storage] max_temp_c must be greater than min_temp_c.")

    return float(installed_capacity_kwh_th * initial_soc_fraction)


def step_district_thermal_storage(
    available_charge_kwh: float,
    requested_discharge_kwh: float,
    soc_prev_kwh: float,
    installed_capacity_kwh_th: float,
    config: Any,
    dt_h: float = 1.0,
) -> Dict[str, float]:
    available_charge_kwh = float(available_charge_kwh)
    requested_discharge_kwh = float(requested_discharge_kwh)
    soc_prev_kwh = float(soc_prev_kwh)
    installed_capacity_kwh_th = float(installed_capacity_kwh_th)
    dt_h = float(dt_h)

    if available_charge_kwh < 0.0 or requested_discharge_kwh < 0.0:
        raise ValueError("[district_thermal_storage] Charge/discharge requests must be >= 0.")
    if available_charge_kwh > 0.0 and requested_discharge_kwh > 0.0:
        raise ValueError("[district_thermal_storage] Charging and discharging in the same timestep is not allowed.")
    if soc_prev_kwh < 0.0 or installed_capacity_kwh_th < 0.0:
        raise ValueError("[district_thermal_storage] SoC and capacity must be >= 0.")
    if soc_prev_kwh - installed_capacity_kwh_th > 1e-9:
        raise ValueError("[district_thermal_storage] SoC must not exceed installed capacity.")
    if dt_h <= 0.0:
        raise ValueError("[district_thermal_storage] dt_h must be > 0.")

    min_temp_c = _require_config_value(config, "min_temp_c")
    max_temp_c = _require_config_value(config, "max_temp_c")
    charge_efficiency = _require_config_value(config, "charge_efficiency")
    discharge_efficiency = _require_config_value(config, "discharge_efficiency")
    standing_loss_kwh_per_day = _require_config_value(config, "standing_loss_kwh_per_day")
    if max_temp_c <= min_temp_c:
        raise ValueError("[district_thermal_storage] max_temp_c must be greater than min_temp_c.")
    if not 0.0 < charge_efficiency <= 1.0:
        raise ValueError("[district_thermal_storage] charge_efficiency must be within (0, 1].")
    if not 0.0 < discharge_efficiency <= 1.0:
        raise ValueError("[district_thermal_storage] discharge_efficiency must be within (0, 1].")
    if standing_loss_kwh_per_day < 0.0:
        raise ValueError("[district_thermal_storage] standing_loss_kwh_per_day must be >= 0.")

    losses_kwh = min(soc_prev_kwh, standing_loss_kwh_per_day * (dt_h / 24.0))
    soc_after_losses = max(0.0, soc_prev_kwh - losses_kwh)

    charge_headroom_kwh = max(0.0, installed_capacity_kwh_th - soc_after_losses)
    max_charge_input_kwh = charge_headroom_kwh / charge_efficiency if charge_efficiency > 0.0 else 0.0
    charge_kwh = min(available_charge_kwh, max_charge_input_kwh)
    soc_after_charge = soc_after_losses + charge_kwh * charge_efficiency

    max_deliverable_kwh = soc_after_charge * discharge_efficiency
    discharge_kwh = min(requested_discharge_kwh, max_deliverable_kwh)
    soc_next_kwh = soc_after_charge - (discharge_kwh / discharge_efficiency if discharge_efficiency > 0.0 else 0.0)
    soc_next_kwh = min(installed_capacity_kwh_th, max(0.0, soc_next_kwh))

    return {
        "charge_kwh": float(charge_kwh),
        "discharge_kwh": float(discharge_kwh),
        "losses_kwh": float(losses_kwh),
        "soc_kwh": float(soc_next_kwh),
    }
