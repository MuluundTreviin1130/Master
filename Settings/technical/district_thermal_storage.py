from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


@dataclass
class DistrictThermalStorageConfig:
    """Single source of truth for a central district-heating thermal store."""

    installed_kwh_th_max: Optional[float] = None
    min_temp_c: Optional[float] = None
    max_temp_c: Optional[float] = None
    initial_soc_fraction: Optional[float] = None
    charge_efficiency: Optional[float] = None
    discharge_efficiency: Optional[float] = None
    standing_loss_kwh_per_day: Optional[float] = None
    cp_water_kj_per_kgk: float = 4.2


def make_district_thermal_storage() -> DistrictThermalStorageConfig:
    return DistrictThermalStorageConfig()
