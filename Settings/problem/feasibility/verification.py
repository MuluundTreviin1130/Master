from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict


@dataclass
class FeasibilityGateConfig:
    enabled: bool = True
    mode: str = "gold_recheck"  # gold_recheck | uncertainty_conservative | hybrid
    selection_scope: str = "pareto_and_uncertain"  # uncertain_only | boundary_only | pareto_and_uncertain | finalists_only | top_k_uncertain
    max_verifications: int = 10
    top_k: int = 5
    label_mode: str = "verified_three_way"  # three_way | verified_three_way
    ranking_mode: str = "lexicographic"  # lexicographic | hard_filter | penalty
    uncertainty_source: str = "quantile"  # quantile | ensemble | none
    uncertainty_quantile: float = 0.90
    conservative_rule: str = "upper_bound"  # upper_bound
    default_constraint_margin: float = 0.02
    constraint_margins: Dict[str, float] = field(default_factory=dict)


def make_feasibility_verification() -> FeasibilityGateConfig:
    return FeasibilityGateConfig()
