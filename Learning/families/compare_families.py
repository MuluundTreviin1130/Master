from __future__ import annotations

from dataclasses import asdict
from typing import Any, Dict, List


FAMILY_KEYS = [
    "system",
    "input_schema",
    "feature_schema",
    "target_schema",
    "time_model",
    "dispatch_signature",
]
REFIT_KEYS: List[str] = []
APPEND_KEYS = [
    "search_space",
]
PROVENANCE_KEYS = [
    "provenance",
]


def _to_dict(spec: Any) -> Dict[str, Any]:
    if isinstance(spec, dict):
        return dict(spec)
    if hasattr(spec, "to_dict"):
        return spec.to_dict()
    return asdict(spec)


def compare_families(current: Any, existing: Any) -> Dict[str, List[str]]:
    cur = _to_dict(current)
    old = _to_dict(existing)

    def _changed(keys: List[str]) -> List[str]:
        return [key for key in keys if cur.get(key) != old.get(key)]

    return {
        "family_changed": _changed(FAMILY_KEYS),
        "append_changed": _changed(APPEND_KEYS),
        "refit_changed": _changed(REFIT_KEYS),
        "provenance_changed": _changed(PROVENANCE_KEYS),
    }
