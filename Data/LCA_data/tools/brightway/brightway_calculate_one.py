from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Dict, Tuple, List

import bw2data as bd
from bw2calc import LCA


def load_method_map(path: Path) -> Dict[str, Tuple[str, str, str]]:
    """Lade die Method-Map aus JSON."""
    raw = json.loads(path.read_text(encoding="utf-8"))
    mm = raw.get("method_map", {})
    out: Dict[str, Tuple[str, str, str]] = {}
    for k, v in mm.items():
        out[k] = (v[0], v[1], v[2])
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--project", default="my_lca_project")
    ap.add_argument("--db", default="ecoinvent 3.11 cutoff")
    ap.add_argument("--code", default="ead5c66a75c3ed5d381399f50b927e47")
    args = ap.parse_args()

    bd.projects.set_current(args.project)

    key = (args.db, args.code)
    act = bd.get_activity(key)

    categories_path = Path(__file__).resolve().parents[2] / "categories.json"
    cats = json.loads(categories_path.read_text(encoding="utf-8"))["categories"]
    cat_keys = [c["key"] for c in cats]

    method_map_path = Path(__file__).resolve().parents[2] / "mappings" / "method_map_efv3_noLT.json"
    if not method_map_path.exists():
        method_map_path = Path(__file__).resolve().parents[2] / "mappings" / "method_map_efv3.json"
    methods_by_cat = load_method_map(method_map_path)
    print(f"Loaded method map from: {method_map_path.name}")

    print("ACTIVITY")
    print(" Name:", act["name"])
    print(" Location:", act["location"])
    print(" Unit:", act["unit"])
    print(" Reference product:", act.get("reference product", "?"))
    print(" Key:", act.key)
    
    bio_count = sum(1 for _ in act.biosphere())
    print(f" Biosphere flows: {bio_count}")
    
    if bio_count == 0:
        print(" WARNING: This is a market activity with no direct biosphere flows.")
        print(" Use brightway_search.py to find production activities.")
    
    prod_exchanges = [e for e in act.exchanges() if e.get("type") == "production"]
    print(f" Production exchanges: {len(prod_exchanges)}")
    
    tech_inputs = list(act.technosphere())
    print(f" Technosphere inputs: {len(tech_inputs)}")

    print("\nLCIA (per 1 unit of reference product)\n")

    fu = {act: 1.0}
    print(f"Using activity: {act.key}")
    
    if cat_keys and cat_keys[0] in methods_by_cat:
        test_method = methods_by_cat[cat_keys[0]]
        try:
            test_lca = LCA(fu, method=test_method)
            test_lca.lci()
            inventory_size = len(test_lca.inventory) if hasattr(test_lca, 'inventory') else 0
            print(f"LCI calculation successful. Inventory size: {inventory_size}")
        except Exception as e:
            print(f"ERROR in LCI calculation: {e}")

    for ck in cat_keys:
        if ck not in methods_by_cat:
            print(f"{ck:28s}  WARNING: No method mapping found")
            continue
            
        method = methods_by_cat[ck]
        try:
            lca = LCA(fu, method=method)
            lca.lci()
            lca.lcia()
            score = float(lca.score)
            print(f"{ck:28s}  score = {score:g}   method = {method}")
        except Exception as e:
            print(f"{ck:28s}  ERROR: {e}   method = {method}")


if __name__ == "__main__":
    main()
