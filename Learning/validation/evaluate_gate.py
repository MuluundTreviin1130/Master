from __future__ import annotations

from typing import Any, Dict, List

import numpy as np


def _r2_score(y_true: np.ndarray, y_pred: np.ndarray) -> float:
    y_true = np.asarray(y_true, dtype=float).reshape(-1)
    y_pred = np.asarray(y_pred, dtype=float).reshape(-1)
    if y_true.size == 0 or float(np.std(y_true)) <= 1e-12:
        return float("nan")
    ss_res = float(np.sum((y_true - y_pred) ** 2))
    ss_tot = float(np.sum((y_true - float(np.mean(y_true))) ** 2))
    return float("nan") if ss_tot <= 1e-12 else float(1.0 - ss_res / ss_tot)


def _target_metrics(y_true: np.ndarray, y_pred: np.ndarray) -> Dict[str, float]:
    y_true = np.asarray(y_true, dtype=float).reshape(-1)
    y_pred = np.asarray(y_pred, dtype=float).reshape(-1)
    if y_true.size == 0:
        raise ValueError("[learning.validation] Holdout target arrays must contain at least one row.")
    diff = y_true - y_pred
    mae = float(np.mean(np.abs(diff)))
    rmse = float(np.sqrt(np.mean(diff * diff)))
    denom = float(np.mean(np.abs(y_true)))
    rel_mae_percent = float("nan") if denom <= 1e-12 else float(mae / denom * 100.0)
    return {
        "r2": _r2_score(y_true, y_pred),
        "rmse": rmse,
        "mae": mae,
        "rel_mae_percent": rel_mae_percent,
    }


def _normalise_holdout_arrays(y_true: Any, y_pred: Any, target_names: List[str]) -> tuple[np.ndarray, np.ndarray]:
    y_true_arr = np.asarray(y_true, dtype=float)
    y_pred_arr = np.asarray(y_pred, dtype=float)
    if y_true_arr.ndim == 1:
        y_true_arr = y_true_arr.reshape(-1, 1)
    if y_pred_arr.ndim == 1:
        y_pred_arr = y_pred_arr.reshape(-1, 1)
    if y_true_arr.shape != y_pred_arr.shape:
        raise ValueError(
            "[learning.validation] y_true and y_pred shape mismatch: "
            f"{y_true_arr.shape} != {y_pred_arr.shape}."
        )
    if y_true_arr.ndim != 2:
        raise ValueError("[learning.validation] y_true and y_pred must be 1D or 2D arrays.")
    if y_true_arr.shape[1] != len(target_names):
        raise ValueError(
            "[learning.validation] target_names length must match holdout columns: "
            f"{len(target_names)} != {y_true_arr.shape[1]}."
        )
    if y_true_arr.shape[0] == 0:
        raise ValueError("[learning.validation] Holdout arrays must contain at least one sample.")
    return y_true_arr, y_pred_arr


def _passes_metric_gate(
    *,
    metrics: Dict[str, float],
    is_critical: bool,
    gate_cfg: Any,
    y_true_col: np.ndarray,
) -> tuple[bool, List[str]]:
    reasons: List[str] = []
    min_r2 = float(
        getattr(
            gate_cfg,
            "critical_target_min_r2" if is_critical else "secondary_target_min_r2",
        )
    )
    max_rel_mae = float(
        getattr(
            gate_cfg,
            "critical_target_max_rel_mae_percent" if is_critical else "secondary_target_max_rel_mae_percent",
        )
    )
    r2 = float(metrics["r2"])
    rel_mae = float(metrics["rel_mae_percent"])
    mae = float(metrics["mae"])

    # Constant targets have undefined R2. In that case, exact or near-exact MAE
    # carries the gate because an R2 threshold would reject perfect constants.
    if np.isfinite(r2) and r2 < min_r2:
        reasons.append(f"r2_below_{min_r2:g}")
    if np.isfinite(rel_mae):
        if rel_mae > max_rel_mae:
            reasons.append(f"rel_mae_above_{max_rel_mae:g}_percent")
    else:
        mean_abs = float(np.mean(np.abs(np.asarray(y_true_col, dtype=float).reshape(-1))))
        if mean_abs <= 1e-12 and mae > 1e-9:
            reasons.append("absolute_mae_nonzero_for_zero_target")
        elif mean_abs > 1e-12:
            reasons.append("rel_mae_not_finite")
    return not reasons, reasons


def evaluate_gate(
    settings: Any,
    *,
    target_names: List[str],
    y_true: Any,
    y_pred: Any,
) -> Dict[str, Any]:
    """Evaluate whether a freshly trained surrogate can be used for optimization."""

    gate_cfg = getattr(getattr(settings, "learning", None), "validation_gate", None)
    if gate_cfg is None:
        raise AttributeError("[learning.validation] settings.learning.validation_gate is required.")
    if not bool(getattr(gate_cfg, "enabled", True)):
        return {
            "eligible": True,
            "enabled": False,
            "reason": "validation_gate_disabled",
            "target_results": [],
            "failed_targets": [],
            "failed_critical_targets": [],
            "failed_secondary_targets": [],
            "pass_share": 1.0,
        }

    targets = [str(name) for name in target_names]
    y_true_arr, y_pred_arr = _normalise_holdout_arrays(y_true, y_pred, targets)
    nonfinite_predictions = ~np.isfinite(y_pred_arr)
    nonfinite_truth = ~np.isfinite(y_true_arr)
    fail_on_nan = bool(getattr(gate_cfg, "fail_on_nan_predictions", True))
    critical_targets = {str(name) for name in getattr(gate_cfg, "critical_targets", [])}

    target_results: List[Dict[str, Any]] = []
    failed_targets: List[str] = []
    failed_critical: List[str] = []
    failed_secondary: List[str] = []
    passed_count = 0

    for idx, target in enumerate(targets):
        is_critical = target in critical_targets
        reasons: List[str] = []
        if np.any(nonfinite_truth[:, idx]):
            reasons.append("nonfinite_truth")
        if fail_on_nan and np.any(nonfinite_predictions[:, idx]):
            reasons.append("nonfinite_prediction")
        if reasons:
            metrics = {"r2": float("nan"), "rmse": float("nan"), "mae": float("nan"), "rel_mae_percent": float("nan")}
            passed = False
        else:
            metrics = _target_metrics(y_true_arr[:, idx], y_pred_arr[:, idx])
            passed, metric_reasons = _passes_metric_gate(
                metrics=metrics,
                is_critical=is_critical,
                gate_cfg=gate_cfg,
                y_true_col=y_true_arr[:, idx],
            )
            reasons.extend(metric_reasons)
        if passed:
            passed_count += 1
        else:
            failed_targets.append(target)
            if is_critical:
                failed_critical.append(target)
            else:
                failed_secondary.append(target)
        target_results.append(
            {
                "target": target,
                "is_critical": bool(is_critical),
                "passed": bool(passed),
                "reasons": reasons,
                **metrics,
            }
        )

    pass_share = float(passed_count / len(targets)) if targets else 0.0
    min_pass_share = float(getattr(gate_cfg, "min_pass_share", 1.0))
    eligible = pass_share >= min_pass_share and not failed_critical
    if bool(getattr(gate_cfg, "require_full_target_coverage", True)) and failed_targets:
        eligible = False

    return {
        "eligible": bool(eligible),
        "enabled": True,
        "pass_share": pass_share,
        "min_pass_share": min_pass_share,
        "failed_targets": failed_targets,
        "failed_critical_targets": failed_critical,
        "failed_secondary_targets": failed_secondary,
        "target_results": target_results,
        "thresholds": {
            "critical_target_min_r2": float(getattr(gate_cfg, "critical_target_min_r2")),
            "critical_target_max_rel_mae_percent": float(getattr(gate_cfg, "critical_target_max_rel_mae_percent")),
            "secondary_target_min_r2": float(getattr(gate_cfg, "secondary_target_min_r2")),
            "secondary_target_max_rel_mae_percent": float(getattr(gate_cfg, "secondary_target_max_rel_mae_percent")),
        },
    }
