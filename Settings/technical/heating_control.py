from __future__ import annotations

from dataclasses import dataclass


@dataclass
class HeatingControlConfig:
    """Reference heating-control settings for reduced-order building demand."""

    reference_control_mode: str = "constant"
    control_mode: str = "constant"
    constant_setpoint_c: float = 22.0
    day_setpoint_c: float = 22.0
    night_setpoint_c: float = 19.0
    day_start_hour: int = 6
    night_start_hour: int = 22
    hysteresis_band_k: float = 1.0
    comfort_band_enabled: bool = False
    comfort_band_k: float = 0.0
    max_flex_duration_h: int = 4
    max_flex_events_per_day: int = 1
    max_heating_power_mode: str = "archetype_design"
    max_heating_power_w_per_m2: float = 60.0
    max_heating_power_multiplier: float = 1.0
    design_indoor_temp_c: float = 22.0
    design_outdoor_temp_c: float = -12.0
    design_ventilation_mode: str = "p95"
    design_internal_gains_w_per_m2: float = 0.0
    design_solar_gains_w_per_m2: float = 0.0
    enable_active_cooling: bool = True
    cooling_setpoint_c: float = 27.0
    max_cooling_power_w_per_m2: float = 40.0


def make_heating_control() -> HeatingControlConfig:
    return HeatingControlConfig()
