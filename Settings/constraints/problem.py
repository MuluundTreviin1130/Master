from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List

from Settings.problem.pb_config import make_pb_cfg_for_engine


@dataclass
class ProblemConstraintConfig:
    names: List[str] = field(default_factory=list)
    senses: List[str] = field(default_factory=list)
    rhs: List[float] = field(default_factory=list)
    cfg: Dict[str, Any] = field(default_factory=dict)


ACTIVE_BASE_CONSTRAINTS: List[str] = [
    "autarky_min",
    "export_share_max",
]


RHS_DEFAULTS: Dict[str, float] = {
    "bess_cyclic": 0.0,
    "h2_cyclic": 0.0,
    "h2_tank_to_ely_min": 0.0,
    "h2_tank_to_ely_max": 0.0,
    "h2_fc_to_ely_min": 0.0,
    "h2_fc_to_ely_max": 0.0,
    "autarky_min": 0.5,
    "export_share_max": 0.5,
}


def make_problem_constraints(engine, lifetime_years: int) -> ProblemConstraintConfig:
    pb_cfg = make_pb_cfg_for_engine(engine)
    enabled_pb_categories = list(pb_cfg.get("enabled_categories", []) or [])
    pb_names = [f"pb_tl_{c}" for c in enabled_pb_categories]

    enable_h2 = bool(getattr(getattr(engine, "features", None), "enable_h2", False))
    bess_names: List[str] = []
    h2_names = ["h2_cyclic"] if enable_h2 else []
    h2_cfg = getattr(getattr(engine, "settings_obj", None), "hydrogen", None)
    if enable_h2 and bool(getattr(h2_cfg, "coupling_enabled", True)):
        h2_names.extend(
            [
                "h2_tank_to_ely_min",
                "h2_tank_to_ely_max",
                "h2_fc_to_ely_min",
                "h2_fc_to_ely_max",
            ]
        )

    names = [
        *pb_names,
        *bess_names,
        *h2_names,
        *ACTIVE_BASE_CONSTRAINTS,
    ]
    senses = ["<=" for _ in names]
    rhs = [0.0 if str(n).startswith("pb_tl_") else float(RHS_DEFAULTS.get(str(n), 0.0)) for n in names]

    return ProblemConstraintConfig(
        names=names,
        senses=senses,
        rhs=rhs,
        cfg={
            "pb": pb_cfg,
            "lca_max": {},
        },
    )
