from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Dict, List, Tuple

import bw2data as bd
from bw2calc import LCA


def patch_sparse_A1() -> None:
    try:
        import scipy.sparse as sp  # type: ignore
    except Exception:
        return

    if not hasattr(sp.csc_matrix, "A1"):
        sp.csc_matrix.A1 = property(lambda self: self.A.ravel())  # type: ignore
    if not hasattr(sp.csr_matrix, "A1"):
        sp.csr_matrix.A1 = property(lambda self: self.A.ravel())  # type: ignore


def _project_root() -> Path:
    here = Path(__file__).resolve()
    for p in [here.parent, *here.parents]:
        if (p / "Data").exists():
            return p
    return here.parents[3]


def load_method_map(path: Path) -> Dict[str, Tuple[str, str, str]]:
    raw = json.loads(path.read_text(encoding="utf-8"))
    mm = raw.get("method_map", {})
    out: Dict[str, Tuple[str, str, str]] = {}
    for k, v in mm.items():
        out[k] = (v[0], v[1], v[2])
    return out

def calculate_ef16_for_activity(act, amount: float, methods: Dict[str, Tuple[str, str, str]]) -> Dict[str, float]:
    """
    Efficient EF16 calculation:
    - LCI once
    - switch LCIA method for each category
    """
    items = list(methods.items())
    if not items:
        raise ValueError("No methods provided")

    first_cat, first_method = items[0]
    lca = LCA({act: float(amount)}, method=first_method)
    lca.lci()

    results: Dict[str, float] = {}

    lca.lcia()
    results[str(first_cat)] = float(lca.score)

    for cat, method in items[1:]:
        lca.switch_method(method)
        lca.lcia()
        results[str(cat)] = float(lca.score)

    return results


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--project", default="my_lca_project")
    ap.add_argument("--activity_db", required=True)
    ap.add_argument("--activity_code", required=True)
    ap.add_argument("--amount", type=float, default=1.0)
    ap.add_argument("--method_map", default=None)
    ap.add_argument("--out", default=None)
    args = ap.parse_args()

    patch_sparse_A1()

    bd.projects.set_current(args.project)
    key = (args.activity_db, args.activity_code)
    act = bd.get_activity(key)

    print(f"ACTIVITY: {act['name']} | {act.get('location','?')} | {act.get('unit','?')} | {key}")

    root = _project_root()
    method_map_path = Path(args.method_map) if args.method_map else (root / "Data" / "LCA_data" / "mappings" / "method_map_efv3_noLT.json")
    mm = load_method_map(method_map_path)

    results: Dict[str, float] = {}
    for cat, method in mm.items():
        lca = LCA({act: args.amount}, method)
        lca.lci()
        lca.lcia()
        score = float(lca.score)
        results[cat] = score
        print(f"{cat:<26} -> {score:.6e}  (method={method})")

    payload = {"activity_key": [args.activity_db, args.activity_code], "amount": args.amount, "results": results}

    if args.out:
        out_path = Path(args.out)
    else:
        out_path = root / "Data" / "LCA_data" / "static" / "_tmp_calc_one.json"

    out_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\n[OK] wrote: {out_path}")


if __name__ == "__main__":
    main()
