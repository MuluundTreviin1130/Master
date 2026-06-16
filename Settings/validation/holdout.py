from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class HoldoutValidationConfig:
    """Explicit runtime override hook for validation-selected surrogate models."""

    model_id: str = ""
    artifact_path: str = ""


@dataclass
class ValidationConfig:
    """Top-level validation settings block used by `Settings.validation`."""

    holdout: HoldoutValidationConfig = field(default_factory=HoldoutValidationConfig)


def make_validation(overrides: dict[str, Any] | None = None) -> ValidationConfig:
    """Build the validation settings block before global override application."""

    cfg = ValidationConfig()
    if overrides is None:
        return cfg
    holdout_override = overrides.get("holdout")
    if holdout_override is None:
        return cfg
    if not isinstance(holdout_override, dict):
        raise TypeError("[settings.validation] holdout override must be a dict.")
    for key, value in holdout_override.items():
        if not hasattr(cfg.holdout, key):
            raise KeyError(f"[settings.validation] unknown holdout override key: {key}")
        setattr(cfg.holdout, key, str(value))
    return cfg
