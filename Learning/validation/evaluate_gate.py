from __future__ import annotations

from typing import Any, Dict, List, Tuple

import numpy as np


def _r2_score(y_true: np.ndarray, y_pred: np.ndarray) -> float:
    """Return R2 without depending on sklearn in the import-critical gate path."""

    true = np.asarray(y_true, dtype=float).reshape(-1)
    pred = np.asarray(y_pred, dtype=float).reshape(-1)
    if true.size == 0:
        raise ValueError("[learning.validation] Holdout target arrays must not be empty.")

    ss_tot = float(np.sum((true - float(np.mean(true))) ** 2))
    if ss_tot <= 1e-12:
        return float("nan")
    ss_res = float(np.sum((true - pred) ** 2))
    return float(1.0 - ss_res / ss_tot)


def _target_metrics(y_true: np.ndarray, y_pred: np.ndarray) -> Dict[str, float]:
    """Compute per-target holdout metrics with explicit zero-target handling."""

    true = np.asarray(y_true, dtype=float).reshape(-1)
    pred = np.asarray(y_pred, dtype=float).reshape(-1)
    if true.size == 0:
        raise ValueError("[learning.validation] Holdout target arrays must not be empty.")

    diff = true - pred
    mae = float(np.mean(np.abs(diff)))
    rmse = float(np.sqrt(np.mean(diff * diff)))
    mean_abs_true = float(np.mean(np.abs(true)))
    if mean_abs_true <= 1e-12:
        rel_mae_percent = 0.0 if mae <= 1e-12 else float("inf")
    else:
        rel_mae_percent = float(mae / mean_abs_true * 100.0)
    return {
        "r2": _r2_score(true, pred),
        "rmse": rmse,
        "mae": mae,
        "rel_mae_percent": rel_mae_percent,
    }


def _normalise_holdout_arrays(
    y_true: Any,
    y_pred: Any,
    target_names: List[str],
) -> Tuple[np.ndarray, np.ndarray]:
    """Validate array shape before any metric or registry status is written."""

    true = np.asarray(y_true, dtype=float)
    pred = np.asarray(y_pred, dtype=float)
    if true.ndim == 1:
        true = true.reshape(-1, 1)
    if pred.ndim == 1:
        pred = pred.reshape(-1, 1)
    if true.ndim != 2 or pred.ndim != 2:
        raise ValueError("[learning.validation] y_true and y_pred must be 1D or 2D arrays.")
    if true.shape != pred.shape:
        raise ValueError(
            "[learning.validation] y_true and y_pred shape mismatch: "
            f"{true.shape} != {pred.shape}."
        )
    if true.shape[0] == 0:
        raise ValueError("[learning.validation] Holdout arrays must contain at least one sample.")
    if true.shape[1] != len(target_names):
        raise ValueError(
            "[learning.validation] target_names length must match holdout columns: "
            f"{len(target_names)} != {true.shape[1]}."
        )
    return true, pred


def _passes_metric_gate(
    *,
    metrics: Dict[str, float],
    is_critical: bool,
    gate_cfg: Any,
) -> Tuple[bool, List[str]]:
    """Apply the configured critical/secondary thresholds to one target."""

    reasons: List[str] = []
    min_r2_attr = "critical_target_min_r2" if is_critical else "secondary_target_min_r2"
    max_mae_attr = "critical_target_max_rel_mae_percent" if is_critical else "secondary_target_max_rel_mae_percent"
    min_r2 = float(getattr(gate_cfg, min_r2_attr))
    max_rel_mae = float(getattr(gate_cfg, max_mae_attr))

    r2 = float(metrics["r2"])
    rel_mae = float(metrics["rel_mae_percent"])
    if np.isfinite(r2) and r2 < min_r2:
        reasons.append(f"r2_below_{min_r2:g}")
    if np.isfinite(rel_mae):
        if rel_mae > max_rel_mae:
            reasons.append(f"rel_mae_above_{max_rel_mae:g}_percent")
    else:
        reasons.append("rel_mae_not_finite")
    return not reasons, reasons


def _result_reason(
    *,
    enabled: bool,
    failed_targets: List[str],
    failed_critical: List[str],
    pass_share: float,
    min_pass_share: float,
) -> str:
    """Return the stable reason strings used by retrain remediation policy."""

    if not enabled:
        return "validation_gate_disabled"
    if failed_critical:
        return "metrics_below_threshold"
    if pass_share < min_pass_share:
        return "insufficient_target_coverage"
    if failed_targets:
        return "metrics_below_threshold"
    return "passed"


def evaluate_gate(
    settings: Any,
    *,
    target_names: List[str],
    y_true: Any,
    y_pred: Any,
) -> Dict[str, Any]:
    """Evaluate whether a freshly trained surrogate is eligible for use.

    The gate is deliberately fail-fast: malformed holdout arrays, missing gate
    settings, non-finite truths, or configured non-finite predictions are
    reported before the model can be promoted in the Learning registry.
    """

    gate_cfg = getattr(getattr(settings, "learning", None), "validation_gate", None)
    if gate_cfg is None:
        raise AttributeError("[learning.validation] settings.learning.validation_gate is required.")

    targets = [str(name) for name in target_names]
    if not targets:
        raise ValueError("[learning.validation] target_names must contain at least one target.")

    if not bool(getattr(gate_cfg, "enabled", True)):
        return {
            "eligible": True,
            "enabled": False,
            "reason": _result_reason(
                enabled=False,
                failed_targets=[],
                failed_critical=[],
                pass_share=1.0,
                min_pass_share=1.0,
            ),
            "pass_share": 1.0,
            "min_pass_share": 1.0,
            "failed_targets": [],
            "failed_critical_targets": [],
            "failed_secondary_targets": [],
            "target_results": [],
            "thresholds": {},
        }

    true, pred = _normalise_holdout_arrays(y_true, y_pred, targets)
    critical_targets = {str(name) for name in getattr(gate_cfg, "critical_targets", [])}
    fail_on_nan = bool(getattr(gate_cfg, "fail_on_nan_predictions", True))

    target_results: List[Dict[str, Any]] = []
    failed_targets: List[str] = []
    failed_critical: List[str] = []
    failed_secondary: List[str] = []
    passed_count = 0

    for idx, target in enumerate(targets):
        reasons: List[str] = []
        is_critical = target in critical_targets

        if np.any(~np.isfinite(true[:, idx])):
            reasons.append("nonfinite_truth")
        if fail_on_nan and np.any(~np.isfinite(pred[:, idx])):
            reasons.append("nonfinite_prediction")

        if reasons:
            metrics = {
                "r2": float("nan"),
                "rmse": float("nan"),
                "mae": float("nan"),
                "rel_mae_percent": float("nan"),
            }
            passed = False
        else:
            metrics = _target_metrics(true[:, idx], pred[:, idx])
            passed, metric_reasons = _passes_metric_gate(
                metrics=metrics,
                is_critical=is_critical,
                gate_cfg=gate_cfg,
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

    pass_share = float(passed_count / len(targets))
    min_pass_share = float(getattr(gate_cfg, "min_pass_share", 1.0))
    require_full_target_coverage = bool(getattr(gate_cfg, "require_full_target_coverage", True))
    eligible = pass_share >= min_pass_share and not failed_critical
    if require_full_target_coverage and failed_targets:
        eligible = False

    reason = "passed" if eligible else _result_reason(
        enabled=True,
        failed_targets=failed_targets,
        failed_critical=failed_critical,
        pass_share=pass_share,
        min_pass_share=min_pass_share,
    )

    return {
        "eligible": bool(eligible),
        "enabled": True,
        "reason": reason,
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
