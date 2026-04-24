from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from Data.district_heating.Vienna.solar_thermal_reference_site import (
    build_solar_thermal_reference_site_values as build_solar_thermal_reference_site_values_vienna,
)


@dataclass
class DistrictSolarThermalConfig:
    """Technical SSOT for a district-heating solar-thermal source."""

    installed_kw_th_fixed: Optional[float] = None
    installed_kw_th_max: Optional[float] = None
    collector_model: str = "oemof_flat_plate"
    irradiance_input_type: str = "ghi"
    # The repo currently has GHI as the solar input truth. Raw DHI is therefore
    # not mandatory in v1, but if tilt/azimuth are active the decomposition path
    # must still be explicit. We use Erbs; nothing gets silently fabricated.
    irradiance_decomposition_model: str = "erbs"
    collector_tilt_deg: float = 50.0
    collector_azimuth_deg: float = 180.0
    eta_0: float = 0.78
    a_1: float = 3.2
    a_2: float = 0.015
    specific_nominal_capacity_kw_per_m2: float = 0.671
    temp_collector_inlet_mode: str = "dh_return_bus"
    reference_site_name: str = ""
    reference_latitude_deg: Optional[float] = None
    reference_longitude_deg: Optional[float] = None
    reference_site_source_urls: list[str] = field(default_factory=list)
    reference_site_note: str = ""


def make_district_solar_thermal(location: str | None = None) -> DistrictSolarThermalConfig:
    cfg = DistrictSolarThermalConfig()
    if location == "Vienna":
        raw = build_solar_thermal_reference_site_values_vienna()
        cfg.reference_site_name = str(raw["name"])
        cfg.reference_latitude_deg = float(raw["latitude_deg"])
        cfg.reference_longitude_deg = float(raw["longitude_deg"])
        cfg.reference_site_source_urls = [str(x) for x in raw.get("source_urls", [])]
        cfg.reference_site_note = str(raw.get("note", ""))
    return cfg
