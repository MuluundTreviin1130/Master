from __future__ import annotations

from dataclasses import dataclass
from typing import Tuple


@dataclass
class BudgetState:
    surrogate_fraction: float
    gold_min_points: int


@dataclass
class ControlState:
    bad_streak: int = 0
    good_streak: int = 0


class BudgetController:
    def __init__(self, cfg_control, baseline_state: BudgetState) -> None:
        self.cfg = cfg_control
        self.baseline = BudgetState(
            surrogate_fraction=float(baseline_state.surrogate_fraction),
            gold_min_points=int(baseline_state.gold_min_points),
        )
        self.state = ControlState()

    def update(self, metric_value: float, state: BudgetState) -> Tuple[BudgetState, ControlState, str]:
        target = float(getattr(self.cfg, "target", 0.25))
        patience = max(1, int(getattr(self.cfg, "patience", 2)))
        surrogate_step = float(getattr(self.cfg, "surrogate_step", 0.05))
        surrogate_cap = float(getattr(self.cfg, "surrogate_cap", 0.40))
        gold_step = int(getattr(self.cfg, "gold_step_points", 5))
        gold_cap = int(getattr(self.cfg, "gold_cap_points", 30))

        bad = metric_value > target
        if bad:
            self.state.bad_streak += 1
            self.state.good_streak = 0
        else:
            self.state.good_streak += 1
            self.state.bad_streak = 0

        surrogate_fraction = float(state.surrogate_fraction)
        gold_min_points = int(state.gold_min_points)
        action = "none"

        if self.state.bad_streak >= patience:
            surrogate_fraction = min(surrogate_fraction + surrogate_step, surrogate_cap)
            gold_min_points = min(gold_min_points + gold_step, gold_cap)
            self.state.bad_streak = 0
            action = "increase"
        elif self.state.good_streak >= patience:
            surrogate_fraction = max(surrogate_fraction - surrogate_step, self.baseline.surrogate_fraction)
            gold_min_points = max(gold_min_points - gold_step, self.baseline.gold_min_points)
            self.state.good_streak = 0
            action = "decrease"

        return BudgetState(surrogate_fraction=surrogate_fraction, gold_min_points=gold_min_points), self.state, action
