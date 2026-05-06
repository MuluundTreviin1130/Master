from __future__ import annotations

from typing import Any

import numpy as np


def dispatch_series_array(values: Any, n_steps: int, *, label: str) -> np.ndarray:
    """Return a one-dimensional dispatch series only when its horizon is exact.

    MILP dispatch decisions are hour-indexed. Padding a short series with its
    last value or truncating a long series shifts prices, availability, CO2
    factors, or thermal demand against the optimization horizon and silently
    corrupts both dispatch decisions and KPIs. Missing optional series must be
    handled by the caller with an explicit length-matched zero/one default.
    """

    arr = np.asarray(values, dtype=float).reshape(-1)
    if arr.size != int(n_steps):
        raise ValueError(
            f"[dispatch.series] Series '{label}' expected horizon "
            f"{int(n_steps)}, got {arr.size}."
        )
    return arr


def optional_dispatch_series(
    series: dict[str, Any],
    key: str,
    n_steps: int,
    *,
    default: float = 0.0,
    nonnegative: bool = False,
) -> np.ndarray:
    """Read an optional dispatch series with an explicit length-matched default."""

    if key in series:
        arr = dispatch_series_array(series[key], n_steps, label=key)
    else:
        arr = np.full(int(n_steps), float(default), dtype=float)
    if nonnegative:
        arr = np.maximum(0.0, arr)
    return arr
