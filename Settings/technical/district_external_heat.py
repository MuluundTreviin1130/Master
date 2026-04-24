from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


@dataclass
class DistrictExternalHeatConfig:
    """Technical SSOT for external industrial waste heat at the DH bus."""

    installed_kw_th_fixed: Optional[float] = None
    installed_kw_th_max: Optional[float] = None
    thermal_availability: Optional[float] = 1.0
    min_partload: Optional[float] = 0.0


def make_district_external_heat() -> DistrictExternalHeatConfig:
    return DistrictExternalHeatConfig()
