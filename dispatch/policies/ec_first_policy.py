from __future__ import annotations

"""EC-first dispatch policy with fixed merit order.

All energy values are expected in kWh for the current timestep (typically 1h).
"""


def allocate_surplus(
    surplus_kwh: float,
    ev_charge_cap_kwh: float,
    thermflex_cap_kwh: float,
    bess_charge_cap_kwh: float,
    h2_ely_cap_kwh: float,
) -> dict:
    rem = max(0.0, float(surplus_kwh))
    ev = min(rem, max(0.0, float(ev_charge_cap_kwh)))
    rem -= ev
    thermflex = min(rem, max(0.0, float(thermflex_cap_kwh)))
    rem -= thermflex
    bess = min(rem, max(0.0, float(bess_charge_cap_kwh)))
    rem -= bess
    h2 = min(rem, max(0.0, float(h2_ely_cap_kwh)))
    rem -= h2
    return {
        "ev_charge": ev,
        "thermflex": thermflex,
        "bess_charge": bess,
        "h2_electrolysis": h2,
        "export": max(0.0, rem),
    }


def allocate_deficit(
    deficit_kwh: float,
    v2h_discharge_cap_kwh: float,
    bess_discharge_cap_kwh: float,
    h2_fc_cap_kwh: float,
) -> dict:
    rem = max(0.0, float(deficit_kwh))
    v2h = min(rem, max(0.0, float(v2h_discharge_cap_kwh)))
    rem -= v2h
    bess = min(rem, max(0.0, float(bess_discharge_cap_kwh)))
    rem -= bess
    h2 = min(rem, max(0.0, float(h2_fc_cap_kwh)))
    rem -= h2
    return {
        "v2h_discharge": v2h,
        "bess_discharge": bess,
        "h2_fuel_cell": h2,
        "import": max(0.0, rem),
    }

