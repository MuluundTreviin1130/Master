from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional

from Settings.run.sh_arms import make_scheduler_arms


@dataclass
class SchedulerArmConfig:
    """One scheduler arm (feature toggles + bounds/settings overrides)."""

    name: str
    features: Dict[str, bool] = field(default_factory=dict)
    bounds_override: Dict[str, List[float]] = field(default_factory=dict)
    caps_override: Dict[str, float] = field(default_factory=dict)
    delta_t_override: Optional[float] = None
    members_override: Optional[dict] = None
    tariff_arm: Optional[str] = None


@dataclass
class SchedulerOutputsConfig:
    """Output policy for scheduler meta-runs."""

    cleanup_nonfinal_runs: bool = True
    cleanup_final_runs: bool = True
    aggregate_final_loadflows_by_arm: bool = True
    aggregate_final_ghg_debug_by_arm: bool = False
    final_export_arm_mode: str = "top_k"  # "top_k" | "all" | "list" | "none"
    final_export_top_k_arms: int = 5
    final_export_arm_names: List[str] = field(default_factory=list)
    final_export_max_points_per_arm: int = 10


@dataclass
class SchedulerConfig:
    """Meta-run configuration for SH/Hyperband via Optuna.

    Defaults target a full run.
    """

    enabled: bool = True
    pruner: str = "successive_halving"  # "successive_halving" | "hyperband"
    budget_param: str = "n_gen"  # locked: budget maps to optimizer.kwargs.n_gen
    # 0 means auto: run all configured arms once.
    n_trials: int = 0
    seed: int = 42
    unique_arms_once: bool = True
    arms_mode: str = "baseline"  # "baseline" | "giw"
    min_resource: int = 5
    reduction_factor: int = 3
    # Constraints used for cross-arm scoring/feasibility in scheduler.
    # Keep this to constraints that are active for all arms.
    scoring_constraints: List[str] = field(default_factory=lambda: ["autarky_min", "export_share_max"])
    # If True and scoring_constraints are set, missing constraints in a run raise an error.
    require_scoring_constraints_present: bool = True
    # TEMP safety option: re-score final stage with gold instead of surrogate outputs.
    # Keep False for normal SH runs; can be removed later.
    use_gold_for_final_scoring: bool = False
    outputs: SchedulerOutputsConfig = field(default_factory=SchedulerOutputsConfig)
    arms: List[SchedulerArmConfig] = field(default_factory=list)

    def __post_init__(self) -> None:
        if not self.arms:
            self.arms = make_scheduler_arms(self.arms_mode)


def make_scheduler() -> SchedulerConfig:
    return SchedulerConfig()
