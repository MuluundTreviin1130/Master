from __future__ import annotations

import argparse
from typing import Any, Dict

import bw2data as bd
from bw2data import Database
import bw2io as bi

# Try to import ExchangeDataset (may not be available in all bw2data versions)
try:
    from bw2data.backends.schema import ExchangeDataset
    HAS_EXCHANGE_DATASET = True
except ImportError:
    HAS_EXCHANGE_DATASET = False
    print("[WARN] ExchangeDataset not available - repair function will be skipped")


def _ensure_biosphere3() -> None:
    if "biosphere3" not in bd.databases:
        print("[INFO] biosphere3 not found -> creating")
        bi.create_default_biosphere3(overwrite=True)


def _extract_flow_code(flow: Dict[str, Any]) -> str | None:
    """Best-effort extraction of a stable identifier used as flow code."""
    for k in ("code", "uuid", "flow_uuid", "id"):
        v = flow.get(k)
        if isinstance(v, str) and v:
            return v
    return None


def _add_missing_biosphere_flows(imp: Any) -> int:
    """Add missing biosphere flows to biosphere3 so linking by UUID can succeed.

    Returns number of flows added.
    """
    if not getattr(imp, "unlinked", None):
        return 0

    biosphere = bd.Database("biosphere3")

    new: Dict[tuple[str, str], Dict[str, Any]] = {}
    for exc in imp.unlinked:
        if exc.get("type") != "biosphere":
            continue
        flow = exc.get("input")
        if not isinstance(flow, dict):
            continue
        code = _extract_flow_code(flow)
        if not code:
            continue
        key = ("biosphere3", code)
        if key in biosphere:
            continue
        cats = flow.get("categories") or ()
        if isinstance(cats, list):
            cats = tuple(cats)
        elif not isinstance(cats, tuple):
            cats = (str(cats),)

        new[key] = {
            "name": flow.get("name") or code,
            "unit": flow.get("unit") or "kilogram",
            "categories": cats,
            "type": flow.get("type") or "emission",
        }

    if not new:
        return 0

    print(f"[FIX] Adding {len(new)} missing biosphere flows to biosphere3")
    # Merge-write: write only the new flows.
    biosphere.write(new)
    return len(new)


def _remove_unlinked_exchanges_manually(imp: Any) -> int:
    """Manually remove unlinked exchanges from importer data before writing.
    
    An exchange is considered linked if its 'input' field is a tuple/list of 2 elements
    (database, code). Everything else is considered unlinked and will be removed.
    
    Returns number of exchanges removed.
    """
    if not getattr(imp, "data", None):
        return 0
    
    removed_count = 0
    total_exchanges = 0
    
    # Go through all datasets and remove unlinked exchanges
    for ds in imp.data:
        if "exchanges" not in ds:
            continue
        
        original_count = len(ds["exchanges"])
        total_exchanges += original_count
        
        # Filter: keep only exchanges where input is a valid tuple/list of 2 elements
        ds["exchanges"] = [
            exc for exc in ds["exchanges"]
            if _is_exchange_linked(exc)
        ]
        
        removed_count += original_count - len(ds["exchanges"])
    
    print(f"[FIX] Removed {removed_count} unlinked exchanges from {total_exchanges} total exchanges")
    return removed_count


def _is_exchange_linked(exc: Dict[str, Any]) -> bool:
    """Check if an exchange is properly linked.
    
    An exchange is linked if 'input' is a tuple/list of exactly 2 elements
    (database name and code).
    """
    input_val = exc.get("input")
    
    # Linked exchange: input is a tuple/list with 2 elements (database, code)
    if isinstance(input_val, (list, tuple)) and len(input_val) == 2:
        # Both elements should be strings
        if isinstance(input_val[0], str) and isinstance(input_val[1], str):
            return True
    
    # Everything else (dict, None, wrong format) is unlinked
    return False


def _repair_invalid_biosphere_refs(eco_name: str) -> int:
    """Repair invalid biosphere references after database write.
    
    Based on step44_add_missing_biosphere3_flows_then_process_ecoinvent.py
    Finds exchanges that reference biosphere3 codes that don't exist,
    creates the missing flows, then processes the database.
    
    Returns number of flows added.
    """
    if not HAS_EXCHANGE_DATASET:
        print("[SKIP] ExchangeDataset not available - skipping repair step")
        return 0
    
    bio = Database("biosphere3")
    bio_codes = set(a.key[1] for a in bio)
    
    # Find invalid refs (input_code not in biosphere3)
    q = (ExchangeDataset
         .select()
         .where((ExchangeDataset.output_database == eco_name) &
                (ExchangeDataset.input_database == "biosphere3")))
    
    total = q.count()
    missing = {}
    
    for ex in q:
        code = ex.input_code
        if code in bio_codes:
            continue
        if code in missing:
            continue
        
        d = ex.data or {}
        name = d.get("name") or "Unknown flow"
        unit = d.get("unit") or "kilogram"
        cats = d.get("categories")
        if cats:
            cats = tuple(cats)
        else:
            cats = ("air",)
        
        data = {
            "name": name,
            "unit": unit,
            "type": "biosphere",
            "categories": cats,
        }
        # Keep useful metadata if present
        for fld in ["CAS number", "chemical formula", "comment", "classifications"]:
            if d.get(fld) is not None:
                data[fld] = d.get(fld)
        
        missing[("biosphere3", code)] = data
    
    if not missing:
        print(f"[REPAIR] No missing biosphere flows found (total exchanges: {total})")
        return 0
    
    print(f"[REPAIR] Found {len(missing)} unique missing biosphere3 codes to add")
    print(f"[REPAIR] Total ecoinvent->biosphere exchanges: {total}")
    
    # Write in batches to avoid huge single transaction
    BATCH = 2000
    items = list(missing.items())
    created = 0
    
    for i in range(0, len(items), BATCH):
        chunk = dict(items[i:i+BATCH])
        bio.write(chunk)
        created += len(chunk)
        print(f"[REPAIR] Wrote {created}/{len(items)} missing flows")
    
    print(f"[REPAIR] Added {created} missing biosphere flows")
    return created


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--project", default="my_lca_project")
    ap.add_argument("--db", "--ecoinvent_db", default="ecoinvent 3.11 cutoff", dest="ecoinvent_db", help="Database name")
    ap.add_argument("--ecospold", "--ecospold_dir", dest="ecospold_dir", required=True, help="Path to ecoSpold2 directory")
    ap.add_argument("--overwrite", action="store_true")
    ap.add_argument("--use_mp", action="store_true", help="Enable multiprocessing (often slower on Windows)")
    ap.add_argument(
        "--allow_unlinked",
        action="store_true",
        help="Continue import even if some biosphere links remain unlinked",
    )
    args = ap.parse_args()

    bd.projects.set_current(args.project)
    _ensure_biosphere3()

    if args.overwrite and args.ecoinvent_db in bd.databases:
        print(f"[WARN] Deleting existing database: {args.ecoinvent_db}")
        del bd.databases[args.ecoinvent_db]

    print("Active project:", bd.projects.current)
    print("Databases before import:", list(bd.databases))

    imp = bi.SingleOutputEcospold2Importer(args.ecospold_dir, args.ecoinvent_db, use_mp=args.use_mp)
    imp.apply_strategies()

    print("\n=== IMPORT STATISTICS (before fix) ===")
    imp.statistics()

    # Try to fix unlinked biosphere flows by adding missing flows and re-linking.
    added = _add_missing_biosphere_flows(imp)

    # Re-run biosphere linking if we added new flows
    if added:
        from bw2io.strategies import link_biosphere_by_flow_uuid

        print("[LINK] Re-linking biosphere flows after adding missing flows")
        imp.apply_strategies([link_biosphere_by_flow_uuid])

        print("\n=== IMPORT STATISTICS (after relink) ===")
        imp.statistics()

    # Decide whether to continue if unlinked biosphere exchanges remain.
    unlinked_all = getattr(imp, "unlinked", None)
    if unlinked_all:
        biosphere_unlinked = [x for x in unlinked_all if x.get("type") == "biosphere"]
        if biosphere_unlinked:
            if not args.allow_unlinked:
                raise RuntimeError(
                    f"Unlinked biosphere edges remain: {len(biosphere_unlinked)}. "
                    "Stop here to keep the database publishable. "
                    "Use --allow_unlinked to continue anyway."
                )
            print(
                f"[WARN] Continuing with {len(biosphere_unlinked)} unlinked biosphere exchanges "
                f"(requested by --allow_unlinked)"
            )
            # Remove unlinked exchanges manually before writing to avoid InvalidExchange errors
            print("[FIX] Removing unlinked exchanges before writing database...")
            _remove_unlinked_exchanges_manually(imp)

    print("\nWriting database...")
    imp.write_database()

    print("Databases after import:", list(bd.databases))
    
    # Repair invalid biosphere references
    print("\n=== REPAIRING INVALID BIOSPHERE REFERENCES ===")
    _repair_invalid_biosphere_refs(args.ecoinvent_db)
    
    # Process the database to ensure consistency
    print("\n=== PROCESSING DATABASE ===")
    Database(args.ecoinvent_db).process()
    print("Database processing complete.")


if __name__ == "__main__":
    main()
