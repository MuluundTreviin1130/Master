from __future__ import annotations

from pathlib import Path
from typing import Dict, Tuple, Optional

import bw2data as bd

from activity_map_io import TechSpec, ProcSpec
from static_schema import make_static_payload, write_json

# Import from calculators (ensure_lca_data_on_syspath() adds Data/LCA_data to sys.path)
from calculators.brightway_calculate_activity_ef16 import (
    calculate_ef16_for_activity,
    load_method_map,
    patch_sparse_A1,
)


def _zeros(methods: Dict[str, Tuple[str, str, str]]) -> Dict[str, float]:
    return {k: 0.0 for k in methods.keys()}


def _calc_block(methods, proc: Optional[ProcSpec]):
    if not proc:
        return None, _zeros(methods)

    key = (proc["db"], proc["code"])
    act = bd.get_activity(key)
    # Verwende proc["amount"] direkt, da ProcSpec amount definiert
    amount = float(proc["amount"]) if "amount" in proc else 1.0
    
    # Debug: Zeige was verwendet wird
    print(f"  Calculating for: {act.get('name', '?')}")
    print(f"    Amount from activity_map: {amount}")
    print(f"    Activity unit: {act.get('unit', '?')}")
    print(f"    Reference product: {act.get('reference product', '?')}")
    
    # Berechne mit amount (für die Umrechnung von Ecoinvent-Einheit auf Optimierungseinheit)
    # amount ist der Umrechnungsfaktor: z.B. 28000 kWh für 1 kWp, oder 6.29 kg für 1 kWh Kapazität
    # Die berechneten Werte sind bereits pro Optimierungseinheit (pro kWp bzw. pro kWh Kapazität)
    ef16 = calculate_ef16_for_activity(act, amount, methods)
    
    # Debug: Zeige einen Beispielwert
    if ef16:
        first_cat = next(iter(ef16.keys()))
        print(f"    Result for {first_cat} (per optimization unit): {ef16[first_cat]:.6e}")

    meta = {
        "activity_db": proc["db"],
        "activity_code": proc["code"],
        "amount": amount,
        **{
            "name": act.get("name"),
            "reference_product": act.get("reference product"),
            "location": act.get("location"),
            "unit": act.get("unit"),
        },
    }
    return meta, ef16


def export_from_activity_map(
    *,
    project: str,
    activity_map: Dict[str, TechSpec],
    method_map_path: Path,
    out_dir: Path,
    skip_existing: bool = True,
) -> None:
    patch_sparse_A1()
    bd.projects.set_current(project)

    methods = load_method_map(method_map_path)
    out_dir.mkdir(parents=True, exist_ok=True)

    for tech, spec in activity_map.items():
        out_path = out_dir / f"{tech}.json"
        if skip_existing and out_path.exists():
            print(f"[SKIP] {tech}: {out_path} already exists")
            continue

        print(f"\n[PROCESSING] {tech}")
        infra_meta, infra = _calc_block(methods, spec.get("infra"))
        op_meta, op = _calc_block(methods, spec.get("op"))

        payload = make_static_payload(
            tech=tech,
            infra=infra,
            op=op,
            infra_activity=infra_meta,
            op_activity=op_meta,
        )

        write_json(out_path, payload)
        print(f"[OK] {tech} -> wrote {out_path}")
