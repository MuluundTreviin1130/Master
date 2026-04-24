from __future__ import annotations

from dataclasses import dataclass


@dataclass
class HydrogenConstraintConfig:
    tank_to_ely_min_enabled: bool = True
    tank_to_ely_max_enabled: bool = True
    fc_to_ely_min_enabled: bool = True
    fc_to_ely_max_enabled: bool = True
