from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict


def pedigree_root() -> Path:
    return Path(__file__).resolve().parent


def country_dir(country: str) -> Path:
    return pedigree_root() / str(country)


def record_path(country: str, tech_key: str) -> Path:
    return country_dir(country) / f"{tech_key}.json"


def load_record(country: str, tech_key: str) -> Dict[str, Any]:
    path = record_path(country, tech_key)
    if not path.exists():
        raise FileNotFoundError(f"[pedigree] record not found: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def load_all_records(country: str) -> Dict[str, Dict[str, Any]]:
    root = country_dir(country)
    if not root.exists():
        raise FileNotFoundError(f"[pedigree] country directory not found: {root}")
    out: Dict[str, Dict[str, Any]] = {}
    for path in sorted(root.glob("*.json")):
        out[path.stem] = json.loads(path.read_text(encoding="utf-8"))
    return out
