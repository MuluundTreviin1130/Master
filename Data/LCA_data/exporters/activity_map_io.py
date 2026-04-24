from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, Optional, TypedDict


class ProcSpec(TypedDict, total=False):
    db: str
    code: str
    amount: float


class TechSpec(TypedDict, total=False):
    infra: ProcSpec
    op: ProcSpec


def _normalize_procspec(spec: dict) -> Optional[ProcSpec]:
    db = str(spec.get("db", "")).strip()
    code = str(spec.get("code", "")).strip()
    amount = float(spec.get("amount", 1.0))
    
    # Debug: Zeige was geladen wird
    print(f"    _normalize_procspec: spec={spec}")
    print(f"    _normalize_procspec: amount from spec={spec.get('amount')}, normalized={amount}")
    
    if not db or not code:
        return None
    result = {"db": db, "code": code, "amount": amount}
    print(f"    _normalize_procspec: returning {result}")
    return result


def load_activity_map(path: Path) -> Dict[str, TechSpec]:
    raw = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict) or not raw:
        raise ValueError(f"activity_map.json must be a non-empty object: {path}")

    print(f"[DEBUG] Loading activity_map from: {path}")
    print(f"[DEBUG] Raw JSON for BESS: {raw.get('BESS', {})}")

    out: Dict[str, TechSpec] = {}
    for tech, spec in raw.items():
        if not isinstance(spec, dict):
            raise ValueError(f"Invalid spec for tech '{tech}': {spec}")

        print(f"[DEBUG] Processing tech: {tech}, spec: {spec}")

        tech_spec: TechSpec = {}
        if "infra" in spec and isinstance(spec["infra"], dict):
            print(f"[DEBUG] Processing infra for {tech}: {spec['infra']}")
            v = _normalize_procspec(spec["infra"])
            if v:
                tech_spec["infra"] = v
                print(f"[DEBUG] After _normalize_procspec infra: {tech_spec.get('infra')}")

        if "op" in spec and isinstance(spec["op"], dict):
            print(f"[DEBUG] Processing op for {tech}: {spec['op']}")
            v = _normalize_procspec(spec["op"])
            if v:
                tech_spec["op"] = v

        # allow empty tech_spec for smoke test (will become zeros)
        out[str(tech)] = tech_spec
        print(f"[DEBUG] Final tech_spec for {tech}: {tech_spec}")

    return out
