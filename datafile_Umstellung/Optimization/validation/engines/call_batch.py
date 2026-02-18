# Optimization/validation/teachers/call_batch.py
from __future__ import annotations

import pandas as pd


def _normalize_batch_output(out, index):
    if isinstance(out, tuple) and len(out) == 2:
        flows, kpis = out
    else:
        flows, kpis = out, None

    F = pd.DataFrame(flows, index=index)
    K = pd.DataFrame(kpis, index=index) if kpis is not None else pd.DataFrame(index=index)
    return F, K


def call_batch(sim_fn, X: pd.DataFrame, S):
    """
    Versucht vektorisierten Call:
      1) simulate(X, S)
      2) simulate(X)
    """
    try:
        out = sim_fn(X, S)
    except TypeError:
        out = sim_fn(X)
    return _normalize_batch_output(out, X.index)
