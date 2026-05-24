from __future__ import annotations

from typing import Any, Dict, List

import numpy as np


def _as_2d_float_matrix(values: Any, *, name: str) -> np.ndarray:
    arr = np.asarray(values, dtype=float)
    if arr.ndim == 1:
        arr = arr.reshape(-1, 1)
    if arr.ndim != 2:
        raise ValueError(f"[learning.validation] {name} must be a 2D numeric matrix.")
    return arr


def _r2_score(y_true: np.ndarray, y_pred: np.ndarray) -> float:
    residual = float(np.sum(np.square(y_true - y_pred)))
    centered = float(np.sum(np.square(y_true - float(np.mean(y_true)))))
    if centered <= 1e-12:
        return float("nan")
    return float(1.0 - residual / centered)


def _target_metrics(y_true: np.ndarray, y_pred: np.ndarray) -> Dict[str, float]:
    diff = y_true - y_pred
    mae = float(np.mean(np.abs(diff)))
    rmse = float(np.sqrt(np.mean(np.square(diff))))
    denom = float(np.mean(np.abs(y_true)))
    rel_mae = float(mae / denom * 100.0) if denom > 1e-12 else float("nan")
    return {
        "r2": _r2_score(y_true, y_pred),
        "rmse": rmse,
        "mae": mae,
        "rel_mae_percent": rel_mae,
    }


def _metric_is_finite(value: float) -> bool:
    return bool(np.isfinite(float(value)))


def _passes_thresholds(
    metrics: Dict[str, float],
    *,
    min_r2: float,
    max_rel_mae_percent: float,
) -> tuple[bool, List[str]]:
    failures: List[str] = []
    r2 = float(metrics["r2"])
    rel_mae = float(metrics["rel_mae_percent"])
    mae = float(metrics["mae"])

    if _metric_is_finite(r2) and r2 < min_r2:
        failures.append(f"r2_below_{min_r2:g}")
    if _metric_is_finite(rel_mae) and rel_mae > max_rel_mae_percent:
        failures.append(f"rel_mae_above_{max_rel_mae_percent:g}")

    # Constant zero targets make both R2 and relative MAE undefined. Those targets
    # are safe only when the model reproduces them exactly; otherwise the gate
    # must block instead of treating NaN metrics as a pass.
    if not _metric_is_finite(r2) and not _metric_is_finite(rel_mae) and mae > 1e-9:
        failures.append("constant_target_nonzero_error")

    return len(failures) == 0, failures


def evaluate_gate(
    settings: Any,
    *,
    target_names: List[str],
    y_true: Any,
    y_pred: Any,
) -> Dict[str, Any]:
    """Evaluate whether a retrained native surrogate may become optimization-eligible."""

    gate_cfg = getattr(getattr(settings, "learning", None), "validation_gate", None)
    enabled = bool(getattr(gate_cfg, "enabled", True)) if gate_cfg is not None else True

    targets = [str(target) for target in list(target_names or [])]
    y_true_arr = _as_2d_float_matrix(y_true, name="y_true")
    y_pred_arr = _as_2d_float_matrix(y_pred, name="y_pred")

    base_result: Dict[str, Any] = {
        "enabled": enabled,
        "eligible": False,
        "reason": "not_evaluated",
        "targets": targets,
        "n_targets": int(len(targets)),
        "n_samples": int(y_true_arr.shape[0]),
        "failed_targets": [],
        "failed_critical_targets": [],
        "failed_secondary_targets": [],
        "passed_targets": [],
        "pass_share": 0.0,
        "target_results": {},
    }

    if not enabled:
        base_result.update(
            {
                "eligible": True,
                "reason": "validation_gate_disabled",
                "pass_share": 1.0,
                "passed_targets": targets,
            }
        )
        return base_result

    if y_true_arr.shape != y_pred_arr.shape:
        base_result["reason"] = "shape_mismatch"
        base_result["shape_true"] = list(y_true_arr.shape)
        base_result["shape_pred"] = list(y_pred_arr.shape)
        return base_result

    if len(targets) != int(y_true_arr.shape[1]):
        base_result["reason"] = "insufficient_target_coverage"
        base_result["target_count"] = int(len(targets))
        base_result["matrix_columns"] = int(y_true_arr.shape[1])
        return base_result

    if not targets:
        base_result["reason"] = "no_targets"
        return base_result

    if y_true_arr.shape[0] == 0:
        base_result["reason"] = "no_holdout_samples"
        return base_result

    fail_on_nan = bool(getattr(gate_cfg, "fail_on_nan_predictions", True))
    if fail_on_nan and (not np.all(np.isfinite(y_true_arr)) or not np.all(np.isfinite(y_pred_arr))):
        base_result["reason"] = "nonfinite_values"
        return base_result

    critical_targets = {
        str(target)
        for target in list(getattr(gate_cfg, "critical_targets", []) or [])
    }
    min_pass_share = float(getattr(gate_cfg, "min_pass_share", 0.9))
    critical_min_r2 = float(getattr(gate_cfg, "critical_target_min_r2", 0.95))
    critical_max_rel = float(getattr(gate_cfg, "critical_target_max_rel_mae_percent", 8.0))
    secondary_min_r2 = float(getattr(gate_cfg, "secondary_target_min_r2", 0.85))
    secondary_max_rel = float(getattr(gate_cfg, "secondary_target_max_rel_mae_percent", 15.0))

    passed_targets: List[str] = []
    failed_targets: List[str] = []
    failed_critical: List[str] = []
    failed_secondary: List[str] = []
    target_results: Dict[str, Dict[str, Any]] = {}

    for col_idx, target in enumerate(targets):
        is_critical = target in critical_targets
        metrics = _target_metrics(y_true_arr[:, col_idx], y_pred_arr[:, col_idx])
        passed, failures = _passes_thresholds(
            metrics,
            min_r2=critical_min_r2 if is_critical else secondary_min_r2,
            max_rel_mae_percent=critical_max_rel if is_critical else secondary_max_rel,
        )
        target_results[target] = {
            "critical": bool(is_critical),
            "passed": bool(passed),
            "failures": failures,
            **metrics,
        }
        if passed:
            passed_targets.append(target)
        else:
            failed_targets.append(target)
            if is_critical:
                failed_critical.append(target)
            else:
                failed_secondary.append(target)

    pass_share = float(len(passed_targets) / len(targets))
    eligible = pass_share >= min_pass_share and not failed_critical
    base_result.update(
        {
            "eligible": bool(eligible),
            "reason": "ok" if eligible else "metrics_below_threshold",
            "failed_targets": failed_targets,
            "failed_critical_targets": failed_critical,
            "failed_secondary_targets": failed_secondary,
            "passed_targets": passed_targets,
            "pass_share": pass_share,
            "target_results": target_results,
            "thresholds": {
                "min_pass_share": min_pass_share,
                "critical_target_min_r2": critical_min_r2,
                "critical_target_max_rel_mae_percent": critical_max_rel,
                "secondary_target_min_r2": secondary_min_r2,
                "secondary_target_max_rel_mae_percent": secondary_max_rel,
            },
        }
    )
    return base_result
