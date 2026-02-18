# Optimization/validation/io/plots.py
from __future__ import annotations

from pathlib import Path
import pandas as pd


def _has_two_cols(df: pd.DataFrame) -> bool:
    return isinstance(df, pd.DataFrame) and df.shape[1] >= 2 and df.shape[0] > 0


def plot_scatter(
    out_root: Path,
    k_ref: pd.DataFrame,
    k_pred: pd.DataFrame,
    title_suffix: str,
    f_ref: pd.DataFrame | None = None,
    f_pred: pd.DataFrame | None = None,
):
    """
    Einfacher 2D-Scatter (erste zwei Spalten) von Referenz vs Prädiktor.
    """
    if not _has_two_cols(k_ref) or not _has_two_cols(k_pred):
        return None

    import matplotlib.pyplot as plt  # noqa: WPS433

    p = out_root / "plots" / f"scatter_{title_suffix.lower()}.png"
    p.parent.mkdir(parents=True, exist_ok=True)

    fig, ax = plt.subplots()
    ax.scatter(k_ref.iloc[:, 0], k_ref.iloc[:, 1], label="reference", alpha=0.7)
    ax.scatter(k_pred.iloc[:, 0], k_pred.iloc[:, 1], label=title_suffix, alpha=0.7)
    ax.set_xlabel(k_ref.columns[0])
    ax.set_ylabel(k_ref.columns[1])
    ax.set_title(f"Scatter: reference vs {title_suffix}")
    ax.legend()
    fig.tight_layout()
    fig.savefig(p, dpi=150)
    plt.close(fig)
    return p


def plot_front(
    out_root: Path,
    k_ref: pd.DataFrame,
    k_pred: pd.DataFrame,
    title_suffix: str,
    f_ref: pd.DataFrame | None = None,
    f_pred: pd.DataFrame | None = None,
):
    """
    2D-Front-Plots (z.B. Pareto-Front) für Referenz vs Prädiktor.
    """
    if not _has_two_cols(k_ref) or not _has_two_cols(k_pred):
        return None

    import matplotlib.pyplot as plt  # noqa: WPS433

    p = out_root / "plots" / f"front_{title_suffix.lower()}.png"
    p.parent.mkdir(parents=True, exist_ok=True)

    fig, ax = plt.subplots()
    ax.plot(k_ref.iloc[:, 0], k_ref.iloc[:, 1], "o-", alpha=0.7, label="reference")
    ax.plot(k_pred.iloc[:, 0], k_pred.iloc[:, 1], "o-", alpha=0.7, label=title_suffix)
    ax.set_xlabel(k_ref.columns[0])
    ax.set_ylabel(k_ref.columns[1])
    ax.set_title(f"Front: reference vs {title_suffix}")
    ax.legend()
    fig.tight_layout()
    fig.savefig(p, dpi=150)
    plt.close(fig)
    return p
