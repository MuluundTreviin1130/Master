# Optimization/framework/Constraints/dispatch.py
from __future__ import annotations

import importlib
import pkgutil
from dataclasses import dataclass
from types import ModuleType
from typing import Any, Callable, Dict, List, Optional


@dataclass(frozen=True)
class Provider:
    module: ModuleType
    can_handle: Callable[[str], bool]
    evaluate_one: Callable[[str, str, float, dict, Any], float]  # (name, sense, rhs, ctx, settings_constraints) -> g


def _discover_providers() -> List[Provider]:
    providers: List[Provider] = []

    pkg_name = __package__  # e.g. "Optimization.framework.Constraints"
    if not pkg_name:
        return providers

    pkg = importlib.import_module(pkg_name)   # <-- neu: Package-Objekt
    for m in pkgutil.iter_modules(pkg.__path__):  # <-- statt __path__
        mod_name = m.name
        if mod_name in {"__init__", "dispatch"}:
            continue

        module = importlib.import_module(f"{pkg_name}.{mod_name}")
        can_handle = getattr(module, "can_handle", None)
        evaluate_one = getattr(module, "evaluate_one", None)

        if callable(can_handle) and callable(evaluate_one):
            providers.append(Provider(module=module, can_handle=can_handle, evaluate_one=evaluate_one))

    return providers



# cache providers once (module import time)
_PROVIDERS: List[Provider] = _discover_providers()


def evaluate_constraints(settings_constraints: Any, ctx: Dict[str, Any]) -> List[float]:
    """
    Central entry point used by all engines.
    Returns a list of g(x) in the SAME ORDER as settings_constraints.names.
    Convention: g(x) <= 0 is satisfied.
    """
    names = list(getattr(settings_constraints, "names", []) or [])
    senses = list(getattr(settings_constraints, "senses", []) or [])
    rhs = list(getattr(settings_constraints, "rhs", []) or [])

    out: List[float] = []

    for i, name in enumerate(names):
        sense = senses[i] if i < len(senses) else "<="
        r = float(rhs[i]) if i < len(rhs) else 0.0

        g: Optional[float] = None
        for p in _PROVIDERS:
            if p.can_handle(name):
                g = float(p.evaluate_one(name, sense, r, ctx, settings_constraints))
                break

        if g is None:
            raise ValueError(f"Unknown constraint provider for {name!r}.")
        out.append(g)

    return out
