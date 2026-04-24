from __future__ import annotations

from dataclasses import dataclass


@dataclass
class HydrogenConfig:
    """Hydrogen module settings.

    cyclic_soc: enforce end-of-year == start-of-year with tolerance
    cyclic_soc_rtol: relative tolerance in kWh_H2
    """

    cyclic_soc: bool = True
    cyclic_soc_rtol: float = 1e-6
    coupling_enabled: bool = True
    tank_to_ely_min_hours: float = 0.5
    tank_to_ely_max_hours: float = 24.0
    fc_to_ely_min_ratio: float = 0.25
    fc_to_ely_max_ratio: float = 2.0


def make_hydrogen() -> HydrogenConfig:
    return HydrogenConfig()
