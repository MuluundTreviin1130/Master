from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class HoldoutValidationConfig:
    """
    Explicit holdout validation selector for surrogate artifacts.

    `model_id` is intentionally empty by default: callers that need to force a
    specific candidate model must do so through a settings override, while the
    normal registry path can continue to resolve the active model explicitly.
    """

    model_id: str = ""
    split: str = "holdout"
    seed: int = 42


@dataclass
class ValidationConfig:
    """Top-level validation settings namespace used by `Settings.Settings`."""

    holdout: HoldoutValidationConfig = field(default_factory=HoldoutValidationConfig)


def make_validation() -> ValidationConfig:
    """Build the validation settings namespace from versioned Settings defaults."""

    return ValidationConfig()
