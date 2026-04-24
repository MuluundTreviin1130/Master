from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


@dataclass
class GatingSurrogateConfig:
    enabled: bool
    rule: str
    fraction_max: float
    uncertainty_quantile: float
    min_points: int
    max_points: Optional[int]


@dataclass
class GatingGoldConfig:
    enabled: bool
    mode: str
    fraction_max: float
    min_points: int
    period_batches: int
    finalists_k: int


@dataclass
class GatingAuditConfig:
    enabled: bool
    ref_margin: float
    rank_method: str


@dataclass
class GatingRetrainConfig:
    enabled: bool
    min_truth_points: int
    every_n_surrogate: int
    every_n_batches: int
    source: str
    save_artifacts: bool
    artifact_dirname: str


@dataclass
class GatingControlConfig:
    enabled: bool
    metric: str
    target: float
    patience: int
    surrogate_step: float
    surrogate_cap: float
    gold_step_points: int
    gold_cap_points: int


@dataclass
class GatingGuardConfig:
    enabled: bool
    metric: str
    threshold: float
    patience: int
    action: str
    print_every: int


@dataclass
class GatingConfig:
    enabled: bool
    surrogate: GatingSurrogateConfig
    gold: GatingGoldConfig
    audit: GatingAuditConfig
    retrain: GatingRetrainConfig
    control: GatingControlConfig
    guard: GatingGuardConfig


def make_gating() -> GatingConfig:
    return GatingConfig(
        enabled=True,
        surrogate=GatingSurrogateConfig(
            enabled=False,
            rule="pareto+finalists",
            fraction_max=0.1,
            uncertainty_quantile=0.90,
            min_points=5,
            max_points=20,
        ),
        gold=GatingGoldConfig(
            enabled=True,
            mode="periodic",  # periodic+finalists
            fraction_max=0.08,
            min_points=8,
            period_batches=2,
            finalists_k=15,
        ),
        audit=GatingAuditConfig(
            enabled=True,
            ref_margin=0.05,
            rank_method="spearman",
        ),
        retrain=GatingRetrainConfig(
            enabled=True,
            min_truth_points=100,
            every_n_surrogate=3,
            every_n_batches=8,
            source="gold",
            save_artifacts=False,
            artifact_dirname="surrogate_versions",
        ),
        control=GatingControlConfig(
            enabled=True,
            metric="hv_error",
            target=0.05,
            patience=3,
            surrogate_step=0.10,
            surrogate_cap=0.30,
            gold_step_points=3,
            gold_cap_points=100,
        ),
        guard=GatingGuardConfig(
            enabled=True,
            metric="hv_error",
            threshold=0.1,
            patience=3,
            action="warn",
            print_every=1,
        ),
    )
