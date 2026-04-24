# Optimization/sensitivity/sobol_global/run_sobol.py
from __future__ import annotations

from pathlib import Path
from typing import Dict, Any

import numpy as np

from Settings import get_settings
from Optimization.sensitivity.sobol_global.sobol_problem import build_sobol_problem_from_settings
from Optimization.sensitivity.sobol_global.sobol_sampling import generate_sobol_samples
from Optimization.sensitivity.sobol_global.sobol_eval import eval_surrogate
from Optimization.sensitivity.sobol_global.sobol_analysis import (
    compute_sobol_indices,
    sobol_result_to_dataframe,
    save_sobol_dataframe,
)
from Optimization.sensitivity.sobol_global.sobol_plots import plot_sobol_bars


def _make_sobol_outdir(settings) -> Path:
    """
    Ergebnisordner für die Sobol-Analyse.

    Struktur:
      {output_root}/{location}/{tag}/sobol_global/
    """
    base = Path(str(settings.reporting.output_root))
    loc = str(settings.engine.location)
    tag = str(settings.run.tag)

    out_dir = base / loc / tag / "sobol_global"
    out_dir.mkdir(parents=True, exist_ok=True)
    return out_dir


def main(
    n_base: int = 1000,
    calc_second_order: bool = False,
) -> None:
    """
    Orchestrator für den globalen Sobol-Run.

    - liest Settings (get_settings)
    - baut Sobol-Problem aus settings.bounds
    - generiert Saltelli-Samples im Designraum
    - evaluiert das trainierte Surrogat
    - berechnet Sobol-Indizes für jede Objective
    - speichert CSV + PNG in den Run-spezifischen Ordner

    n_base sollte sinnvoll gewählt werden (z.B. 500–2000).
    """
    s = get_settings()
    problem: Dict[str, Any] = build_sobol_problem_from_settings(s)

    print(f"[sobol] Problem-Variablen: {problem['names']}")
    print(f"[sobol] Bounds: {problem['bounds']}")

    X = generate_sobol_samples(problem, n_base=n_base, calc_second_order=calc_second_order)
    print(f"[sobol] Generierte Samples: X.shape = {X.shape}")

    # Surrogat auswerten
    outputs = eval_surrogate(s, X)

    out_dir = _make_sobol_outdir(s)

    for obj_name, Y in outputs.items():
        print(f"[sobol] Analyse für Objective: {obj_name}")
        res = compute_sobol_indices(problem, Y, calc_second_order=calc_second_order)
        df = sobol_result_to_dataframe(problem, res)

        csv_path = out_dir / f"sobol_{obj_name}.csv"
        save_sobol_dataframe(df, csv_path)
        print(f"[sobol] CSV gespeichert: {csv_path}")

        png_path = out_dir / f"sobol_{obj_name}.png"
        plot_sobol_bars(df, title=f"Sobol – {obj_name}", out_path=png_path)
        print(f"[sobol] Plot gespeichert: {png_path}")


if __name__ == "__main__":
    # Für direkten Aufruf:
    #   python -m Optimization.sensitivity.sobol_global.run_sobol
    main()
