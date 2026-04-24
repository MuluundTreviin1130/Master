from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict

from Learning.registry.load_registry import load_registry
from Learning.registry.save_registry import save_registry


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
    if extra_fields:
        entry.update(dict(extra_fields))
    entry["updated_at_utc"] = now
    family_models[model_id] = entry

    family_entry = families.setdefault(family_hash, {})
    if is_preferred is True:
        family_entry["preferred_model_id"] = model_id
        family_entry["updated_at_utc"] = now
    elif is_preferred is False and family_entry.get("preferred_model_id") == model_id:
        family_entry["preferred_model_id"] = None
        family_entry["updated_at_utc"] = now

    save_registry(registry_path, registry)
    return entry, registry_path
