from __future__ import annotations
from typing import Any, Dict

def can_handle(name: str) -> bool:
    return name == "export_share_max"

def evaluate_one(name: str, sense: str, rhs: float, ctx: Dict[str, Any], settings_constraints: Any) -> float:
    # Convention: g(x) <= 0 is satisfied
    E_exp = float(ctx.get("E_export_grid_L", 0.0))
    E_pv  = float(ctx.get("PV_generation_L", 0.0))
    export_share = (E_exp / E_pv) if E_pv > 1e-9 else 0.0

    s = (sense or "<=").strip()
    if s == ">=":
        return float(rhs - export_share)   # rhs - share <= 0  <=> share >= rhs
    return float(export_share - rhs)       # share - rhs <= 0  <=> share <= rhs
