from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


@dataclass
class DistrictHeatPumpConfig:
    """Single source of truth for a large district-heating heat pump."""

    installed_kw_th_max: Optional[float] = None
    source_temp_c: Optional[float] = None
    supply_temp_c: Optional[float] = None
    return_temp_c: Optional[float] = None
    cop_max: Optional[float] = None


def make_district_heat_pump() -> DistrictHeatPumpConfig:
    return DistrictHeatPumpConfig()
