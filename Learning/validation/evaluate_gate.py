from __future__ import annotations

from typing import Any

import numpy as np

from Optimization.framework.engines.Surrogat_model.validate.holdout import metrics_by_column


def evaluate_gate(
    settings: Any,
    *,
    target_names: list[str],
    y_true: np.ndarray,
    y_pred: np.ndarray,
) -> dict[str, Any]:
    """Evaluate native surrogate holdout predictions against settings thresholds.

    The training path registers candidate models before it promotes them for
    optimization.  This gate is the explicit boundary between those states: it
    does not invent fallback thresholds, and it reports exactly which configured
    targets prevented eligibility.
    """

    gate_cfg = getattr(getattr(settings, "learning", None), "validation_gate", None)
    if gate_cfg is None:
        raise AttributeError("[validation_gate] settings.learning.validation_gate is required.")
    if not bool(getattr(gate_cfg, "enabled", True)):
        return {
            "eligible": True,
            "reason": "disabled",
            "pass_share": 1.0,
            "failed_targets": [],
            "failed_critical_targets": [],
            "failed_secondary_targets": [],
            "metrics_by_target": {},
        }

    y_true_arr = np.asarray(y_true, dtype=float)
    y_pred_arr = np.asarray(y_pred, dtype=float)
    _validate_gate_inputs(target_names=target_names, y_true=y_true_arr, y_pred=y_pred_arr)

    target_list = [str(target) for target in target_names]
    critical_targets = [str(target) for target in getattr(gate_cfg, "critical_targets", [])]
    missing_critical = [target for target in critical_targets if target not in target_list]
    if bool(getattr(gate_cfg, "require_full_target_coverage", True)) and missing_critical:
        return {
            "eligible": False,
            "reason": "insufficient_target_coverage",
            "pass_share": 0.0,
            "failed_targets": list(missing_critical),
            "failed_critical_targets": list(missing_critical),
            "failed_secondary_targets": [],
            "missing_critical_targets": list(missing_critical),
            "metrics_by_target": {},
        }

    if y_true_arr.shape[0] == 0:
        return {
            "eligible": False,
            "reason": "empty_holdout",
            "pass_share": 0.0,
            "failed_targets": list(target_list),
            "failed_critical_targets": [target for target in target_list if target in critical_targets],
            "failed_secondary_targets": [target for target in target_list if target not in critical_targets],
            "metrics_by_target": {},
        }

    if bool(getattr(gate_cfg, "fail_on_nan_predictions", True)) and (
        not np.isfinite(y_true_arr).all() or not np.isfinite(y_pred_arr).all()
    ):
        failed_critical = [target for target in target_list if target in critical_targets]
        failed_secondary = [target for target in target_list if target not in critical_targets]
        return {
            "eligible": False,
            "reason": "nonfinite_holdout_values",
            "pass_share": 0.0,
            "failed_targets": list(target_list),
            "failed_critical_targets": failed_critical,
            "failed_secondary_targets": failed_secondary,
            "metrics_by_target": {},
        }

    metrics = metrics_by_column(y_true_arr, y_pred_arr, target_names=target_list)
    metrics_by_target = _metrics_by_target(metrics)
    failed_critical: list[str] = []
    failed_secondary: list[str] = []
    passed_count = 0
    for target in target_list:
        target_metrics = metrics_by_target[target]
        is_critical = target in critical_targets
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
        r2_value = float(target_metrics["r2"])
        rel_mae_value = float(target_metrics["rel_mae_percent"])
        passed = np.isfinite(r2_value) and np.isfinite(rel_mae_value) and r2_value >= min_r2 and rel_mae_value <= max_rel_mae
        target_metrics["is_critical"] = bool(is_critical)
        target_metrics["min_r2"] = min_r2
        target_metrics["max_rel_mae_percent"] = max_rel_mae
        target_metrics["passed"] = bool(passed)
        if passed:
            passed_count += 1
        elif is_critical:
            failed_critical.append(target)
        else:
            failed_secondary.append(target)

    failed_targets = [*failed_critical, *failed_secondary]
    pass_share = float(passed_count / len(target_list)) if target_list else 0.0
    min_pass_share = float(getattr(gate_cfg, "min_pass_share"))
    eligible = not failed_critical and pass_share >= min_pass_share
    return {
        "eligible": bool(eligible),
        "reason": "passed" if eligible else "metrics_below_threshold",
        "pass_share": pass_share,
        "min_pass_share": min_pass_share,
        "failed_targets": failed_targets,
        "failed_critical_targets": failed_critical,
        "failed_secondary_targets": failed_secondary,
        "missing_critical_targets": [],
        "metrics_by_target": metrics_by_target,
    }


def _validate_gate_inputs(
    *,
    target_names: list[str],
    y_true: np.ndarray,
    y_pred: np.ndarray,
) -> None:
    if y_true.ndim != 2 or y_pred.ndim != 2:
        raise ValueError("[validation_gate] y_true and y_pred must both be 2D arrays.")
    if y_true.shape != y_pred.shape:
        raise ValueError(
            "[validation_gate] y_true and y_pred shapes differ: "
            f"{tuple(y_true.shape)} != {tuple(y_pred.shape)}."
        )
    if len(target_names) != int(y_true.shape[1]):
        raise ValueError(
            "[validation_gate] target_names length does not match holdout columns: "
            f"{len(target_names)} != {y_true.shape[1]}."
        )
    if not target_names:
        raise ValueError("[validation_gate] at least one target is required.")


def _metrics_by_target(metrics: dict[str, list[float]]) -> dict[str, dict[str, float]]:
    targets = list(metrics["targets"])
    result: dict[str, dict[str, float]] = {}
    for idx, target in enumerate(targets):
        result[str(target)] = {
            "r2": float(metrics["r2"][idx]),
            "rmse": float(metrics["rmse"][idx]),
            "mae": float(metrics["mae"][idx]),
            "rel_mae_percent": float(metrics["rel_mae_percent"][idx]),
        }
    return result
