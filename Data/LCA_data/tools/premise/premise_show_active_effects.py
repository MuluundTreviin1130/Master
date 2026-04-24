from __future__ import annotations

import argparse
import json

from Data.LCA_data.tools.common.scenario_registry import lca_data_dir


def main() -> int:
    ap = argparse.ArgumentParser(description="Show active effects pointer (static/<country>/active_effects.json) and basic checks")
    ap.add_argument("--country", required=True)
    ap.add_argument("--techs", nargs="*", default=["Grid", "PV", "BESS"])
    args = ap.parse_args()

    p = lca_data_dir() / "static" / args.country / "active_effects.json"
    if not p.exists():
        print(f"[WARN] Pointer not found: {p}")
        return 1

    with p.open("r", encoding="utf-8") as f:
        d = json.load(f)

    active_root = d.get("active_root")
    print(f"[OK] active_root = {active_root}")

    if not active_root:
        return 1

    base = lca_data_dir() / active_root
    print(f"[INFO] resolved path = {base}")

    missing = []
    for tech in args.techs:
        fp = base / f"{tech}.json"
        if not fp.exists():
            missing.append(str(fp))
    if missing:
        print("[WARN] Missing tech files:")
        for m in missing:
            print(f"- {m}")
        return 2

    print("[OK] All requested tech files are present.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
