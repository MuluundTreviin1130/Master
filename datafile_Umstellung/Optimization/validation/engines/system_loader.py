# Optimization/validation/teachers/system_loader.py
from __future__ import annotations

from importlib import import_module


def load_system_callable(system_id: str):
    """
    Lädt aus Technical_model.energy_system.systems.{system_id}
    eine passende Simulationsfunktion. Kein Registry-Overhead,
    nur Konvention über Funktionsnamen.
    """
    mod = import_module(f"Technical_model.energy_system.systems.{system_id}")
    for name in ("simulate_system", "simulate_energy_system", "simulate_energy_system_with_v2h"):
        fn = getattr(mod, name, None)
        if callable(fn):
            return fn

    raise AttributeError(
        f"[teacher] {system_id} hat keine passende Funktion "
        f"(simulate_system | simulate_energy_system | simulate_energy_system_with_v2h)"
    )
