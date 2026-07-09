from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class HoldoutValidationConfig:
    """Explicit model override hooks for validation and replay runs."""

    model_id: str = ""
    artifact_path: str = ""


@dataclass
class ValidationConfig:
    """Top-level validation settings namespace."""

    holdout: HoldoutValidationConfig = field(default_factory=HoldoutValidationConfig)


def make_validation() -> ValidationConfig:
    return ValidationConfig()

