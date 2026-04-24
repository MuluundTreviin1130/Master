from __future__ import annotations

from typing import Any, Dict


def can_handle(name: str) -> bool:
    return name in {
        "h2_cyclic",
        "h2_tank_to_ely_min",
        "h2_tank_to_ely_max",
        "h2_fc_to_ely_min",
        "h2_fc_to_ely_max",
    }


def evaluate_one(name: str, sense: str, rhs: float, ctx: Dict[str, Any], settings_constraints: Any) -> float:
    """Hydrogen cyclic SoC constraint.

    Convention:
      g(x) <= 0 is feasible.
      We pass the positive residual violation [kWh_H2] from system simulation:
        violation = max(0, |E_end - E_start| - tolerance)
      and enforce violation <= rhs (rhs is typically 0.0).
    """
    if name != "h2_cyclic":
        hydrogen_cfg = getattr(ctx.get("settings"), "hydrogen", None)
        if not bool(getattr(hydrogen_cfg, "coupling_enabled", True)):
            return 0.0
        ely_kw = float(ctx.get("ely_kw", 0.0))
        tank_kwh = float(ctx.get("h2_tank_kwh", 0.0))
        fc_kw = float(ctx.get("fc_kw", 0.0))
        if ely_kw <= 0.0:
            return 0.0

        tank_to_ely_min = float(getattr(hydrogen_cfg, "tank_to_ely_min_hours", 0.0))
        tank_to_ely_max = float(getattr(hydrogen_cfg, "tank_to_ely_max_hours", 0.0))
        fc_to_ely_min = float(getattr(hydrogen_cfg, "fc_to_ely_min_ratio", 0.0))
        fc_to_ely_max = float(getattr(hydrogen_cfg, "fc_to_ely_max_ratio", 0.0))

        if name == "h2_tank_to_ely_min":
            return float((tank_to_ely_min * ely_kw) - tank_kwh - float(rhs))
        if name == "h2_tank_to_ely_max":
            return float(tank_kwh - (tank_to_ely_max * ely_kw) - float(rhs))
        if name == "h2_fc_to_ely_min":
            return float((fc_to_ely_min * ely_kw) - fc_kw - float(rhs))
        if name == "h2_fc_to_ely_max":
            return float(fc_kw - (fc_to_ely_max * ely_kw) - float(rhs))
        return 0.0
    v = float(ctx.get("h2_cyclic_violation_kwh", 0.0))
    return float(v - float(rhs))
