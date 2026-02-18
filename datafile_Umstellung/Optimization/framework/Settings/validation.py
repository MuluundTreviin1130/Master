from __future__ import annotations

from dataclasses import dataclass, field
from typing import List


@dataclass
class HoldoutConfig:
    enabled: bool = True    
    mode: str = "generate"  # "generate" | "file"
    holdout_id: str = "v002"
    n: int = 600 # 1000 für 1000 Punkte
    seed: int = 0
    sampler: str = "lhs"
    xschema: List[str] = field(default_factory=list)
    bounds_source: str = "settings"
    report_kpis: List[str] = field(default_factory=lambda: ["npc_eur", "grid_interaction_kwh"])
    ref_engine: str = "gold"
    pred_engine: str = "gated"
    root_dir: str = "V2H_energy_community_surrogat_datafilenew/datafile_Umstellung/Optimization/validation/results"
    strict: bool = True
    cache_gold_truth: bool = True
    batch_size: int = 10  # Batch size for gated engine evaluation (smaller = more batches = more non-dominated points per batch)


@dataclass
class ValidationConfig:
    holdout: HoldoutConfig


def make_validation() -> ValidationConfig:
    return ValidationConfig(holdout=HoldoutConfig())
