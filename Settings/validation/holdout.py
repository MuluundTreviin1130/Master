from __future__ import annotations

from dataclasses import dataclass, field
from typing import List


@dataclass
class HoldoutConfig:
    """Holdout validation settings kept under the Settings SSOT.

    The large repo re-layout moved the old validation config out of
    ``Optimization/framework/Settings``.  Settings imports still expect this
    object, and the Learning runtime also reads ``model_id`` and
    ``artifact_path`` for explicit validation overrides.
    """

    enabled: bool = True
    mode: str = "generate"  # "generate" | "file"
    holdout_id: str = "v002"
    n: int = 600
    seed: int = 0
    sampler: str = "lhs"
    xschema: List[str] = field(default_factory=list)
    bounds_source: str = "settings"
    report_kpis: List[str] = field(default_factory=lambda: ["npc_eur", "grid_interaction_kwh"])
    ref_engine: str = "gold"
    pred_engine: str = "gated"
    root_dir: str = "Optimization/run/validation/results"
    strict: bool = True
    cache_gold_truth: bool = True
    batch_size: int = 10
    model_id: str = ""
    artifact_path: str = ""


@dataclass
class ValidationConfig:
    holdout: HoldoutConfig = field(default_factory=HoldoutConfig)


def make_validation() -> ValidationConfig:
    return ValidationConfig()
