from __future__ import annotations

from dataclasses import dataclass


@dataclass
class ThermalConfig:
    """Thermal flexibility settings.

    delta_T is in Kelvin and applied globally to all members.
    outdoor_smoothing_hours defines the effective envelope response horizon
    for the reduced-order building model.
    """

    delta_T: float = 0.0
    outdoor_smoothing_hours: float = 24.0
    runtime_solar_gains_mode: str = "irradiance_window_transmission"
    runtime_solar_shading_factor: float = 0.6
    runtime_solar_frame_fraction: float = 0.3
    runtime_solar_non_perpendicular_factor: float = 0.9


def make_thermal() -> ThermalConfig:
    return ThermalConfig(
        delta_T=0.0,
        outdoor_smoothing_hours=24.0,
        runtime_solar_gains_mode="irradiance_window_transmission",
        runtime_solar_shading_factor=0.6,
        runtime_solar_frame_fraction=0.3,
        runtime_solar_non_perpendicular_factor=0.9,
    )
