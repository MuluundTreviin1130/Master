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

    # --- LCA injection from JSON DB (minimal, central, non-breaking) ---
    try:
        from Sustainability.planetary_boundaries.lca_facade import apply_lca_to_params, LcaDbConfig
        cfg = LcaDbConfig(mode="static", country="AT", debug_print=False)
        apply_lca_to_params(params, cfg)

    except Exception as e:
        print("[LCA-INJECT] FAILED:", repr(e))

    # ---------------------------------------------------------------

    return params
