from __future__ import annotations

import argparse
import bw2data as bd


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--project", default="my_lca_project")
    ap.add_argument("--db", default="ecoinvent 3.11 cutoff")
    ap.add_argument("--query", default="fuel cell")
    ap.add_argument("--location", default="AT", help="Preferred location (fallback if not found)")
    ap.add_argument("--limit", type=int, default=200)
    args = ap.parse_args()

    bd.projects.set_current(args.project)
    db = bd.Database(args.db)

    hits = db.search(args.query, limit=args.limit)

    # 1) Try strict location
    hits_loc = [a for a in hits if a.get("location") == args.location]

    if hits_loc:
        final_hits = hits_loc
        print(f"[OK] Found {len(final_hits)} results with location='{args.location}'")
    else:
        # 2) Fallback: no location filter
        final_hits = hits
        print(
            f"[WARN] No results with location='{args.location}'. "
            f"Showing unfiltered results instead."
        )

    for a in final_hits:
        print("\nName:", a.get("name"))
        print("Reference product:", a.get("reference product"))
        print("Location:", a.get("location"))
        print("Unit:", a.get("unit"))
        print("Key:", a.key)


if __name__ == "__main__":
    main()
