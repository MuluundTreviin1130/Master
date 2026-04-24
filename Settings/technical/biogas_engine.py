from __future__ import annotations

from dataclasses import dataclass


@dataclass
class BiogasEngineConfig:
    min_partload: float = 0.35
    max_partload: float = 1.0
    fixed_output_fraction: float = 0.6
    dispatch_mode: str = "fixed_band"  # fixed_band | demand_following


def make_biogas_engine() -> BiogasEngineConfig:
    return BiogasEngineConfig()
