from __future__ import annotations

from typing import Any, Dict, List, Optional

import numpy as np


def get_hv_config(settings: Any) -> Any:
    return getattr(settings, "hypervolume", None)


def hv_mode(settings: Any) -> str:
    cfg = get_hv_config(settings)
    if cfg is None or not bool(getattr(cfg, "enabled", False)):
        return "off"
    return str(getattr(cfg, "mode", "off")).lower().strip() or "off"


def validate_reference_point(ref_point: List[float] | np.ndarray | None, n_obj: int) -> np.ndarray:
    if ref_point is None:
        raise ValueError("[hv] reference_point is required but missing.")
    arr = np.asarray(ref_point, dtype=float).reshape(-1)
    if arr.size != int(n_obj):
        raise ValueError(f"[hv] reference_point size mismatch: expected {n_obj}, got {arr.size}.")
    return arr


def apply_margin(values: np.ndarray, margin_mode: str, margin_value: float) -> np.ndarray:
    arr = np.asarray(values, dtype=float).reshape(-1)
    if arr.size == 0:
        raise ValueError("[hv] cannot apply margin to empty values.")
    mode = str(margin_mode).lower().strip()
    val = float(margin_value)
    if mode == "absolute":
        return arr + val
    if mode == "relative":
        bump = np.maximum(np.abs(arr) * val, val if val > 0.0 else 0.0)
        return arr + bump
    raise ValueError(f"[hv] unknown margin_mode='{margin_mode}'.")


def resolve_reference_point_from_seen(
    settings: Any,
    F_seen: np.ndarray,
    feasible_mask: np.ndarray | None = None,
    current_ref_point: np.ndarray | None = None,
) -> np.ndarray:
    F_seen = np.asarray(F_seen, dtype=float)
    if F_seen.ndim == 1:
        F_seen = F_seen.reshape(1, -1)
    if F_seen.shape[0] == 0:
        raise ValueError("[hv] cannot resolve reference point from empty F_seen.")
    if feasible_mask is not None:
        mask = np.asarray(feasible_mask, dtype=bool).reshape(-1)
        if mask.size == F_seen.shape[0]:
            F_eff = F_seen[mask, :]
        else:
            F_eff = F_seen
    else:
        F_eff = F_seen
    if F_eff.shape[0] == 0:
        F_eff = F_seen

    cfg = get_hv_config(settings)
    margin_mode = str(getattr(cfg, "margin_mode", "relative"))
    margin_value = float(getattr(cfg, "margin_value", 0.1))
    ref_point = apply_margin(np.max(F_eff, axis=0), margin_mode=margin_mode, margin_value=margin_value)
    if current_ref_point is not None:
        ref_point = np.maximum(np.asarray(current_ref_point, dtype=float).reshape(-1), ref_point)
    return ref_point


def resolve_reference_point(
    settings: Any,
    n_obj: int,
    F_seen: np.ndarray | None = None,
    feasible_mask: np.ndarray | None = None,
    current_ref_point: np.ndarray | None = None,
) -> np.ndarray | None:
    mode = hv_mode(settings)
    if mode == "off":
        return None
    cfg = get_hv_config(settings)
    if mode == "fixed":
        return validate_reference_point(getattr(cfg, "reference_point", None), n_obj=n_obj)
    if mode in {"auto_from_seen", "auto_from_warmup"}:
        if F_seen is None:
            raise ValueError(f"[hv] mode='{mode}' requires F_seen.")
        return resolve_reference_point_from_seen(
            settings,
            F_seen=F_seen,
            feasible_mask=feasible_mask,
            current_ref_point=current_ref_point,
        )
    raise ValueError(f"[hv] unknown mode='{mode}'.")


def compute_hv(F: np.ndarray, feasible_mask: np.ndarray, ref_point: np.ndarray | List[float] | None) -> float:
    from pymoo.indicators.hv import HV

    if ref_point is None:
        return 0.0
    F = np.asarray(F, dtype=float)
    if F.ndim == 1:
        F = F.reshape(1, -1)
    mask = np.asarray(feasible_mask, dtype=bool).reshape(-1)
    F_feasible = F[mask, :]
    if F_feasible.shape[0] == 0:
        return 0.0
    hv = HV(ref_point=np.asarray(ref_point, dtype=float).reshape(-1))
    return float(hv(F_feasible))


def zero_hv_fraction(values: List[float]) -> float:
    vals = [float(v) for v in values if v is not None]
    if not vals:
        return 0.0
    return float(sum(1 for v in vals if abs(v) <= 1e-12) / len(vals))


def build_hv_summary(settings: Any, resolved_ref_point: np.ndarray | None, source: str) -> Dict[str, Any]:
    cfg = get_hv_config(settings)
    return {
        "enabled": bool(getattr(cfg, "enabled", False)) if cfg is not None else False,
        "mode": hv_mode(settings),
        "reference_point": [float(x) for x in np.asarray(resolved_ref_point, dtype=float).reshape(-1)] if resolved_ref_point is not None else None,
        "source": str(source),
        "margin_mode": str(getattr(cfg, "margin_mode", "relative")) if cfg is not None else None,
        "margin_value": float(getattr(cfg, "margin_value", 0.0)) if cfg is not None else None,
        "warmup_stage_index": int(getattr(cfg, "warmup_stage_index", 0)) if cfg is not None else None,
    }
