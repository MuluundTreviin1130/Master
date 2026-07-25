from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict

from Learning.registry.load_registry import load_registry
from Learning.registry.save_registry import save_registry


def _is_native_training(entry: Dict[str, Any]) -> bool:
    # Native optimization surrogates are the only models that compete in
    # resolve_model's active-native fallback. Keep peer deactivation scoped
    # to that source so ThermFlex / bootstrap entries stay untouched.
    return str(entry.get("source", "")).strip().lower() == "native_training"


def update_model_status(
    settings: Any,
    family_hash: str,
    model_id: str,
    *,
    validation_stage: str | None = None,
    is_active: bool | None = None,
    is_preferred: bool | None = None,
    extra_fields: Dict[str, Any] | None = None,
):
    registry_path = getattr(getattr(settings, "learning", None), "registry_path", "Learning/registry/registry.json")
    registry = load_registry(registry_path)
    models = registry.setdefault("models", {})
    families = registry.setdefault("families", {})
    family_models = models.setdefault(family_hash, {})
    if model_id not in family_models:
        raise KeyError(f"[learning] unknown model_id '{model_id}' for family '{family_hash}'.")

    now = datetime.now(timezone.utc).isoformat()
    entry = dict(family_models[model_id])
    if validation_stage is not None:
        entry["validation_stage"] = str(validation_stage)
    if is_active is not None:
        entry["is_active"] = bool(is_active)
    # Persist preference on the model entry itself. Family preferred_model_id
    # is the runtime selector, but entry.is_preferred must stay consistent for
    # audits and later status updates.
    if is_preferred is not None:
        entry["is_preferred"] = bool(is_preferred)
    if extra_fields:
        entry.update(dict(extra_fields))
    entry["updated_at_utc"] = now
    family_models[model_id] = entry

    family_entry = families.setdefault(family_hash, {})
    if is_preferred is True:
        family_entry["preferred_model_id"] = model_id
        family_entry["updated_at_utc"] = now
        # Preferring one native model must remove older active native peers from
        # the eligible pool. Otherwise resolve_model can still return a stale
        # peer when preferred_model_id is absent or the preferred artifact is
        # skipped, and insertion order silently wins.
        for peer_id, peer_entry in list(family_models.items()):
            if peer_id == model_id:
                continue
            if not _is_native_training(peer_entry):
                continue
            if not bool(peer_entry.get("is_active")):
                continue
            peer = dict(peer_entry)
            peer["is_active"] = False
            peer["is_preferred"] = False
            peer["updated_at_utc"] = now
            family_models[peer_id] = peer
    elif is_preferred is False and family_entry.get("preferred_model_id") == model_id:
        family_entry["preferred_model_id"] = None
        family_entry["updated_at_utc"] = now

    save_registry(registry_path, registry)
    return entry, registry_path
