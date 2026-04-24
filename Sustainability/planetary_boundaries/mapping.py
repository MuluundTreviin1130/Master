from dataclasses import dataclass

@dataclass(frozen=True)
class PbMapping:
    category: str
    pb_constraint_name: str
    pb_ready: bool  # methodisch robust?

def get_pb_mapping() -> dict[str, PbMapping]:
    return {
        "climate_change": PbMapping("climate_change", "pb_climate_change", True),
        "water_use": PbMapping("water_use", "pb_water_use", True),
        "ozone_depletion": PbMapping("ozone_depletion", "pb_ozone_depletion", True),

        "land_use": PbMapping("land_use", "pb_land_use", True),
        "freshwater_eutrophication": PbMapping("freshwater_eutrophication", "pb_eutrophication", True),
        "acidification": PbMapping("acidification", "pb_acidification", True),
        "particulate_matter": PbMapping("particulate_matter", "pb_particulate_matter", True),
        "freshwater_ecotoxicity": PbMapping("freshwater_ecotoxicity", "pb_ecotoxicity", True),
        "material_resources": PbMapping("material_resources", "pb_resources", True),
    }
