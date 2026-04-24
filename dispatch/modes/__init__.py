from __future__ import annotations

__all__ = ["run_heuristic_dispatch", "run_milp_day_ahead_dispatch", "run_milp_two_stage_dispatch"]


def run_heuristic_dispatch(*args, **kwargs):
    from .heuristic import run_heuristic_dispatch as _fn
    return _fn(*args, **kwargs)


def run_milp_day_ahead_dispatch(*args, **kwargs):
    from .milp_day_ahead import run_milp_day_ahead_dispatch as _fn
    return _fn(*args, **kwargs)


def run_milp_two_stage_dispatch(*args, **kwargs):
    from .milp_two_stage import run_milp_two_stage_dispatch as _fn
    return _fn(*args, **kwargs)
