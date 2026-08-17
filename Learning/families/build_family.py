from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass, field, is_dataclass
from typing import Any, Dict, List

from Optimization.framework.engines.Surrogat_model.features import (
    engine_feature_policy_identity,
    heating_control_policy_identity,
    resolve_feature_encoding,
    resolve_feature_names,
    resolve_surrogate_targets,
    thermflex_event_response_policy_identity,
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


def build_family(settings: Any, provenance: Dict[str, Any] | None = None) -> FamilySpec:
    engine = getattr(settings, "engine", None)
    run = getattr(settings, "run", None)
    surrogate = getattr(settings, "surrogate", None)
    surrogate_train = getattr(settings, "surrogate_train", None)
    market = getattr(settings, "market", None)

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
    # Heating-control setpoints/modes change ThermFlex/EC teacher KPIs under an
    # otherwise identical design space and feature-name schema. Keep the live
    # values inside the hashed family payload so 22.0 vs 22.5 (or constant vs
    # day_night) cannot silently reuse one dataset/model family. Sibling of the
    # ThermFlex envelope identity fields (constant_lower / duration / events).
    #
    # Event-response bounds are a separate Vienna-paper policy cut: Settings
    # defaults keep ``use_event_response_bounds=False`` while paper cases set
    # ``True``. That must also participate in family identity (distinct from
    # open PR #39 envelope lowers).
    #
    # SH/GIW arms also toggle engine feature flags (e.g. enable_thermflex tf0/tf1)
    # without changing feature *names*; hash those live values too so arm cuts
    # cannot share one cached teacher family.
    dispatch_signature = {
        "dispatch_model_id": str(getattr(getattr(settings, "learning", None), "dispatch_model_id", "default")),
        "dispatch_params": {
            "delta_T": 0.0,
            **engine_feature_policy_identity(settings),
            **heating_control_policy_identity(settings),
            **thermflex_event_response_policy_identity(settings),
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
