from __future__ import annotations

from typing import Dict, List, Tuple

import numpy as np

from .types import FeasibilityDecision


def classify_population(
    *,
    G_pred: np.ndarray | None,
    constraint_names: List[str],
    constraint_margins: Dict[str, float],
    G_lower: np.ndarray | None = None,
    G_upper: np.ndarray | None = None,
    default_constraint_margin: float = 0.0,
) -> Tuple[np.ndarray, List[FeasibilityDecision]]:
    """Classify rows in standard ``g(x) <= 0`` space with optional uncertainty bounds."""

    if G_pred is None:
        return np.zeros((0,), dtype=object), []

    G_pred = np.asarray(G_pred, dtype=float)
    if G_pred.ndim == 1:
        G_pred = G_pred.reshape(1, -1)
    if G_pred.shape[1] == 0 or not constraint_names:
        labels = np.array(["feasible"] * G_pred.shape[0], dtype=object)
        decisions = [FeasibilityDecision(status="feasible", source="nominal") for _ in range(G_pred.shape[0])]
        return labels, decisions

    if G_lower is not None:
        G_lower = np.asarray(G_lower, dtype=float)
        if G_lower.ndim == 1:
            G_lower = G_lower.reshape(1, -1)
    if G_upper is not None:
        G_upper = np.asarray(G_upper, dtype=float)
        if G_upper.ndim == 1:
            G_upper = G_upper.reshape(1, -1)

    labels: List[str] = []
    decisions: List[FeasibilityDecision] = []
    for i in range(G_pred.shape[0]):
        row_status = "feasible"
        per_constraint: Dict[str, str] = {}
        for j, name in enumerate(constraint_names):
            margin = float(constraint_margins.get(str(name), default_constraint_margin))
            g_pred = float(G_pred[i, j]) if j < G_pred.shape[1] else 0.0
            g_lower = float(G_lower[i, j]) if G_lower is not None and j < G_lower.shape[1] else g_pred
            g_upper = float(G_upper[i, j]) if G_upper is not None and j < G_upper.shape[1] else g_pred

            if g_upper <= -margin:
                status = "feasible"
            elif g_lower > margin:
                status = "infeasible"
            else:
                status = "uncertain"
            per_constraint[str(name)] = status
            if status == "infeasible":
                row_status = "infeasible"
            elif status == "uncertain" and row_status != "infeasible":
                row_status = "uncertain"
        labels.append(row_status)
        decisions.append(FeasibilityDecision(status=row_status, per_constraint=per_constraint, source="classifier"))
    return np.asarray(labels, dtype=object), decisions
