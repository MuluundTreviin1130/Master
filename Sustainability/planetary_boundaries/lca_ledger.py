"""
Generic LCA impact aggregation for PV/BESS/Grid.

Assumes params[tech]["LCA"] structure:
  LCA = {"infra": {cat: factor}, "op": {cat: factor}, "meta": {...}}

Conventions:
  - PV infra scales with pv_kwp (kWp installed)
  - BESS infra scales with bess_kwh (kWh capacity)
  - Grid op scales with E_import_grid_L (kWh imported over lifetime)
"""
from __future__ import annotations
from typing import Dict, Any, Iterable


def _f(x: Any) -> float:
    try:
        return float(x)
    except Exception:
        return 0.0


def total_lca_impacts(
    *,
    params: Dict[str, Any],
    categories: Iterable[str],
    pv_kwp: float,
    bess_kwh: float,
    E_import_grid_L: float,
) -> Dict[str, float]:
    PV = params.get("PV", {})
    BESS = params.get("BESS", {})
    Grid = params.get("Grid", {})

    pv_lca = PV.get("LCA", None)
    bess_lca = BESS.get("LCA", None)
    grid_lca = Grid.get("LCA", None)

    out: Dict[str, float] = {c: 0.0 for c in categories}

    for c in categories:
        if isinstance(pv_lca, dict):
            out[c] += _f(pv_lca.get("infra", {}).get(c, 0.0)) * _f(pv_kwp)
        if isinstance(bess_lca, dict):
            out[c] += _f(bess_lca.get("infra", {}).get(c, 0.0)) * _f(bess_kwh)

        if isinstance(grid_lca, dict):
            out[c] += _f(grid_lca.get("op", {}).get(c, 0.0)) * _f(E_import_grid_L)

    return out
