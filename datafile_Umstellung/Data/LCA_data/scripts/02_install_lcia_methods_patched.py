from __future__ import annotations

import argparse
import json
import zipfile
from pathlib import Path
from typing import Any, Dict, List, Tuple

import bw2data as bd
import bw2io as bi
from bw2data import Method


def _find_bw2io_lcia_zip() -> Path:
    import bw2io  # noqa

    root = Path(bw2io.__file__).resolve().parent
    cand = root / "data" / "lcia" / "lcia_39_ecoinvent.zip"
    if not cand.exists():
        raise FileNotFoundError(f"LCIA zip not found at expected path: {cand}")
    return cand


def _as_tuple(x: Any) -> Any:
    if isinstance(x, list):
        return tuple(_as_tuple(v) for v in x)
    return x


def _load_methods_from_zip(zip_path: Path) -> List[Dict[str, Any]]:
    with zipfile.ZipFile(zip_path, mode="r") as zf:
        with zf.open("data.json") as fp:
            data = json.load(fp)

    # Patch: lists -> tuples where Brightway expects tuples
    for m in data:
        if "name" in m:
            m["name"] = _as_tuple(m["name"])
        for exc in m.get("exchanges", []):
            if "input" in exc:
                exc["input"] = _as_tuple(exc["input"])
            if "categories" in exc:
                exc["categories"] = _as_tuple(exc["categories"])

    return data


def _write_methods(method_dicts: List[Dict[str, Any]], overwrite: bool) -> int:
    if overwrite:
        for m in method_dicts:
            name = tuple(m["name"])
            if name in bd.methods:
                del bd.methods[name]

    n_written = 0
    for m in method_dicts:
        name = tuple(m["name"])
        unit = m.get("unit", "")
        desc = m.get("description", "")
        filename = m.get("filename", "")

        method = Method(name)
        if name not in bd.methods:
            method.register(unit=unit, description=desc, filename=filename)

        cfs: List[Tuple[Tuple[str, str], float]] = []
        for exc in m.get("exchanges", []):
            inp = exc.get("input")
            amt = exc.get("amount")
            if inp is None or amt is None:
                continue
            if isinstance(inp, tuple) and len(inp) == 2:
                cfs.append((inp, float(amt)))

        method.write(cfs)
        n_written += 1

    return n_written


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--project", default="my_lca_project")
    ap.add_argument("--overwrite", action="store_true")
    ap.add_argument("--ensure_biosphere3", action="store_true")
    args = ap.parse_args()

    bd.projects.set_current(args.project)
    print("Active project:", bd.projects.current)

    if args.ensure_biosphere3:
        if "biosphere3" not in bd.databases:
            print("Creating biosphere3 (required for LCIA methods)...")
            bi.create_default_biosphere3(overwrite=True)

    print("Before methods:", len(list(bd.methods)))

    zip_path = _find_bw2io_lcia_zip()
    print("Using LCIA zip:", zip_path)

    data = _load_methods_from_zip(zip_path)
    n_written = _write_methods(data, overwrite=bool(args.overwrite))

    print(f"[OK] Wrote {n_written} LCIA methods")
    print("After methods:", len(list(bd.methods)))

    ef = [m for m in bd.methods if "ef" in " | ".join(map(str, m)).lower()]
    print("EF-like methods:", len(ef))
    print("EF sample (first 10):", ef[:10])


if __name__ == "__main__":
    main()
