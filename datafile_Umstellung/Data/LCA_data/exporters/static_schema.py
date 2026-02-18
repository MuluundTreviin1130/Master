from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Optional


def _meta(act: Any) -> Dict[str, Any]:
    return {
        "name": act.get("name"),
        "reference_product": act.get("reference product"),
        "location": act.get("location"),
        "unit": act.get("unit"),
    }


def make_static_payload(
    *,
    tech: str,
    infra: Dict[str, float],
    op: Dict[str, float],
    infra_activity: Optional[Dict[str, Any]] = None,
    op_activity: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    payload: Dict[str, Any] = {
        "tech": tech,
        "infra": {k: float(v) for k, v in infra.items()},
        "op": {k: float(v) for k, v in op.items()},
    }
    if infra_activity:
        payload["infra_activity"] = infra_activity
    if op_activity:
        payload["op_activity"] = op_activity
    return payload


def write_json(path: Path, payload: Dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
