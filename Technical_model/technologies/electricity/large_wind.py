from __future__ import annotations

import numpy as np

from .small_wind import simulate_small_wind_generation


def simulate_large_wind_generation(
    *,
    installed_kw: float,
    wind_speed_ms: np.ndarray,
    reference_height_m: float,
    hub_height_m: float,
    shear_exponent: float,
    cut_in_ms: float,
    rated_ms: float,
    cut_out_ms: float,
    temperature_c: np.ndarray | None = None,
    pressure_hpa: np.ndarray | None = None,
    reference_air_density_kg_per_m3: float = 1.225,
    dt_h: float = 1.0,
) -> np.ndarray:
    return simulate_small_wind_generation(
        installed_kw=installed_kw,
        wind_speed_ms=wind_speed_ms,
        reference_height_m=reference_height_m,
        hub_height_m=hub_height_m,
        shear_exponent=shear_exponent,
        cut_in_ms=cut_in_ms,
        rated_ms=rated_ms,
        cut_out_ms=cut_out_ms,
        temperature_c=temperature_c,
        pressure_hpa=pressure_hpa,
        reference_air_density_kg_per_m3=reference_air_density_kg_per_m3,
        dt_h=dt_h,
    )
