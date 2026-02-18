from __future__ import annotations
from dataclasses import dataclass, field
from typing import Dict

@dataclass
class OptimizerConfig:
    name: str = "R-NSGA2"
    kwargs: Dict = field(default_factory=dict)
    seed: int = 5
    n_jobs: int = 1


def make_optimizer() -> OptimizerConfig:
    """Default optimizer selection."""
    return OptimizerConfig(
        name="nsga2",
        kwargs={"pop_size":200,"n_gen": 200},
        seed=3,
        n_jobs=4,
    )

    # Alternatives (copy/paste)
    # return OptimizerConfig(name="nsga2",  kwargs={"pop_size":100, "n_gen":200}, seed=5, n_jobs=1)
    # return OptimizerConfig(name="moead",  kwargs={"pop_size":200, "n_gen":200}, seed=5, n_jobs=1)
    # return OptimizerConfig(name="agemoea", kwargs={"pop_size":200, "n_gen":200}, seed=5, n_jobs=1)
    # return OptimizerConfig(name="smsemoa", kwargs={"pop_size":100, "n_gen":200}, seed=5, n_jobs=1)
