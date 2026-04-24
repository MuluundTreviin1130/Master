from __future__ import annotations

import argparse
from textwrap import shorten

from Data.LCA_data.tools.common.scenario_registry import list_scenarios


def main() -> int:
    ap = argparse.ArgumentParser(description="List available premise scenarios from bw_db_meta.json files")
    ap.add_argument("--country", default=None, help="Filter by country, e.g. AT")
    args = ap.parse_args()

    scenarios = list_scenarios(country=args.country)
    if not scenarios:
        print("[WARN] No scenarios found. Expected bw_db_meta.json under Data/LCA_data/proxies/prospective/**/")
        return 1

    print("country | iam | scenario | year | bw_database_name | created_at")
    print("-" * 120)
    for m in scenarios:
        dbn = shorten(m.bw_database_name, width=60, placeholder="…")
        print(f"{m.ref.country:7} | {m.ref.iam:6} | {m.ref.scenario:12} | {int(m.ref.year):4} | {dbn:60} | {m.created_at or ''}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
