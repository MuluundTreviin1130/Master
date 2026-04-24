from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


@dataclass
class DistrictGeothermalConfig:
    """Technical SSOT for a district-heating geothermal ORC source."""

    installed_kw_el_max: Optional[float] = None
    heat_to_power_ratio: Optional[float] = None
    scheduled_downtime_days_per_year: float = 7.0
    scheduled_downtime_start_day_of_year: int = 200


def make_district_geothermal() -> DistrictGeothermalConfig:
    return DistrictGeothermalConfig()
