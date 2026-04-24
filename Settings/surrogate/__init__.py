from __future__ import annotations

from .surrogate import SurrogateConfig, make_surrogate
from .train import SurrogateTrainConfig, make_surrogate_train

__all__ = ["SurrogateConfig", "SurrogateTrainConfig", "make_surrogate", "make_surrogate_train"]
