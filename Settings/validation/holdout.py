from __future__ import annotations

from dataclasses import dataclass


@dataclass
class ValidationConfig:
    """Shared validation defaults used by settings-driven holdout workflows."""

    holdout_fraction: float = 0.2
    random_state: int = 42
    min_samples: int = 10
    group_column: str = "split_group_run"


def make_validation() -> ValidationConfig:
    return ValidationConfig()
