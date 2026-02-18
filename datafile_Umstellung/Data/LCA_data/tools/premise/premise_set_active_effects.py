from __future__ import annotations

import argparse
import json
from pathlib import Path

from Data.LCA_data.tools.common.scenario_registry import lca_data_dir


def main() -> int:
    ap = argparse.ArgumentParser(description="Set static/<country>/active_effects.json to point to a dataset under effects/")
    ap.add_argument("--country", required=True)
    grp = ap.add_mutually_exclusive_group(required=True)
    grp.add_argument("--brightway-static", action="store_true", help="Point to effects/brightway/static/<country>")
    grp.add_argument("--premise", action="store_true", help="Point to effects/premise/<country>/<iam>/<scenario>/<year>")
    ap.add_argument("--iam", default=None)
    ap.add_argument("--scenario", default=None)
    ap.add_argument("--year", type=int, default=None)
    args = ap.parse_args()

    if args.brightway_static:
        active_root = f"effects/brightway/static/{args.country}"
    else:
        if not (args.iam and args.scenario and args.year):
            raise SystemExit("[ERROR] --premise requires --iam, --scenario, and --year")
        active_root = f"effects/premise/{args.country}/{args.iam}/{args.scenario}/{int(args.year)}"

    p = lca_data_dir() / "static" / args.country / "active_effects.json"
    p.parent.mkdir(parents=True, exist_ok=True)

    payload = {
        "active_root": active_root,
        "country": args.country,
    }
    with p.open("w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2)

    print(f"[OK] Wrote pointer: {p} -> {active_root}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
