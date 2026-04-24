from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict


def save_registry(path: str | Path, payload: Dict[str, Any]) -> Path:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    return p

