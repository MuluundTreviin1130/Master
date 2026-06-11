from __future__ import annotations

from typing import Any

import numpy as np

_EPS = 1e-12


def evaluate_gate(
    settings: Any,
    *,
    target_names: list[str],
    y_true: Any,
    y_pred: Any,
) -> dict[str, Any]:
    """Evaluate the retrain holdout against the Settings-backed promotion gate.

    The training path persists this payload into the Learning registry. Keep the
    result JSON-safe and explicit so a candidate model can never become eligible
    because a missing metric was hidden behind a numeric fallback.
    """

    gate_cfg = _require_gate_config(settings)
    names = [str(target_name) for target_name in target_names]
    if not names:
        raise ValueError("[learning.validation] target_names must not be empty.")

    if not bool(getattr(gate_cfg, "enabled", True)):
        return {
            "eligible": True,
            "metrics_passed": True,
            "reason": "gate_disabled",
            "pass_share": 1.0,
            "n_targets": int(len(names)),
            "n_test_rows": int(np.asarray(y_true).shape[0]) if np.asarray(y_true).ndim >= 1 else 0,
            "target_metrics": [],
            "failed_targets": [],
            "failed_critical_targets": [],
            "failed_secondary_targets": [],
        }

    true = _as_2d_float_array(y_true, label="y_true")
    pred = _as_2d_float_array(y_pred, label="y_pred")
    if true.shape[0] != pred.shape[0]:
        raise ValueError(
            "[learning.validation] y_true/y_pred row mismatch: "
            f"{true.shape[0]} != {pred.shape[0]}."
        )
    if true.shape[1] != pred.shape[1]:
        raise ValueError(
            "[learning.validation] y_true/y_pred target-column mismatch: "
            f"{true.shape[1]} != {pred.shape[1]}."
        )

    require_full_coverage = bool(getattr(gate_cfg, "require_full_target_coverage", True))
    if true.shape[1] != len(names):
        if require_full_coverage:
            return _blocked_payload(
                reason="insufficient_target_coverage",
                names=names,
                n_test_rows=int(true.shape[0]),
                target_metrics=[],
                failed_targets=names,
                failed_critical_targets=_ordered_critical(names, gate_cfg),
                failed_secondary_targets=_ordered_secondary(names, gate_cfg),
                pass_share=0.0,
                extra={
                    "expected_target_columns": int(len(names)),
                    "observed_target_columns": int(true.shape[1]),
                },
            )
        if true.shape[1] > len(names):
            raise ValueError(
                "[learning.validation] y_true/y_pred contain unlabeled target columns: "
                f"{true.shape[1]} columns for {len(names)} target names."
            )
        names = names[: true.shape[1]]

    if true.shape[0] <= 0:
        return _blocked_payload(
            reason="empty_holdout",
            names=names,
            n_test_rows=0,
            target_metrics=[],
            failed_targets=names,
            failed_critical_targets=_ordered_critical(names, gate_cfg),
            failed_secondary_targets=_ordered_secondary(names, gate_cfg),
            pass_share=0.0,
        )

    non_finite_truth = _targets_with_non_finite(true, names)
    non_finite_pred = _targets_with_non_finite(pred, names)
    if non_finite_truth or (bool(getattr(gate_cfg, "fail_on_nan_predictions", True)) and non_finite_pred):
        failed = _ordered_unique([*non_finite_truth, *non_finite_pred])
        return _blocked_payload(
            reason="non_finite_values",
            names=names,
            n_test_rows=int(true.shape[0]),
            target_metrics=[],
            failed_targets=failed,
            failed_critical_targets=_ordered_critical(failed, gate_cfg),
            failed_secondary_targets=_ordered_secondary(failed, gate_cfg),
            pass_share=0.0,
            extra={
                "non_finite_truth_targets": non_finite_truth,
                "non_finite_prediction_targets": non_finite_pred,
            },
        )

    critical_targets = set(str(target) for target in getattr(gate_cfg, "critical_targets", []) or [])
    min_pass_share = float(getattr(gate_cfg, "min_pass_share", 0.9))
    target_metrics: list[dict[str, Any]] = []
    failed_targets: list[str] = []
    failed_critical: list[str] = []
    failed_secondary: list[str] = []

    for idx, target_name in enumerate(names):
        is_critical = target_name in critical_targets
        thresholds = _thresholds_for_target(gate_cfg, is_critical=is_critical)
        metric = _target_metric(
            target_name=target_name,
            y_true=true[:, idx],
            y_pred=pred[:, idx],
            is_critical=is_critical,
            min_r2=thresholds["min_r2"],
            max_rel_mae_percent=thresholds["max_rel_mae_percent"],
        )
        target_metrics.append(metric)
        if not bool(metric["passed"]):
            failed_targets.append(target_name)
            if is_critical:
                failed_critical.append(target_name)
            else:
                failed_secondary.append(target_name)

    passed_count = int(len(names) - len(failed_targets))
    pass_share = float(passed_count / len(names))
    metrics_passed = bool(pass_share >= min_pass_share and not failed_critical)
    auto_validate = bool(getattr(gate_cfg, "auto_validate_after_retrain", True))
    auto_promote = bool(getattr(gate_cfg, "auto_promote_to_eligible", True))
    eligible = bool(metrics_passed and auto_validate and auto_promote)

    if eligible:
        reason = "metrics_passed"
    elif not auto_validate and metrics_passed:
        reason = "auto_validation_disabled"
    elif not auto_promote and metrics_passed:
        reason = "auto_promote_disabled"
    else:
        reason = "metrics_below_threshold"

    return {
        "eligible": eligible,
        "metrics_passed": metrics_passed,
        "reason": reason,
        "pass_share": pass_share,
        "min_pass_share": min_pass_share,
        "n_targets": int(len(names)),
        "n_test_rows": int(true.shape[0]),
        "passed_targets": [name for name in names if name not in set(failed_targets)],
        "failed_targets": failed_targets,
        "failed_critical_targets": failed_critical,
        "failed_secondary_targets": failed_secondary,
        "critical_targets": [name for name in names if name in critical_targets],
        "target_metrics": target_metrics,
    }


def _require_gate_config(settings: Any) -> Any:
    learning = getattr(settings, "learning", None)
    gate_cfg = getattr(learning, "validation_gate", None) if learning is not None else None
    if gate_cfg is None:
        raise AttributeError("[learning.validation] settings.learning.validation_gate is required.")
    return gate_cfg


def _as_2d_float_array(value: Any, *, label: str) -> np.ndarray:
    arr = np.asarray(value, dtype=float)
    if arr.ndim != 2:
        raise ValueError(f"[learning.validation] {label} must be a 2D array, got shape {arr.shape}.")
    return arr


def _targets_with_non_finite(values: np.ndarray, names: list[str]) -> list[str]:
    bad: list[str] = []
    for idx, target_name in enumerate(names):
        if not bool(np.all(np.isfinite(values[:, idx]))):
            bad.append(target_name)
    return bad


def _target_metric(
    *,
    target_name: str,
    y_true: np.ndarray,
    y_pred: np.ndarray,
    is_critical: bool,
    min_r2: float,
    max_rel_mae_percent: float,
) -> dict[str, Any]:
    err = np.asarray(y_pred, dtype=float) - np.asarray(y_true, dtype=float)
    mae = float(np.mean(np.abs(err)))
    rmse = float(np.sqrt(np.mean(np.square(err))))
    bias = float(np.mean(err))
    true_abs_mean = float(np.mean(np.abs(y_true)))
    true_std = float(np.std(y_true))
    r2 = _safe_r2(y_true, y_pred)
    rel_mae_percent = _relative_mae_percent(mae=mae, true_abs_mean=true_abs_mean)
    r2_passed = bool(r2 is not None and r2 >= min_r2)
    rel_mae_passed = bool(rel_mae_percent is not None and rel_mae_percent <= max_rel_mae_percent)
    passed = bool(r2_passed and rel_mae_passed)
    failure_reasons: list[str] = []
    if not r2_passed:
        failure_reasons.append("r2_below_threshold" if r2 is not None else "r2_undefined")
    if not rel_mae_passed:
        failure_reasons.append("rel_mae_above_threshold" if rel_mae_percent is not None else "rel_mae_undefined")
    return {
        "target": target_name,
        "critical": bool(is_critical),
        "passed": passed,
        "failure_reasons": failure_reasons,
        "r2": r2,
        "min_r2": float(min_r2),
        "mae": mae,
        "rmse": rmse,
        "bias": bias,
        "true_abs_mean": true_abs_mean,
        "true_std": true_std,
        "rel_mae_percent": rel_mae_percent,
        "max_rel_mae_percent": float(max_rel_mae_percent),
    }


def _safe_r2(y_true: np.ndarray, y_pred: np.ndarray) -> float | None:
    true = np.asarray(y_true, dtype=float)
    pred = np.asarray(y_pred, dtype=float)
    residual_sum = float(np.sum(np.square(true - pred)))
    total_sum = float(np.sum(np.square(true - float(np.mean(true)))))
    if total_sum <= _EPS:
        return 1.0 if residual_sum <= _EPS else None
    return float(1.0 - residual_sum / total_sum)


def _relative_mae_percent(*, mae: float, true_abs_mean: float) -> float | None:
    if true_abs_mean <= _EPS:
        return 0.0 if mae <= _EPS else None
    return float(100.0 * mae / true_abs_mean)


def _thresholds_for_target(gate_cfg: Any, *, is_critical: bool) -> dict[str, float]:
    if is_critical:
        return {
            "min_r2": float(getattr(gate_cfg, "critical_target_min_r2", 0.95)),
            "max_rel_mae_percent": float(getattr(gate_cfg, "critical_target_max_rel_mae_percent", 8.0)),
        }
    return {
        "min_r2": float(getattr(gate_cfg, "secondary_target_min_r2", 0.85)),
        "max_rel_mae_percent": float(getattr(gate_cfg, "secondary_target_max_rel_mae_percent", 15.0)),
    }


def _blocked_payload(
    *,
    reason: str,
    names: list[str],
    n_test_rows: int,
    target_metrics: list[dict[str, Any]],
    failed_targets: list[str],
    failed_critical_targets: list[str],
    failed_secondary_targets: list[str],
    pass_share: float,
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    payload = {
        "eligible": False,
        "metrics_passed": False,
        "reason": reason,
        "pass_share": float(pass_share),
        "n_targets": int(len(names)),
        "n_test_rows": int(n_test_rows),
        "passed_targets": [],
        "failed_targets": failed_targets,
        "failed_critical_targets": failed_critical_targets,
        "failed_secondary_targets": failed_secondary_targets,
        "target_metrics": target_metrics,
    }
    if extra:
        payload.update(extra)
    return payload


def _ordered_critical(names: list[str], gate_cfg: Any) -> list[str]:
    critical = set(str(target) for target in getattr(gate_cfg, "critical_targets", []) or [])
    return [name for name in names if name in critical]


def _ordered_secondary(names: list[str], gate_cfg: Any) -> list[str]:
    critical = set(str(target) for target in getattr(gate_cfg, "critical_targets", []) or [])
    return [name for name in names if name not in critical]


def _ordered_unique(names: list[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for name in names:
        if name in seen:
            continue
        seen.add(name)
        out.append(name)
    return out
