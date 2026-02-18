# Optimization/validation/metrics/pairwise_objectives.py
from __future__ import annotations

from typing import Dict, List
import numpy as np
import pandas as pd


def compute_pairwise_metrics(
    F_fast: pd.DataFrame,
    F_gold: pd.DataFrame,
    obj_names: List[str],
) -> Dict[str, float]:
    """
    Einfache Kennzahlen FAST vs GOLD:
      - R², RMSE, MAPE je Objective

    Keys: "<obj>_r2", "<obj>_rmse", "<obj>_mape"
    Referenz = GOLD, Prädiktor = FAST.
    """
    if F_fast is None or F_gold is None or not obj_names:
        return {}

    def r2(y, yhat):
        y = np.asarray(y, float)
        yhat = np.asarray(yhat, float)
        mask = np.isfinite(y) & np.isfinite(yhat)
        if not mask.any():
            return float("nan")
        y, yhat = y[mask], yhat[mask]
        ss_res = float(np.sum((y - yhat) ** 2))
        ss_tot = float(np.sum((y - np.mean(y)) ** 2))
        return 1.0 - ss_res / ss_tot if ss_tot > 0 else float("nan")

    def rmse(y, yhat):
        y = np.asarray(y, float)
        yhat = np.asarray(yhat, float)
        mask = np.isfinite(y) & np.isfinite(yhat)
        if not mask.any():
            return float("nan")
        return float(np.sqrt(np.mean((yhat[mask] - y[mask]) ** 2)))

    def mape(y, yhat, eps=1e-9):
        y = np.asarray(y, float)
        yhat = np.asarray(yhat, float)
        mask = np.isfinite(y) & np.isfinite(yhat) & (np.abs(y) > eps)
        if not mask.any():
            return float("nan")
        return float(np.mean(np.abs((yhat[mask] - y[mask]) / y[mask]))) * 100.0

    common_idx = F_fast.index.intersection(F_gold.index)
    if len(common_idx) == 0:
        return {}

    A = F_fast.loc[common_idx, obj_names]
    B = F_gold.loc[common_idx, obj_names]

    out: Dict[str, float] = {}
    for name in obj_names:
        if name not in A.columns or name not in B.columns:
            continue
        out[f"{name}_r2"] = r2(B[name].values, A[name].values)
        out[f"{name}_rmse"] = rmse(B[name].values, A[name].values)
        out[f"{name}_mape"] = mape(B[name].values, A[name].values)
    return out
