# Optimization/validation/sampling/subsets.py
from __future__ import annotations

from typing import Iterable, Optional
import numpy as np
import pandas as pd


def _rng(seed: Optional[int]) -> np.random.Generator:
    return np.random.default_rng(None if seed is None else int(seed))


def _numeric_cols(df: pd.DataFrame) -> list[str]:
    return [c for c in df.columns if pd.api.types.is_numeric_dtype(df[c])]


def _edge_indices(df: pd.DataFrame, cols: Iterable[str]) -> list[int]:
    """
    Liefert Index-Positionen von Zeilen, die an den Min/Max-Rändern pro Spalte liegen.
    """
    idx = set()
    for c in cols:
        if c in df.columns and pd.api.types.is_numeric_dtype(df[c]):
            col = df[c]
            if col.empty:
                continue
            mn = float(col.min())
            mx = float(col.max())
            idx.update(col.index[col == mn].tolist())
            idx.update(col.index[col == mx].tolist())
    return sorted(idx)


def subset_by_strategy(
    X: pd.DataFrame,
    strategy: str,
    k_total: int,
    seed: Optional[int] = None,
    xschema_names: Optional[Iterable[str]] = None,
) -> pd.DataFrame:
    """
    Wählt ein Subset der Zeilen basierend auf einer Strategie.
    Unterstützte Strategien:
      - "all"         : alles
      - "fixed_k"     : erste k_total Zeilen
      - "edges"       : Randpunkte (Min/Max pro Spalte) + ggf. Zufall auffüllen
      - "mixed"       : wie edges, aber Rest random
      - "pareto_focus": derzeit leichter Fallback (random)
      - "diverse_kcenter": derzeit leichter Fallback (random)
      - "top_error"   : derzeit leichter Fallback (random)
      - sonst         : random
    """
    dfn = X.reset_index(drop=True)
    n = len(dfn)
    if n == 0:
        return dfn

    if k_total is None or k_total >= n:
        return dfn.copy()
    if k_total <= 0:
        return dfn.head(0).copy()

    k_total = int(k_total)
    rng = _rng(seed)

    if strategy == "all":
        return dfn.copy()

    if strategy == "fixed_k":
        return dfn.head(k_total).copy()

    if strategy in ("edges", "mixed"):
        cols = list(xschema_names) if xschema_names else _numeric_cols(dfn)
        edge_idx = _edge_indices(dfn, cols)
        sel = dfn.loc[edge_idx].drop_duplicates()
        need = max(0, k_total - len(sel))
        if need > 0:
            rest = dfn.drop(index=sel.index, errors="ignore")
            if len(rest) > 0:
                pick = rng.choice(len(rest), size=min(need, len(rest)), replace=False)
                sel = pd.concat([sel, rest.iloc[pick]], axis=0)
        return sel.reset_index(drop=True)

    # Fallback-Strategien: derzeit random-Subset gleicher Größe
    if strategy in ("pareto_focus", "diverse_kcenter", "top_error"):
        k = min(k_total, n)
        pick = rng.choice(n, size=k, replace=False)
        return dfn.iloc[pick].reset_index(drop=True)

    # Default: random
    k = min(k_total, n)
    pick = rng.choice(n, size=k, replace=False)
    return dfn.iloc[pick].reset_index(drop=True)
