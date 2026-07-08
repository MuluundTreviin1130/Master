from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class HoldoutValidationConfig:
    """Explicit model override used by validation and debugging runs.

    Empty strings mean "no forced model" and let the Learning registry resolver
    choose the active eligible model.  Keeping these values under Settings makes
    validation overrides visible in the same SSOT path as all other run-time
    configuration instead of hiding them in the resolver.
    """

    model_id: str = ""
    artifact_path: str = ""


@dataclass
class ValidationConfig:
    """Top-level validation configuration namespace."""

    holdout: HoldoutValidationConfig = field(default_factory=HoldoutValidationConfig)


def make_validation() -> ValidationConfig:
    """Build the default validation config for `Settings.get_settings`."""

    return ValidationConfig()
