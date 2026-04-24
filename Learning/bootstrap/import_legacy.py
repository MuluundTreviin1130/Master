from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Tuple

current = Path(__file__).resolve()
project_root = None
for parent in current.parents:
    if (parent / "Learning").is_dir() and (parent / "Optimization").is_dir():
        project_root = parent
        break
if project_root is None:
    raise RuntimeError(f"[import_legacy] Project root not found from {current}")
project_root_str = str(project_root.resolve())
if project_root_str not in sys.path:
    sys.path.insert(0, project_root_str)

from Learning.registry.load_registry import load_registry
from Learning.registry.register_family import register_family
from Learning.registry.register_model import register_model
from Learning.registry.save_registry import save_registry
from Settings.get_settings import get_settings


def _load_json(path: Path) -> Dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _candidate_rank(item: Dict[str, Any]) -> Tuple[int, int, int, int]:
    status = str(item.get("legacy_status", "reference_only"))
    priority = {
        "bootstrap_candidate": 0,
        "importable_with_mapping": 1,
        "reference_only": 2,
        "obsolete": 3,
    }.get(status, 9)
    details = item.get("match_details", {}) or {}
    input_shared = int(details.get("input_match", {}).get("shared_count", 0))
    feature_shared = int(details.get("feature_match", {}).get("shared_count", 0))
    target_shared = int(details.get("target_match", {}).get("shared_count", 0))
    return (priority, -input_shared, -feature_shared, -target_shared)


def import_legacy_models(classification_path: Path, settings_overrides: Dict[str, Any] | None = None) -> Dict[str, Any]:
    classification = _load_json(classification_path)
    settings = get_settings(settings_overrides or {})
    family_spec, registry_path = register_family(settings, provenance={"source": "legacy_import"})
    family_hash = family_spec.family_hash

    selected = [
        item
        for item in list(classification.get("legacy_artifacts", []) or [])
        if item.get("legacy_status") in {"bootstrap_candidate", "importable_with_mapping"}
    ]
    selected.sort(key=_candidate_rank)

    imported_models: List[Dict[str, Any]] = []
    preferred_model_id = None
    for index, item in enumerate(selected):
        signature_hash = str(item.get("signature_hash", "") or "")
        if not signature_hash:
            continue
        model_id = f"legacy_{signature_hash}"
        if preferred_model_id is None:
            preferred_model_id = model_id
        payload = {
            "source": "legacy_import",
            "backend_name": "rf",
            "legacy_status": item.get("legacy_status"),
            "legacy_signature_hash": signature_hash,
            "legacy_source_path": item.get("source_path"),
            "match_details": item.get("match_details", {}),
            "rank": index,
            "is_preferred_bootstrap": index == 0,
        }
        entry, _ = register_model(settings, family_hash, model_id, payload)
        imported_models.append(entry)

    registry = load_registry(registry_path)
    family_entry = registry.setdefault("families", {}).setdefault(family_hash, {})
    family_entry["preferred_bootstrap_model_id"] = preferred_model_id
    family_entry["bootstrap_model_ids"] = [row["model_id"] for row in imported_models]
    family_entry["updated_at_utc"] = datetime.now(timezone.utc).isoformat()
    save_registry(registry_path, registry)

    return {
        "family_hash": family_hash,
        "registry_path": registry_path,
        "preferred_bootstrap_model_id": preferred_model_id,
        "imported_model_count": len(imported_models),
        "imported_models": imported_models,
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--classification", default="Learning/bootstrap/legacy_classification.json")
    ap.add_argument("--output", default="Learning/bootstrap/legacy_import_manifest.json")
    ap.add_argument("--overrides-json", default="")
    args = ap.parse_args()

    overrides: Dict[str, Any] | None = None
    if args.overrides_json:
        overrides = _load_json(Path(args.overrides_json))
    payload = import_legacy_models(Path(args.classification), settings_overrides=overrides)
    out = save_registry(args.output, payload)
    print(out)


if __name__ == "__main__":
    main()
