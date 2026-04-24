from __future__ import annotations

from typing import Any, Dict, List, Tuple

import numpy as np

from .classifier import classify_population
from .selector import select_verification_indices
from .types import FeasibilityVerificationSummary
from .verifier import verify_indices_with_gold


def _resolve_active_constraint_names(settings: Any, G: np.ndarray | None) -> List[str]:
    names = list(getattr(getattr(settings, "constraints", None), "names", []) or [])
    if G is None:
        return []
    G = np.asarray(G, dtype=float)
    if G.ndim == 1:
        G = G.reshape(1, -1)
    return [str(names[i]) for i in range(min(len(names), G.shape[1]))]


def _summary_from_labels(
    *,
    summary: FeasibilityVerificationSummary,
    labels: np.ndarray,
) -> None:
    as_list = [str(x) for x in np.asarray(labels, dtype=object).tolist()]
    summary.labels = list(as_list)
    summary.feasible_indices = [int(i) for i, lbl in enumerate(as_list) if lbl == "feasible"]
    summary.infeasible_indices = [int(i) for i, lbl in enumerate(as_list) if lbl == "infeasible"]
    summary.uncertain_indices = [int(i) for i, lbl in enumerate(as_list) if lbl == "uncertain"]
    summary.verified_feasible_indices = [int(i) for i, lbl in enumerate(as_list) if lbl == "verified_feasible"]
    summary.verified_infeasible_indices = [int(i) for i, lbl in enumerate(as_list) if lbl == "verified_infeasible"]


def _require_uncertainty(mode: str) -> bool:
    return str(mode).strip().lower() in {"uncertainty_conservative", "hybrid"}


def apply_feasibility_gate(
    *,
    settings: Any,
    engine: Any,
    X: np.ndarray,
    F: np.ndarray,
    G: np.ndarray | None,
    runtime_meta: Dict[str, Any] | None = None,
) -> Tuple[np.ndarray, np.ndarray | None, Dict[str, Any]]:
    cfg = getattr(settings, "feasibility", None)
    mode = str(getattr(cfg, "mode", "hybrid")) if cfg is not None else "off"
    summary = FeasibilityVerificationSummary(
        enabled=bool(getattr(cfg, "enabled", False)) if cfg is not None else False,
        applied=False,
        scope=str(getattr(cfg, "selection_scope", "off")) if cfg is not None else "off",
        mode=mode,
        label_mode=str(getattr(cfg, "label_mode", "verified_three_way")) if cfg is not None else "verified_three_way",
        ranking_mode=str(getattr(cfg, "ranking_mode", "lexicographic")) if cfg is not None else "lexicographic",
        reason="disabled",
    )
    if cfg is None or not summary.enabled:
        return F, G, summary.__dict__

    X_arr = np.asarray(X, dtype=float)
    F_arr = np.asarray(F, dtype=float)
    G_arr = None if G is None else np.asarray(G, dtype=float)
    if X_arr.size == 0 or G_arr is None or G_arr.size == 0:
        summary.reason = "no_constraints_or_points"
        return F_arr, G_arr, summary.__dict__

    active_names = _resolve_active_constraint_names(settings, G_arr)
    margins = {str(k): float(v) for k, v in (getattr(cfg, "constraint_margins", {}) or {}).items()}
    default_margin = float(getattr(cfg, "default_constraint_margin", 0.0))

    G_pred = G_arr
    G_lower = None
    G_upper = None
    if _require_uncertainty(mode):
        predictor = getattr(engine, "predict_constraints_with_uncertainty", None)
        if predictor is None:
            raise RuntimeError(
                f"[feasibility] mode='{mode}' requires predict_constraints_with_uncertainty(X) on the active engine."
            )
        bundle = predictor(X_arr)
        bundle_names = [str(x) for x in list(bundle.get("constraint_names", []) or [])]
        if bundle_names != active_names:
            raise RuntimeError(
                f"[feasibility] Constraint name mismatch between settings/results and uncertainty bundle: "
                f"{active_names} vs {bundle_names}"
            )
        G_pred = np.asarray(bundle.get("g_pred"), dtype=float)
        G_lower = np.asarray(bundle.get("g_lower"), dtype=float)
        G_upper = np.asarray(bundle.get("g_upper"), dtype=float)

    labels, _decisions = classify_population(
        G_pred=G_pred,
        G_lower=G_lower,
        G_upper=G_upper,
        constraint_names=active_names,
        constraint_margins=margins,
        default_constraint_margin=default_margin,
    )
    _summary_from_labels(summary=summary, labels=labels)

    if str(mode).strip().lower() not in {"gold_recheck", "hybrid"}:
        summary.applied = True
        summary.reason = "classified_without_gold_recheck"
        return F_arr, G_arr, summary.__dict__

    selected = select_verification_indices(
        F=F_arr,
        labels=labels,
        settings=settings,
        runtime_meta=runtime_meta,
    )
    summary.selected_indices = list(selected)
    if not selected:
        summary.applied = True
        summary.reason = "no_selected_candidates"
        return F_arr, G_arr, summary.__dict__

    eng_name = str(getattr(getattr(settings, "engine", None), "name", "")).lower().strip()
    if eng_name == "gold":
        summary.applied = True
        summary.reason = "gold_run_no_recheck_needed"
        return F_arr, G_arr, summary.__dict__

    F_out, G_out, verified_labels = verify_indices_with_gold(
        settings=settings,
        X=X_arr,
        F=F_arr,
        G=G_arr,
        selected_indices=selected,
        active_constraint_names=active_names,
        original_labels=labels,
    )
    summary.verified_indices = list(selected)
    _summary_from_labels(summary=summary, labels=verified_labels)
    summary.applied = True
    summary.reason = "gold_verified"
    return F_out, G_out, summary.__dict__
