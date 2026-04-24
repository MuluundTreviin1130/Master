from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict


@dataclass
class OptimizerConfig:
    name: str = "R-NSGA2"
    kwargs: Dict = field(default_factory=dict)
    seed: int = 1
    n_jobs: int = 1


def make_optimizer() -> OptimizerConfig:
    """Default optimizer selection for conservative native runs."""
    return OptimizerConfig(
        name="nsga2",
        kwargs={"pop_size": 30, "n_gen": 30},
        seed=1,
        n_jobs=1,
    )
