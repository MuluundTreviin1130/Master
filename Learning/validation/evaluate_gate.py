from __future__ import annotations

from typing import Any, Dict, List

import numpy as np


def _as_2d_float_array(name: str, value: Any) -> np.ndarray:
    """Normalize gate inputs while rejecting ambiguous array shapes."""
    arr = np.asarray(value, dtype=float)
    if arr.ndim == 1:
        arr = arr.reshape(-1, 1)
    if arr.ndim != 2:
        raise ValueError(f"[validation_gate] {name} must be a 1D or 2D numeric array, got shape={arr.shape}.")
    return arr


def _target_metrics(y_true: np.ndarray, y_pred: np.ndarray) -> Dict[str, float]:
    """Compute deterministic per-target metrics without depending on sklearn internals."""
    residual = y_true - y_pred
    mae = float(np.mean(np.abs(residual)))
    scale = float(np.mean(np.abs(y_true)))
    rel_mae_percent = 0.0 if scale <= 1e-12 and mae <= 1e-12 else float(100.0 * mae / max(scale, 1e-12))
    ss_res = float(np.sum(residual * residual))
    centered = y_true - float(np.mean(y_true))
    ss_tot = float(np.sum(centered * centered))
    r2 = 1.0 if ss_tot <= 1e-12 and ss_res <= 1e-12 else float(1.0 - ss_res / max(ss_tot, 1e-12))
    return {
        "mae": mae,
        "rel_mae_percent": rel_mae_percent,
        "r2": r2,
    }


def evaluate_gate(
    settings: Any,
    *,
    target_names: List[str],
    y_true: Any,
    y_pred: Any,
) -> Dict[str, Any]:
    """
    Evaluate the native retrain holdout before registry status is promoted.

    The gate mirrors the SSOT thresholds in ``Settings.learning.ValidationGateConfig``.
    It returns a structured result for remediation policy; malformed inputs still
    raise immediately because they indicate a broken training pipeline, not a
    model-quality failure that can be remediated with more samples.
    """
    gate_cfg = getattr(getattr(settings, "learning", None), "validation_gate", None)
    if gate_cfg is None:
        raise RuntimeError("[validation_gate] settings.learning.validation_gate is required for native retrain.")

    names = [str(name) for name in list(target_names or [])]
    if len(names) != len(set(names)):
        raise ValueError(f"[validation_gate] target_names contains duplicates: {names}.")
    if not names:
        raise ValueError("[validation_gate] target_names must not be empty.")

    true_arr = _as_2d_float_array("y_true", y_true)
    pred_arr = _as_2d_float_array("y_pred", y_pred)
    if true_arr.shape != pred_arr.shape:
        raise ValueError(
            f"[validation_gate] y_true and y_pred shape mismatch: {true_arr.shape} != {pred_arr.shape}."
        )

    enabled = bool(getattr(gate_cfg, "enabled", True))
    if not enabled:
        return {
            "eligible": True,
            "reason": "gate_disabled",
            "pass_share": 1.0,
            "target_metrics": {},
            "failed_targets": [],
            "failed_critical_targets": [],
            "failed_secondary_targets": [],
        }

    if true_arr.shape[0] == 0:
        return {
            "eligible": False,
            "reason": "insufficient_holdout_rows",
            "pass_share": 0.0,
            "target_metrics": {},
            "failed_targets": names,
            "failed_critical_targets": [name for name in names if name in set(getattr(gate_cfg, "critical_targets", []) or [])],
            "failed_secondary_targets": [name for name in names if name not in set(getattr(gate_cfg, "critical_targets", []) or [])],
        }
    if bool(getattr(gate_cfg, "require_full_target_coverage", True)) and true_arr.shape[1] != len(names):
        return {
            "eligible": False,
            "reason": "insufficient_target_coverage",
            "pass_share": 0.0,
            "target_metrics": {},
            "failed_targets": names,
            "failed_critical_targets": [name for name in names if name in set(getattr(gate_cfg, "critical_targets", []) or [])],
            "failed_secondary_targets": [name for name in names if name not in set(getattr(gate_cfg, "critical_targets", []) or [])],
        }
    if true_arr.shape[1] != len(names):
        raise ValueError(
            f"[validation_gate] target_names length {len(names)} does not match holdout columns {true_arr.shape[1]}."
        )

    finite_true = np.isfinite(true_arr)
    finite_pred = np.isfinite(pred_arr)
    if not bool(finite_true.all()):
        raise ValueError("[validation_gate] y_true contains non-finite values from the teacher dataset.")
    if bool(getattr(gate_cfg, "fail_on_nan_predictions", True)) and not bool(finite_pred.all()):
        non_finite_targets = [names[j] for j in range(pred_arr.shape[1]) if not bool(finite_pred[:, j].all())]
        return {
            "eligible": False,
            "reason": "nan_predictions",
            "pass_share": 0.0,
            "target_metrics": {},
            "failed_targets": non_finite_targets,
            "failed_critical_targets": [name for name in non_finite_targets if name in set(getattr(gate_cfg, "critical_targets", []) or [])],
            "failed_secondary_targets": [name for name in non_finite_targets if name not in set(getattr(gate_cfg, "critical_targets", []) or [])],
        }

    critical_targets = {str(name) for name in list(getattr(gate_cfg, "critical_targets", []) or [])}
    critical_min_r2 = float(getattr(gate_cfg, "critical_target_min_r2", 0.95))
    critical_max_rel_mae = float(getattr(gate_cfg, "critical_target_max_rel_mae_percent", 8.0))
    secondary_min_r2 = float(getattr(gate_cfg, "secondary_target_min_r2", 0.85))
    secondary_max_rel_mae = float(getattr(gate_cfg, "secondary_target_max_rel_mae_percent", 15.0))

    target_metrics: Dict[str, Dict[str, float | bool | str]] = {}
    failed_targets: List[str] = []
    failed_critical: List[str] = []
    failed_secondary: List[str] = []

    for idx, name in enumerate(names):
        metrics = _target_metrics(true_arr[:, idx], pred_arr[:, idx])
        is_critical = name in critical_targets
        min_r2 = critical_min_r2 if is_critical else secondary_min_r2
        max_rel_mae = critical_max_rel_mae if is_critical else secondary_max_rel_mae
        passed = metrics["r2"] >= min_r2 and metrics["rel_mae_percent"] <= max_rel_mae
        target_metrics[name] = {
            **metrics,
            "critical": bool(is_critical),
            "passed": bool(passed),
            "min_r2": float(min_r2),
            "max_rel_mae_percent": float(max_rel_mae),
        }
        if passed:
            continue
        failed_targets.append(name)
        if is_critical:
            failed_critical.append(name)
        else:
            failed_secondary.append(name)

    pass_share = float((len(names) - len(failed_targets)) / len(names))
    eligible = pass_share >= float(getattr(gate_cfg, "min_pass_share", 0.9)) and not failed_critical
    reason = "passed" if eligible else "metrics_below_threshold"
    return {
        "eligible": bool(eligible),
        "reason": reason,
        "pass_share": pass_share,
        "target_metrics": target_metrics,
        "failed_targets": failed_targets,
        "failed_critical_targets": failed_critical,
        "failed_secondary_targets": failed_secondary,
    }
