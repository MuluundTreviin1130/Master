from __future__ import annotations

from typing import Any, Dict, List

import numpy as np


def _lexicographic_order(F: np.ndarray, minimize: List[bool]) -> np.ndarray:
    if F.size == 0:
        return np.zeros((0,), dtype=int)
    Fm = np.asarray(F, dtype=float).copy()
    signs = np.array([1.0 if bool(m) else -1.0 for m in minimize[: Fm.shape[1]]], dtype=float)
    if signs.shape[0] < Fm.shape[1]:
        signs = np.pad(signs, (0, Fm.shape[1] - signs.shape[0]), constant_values=1.0)
    Fm *= signs.reshape(1, -1)
    keys = [Fm[:, j] for j in reversed(range(Fm.shape[1]))]
    return np.lexsort(keys)


def select_verification_indices(
    *,
    F: np.ndarray,
    labels: np.ndarray,
    settings: Any,
    runtime_meta: Dict[str, Any] | None,
) -> List[int]:
    cfg = getattr(settings, "feasibility", None)
    if cfg is None or not bool(getattr(cfg, "enabled", False)):
        return []

    uncertain = [int(i) for i, lbl in enumerate(np.asarray(labels, dtype=object).tolist()) if str(lbl) == "uncertain"]
    if not uncertain:
        return []

    scope = str(getattr(cfg, "selection_scope", "pareto_and_uncertain")).lower().strip()
    max_verifications = max(0, int(getattr(cfg, "max_verifications", 0)))
    top_k = max(0, int(getattr(cfg, "top_k", 0)))
    arm_meta = (runtime_meta or {}).get("arm", {}) if isinstance(runtime_meta, dict) else {}
    is_scheduler_final_stage = bool(arm_meta.get("is_final_stage", False))

    if scope == "finalists_only" and not is_scheduler_final_stage:
        return []
    if scope in {"uncertain_only", "boundary_only", "finalists_only"}:
        chosen = uncertain
    elif scope == "pareto_and_uncertain":
        chosen = uncertain
    elif scope == "top_k_uncertain":
        minimize = list(getattr(getattr(settings, "objectives", None), "minimize", []) or [])
        order = _lexicographic_order(np.asarray(F, dtype=float)[uncertain, :], minimize)
        limit = top_k if top_k > 0 else len(uncertain)
        chosen = [uncertain[int(i)] for i in order[:limit]]
    else:
        chosen = uncertain

    if max_verifications <= 0:
        return []
    return [int(i) for i in chosen[:max_verifications]]
