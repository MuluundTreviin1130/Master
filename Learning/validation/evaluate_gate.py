from __future__ import annotations

"""Holdout gate for native Learning surrogate retraining.

The gate is deliberately strict about malformed inputs because it decides
whether a freshly written native model is eligible for optimization use.
Thresholds come from ``settings.learning.validation_gate``; this module only
implements their evaluation.
"""

from typing import Any, Dict, List

import numpy as np


_EPS = 1.0e-12


def _json_float(value: float) -> float | None:
    """Keep registry JSON valid by replacing non-finite metrics with ``None``."""

    value_f = float(value)
    return value_f if np.isfinite(value_f) else None


def _r2_score(y_true: np.ndarray, y_pred: np.ndarray) -> float:
    """Compute R2 without adding another dependency to the validation module."""

    residual = y_true - y_pred
    ss_res = float(np.sum(residual * residual))
    centered = y_true - float(np.mean(y_true))
    ss_tot = float(np.sum(centered * centered))
    if ss_tot <= _EPS:
        return float("nan")
    return float(1.0 - ss_res / ss_tot)


def _rel_mae_percent(y_true: np.ndarray, y_pred: np.ndarray) -> float:
    """Return MAE relative to the mean absolute truth magnitude."""

    mae = float(np.mean(np.abs(y_true - y_pred)))
    denom = float(np.mean(np.abs(y_true)))
    if denom <= _EPS:
        return 0.0 if mae <= _EPS else float("inf")
    return float(mae / denom * 100.0)


def _blocked_result(reason: str, target_names: List[str], details: Dict[str, Any]) -> Dict[str, Any]:
    """Build a consistent non-eligible gate payload."""

    return {
        "enabled": True,
        "eligible": False,
        "reason": reason,
        "target_count": int(len(target_names)),
        "passed_targets": [],
        "failed_targets": list(target_names),
        "failed_critical_targets": list(details.get("failed_critical_targets", []) or []),
        "failed_secondary_targets": list(details.get("failed_secondary_targets", []) or []),
        "pass_share": 0.0,
        "metrics_by_target": {},
        "details": details,
    }


def evaluate_gate(
    settings: Any,
    *,
    target_names: List[str],
    y_true: Any,
    y_pred: Any,
) -> Dict[str, Any]:
    """Evaluate the configured validation gate for one holdout prediction matrix."""

    gate_cfg = getattr(getattr(settings, "learning", None), "validation_gate", None)
    names = [str(name) for name in list(target_names or [])]
    if gate_cfg is None:
        raise AttributeError("[validation_gate] settings.learning.validation_gate is missing.")
    if not bool(getattr(gate_cfg, "enabled", True)):
        return {
            "enabled": False,
            "eligible": True,
            "reason": "gate_disabled",
            "target_count": int(len(names)),
            "passed_targets": list(names),
            "failed_targets": [],
            "failed_critical_targets": [],
            "failed_secondary_targets": [],
            "pass_share": 1.0,
            "metrics_by_target": {},
            "details": {},
        }

    Y_true = np.asarray(y_true, dtype=float)
    Y_pred = np.asarray(y_pred, dtype=float)
    if Y_true.ndim != 2 or Y_pred.ndim != 2:
        return _blocked_result(
            "invalid_holdout_shape",
            names,
            {"y_true_shape": list(Y_true.shape), "y_pred_shape": list(Y_pred.shape)},
        )
    if Y_true.shape != Y_pred.shape:
        return _blocked_result(
            "invalid_holdout_shape",
            names,
            {"y_true_shape": list(Y_true.shape), "y_pred_shape": list(Y_pred.shape)},
        )
    if not names or int(Y_true.shape[1]) != len(names):
        return _blocked_result(
            "insufficient_target_coverage",
            names,
            {"target_count": int(len(names)), "holdout_width": int(Y_true.shape[1])},
        )
    if int(Y_true.shape[0]) == 0:
        return _blocked_result("empty_holdout", names, {"holdout_rows": 0})

    fail_on_nonfinite = bool(getattr(gate_cfg, "fail_on_nan_predictions", True))
    if fail_on_nonfinite and (not np.isfinite(Y_true).all() or not np.isfinite(Y_pred).all()):
        return _blocked_result(
            "non_finite_holdout_values",
            names,
            {
                "y_true_finite": bool(np.isfinite(Y_true).all()),
                "y_pred_finite": bool(np.isfinite(Y_pred).all()),
            },
        )

    critical_targets = {str(name) for name in list(getattr(gate_cfg, "critical_targets", []) or [])}
    critical_min_r2 = float(getattr(gate_cfg, "critical_target_min_r2", 0.95))
    critical_max_rel = float(getattr(gate_cfg, "critical_target_max_rel_mae_percent", 8.0))
    secondary_min_r2 = float(getattr(gate_cfg, "secondary_target_min_r2", 0.85))
    secondary_max_rel = float(getattr(gate_cfg, "secondary_target_max_rel_mae_percent", 15.0))

    passed: List[str] = []
    failed: List[str] = []
    failed_critical: List[str] = []
    failed_secondary: List[str] = []
    metrics_by_target: Dict[str, Dict[str, Any]] = {}

    for idx, target in enumerate(names):
        yt = Y_true[:, idx]
        yp = Y_pred[:, idx]
        r2 = _r2_score(yt, yp)
        rel_mae = _rel_mae_percent(yt, yp)
        mae = float(np.mean(np.abs(yt - yp)))
        is_critical = target in critical_targets
        min_r2 = critical_min_r2 if is_critical else secondary_min_r2
        max_rel = critical_max_rel if is_critical else secondary_max_rel
        r2_ok = True if not np.isfinite(r2) else bool(r2 >= min_r2)
        rel_ok = bool(np.isfinite(rel_mae) and rel_mae <= max_rel)
        target_passed = bool(r2_ok and rel_ok)
        metrics_by_target[target] = {
            "critical": bool(is_critical),
            "r2": _json_float(r2),
            "mae": _json_float(mae),
            "rel_mae_percent": _json_float(rel_mae),
            "min_r2": float(min_r2),
            "max_rel_mae_percent": float(max_rel),
            "passed": bool(target_passed),
        }
        if target_passed:
            passed.append(target)
            continue
        failed.append(target)
        if is_critical:
            failed_critical.append(target)
        else:
            failed_secondary.append(target)

    pass_share = float(len(passed) / len(names))
    required_share = float(getattr(gate_cfg, "min_pass_share", 0.9))
    eligible = bool(pass_share >= required_share and not failed_critical)
    reason = "ok" if eligible else "metrics_below_threshold"
    return {
        "enabled": True,
        "eligible": eligible,
        "reason": reason,
        "target_count": int(len(names)),
        "passed_targets": passed,
        "failed_targets": failed,
        "failed_critical_targets": failed_critical,
        "failed_secondary_targets": failed_secondary,
        "pass_share": pass_share,
        "metrics_by_target": metrics_by_target,
        "thresholds": {
            "min_pass_share": required_share,
            "critical_target_min_r2": critical_min_r2,
            "critical_target_max_rel_mae_percent": critical_max_rel,
            "secondary_target_min_r2": secondary_min_r2,
            "secondary_target_max_rel_mae_percent": secondary_max_rel,
        },
    }
