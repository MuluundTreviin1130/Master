from __future__ import annotations

"""Hydrogen tank state update helpers."""


def clamp_soc(e_h2_kwh: float, e_max_kwh: float) -> float:
    return min(max(0.0, float(e_h2_kwh)), max(0.0, float(e_max_kwh)))


def cyclic_soc_ok(e_start_kwh: float, e_end_kwh: float, e_max_kwh: float, rtol: float = 1e-6) -> bool:
    tol = float(rtol) * max(1.0, float(e_max_kwh))
    return abs(float(e_end_kwh) - float(e_start_kwh)) <= tol

