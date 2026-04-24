from __future__ import annotations

from dataclasses import dataclass


@dataclass
class FullLoadHoursConfig:
    """Central operating assumptions used to translate annual potentials into capacity caps."""

    district_biomass_chp: float = 7500.0
    district_biogas_chp: float = 7500.0
    district_wood_chip_boiler: float = 7500.0
    district_solar_thermal: float = 1200.0
    district_waste_incineration: float = 7500.0


def make_full_load_hours() -> FullLoadHoursConfig:
    return FullLoadHoursConfig()
