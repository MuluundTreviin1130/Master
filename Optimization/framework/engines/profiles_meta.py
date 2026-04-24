from __future__ import annotations

import hashlib
import json
from typing import Any, Dict
import numpy as np


def _sha1_hex(payload: Dict[str, Any]) -> str:
    data = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return hashlib.sha1(data.encode("utf-8")).hexdigest()


def _array_fingerprint(v: Any) -> str:
    """Stable hash for numeric profile arrays (shape + values)."""
    a = np.asarray(v)
    if a.size == 0:
        return "empty"
    if not np.issubdtype(a.dtype, np.number):
        # Non-numeric arrays should not drive surrogate compatibility.
        return "non_numeric"
    a = np.asarray(a, dtype=np.float64)
    return hashlib.sha1(a.tobytes()).hexdigest()


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
    profile_fingerprint = {}
    if isinstance(profiles, dict):
        keys = sorted([k for k in profiles.keys() if k not in {"load", "timestamps"}])
        # Include content-derived fingerprint for key time-series that affect dispatch.
        for k in ("pv_generation", "T_outdoor", "irradiance", "solargains", "min_SOC", "availability_profile", "driving_profile"):
            if k in profiles:
                try:
                    profile_fingerprint[k] = _array_fingerprint(profiles[k])
                except Exception:
                    profile_fingerprint[k] = "error"
    payload = {
        "location": str(location or "unknown"),
        "data_source": str(data_source or "unknown"),
        "profile_keys": keys,
        "n_profiles": int(len(keys)),
        "profile_fingerprint": profile_fingerprint,
    }
    return _sha1_hex(payload)
