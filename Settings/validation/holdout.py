from __future__ import annotations

from dataclasses import dataclass


@dataclass
class ValidationConfig:
    """Top-level validation settings used by the Settings dataclass."""

    enabled: bool = True
    holdout_frac: float = 0.2
    random_seed: int = 42
    artifact_root: str = "Optimization/run/validation"


def make_validation() -> ValidationConfig:
    return ValidationConfig()
