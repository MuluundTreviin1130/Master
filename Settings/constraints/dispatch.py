from __future__ import annotations

from dataclasses import dataclass


@dataclass
class DispatchConstraintConfig:
    unserved_penalty_eur_per_kwh: float = 1e6
    spill_penalty_eur_per_kwh: float = 1e-6
    allow_grid_export: bool = True
    allow_unserved_el: bool = True
    allow_unserved_dh: bool = True
    enable_gas_procurement_model: bool = False
    enable_co2_cost_model: bool = True
