from __future__ import annotations

from dataclasses import dataclass


@dataclass
class SurrogateConfig:
    """Surrogate model selection (extensible via factory/registry)."""

    model: str = "xgb"  # "rf" | "gpr" | "xgb"


def make_surrogate() -> SurrogateConfig:
    return SurrogateConfig(model="xgb")
