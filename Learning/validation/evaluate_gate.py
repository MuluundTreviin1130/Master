from __future__ import annotations

import math
from typing import Any

import numpy as np


def _required_attr(obj: Any, name: str, context: str) -> Any:
    if obj is None or not hasattr(obj, name):
        raise AttributeError(f"[validation_gate] missing required setting `{context}.{name}`.")
    return getattr(obj, name)


def _as_2d_float_matrix(value: Any, *, name: str) -> np.ndarray:
    matrix = np.asarray(value, dtype=float)
    if matrix.ndim != 2:
        raise ValueError(f"[validation_gate] {name} must be a 2D array.")
    return matrix


def _finite_float(value: Any, *, name: str) -> float:
    number = float(value)
    if not math.isfinite(number):
        raise ValueError(f"[validation_gate] setting `{name}` must be finite.")
    return number


def _r2_score(y_true: np.ndarray, y_pred: np.ndarray) -> float:
    # R2 is undefined for a single holdout row; callers must classify that as
    # insufficient coverage before reaching this helper.
    residual_sum = float(np.sum((y_true - y_pred) ** 2))
    centered_sum = float(np.sum((y_true - float(np.mean(y_true))) ** 2))
    if centered_sum == 0.0:
        return 1.0 if residual_sum == 0.0 else 0.0
    return 1.0 - residual_sum / centered_sum


def _relative_mae_percent(y_true: np.ndarray, y_pred: np.ndarray) -> float:
    mae = float(np.mean(np.abs(y_true - y_pred)))
    denominator = float(np.mean(np.abs(y_true)))
    if denominator == 0.0:
        return 0.0 if mae == 0.0 else math.inf
    return 100.0 * mae / denominator


def _target_thresholds(gate_cfg: Any, *, critical: bool) -> dict[str, float]:
    if critical:
        return {
            "min_r2": _finite_float(
                _required_attr(gate_cfg, "critical_target_min_r2", "settings.learning.validation_gate"),
                name="settings.learning.validation_gate.critical_target_min_r2",
            ),
            "max_rel_mae_percent": _finite_float(
                _required_attr(gate_cfg, "critical_target_max_rel_mae_percent", "settings.learning.validation_gate"),
                name="settings.learning.validation_gate.critical_target_max_rel_mae_percent",
            ),
        }
    return {
        "min_r2": _finite_float(
            _required_attr(gate_cfg, "secondary_target_min_r2", "settings.learning.validation_gate"),
            name="settings.learning.validation_gate.secondary_target_min_r2",
        ),
        "max_rel_mae_percent": _finite_float(
            _required_attr(gate_cfg, "secondary_target_max_rel_mae_percent", "settings.learning.validation_gate"),
            name="settings.learning.validation_gate.secondary_target_max_rel_mae_percent",
        ),
    }


def evaluate_gate(
    settings: Any,
    *,
    target_names: list[str],
    y_true: Any,
    y_pred: Any,
) -> dict[str, Any]:
    """
    Evaluate whether a freshly trained surrogate is safe to mark eligible.

    The gate is intentionally strict: a model must pass Settings-defined R2 and
    relative-MAE thresholds target by target. Invalid shapes, missing gate
    settings, non-finite values, and too-small holdout coverage fail fast or
    block eligibility instead of being interpreted as acceptable defaults.
    """

    learning = _required_attr(settings, "learning", "settings")
    gate_cfg = _required_attr(learning, "validation_gate", "settings.learning")
    enabled = bool(_required_attr(gate_cfg, "enabled", "settings.learning.validation_gate"))

    targets = [str(target) for target in list(target_names)]
    if not targets:
        raise ValueError("[validation_gate] target_names must not be empty.")
    if len(set(targets)) != len(targets):
        raise ValueError("[validation_gate] target_names must be unique.")

    truth = _as_2d_float_matrix(y_true, name="y_true")
    prediction = _as_2d_float_matrix(y_pred, name="y_pred")
    if truth.shape != prediction.shape:
        raise ValueError(
            f"[validation_gate] y_true shape {truth.shape} does not match y_pred shape {prediction.shape}."
        )
    if truth.shape[1] != len(targets):
        raise ValueError(
            "[validation_gate] target_names length "
            f"{len(targets)} does not match holdout column count {truth.shape[1]}."
        )

    if not enabled:
        return {
            "eligible": True,
            "reason": "gate_disabled",
            "pass_share": 1.0,
            "target_count": int(len(targets)),
            "passed_targets": list(targets),
            "failed_targets": [],
            "failed_critical_targets": [],
            "failed_secondary_targets": [],
            "metrics": {},
        }

    min_pass_share = _finite_float(
        _required_attr(gate_cfg, "min_pass_share", "settings.learning.validation_gate"),
        name="settings.learning.validation_gate.min_pass_share",
    )
    if min_pass_share < 0.0 or min_pass_share > 1.0:
        raise ValueError("[validation_gate] settings.learning.validation_gate.min_pass_share must be in [0, 1].")

    require_full_target_coverage = bool(
        _required_attr(gate_cfg, "require_full_target_coverage", "settings.learning.validation_gate")
    )
    fail_on_nan_predictions = bool(
        _required_attr(gate_cfg, "fail_on_nan_predictions", "settings.learning.validation_gate")
    )
    critical_targets = {
        str(target)
        for target in list(
            _required_attr(gate_cfg, "critical_targets", "settings.learning.validation_gate") or []
        )
    }

    metrics: dict[str, dict[str, Any]] = {}
    passed_targets: list[str] = []
    failed_targets: list[str] = []
    failed_critical_targets: list[str] = []
    failed_secondary_targets: list[str] = []
    coverage_failures: list[str] = []
    nonfinite_failures: list[str] = []

    for idx, target in enumerate(targets):
        is_critical = target in critical_targets
        thresholds = _target_thresholds(gate_cfg, critical=is_critical)
        target_truth = truth[:, idx]
        target_prediction = prediction[:, idx]

        if target_truth.shape[0] < 2:
            passed = False
            reason = "insufficient_holdout_rows"
            coverage_failures.append(target)
            r2 = math.nan
            rel_mae_percent = math.nan
        elif not np.all(np.isfinite(target_truth)) or not np.all(np.isfinite(target_prediction)):
            # Non-finite teacher labels or predictions make metric comparisons
            # undefined. The setting is kept in the result for traceability, but
            # the gate still blocks because NaNs cannot be promoted safely.
            passed = False
            reason = "non_finite_values"
            nonfinite_failures.append(target)
            r2 = math.nan
            rel_mae_percent = math.nan
        else:
            r2 = _r2_score(target_truth, target_prediction)
            rel_mae_percent = _relative_mae_percent(target_truth, target_prediction)
            passed = (
                math.isfinite(r2)
                and math.isfinite(rel_mae_percent)
                and r2 >= thresholds["min_r2"]
                and rel_mae_percent <= thresholds["max_rel_mae_percent"]
            )
            reason = "passed" if passed else "metrics_below_threshold"

        metrics[target] = {
            "critical": bool(is_critical),
            "passed": bool(passed),
            "reason": reason,
            "r2": float(r2) if math.isfinite(r2) else None,
            "rel_mae_percent": float(rel_mae_percent) if math.isfinite(rel_mae_percent) else None,
            "min_r2": float(thresholds["min_r2"]),
            "max_rel_mae_percent": float(thresholds["max_rel_mae_percent"]),
        }

        if passed:
            passed_targets.append(target)
            continue
        failed_targets.append(target)
        if is_critical:
            failed_critical_targets.append(target)
        else:
            failed_secondary_targets.append(target)

    pass_share = float(len(passed_targets) / len(targets))
    full_coverage_ok = not require_full_target_coverage or not coverage_failures
    finite_ok = not fail_on_nan_predictions or not nonfinite_failures
    metrics_ok = not failed_critical_targets and pass_share >= min_pass_share
    eligible = bool(full_coverage_ok and finite_ok and metrics_ok)

    if eligible:
        reason = "passed"
    elif coverage_failures and require_full_target_coverage:
        reason = "insufficient_target_coverage"
    elif nonfinite_failures and fail_on_nan_predictions:
        reason = "non_finite_values"
    else:
        reason = "metrics_below_threshold"

    return {
        "eligible": eligible,
        "reason": reason,
        "pass_share": pass_share,
        "target_count": int(len(targets)),
        "passed_targets": passed_targets,
        "failed_targets": failed_targets,
        "failed_critical_targets": failed_critical_targets,
        "failed_secondary_targets": failed_secondary_targets,
        "insufficient_coverage_targets": coverage_failures,
        "nonfinite_targets": nonfinite_failures,
        "metrics": metrics,
        "settings": {
            "min_pass_share": float(min_pass_share),
            "require_full_target_coverage": bool(require_full_target_coverage),
            "fail_on_nan_predictions": bool(fail_on_nan_predictions),
        },
    }

