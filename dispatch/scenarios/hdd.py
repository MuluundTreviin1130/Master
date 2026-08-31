"""Celsius heating-degree-hour contract for historical DH demand scaling.

Kept import-light (numpy only) so unit tests can lock the Kelvin-vs-Celsius
guard without pulling pandas/weather IO from historical_data.py.
"""

from __future__ import annotations

import numpy as np

# HDD uses a 15 °C base. Kelvin outdoor (~280 K) makes every hour HDD=0, so
# downstream _safe_ratio falls through to 1.0 and historical DH demand never
# scales with weather.
HEATING_DEGREE_BASE_C = 15.0
_AMBIENT_CELSIUS_MEDIAN_MAX = 150.0


def require_ambient_temperature_c(temperature_c: np.ndarray, *, ctx: str) -> np.ndarray:
    """Reject Kelvin-looking ambient series before HDD scaling.

    IES profile T_outdoor is Kelvin. If that series is forwarded as
    ambient_temperature_c, 15 − T is negative for every hour, base HDD is
    identically zero, and every scenario DH factor silently becomes 1.0.
    """
    arr = np.asarray(temperature_c, dtype=float).reshape(-1)
    finite = arr[np.isfinite(arr)]
    if finite.size == 0:
        raise ValueError(f"[dispatch.scenarios] {ctx} ambient temperature series has no finite values.")
    median = float(np.nanmedian(finite))
    if median > _AMBIENT_CELSIUS_MEDIAN_MAX:
        raise ValueError(
            f"[dispatch.scenarios] {ctx} ambient_temperature_c looks like Kelvin "
            f"(median={median:.2f}). HDD uses a {HEATING_DEGREE_BASE_C:.0f} °C base; pass Celsius."
        )
    return arr


def heating_degree_hours(temperature_c: np.ndarray, *, ctx: str) -> np.ndarray:
    arr = require_ambient_temperature_c(temperature_c, ctx=ctx)
    return np.maximum(0.0, HEATING_DEGREE_BASE_C - arr)
