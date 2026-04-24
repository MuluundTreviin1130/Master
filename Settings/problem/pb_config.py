"""
Settings-only PB (AESA) configuration.

Engines only consume settings.constraints.cfg['pb'] and compute TL constraints.
Edit values here; no other code changes required.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List

# EF 3.0 / Balanza-like categories (incl. resources if you want it as PB constraint)
PB8_CATEGORIES = [
    # "climate_change",
    # "freshwater_eutrophication",
    # "water_use",
    # "land_use",
    # "ozone_depletion",
    # "acidification",
    # "particulate_matter",
    # "freshwater_ecotoxicity",
    # "material_resources",
]

# PB allocation defaults (single source of truth).
PB_METHOD_DEFAULT = "per_capita"  # "per_capita" | "grandfathering" | "fixed"
PB_PEOPLE_PER_HOUSEHOLD_DEFAULT = 2.2
PB_WORLD_POPULATION_DEFAULT = 6.916e9
PB_ALPHA_ENERGY_DEFAULT = 0.2
PB_ENABLED_CATEGORIES_DEFAULT: List[str] = []
PB_FIXED_SOSOS_BY_CATEGORY_DEFAULT: Dict[str, float] = {}


@dataclass
class PbSettings:
    method: str = PB_METHOD_DEFAULT
    people_per_household: float = PB_PEOPLE_PER_HOUSEHOLD_DEFAULT
    world_population: float = PB_WORLD_POPULATION_DEFAULT
    alpha_energy: float = PB_ALPHA_ENERGY_DEFAULT
    enabled_categories: List[str] = field(default_factory=lambda: list(PB_ENABLED_CATEGORIES_DEFAULT))
    fixed_sosos_by_category: Dict[str, float] = field(default_factory=lambda: dict(PB_FIXED_SOSOS_BY_CATEGORY_DEFAULT))


def make_pb_settings() -> PbSettings:
    return PbSettings()


def make_pb_cfg(
    *,
    world_population: float,
    region_population: float,
    people_per_household: float,
    method: str = "per_capita",
) -> Dict[str, Any]:
    return {
        "method": str(method),
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
        "enabled_categories": [],
    }


def make_pb_cfg_for_engine(engine: Any) -> Dict[str, Any]:
    """Build a validated PB config using engine/system-size context."""
    pb_settings = make_pb_settings()

    n_hh = float(getattr(engine, "N_HH", 0))
    region_population = n_hh * float(pb_settings.people_per_household)
    world_population = float(pb_settings.world_population)
    grandfathering_share = (region_population / world_population) if world_population > 0 else 0.0

    pb_cfg = make_pb_cfg(
        world_population=world_population,
        region_population=region_population,
        people_per_household=float(pb_settings.people_per_household),
        method=str(pb_settings.method),
    )
    pb_cfg["enabled_categories"] = list(pb_settings.enabled_categories)

    method = str(pb_settings.method)
    if method == "per_capita":
        pb_cfg["alpha_energy_by_category"] = {c: float(pb_settings.alpha_energy) for c in PB8_CATEGORIES}
    elif method == "grandfathering":
        pb_cfg["grandfathering"]["share_by_category"] = {c: float(grandfathering_share) for c in PB8_CATEGORIES}
    elif method == "fixed":
        pb_cfg["fixed"]["sosos_by_category"].update({str(k): float(v) for k, v in pb_settings.fixed_sosos_by_category.items()})
    else:
        raise ValueError(f"Unknown PB method={method!r}. Use 'per_capita', 'grandfathering', or 'fixed'.")

    for category in pb_cfg["enabled_categories"]:
        if category not in PB8_CATEGORIES:
            raise ValueError(
                f"PB category {category!r} is not in PB8_CATEGORIES={PB8_CATEGORIES}. "
                "Either add it to PB8_CATEGORIES or remove it from pb_settings.enabled_categories."
            )

    return pb_cfg
