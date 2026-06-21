from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class ValidationHoldoutConfig:
    """Explicit model override used by validation and audit runs.

    Empty strings mean that no validation override is active. Runtime code then
    resolves models through the normal Learning registry path.
    """

    model_id: str = ""
    artifact_path: str = ""


@dataclass
class ValidationConfig:
    holdout: ValidationHoldoutConfig = field(default_factory=ValidationHoldoutConfig)


def make_validation() -> ValidationConfig:
    return ValidationConfig()
