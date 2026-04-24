from __future__ import annotations

from typing import Any

import numpy as np


def _weighted_average(values: Any, probabilities: np.ndarray | None = None) -> np.ndarray:
    arr = np.asarray(values, dtype=float)
    if probabilities is None:
        return np.asarray(arr, dtype=float)
    probs = np.asarray(probabilities, dtype=float).reshape(-1)
    if arr.ndim == 1:
        return arr
    if arr.shape[0] != probs.size:
        raise ValueError(
            f"[thermflex_metrics] Expected first dimension {probs.size} for weighted average, got {arr.shape[0]}."
        )
    return np.tensordot(probs, arr, axes=(0, 0))


def compute_series_peak_change_kw(
    actual: Any,
    reference: Any,
    *,
    probabilities: np.ndarray | None = None,
) -> float:
    """Return the scalar peak delta between an actual and reference series."""

    actual_arr = _weighted_average(actual, probabilities).reshape(-1)
    reference_arr = _weighted_average(reference, probabilities).reshape(-1)
    if actual_arr.shape != reference_arr.shape:
        raise ValueError(
            f"[thermflex_metrics] actual and reference must have identical shape, got "
            f"{actual_arr.shape} vs {reference_arr.shape}."
        )
    if actual_arr.size == 0:
        return 0.0
    return float(np.max(actual_arr) - np.max(reference_arr))


def compute_series_peak_kw(
    series: Any,
    *,
    probabilities: np.ndarray | None = None,
) -> float:
    """Return the absolute peak of a scalar time series."""

    arr = _weighted_average(series, probabilities).reshape(-1)
    if arr.size == 0:
        return 0.0
    return float(np.max(arr))


def _rebound_after_reduction_kwh(diff: np.ndarray, eps: float = 1e-9) -> float:
    negative_seen = False
    rebound = 0.0
    for value in np.asarray(diff, dtype=float).reshape(-1):
        if value < -eps:
            negative_seen = True
            continue
        if negative_seen and value > eps:
            rebound += float(value)
    return float(rebound)


def compute_thermflex_series_metrics(
    space_heat: Any,
    space_heat_ref: Any,
    *,
    probabilities: np.ndarray | None = None,
) -> dict[str, float | np.ndarray]:
    actual = _weighted_average(space_heat, probabilities).reshape(-1)
    reference = _weighted_average(space_heat_ref, probabilities).reshape(-1)
    if actual.shape != reference.shape:
        raise ValueError(
            f"[thermflex_metrics] space_heat and space_heat_ref must have identical shape, got {actual.shape} vs {reference.shape}."
        )

    diff = actual - reference
    inventory = np.cumsum(diff, dtype=float)
    ramps = np.diff(actual) if actual.size >= 2 else np.zeros(0, dtype=float)

    return {
        "thermflex_shifted_space_heat_kwh": float(np.sum(np.abs(diff)) / 2.0),
        "thermflex_additional_space_heat_kwh": float(max(0.0, np.sum(diff))),
        "thermflex_rebound_kwh": _rebound_after_reduction_kwh(diff),
        "thermflex_peak_change_kw": compute_series_peak_change_kw(actual, reference),
        "thermflex_heat_up_ramp_kw_per_h": float(max(0.0, np.max(ramps))) if ramps.size else 0.0,
        "thermflex_heat_down_ramp_kw_per_h": float(max(0.0, np.max(-ramps))) if ramps.size else 0.0,
        "thermflex_effective_thermal_storage_kwh": float(max(0.0, np.max(inventory) - np.min(inventory)))
        if inventory.size
        else 0.0,
        "thermflex_max_preheat_headroom_kwh": float(max(0.0, np.max(inventory))) if inventory.size else 0.0,
        "thermflex_space_heat_delta_kwh": diff,
        "thermflex_virtual_storage_inventory_kwh": inventory,
    }
