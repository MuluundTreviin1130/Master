from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List


@dataclass
class FeasibilityDecision:
    status: str
    per_constraint: Dict[str, str] = field(default_factory=dict)
    source: str = ""


@dataclass
class FeasibilityVerificationSummary:
    enabled: bool
    applied: bool
    scope: str
    mode: str = ""
    label_mode: str = ""
    ranking_mode: str = ""
    selected_indices: List[int] = field(default_factory=list)
    verified_indices: List[int] = field(default_factory=list)
    uncertain_indices: List[int] = field(default_factory=list)
    feasible_indices: List[int] = field(default_factory=list)
    infeasible_indices: List[int] = field(default_factory=list)
    verified_feasible_indices: List[int] = field(default_factory=list)
    verified_infeasible_indices: List[int] = field(default_factory=list)
    labels: List[str] = field(default_factory=list)
    reason: str = ""
