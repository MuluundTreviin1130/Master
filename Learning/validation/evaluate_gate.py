from __future__ import annotations

from typing import Any, Iterable

import numpy as np


def evaluate_gate(
    settings: Any,
    *,
    target_names: Iterable[str],
    y_true: np.ndarray,
    y_pred: np.ndarray,
) -> dict[str, Any]:
    """
    Evaluate the native surrogate validation gate against holdout predictions.

    The gate contract lives in `settings.learning.validation_gate`.  This
    function only scores the arrays it receives; it does not invent missing
    targets, coerce shapes, or silently accept non-finite predictions.
    """

    gate_cfg = getattr(getattr(settings, "learning", None), "validation_gate", None)
    if gate_cfg is None:
        raise AttributeError("[validation_gate] settings.learning.validation_gate is required.")

    targets = [str(name) for name in target_names]
    truth = np.asarray(y_true, dtype=float)
    pred = np.asarray(y_pred, dtype=float)
    if truth.ndim != 2 or pred.ndim != 2:
        raise ValueError("[validation_gate] y_true and y_pred must both be 2D arrays.")
    if truth.shape != pred.shape:
        raise ValueError(
            "[validation_gate] y_true and y_pred shape mismatch: "
            f"{truth.shape} != {pred.shape}."
        )
    if len(targets) != int(truth.shape[1]):
        raise ValueError(
            "[validation_gate] target_names length does not match prediction columns: "
            f"{len(targets)} != {truth.shape[1]}."
        )
    if truth.shape[0] == 0:
        raise ValueError("[validation_gate] holdout arrays must contain at least one row.")

    non_finite_truth = not bool(np.isfinite(truth).all())
    non_finite_pred = not bool(np.isfinite(pred).all())
    if non_finite_truth or non_finite_pred:
        if bool(getattr(gate_cfg, "fail_on_nan_predictions", True)):
            return {
                "enabled": bool(getattr(gate_cfg, "enabled", True)),
                "eligible": False,
                "reason": "non_finite_holdout_values",
                "non_finite_truth": non_finite_truth,
                "non_finite_predictions": non_finite_pred,
                "pass_share": 0.0,
                "failed_targets": targets,
                "failed_critical_targets": _critical_targets(gate_cfg, targets),
                "failed_secondary_targets": [
                    target for target in targets if target not in set(_critical_targets(gate_cfg, targets))
                ],
                "target_metrics": [],
            }
        raise ValueError("[validation_gate] non-finite holdout values are not allowed by this evaluator.")

    enabled = bool(getattr(gate_cfg, "enabled", True))
    if not enabled:
        return {
            "enabled": False,
            "eligible": True,
            "reason": "disabled",
            "pass_share": 1.0,
            "failed_targets": [],
            "failed_critical_targets": [],
            "failed_secondary_targets": [],
            "target_metrics": [],
        }

    critical = set(_critical_targets(gate_cfg, targets))
    target_metrics: list[dict[str, Any]] = []
    failed_targets: list[str] = []
    failed_critical: list[str] = []
    failed_secondary: list[str] = []

    for idx, target in enumerate(targets):
        target_truth = truth[:, idx]
        target_pred = pred[:, idx]
        is_critical = target in critical
        min_r2 = float(
            getattr(
                gate_cfg,
                "critical_target_min_r2" if is_critical else "secondary_target_min_r2",
                0.95 if is_critical else 0.85,
            )
        )
        max_rel_mae_percent = float(
            getattr(
                gate_cfg,
                (
                    "critical_target_max_rel_mae_percent"
                    if is_critical
                    else "secondary_target_max_rel_mae_percent"
                ),
                8.0 if is_critical else 15.0,
            )
        )
        r2 = _r2_score(target_truth, target_pred)
        mae = float(np.mean(np.abs(target_pred - target_truth)))
        rel_mae_percent = _relative_mae_percent(target_truth, mae)
        passed = bool(r2 >= min_r2 and rel_mae_percent <= max_rel_mae_percent)
        if not passed:
            failed_targets.append(target)
            if is_critical:
                failed_critical.append(target)
            else:
                failed_secondary.append(target)
        target_metrics.append(
            {
                "target": target,
                "critical": is_critical,
                "r2": float(r2),
                "mae": mae,
                "rel_mae_percent": float(rel_mae_percent),
                "min_r2": min_r2,
                "max_rel_mae_percent": max_rel_mae_percent,
                "passed": passed,
            }
        )

    passed_count = len(targets) - len(failed_targets)
    pass_share = float(passed_count / len(targets)) if targets else 0.0
    min_pass_share = float(getattr(gate_cfg, "min_pass_share", 0.9))
    full_coverage_required = bool(getattr(gate_cfg, "require_full_target_coverage", True))
    eligible = bool(pass_share >= min_pass_share and not failed_critical)
    if full_coverage_required and not targets:
        eligible = False
    reason = "passed" if eligible else "metrics_below_threshold"
    if full_coverage_required and not targets:
        reason = "insufficient_target_coverage"

    return {
        "enabled": True,
        "eligible": eligible,
        "reason": reason,
        "pass_share": pass_share,
        "min_pass_share": min_pass_share,
        "failed_targets": failed_targets,
        "failed_critical_targets": failed_critical,
        "failed_secondary_targets": failed_secondary,
        "target_metrics": target_metrics,
    }


def _critical_targets(gate_cfg: Any, targets: list[str]) -> list[str]:
    configured = [str(name) for name in getattr(gate_cfg, "critical_targets", [])]
    if not configured:
        return []
    known = set(targets)
    return [target for target in configured if target in known]


def _r2_score(y_true: np.ndarray, y_pred: np.ndarray) -> float:
    residual = float(np.sum((y_true - y_pred) ** 2))
    centered = float(np.sum((y_true - float(np.mean(y_true))) ** 2))
    if centered <= 0.0:
        return 1.0 if residual <= 1e-12 else float("-inf")
    return 1.0 - residual / centered


def _relative_mae_percent(y_true: np.ndarray, mae: float) -> float:
    scale = float(np.mean(np.abs(y_true)))
    if scale <= 1e-12:
        return 0.0 if mae <= 1e-12 else float("inf")
    return 100.0 * mae / scale
