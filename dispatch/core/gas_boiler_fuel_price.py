from __future__ import annotations

"""Resolve the fossil peak-boiler fuel price used by MILP dispatch.

Vienna economics intentionally store a gas/oil mix price in
``district_gas_boiler.fuel_eur_per_m3`` (gas-volume equivalent). That mix must
drive peak-boiler fuel cost in the MILP. Reusing the Gas-CHP day-ahead gas
series silently drops the oil share and underprices the boiler.
"""

from typing import Any, Mapping

import numpy as np


def constant_fuel_price_eur_per_mwh_from_m3(
    *,
    fuel_eur_per_m3: float,
    fuel_lhv_kwh_per_m3: float,
    error_label: str,
) -> float:
    """Convert a gas-volume-equivalent fuel price into EUR/MWh_fuel."""

    price_m3 = float(fuel_eur_per_m3)
    lhv = float(fuel_lhv_kwh_per_m3)
    if not np.isfinite(price_m3) or price_m3 <= 0.0:
        raise ValueError(f"[{error_label}] fuel_eur_per_m3 must be finite and > 0, got {fuel_eur_per_m3!r}.")
    if not np.isfinite(lhv) or lhv <= 0.0:
        raise ValueError(
            f"[{error_label}] fuel_lhv_kwh_per_m3 must be finite and > 0 to convert fuel_eur_per_m3, got {fuel_lhv_kwh_per_m3!r}."
        )
    return price_m3 * 1000.0 / lhv


def resolve_gas_boiler_fuel_price_eur_per_mwh(
    series: Mapping[str, Any],
    params: Mapping[str, Any],
    *,
    n_steps: int,
    align_arr,
    error_label: str,
) -> np.ndarray:
    """Resolve the peak-boiler fuel-price series for one MILP solve.

    Precedence:
    1. Explicit ``district_gas_boiler_day_ahead_price_eur_per_mwh_fuel`` series
       packed by the integrated energy system from economics SSOT (or from the
       optional day-ahead override flag).
    2. Constant conversion from packed ``district_gas_boiler_fuel_cost_eur_per_m3``
       and ``district_gas_boiler_fuel_lhv_kwh_per_m3``.

    The Gas-CHP gas price series is intentionally never used here.
    """

    if n_steps < 0:
        raise ValueError(f"[{error_label}] n_steps must be >= 0, got {n_steps}.")

    raw = series.get("district_gas_boiler_day_ahead_price_eur_per_mwh_fuel")
    if raw is not None:
        price = np.asarray(align_arr(raw, n_steps), dtype=float).reshape(-1)
    else:
        # Direct DispatchInput callers may omit the series; still refuse to fall
        # back to the Gas-CHP gas price and require the boiler economics instead.
        price_mwh = constant_fuel_price_eur_per_mwh_from_m3(
            fuel_eur_per_m3=float(params.get("district_gas_boiler_fuel_cost_eur_per_m3", 0.0) or 0.0),
            fuel_lhv_kwh_per_m3=float(params.get("district_gas_boiler_fuel_lhv_kwh_per_m3", 0.0) or 0.0),
            error_label=error_label,
        )
        price = np.full(n_steps, price_mwh, dtype=float)

    if price.size != n_steps:
        raise ValueError(
            f"[{error_label}] district_gas_boiler fuel price length {price.size} != n_steps={n_steps}."
        )
    if np.any(~np.isfinite(price)) or np.any(price <= 0.0):
        raise ValueError(
            f"[{error_label}] district_gas_boiler fuel price must be finite and strictly positive."
        )
    return price
