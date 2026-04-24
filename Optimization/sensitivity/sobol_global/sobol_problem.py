# Optimization/sensitivity/sobol_global/sobol_problem.py
from __future__ import annotations

from typing import Dict, Any, List


def build_sobol_problem_from_settings(settings) -> Dict[str, Any]:
    """
    Baut das SALib-kompatible "problem"-Dict aus den Bounds in den Settings.

    Aktuell: nur Design-Variablen (settings.bounds.*).
    Später: hier können optional Unsicherheits-Parameter (theta) ergänzt werden,
    z.B. settings.uncertainty.names / bounds.
    """
    names: List[str] = list(settings.bounds.names)
    lower: List[float] = list(settings.bounds.lower)
    upper: List[float] = list(settings.bounds.upper)

    if not (names and lower and upper):
        raise ValueError("[sobol] bounds in settings sind leer oder inkonsistent.")

    if not (len(names) == len(lower) == len(upper)):
        raise ValueError(
            f"[sobol] bounds length mismatch: "
            f"names={len(names)}, lower={len(lower)}, upper={len(upper)}"
        )

    bounds = [[float(lo), float(hi)] for lo, hi in zip(lower, upper)]

    problem: Dict[str, Any] = {
        "num_vars": len(names),
        "names": names,
        "bounds": bounds,
    }
    return problem
