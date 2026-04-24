from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Tuple

current = Path(__file__).resolve()
project_root = None
for parent in current.parents:
    if (parent / "Learning").is_dir() and (parent / "Optimization").is_dir():
        project_root = parent
        break
if project_root is None:
    raise RuntimeError(f"[classify_legacy] Project root not found from {current}")
project_root_str = str(project_root.resolve())
if project_root_str not in sys.path:
    sys.path.insert(0, project_root_str)

from Learning.families.build_family import build_family
from Learning.registry.save_registry import save_registry
from Settings.get_settings import get_settings


def _load_json(path: Path) -> Dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _ratio(shared: int, total: int) -> float:
    if total <= 0:
        return 1.0
    return float(shared) / float(total)


def _schema_stats(current_names: List[str], legacy_names: List[str]) -> Dict[str, Any]:
    cur = list(current_names or [])
    old = list(legacy_names or [])
    cur_set = set(cur)
    old_set = set(old)
    shared = sorted(cur_set & old_set)
    return {
        "current_count": len(cur),
        "legacy_count": len(old),
        "shared_count": len(shared),
        "shared_names": shared,
        "current_coverage": _ratio(len(shared), len(cur_set)),
        "legacy_coverage": _ratio(len(shared), len(old_set)),
        "exact_match": cur == old,
    }


def _classify_record(record: Dict[str, Any], current_family: Dict[str, Any]) -> Tuple[str, Dict[str, Any]]:
    if record.get("status") == "unreadable":
        return "obsolete", {"reason": "unreadable"}

    current_system = str(current_family.get("system", {}).get("system_id", ""))
    legacy_system = str(record.get("system_id", "") or "")
    input_stats = _schema_stats(current_family.get("input_schema", {}).get("names", []), record.get("input_names", []))
    feature_stats = _schema_stats(current_family.get("feature_schema", {}).get("names", []), record.get("feature_names", []))
    target_stats = _schema_stats(current_family.get("target_schema", {}).get("names", []), record.get("targets", []))

    same_system = current_system == legacy_system and current_system != ""
    exact_core_match = same_system and input_stats["exact_match"] and feature_stats["exact_match"] and target_stats["exact_match"]
    strong_schema_match = (
        same_system
        and input_stats["current_coverage"] >= 0.8
        and feature_stats["current_coverage"] >= 0.7
        and target_stats["current_coverage"] >= 0.7
    )
    partial_schema_match = (
        same_system
        and input_stats["shared_count"] > 0
        and (feature_stats["shared_count"] > 0 or target_stats["shared_count"] > 0)
    )

    if exact_core_match:
        status = "bootstrap_candidate"
        reason = "exact_core_match"
    elif strong_schema_match:
        status = "importable_with_mapping"
        reason = "strong_schema_match"
    elif partial_schema_match:
        status = "reference_only"
        reason = "partial_schema_match"
    else:
        status = "obsolete"
        reason = "schema_mismatch"

    details = {
        "reason": reason,
        "same_system": same_system,
        "input_match": input_stats,
        "feature_match": feature_stats,
        "target_match": target_stats,
    }
    return status, details


def classify_legacy_inventory(inventory_path: Path, settings_overrides: Dict[str, Any] | None = None) -> Dict[str, Any]:
    inventory = _load_json(inventory_path)
    settings = get_settings(settings_overrides or {})
    family = build_family(settings).to_dict()

    classified: List[Dict[str, Any]] = []
    counts: Dict[str, int] = {
        "bootstrap_candidate": 0,
        "importable_with_mapping": 0,
        "reference_only": 0,
        "obsolete": 0,
    }
    for record in list(inventory.get("legacy_artifacts", []) or []):
        status, details = _classify_record(record, family)
        counts[status] = counts.get(status, 0) + 1
        enriched = dict(record)
        enriched["legacy_status"] = status
        enriched["match_details"] = details
        classified.append(enriched)

    top_candidates = [
        {
            "signature_hash": r.get("signature_hash"),
            "source_path": r.get("source_path"),
            "legacy_status": r.get("legacy_status"),
        }
        for r in classified
        if r.get("legacy_status") in {"bootstrap_candidate", "importable_with_mapping"}
    ]

    return {
        "current_family": family,
        "summary": counts,
        "top_candidates": top_candidates,
        "legacy_artifacts": classified,
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--inventory", default="Learning/bootstrap/legacy_inventory.json")
    ap.add_argument("--output", default="Learning/bootstrap/legacy_classification.json")
    ap.add_argument("--overrides-json", default="")
    args = ap.parse_args()

    overrides: Dict[str, Any] | None = None
    if args.overrides_json:
        overrides = _load_json(Path(args.overrides_json))
    payload = classify_legacy_inventory(Path(args.inventory), settings_overrides=overrides)
    out = save_registry(args.output, payload)
    print(out)


if __name__ == "__main__":
    main()
