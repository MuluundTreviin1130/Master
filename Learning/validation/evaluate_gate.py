from __future__ import annotations

from typing import Any, Dict, List

import numpy as np


def _as_2d_float_array(name: str, value: Any) -> np.ndarray:
    arr = np.asarray(value, dtype=float)
    if arr.ndim != 2:
        raise ValueError(f"[validation_gate] {name} must be a 2D array, got shape {arr.shape}.")
    return arr


def _safe_r2(y_true: np.ndarray, y_pred: np.ndarray) -> float:
    residual_sum = float(np.sum((y_true - y_pred) ** 2))
    total_sum = float(np.sum((y_true - float(np.mean(y_true))) ** 2))
    if total_sum <= 0.0:
        return 1.0 if residual_sum <= 0.0 else float("-inf")
    return 1.0 - residual_sum / total_sum


def _relative_mae_percent(y_true: np.ndarray, y_pred: np.ndarray) -> float:
    mae = float(np.mean(np.abs(y_true - y_pred)))
    scale = float(np.mean(np.abs(y_true)))
    if scale <= 0.0:
        return 0.0 if mae <= 0.0 else float("inf")
    return 100.0 * mae / scale


def evaluate_gate(
    settings: Any,
    *,
    target_names: List[str],
    y_true: Any,
    y_pred: Any,
) -> Dict[str, Any]:
    gate_cfg = getattr(getattr(settings, "learning", None), "validation_gate", None)
    if gate_cfg is None:
        raise TypeError("[validation_gate] settings.learning.validation_gate is required.")

    target_names = [str(target).strip() for target in target_names if str(target).strip()]
    if not target_names:
        raise ValueError("[validation_gate] target_names must not be empty.")

    y_true_arr = _as_2d_float_array("y_true", y_true)
    y_pred_arr = _as_2d_float_array("y_pred", y_pred)
    if y_true_arr.shape != y_pred_arr.shape:
        raise ValueError(
            f"[validation_gate] y_true shape {y_true_arr.shape} does not match y_pred shape {y_pred_arr.shape}."
        )
    if y_true_arr.shape[1] != len(target_names):
        raise ValueError(
            f"[validation_gate] target_names has {len(target_names)} entries, "
            f"but arrays contain {y_true_arr.shape[1]} target columns."
        )

    required_critical = [str(t) for t in list(getattr(gate_cfg, "critical_targets", []) or [])]
    covered_targets = set(target_names)
    missing_critical = [target for target in required_critical if target not in covered_targets]
    require_full_coverage = bool(getattr(gate_cfg, "require_full_target_coverage", True))

    nan_targets: List[str] = []
    if bool(getattr(gate_cfg, "fail_on_nan_predictions", True)):
        for idx, target in enumerate(target_names):
            if not np.all(np.isfinite(y_pred_arr[:, idx])):
                nan_targets.append(target)

    critical_targets = set(required_critical) & covered_targets
    critical_min_r2 = float(getattr(gate_cfg, "critical_target_min_r2", 0.95))
    critical_max_rel_mae = float(getattr(gate_cfg, "critical_target_max_rel_mae_percent", 8.0))
    secondary_min_r2 = float(getattr(gate_cfg, "secondary_target_min_r2", 0.85))
    secondary_max_rel_mae = float(getattr(gate_cfg, "secondary_target_max_rel_mae_percent", 15.0))

    target_results: Dict[str, Dict[str, Any]] = {}
    failed_targets: List[str] = []
    failed_critical_targets: List[str] = []
    failed_secondary_targets: List[str] = []
    passed_targets = 0

    for idx, target in enumerate(target_names):
        is_critical = target in critical_targets
        min_r2 = critical_min_r2 if is_critical else secondary_min_r2
        max_rel_mae = critical_max_rel_mae if is_critical else secondary_max_rel_mae
        has_nan = target in nan_targets
        if has_nan:
            r2 = float("-inf")
            rel_mae_percent = float("inf")
        else:
            r2 = _safe_r2(y_true_arr[:, idx], y_pred_arr[:, idx])
            rel_mae_percent = _relative_mae_percent(y_true_arr[:, idx], y_pred_arr[:, idx])
        passed = (not has_nan) and r2 >= min_r2 and rel_mae_percent <= max_rel_mae
        if passed:
            passed_targets += 1
        else:
            failed_targets.append(target)
            if is_critical:
                failed_critical_targets.append(target)
            else:
                failed_secondary_targets.append(target)
        target_results[target] = {
            "r2": float(r2),
            "rel_mae_percent": float(rel_mae_percent),
            "min_r2": float(min_r2),
            "max_rel_mae_percent": float(max_rel_mae),
            "critical": bool(is_critical),
            "passed": bool(passed),
            "has_nan_prediction": bool(has_nan),
        }

    pass_share = float(passed_targets / len(target_names))
    min_pass_share = float(getattr(gate_cfg, "min_pass_share", 0.9))
    enabled = bool(getattr(gate_cfg, "enabled", True))

    if not enabled:
        eligible = True
        reason = "gate_disabled"
    elif require_full_coverage and missing_critical:
        eligible = False
        reason = "insufficient_target_coverage"
    elif nan_targets:
        eligible = False
        reason = "nan_predictions"
    elif failed_critical_targets or pass_share < min_pass_share:
        eligible = False
        reason = "metrics_below_threshold"
    else:
        eligible = True
        reason = "eligible"

    return {
        "enabled": enabled,
        "eligible": bool(eligible),
        "reason": reason,
        "n_targets": int(len(target_names)),
        "n_passed_targets": int(passed_targets),
        "pass_share": pass_share,
        "min_pass_share": min_pass_share,
        "missing_critical_targets": missing_critical,
        "failed_targets": failed_targets,
        "failed_critical_targets": failed_critical_targets,
        "failed_secondary_targets": failed_secondary_targets,
        "nan_targets": nan_targets,
        "target_results": target_results,
    }

