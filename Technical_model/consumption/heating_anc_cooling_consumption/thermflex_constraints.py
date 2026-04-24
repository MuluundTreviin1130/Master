from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

from Technical_model.consumption.heating_anc_cooling_consumption.heating_control import (
    active_reference_heating_setpoint_k,
    comfort_band_enabled,
    comfort_band_k,
    max_flex_duration_h,
    max_flex_events_per_day,
)


def build_thermflex_constraint_frame(timestamps, heating_control: Any) -> pd.DataFrame:
    """Build an explicit thermflex constraint table from the configured reference mode.

    This is intentionally separate from the forward heating controller:
    the controller follows only the active operating setpoint and hysteresis,
    while thermflex constraints define the admissible deviation band that a later
    optimizer may exploit.
    """

    idx = pd.DatetimeIndex(timestamps)
    band_k = comfort_band_k(heating_control) if comfort_band_enabled(heating_control) else 0.0
    max_duration = max_flex_duration_h(heating_control)
    max_events = max_flex_events_per_day(heating_control)

    reference_c = []
    lower_c = []
    upper_c = []
    for ts in idx:
        ref_k = active_reference_heating_setpoint_k(int(ts.hour), heating_control)
        ref_c = float(ref_k - 273.15)
        reference_c.append(ref_c)
        lower_c.append(ref_c - band_k)
        upper_c.append(ref_c + band_k)

    return pd.DataFrame(
        {
            "timestamp": idx,
            "reference_setpoint_c": reference_c,
            "flex_lower_c": lower_c,
            "flex_upper_c": upper_c,
            "comfort_band_k": float(band_k),
            "max_flex_duration_h": int(max_duration),
            "max_flex_events_per_day": int(max_events),
        }
    )


def apply_activation_schedule(
    constraint_frame: pd.DataFrame,
    flex_active,
) -> pd.DataFrame:
    """Apply a boolean flex activation schedule to the admissible band.

    Inactive hours collapse back to the reference setpoint. Active hours expose the
    configured flex bounds. This mirrors the intended later optimizer semantics.
    """

    frame = constraint_frame.copy()
    active = np.asarray(flex_active, dtype=bool)
    if len(active) != len(frame):
        raise ValueError(
            "[thermflex_constraints] flex_active length must match constraint frame length."
        )
    frame["flex_active"] = active
    frame["active_lower_c"] = np.where(active, frame["flex_lower_c"], frame["reference_setpoint_c"])
    frame["active_upper_c"] = np.where(active, frame["flex_upper_c"], frame["reference_setpoint_c"])
    return frame


def summarize_activation_schedule(
    constraint_frame: pd.DataFrame,
    flex_active,
) -> pd.DataFrame:
    """Summarize active hours and event starts per day for a candidate schedule."""

    frame = apply_activation_schedule(constraint_frame, flex_active)
    ts = pd.DatetimeIndex(frame["timestamp"])
    day = ts.normalize()
    active_int = frame["flex_active"].astype(int).to_numpy(dtype=int)
    starts = np.zeros(len(frame), dtype=int)
    starts[0] = active_int[0]
    starts[1:] = np.maximum(0, active_int[1:] - active_int[:-1])
    frame["flex_event_start"] = starts
    summary = (
        frame.assign(day=day)
        .groupby("day", as_index=False)
        .agg(
            active_hours=("flex_active", "sum"),
            event_starts=("flex_event_start", "sum"),
            max_flex_duration_h=("max_flex_duration_h", "max"),
            max_flex_events_per_day=("max_flex_events_per_day", "max"),
        )
    )
    summary["duration_violation_h"] = np.maximum(
        0,
        summary["active_hours"].to_numpy(dtype=int) - summary["max_flex_duration_h"].to_numpy(dtype=int),
    )
    summary["event_violation_count"] = np.maximum(
        0,
        summary["event_starts"].to_numpy(dtype=int) - summary["max_flex_events_per_day"].to_numpy(dtype=int),
    )
    summary["is_feasible"] = (
        (summary["duration_violation_h"] <= 0) & (summary["event_violation_count"] <= 0)
    )
    return summary


def validate_activation_schedule(
    constraint_frame: pd.DataFrame,
    flex_active,
) -> dict:
    """Return a compact feasibility check for a candidate thermflex schedule."""

    daily = summarize_activation_schedule(constraint_frame, flex_active)
    violating_days = daily.loc[~daily["is_feasible"], "day"].dt.strftime("%Y-%m-%d").tolist()
    return {
        "is_feasible": bool(daily["is_feasible"].all()),
        "violating_days": violating_days,
        "max_active_hours_used": int(daily["active_hours"].max()) if len(daily) else 0,
        "max_event_starts_used": int(daily["event_starts"].max()) if len(daily) else 0,
    }
