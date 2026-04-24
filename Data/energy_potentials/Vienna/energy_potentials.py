from __future__ import annotations

from pathlib import Path


SOURCE_FILE_PATH = Path(
    r"C:\Users\Philipp Thunshirn\Desktop\PhD\Daten\Citiwatt_indicators_Vienna.txt"
)


def build_energy_potentials_values() -> dict[str, float | str | None]:
    """Manually curated Vienna energy-potential snapshot.

    The active values are kept in the Data layer so location-specific truths do
    not live inside the Settings layer.
    """

    district_solar_thermal_rooftop_avg_mwh_per_ha_per_year = 412.32
    district_solar_thermal_open_field_avg_mwh_per_ha_per_year = 1179.31
    district_solar_thermal_rooftop_area_ha = 25507.0
    district_solar_thermal_open_field_area_ha = 5393.0
    district_solar_thermal_rooftop_gwh_per_year_max = (
        district_solar_thermal_rooftop_avg_mwh_per_ha_per_year * district_solar_thermal_rooftop_area_ha / 1000.0
    )
    district_solar_thermal_open_field_gwh_per_year_max = (
        district_solar_thermal_open_field_avg_mwh_per_ha_per_year * district_solar_thermal_open_field_area_ha / 1000.0
    )

    return {
        "source": "manual_citiwatt_snapshot",
        "location": "Vienna",
        "source_file_path": str(SOURCE_FILE_PATH),
        "enforce_hard_caps": True,
        "large_wind_kw_max": 0.0,
        "district_wastewater_heat_kw_th_max": 257777.78,
        "district_waste_incineration_gwh_per_year_max": 811.11,
        "district_biogas_feedstock_gwh_per_year_max": 19.44,
        "district_biomass_feedstock_gwh_per_year_max": 977.08,
        "district_solar_thermal_rooftop_avg_mwh_per_ha_per_year": district_solar_thermal_rooftop_avg_mwh_per_ha_per_year,
        "district_solar_thermal_open_field_avg_mwh_per_ha_per_year": district_solar_thermal_open_field_avg_mwh_per_ha_per_year,
        "district_solar_thermal_rooftop_area_ha": district_solar_thermal_rooftop_area_ha,
        "district_solar_thermal_open_field_area_ha": district_solar_thermal_open_field_area_ha,
        "district_solar_thermal_rooftop_gwh_per_year_max": district_solar_thermal_rooftop_gwh_per_year_max,
        "district_solar_thermal_open_field_gwh_per_year_max": district_solar_thermal_open_field_gwh_per_year_max,
        "district_solar_thermal_total_gwh_per_year_max": (
            district_solar_thermal_rooftop_gwh_per_year_max + district_solar_thermal_open_field_gwh_per_year_max
        ),
    }

