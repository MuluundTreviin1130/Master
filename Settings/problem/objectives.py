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
        # optional dispatch alternatives:
        # "dispatch_cost_eur",
        # "fuel_cost_eur",
        # "co2_cost_eur",
        # LCA indicators (direct LCIA category keys from your LCA data)
        "climate_change",
        # Optional alternatives:
        # "grid_interaction_kwh",
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
