# Optimization/validation/core/input_builder.py
from __future__ import annotations

import numpy as np
import pandas as pd


def build_X_from_bounds(S) -> pd.DataFrame:
    """
    Fallback: falls validate(cfg) kein X bekommt, erzeugen wir
    eine einfache Stichprobe aus den Bounds.

    Anzahl & Seed kommen aus S.validation.probes / S.validation.random_seed.
    """
    b = S.bounds
    names = list(b.names)
    lower = np.asarray(b.lower, dtype=float)
    upper = np.asarray(b.upper, dtype=float)

    V = getattr(S, "validation", None)
    n_total = 10
    seed = 0
    if V is not None:
        probes = getattr(V, "probes", None)
        if probes is not None:
            n_total = int(getattr(probes, "n_total", n_total))
        seed = int(getattr(V, "random_seed", seed))

    rng = np.random.default_rng(seed)
    u = rng.random((n_total, len(names)))
    X = lower + u * (upper - lower)
    return pd.DataFrame(X, columns=names)
