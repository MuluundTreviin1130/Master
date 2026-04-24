from __future__ import annotations

from pathlib import Path


_HERE = Path(__file__).resolve().parent
_DATA_ROOT = _HERE.parent
_PROFILES_ROOT = _DATA_ROOT / "profiles"


def _p(*parts: str) -> str:
    return str((_PROFILES_ROOT.joinpath(*parts)).resolve())


# Centralized repo-local profile paths.
location_loadprofiles = {
    "Vienna": _p("Vienna", "load", "loadprofiles.xlsx"),
    "VilaReal": r"Pfad\zu\VilaReal_loadprofiles.xlsx",
    "Kemi": r"Pfad\zu\Kemi_loadprofiles.xlsx",
}

location_PVprofiles = {
    "Vienna": _p("Vienna", "pv", "PV_Erzeugung.csv"),
    "VilaReal": r"Pfad\zu\VilaReal_pv.csv",
    "Kemi": r"Pfad\zu\Kemi_pv.csv",
}

location_temp_profiles = {
    "Vienna": _p("Vienna", "temperature", "Median_Temperatur_Referenzjahr_2016_2025.csv"),
    "VilaReal": r"Pfad\zu\VilaReal_temp.csv",
    "Kemi": r"Pfad\zu\Kemi_temp.csv",
}

location_wind_profiles = {
    "Vienna": _p("Vienna", "wind", "Messdaten_geosphere_Wind.csv"),
    "VilaReal": r"Pfad\zu\VilaReal_wind.csv",
    "Kemi": r"Pfad\zu\Kemi_wind.csv",
}

location_solarirradiation_profiles = {
    "Vienna": _p("Vienna", "irradiance", "Strahlungsdaten_Felixgasse22.csv"),
    "VilaReal": r"Pfad\zu\VilaReal_irradiance.csv",
    "Kemi": r"Pfad\zu\Kemi_irradiance.csv",
}

location_solargains_profiles = {
    "Vienna": _p("Vienna", "solar_gains", "Solar_gains.csv"),
}

location_openmeteo_weather_archives = {
    "Vienna": _p("Vienna", "weather", "openmeteo_hourly_archive_2016_2025.csv"),
}

# Common shared profile inputs.
location_usage_profiles = _p("common", "usage", "usage_profiles.xlsx")
location_V2H_profiles = _p("common", "v2h", "ENTSO-E_profiels.xlsx")
