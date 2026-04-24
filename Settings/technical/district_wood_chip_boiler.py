from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


@dataclass
class DistrictWoodChipBoilerConfig:
    """Technical SSOT for a district-heating wood-chip boiler."""

    installed_kw_th_max: Optional[float] = None
    min_partload: Optional[float] = None
    max_partload: Optional[float] = None
    eta_th: Optional[float] = None
    fuel_lhv_kwh_per_kg: Optional[float] = None
    scheduled_downtime_days_per_year: float = 7.0
    scheduled_downtime_start_day_of_year: int = 200


def make_district_wood_chip_boiler() -> DistrictWoodChipBoilerConfig:
    return DistrictWoodChipBoilerConfig()
