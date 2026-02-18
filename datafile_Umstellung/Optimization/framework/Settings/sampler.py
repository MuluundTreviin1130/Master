from __future__ import annotations
from dataclasses import dataclass, field
from typing import Dict

@dataclass
class SamplerConfig:
    name: str = "random"
    n_samples: int = 200
    seed: int = 40
    kwargs: Dict = field(default_factory=dict)


def make_sampler() -> SamplerConfig:
    """Default sampler selection."""
    # Empfehlung für bessere Surrogate-Qualität:
    # - Mehr Samples: 300-500 für gute Qualität, 500-1000 für sehr gute Qualität
    # - LHS oder Sobol sind oft besser als random (gleichmäßigere Abdeckung)
    # - LHS mit "maximin" criterion optimiert die Verteilung
    
    # Option 1: LHS mit mehr Samples (EMPFOHLEN für bessere Qualität)
    return SamplerConfig(
        name="lhs",
        n_samples=400,  # Erhöht von 200 auf 400 für bessere Qualität
        seed=30,
        kwargs={"criterion": "maximin", "trials": 10},  # Mehr Trials = bessere Verteilung
    )

    # Option 2: Sobol (sehr gleichmäßige Verteilung, aber n_samples sollte Potenz von 2 sein)
    # return SamplerConfig(name="sobol", n_samples=512, seed=30, kwargs={})
    
    # Option 3: Random (schnell, aber weniger gleichmäßig)
    # return SamplerConfig(name="random", n_samples=500, seed=30, kwargs={})
