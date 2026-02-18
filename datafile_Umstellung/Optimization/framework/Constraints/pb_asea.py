# Optimization/framework/Constraints/pb_aesa.py
from __future__ import annotations

from typing import Any, Dict, Iterable, List, Tuple

from Sustainability.planetary_boundaries.sosos import get_sosos_per_year


def can_handle(name: str) -> bool:
    return name.startswith("pb_tl_") or name.startswith("lca_max_")


def _f(x: Any) -> float:
    try:
        return float(x)
    except Exception:
        return 0.0


def _total_lca_impacts(
    *,
    params: Dict[str, Any],
    categories: Iterable[str],
    pv_kwp: float,
    bess_kwh: float,
    E_import_grid_L: float,
) -> Dict[str, float]:
    """
    Uses params[tech]["LCA"] dicts with structure:
      LCA = {"infra": {cat: factor}, "op": {cat: factor}, "meta": {...}}

    Conventions:
      - PV infra scales with pv_kwp
      - BESS infra scales with bess_kwh
      - Grid op scales with E_import_grid_L
    """
    PV = params.get("PV", {})
    BESS = params.get("BESS", {})
    Grid = params.get("Grid", {})

    pv_lca = PV.get("LCA", {})
    bess_lca = BESS.get("LCA", {})
    grid_lca = Grid.get("LCA", {})

    out = {c: 0.0 for c in categories}

    for c in out.keys():
        out[c] += _f(pv_lca.get("infra", {}).get(c, 0.0)) * _f(pv_kwp)
        out[c] += _f(bess_lca.get("infra", {}).get(c, 0.0)) * _f(bess_kwh)
        out[c] += _f(grid_lca.get("op", {}).get(c, 0.0)) * _f(E_import_grid_L)

    return out


def evaluate_one(name: str, sense: str, rhs: float, ctx: Dict[str, Any], settings_constraints: Any) -> float:
    params = ctx.get("params", {})
    pv_kwp = float(ctx.get("pv_kwp", 0.0))
    bess_kwh = float(ctx.get("bess_kwh", 0.0))
    E_import_grid_L = float(ctx.get("E_import_grid_L", 0.0))

    cfg = dict(getattr(settings_constraints, "cfg", {}) or {})
    pb_cfg = dict(cfg.get("pb", {}) or {})
    lca_max_cfg = dict(cfg.get("lca_max", {}) or {})

    # lifetime must come from params (single source of truth)
    L_years = float(params.get("lifetime", 0.0))

    # Determine category
    if name.startswith("pb_tl_"):
        cat = name.replace("pb_tl_", "", 1)
        impacts = _total_lca_impacts(
            params=params,
            categories=[cat],
            pv_kwp=pv_kwp,
            bess_kwh=bess_kwh,
            E_import_grid_L=E_import_grid_L,
        )
        impact = float(impacts.get(cat, 0.0))

        sosos_per_year = float(get_sosos_per_year(pb_cfg, cat))
        denom = sosos_per_year * L_years if sosos_per_year > 0 and L_years > 0 else 0.0
        tl = (impact / denom) if denom > 0 else 0.0

        # TL <= 1  => g = tl - 1 <= 0
        return float(tl - 1.0)

    if name.startswith("lca_max_"):
        cat = name.replace("lca_max_", "", 1)
        maxv = float(lca_max_cfg.get(cat, rhs))
        impacts = _total_lca_impacts(
            params=params,
            categories=[cat],
            pv_kwp=pv_kwp,
            bess_kwh=bess_kwh,
            E_import_grid_L=E_import_grid_L,
        )
        impact = float(impacts.get(cat, 0.0))
        # impact <= maxv  => g = impact - maxv <= 0
        return float(impact - maxv)

    return 0.0
