from __future__ import annotations

import argparse

import bw2data as bd

from Data.LCA_data.tools.common.scenario_registry import resolve_scenario


def main() -> int:
    ap = argparse.ArgumentParser(description="Search activities in a premise-generated Brightway database")
    ap.add_argument("--country", required=True)
    ap.add_argument("--iam", required=True)
    ap.add_argument("--scenario", required=True)
    ap.add_argument("--year", type=int, required=True)
    ap.add_argument("--query", required=True, help="Substring query applied to activity name")
    ap.add_argument("--limit", type=int, default=20)
    args = ap.parse_args()

    meta = resolve_scenario(args.country, args.iam, args.scenario, args.year)

    if meta.bw_project:
        bd.projects.set_current(meta.bw_project)

    db = bd.Database(meta.bw_database_name)
    q = args.query.lower().strip()

    matches = []
    for act in db:
        name = (act.get("name") or "").lower()
        if q in name:
            matches.append(act)
            if len(matches) >= args.limit:
                break

    if not matches:
        print(f"[INFO] No matches for query={args.query!r} in db={meta.bw_database_name!r}")
        return 0

    print(f"[OK] db={meta.bw_database_name}")
    for i, act in enumerate(matches, start=1):
        print(f"{i:2d}. name={act.get('name')} | ref={act.get('reference product')} | loc={act.get('location')} | unit={act.get('unit')} | code={act['code']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
