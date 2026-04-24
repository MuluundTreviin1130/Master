from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict

REQUIRED_DISPATCH_OBJECTIVE_TERMS = (
    "grid_import_cost",
    "grid_export_revenue",
    "fuel_cost",
    "co2_cost",
    "variable_opex",
    "unserved_penalty",
    "spill_penalty",
    "thermflex_activation_penalty",
    "temperature_violation_penalty",
)


@dataclass
class DispatchCostBreakdown:
    dispatch_cost_eur: float
    dispatch_objective_eur: float
    dispatch_operating_cost_eur: float
    dispatch_penalty_total_eur: float
    mc_auction_import_cost_proxy_eur: float
    fuel_cost_eur: float
    co2_cost_eur: float
    variable_opex_eur: float
    unserved_penalty_eur: float
    spill_penalty_eur: float
    thermflex_activation_penalty_eur: float
    temperature_violation_penalty_eur: float
    grid_export_revenue_eur: float


def build_dispatch_cost_breakdown(
    objective_terms: Dict[str, Any] | None,
    *,
    strict: bool = False,
) -> DispatchCostBreakdown:
    if objective_terms is None:
        if strict:
            raise ValueError("[dispatch_cost] objective_terms fehlen trotz strict=True.")
        terms = {}
    else:
        terms = {str(k): float(v) for k, v in dict(objective_terms).items()}
    if strict:
        missing = [k for k in REQUIRED_DISPATCH_OBJECTIVE_TERMS if k not in terms]
        if missing:
            raise KeyError(
                "[dispatch_cost] objective_terms unvollstaendig. Fehlend: "
                + ", ".join(missing)
            )
    mc_import = float(terms.get("grid_import_cost", 0.0))
    export_revenue = float(terms.get("grid_export_revenue", 0.0))
    fuel = float(terms.get("fuel_cost", 0.0))
    co2 = float(terms.get("co2_cost", 0.0))
    variable_opex = float(terms.get("variable_opex", 0.0))
    unserved = float(terms.get("unserved_penalty", 0.0))
    spill = float(terms.get("spill_penalty", 0.0))
    thermflex_activation = float(terms.get("thermflex_activation_penalty", 0.0))
    temp_violation = float(terms.get("temperature_violation_penalty", 0.0))
    operating_cost = float(mc_import - export_revenue + fuel + co2 + variable_opex)
    penalty_total = float(unserved + spill + thermflex_activation + temp_violation)
    dispatch_objective = float(operating_cost + penalty_total)
    return DispatchCostBreakdown(
        dispatch_cost_eur=dispatch_objective,
        dispatch_objective_eur=dispatch_objective,
        dispatch_operating_cost_eur=operating_cost,
        dispatch_penalty_total_eur=penalty_total,
        mc_auction_import_cost_proxy_eur=mc_import,
        fuel_cost_eur=fuel,
        co2_cost_eur=co2,
        variable_opex_eur=variable_opex,
        unserved_penalty_eur=unserved,
        spill_penalty_eur=spill,
        thermflex_activation_penalty_eur=thermflex_activation,
        temperature_violation_penalty_eur=temp_violation,
        grid_export_revenue_eur=export_revenue,
    )
