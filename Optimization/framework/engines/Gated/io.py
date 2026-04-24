from __future__ import annotations

import csv
import json
import shutil
import time
from pathlib import Path
from typing import Any, Dict, Iterable


def append_csv(path: Path, header: Iterable[str], row: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    header_list = list(header)
    exists = path.exists()
    with path.open("a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=header_list, extrasaction="ignore")
        if not exists:
            writer.writeheader()
        ordered = {k: row.get(k, "") for k in header_list}
        writer.writerow(ordered)


def write_summary_line(run_dir: str | None, text: str) -> None:
    if not run_dir:
        return
    path = Path(run_dir) / "summary.txt"
    prefix = "" if not path.exists() else "\n"
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(prefix + text)


def update_manifest_json(run_dir: str | None, patch_dict: Dict[str, Any]) -> None:
    if not run_dir:
        return
    path = Path(run_dir) / "gating_manifest.json"
    if path.exists():
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            payload = {}
    else:
        payload = {}
    payload.update(patch_dict)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=True), encoding="utf-8")


def promote_surrogate_version(signature_hash: str, source_dir: Path, run_dir: str | None) -> Path | None:
    """
    Promote latest surrogate into signature-scoped baseline:
      Optimization/run/artifacts/surrogates/<signature_hash>/
    Uses the primary bundle when present and keeps legacy files for compatibility.
    """
    if not signature_hash:
        return None
    primary_joblib = source_dir / "surrogate_bundle.joblib"
    legacy_joblib = source_dir / "surrogate_rf.joblib"
    primary_meta = source_dir / "surrogate_bundle.meta.json"
    legacy_meta = source_dir / "surrogate_rf.meta.json"
    generic_meta = source_dir / "meta.json"

    if not primary_joblib.exists() and not legacy_joblib.exists():
        return None

    base = Path("Optimization") / "run" / "artifacts" / "surrogates" / str(signature_hash)
    base.mkdir(parents=True, exist_ok=True)

    if primary_joblib.exists():
        shutil.copy2(str(primary_joblib), str(base / primary_joblib.name))
    if legacy_joblib.exists():
        shutil.copy2(str(legacy_joblib), str(base / legacy_joblib.name))
    if primary_meta.exists():
        shutil.copy2(str(primary_meta), str(base / primary_meta.name))
    if legacy_meta.exists():
        shutil.copy2(str(legacy_meta), str(base / legacy_meta.name))
    if generic_meta.exists():
        shutil.copy2(str(generic_meta), str(base / generic_meta.name))

    provenance = {
        "source_run_dir": str(run_dir or ""),
        "source_dir": str(source_dir),
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
    }
    (base / "provenance.txt").write_text(json.dumps(provenance, indent=2), encoding="utf-8")
    return base
