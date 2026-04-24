from __future__ import annotations

from typing import Any, Dict


def can_handle(name: str) -> bool:
    return name == "bess_cyclic"


def evaluate_one(name: str, sense: str, rhs: float, ctx: Dict[str, Any], settings_constraints: Any) -> float:
    if name != "bess_cyclic":
        return 0.0
    v = float(ctx.get("bess_cyclic_violation_kwh", 0.0))
    return float(v - float(rhs))
