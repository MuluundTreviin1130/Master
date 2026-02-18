from __future__ import annotations

import hashlib
import json
from typing import Any, Dict, Iterable


def _stable_list(values: Iterable[Any]) -> list[Any]:
    return [v for v in values]


def build_signature_dict(cfg, surrogate_meta_hint: Dict[str, Any] | None = None, system_context: Dict[str, Any] | None = None) -> Dict[str, Any]:
    surrogate_meta_hint = surrogate_meta_hint or {}
    system_context = system_context or {}

    bounds = getattr(cfg, "bounds", None)
    objectives = getattr(cfg, "objectives", None)
    engine = getattr(cfg, "engine", None)
    train = getattr(cfg, "surrogate_train", None)

    input_names = _stable_list(getattr(bounds, "names", []) or [])
    target_names = _stable_list(
        surrogate_meta_hint.get("targets")
        or getattr(train, "targets", [])  # type: ignore[arg-type]
        or []
    )
    train_targets = _stable_list(getattr(train, "targets", []) or [])
    runtime_targets = _stable_list(system_context.get("runtime_targets", []) or [])
    feature_names = _stable_list(system_context.get("feature_names", []) or surrogate_meta_hint.get("feature_names", []) or [])
    feature_encoding = dict(system_context.get("feature_encoding", {}) or surrogate_meta_hint.get("feature_encoding", {}) or {})
    profile_id = system_context.get("profile_id") or surrogate_meta_hint.get("profile_id")
    system_id = system_context.get("system_id") or surrogate_meta_hint.get("system_id") or getattr(engine, "system_id", None)

    signature = {
        "input_schema": {
            "names": input_names,
            "count": int(len(input_names)),
            "dtypes": _stable_list(system_context.get("input_dtypes", [])),
        },
        "target_schema": {
            "names": target_names,
            "count": int(len(target_names)),
            "train_targets": train_targets,
            "runtime_targets": runtime_targets,
        },
        "feature_schema": {
            "names": feature_names,
            "encoding": feature_encoding,
        },
        "profile_id": str(profile_id or "unknown"),
        "system_id": str(system_id or "unknown"),
        "system_flags": {
            "system_id": str(getattr(engine, "system_id", "unknown")),
            "flags": dict(system_context.get("system_flags", {})),
        },
        "timeseries_id": str(system_context.get("timeseries_id") or getattr(engine, "location", "unknown")),
        "engine_version": str(system_context.get("engine_version") or "unknown"),
        "objectives": {
            "names": _stable_list(getattr(objectives, "names", []) or []),
            "minimize": _stable_list(getattr(objectives, "minimize", []) or []),
        },
    }
    return signature


def signature_hash(signature_dict: Dict[str, Any]) -> str:
    payload = json.dumps(signature_dict, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def is_compatible(current_hash: str, artifact_hash: str | None) -> bool:
    if not artifact_hash:
        return False
    return str(current_hash) == str(artifact_hash)


def summarize_mismatch(current_dict: Dict[str, Any], artifact_dict: Dict[str, Any] | None) -> str:
    if not artifact_dict:
        return "artifact signature missing"
    diffs: list[str] = []
    for k in sorted(set(current_dict.keys()) | set(artifact_dict.keys())):
        if current_dict.get(k) != artifact_dict.get(k):
            diffs.append(k)
    if not diffs:
        return "hash mismatch but no field diffs detected"
    return "mismatch fields: " + ", ".join(diffs[:8])

