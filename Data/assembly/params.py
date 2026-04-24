# Data/params.py — canonical parameter assembly (single-source-of-truth via settings stays upstream)
from __future__ import annotations

from typing import Dict, Any

from .tech_params import technologies_global
from .location_params import technologies_local

DEFAULT_LIFETIME_YEARS = 25  # identical to legacy Data/data.py


def get_parameters(location: str, lifetime_years: int = DEFAULT_LIFETIME_YEARS) -> Dict[str, Any]:
    """Return merged parameter dict (global tech + local economics + lifetime)."""
    params: Dict[str, Any] = {}
    params.update(technologies_global)
    params["lifetime"] = int(lifetime_years)
    params.update(technologies_local[location])
    country_code = params.get("country_code")
    if not country_code:
        raise ValueError(
            f"[params] Missing country_code for location='{location}' in Data/economic_data/location/."
        )

    # --- LCA injection from JSON DB (Data/LCA_data/static/<country>/*.json) ---
    from Data.LCA_data.lca_facade import apply_lca_to_params, LcaDbConfig
    cfg = LcaDbConfig(mode="static", country=str(country_code), debug_print=False)
    apply_lca_to_params(params, cfg)

    # ---------------------------------------------------------------

    return params
