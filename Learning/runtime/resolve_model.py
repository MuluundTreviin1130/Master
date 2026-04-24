from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, Optional

from Learning.registry.load_registry import load_registry
from Learning.families.build_family import build_family


def _model_path_from_entry(entry: Dict[str, Any]) -> Optional[Path]:
    artifact_path = entry.get("artifact_path")
    if artifact_path:
        return Path(str(artifact_path))
    legacy_source = entry.get("legacy_source_path")
    if legacy_source:
        meta_path = Path(str(legacy_source))
        return meta_path.with_name(meta_path.name.replace(".meta.json", ".joblib"))
    return None


def _is_validated_native(entry: Dict[str, Any]) -> bool:
    stage = str(entry.get("validation_stage", "") or "").strip().lower()
    return stage in {"validated", "production"}


def _is_native_training(entry: Dict[str, Any]) -> bool:
    return str(entry.get("source", "")).strip().lower() == "native_training"


def _is_optimization_eligible_native(entry: Dict[str, Any]) -> bool:
    stage = str(entry.get("validation_stage", "") or "").strip().lower()
    return stage in {"eligible", "validated", "production"}


def _validation_forced_model_id(settings: Any) -> Optional[str]:
    holdout = getattr(getattr(settings, "validation", None), "holdout", None)
    if holdout is None:
        return None
    value = str(getattr(holdout, "model_id", "") or "").strip()
    return value or None


def _validation_forced_artifact_path(settings: Any) -> Optional[Path]:
    holdout = getattr(getattr(settings, "validation", None), "holdout", None)
    if holdout is None:
        return None
    value = str(getattr(holdout, "artifact_path", "") or "").strip()
    return Path(value) if value else None


def resolve_model(settings: Any) -> Dict[str, Any]:
    learning = getattr(settings, "learning", None)
    registry_path = getattr(learning, "registry_path", "Learning/registry/registry.json")
    registry = load_registry(registry_path)

    spec = build_family(settings)
    family_hash = spec.family_hash
    families = registry.get("families", {}) or {}
    models = registry.get("models", {}) or {}
    family_entry = families.get(family_hash, {}) or {}
    family_models = models.get(family_hash, {}) or {}

    forced_model_id = _validation_forced_model_id(settings)
    if forced_model_id:
        entry = dict(family_models.get(forced_model_id, {}) or {})
        path = _model_path_from_entry(entry) if entry else None
        return {
            "family_hash": family_hash,
            "model_id": forced_model_id,
            "entry": entry or None,
            "artifact_path": path,
            "found": bool(path and path.exists()),
            "forced": True,
        }

    forced_artifact_path = _validation_forced_artifact_path(settings)
    if forced_artifact_path is not None:
        return {
            "family_hash": family_hash,
            "model_id": None,
            "entry": None,
            "artifact_path": forced_artifact_path,
            "found": bool(forced_artifact_path.exists()),
            "forced": True,
        }

    preferred_native_id = family_entry.get("preferred_model_id")
    if preferred_native_id and preferred_native_id in family_models:
        entry = dict(family_models[preferred_native_id])
        path = _model_path_from_entry(entry)
        if _is_optimization_eligible_native(entry):
            return {
                "family_hash": family_hash,
                "model_id": preferred_native_id,
                "entry": entry,
                "artifact_path": path,
                "found": bool(path and path.exists()),
                "forced": False,
            }
        if _is_native_training(entry):
            preferred_native_id = None

    active_native = [
        (model_id, dict(entry))
        for model_id, entry in family_models.items()
        if (
            bool(entry.get("is_active"))
            and _is_native_training(entry)
            and _is_optimization_eligible_native(entry)
        )
    ]
    for model_id, entry in active_native:
        path = _model_path_from_entry(entry)
        if path and path.exists():
            return {
                "family_hash": family_hash,
                "model_id": model_id,
                "entry": entry,
                "artifact_path": path,
                "found": True,
                "forced": False,
            }

    preferred_bootstrap_id = family_entry.get("preferred_bootstrap_model_id")
    if preferred_bootstrap_id and preferred_bootstrap_id in family_models:
        entry = dict(family_models[preferred_bootstrap_id])
        path = _model_path_from_entry(entry)
        return {
            "family_hash": family_hash,
            "model_id": preferred_bootstrap_id,
            "entry": entry,
            "artifact_path": path,
            "found": bool(path and path.exists()),
            "forced": False,
        }

    for model_id, entry in family_models.items():
        if _is_native_training(entry) and not _is_optimization_eligible_native(entry):
            continue
        path = _model_path_from_entry(entry)
        if path and path.exists():
            return {
                "family_hash": family_hash,
                "model_id": model_id,
                "entry": dict(entry),
                "artifact_path": path,
                "found": True,
                "forced": False,
            }

    return {
        "family_hash": family_hash,
        "model_id": None,
        "entry": None,
        "artifact_path": None,
        "found": False,
        "forced": False,
    }
