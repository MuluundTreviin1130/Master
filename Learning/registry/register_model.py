from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict

from Learning.registry.load_registry import load_registry
from Learning.registry.save_registry import save_registry


def register_model(settings: Any, family_hash: str, model_id: str, payload: Dict[str, Any]):
    registry_path = getattr(getattr(settings, "learning", None), "registry_path", "Learning/registry/registry.json")
    registry = load_registry(registry_path)
    models = registry.setdefault("models", {})
    families = registry.setdefault("families", {})
    family_models = models.setdefault(family_hash, {})
    now = datetime.now(timezone.utc).isoformat()
    entry = family_models.get(model_id, {})
    entry.update(payload)
    entry["model_id"] = model_id
    entry["family_hash"] = family_hash
    entry["updated_at_utc"] = now
    if "created_at_utc" not in entry:
        entry["created_at_utc"] = now
    family_models[model_id] = entry
    if bool(payload.get("is_preferred")):
        family_entry = families.setdefault(family_hash, {})
        family_entry["preferred_model_id"] = model_id
        family_entry["updated_at_utc"] = now
    save_registry(registry_path, registry)
    return entry, registry_path
