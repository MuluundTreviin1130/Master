from __future__ import annotations

import math
from typing import Any, Dict, Iterable, List

import numpy as np


def _json_float(value: float) -> float | None:
    if math.isfinite(float(value)):
        return float(value)
    return None


def _r2_score(y_true: np.ndarray, y_pred: np.ndarray) -> float:
    residual = float(np.sum((y_true - y_pred) ** 2))
    centered = y_true - float(np.mean(y_true))
    total = float(np.sum(centered ** 2))
    if total <= 1e-12:
        return 1.0 if residual <= 1e-12 else float("-inf")
    return 1.0 - residual / total


def _rel_mae_percent(y_true: np.ndarray, mae: float) -> float:
    denom = float(np.mean(np.abs(y_true)))
    if denom <= 1e-12:
        return 0.0 if mae <= 1e-12 else float("inf")
    return float(mae / denom * 100.0)


def _as_name_set(values: Iterable[Any]) -> set[str]:
    return {str(value) for value in values}


def evaluate_gate(
    settings: Any,
    *,
    target_names: List[str],
    y_true: Any,
    y_pred: Any,
) -> Dict[str, Any]:
    """Evaluate the native Learning holdout gate.

    The caller persists this dictionary directly in the Learning registry, so
    all values are kept JSON-safe and explicit. Threshold misses return a
    blocked result; malformed arrays raise because they indicate a training
    contract error rather than a merely weak model.
    """

    gate_cfg = getattr(getattr(settings, "learning", None), "validation_gate", None)
    if gate_cfg is None:
        raise ValueError("[learning.validation] Missing learning.validation_gate settings.")
    if not bool(getattr(gate_cfg, "enabled", True)):
        return {
            "eligible": True,
            "reason": "gate_disabled",
            "pass_share": 1.0,
            "failed_targets": [],
            "failed_critical_targets": [],
            "failed_secondary_targets": [],
            "target_metrics": [],
        }

    names = [str(name) for name in target_names]
    yt = np.asarray(y_true, dtype=float)
    yp = np.asarray(y_pred, dtype=float)
    if yt.shape != yp.shape:
        raise ValueError(
            f"[learning.validation] y_true/y_pred shape mismatch: {yt.shape} != {yp.shape}."
        )
    if yt.ndim == 1:
        yt = yt.reshape((-1, 1))
        yp = yp.reshape((-1, 1))
    if yt.ndim != 2:
        raise ValueError(f"[learning.validation] Expected 2-D target arrays, got ndim={yt.ndim}.")
    if yt.shape[1] != len(names):
        raise ValueError(
            "[learning.validation] target_names length does not match prediction columns: "
            f"{len(names)} != {yt.shape[1]}."
        )
    if yt.shape[0] == 0:
        return {
            "eligible": False,
            "reason": "empty_holdout",
            "pass_share": 0.0,
            "failed_targets": names,
            "failed_critical_targets": [],
            "failed_secondary_targets": names,
            "target_metrics": [],
        }

    if bool(getattr(gate_cfg, "fail_on_nan_predictions", True)) and (
        not np.all(np.isfinite(yt)) or not np.all(np.isfinite(yp))
    ):
        return {
            "eligible": False,
            "reason": "non_finite_values",
            "pass_share": 0.0,
            "failed_targets": names,
            "failed_critical_targets": [],
            "failed_secondary_targets": names,
            "target_metrics": [],
        }

    critical_targets = _as_name_set(getattr(gate_cfg, "critical_targets", []) or [])
    name_set = set(names)
    missing_critical = sorted(critical_targets - name_set)
    if bool(getattr(gate_cfg, "require_full_target_coverage", True)) and missing_critical:
        return {
            "eligible": False,
            "reason": "insufficient_target_coverage",
            "pass_share": 0.0,
            "failed_targets": missing_critical,
            "failed_critical_targets": missing_critical,
            "failed_secondary_targets": [],
            "missing_targets": missing_critical,
            "target_metrics": [],
        }

    critical_min_r2 = float(getattr(gate_cfg, "critical_target_min_r2", 0.95))
    critical_max_rel_mae = float(getattr(gate_cfg, "critical_target_max_rel_mae_percent", 8.0))
    secondary_min_r2 = float(getattr(gate_cfg, "secondary_target_min_r2", 0.85))
    secondary_max_rel_mae = float(getattr(gate_cfg, "secondary_target_max_rel_mae_percent", 15.0))

    target_metrics: List[Dict[str, Any]] = []
    failed_critical: List[str] = []
    failed_secondary: List[str] = []
    passed = 0
    for col, name in enumerate(names):
        true_col = yt[:, col]
        pred_col = yp[:, col]
        r2 = _r2_score(true_col, pred_col)
        mae = float(np.mean(np.abs(true_col - pred_col)))
        rel_mae = _rel_mae_percent(true_col, mae)
        is_critical = name in critical_targets
        min_r2 = critical_min_r2 if is_critical else secondary_min_r2
        max_rel_mae = critical_max_rel_mae if is_critical else secondary_max_rel_mae
        passed_target = bool(r2 >= min_r2 and rel_mae <= max_rel_mae)
        if passed_target:
            passed += 1
        elif is_critical:
            failed_critical.append(name)
        else:
            failed_secondary.append(name)
        target_metrics.append(
            {
                "target": name,
                "critical": bool(is_critical),
                "passed": passed_target,
                "r2": _json_float(r2),
                "mae": _json_float(mae),
                "rel_mae_percent": _json_float(rel_mae),
                "min_r2": min_r2,
                "max_rel_mae_percent": max_rel_mae,
            }
        )

    failed_targets = failed_critical + failed_secondary
    pass_share = float(passed / len(names)) if names else 0.0
    eligible = (
        pass_share >= float(getattr(gate_cfg, "min_pass_share", 0.9))
        and not failed_critical
        and not missing_critical
    )
    return {
        "eligible": bool(eligible),
        "reason": "passed" if eligible else "metrics_below_threshold",
        "pass_share": pass_share,
        "failed_targets": failed_targets,
        "failed_critical_targets": failed_critical,
        "failed_secondary_targets": failed_secondary,
        "target_metrics": target_metrics,
    }
