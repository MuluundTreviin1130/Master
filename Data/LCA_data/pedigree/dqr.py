from __future__ import annotations

from typing import Any, Dict

PEDIGREE_KEYS = [
    "reliability",
    "completeness",
    "technological_representativeness",
    "geographical_representativeness",
    "temporal_representativeness",
]


def extract_scores(record: Dict[str, Any]) -> Dict[str, int]:
    scores = dict(record.get("pedigree_scores", {}) or {})
    out: Dict[str, int] = {}
    missing = []
    for key in PEDIGREE_KEYS:
        value = scores.get(key, None)
        if value is None:
            missing.append(key)
            continue
        ivalue = int(value)
        if ivalue < 1 or ivalue > 5:
            raise ValueError(f"[pedigree] score '{key}' must be in [1, 5], got {ivalue}.")
        out[key] = ivalue
    if missing:
        raise ValueError(f"[pedigree] incomplete pedigree scores, missing: {missing}")
    return out


def compute_dqr_from_scores(scores: Dict[str, int]) -> float:
    values = [int(scores[k]) for k in PEDIGREE_KEYS]
    weakest = max(values)
    return float((sum(values) + weakest * 4) / 9.0)


def classify_dqr(dqr: float) -> str:
    if dqr < 1.6:
        return "high_quality"
    if dqr > 3.0:
        return "data_estimate"
    return "medium_quality"


def enrich_record_with_dqr(record: Dict[str, Any]) -> Dict[str, Any]:
    out = dict(record)
    scores = extract_scores(out)
    value = compute_dqr_from_scores(scores)
    out["dqr"] = {
        "formula": "(sum(scores) + weakest_score * 4) / 9",
        "value": value,
        "class": classify_dqr(value),
    }
    return out
