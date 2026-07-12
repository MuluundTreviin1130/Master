from __future__ import annotations

"""Validation settings used by Learning runtime overrides.

The Learning runtime already resolves optional holdout overrides from
``settings.validation.holdout``.  This module makes that configuration explicit
in Settings instead of letting those imports fail or relying on ad hoc
attributes.
"""

from dataclasses import dataclass, field


@dataclass
class HoldoutValidationConfig:
    """Explicit model override used for validation-only Learning runs."""

    model_id: str = ""
    artifact_path: str = ""


@dataclass
class ValidationConfig:
    """Top-level validation configuration namespace."""

    holdout: HoldoutValidationConfig = field(default_factory=HoldoutValidationConfig)


def make_validation() -> ValidationConfig:
    """Return the default validation Settings subtree."""

    return ValidationConfig()
