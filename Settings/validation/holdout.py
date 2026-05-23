from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class HoldoutValidationConfig:
    """Explicit validation-only model override settings.

    Normal production model resolution should use the Learning registry.  These
    fields stay empty unless a validation run intentionally pins a model or
    artifact, which keeps the override visible in Settings instead of hidden in
    runtime code.
    """

    model_id: str = ""
    artifact_path: str = ""


@dataclass
class ValidationConfig:
    """Top-level Settings namespace for validation-specific configuration."""

    holdout: HoldoutValidationConfig = field(default_factory=HoldoutValidationConfig)


def make_validation() -> ValidationConfig:
    """Build validation settings from the Settings SSOT defaults."""

    return ValidationConfig()
