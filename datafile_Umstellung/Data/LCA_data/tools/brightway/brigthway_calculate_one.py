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
    ap.add_argument("--code", default="b47a4426debc122d1dfbac53cbcdf656")
    args = ap.parse_args()

    bd.projects.set_current(args.project)

    # Deine Activity:
    key = (args.db, args.code)  # market for electricity, high voltage | AT
    act = bd.get_activity(key)

    # Kategorien aus deinem File:
    categories_path = Path(__file__).resolve().parents[2] / "categories.json"  # .../Data/LCA_data/categories.json
    cats = json.loads(categories_path.read_text(encoding="utf-8"))["categories"]
    cat_keys = [c["key"] for c in cats]

    # Methoden aus method_map laden (wie in brightway_calculate_activity_ef16.py):
    # Verwende method_map_efv3_noLT.json wie in der funktionierenden Version
    method_map_path = Path(__file__).resolve().parents[2] / "mappings" / "method_map_efv3_noLT.json"
    if not method_map_path.exists():
        # Fallback zu method_map_efv3.json
        method_map_path = Path(__file__).resolve().parents[2] / "mappings" / "method_map_efv3.json"
    methods_by_cat = load_method_map(method_map_path)
    print(f"Loaded method map from: {method_map_path.name}")

    print("ACTIVITY")
    print(" Name:", act["name"])
    print(" Location:", act["location"])
    print(" Unit:", act["unit"])
    print(" Reference product:", act.get("reference product", "?"))
    print(" Key:", act.key)
    
    # Prüfe ob Activity Biosphere-Flows hat:
    bio_count = sum(1 for _ in act.biosphere())
    print(f" Biosphere flows: {bio_count}")
    
    if bio_count == 0:
        print(" WARNING: This is a market activity with no direct biosphere flows.")
        print(" It should still work if the supply chain resolves correctly.")
        print(" If all scores are 0, try using a production activity instead.")
        print(" Use brightway_search.py to find production activities.")
    
    # Prüfe Production-Exchange:
    prod_exchanges = [e for e in act.exchanges() if e.get("type") == "production"]
    print(f" Production exchanges: {len(prod_exchanges)}")
    if prod_exchanges:
        for pe in prod_exchanges[:3]:  # Zeige erste 3
            print(f"   - {pe.amount} {pe.unit} of {pe.input.get('name', '?')}")
    
    # Prüfe Technosphere-Inputs:
    tech_inputs = list(act.technosphere())
    tech_count = len(tech_inputs)
    print(f" Technosphere inputs: {tech_count}")
    if tech_inputs:
        print(" First technosphere input:")
        first_tech = tech_inputs[0]
        tech_act = first_tech.input
        print(f"   - {first_tech.amount:g} {first_tech.unit} | {tech_act.get('name', '?')} | {tech_act.get('location', '?')}")
        tech_bio_count = sum(1 for _ in tech_act.biosphere())
        print(f"   - This input has {tech_bio_count} biosphere flows")
    
    print("\nLCIA (per 1 unit of reference product)\n")

    # Verwende Activity direkt (wie in brightway_calculate_activity_ef16.py)
    # Market-Activities sollten trotzdem funktionieren, da LCA die Supply Chain auflöst
    fu = {act: 1.0}
    print(f"Using activity directly: {act.key}")
    
    # Test: Prüfe ob LCI überhaupt funktioniert
    if cat_keys and cat_keys[0] in methods_by_cat:
        test_method = methods_by_cat[cat_keys[0]]
        try:
            test_lca = LCA(fu, method=test_method)
            test_lca.lci()
            inventory_size = len(test_lca.inventory) if hasattr(test_lca, 'inventory') else 0
            print(f"LCI calculation successful. Inventory size: {inventory_size}")
            if inventory_size == 0:
                print("WARNING: Inventory is empty! This means the supply chain is not being resolved.")
                print("This could be because:")
                print("  1. The market activity only references other market activities")
                print("  2. The supply chain is circular or incomplete")
                print("  3. Try using a production activity instead of a market activity")
            
            # Prüfe ob es Biosphere-Flows im Inventory gibt
            if hasattr(test_lca, 'biosphere_dict'):
                bio_dict_size = len(test_lca.biosphere_dict) if test_lca.biosphere_dict else 0
                print(f"Biosphere flows in inventory: {bio_dict_size}")
        except Exception as e:
            print(f"ERROR in LCI calculation: {e}")
            import traceback
            traceback.print_exc()

    # Test: Prüfe ob erste Methode existiert und Characterisation Factors hat
    first_ck = cat_keys[0] if cat_keys else None
    if first_ck and first_ck in methods_by_cat:
        test_method = methods_by_cat[first_ck]
        try:
            method_obj = bd.Method(test_method)
            cf_count = sum(1 for _ in method_obj.load())
            print(f"Test method {test_method} has {cf_count} characterisation factors")
        except Exception as e:
            print(f"WARNING: Could not load test method {test_method}: {e}")

    # Für jede Methode einzeln berechnen (wie in brightway_calculate_activity_ef16.py)
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
