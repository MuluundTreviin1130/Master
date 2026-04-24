from __future__ import annotations

from dataclasses import dataclass


@dataclass
class TechnologyActivationConfig:
    """Central SSOT for enabling/disabling technologies."""

    district_heat_pump: bool = False
    district_thermal_storage: bool = False
    district_external_heat: bool = False
    district_gas_boiler: bool = False
    district_wood_chip_boiler: bool = False
    district_geothermal: bool = False
    district_gas_chp: bool = False
    district_biogas_chp: bool = False
    district_solar_thermal: bool = False
    district_biomass_chp: bool = False
    district_waste_incineration: bool = False


def make_technology_activation() -> TechnologyActivationConfig:
    return TechnologyActivationConfig()
