from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict

from .dispatch import DispatchConstraintConfig
from .hydrogen import HydrogenConstraintConfig
from .policy import PolicyConstraintConfig
from .problem import ProblemConstraintConfig, make_problem_constraints
from .storage import StorageConstraintConfig
from .thermflex import ThermflexConstraintConfig


@dataclass
class Constraints:
    names: list[str] = field(default_factory=list)
    senses: list[str] = field(default_factory=list)
    rhs: list[float] = field(default_factory=list)
    cfg: Dict[str, Any] = field(default_factory=dict)
    problem: ProblemConstraintConfig = field(default_factory=ProblemConstraintConfig)
    storage: StorageConstraintConfig = field(default_factory=StorageConstraintConfig)
    hydrogen: HydrogenConstraintConfig = field(default_factory=HydrogenConstraintConfig)
    policy: PolicyConstraintConfig = field(default_factory=lambda: PolicyConstraintConfig(enabled_categories=[], cfg={}))
    dispatch: DispatchConstraintConfig = field(default_factory=DispatchConstraintConfig)
    thermflex: ThermflexConstraintConfig = field(default_factory=ThermflexConstraintConfig)


def make_constraints(engine, lifetime_years: int) -> Constraints:
    problem = make_problem_constraints(engine, lifetime_years=lifetime_years)
    policy_cfg = dict(problem.cfg.get("pb", {}) or {})
    return Constraints(
        names=list(problem.names),
        senses=list(problem.senses),
        rhs=[float(x) for x in problem.rhs],
        cfg=dict(problem.cfg),
        problem=problem,
        storage=StorageConstraintConfig(),
        hydrogen=HydrogenConstraintConfig(),
        policy=PolicyConstraintConfig(
            enabled_categories=list(policy_cfg.get("enabled_categories", []) or []),
            cfg=policy_cfg,
        ),
        dispatch=DispatchConstraintConfig(),
        thermflex=ThermflexConstraintConfig(),
    )
