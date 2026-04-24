from __future__ import annotations

# Facade module: keeps legacy API stable.
# - get_parameters(location) -> dict with identical legacy keys
# - load_profiles(location)  -> dict with identical legacy keys
# - exposes location_* path dicts and technologies_* dicts for backward compatibility

from .params import get_parameters
from Data.profiles import load_profiles

# Backward-compatible exports (some code may import these directly)
from Data.profiles import (
    location_loadprofiles,
    location_PVprofiles,
    location_temp_profiles,
    location_wind_profiles,
    location_solarirradiation_profiles,
    location_solargains_profiles,
    location_usage_profiles,
    location_V2H_profiles,
)

from .tech_params import technologies_global
from .location_params import technologies_local
