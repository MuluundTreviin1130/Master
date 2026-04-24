from __future__ import annotations

"""Thermal flexibility control helper.

Returns additional HVAC electrical capacity [kWh_el] that can be consumed
without violating extended comfort band [T_min-delta_T, T_max+delta_T].
"""

from Technical_model.technologies.buildings.thermal_building_state import ThermalBuildingState


def thermflex_extra_cap_kwh(
    state: ThermalBuildingState,
    t_out_k: float,
    delta_t_k: float,
    cop_heat: float,
    cop_cool: float,
) -> tuple[float, str]:
    low = state.t_min_k - max(0.0, float(delta_t_k))
    high = state.t_max_k + max(0.0, float(delta_t_k))
    # Heating pre-charge in colder hours, cooling pre-charge in warmer hours.
    if float(t_out_k) < state.ti_k:
        delta_k = max(0.0, high - state.ti_k)
        thermal_kwh = delta_k * state.c_th_wh_per_k / 1000.0
        return thermal_kwh / max(1e-9, float(cop_heat)), "heat"
    delta_k = max(0.0, state.ti_k - low)
    thermal_kwh = delta_k * state.c_th_wh_per_k / 1000.0
    return thermal_kwh / max(1e-9, float(cop_cool)), "cool"
