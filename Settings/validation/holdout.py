from __future__ import annotations

from dataclasses import dataclass


@dataclass
class ValidationConfig:
    """Validation settings attached to the top-level Settings SSOT."""

    holdout_fraction: float = 0.2
    random_state: int = 42
    min_holdout_samples: int = 1
    fail_on_empty_holdout: bool = True


def make_validation() -> ValidationConfig:
    return ValidationConfig()
