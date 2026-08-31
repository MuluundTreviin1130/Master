from __future__ import annotations

import numpy as np

# Outdoor air denser than ~150 °C is not a physical ambient series. Profile
# `T_outdoor` in this repo is Kelvin; callers that pass it here as Celsius
# would compute T_K = T_outdoor + 273.15 ≈ 553 K and clip density to 0.5.
_AMBIENT_CELSIUS_MEDIAN_MAX = 150.0


def require_temperature_celsius(temperature_c: np.ndarray) -> np.ndarray:
    """Reject Kelvin-looking outdoor series before the +273.15 density step.

    The air-density correction is ρ = P / (R * (T_C + 273.15)). A Kelvin
    profile (~280 K in Vienna) passed as Celsius is indistinguishable from a
    280 °C gas and must not silently understate wind yield.
    """
    arr = np.asarray(temperature_c, dtype=float)
    finite = arr[np.isfinite(arr)]
    if finite.size == 0:
        raise ValueError("[small_wind] temperature_c has no finite values.")
    median = float(np.nanmedian(finite))
    if median > _AMBIENT_CELSIUS_MEDIAN_MAX:
        raise ValueError(
            f"[small_wind] temperature_c looks like Kelvin (median={median:.2f}). "
            "Air density uses T_K = T_C + 273.15; pass outdoor temperature in Celsius."
        )
    return arr


def _adjust_to_hub_height(
    wind_speed_ms: np.ndarray,
    *,
    reference_height_m: float,
    hub_height_m: float,
    shear_exponent: float,
) -> np.ndarray:
    ref_h = max(1e-6, float(reference_height_m))
    hub_h = max(1e-6, float(hub_height_m))
    alpha = float(shear_exponent)
    return np.asarray(wind_speed_ms, dtype=float) * (hub_h / ref_h) ** alpha


def _normalized_power_curve(
    wind_speed_ms: np.ndarray,
    *,
    cut_in_ms: float,
    rated_ms: float,
    cut_out_ms: float,
) -> np.ndarray:
    v = np.asarray(wind_speed_ms, dtype=float)
    cut_in = float(cut_in_ms)
    rated = max(cut_in + 1e-6, float(rated_ms))
    cut_out = max(rated + 1e-6, float(cut_out_ms))
    p = np.zeros_like(v, dtype=float)
    ramp = (v >= cut_in) & (v < rated)
    rated_mask = (v >= rated) & (v < cut_out)
    p[ramp] = ((v[ramp] - cut_in) / max(1e-9, rated - cut_in)) ** 3
    p[rated_mask] = 1.0
    return np.clip(p, 0.0, 1.0)


def _air_density_correction_factor(
    *,
    temperature_c: np.ndarray,
    pressure_hpa: np.ndarray,
    reference_air_density_kg_per_m3: float,
) -> np.ndarray:
    # Ideal-gas density vs the configured reference (typically 1.225 kg/m³ at
    # 15 °C). The +273.15 offset is only valid for Celsius input.
    temp_k = require_temperature_celsius(temperature_c) + 273.15
    pressure_pa = np.asarray(pressure_hpa, dtype=float) * 100.0
    rho_ref = max(1e-9, float(reference_air_density_kg_per_m3))
    rho = pressure_pa / (287.05 * np.clip(temp_k, 1e-9, None))
    return np.clip(rho / rho_ref, 0.5, 1.5)


def simulate_small_wind_generation(
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
    if float(installed_kw) <= 0.0:
        return np.zeros_like(np.asarray(wind_speed_ms, dtype=float))
    v_hub = _adjust_to_hub_height(
        wind_speed_ms,
        reference_height_m=reference_height_m,
        hub_height_m=hub_height_m,
        shear_exponent=shear_exponent,
    )
    power_frac = _normalized_power_curve(
        v_hub,
        cut_in_ms=cut_in_ms,
        rated_ms=rated_ms,
        cut_out_ms=cut_out_ms,
    )
    if temperature_c is not None and pressure_hpa is not None:
        density_factor = _air_density_correction_factor(
            temperature_c=np.asarray(temperature_c, dtype=float),
            pressure_hpa=np.asarray(pressure_hpa, dtype=float),
            reference_air_density_kg_per_m3=reference_air_density_kg_per_m3,
        )
        power_frac = np.clip(power_frac * density_factor, 0.0, 1.0)
    return np.asarray(power_frac * float(installed_kw) * float(dt_h), dtype=float)
