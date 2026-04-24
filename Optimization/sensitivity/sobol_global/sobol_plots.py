# Optimization/sensitivity/sobol_global/sobol_plots.py
from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd


def plot_sobol_bars(
    df: pd.DataFrame,
    title: str,
    out_path: Path,
    sort_by: str = "S1",
) -> Path:
    """
    Einfacher Balkenplot für S1 und ST pro Eingangsvariable.

    Parameters
    ----------
    df : DataFrame
        Muss Spalten "var", "S1", "ST" enthalten.
    title : str
        Plot-Titel.
    out_path : Path
        Wohin der Plot geschrieben werden soll (PNG).
    sort_by : {"S1","ST"}
        Nach welcher Spalte sortiert werden soll.
    """
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    if sort_by not in ("S1", "ST"):
        sort_by = "S1"

    df_plot = df.sort_values(sort_by, ascending=False)

    vars_ = df_plot["var"].tolist()
    S1 = df_plot["S1"].values
    ST = df_plot["ST"].values

    x = range(len(vars_))

    plt.figure(figsize=(8, 5))
    plt.bar(x, S1, width=0.4, label="S1 (First-order)", align="center")
    plt.bar(
        [i + 0.4 for i in x],
        ST,
        width=0.4,
        label="ST (Total-order)",
        align="center",
    )
    plt.xticks([i + 0.2 for i in x], vars_, rotation=45, ha="right")
    plt.ylabel("Sobol-Index")
    plt.title(title)
    plt.legend()
    plt.tight_layout()
    plt.savefig(out_path, dpi=150)
    plt.close()

    return out_path
