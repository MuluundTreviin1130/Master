from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any, Dict


def _iso_now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _json_default(value: Any) -> Any:
    if isinstance(value, Path):
        return str(value)
    raise TypeError(f"Object of type {type(value).__name__} is not JSON serializable")


def _read_json(path: Path) -> Dict[str, Any]:
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return payload if isinstance(payload, dict) else {}


def write_run_metrics(run_dir: str | Path, payload: Dict[str, Any]) -> Path:
    path = Path(run_dir) / "run_metrics.json"
    merged = dict(_read_json(path))
    merged.update(payload or {})
    merged["updated_at"] = _iso_now()
    path.write_text(json.dumps(merged, indent=2, ensure_ascii=False, default=_json_default), encoding="utf-8")
    return path
