from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd


def compute_household_hotwater_load_kwh(
    usage_profile: pd.DataFrame,
    a_floor_m2: float,
) -> np.ndarray:
    """
    Convert the common usage-profile DHW intensity into an hourly household load.

    Expected input column:
    - ``Warmwasserbedarf_W_m2``: hourly domestic hot water demand intensity in W/m2

    Output:
    - hourly DHW load in kWh for the given household/building type
    """
    if "Warmwasserbedarf_W_m2" not in usage_profile.columns:
        raise KeyError("usage_profile fehlt Spalte 'Warmwasserbedarf_W_m2'")

    hotwater_w_per_m2 = usage_profile["Warmwasserbedarf_W_m2"].to_numpy(dtype=float)
    a_floor_m2 = float(a_floor_m2)
    if a_floor_m2 <= 0.0:
        raise ValueError("A_floor muss > 0 sein, um die Haushalts-DHW-Last zu berechnen.")

    # W/m2 * m2 -> W. For 1h steps, W / 1000 = kWh per timestep.
    return (hotwater_w_per_m2 * a_floor_m2) / 1000.0
