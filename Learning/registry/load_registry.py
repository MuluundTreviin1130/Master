from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict


def load_registry(path: str | Path) -> Dict[str, Any]:
    p = Path(path)
    if not p.exists():
        return {"families": {}, "models": {}, "datasets": {}}
    return json.loads(p.read_text(encoding="utf-8"))

