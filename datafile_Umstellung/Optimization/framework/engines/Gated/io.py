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
      Optimization/run/artifacts/surrogates/<signature_hash>/surrogate_rf.joblib
    Also copies meta.json and writes a small provenance.txt.
    """
    if not signature_hash:
        return None
    joblib_path = source_dir / "surrogate_rf.joblib"
    meta_path = source_dir / "meta.json"
    if not joblib_path.exists() or not meta_path.exists():
        return None

    base = Path("Optimization") / "run" / "artifacts" / "surrogates" / str(signature_hash)
    base.mkdir(parents=True, exist_ok=True)

    shutil.copy2(str(joblib_path), str(base / joblib_path.name))
    shutil.copy2(str(meta_path), str(base / meta_path.name))

    provenance = {
        "source_run_dir": str(run_dir or ""),
        "source_dir": str(source_dir),
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
    }
    (base / "provenance.txt").write_text(json.dumps(provenance, indent=2), encoding="utf-8")
    return base

