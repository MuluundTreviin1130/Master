from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


@dataclass
class DistrictWasteIncinerationConfig:
    """Technical SSOT for a district-heating waste-incineration source."""

    installed_kw_th_fixed: Optional[float] = None
    installed_kw_th_max: Optional[float] = None
    thermal_availability: Optional[float] = 0.9
    min_partload: Optional[float] = 0.0
    must_run: bool = True


def make_district_waste_incineration() -> DistrictWasteIncinerationConfig:
    return DistrictWasteIncinerationConfig()
