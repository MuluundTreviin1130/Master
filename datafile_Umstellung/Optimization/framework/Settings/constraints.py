from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List

from .pb_config import PB8_CATEGORIES, make_pb_cfg


@dataclass
class Constraints:
    names: List[str] = field(default_factory=list)
    senses: List[str] = field(default_factory=list)
    rhs: List[float] = field(default_factory=list)
    cfg: Dict[str, Any] = field(default_factory=dict)


def make_constraints(engine, lifetime_years: int) -> Constraints:
    """
    Central place to define *active* constraints and their configuration.

    PB-TL constraints:
      - names: "pb_tl_<category>"
      - convention: provider returns (TL - 1), so constraint is (TL - 1) <= 0  -> RHS = 0.0

    IMPORTANT:
      - Number of households is taken from engine.N_HH (single source of truth).
    """

    # ---------------------------------------------------------------------
    # 0) Read system size from engine context (single source of truth)
    # ---------------------------------------------------------------------
    N_HH = getattr(engine, "N_HH", None)

    # ---------------------------------------------------------------------
    # 1) PB / AESA configuration (edit these to run different allocations)
    # ---------------------------------------------------------------------
    PB_METHOD = "per_capita"  # "per_capita" | "grandfathering" | "fixed"

    # Household -> population conversion (PB-specific assumption)
    PEOPLE_PER_HOUSEHOLD = 2.2
    REGION_POPULATION = float(N_HH) * float(PEOPLE_PER_HOUSEHOLD)

    # Keep consistent with your SOS source (Sala-2010-based SOS -> Sala 2010 world pop)
    WORLD_POPULATION = 6.916e9

    # Which PB categories are enforced (must match your LCIA units!)
    # Recommendation: keep land_use disabled unless your LCIA unit matches kg soil loss.
    ENABLED_PB_CATEGORIES = [
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

    # per_capita method: sector-share alpha (strictness knob)
    ALPHA_ENERGY = 0.2  # 1.0 = generous; 0.2 baseline; 0.1 strict

    # grandfathering method: direct shares of global SOS (placeholder default)
    GRANDFATHERING_SHARE = REGION_POPULATION / WORLD_POPULATION

    # fixed method: direct allocated SoSOS per year by category (fill if PB_METHOD == "fixed")
    FIXED_SOSOS_BY_CATEGORY: Dict[str, float] = {
        # "climate_change": 1.0e6,  # kg CO2-eq / year allocated to your EC
    }

    # ---------------------------------------------------------------------
    # 2) Build pb_cfg (allocation behaviour controlled by PB_METHOD)
    # ---------------------------------------------------------------------
    pb_cfg = make_pb_cfg(
        world_population=WORLD_POPULATION,
        region_population=REGION_POPULATION,
        people_per_household=PEOPLE_PER_HOUSEHOLD,
        method=PB_METHOD,
    )

    pb_cfg["enabled_categories"] = list(ENABLED_PB_CATEGORIES)

    # Method-specific knobs
    if PB_METHOD == "per_capita":
        pb_cfg["alpha_energy_by_category"] = {c: float(ALPHA_ENERGY) for c in PB8_CATEGORIES}

    elif PB_METHOD == "grandfathering":
        pb_cfg["grandfathering"]["share_by_category"] = {c: float(GRANDFATHERING_SHARE) for c in PB8_CATEGORIES}

    elif PB_METHOD == "fixed":
        pb_cfg["fixed"]["sosos_by_category"].update({k: float(v) for k, v in FIXED_SOSOS_BY_CATEGORY.items()})

    else:
        raise ValueError(f"Unknown PB_METHOD={PB_METHOD!r}. Use 'per_capita', 'grandfathering', or 'fixed'.")

    # Validate enabled categories
    for c in pb_cfg["enabled_categories"]:
        if c not in PB8_CATEGORIES:
            raise ValueError(
                f"PB category {c!r} is not in PB8_CATEGORIES={PB8_CATEGORIES}. "
                f"Either add it to PB8_CATEGORIES or remove it from ENABLED_PB_CATEGORIES."
            )

    # ---------------------------------------------------------------------
    # 3) Define active constraints (names)
    # ---------------------------------------------------------------------
    pb_names = [f"pb_tl_{c}" for c in pb_cfg.get("enabled_categories", [])]

    names = [
        *pb_names,

        # Autarky
       "autarky_min",
      #"export_share_max",

        # LCA-Max (optional)
        # "lca_max_material_resources",
    ]

    senses = ["<=" for _ in names]

    # RHS mapping: pb_tl_* uses 0.0 because provider returns (TL - 1)
    rhs_map = {
        **{f"pb_tl_{c}": 0.0 for c in PB8_CATEGORIES},

        "autarky_min": 0.5,
        "export_share_max": 0.5,
        #"lca_max_material_resources": 1.0e9,
    }
    rhs = [float(rhs_map.get(n, 0.0)) for n in names]

    return Constraints(
        names=names,
        senses=senses,
        rhs=rhs,
        cfg={
            "pb": pb_cfg,
            "lca_max": {
                # Optional: centralize thresholds here instead of rhs_map if desired.
            },
        },
    )
