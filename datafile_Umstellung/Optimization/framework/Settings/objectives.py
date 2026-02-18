from __future__ import annotations
from dataclasses import dataclass
from typing import List

@dataclass
class Objectives:
    names: List[str]
    minimize: List[bool]  # True=minimize, False=maximize

def make_objectives() -> Objectives:
    # Zentral: hier definierst du ALLE Ziele, inkl. LCA Kategorien
    names = [
        # economic
        "npc_eur",
        # -----------------
        # -----------------
        # Technical
        #grid_import_kwh",
       #"grid_export_kwh",
        "grid_interaction_kwh",
        # -----------------
        # -----------------
        # LCA indicators
        #"climate_change",
        #"water_use",
        #"acidification",
        #"freshwater_eutrophication",
        #"particulate_matter",
        #"freshwater_ecotoxicity",
        #"ozone_depletion",
        # "material_resources",
        #"land_use",
    ]

    # Standard: alles minimieren (außer du hast z.B. autarky als Ziel, dann False)
    minimize = [True for _ in names]

    return Objectives(names=names, minimize=minimize)
