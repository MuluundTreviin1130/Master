from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


@dataclass
class DistrictBiogasCHPConfig:
    """Technical SSOT for a district-heating biogas CHP with gas engine."""

    installed_kw_el_max: Optional[float] = None
    eta_el: Optional[float] = None
    eta_th: Optional[float] = None
    min_partload: Optional[float] = None
    fuel_lhv_kwh_per_nm3: Optional[float] = None
    scheduled_downtime_days_per_year: float = 7.0
    scheduled_downtime_start_day_of_year: int = 200


def make_district_biogas_chp() -> DistrictBiogasCHPConfig:
    return DistrictBiogasCHPConfig()
