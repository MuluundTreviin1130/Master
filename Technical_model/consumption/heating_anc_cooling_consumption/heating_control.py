from __future__ import annotations

from typing import Any


SUPPORTED_CONTROL_MODES = {"constant", "day_night"}


def _require_attr(cfg: Any, name: str) -> float:
    if cfg is None:
        raise ValueError(
            "[heating_control] Heating control config is required. No implicit fallback is allowed."
        )
    if not hasattr(cfg, name):
        raise AttributeError(f"[heating_control] Missing required config attribute: {name}")
    return float(getattr(cfg, name))


def _require_any_attr(cfg: Any, name: str) -> Any:
    if cfg is None:
        raise ValueError(
            "[heating_control] Heating control config is required. No implicit fallback is allowed."
        )
    if not hasattr(cfg, name):
        raise AttributeError(f"[heating_control] Missing required config attribute: {name}")
    return getattr(cfg, name)


def is_night_hour(hour_of_day: int, cfg: Any) -> bool:
    day_start = int(_require_attr(cfg, "day_start_hour"))
    night_start = int(_require_attr(cfg, "night_start_hour"))
    hour = int(hour_of_day) % 24
    if day_start == night_start:
        return False
    if night_start > day_start:
        return hour < day_start or hour >= night_start
    return night_start <= hour < day_start


def heating_control_mode(cfg: Any) -> str:
    mode = str(_require_any_attr(cfg, "control_mode")).strip().lower()
    if mode not in SUPPORTED_CONTROL_MODES:
        raise ValueError(
            f"[heating_control] Unsupported control_mode='{mode}'. Expected 'constant' or 'day_night'."
        )
    return mode


def reference_control_mode(cfg: Any) -> str:
    mode = str(_require_any_attr(cfg, "reference_control_mode")).strip().lower()
    if mode not in SUPPORTED_CONTROL_MODES:
        raise ValueError(
            "[heating_control] Unsupported reference_control_mode="
            f"'{mode}'. Expected 'constant' or 'day_night'."
        )
    return mode


def _setpoint_for_mode_k(hour_of_day: int, cfg: Any, mode: str) -> float:
    if mode == "constant":
        return float(_require_attr(cfg, "constant_setpoint_c") + 273.15)
    day_c = _require_attr(cfg, "day_setpoint_c")
    night_c = _require_attr(cfg, "night_setpoint_c")
    return float((night_c if is_night_hour(hour_of_day, cfg) else day_c) + 273.15)


def active_heating_setpoint_k(hour_of_day: int, cfg: Any) -> float:
    return _setpoint_for_mode_k(hour_of_day, cfg, heating_control_mode(cfg))


def active_reference_heating_setpoint_k(hour_of_day: int, cfg: Any) -> float:
    return _setpoint_for_mode_k(hour_of_day, cfg, reference_control_mode(cfg))


def comfort_band_enabled(cfg: Any) -> bool:
    return bool(_require_any_attr(cfg, "comfort_band_enabled"))


def comfort_band_k(cfg: Any) -> float:
    return float(max(0.0, _require_attr(cfg, "comfort_band_k")))


def max_flex_duration_h(cfg: Any) -> int:
    return int(max(0, round(_require_attr(cfg, "max_flex_duration_h"))))


def max_flex_events_per_day(cfg: Any) -> int:
    return int(max(0, round(_require_attr(cfg, "max_flex_events_per_day"))))


def heating_hysteresis_bounds_k(setpoint_k: float, cfg: Any) -> tuple[float, float]:
    band_k = max(0.0, _require_attr(cfg, "hysteresis_band_k"))
    lower = setpoint_k - 0.5 * band_k
    upper = setpoint_k + 0.5 * band_k
    return float(lower), float(upper)


def flex_temperature_bounds_k(reference_setpoint_k: float, cfg: Any) -> tuple[float, float]:
    flex_band = comfort_band_k(cfg) if comfort_band_enabled(cfg) else 0.0
    lower = reference_setpoint_k - flex_band
    upper = reference_setpoint_k + flex_band
    return float(lower), float(upper)


def cooling_setpoint_k(cfg: Any) -> float:
    return float(_require_attr(cfg, "cooling_setpoint_c") + 273.15)


def active_cooling_enabled(cfg: Any) -> bool:
    return bool(_require_any_attr(cfg, "enable_active_cooling"))


def heating_power_mode(cfg: Any) -> str:
    mode = str(_require_any_attr(cfg, "max_heating_power_mode")).strip().lower()
    if mode not in {"fixed", "archetype_design"}:
        raise ValueError(
            f"[heating_control] Unsupported max_heating_power_mode='{mode}'. "
            "Expected 'fixed' or 'archetype_design'."
        )
    return mode


def design_indoor_temp_k(cfg: Any) -> float:
    return float(_require_attr(cfg, "design_indoor_temp_c") + 273.15)


def design_outdoor_temp_k(cfg: Any) -> float:
    return float(_require_attr(cfg, "design_outdoor_temp_c") + 273.15)


def design_ventilation_mode(cfg: Any) -> str:
    mode = str(_require_any_attr(cfg, "design_ventilation_mode")).strip().lower()
    if mode not in {"mean", "p95", "max"}:
        raise ValueError(
            f"[heating_control] Unsupported design_ventilation_mode='{mode}'. "
            "Expected 'mean', 'p95' or 'max'."
        )
    return mode


def max_heating_power_multiplier(cfg: Any) -> float:
    return float(max(0.0, _require_attr(cfg, "max_heating_power_multiplier")))


def design_internal_gains_w_per_m2(cfg: Any) -> float:
    return float(_require_attr(cfg, "design_internal_gains_w_per_m2"))


def design_solar_gains_w_per_m2(cfg: Any) -> float:
    return float(_require_attr(cfg, "design_solar_gains_w_per_m2"))


def max_heating_energy_wh(a_floor_m2: float, dt_h: float, cfg: Any) -> float:
    return float(max(0.0, _require_attr(cfg, "max_heating_power_w_per_m2")) * float(a_floor_m2) * float(dt_h))


def max_cooling_energy_wh(a_floor_m2: float, dt_h: float, cfg: Any) -> float:
    return float(max(0.0, _require_attr(cfg, "max_cooling_power_w_per_m2")) * float(a_floor_m2) * float(dt_h))
