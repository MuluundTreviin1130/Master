from __future__ import annotations

"""Fuel-cell conversion model.

Units:
- h2_input_kwh: hydrogen energy drawn from tank [kWh_H2]
- electric_output_kwh: electrical energy delivered [kWh_el]
"""


def run_fuel_cell(required_electric_kwh: float, p_max_kw: float, eta_fc: float, h2_available_kwh: float, dt_h: float = 1.0) -> tuple[float, float]:
    p_cap_kwh = max(0.0, float(p_max_kw) * float(dt_h))
    el_target = min(max(0.0, float(required_electric_kwh)), p_cap_kwh)
    eff = max(1e-9, float(eta_fc))
    h2_needed = el_target / eff
    h2_used = min(max(0.0, float(h2_available_kwh)), h2_needed)
    el_out = h2_used * eff
    return el_out, h2_used

