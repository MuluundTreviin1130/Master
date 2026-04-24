from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Optional

from Data.energy_potentials.Vienna.energy_potentials import (
    build_energy_potentials_values as build_energy_potentials_values_vienna,
)


def _gwh_to_kwh(value_gwh: Optional[float]) -> Optional[float]:
    if value_gwh is None:
        return None
    return float(value_gwh) * 1_000_000.0


@dataclass
class EnergyPotentialsConfig:
    """Hard technology potentials / availability caps."""

    source: str = "manual_snapshot"
    location: Optional[str] = None
    source_file_path: Optional[str] = None
    enforce_hard_caps: bool = False

    pv_kwp_max: Optional[float] = None
    small_wind_kw_max: Optional[float] = None
    large_wind_kw_max: Optional[float] = None

    district_heat_pump_kw_th_max: Optional[float] = None
    district_thermal_storage_kwh_th_max: Optional[float] = None
    district_wood_chip_boiler_kw_th_max: Optional[float] = None
    district_biomass_chp_kw_th_max: Optional[float] = None
    district_geothermal_kw_el_max: Optional[float] = None
    district_gas_chp_kw_el_max: Optional[float] = None
    district_biogas_chp_kw_el_max: Optional[float] = None
    district_solar_thermal_kw_th_max: Optional[float] = None
    district_waste_incineration_kw_th_max: Optional[float] = None
    district_wastewater_heat_kw_th_max: Optional[float] = None

    district_waste_incineration_gwh_per_year_max: Optional[float] = None
    district_biogas_feedstock_gwh_per_year_max: Optional[float] = None
    district_biomass_feedstock_gwh_per_year_max: Optional[float] = None
    district_solar_thermal_rooftop_avg_mwh_per_ha_per_year: Optional[float] = None
    district_solar_thermal_open_field_avg_mwh_per_ha_per_year: Optional[float] = None
    district_solar_thermal_rooftop_area_ha: Optional[float] = None
    district_solar_thermal_open_field_area_ha: Optional[float] = None
    district_solar_thermal_rooftop_gwh_per_year_max: Optional[float] = None
    district_solar_thermal_open_field_gwh_per_year_max: Optional[float] = None
    district_solar_thermal_total_gwh_per_year_max: Optional[float] = None

    def to_bounds_caps(self) -> Dict[str, float]:
        caps: Dict[str, float] = {}
        mapping = {
            "pv_kwp": self.pv_kwp_max,
            "small_wind_kw": self.small_wind_kw_max,
            "large_wind_kw": self.large_wind_kw_max,
            "district_heat_pump_kw_th": self.district_heat_pump_kw_th_max,
            "district_thermal_storage_kwh_th": self.district_thermal_storage_kwh_th_max,
            "district_wood_chip_boiler_kw_th": self.district_wood_chip_boiler_kw_th_max,
            "district_biomass_chp_kw_th": self.district_biomass_chp_kw_th_max,
            "district_geothermal_kw_el": self.district_geothermal_kw_el_max,
            "district_gas_chp_kw_el": self.district_gas_chp_kw_el_max,
            "district_biogas_chp_kw_el": self.district_biogas_chp_kw_el_max,
            "district_solar_thermal_kw_th": self.district_solar_thermal_kw_th_max,
            "district_waste_incineration_kw_th": self.district_waste_incineration_kw_th_max,
        }
        for key, value in mapping.items():
            if value is not None:
                caps[key] = float(value)
        return caps

    def to_annual_energy_caps_kwh(self) -> Dict[str, float]:
        caps: Dict[str, float] = {}
        mapping = {
            "district_waste_incineration_kwh_per_year": _gwh_to_kwh(self.district_waste_incineration_gwh_per_year_max),
            "district_biogas_feedstock_kwh_per_year": _gwh_to_kwh(self.district_biogas_feedstock_gwh_per_year_max),
            "district_biomass_feedstock_kwh_per_year": _gwh_to_kwh(self.district_biomass_feedstock_gwh_per_year_max),
            "district_solar_thermal_rooftop_kwh_per_year": _gwh_to_kwh(self.district_solar_thermal_rooftop_gwh_per_year_max),
            "district_solar_thermal_open_field_kwh_per_year": _gwh_to_kwh(self.district_solar_thermal_open_field_gwh_per_year_max),
            "district_solar_thermal_total_kwh_per_year": _gwh_to_kwh(self.district_solar_thermal_total_gwh_per_year_max),
        }
        for key, value in mapping.items():
            if value is not None:
                caps[key] = float(value)
        return caps


def make_energy_potentials(location: str) -> EnergyPotentialsConfig:
    if not isinstance(location, str) or not location.strip():
        raise ValueError("[energy_potentials] Explicit non-empty location is required.")
    resolved_location = location.strip()
    if resolved_location == "Vienna":
        return EnergyPotentialsConfig(**build_energy_potentials_values_vienna())
    raise ValueError(
        f"[energy_potentials] No hardcoded energy-potentials snapshot registered for location='{resolved_location}'. "
        "Add a dedicated file under Data/energy_potentials/<Location>/."
    )
