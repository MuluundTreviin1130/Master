from __future__ import annotations

import hashlib
import json
from typing import Any, Dict


def _sha1_hex(payload: Dict[str, Any]) -> str:
    data = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return hashlib.sha1(data.encode("utf-8")).hexdigest()


def get_profile_id(profiles: Dict[str, Any], settings: Any) -> str:
    # Try explicit meta fields first
    meta = profiles.get("meta") if isinstance(profiles, dict) else None
    if isinstance(meta, dict):
        for k in ("profile_id", "dataset_id", "source_id", "version"):
            v = meta.get(k)
            if isinstance(v, str) and v.strip():
                return v

    eng = getattr(settings, "engine", None)
    location = getattr(eng, "location", None) or getattr(settings, "location", None)
    data = getattr(settings, "data", None)
    data_source = getattr(data, "source", None) if data is not None else None

    # Deterministic fallback: hash lightweight identifiers (no raw arrays)
    keys = []
    if isinstance(profiles, dict):
        keys = sorted([k for k in profiles.keys() if k not in {"load", "timestamps"}])
    payload = {
        "location": str(location or "unknown"),
        "data_source": str(data_source or "unknown"),
        "profile_keys": keys,
        "n_profiles": int(len(keys)),
    }
    return _sha1_hex(payload)

