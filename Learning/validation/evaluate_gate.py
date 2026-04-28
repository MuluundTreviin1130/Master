from __future__ import annotations

from typing import Any, Dict, Iterable, List

import numpy as np


def _as_2d_float(name: str, value: Any) -> np.ndarray:
    arr = np.asarray(value, dtype=float)
    if arr.ndim != 2:
        raise ValueError(f"[validation_gate] {name} must be a 2D array, got shape {arr.shape}.")
    return arr


def _safe_r2(y_true: np.ndarray, y_pred: np.ndarray) -> float:
    residual = float(np.sum((y_true - y_pred) ** 2))
    centered = float(np.sum((y_true - float(np.mean(y_true))) ** 2))
    if centered <= 0.0:
        return 1.0 if residual <= 0.0 else 0.0
    return float(1.0 - residual / centered)


def _relative_mae_percent(y_true: np.ndarray, y_pred: np.ndarray) -> float:
    mae = float(np.mean(np.abs(y_true - y_pred)))
    scale = float(np.mean(np.abs(y_true)))
    if scale <= 0.0:
        return 0.0 if mae <= 0.0 else float("inf")
    return float(100.0 * mae / scale)


def _target_set(values: Iterable[str]) -> set[str]:
    return {str(value) for value in values}


def evaluate_gate(
    settings: Any,
    *,
    target_names: List[str],
    y_true: Any,
    y_pred: Any,
) -> Dict[str, Any]:
    """Evaluate retrained surrogate holdout predictions against settings thresholds.

    The training pipeline imports this module on the normal SurrogateEngine path,
    so the gate must be a real fail-fast implementation rather than an optional
    placeholder.  It uses only the explicit `settings.learning.validation_gate`
    thresholds and returns the fields consumed by retrain remediation logic.
    """

    names = [str(name) for name in target_names]
    true_arr = _as_2d_float("y_true", y_true)
    pred_arr = _as_2d_float("y_pred", y_pred)
    if true_arr.shape != pred_arr.shape:
        raise ValueError(
            "[validation_gate] y_true/y_pred shape mismatch: "
            f"{true_arr.shape} vs {pred_arr.shape}."
        )
    if true_arr.shape[1] != len(names):
        raise ValueError(
            "[validation_gate] target_names length does not match prediction width: "
            f"{len(names)} vs {true_arr.shape[1]}."
        )

    gate_cfg = getattr(getattr(settings, "learning", None), "validation_gate", None)
    if gate_cfg is None:
        raise ValueError("[validation_gate] settings.learning.validation_gate is missing.")

    if not bool(getattr(gate_cfg, "enabled", True)):
        return {
            "eligible": True,
            "reason": "disabled",
            "pass_share": 1.0,
            "target_results": [],
            "failed_targets": [],
            "failed_critical_targets": [],
            "failed_secondary_targets": [],
        }

    if bool(getattr(gate_cfg, "fail_on_nan_predictions", True)):
        if not np.all(np.isfinite(true_arr)) or not np.all(np.isfinite(pred_arr)):
            return {
                "eligible": False,
                "reason": "non_finite_values",
                "pass_share": 0.0,
                "target_results": [],
                "failed_targets": list(names),
                "failed_critical_targets": list(names),
                "failed_secondary_targets": [],
            }

    critical_targets = _target_set(getattr(gate_cfg, "critical_targets", []) or [])
    require_full_coverage = bool(getattr(gate_cfg, "require_full_target_coverage", True))
    if require_full_coverage:
        missing_critical = sorted(critical_targets.difference(names))
        if missing_critical:
            return {
                "eligible": False,
                "reason": "insufficient_target_coverage",
                "pass_share": 0.0,
                "target_results": [],
                "failed_targets": missing_critical,
                "failed_critical_targets": missing_critical,
                "failed_secondary_targets": [],
            }

    target_results: List[Dict[str, Any]] = []
    failed_targets: List[str] = []
    failed_critical: List[str] = []
    failed_secondary: List[str] = []
    for idx, name in enumerate(names):
        is_critical = name in critical_targets
        min_r2 = float(
            getattr(
                gate_cfg,
                "critical_target_min_r2" if is_critical else "secondary_target_min_r2",
                0.0,
            )
        )
        max_rel_mae = float(
            getattr(
                gate_cfg,
                "critical_target_max_rel_mae_percent"
                if is_critical
                else "secondary_target_max_rel_mae_percent",
                float("inf"),
            )
        )
        r2 = _safe_r2(true_arr[:, idx], pred_arr[:, idx])
        rel_mae_percent = _relative_mae_percent(true_arr[:, idx], pred_arr[:, idx])
        passed = bool(r2 >= min_r2 and rel_mae_percent <= max_rel_mae)
        row = {
            "target": name,
            "critical": is_critical,
            "r2": r2,
            "relative_mae_percent": rel_mae_percent,
            "min_r2": min_r2,
            "max_relative_mae_percent": max_rel_mae,
            "passed": passed,
        }
        target_results.append(row)
        if not passed:
            failed_targets.append(name)
            if is_critical:
                failed_critical.append(name)
            else:
                failed_secondary.append(name)

    pass_share = float(
        sum(1 for row in target_results if bool(row["passed"])) / len(target_results)
        if target_results
        else 0.0
    )
    min_pass_share = float(getattr(gate_cfg, "min_pass_share", 0.0))
    eligible = not failed_critical and pass_share >= min_pass_share
    return {
        "eligible": bool(eligible),
        "reason": "passed" if eligible else "metrics_below_threshold",
        "pass_share": pass_share,
        "target_results": target_results,
        "failed_targets": failed_targets,
        "failed_critical_targets": failed_critical,
        "failed_secondary_targets": failed_secondary,
    }
