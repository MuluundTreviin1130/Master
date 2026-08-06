"""Fail-fast COP resolution for district heat-pump MILP assets.

The heat-pump electricity draw is ``thermal / COP``. Inventing ``COP=1.0`` when
the series is missing understates electricity by the true Carnot/settings COP
(typically ~3–4), which silently corrupts DH merit order, grid import, and
Learning teacher labels. Coercing a zero-filled series through ``max(1e-9, ·)``
with positive thermal capacity also explodes Big-M import bounds
(``capacity / 1e-9``) and weakens import/export binaries numerically.
"""

from __future__ import annotations

from typing import Any, Mapping

import numpy as np


def resolve_district_heat_pump_cop(
    series: Mapping[str, Any],
    *,
    hp_th_cap: float,
    n: int,
    label: str,
) -> np.ndarray:
    """Return the HP COP series without silent ``ones`` / ``1e-9`` invention.

    - When ``hp_th_cap > 0`` the COP series is mandatory: present, length ``n``,
      finite, and strictly positive.
    - When ``hp_th_cap <= 0`` COP cannot affect dispatch or Big-M
      (``cap / cop == 0``). An explicit series is validated for length when
      present; otherwise zeros are returned (never ones).
    """

    hp_th_cap = float(hp_th_cap)
    raw = series.get("district_heat_pump_cop")
    if hp_th_cap > 0.0:
        if raw is None:
            raise ValueError(
                f"[{label}] assets['district_heat_pump_kw_th']={hp_th_cap} > 0 requires "
                "series['district_heat_pump_cop'] with finite values > 0."
            )
        arr = np.asarray(raw, dtype=float).reshape(-1)
        if arr.size != n:
            raise ValueError(
                f"[{label}] series['district_heat_pump_cop'] length must equal horizon "
                f"n={n}, got {arr.size}."
            )
        if np.any(~np.isfinite(arr)) or np.any(arr <= 0.0):
            raise ValueError(
                f"[{label}] series['district_heat_pump_cop'] must be finite and > 0 when "
                "district_heat_pump_kw_th > 0."
            )
        return arr

    if raw is None:
        return np.zeros(n, dtype=float)
    arr = np.asarray(raw, dtype=float).reshape(-1)
    if arr.size != n:
        raise ValueError(
            f"[{label}] series['district_heat_pump_cop'] length must equal horizon "
            f"n={n}, got {arr.size}."
        )
    return arr
