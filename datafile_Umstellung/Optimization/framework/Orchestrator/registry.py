# Optimization/framework/Orchestrator/registry.py

# Relative Imports für Konsistenz mit dem Rest des Projekts
from ..engines.Gold.gold_engine import GoldEngine
from ..engines.Vectorized_model.fast_engine import FastEngine
from ..engines.Surrogat_model.surrogate_engine import SurrogateEngine
from ..engines.Gated.gated_engine import GatedEngine

_ENGINE_REG = {
    "gold": GoldEngine,
    "fast": FastEngine,
    "surrogate": SurrogateEngine,
    "gated": GatedEngine,
}

def resolve_engine(name: str):
    import inspect
    key = (name or "").lower()
    if key not in _ENGINE_REG:
        raise ValueError(f"[registry] Unknown engine '{name}'. Available: {list(_ENGINE_REG)}")
    Eng = _ENGINE_REG[key]
    return Eng
