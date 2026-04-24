from __future__ import annotations

"""Stateful hydrogen subsystem (ELY + tank + FC)."""

from dataclasses import dataclass

from .electrolyzer_model import run_electrolyzer
from .fuel_cell_model import run_fuel_cell
from .h2_tank_model import clamp_soc, cyclic_soc_ok


@dataclass
class HydrogenSystem:
    p_ely_max_kw: float
    e_h2_max_kwh: float
    p_fc_max_kw: float
    eta_ely: float
    eta_fc: float
    soc_kwh: float = 0.0
    dt_h: float = 1.0

    def charge(self, available_electric_kwh: float) -> tuple[float, float]:
        """Use surplus electricity for electrolysis.

        Returns:
            electric_used_kwh, h2_stored_kwh
        """
        room = max(0.0, self.e_h2_max_kwh - self.soc_kwh)
        el_in, h2_out = run_electrolyzer(available_electric_kwh, self.p_ely_max_kw, self.eta_ely, self.dt_h)
        h2_stored = min(room, h2_out)
        if h2_out > 0.0 and h2_stored < h2_out:
            el_in *= h2_stored / h2_out
        self.soc_kwh = clamp_soc(self.soc_kwh + h2_stored, self.e_h2_max_kwh)
        return el_in, h2_stored

    def discharge(self, required_electric_kwh: float) -> tuple[float, float]:
        """Use fuel cell during deficit.

        Returns:
            electric_out_kwh, h2_used_kwh
        """
        el_out, h2_used = run_fuel_cell(required_electric_kwh, self.p_fc_max_kw, self.eta_fc, self.soc_kwh, self.dt_h)
        self.soc_kwh = clamp_soc(self.soc_kwh - h2_used, self.e_h2_max_kwh)
        return el_out, h2_used

    def cyclic_ok(self, start_soc_kwh: float, rtol: float) -> bool:
        return cyclic_soc_ok(start_soc_kwh, self.soc_kwh, self.e_h2_max_kwh, rtol=rtol)

