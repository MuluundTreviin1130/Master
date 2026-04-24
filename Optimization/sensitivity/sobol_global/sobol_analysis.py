# Optimization/sensitivity/sobol_global/sobol_analysis.py
from __future__ import annotations

from pathlib import Path
from typing import Dict, Any

import numpy as np
import pandas as pd

try:
    from SALib.analyze import sobol
except ImportError as exc:  # pragma: no cover
    raise ImportError(
        "[sobol] SALib ist nicht installiert. "
        "Bitte mit `pip install SALib` nachrüsten."
    ) from exc


def compute_sobol_indices(
    problem: Dict[str, Any],
    Y: np.ndarray,
    calc_second_order: bool = False,
) -> Dict[str, Any]:
    """
    Führt die Sobol-Analyse für einen Output-Vektor Y durch.

    Parameters
    ----------
    problem : dict
        SALib-kompatibles Problem-Dict.
    Y : ndarray, shape (N,)
        Modelloutput (z.B. NPC-Werte).
    calc_second_order : bool
        Ob Second-Order-Indizes berechnet werden sollen.

    Returns
    -------
    result : dict
        SALib-Ergebnis mit S1, ST, (optional S2) und Konfidenzintervallen.
    """
    Y = np.asarray(Y, float).ravel()
    if Y.ndim != 1:
        raise ValueError(f"[sobol] Y muss 1D sein, ist aber shape={Y.shape}.")

    res = sobol.analyze(
        problem,
        Y,
        calc_second_order=calc_second_order,
        print_to_console=False,
    )
    return res


def sobol_result_to_dataframe(
    problem: Dict[str, Any],
    res: Dict[str, Any],
) -> pd.DataFrame:
    """
    Formatiert SALib-Sobol-Resultate als DataFrame.

    Spalten:
      - var: Name der Eingangsvariablen
      - S1, S1_conf
      - ST, ST_conf
      - optional: S2_idx, S2, S2_conf (falls second order berechnet wurde)
    """
    names = list(problem["names"])
    S1 = res["S1"]
    S1_conf = res["S1_conf"]
    ST = res["ST"]
    ST_conf = res["ST_conf"]

    df = pd.DataFrame(
        {
            "var": names,
            "S1": S1,
            "S1_conf": S1_conf,
            "ST": ST,
            "ST_conf": ST_conf,
        }
    )

    # Optional: pairwise S2 (Matrix)
    if "S2" in res and res["S2"] is not None:
        # Wir flatten die nicht-diagonalen Einträge, falls du das später brauchst.
        # Für die einfache Auswertung reichen S1/ST normalerweise.
        pass

    return df


def save_sobol_dataframe(df, out_path: Path) -> Path:
    """
    Speichert den Sobol-DataFrame als CSV.
    """
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(out_path, index=False)
    return out_path
