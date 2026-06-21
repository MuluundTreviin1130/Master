from __future__ import annotations

import math
from typing import Any, Dict, List

import numpy as np


def evaluate_gate(
    settings: Any,
    *,
    target_names: List[str],
    y_true: np.ndarray,
    y_pred: np.ndarray,
) -> Dict[str, Any]:
    """Evaluate the native surrogate holdout against the settings-defined gate.

    Native retraining writes model registry eligibility directly after this
    function returns. The gate therefore validates array shape, target coverage
    and target-wise errors explicitly instead of letting malformed holdouts
    become usable optimization models.
    """

    gate_cfg = getattr(getattr(settings, "learning", None), "validation_gate", None)
    names = [str(name) for name in target_names]
    true = np.asarray(y_true, dtype=float)
    pred = np.asarray(y_pred, dtype=float)
    _validate_contract(names=names, true=true, pred=pred)

    if gate_cfg is None or not bool(getattr(gate_cfg, "enabled", True)):
        return {
            "eligible": True,
            "reason": "disabled",
            "pass_share": 1.0,
            "metrics": _metric_rows(names=names, true=true, pred=pred),
            "failed_targets": [],
            "failed_critical_targets": [],
            "failed_secondary_targets": [],
            "missing_critical_targets": [],
        }

    critical_targets = [str(name) for name in getattr(gate_cfg, "critical_targets", []) or []]
    critical_set = set(critical_targets)
    present_set = set(names)
    out_of_scope_critical = sorted(critical_set.difference(present_set))

    if true.shape[0] == 0:
        return {
            "eligible": False,
            "reason": "empty_holdout",
            "pass_share": 0.0,
            "metrics": [],
            "failed_targets": names,
            "failed_critical_targets": sorted(critical_set.intersection(present_set)),
            "failed_secondary_targets": sorted(present_set.difference(critical_set)),
            "missing_critical_targets": [],
            "out_of_scope_critical_targets": out_of_scope_critical,
        }

    metrics = _metric_rows(names=names, true=true, pred=pred)
    failed_critical: List[str] = []
    failed_secondary: List[str] = []
    for metric in metrics:
        target = str(metric["target"])
        is_critical = target in critical_set
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
                math.inf,
            )
        )
        r2 = metric["r2"]
        rel_mae = metric["rel_mae_percent"]
        finite_metrics = r2 is not None and rel_mae is not None
        target_passed = bool(finite_metrics and float(r2) >= min_r2 and float(rel_mae) <= max_rel_mae)
        metric["is_critical"] = bool(is_critical)
        metric["passed"] = bool(target_passed)
        metric["min_r2"] = min_r2
        metric["max_rel_mae_percent"] = max_rel_mae
        if not target_passed:
            if is_critical:
                failed_critical.append(target)
            else:
                failed_secondary.append(target)

    failed_targets = failed_critical + failed_secondary
    pass_share = float((len(metrics) - len(failed_targets)) / len(metrics)) if metrics else 0.0
    min_pass_share = float(getattr(gate_cfg, "min_pass_share", 1.0))
    eligible = not failed_critical and pass_share >= min_pass_share
    return {
        "eligible": bool(eligible),
        "reason": "eligible" if eligible else "metrics_below_threshold",
        "pass_share": pass_share,
        "metrics": metrics,
        "failed_targets": failed_targets,
        "failed_critical_targets": failed_critical,
        "failed_secondary_targets": failed_secondary,
        "missing_critical_targets": [],
        "out_of_scope_critical_targets": out_of_scope_critical,
    }


def _validate_contract(*, names: List[str], true: np.ndarray, pred: np.ndarray) -> None:
    if not names:
        raise ValueError("[learning.validation] validation gate requires at least one target.")
    if true.ndim != 2 or pred.ndim != 2:
        raise ValueError("[learning.validation] y_true and y_pred must be two-dimensional arrays.")
    if true.shape != pred.shape:
        raise ValueError(
            "[learning.validation] y_true/y_pred shape mismatch: "
            f"{tuple(true.shape)} != {tuple(pred.shape)}."
        )
    if true.shape[1] != len(names):
        raise ValueError(
            "[learning.validation] target_names length does not match prediction columns: "
            f"{len(names)} != {true.shape[1]}."
        )


def _metric_rows(*, names: List[str], true: np.ndarray, pred: np.ndarray) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    for idx, target in enumerate(names):
        y_true = np.asarray(true[:, idx], dtype=float)
        y_pred = np.asarray(pred[:, idx], dtype=float)
        finite = bool(np.isfinite(y_true).all() and np.isfinite(y_pred).all())
        if not finite:
            rows.append(
                {
                    "target": target,
                    "mae": None,
                    "rmse": None,
                    "bias": None,
                    "r2": None,
                    "rel_mae_percent": None,
                    "mean_abs_true": None,
                    "finite": False,
                }
            )
            continue
        err = y_pred - y_true
        mae = float(np.mean(np.abs(err))) if len(err) else math.inf
        rmse = float(np.sqrt(np.mean(err * err))) if len(err) else math.inf
        bias = float(np.mean(err)) if len(err) else math.inf
        mean_abs_true = float(np.mean(np.abs(y_true))) if len(y_true) else 0.0
        rows.append(
            {
                "target": target,
                "mae": _json_float(mae),
                "rmse": _json_float(rmse),
                "bias": _json_float(bias),
                "r2": _json_float(_safe_r2(y_true, y_pred)),
                "rel_mae_percent": _json_float(_relative_mae_percent(mae, mean_abs_true)),
                "mean_abs_true": _json_float(mean_abs_true),
                "finite": True,
            }
        )
    return rows


def _safe_r2(y_true: np.ndarray, y_pred: np.ndarray) -> float:
    if len(y_true) <= 1:
        return 1.0 if np.allclose(y_true, y_pred, rtol=0.0, atol=1e-12) else -math.inf
    centered = y_true - float(np.mean(y_true))
    ss_tot = float(np.sum(centered * centered))
    ss_res = float(np.sum((y_pred - y_true) * (y_pred - y_true)))
    if ss_tot <= 1e-12:
        return 1.0 if ss_res <= 1e-12 else -math.inf
    return float(1.0 - ss_res / ss_tot)


def _relative_mae_percent(mae: float, mean_abs_true: float) -> float:
    if mean_abs_true > 1e-12:
        return float(100.0 * mae / mean_abs_true)
    return 0.0 if mae <= 1e-12 else math.inf


def _json_float(value: float) -> float | None:
    value = float(value)
    return value if math.isfinite(value) else None
