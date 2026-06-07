from __future__ import annotations

from dataclasses import dataclass, field
from typing import List


@dataclass
class ValidationConfig:
    # Generic holdout validation can be disabled explicitly by settings overrides,
    # but the config must exist so every Settings object has one typed contract.
    enabled: bool = True
    # Keep the split contract aligned with surrogate_train unless callers override
    # one of the two sections for a specific experiment.
    holdout_frac: float = 0.2
    random_seed: int = 42
    min_samples: int = 5
    metrics: List[str] = field(default_factory=lambda: ["r2", "rmse", "mae", "rel_mae_percent"])
    output_root: str = "Optimization/run/validation"


def make_validation() -> ValidationConfig:
    return ValidationConfig()
