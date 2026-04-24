from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict

from Learning.families.build_family import build_family
from Learning.registry.load_registry import load_registry
from Learning.registry.save_registry import save_registry


def register_family(settings: Any, provenance: Dict[str, Any] | None = None):
    spec = build_family(settings, provenance=provenance)
    registry_path = getattr(getattr(settings, "learning", None), "registry_path", "Learning/registry/registry.json")
    registry = load_registry(registry_path)
    families = registry.setdefault("families", {})
    now = datetime.now(timezone.utc).isoformat()
    entry = families.get(spec.family_hash, {})
    entry["family_hash"] = spec.family_hash
    entry["updated_at_utc"] = now
    if "spec" not in entry:
        entry["spec"] = spec.to_dict()
    entry["last_seen_spec"] = spec.to_dict()
    if "created_at_utc" not in entry:
        entry["created_at_utc"] = now
    families[spec.family_hash] = entry
    save_registry(registry_path, registry)
    return spec, registry_path
