from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from typing import Any, Dict


def save_registry(path: str | Path, payload: Dict[str, Any]) -> Path:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(payload, indent=2, ensure_ascii=False)
    tmp_path: Path | None = None

    try:
        # Write the full JSON to a sibling file first; replacing the registry is
        # then a single filesystem operation, so a killed process cannot leave a
        # truncated registry at the canonical path.
        with tempfile.NamedTemporaryFile(
            "w",
            encoding="utf-8",
            dir=str(p.parent),
            prefix=f".{p.name}.",
            suffix=".tmp",
            delete=False,
        ) as tmp:
            tmp.write(text)
            tmp.write("\n")
            tmp.flush()
            os.fsync(tmp.fileno())
            tmp_path = Path(tmp.name)
        os.replace(tmp_path, p)
    except Exception:
        if tmp_path is not None and tmp_path.exists():
            tmp_path.unlink()
        raise
    return p

