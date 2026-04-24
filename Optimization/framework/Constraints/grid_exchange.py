from __future__ import annotations

from typing import Any, Dict


def can_handle(name: str) -> bool:
    return name == "grid_exchange_share_max"


def evaluate_one(name: str, sense: str, rhs: float, ctx: Dict[str, Any], settings_constraints: Any) -> float:
    """
    Constraint: grid exchange share <= rhs
      exchange_share = (E_import_grid_L + E_export_grid_L) / E_load_L
      g = exchange_share - rhs  <= 0
    """
    if name != "grid_exchange_share_max":
        return 0.0

    E_import_grid_L = max(0.0, float(ctx.get("E_import_grid_L", 0.0)))
    E_export_grid_L = max(0.0, float(ctx.get("E_export_grid_L", 0.0)))
    E_load_L = float(ctx.get("E_load_L", 0.0))

    if E_load_L > 1e-9:
        exchange_share = (E_import_grid_L + E_export_grid_L) / E_load_L
    else:
        # Zero-load case: no meaningful exchange share; treat as no violation.
        exchange_share = 0.0

    return float(exchange_share - float(rhs))
