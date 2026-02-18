from __future__ import annotations

"""
Global SOS (Safe Operating Space / carrying capacity) per category and per year.

These values must be in the SAME UNITS as your LCA factors in the tech JSONs
(e.g., EF v3.0 "no LT" midpoint indicators).

Source: Sala et al. (2020) main text, Table 3 (LCIA-based PBs / carrying capacities).
Note: land_use in Sala Table 3 is expressed as kg soil loss (soil erosion).
If your 'land_use' LCA indicator is in Pt (EF land use), do NOT enable the PB constraint
for land_use until you have unit-consistent land-use impacts.
"""

def get_global_sos_by_category() -> dict[str, float]:
    return {
        # EF midpoint: kg CO2-eq / year
        "climate_change": 6.81e12,

        # EF midpoint: kg CFC-11-eq / year
        "ozone_depletion": 5.39e8,

        # EF midpoint: kg P-eq / year
        "freshwater_eutrophication": 5.81e9,

        # EF midpoint: molc H+-eq / year
        "acidification": 1.00e12,

        # EF midpoint: disease incidence / year
        "particulate_matter": 5.16e5,

        # EF midpoint: m3 world eq (deprivation-weighted water use) / year
        "water_use": 1.82e14,

        # EF midpoint: CTUe / year
        "freshwater_ecotoxicity": 1.31e14,

        # EF midpoint: kg Sb-eq / year
        "material_resources": 2.19e8,

        # WARNING: Sala Table 3 uses kg soil loss (soil erosion) / year.
        # If your LCA 'land_use' is in Pt (EF land use), keep PB constraint disabled for land_use.
        "land_use": 1.27e13,
    }
