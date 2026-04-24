from __future__ import annotations

from dataclasses import dataclass


@dataclass
class WoodGasifierConfig:
    min_partload: float = 0.5
    max_partload: float = 1.0
    dispatch_mode: str = "demand_following"  # demand_following | fixed_band


def make_wood_gasifier() -> WoodGasifierConfig:
    return WoodGasifierConfig()
