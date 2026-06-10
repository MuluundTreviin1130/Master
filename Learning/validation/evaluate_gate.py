from __future__ import annotations

from typing import Any

import numpy as np


def evaluate_gate(
    settings: Any,
    *,
    target_names: list[str],
    y_true: np.ndarray,
    y_pred: np.ndarray,
) -> dict[str, Any]:
    """
    Evaluate one native surrogate holdout against the explicit validation gate.

    The retrain path imports this module at `SurrogateEngine` import time.  This
    function therefore keeps the contract small and fail-fast: callers must pass
    named 2-D target matrices, and the threshold values must come from
    `settings.learning.validation_gate`, not from hidden runtime defaults.
    """

    gate_cfg = _require_gate_config(settings)
    names = _normalize_target_names(target_names)
    true_arr = _require_2d_array(y_true, label="y_true")
    pred_arr = _require_2d_array(y_pred, label="y_pred")
    if true_arr.shape != pred_arr.shape:
        raise ValueError(
            "[learning.validation] y_true/y_pred shape mismatch: "
            f"{true_arr.shape} != {pred_arr.shape}"
        )
    if true_arr.shape[1] != len(names):
        raise ValueError(
            "[learning.validation] target_names length does not match holdout columns: "
            f"{len(names)} names for {true_arr.shape[1]} columns"
        )

    fail_on_nan = bool(getattr(gate_cfg, "fail_on_nan_predictions", True))
    if fail_on_nan and (not np.isfinite(true_arr).all() or not np.isfinite(pred_arr).all()):
        return {
            "eligible": False,
            "reason": "non_finite_holdout_values",
            "target_metrics": [],
            "failed_targets": names,
            "failed_critical_targets": _critical_subset(gate_cfg, names),
            "failed_secondary_targets": _secondary_subset(gate_cfg, names),
            "pass_share": 0.0,
        }

    if true_arr.shape[0] == 0:
        return {
            "eligible": False,
            "reason": "empty_holdout",
            "target_metrics": [],
            "failed_targets": names,
            "failed_critical_targets": _critical_subset(gate_cfg, names),
            "failed_secondary_targets": _secondary_subset(gate_cfg, names),
            "pass_share": 0.0,
        }

    target_metrics: list[dict[str, Any]] = []
    failed_targets: list[str] = []
    failed_critical_targets: list[str] = []
    failed_secondary_targets: list[str] = []
    critical_targets = set(_critical_subset(gate_cfg, names))

    for idx, target_name in enumerate(names):
        is_critical = target_name in critical_targets
        thresholds = _thresholds_for_target(gate_cfg, is_critical=is_critical)
        metrics = _target_metric_row(
            target_name=target_name,
            y_true=true_arr[:, idx],
            y_pred=pred_arr[:, idx],
            is_critical=is_critical,
            min_r2=thresholds["min_r2"],
            max_rel_mae_percent=thresholds["max_rel_mae_percent"],
        )
        target_metrics.append(metrics)
        if not bool(metrics["passed"]):
            failed_targets.append(target_name)
            if is_critical:
                failed_critical_targets.append(target_name)
            else:
                failed_secondary_targets.append(target_name)

    pass_share = float((len(names) - len(failed_targets)) / len(names))
    min_pass_share = float(getattr(gate_cfg, "min_pass_share"))
    eligible = len(failed_critical_targets) == 0 and pass_share >= min_pass_share
    return {
        "eligible": bool(eligible),
        "reason": "passed" if eligible else "metrics_below_threshold",
        "target_metrics": target_metrics,
        "failed_targets": failed_targets,
        "failed_critical_targets": failed_critical_targets,
        "failed_secondary_targets": failed_secondary_targets,
        "pass_share": pass_share,
        "min_pass_share": min_pass_share,
    }


def _require_gate_config(settings: Any) -> Any:
    learning = getattr(settings, "learning", None)
    gate_cfg = getattr(learning, "validation_gate", None)
    if gate_cfg is None:
        raise AttributeError("[learning.validation] settings.learning.validation_gate is required.")
    required_attrs = (
        "min_pass_share",
        "critical_target_min_r2",
        "critical_target_max_rel_mae_percent",
        "secondary_target_min_r2",
        "secondary_target_max_rel_mae_percent",
    )
    missing = [name for name in required_attrs if not hasattr(gate_cfg, name)]
    if missing:
        raise AttributeError(
            "[learning.validation] validation_gate missing required fields: " + ", ".join(missing)
        )
    return gate_cfg


def _normalize_target_names(target_names: list[str]) -> list[str]:
    names = [str(name).strip() for name in list(target_names or [])]
    if not names or any(not name for name in names):
        raise ValueError("[learning.validation] target_names must contain non-empty names.")
    if len(set(names)) != len(names):
        raise ValueError("[learning.validation] target_names must be unique.")
    return names


def _require_2d_array(values: np.ndarray, *, label: str) -> np.ndarray:
    arr = np.asarray(values, dtype=float)
    if arr.ndim != 2:
        raise ValueError(f"[learning.validation] {label} must be a 2-D array.")
    return arr


def _critical_subset(gate_cfg: Any, target_names: list[str]) -> list[str]:
    configured = {str(name).strip() for name in list(getattr(gate_cfg, "critical_targets", []) or [])}
    return [name for name in target_names if name in configured]


def _secondary_subset(gate_cfg: Any, target_names: list[str]) -> list[str]:
    critical = set(_critical_subset(gate_cfg, target_names))
    return [name for name in target_names if name not in critical]


def _thresholds_for_target(gate_cfg: Any, *, is_critical: bool) -> dict[str, float]:
    if is_critical:
        return {
            "min_r2": float(getattr(gate_cfg, "critical_target_min_r2")),
            "max_rel_mae_percent": float(getattr(gate_cfg, "critical_target_max_rel_mae_percent")),
        }
    return {
        "min_r2": float(getattr(gate_cfg, "secondary_target_min_r2")),
        "max_rel_mae_percent": float(getattr(gate_cfg, "secondary_target_max_rel_mae_percent")),
    }


def _target_metric_row(
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
    rmse = float(np.sqrt(np.mean(err * err)))
    mean_abs_true = float(np.mean(np.abs(y_true)))
    rel_mae_percent = float("inf") if mean_abs_true <= 1e-12 and mae > 1e-12 else 0.0
    if mean_abs_true > 1e-12:
        rel_mae_percent = float(100.0 * mae / mean_abs_true)
    r2 = _safe_r2(y_true, y_pred)
    r2_pass = True if np.isnan(r2) and mae <= 1e-12 else bool(r2 >= min_r2)
    rel_pass = bool(rel_mae_percent <= max_rel_mae_percent)
    return {
        "target": target_name,
        "is_critical": bool(is_critical),
        "mae": mae,
        "rmse": rmse,
        "r2": float(r2),
        "rel_mae_percent": rel_mae_percent,
        "min_r2": min_r2,
        "max_rel_mae_percent": max_rel_mae_percent,
        "passed": bool(r2_pass and rel_pass),
    }


def _safe_r2(y_true: np.ndarray, y_pred: np.ndarray) -> float:
    values = np.asarray(y_true, dtype=float)
    if len(values) <= 1:
        return float("nan")
    centered = values - float(np.mean(values))
    total = float(np.sum(centered * centered))
    if total <= 1e-12:
        return float("nan")
    residual = np.asarray(y_pred, dtype=float) - values
    return float(1.0 - float(np.sum(residual * residual)) / total)
