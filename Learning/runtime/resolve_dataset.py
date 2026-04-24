from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, Optional

from Learning.families.build_family import build_family
from Learning.registry.load_registry import load_registry


def _dataset_path_from_entry(entry: Dict[str, Any]) -> Optional[Path]:
    artifact_path = entry.get("artifact_path")
    if artifact_path:
        return Path(str(artifact_path))
    return None


def resolve_dataset(settings: Any) -> Dict[str, Any]:
    learning = getattr(settings, "learning", None)
    registry_path = getattr(learning, "registry_path", "Learning/registry/registry.json")
    registry = load_registry(registry_path)

    spec = build_family(settings)
    family_hash = spec.family_hash
    families = registry.get("families", {}) or {}
    datasets = registry.get("datasets", {}) or {}
    family_entry = families.get(family_hash, {}) or {}
    family_datasets = datasets.get(family_hash, {}) or {}

    preferred_id = family_entry.get("preferred_dataset_id")
    if preferred_id and preferred_id in family_datasets:
        entry = dict(family_datasets[preferred_id])
        path = _dataset_path_from_entry(entry)
        return {
            "family_hash": family_hash,
            "dataset_id": preferred_id,
            "entry": entry,
            "artifact_path": path,
            "found": bool(path and path.exists()),
        }

    for dataset_id, entry in family_datasets.items():
        path = _dataset_path_from_entry(entry)
        if path and path.exists():
            return {
                "family_hash": family_hash,
                "dataset_id": dataset_id,
                "entry": dict(entry),
                "artifact_path": path,
                "found": True,
            }

    return {
        "family_hash": family_hash,
        "dataset_id": None,
        "entry": None,
        "artifact_path": None,
        "found": False,
    }
