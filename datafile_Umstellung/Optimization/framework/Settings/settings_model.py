from __future__ import annotations
from dataclasses import dataclass

from .run import RunConfig
from .engine import EngineConfig
from .bounds import Bounds
from .objectives import Objectives
from .constraints import Constraints
from .sampler import SamplerConfig
from .optimizer import OptimizerConfig
from .reporting import ReportingConfig
from .surrogate_train import SurrogateTrainConfig
from .gating import GatingConfig
from .validation import ValidationConfig

@dataclass
class Settings:
    run: RunConfig
    engine: EngineConfig
    bounds: Bounds
    objectives: Objectives
    constraints: Constraints
    sampler: SamplerConfig
    optimizer: OptimizerConfig
    reporting: ReportingConfig
    surrogate_train: SurrogateTrainConfig
    gating: GatingConfig
    validation: ValidationConfig