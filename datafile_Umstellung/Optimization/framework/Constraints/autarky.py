# Optimization/framework/Constraints/autarky.py
from __future__ import annotations

from typing import Any, Dict


def can_handle(name: str) -> bool:
    return name == "autarky_min"


def evaluate_one(name: str, sense: str, rhs: float, ctx: Dict[str, Any], settings_constraints: Any) -> float:
    """
    Berechnet die Autarkie-Constraint.
    
    Autarkie-Formel: autarky = 1 - (E_import_grid_L / E_load_L)
    Constraint: autarky >= rhs   => g = rhs - autarky <= 0
    
    Args:
        name: Constraint-Name (muss "autarky_min" sein)
        sense: Constraint-Sense (wird ignoriert, immer "autarky >= rhs")
        rhs: Mindest-Autarkie (z.B. 0.8 für 80%)
        ctx: Kontext mit E_import_grid_L und E_load_L (beide in kWh, Lebensdauer)
        settings_constraints: Settings-Objekt (wird nicht verwendet)
    
    Returns:
        Constraint-Wert g, wobei g <= 0 bedeutet, dass die Constraint erfüllt ist.
        g = rhs - autarky
        Beispiel: Bei rhs=0.8 und autarky=0.9 ist g = 0.8 - 0.9 = -0.1 (erfüllt)
                  Bei rhs=0.8 und autarky=0.7 ist g = 0.8 - 0.7 = +0.1 (verletzt)
    """
    if name != "autarky_min":
        return 0.0

    E_import_grid_L = float(ctx.get("E_import_grid_L", 0.0))
    E_load_L = float(ctx.get("E_load_L", 0.0))

    # Sicherstellen, dass E_import_grid_L nicht negativ ist
    E_import_grid_L = max(0.0, E_import_grid_L)
    
    # Autarkie berechnen
    if E_load_L > 1e-6:  # Vermeide Division durch sehr kleine Zahlen
        autarky = 1.0 - (E_import_grid_L / E_load_L)
    else:
        # Keine Last oder sehr kleine Last: Autarkie ist undefiniert, setze auf 0
        autarky = 0.0
    
    # Autarkie auf [0, 1] klemmem (sollte eigentlich nicht nötig sein, aber sicherheitshalber)
    autarky = float(max(0.0, min(1.0, autarky)))

    # Constraint: autarky >= rhs   => g = rhs - autarky <= 0
    # enforce "autarky >= rhs" regardless of sense string
    g = float(rhs - autarky)
    
    # Debug-Check: Wenn g sehr negativ ist, könnte es ein Problem geben
    if g < -1.0:
        # Das sollte nicht passieren, da autarky auf [0, 1] geklemmt wird
        # Falls doch, gibt es möglicherweise ein Problem mit E_load_L oder E_import_grid_L
        import warnings
        warnings.warn(
            f"[autarky] Unerwartet negativer Constraint-Wert: g={g:.4f}, "
            f"autarky={autarky:.4f}, rhs={rhs:.4f}, "
            f"E_import_grid_L={E_import_grid_L:.2f}, E_load_L={E_load_L:.2f}. "
            f"Dies deutet auf ein Problem mit der Berechnung hin."
        )
    
    return g
