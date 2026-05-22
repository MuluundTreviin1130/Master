from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class HoldoutValidationConfig:
    """Manual model override for explicit validation-only runs.

    The normal resolver path must not silently pin a model. A non-empty
    ``model_id`` or ``artifact_path`` therefore represents an intentional
    validation override supplied through settings.
    """

    model_id: str = ""
    artifact_path: str = ""


@dataclass
class ValidationConfig:
    """Top-level validation settings namespace."""

    holdout: HoldoutValidationConfig = field(default_factory=HoldoutValidationConfig)


def make_validation() -> ValidationConfig:
    return ValidationConfig()
