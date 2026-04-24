from __future__ import annotations

import argparse

import bw2data as bd


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--project", default="my_lca_project")
    ap.add_argument("--token", default="ef v3")
    ap.add_argument("--limit", type=int, default=50)
    args = ap.parse_args()

    bd.projects.set_current(args.project)

    methods = [m for m in bd.methods if isinstance(m, tuple) and len(m) == 3]
    print("Total methods:", len(methods))

    tok = args.token.lower().strip()
    if tok:
        methods = [m for m in methods if tok in " | ".join(map(str, m)).lower()]

    print(f"Matching methods for token '{args.token}':", len(methods))
    for m in methods[: args.limit]:
        print(m)


if __name__ == "__main__":
    main()
