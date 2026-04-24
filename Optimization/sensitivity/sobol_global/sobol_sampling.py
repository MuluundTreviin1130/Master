# Optimization/sensitivity/sobol_global/sobol_sampling.py
from __future__ import annotations

from typing import Dict, Any
import numpy as np

try:
    # SALib ist der De-facto Standard für Sobol/Saltelli
    from SALib.sample import saltelli
except ImportError as exc:  # pragma: no cover - nur Laufzeit
    raise ImportError(
        "[sobol] SALib ist nicht installiert. "
        "Bitte mit `pip install SALib` nachrüsten."
    ) from exc


def generate_sobol_samples(
    problem: Dict[str, Any],
    n_base: int,
    calc_second_order: bool = False,
) -> np.ndarray:
    """
    Erzeugt Saltelli-Samples im Eingangsraum.

    Parameters
    ----------
    problem : dict
        SALib-kompatibles Problem-Dict (num_vars, names, bounds)
    n_base : int
        Basisstichprobe N. Die tatsächliche Zahl der Samples wird durch
        die Saltelli-Formel N * (2D + 2) bestimmt.
    calc_second_order : bool
        Ob Second-Order-Indizes (S2) berechnet werden sollen. Das erhöht
        die Sample-Anzahl noch einmal deutlich.

    Returns
    -------
    X : ndarray, shape (N_eff, D)
        Sample-Matrix im Designraum.
    """
    if n_base <= 0:
        raise ValueError(f"[sobol] n_base muss > 0 sein, ist aber {n_base}.")

    X = saltelli.sample(
        problem,
        N=n_base,
        calc_second_order=calc_second_order,
    )
    # SALib liefert bereits ein np.ndarray
    return X
