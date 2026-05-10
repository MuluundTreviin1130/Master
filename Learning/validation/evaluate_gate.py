from __future__ import annotations

from typing import Any, Dict, List

import numpy as np


def _target_metrics(y_true: np.ndarray, y_pred: np.ndarray) -> Dict[str, float]:
    """Calculate deterministic per-target holdout metrics.

    Relative MAE is scaled by the target's mean absolute truth value.  When the
    truth is identically zero, any non-zero error is treated as an infinite
    relative error so a zero-scale critical target cannot pass silently.
    """

    err = np.asarray(y_pred, dtype=float) - np.asarray(y_true, dtype=float)
    mae = float(np.mean(np.abs(err)))
    scale = float(np.mean(np.abs(y_true)))
    rel_mae_percent = 0.0 if scale <= 1e-12 and mae <= 1e-12 else float("inf")
    if scale > 1e-12:
        rel_mae_percent = 100.0 * mae / scale

    ss_res = float(np.sum(err * err))
    centered = np.asarray(y_true, dtype=float) - float(np.mean(y_true))
    ss_tot = float(np.sum(centered * centered))
    if ss_tot <= 1e-12:
        r2 = 1.0 if ss_res <= 1e-12 else float("-inf")
    else:
        r2 = 1.0 - ss_res / ss_tot
    return {"mae": mae, "rel_mae_percent": rel_mae_percent, "r2": r2}


def evaluate_gate(
    settings: Any,
    *,
    target_names: List[str],
    y_true: Any,
    y_pred: Any,
) -> Dict[str, Any]:
    """Evaluate the post-training validation gate for native surrogate models.

    The gate is intentionally fail-closed.  Missing target coverage, empty
    holdouts, non-finite predictions, or metrics below the configured threshold
    block automatic eligibility instead of promoting an unsafe surrogate.
    """

    gate_cfg = getattr(getattr(settings, "learning", None), "validation_gate", None)
    if gate_cfg is not None and not bool(getattr(gate_cfg, "enabled", True)):
        return {
            "eligible": True,
            "reason": "gate_disabled",
            "pass_share": 1.0,
            "target_metrics": {},
            "failed_targets": [],
            "failed_critical_targets": [],
            "failed_secondary_targets": [],
        }

    names = [str(name) for name in (target_names or [])]
    truth = np.asarray(y_true, dtype=float)
    pred = np.asarray(y_pred, dtype=float)
    if truth.ndim == 1:
        truth = truth.reshape(-1, 1)
    if pred.ndim == 1:
        pred = pred.reshape(-1, 1)

    if not names:
        return _blocked("insufficient_target_coverage", "No target names were provided.")
    if truth.shape != pred.shape or truth.ndim != 2:
        return _blocked(
            "shape_mismatch",
            f"y_true shape {truth.shape} does not match y_pred shape {pred.shape}.",
        )
    if truth.shape[0] == 0:
        return _blocked("empty_holdout", "No holdout rows are available for validation.")
    if truth.shape[1] != len(names):
        return _blocked(
            "shape_mismatch",
            f"Target count {len(names)} does not match holdout width {truth.shape[1]}.",
        )
    if np.any(~np.isfinite(truth)):
        return _blocked("nonfinite_truth", "Holdout truth contains non-finite values.")
    if np.any(~np.isfinite(pred)):
        return _blocked("nonfinite_predictions", "Holdout predictions contain non-finite values.")

    critical_targets = set(str(x) for x in getattr(gate_cfg, "critical_targets", []) or [])
    available = set(names)
    missing_critical = sorted(critical_targets - available)
    if bool(getattr(gate_cfg, "require_full_target_coverage", True)) and missing_critical:
        return {
            **_blocked(
                "insufficient_target_coverage",
                "Critical validation targets are missing from the trained target set.",
            ),
            "missing_critical_targets": missing_critical,
        }

    critical_min_r2 = float(getattr(gate_cfg, "critical_target_min_r2", 0.95))
    critical_max_rel_mae = float(getattr(gate_cfg, "critical_target_max_rel_mae_percent", 8.0))
    secondary_min_r2 = float(getattr(gate_cfg, "secondary_target_min_r2", 0.85))
    secondary_max_rel_mae = float(getattr(gate_cfg, "secondary_target_max_rel_mae_percent", 15.0))

    target_metrics: Dict[str, Dict[str, float | bool | str]] = {}
    failed_targets: List[str] = []
    failed_critical: List[str] = []
    failed_secondary: List[str] = []
    passed_count = 0

    for idx, name in enumerate(names):
        metrics = _target_metrics(truth[:, idx], pred[:, idx])
        is_critical = name in critical_targets
        min_r2 = critical_min_r2 if is_critical else secondary_min_r2
        max_rel_mae = critical_max_rel_mae if is_critical else secondary_max_rel_mae
        passed = bool(metrics["r2"] >= min_r2 and metrics["rel_mae_percent"] <= max_rel_mae)
        passed_count += int(passed)
        target_metrics[name] = {
            **metrics,
            "critical": is_critical,
            "passed": passed,
            "min_r2": min_r2,
            "max_rel_mae_percent": max_rel_mae,
        }
        if not passed:
            failed_targets.append(name)
            if is_critical:
                failed_critical.append(name)
            else:
                failed_secondary.append(name)

    pass_share = passed_count / len(names)
    min_pass_share = float(getattr(gate_cfg, "min_pass_share", 0.9))
    eligible = not failed_critical and pass_share >= min_pass_share
    reason = "eligible" if eligible else "metrics_below_threshold"
    return {
        "eligible": eligible,
        "reason": reason,
        "pass_share": float(pass_share),
        "min_pass_share": min_pass_share,
        "target_metrics": target_metrics,
        "failed_targets": failed_targets,
        "failed_critical_targets": failed_critical,
        "failed_secondary_targets": failed_secondary,
        "missing_critical_targets": [],
    }


def _blocked(reason: str, message: str) -> Dict[str, Any]:
    return {
        "eligible": False,
        "reason": reason,
        "message": message,
        "pass_share": 0.0,
        "target_metrics": {},
        "failed_targets": [],
        "failed_critical_targets": [],
        "failed_secondary_targets": [],
        "missing_critical_targets": [],
    }
