from __future__ import annotations

from dataclasses import dataclass


@dataclass
class ValidationConfig:
    """Explicit model-holdout override channel used by runtime model resolution."""

    model_id: str = ""
    artifact_path: str = ""


ValidationHoldoutConfig = ValidationConfig


def make_validation() -> ValidationConfig:
    return ValidationConfig()
