from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class HoldoutValidationConfig:
    """Explicit override hook for validation-only surrogate model selection."""

    model_id: str = ""
    artifact_path: str = ""


@dataclass
class ValidationConfig:
    """Top-level validation settings block.

    Runtime model resolution reads this block to force a particular native
    model during gold/holdout rechecks. Empty strings mean no forced model.
    """

    holdout: HoldoutValidationConfig = field(default_factory=HoldoutValidationConfig)


def make_validation() -> ValidationConfig:
    return ValidationConfig()
