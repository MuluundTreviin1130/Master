from __future__ import annotations

import argparse

import bw2data as bd


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--project", default="my_lca_project")
    ap.add_argument("--db", default="ecoinvent 3.11 cutoff")
    ap.add_argument("--code", default="b47a4426debc122d1dfbac53cbcdf656")
    ap.add_argument("--n", type=int, default=20)
    args = ap.parse_args()

    bd.projects.set_current(args.project)

    key = (args.db, args.code)
    act = bd.get_activity(key)

    print("ACTIVITY")
    print(" Name:", act.get("name"))
    print(" Ref product:", act.get("reference product"))
    print(" Location:", act.get("location"))
    print(" Unit:", act.get("unit"))
    print(" Key:", act.key)

    print(f"\nTECHNOSPHERE INPUTS (first {args.n})")
    count = 0
    for exc in act.technosphere():
        inp = exc.input
        print(f"- {exc.amount:g} {exc.unit} | {inp.get('name')} | {inp.get('location','?')}")
        count += 1
        if count >= args.n:
            break

    print(f"\nBIOSPHERE FLOWS (first {args.n})")
    count = 0
    for exc in act.biosphere():
        inp = exc.input
        print(f"- {exc.amount:g} {exc.unit} | {inp.get('name')} | {inp.get('categories')}")
        count += 1
        if count >= args.n:
            break


if __name__ == "__main__":
    main()
