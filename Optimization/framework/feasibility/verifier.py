from __future__ import annotations

from typing import Any, List, Tuple

import numpy as np

from Optimization.framework.engines.Gold.gold_engine import GoldEngine


def verify_indices_with_gold(
    *,
    settings: Any,
    X: np.ndarray,
    F: np.ndarray,
    G: np.ndarray,
    selected_indices: List[int],
    active_constraint_names: List[str],
    original_labels: np.ndarray,
) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    X_arr = np.asarray(X, dtype=float)
    F_out = np.asarray(F, dtype=float).copy()
    G_out = np.asarray(G, dtype=float).copy()
    labels = np.asarray(original_labels, dtype=object).copy()

    gold = GoldEngine(settings)
    for idx in selected_indices:
        F_i, G_i, _flows, _raw = gold.evaluate_one_with_details(X_arr[idx, :])
        F_out[idx, :] = np.asarray(F_i, dtype=float).reshape(-1)
        G_row = np.asarray(G_i, dtype=float).reshape(-1)
        if G_out.size:
            G_out[idx, :] = G_row
        is_feasible = bool(np.all(G_row[: len(active_constraint_names)] <= 0.0))
        labels[idx] = "verified_feasible" if is_feasible else "verified_infeasible"
    return F_out, G_out, labels


def apply_feasibility_verification(
    *,
    settings: Any,
    engine: Any,
    X: np.ndarray,
    F: np.ndarray,
    G: np.ndarray | None,
    runtime_meta: dict | None = None,
):
    from .gate import apply_feasibility_gate

    return apply_feasibility_gate(
        settings=settings,
        engine=engine,
        X=X,
        F=F,
        G=G,
        runtime_meta=runtime_meta,
    )
