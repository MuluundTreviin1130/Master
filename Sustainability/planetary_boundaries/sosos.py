from .sos_global import get_global_sos_by_category
from .allocation import allocate_share

def get_sosos_per_year(cfg: dict, category: str) -> float:
    if cfg["method"] == "fixed":
        return float(cfg["fixed"]["sosos_by_category"][category])

    sos_global = get_global_sos_by_category()[category]
    share = allocate_share(cfg, category)
    return float(sos_global) * float(share)
