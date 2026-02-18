from __future__ import annotations

from dataclasses import dataclass
from typing import Tuple


@dataclass
class GuardState:
    bad_streak: int = 0
    updates: int = 0


class FidelityGuard:
    def __init__(self, cfg_guard) -> None:
        self.cfg = cfg_guard
        self.state = GuardState()

    def update(self, metric_value: float, run_id: str = "") -> Tuple[GuardState, bool, str]:
        threshold = float(getattr(self.cfg, "threshold", 0.40))
        patience = max(1, int(getattr(self.cfg, "patience", 3)))
        print_every = max(1, int(getattr(self.cfg, "print_every", 1)))

        self.state.updates += 1
        if metric_value > threshold:
            self.state.bad_streak += 1
        else:
            self.state.bad_streak = 0

        triggered = self.state.bad_streak >= patience and (self.state.updates % print_every == 0)
        if not triggered:
            return self.state, False, ""

        rid = run_id or "unknown_run"
        msg = (
            f"[gated][guard] run={rid} hv_error={metric_value:.4f} > {threshold:.4f} "
            f"(streak={self.state.bad_streak}/{patience}). Recommended: increase FAST/GOLD budgets, "
            "enable retrain, and check signature compatibility."
        )
        return self.state, True, msg

