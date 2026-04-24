from __future__ import annotations

"""Electrolyzer conversion model.

Units:
- electric_input_kwh: electrical energy consumed in timestep [kWh_el]
- h2_output_kwh: hydrogen energy stored [kWh_H2]
"""


def run_electrolyzer(electric_input_kwh: float, p_max_kw: float, eta_ely: float, dt_h: float = 1.0) -> tuple[float, float]:
    p_cap_kwh = max(0.0, float(p_max_kw) * float(dt_h))
    el_in = min(max(0.0, float(electric_input_kwh)), p_cap_kwh)
    h2_out = el_in * max(0.0, float(eta_ely))
    return el_in, h2_out

