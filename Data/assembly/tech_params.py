from __future__ import annotations

# Backward-compatible: keep technologies_global with EXACT keys from legacy Data/data.py.
#
# This module now lives under Data/assembly/, while the canonical technology
# dictionaries remain under Data/technology_data/. The import must therefore be
# absolute-from-parent, not relative-to-assembly, otherwise the moved module
# resolves to the non-existent package Data.assembly.technology_data.
from Data.technology_data import (
    PV,
    BESS,
    BIOGAS_ENGINE,
    BIOMASS_CHP,
    Grid,
    FC,
    ELY,
    GEOTHERMAL,
    heatpump,
    LARGE_WIND,
    SOLAR_THERMAL,
    building,
    EV,
    SMALL_WIND,
    WASTE_INCINERATION,
    WOOD_GASIFIER,
)

technologies_global = {
    'PV': dict(PV),
    'BESS': dict(BESS),
    'Grid': dict(Grid),
    'FC': dict(FC),
    'ELY': dict(ELY),
    'SMALL_WIND': dict(SMALL_WIND),
    'LARGE_WIND': dict(LARGE_WIND),
    'BIOGAS_ENGINE': dict(BIOGAS_ENGINE),
    'BIOMASS_CHP': dict(BIOMASS_CHP),
    'SOLAR_THERMAL': dict(SOLAR_THERMAL),
    'GEOTHERMAL': dict(GEOTHERMAL),
    'WASTE_INCINERATION': dict(WASTE_INCINERATION),
    'WOOD_GASIFIER': dict(WOOD_GASIFIER),
    'heatpump': dict(heatpump),
    'building': dict(building),
    'EV': dict(EV),
}
