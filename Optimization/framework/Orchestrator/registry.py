# Optimization/framework/Orchestrator/registry.py
from __future__ import annotations

from ..engines.Gated.gated_engine import GatedEngine
from ..engines.Gold.gold_engine import GoldEngine
from ..engines.Surrogat_model.surrogate_engine import SurrogateEngine

_ENGINE_REG = {
    "gold": GoldEngine,
    "surrogate": SurrogateEngine,
    "gated": GatedEngine,
}


def resolve_engine(name: str):
    key = (name or "").lower()
    if key not in _ENGINE_REG:
        raise ValueError(f"[registry] Unknown engine '{name}'. Available: {list(_ENGINE_REG)}")
    return _ENGINE_REG[key]

