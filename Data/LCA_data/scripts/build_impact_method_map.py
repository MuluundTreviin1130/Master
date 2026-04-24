from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Dict, List, Tuple

import bw2data as bd


EXPECTED_L2 = {
    "climate_change": "climate change",
    "ozone_depletion": "ozone depletion",
    "human_toxicity_cancer": "human toxicity: carcinogenic",
    "human_toxicity_non_cancer": "human toxicity: non-carcinogenic",
    "particulate_matter": "particulate matter formation",
    "ionising_radiation": "ionising radiation: human health",
    "photochemical_ozone_formation": "photochemical oxidant formation: human health",
    "acidification": "acidification",
    "eutrophication_terrestrial": "eutrophication: terrestrial",
    "freshwater_eutrophication": "eutrophication: freshwater",
    "marine_eutrophication": "eutrophication: marine",
    "freshwater_ecotoxicity": "ecotoxicity: freshwater",
    "land_use": "land use",
    "water_use": "water use",
    "fossil_resource_use": "energy resources: non-renewable",
    "material_resources": "material resources: metals/minerals",
}


def _project_root() -> Path:
    here = Path(__file__).resolve()
    for p in [here.parent, *here.parents]:
        if (p / "Data").exists():
            return p
    return here.parents[3]


def _normalize(s: str) -> str:
    s = str(s).lower().strip()
    if s.endswith(" no lt"):
        s = s[: -len(" no lt")]
    return s


def pick_family(preferred: List[str]) -> str:
    families = sorted({m[0] for m in bd.methods if isinstance(m, tuple) and len(m) == 3})
    for fam in preferred:
        if fam in families:
            return fam
    raise RuntimeError(f"None of the preferred families found. Available include: {families[:20]}")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--project", default="my_lca_project")
    ap.add_argument(
        "--family",
        default=None,
        help="Exact method family to use (e.g., 'EF v3.0 no LT' or 'EF v3.0'). If omitted, auto-pick.",
    )
    ap.add_argument(
        "--out",
        default=None,
        help="Output JSON path. Default: Data/LCA_data/mappings/method_map_efv3.json",
    )
    args = ap.parse_args()

    bd.projects.set_current(args.project)

    root = _project_root()
    categories_path = root / "Data" / "LCA_data" / "categories.json"
    out_path = Path(args.out) if args.out else root / "Data" / "LCA_data" / "mappings" / "method_map_efv3.json"

    cats = json.loads(categories_path.read_text(encoding="utf-8"))["categories"]
    keys = [c["key"] for c in cats]

    family = args.family or pick_family(["EF v3.0 no LT", "EF v3.0", "EF v3.1 no LT", "EF v3.1"])

    ef_methods = [m for m in bd.methods if isinstance(m, tuple) and len(m) == 3 and m[0] == family]
    if not ef_methods:
        raise RuntimeError(f"No methods found for family: {family}")

    by_l2: Dict[str, List[Tuple[str, str, str]]] = {}
    for m in ef_methods:
        by_l2.setdefault(_normalize(m[1]), []).append(m)

    method_map: Dict[str, List[str]] = {}
    unresolved: Dict[str, Any] = {}

    for k in keys:
        want = _normalize(EXPECTED_L2.get(k, k.replace("_", " ")))

        exact = by_l2.get(want, [])
        if len(exact) == 1:
            method_map[k] = list(exact[0])
            continue

        # Fuzzy contains (still within same family)
        fuzzy = [m for m in ef_methods if want in _normalize(m[1])]
        if len(fuzzy) == 1:
            method_map[k] = list(fuzzy[0])
            continue

        unresolved[k] = {
            "wanted_l2": want,
            "exact_candidates": exact[:20],
            "fuzzy_candidates": fuzzy[:20],
        }

    payload = {"project": args.project, "family": family, "method_map": method_map, "unresolved": unresolved}
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")

    if unresolved:
        print("[WARN] Some categories could not be mapped uniquely:")
        for k, info in unresolved.items():
            print(f" - {k}: wanted '{info['wanted_l2']}', exact={len(info['exact_candidates'])}, fuzzy={len(info['fuzzy_candidates'])}")
        print(f"[OK] wrote partial map: {out_path}")
        print(f"[OK] mapped {len(method_map)}/{len(keys)} categories")
    else:
        print("[OK] All categories mapped uniquely.")
        print(f"[OK] wrote: {out_path}")
        print(f"[OK] mapped {len(method_map)}/{len(keys)} categories")


if __name__ == "__main__":
    main()
