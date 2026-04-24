from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


@dataclass
class DistrictGasBoilerConfig:
    """Technical SSOT for a district-heating gas boiler / fossil peak boiler."""

    installed_kw_th_fixed: Optional[float] = None
    installed_kw_th_max: Optional[float] = None
    min_partload: Optional[float] = None
    max_partload: Optional[float] = None
    eta_th: Optional[float] = None
    fuel_lhv_kwh_per_m3: Optional[float] = None
    scheduled_downtime_days_per_year: float = 0.0
    scheduled_downtime_start_day_of_year: int = 200


def make_district_gas_boiler() -> DistrictGasBoilerConfig:
    return DistrictGasBoilerConfig()
