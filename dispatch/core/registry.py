from __future__ import annotations

from collections.abc import Callable


DispatchRunner = Callable[..., object]


def get_dispatch_runner(mode: str) -> DispatchRunner:
    key = str(mode or "heuristic").strip().lower()
    if key == "heuristic":
        from dispatch.modes.heuristic import run_heuristic_dispatch
        return run_heuristic_dispatch
    if key == "milp_day_ahead":
        from dispatch.modes.milp_day_ahead import run_milp_day_ahead_dispatch
        return run_milp_day_ahead_dispatch
    if key == "milp_two_stage":
        from dispatch.modes.milp_two_stage import run_milp_two_stage_dispatch
        return run_milp_two_stage_dispatch
    raise ValueError(f"[dispatch] Unknown dispatch mode '{mode}'.")
