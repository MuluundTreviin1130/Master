from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class HoldoutValidationConfig:
    """Optional explicit model selection for validation runs.

    Empty strings mean that no validation override is active.  Runtime code must
    still validate any non-empty model id or artifact path before using it.
    """

    model_id: str = ""
    artifact_path: str = ""


@dataclass
class ValidationConfig:
    holdout: HoldoutValidationConfig = field(default_factory=HoldoutValidationConfig)


def make_validation() -> ValidationConfig:
    return ValidationConfig()
