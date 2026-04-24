from __future__ import annotations

"""Indoor temperature state model for one member/building.

Assumptions:
- Time step is 1h by default.
- Heat balance uses Wh and W consistently:
  delta_T = (Q_net_W * dt_h) / C_th_Wh_per_K
"""

from dataclasses import dataclass

import numpy as np


@dataclass
class ThermalBuildingState:
    ti_k: float
    c_th_wh_per_k: float
    ua_w_per_k: float
    a_floor_m2: float
    t_min_k: float
    t_max_k: float
    dt_h: float = 1.0

    def passive_step(self, t_out_k: float, internal_w_m2: float, solar_w_m2: float) -> float:
        q_loss_w = self.ua_w_per_k * (self.ti_k - float(t_out_k))
        q_internal_w = float(internal_w_m2) * self.a_floor_m2
        q_solar_w = float(solar_w_m2) * self.a_floor_m2
        q_net_w = q_internal_w + q_solar_w - q_loss_w
        self.ti_k += (q_net_w * self.dt_h) / max(1e-9, self.c_th_wh_per_k)
        return self.ti_k

    def base_hvac_energy(self) -> tuple[float, float]:
        """Clamp TI to base comfort band and return thermal demand in kWh_th."""
        heat_kwh = 0.0
        cool_kwh = 0.0
        if self.ti_k < self.t_min_k:
            heat_kwh = (self.t_min_k - self.ti_k) * self.c_th_wh_per_k / 1000.0
            self.ti_k = self.t_min_k
        elif self.ti_k > self.t_max_k:
            cool_kwh = (self.ti_k - self.t_max_k) * self.c_th_wh_per_k / 1000.0
            self.ti_k = self.t_max_k
        return heat_kwh, cool_kwh


def smooth_effective_outdoor_temperature(t_out_k: np.ndarray, smoothing_hours: float) -> np.ndarray:
    """Trailing moving-average ambient for slower building-envelope dynamics."""
    arr = np.asarray(t_out_k, dtype=float).reshape(-1)
    window = max(1, int(round(float(smoothing_hours))))
    if window <= 1 or arr.size <= 1:
        return arr.copy()
    out = np.empty_like(arr)
    csum = np.cumsum(np.insert(arr, 0, 0.0))
    for idx in range(arr.size):
        start = max(0, idx - window + 1)
        count = idx - start + 1
        out[idx] = (csum[idx + 1] - csum[start]) / float(count)
    return out
