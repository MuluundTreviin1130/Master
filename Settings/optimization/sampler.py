from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict


@dataclass
class SamplerConfig:
    name: str = "random"
    n_samples: int = 1
    seed: int = 1
    kwargs: Dict = field(default_factory=dict)


def make_sampler() -> SamplerConfig:
    """Default sampler selection for moderate native runs."""
    return SamplerConfig(
        name="lhs",
        n_samples=16,
        seed=5,
        kwargs={"criterion": "maximin", "trials": 4},
    )
