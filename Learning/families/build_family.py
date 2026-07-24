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


def _require_family_delta_t(settings: Any) -> float:
    """
    ThermFlex/EC teacher labels depend on the comfort-band relaxation.
    Family identity must therefore read the live Settings SSOT value instead of
    a hardcoded placeholder; otherwise a changed delta_T silently reuses models.
    """
    thermal = getattr(settings, "thermal", None)
    if thermal is None:
        raise ValueError(
            "[learning.families] settings.thermal is required for family identity "
            "because teacher labels depend on thermal.delta_T."
        )
    if not hasattr(thermal, "delta_T"):
        raise ValueError(
            "[learning.families] settings.thermal.delta_T is required for family identity."
        )
    return float(getattr(thermal, "delta_T"))


def _require_family_active_tariff_arm(settings: Any) -> str:
    """
    Tariff-aware NPC and related economic targets change with the active arm.
    Keep the arm in the hashed dispatch signature so a tariff switch cannot reuse
    an incompatible dataset/model family as if nothing changed.
    """
    market = getattr(settings, "market", None)
    if market is None:
        raise ValueError(
            "[learning.families] settings.market is required for family identity "
            "because economic teacher labels depend on market.active_tariff_arm."
        )
    if not hasattr(market, "active_tariff_arm"):
        raise ValueError(
            "[learning.families] settings.market.active_tariff_arm is required for family identity."
        )
    active_tariff_arm = str(getattr(market, "active_tariff_arm") or "").strip().lower()
    if not active_tariff_arm:
        raise ValueError(
            "[learning.families] settings.market.active_tariff_arm must be a non-empty string."
        )
    return active_tariff_arm


def build_family(settings: Any, provenance: Dict[str, Any] | None = None) -> FamilySpec:
    engine = getattr(settings, "engine", None)
    run = getattr(settings, "run", None)
    surrogate = getattr(settings, "surrogate", None)
    surrogate_train = getattr(settings, "surrogate_train", None)
    # Read identity-critical Settings fields fail-fast before hashing.
    delta_T = _require_family_delta_t(settings)
    active_tariff_arm = _require_family_active_tariff_arm(settings)

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
    # delta_T and active_tariff_arm belong in the hashed signature because both
    # change teacher behavior/labels while leaving schema names unchanged.
    dispatch_signature = {
        "dispatch_model_id": str(getattr(getattr(settings, "learning", None), "dispatch_model_id", "default")),
        "dispatch_params": {
            "delta_T": float(delta_T),
        },
        "active_tariff_arm": active_tariff_arm,
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
            # Keep a human-readable copy in provenance; identity uses dispatch_signature.
            "active_tariff_arm": active_tariff_arm,
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
