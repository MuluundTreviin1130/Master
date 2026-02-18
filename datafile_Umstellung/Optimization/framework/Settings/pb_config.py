"""
Settings-only PB (AESA) configuration.

Engines only consume settings.constraints.cfg['pb'] and compute TL constraints.
Edit values here; no other code changes required.
"""
from __future__ import annotations
from typing import Dict, Any

# EF 3.0 / Balanza-like categories (incl. resources if you want it as PB constraint)
PB8_CATEGORIES = [
    #"climate_change",
    #"freshwater_eutrophication",
    #"water_use",
    #"land_use",
    #"ozone_depletion",
    #"acidification",
    #"particulate_matter",
    #"freshwater_ecotoxicity",
    #"material_resources",
]


def make_pb_cfg(
    *,
    world_population: float,
    region_population: float,
    people_per_household: float,
    method: str = "per_capita",
) -> Dict[str, Any]:


    return {
        "method": method,
        "world_population": float(world_population),
        "region_population": float(region_population),
        "people_per_household": float(people_per_household),
        "scale_with_lifetime": True,

        # per-capita needs an energy-sector alpha per category (Balanza alpha_energy,p concept)
        "alpha_energy_by_category": {c: 0.0 for c in PB8_CATEGORIES},

        # grandfathering uses shares per category (SoSOS-share of global SOS)
        "grandfathering": {"share_by_category": {c: 0.0 for c in PB8_CATEGORIES}},

        # fixed = you directly set SoSOS per year (already allocated)
        "fixed": {"sosos_by_category": {c: 0.0 for c in PB8_CATEGORIES}},

        # Which PB categories are enforced as TL constraints (subset)
        "enabled_categories": [
            #"climate_change",
           # "water_use",
    

        ],
    }
