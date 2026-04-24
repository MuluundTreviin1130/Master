from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, List

current = Path(__file__).resolve()
project_root = None
for parent in current.parents:
    if (parent / "Learning").is_dir() and (parent / "Optimization").is_dir():
        project_root = parent
        break
if project_root is None:
    raise RuntimeError(f"[scan_legacy] Project root not found from {current}")
project_root_str = str(project_root.resolve())
if project_root_str not in sys.path:
    sys.path.insert(0, project_root_str)

from Learning.registry.save_registry import save_registry


def _load_json(path: Path) -> Dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def scan_legacy_artifacts(artifacts_root: Path) -> List[Dict[str, Any]]:
    records: List[Dict[str, Any]] = []
    for meta_path in sorted(artifacts_root.rglob("surrogate_rf.meta.json")):
        try:
            meta = _load_json(meta_path)
        except Exception as exc:
            records.append(
                {
                    "source_path": str(meta_path),
                    "status": "unreadable",
                    "error": str(exc),
                }
            )
            continue
        sig = meta.get("signature_dict", {}) or {}
        records.append(
            {
                "source_path": str(meta_path),
                "status": "reference_only",
                "signature_hash": meta.get("signature_hash"),
                "system_id": meta.get("system_id"),
                "profile_id": meta.get("profile_id"),
                "targets": meta.get("targets", []),
                "feature_names": meta.get("feature_names", []),
                "input_names": sig.get("input_schema", {}).get("names", []),
                "engine_version": sig.get("engine_version"),
            }
        )
    return records


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--artifacts-root", default="Optimization/run/artifacts/surrogates")
    ap.add_argument("--output", default="Learning/bootstrap/legacy_inventory.json")
    args = ap.parse_args()

    payload = {
        "legacy_artifacts": scan_legacy_artifacts(Path(args.artifacts_root)),
    }
    out = save_registry(args.output, payload)
    print(out)


if __name__ == "__main__":
    main()
