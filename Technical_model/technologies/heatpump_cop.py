from __future__ import annotations

"""Household heat-pump COP contract.

The Data SSOT stores condenser/evaporator setpoints in Kelvin
(``T_flow=303.15``, ``T_flow_cool=290.15``). Carnot COP is only valid on an
absolute temperature scale, so outdoor air must be Kelvin as well.

``cop_max`` / ``eer_max`` are caps, not operating COPs. The operating COP is
``eta_cop * T_hot / (T_hot - T_cold)``, then clipped to ``[1, cap]``.
"""

from typing import Any, Mapping, Tuple

import numpy as np


_REQUIRED_HEATPUMP_KEYS = ("T_flow", "T_flow_cool", "eta_cop", "cop_max", "eer_max")
# Outdoor air and hydronic setpoints in this repo live on the Kelvin scale.
# A median below this threshold is Celsius-looking and would silently collapse
# Carnot COP toward the floor of 1.0 if mixed with Kelvin setpoints.
_KELVIN_MEDIAN_MIN = 150.0


def _require_finite_positive(name: str, value: Any) -> float:
    number = float(value)
    if not np.isfinite(number) or number <= 0.0:
        raise ValueError(f"[heatpump_cop] '{name}' must be finite and > 0, got {value!r}.")
    return number


def _require_kelvin_scale(name: str, value: float) -> float:
    if value < _KELVIN_MEDIAN_MIN:
        raise ValueError(
            f"[heatpump_cop] '{name}' must be Kelvin-scale (>= {_KELVIN_MEDIAN_MIN}), got {value}."
        )
    return value


def cop_heating_from_kelvin(
    t_outdoor_k: float,
    t_flow_k: float,
    eta_cop: float,
    cop_max: float,
) -> float:
    """Real heating COP for one hour. Temperatures must be Kelvin."""
    if t_flow_k <= t_outdoor_k:
        return 1.0
    cop_real = eta_cop * t_flow_k / (t_flow_k - t_outdoor_k)
    return min(max(cop_real, 1.0), cop_max)


def cop_cooling_from_kelvin(
    t_outdoor_k: float,
    t_flow_cool_k: float,
    eta_cop: float,
    eer_max: float,
) -> float:
    """Real cooling COP for one hour. Temperatures must be Kelvin."""
    if t_outdoor_k <= t_flow_cool_k:
        return 1.0
    cop_real = eta_cop * t_flow_cool_k / (t_outdoor_k - t_flow_cool_k)
    return min(max(cop_real, 1.0), eer_max)


def resolve_household_heatpump_cop_series(
    *,
    heatpump: Mapping[str, Any],
    t_outdoor_k: Any,
) -> Tuple[np.ndarray, np.ndarray]:
    """Return hourly heating and cooling COP arrays from Data SSOT + Kelvin outdoor air.

    This is the single runtime contract for EC_FLEX / IES household HPs. Callers
    must not substitute ``cop_max`` / ``eer_max`` as operating COPs.
    """
    missing = [key for key in _REQUIRED_HEATPUMP_KEYS if key not in heatpump or heatpump[key] is None]
    if missing:
        raise ValueError(
            "[heatpump_cop] Missing required heatpump keys: " + ", ".join(missing) + "."
        )

    t_flow_k = _require_kelvin_scale("T_flow", _require_finite_positive("T_flow", heatpump["T_flow"]))
    t_flow_cool_k = _require_kelvin_scale(
        "T_flow_cool", _require_finite_positive("T_flow_cool", heatpump["T_flow_cool"])
    )
    eta_cop = _require_finite_positive("eta_cop", heatpump["eta_cop"])
    cop_max = _require_finite_positive("cop_max", heatpump["cop_max"])
    eer_max = _require_finite_positive("eer_max", heatpump["eer_max"])
    if eta_cop > 1.0:
        raise ValueError(f"[heatpump_cop] eta_cop must be <= 1, got {eta_cop}.")

    t_out = np.asarray(t_outdoor_k, dtype=float).reshape(-1)
    if t_out.size == 0:
        raise ValueError("[heatpump_cop] T_outdoor must be a non-empty series.")
    if np.any(~np.isfinite(t_out)):
        raise ValueError("[heatpump_cop] T_outdoor must be finite.")
    median_out = float(np.median(t_out))
    if median_out < _KELVIN_MEDIAN_MIN:
        raise ValueError(
            "[heatpump_cop] T_outdoor looks like Celsius "
            f"(median={median_out:.2f}). Household HP COP requires Kelvin outdoor air."
        )

    delta_heat = t_flow_k - t_out
    cop_carnot_heat = np.divide(t_flow_k, delta_heat, out=np.ones_like(t_out), where=delta_heat > 0.0)
    cop_heat = np.where(
        delta_heat > 0.0,
        np.clip(eta_cop * cop_carnot_heat, 1.0, cop_max),
        1.0,
    )

    delta_cool = t_out - t_flow_cool_k
    cop_carnot_cool = np.divide(t_flow_cool_k, delta_cool, out=np.ones_like(t_out), where=delta_cool > 0.0)
    cop_cool = np.where(
        delta_cool > 0.0,
        np.clip(eta_cop * cop_carnot_cool, 1.0, eer_max),
        1.0,
    )
    return np.asarray(cop_heat, dtype=float), np.asarray(cop_cool, dtype=float)
