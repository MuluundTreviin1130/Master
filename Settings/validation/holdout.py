from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class ValidationHoldoutConfig:
    """Settings SSOT for explicit validation-holdout model selection."""

    model_id: str = ""


@dataclass
class ValidationConfig:
    """Top-level validation settings group."""

    holdout: ValidationHoldoutConfig = field(default_factory=ValidationHoldoutConfig)


def make_validation() -> ValidationConfig:
    return ValidationConfig()
