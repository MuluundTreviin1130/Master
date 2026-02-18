from __future__ import annotations

import argparse
import json

import bw2data as bd

from Data.LCA_data.tools.common.scenario_registry import resolve_scenario


def main() -> int:
    ap = argparse.ArgumentParser(description="Inspect a specific activity in a premise Brightway database")
    ap.add_argument("--country", required=True)
    ap.add_argument("--iam", required=True)
    ap.add_argument("--scenario", required=True)
    ap.add_argument("--year", type=int, required=True)
    ap.add_argument("--code", required=True, help="Activity code (as printed by premise_search.py)")
    ap.add_argument("--show-exchanges", action="store_true", help="Print basic technosphere exchanges (count + top 20 names)")
    args = ap.parse_args()

    meta = resolve_scenario(args.country, args.iam, args.scenario, args.year)
    if meta.bw_project:
        bd.projects.set_current(meta.bw_project)

    act = bd.Database(meta.bw_database_name).get(args.code)
    if act is None:
        raise SystemExit(f"[ERROR] Activity not found in {meta.bw_database_name}: code={args.code}")

    info = {
        "database": meta.bw_database_name,
        "code": act["code"],
        "name": act.get("name"),
        "reference product": act.get("reference product"),
        "location": act.get("location"),
        "unit": act.get("unit"),
        "key": (meta.bw_database_name, act["code"]),
    }
    print(json.dumps(info, indent=2))

    if args.show_exchanges:
        exc = list(act.technosphere())
        print(f"\n[INFO] technosphere exchanges: {len(exc)} (showing up to 20)")
        for e in exc[:20]:
            inp = e.input
            print(f"- {inp.get('name')} | {inp.get('location')} | amount={e['amount']} {inp.get('unit')}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
