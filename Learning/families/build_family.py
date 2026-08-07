from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass, field, is_dataclass
from typing import Any, Dict, List

from Optimization.framework.engines.Surrogat_model.features import (
    resolve_feature_encoding,
    resolve_feature_names,
    resolve_surrogate_targets,
)


def _stable_hash(payload: Dict[str, Any]) -> str:
    text = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _normalize_model_params(params: Dict[str, Any] | None) -> Dict[str, Any]:
    out: Dict[str, Any] = {}
    for key, value in dict(params or {}).items():
        if is_dataclass(value):
            out[str(key)] = asdict(value)
        elif isinstance(value, (str, int, float, bool)) or value is None:
            out[str(key)] = value
        else:
            out[str(key)] = repr(value)
    return out


@dataclass
class FamilySpec:
    system: Dict[str, Any]
    input_schema: Dict[str, Any]
    feature_schema: Dict[str, Any]
    target_schema: Dict[str, Any]
    search_space: Dict[str, Any]
    training_spec: Dict[str, Any]
    time_model: Dict[str, Any]
    dispatch_signature: Dict[str, Any]
    provenance: Dict[str, Any] = field(default_factory=dict)
    family_hash: str = ""

    def to_dict(self) -> Dict[str, Any]:
        data = asdict(self)
        return data


def _require_family_dispatch_mode(settings: Any) -> str:
    """
    Teacher labels are produced by the active operational policy.
    Family identity must therefore hash the live dispatch.mode; otherwise a
    switch such as milp_day_ahead -> milp_two_stage keeps the same family_hash
    and resolve_model silently reuses the previous native artifact.
    """
    dispatch = getattr(settings, "dispatch", None)
    if dispatch is None:
        raise ValueError(
            "[learning.families] settings.dispatch is required for family identity "
            "because teacher labels depend on dispatch.mode."
        )
    if not hasattr(dispatch, "mode"):
        raise ValueError(
            "[learning.families] settings.dispatch.mode is required for family identity."
        )
    mode = str(getattr(dispatch, "mode") or "").strip().lower()
    if not mode:
        raise ValueError(
            "[learning.families] settings.dispatch.mode must be a non-empty string."
        )
    return mode


def _require_family_dispatch_horizon_h(settings: Any) -> int:
    """
    MILP and rolling dispatch horizons change commitment/lookahead and therefore
    the teacher objective surface. Keep horizon_h in the hashed signature so a
    24h -> 48h change cannot reuse an incompatible dataset/model family.
    """
    dispatch = getattr(settings, "dispatch", None)
    if dispatch is None:
        raise ValueError(
            "[learning.families] settings.dispatch is required for family identity "
            "because teacher labels depend on dispatch.horizon_h."
        )
    if not hasattr(dispatch, "horizon_h"):
        raise ValueError(
            "[learning.families] settings.dispatch.horizon_h is required for family identity."
        )
    horizon_h = int(getattr(dispatch, "horizon_h"))
    if horizon_h <= 0:
        raise ValueError(
            "[learning.families] settings.dispatch.horizon_h must be a positive integer, "
            f"got {horizon_h}."
        )
    return horizon_h


def _require_family_dispatch_stochastic_enabled(settings: Any) -> bool:
    """
    Stochastic two-stage dispatch changes expected-cost teacher labels even when
    the nominal mode string stays fixed. Hash the live SSOT flag so enabling
    stochastic scenarios cannot silently reuse a deterministic native model.
    """
    dispatch = getattr(settings, "dispatch", None)
    if dispatch is None:
        raise ValueError(
            "[learning.families] settings.dispatch is required for family identity "
            "because teacher labels depend on dispatch.stochastic_enabled."
        )
    if not hasattr(dispatch, "stochastic_enabled"):
        raise ValueError(
            "[learning.families] settings.dispatch.stochastic_enabled is required for family identity."
        )
    value = getattr(dispatch, "stochastic_enabled")
    if not isinstance(value, bool):
        raise ValueError(
            "[learning.families] settings.dispatch.stochastic_enabled must be a bool, "
            f"got {type(value).__name__}."
        )
    return bool(value)


def _require_family_district_heating_share(settings: Any) -> float:
    """
    District-heating share reshapes the EC/DH teacher demand split and coupled
    costs. Include the live share in the hashed signature so a share change
    cannot reuse models trained under a different bus mix.
    """
    district_heating = getattr(settings, "district_heating", None)
    if district_heating is None:
        raise ValueError(
            "[learning.families] settings.district_heating is required for family identity "
            "because teacher labels depend on district_heating.share."
        )
    if not hasattr(district_heating, "share"):
        raise ValueError(
            "[learning.families] settings.district_heating.share is required for family identity."
        )
    share = float(getattr(district_heating, "share"))
    if share < 0.0 or share > 1.0:
        raise ValueError(
            "[learning.families] settings.district_heating.share must be in [0, 1], "
            f"got {share}."
        )
    return share


def build_family(settings: Any, provenance: Dict[str, Any] | None = None) -> FamilySpec:
    engine = getattr(settings, "engine", None)
    run = getattr(settings, "run", None)
    surrogate = getattr(settings, "surrogate", None)
    surrogate_train = getattr(settings, "surrogate_train", None)
    market = getattr(settings, "market", None)
    # Read identity-critical dispatch/DH Settings fields fail-fast before hashing.
    # Sibling of the thermal.delta_T / market.active_tariff_arm identity fix:
    # registry selection keys only on family_hash, and choose_artifact_path prefers
    # the resolved registry artifact over the signature-scoped path, so any
    # teacher-label-changing contract field omitted here becomes silent reuse.
    dispatch_mode = _require_family_dispatch_mode(settings)
    dispatch_horizon_h = _require_family_dispatch_horizon_h(settings)
    dispatch_stochastic_enabled = _require_family_dispatch_stochastic_enabled(settings)
    district_heating_share = _require_family_district_heating_share(settings)

    system = {
        "system_id": str(getattr(engine, "system_id", "unknown")),
    }
    input_schema = {
        "names": list(getattr(settings.bounds, "names", []) or []),
        "count": int(len(getattr(settings.bounds, "names", []) or [])),
    }
    feature_schema = {
        "names": list(resolve_feature_names(settings)),
        "encoding": dict(resolve_feature_encoding(settings)),
    }
    target_names = list(resolve_surrogate_targets(settings))
    target_schema = {
        "names": target_names,
        "count": int(len(target_names)),
        "blocks": [],
    }
    search_space = {
        "names": list(getattr(settings.bounds, "names", []) or []),
        "steps": [float(x) for x in list(getattr(settings.bounds, "steps", []) or [])],
        "caps": {
            str(k): float(v)
            for k, v in dict(getattr(settings.bounds, "caps", {}) or {}).items()
        },
    }
    training_spec = {
        "model_name": str(getattr(surrogate, "model", "unknown")),
        "model_params": _normalize_model_params(getattr(surrogate_train, "model_params", {}) or {}),
    }
    time_model = {
        "resolution": str(getattr(getattr(settings, "learning", None), "resolution", "1h")),
        "horizon_type": str(getattr(getattr(settings, "learning", None), "horizon_type", "full_year")),
        "time_series_schema": list(getattr(getattr(settings, "learning", None), "time_series_schema", []) or []),
        "location_mode": str(getattr(getattr(settings, "learning", None), "location_mode", "dataset_context")),
    }
    # learning.dispatch_model_id remains an explicit manual discriminator, but the
    # live Settings contract below must also be hashed: leaving dispatch_model_id
    # at its default "default" while changing mode/horizon/stochastic/share is the
    # concrete silent-reuse trigger this fix closes.
    dispatch_signature = {
        "dispatch_model_id": str(getattr(getattr(settings, "learning", None), "dispatch_model_id", "default")),
        "dispatch_mode": dispatch_mode,
        "dispatch_horizon_h": int(dispatch_horizon_h),
        "dispatch_stochastic_enabled": bool(dispatch_stochastic_enabled),
        "district_heating_share": float(district_heating_share),
        "dispatch_params": {
            "delta_T": 0.0,
        },
    }
    spec = FamilySpec(
        system=system,
        input_schema=input_schema,
        feature_schema=feature_schema,
        target_schema=target_schema,
        search_space=search_space,
        training_spec=training_spec,
        time_model=time_model,
        dispatch_signature=dispatch_signature,
        provenance={
            "run_tag": str(getattr(run, "tag", "") or ""),
            "active_tariff_arm": str(getattr(market, "active_tariff_arm", "flat")),
            **dict(provenance or {}),
        },
    )
    family_payload = {
        "system": system,
        "input_schema": input_schema,
        "feature_schema": feature_schema,
        "target_schema": target_schema,
        "time_model": time_model,
        "dispatch_signature": dispatch_signature,
    }
    spec.family_hash = _stable_hash(family_payload)
    return spec
