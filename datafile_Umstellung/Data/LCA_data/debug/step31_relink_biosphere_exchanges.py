import json
from pathlib import Path

import bw2data as bd
from bw2data import Database
from bw2data.backends.schema import ExchangeDataset
from peewee import fn

bd.projects.set_current("my_lca_project")

DEBUG_DIR = Path("Data/LCA_data/debug")
DEBUG_DIR.mkdir(parents=True, exist_ok=True)
REPORT = DEBUG_DIR / "relink_report_step31.json"

db_bio = Database("biosphere3")

# All broken biosphere inputs in ecoinvent (32-hex codes)
q = (ExchangeDataset
     .select()
     .where((ExchangeDataset.output_database == "ecoinvent 3.11 cutoff") &
            (ExchangeDataset.input_database == "biosphere3") &
            (fn.length(ExchangeDataset.input_code) == 32)))

total = q.count()
print("Broken biosphere exchanges (len(code)==32):", total)

# category preference when exchange has no categories
PREF = [
    ("air",),
    ("water",),
    ("soil",),
]

cache = {}  # (name, unit, cats_tuple_or_None) -> chosen flow key (('biosphere3', uuid)) or None
stats = {"updated": 0, "unresolved": 0, "ambiguous_resolved": 0, "fuzzy_used": 0}

samples_unresolved = []
samples_amb = []
samples_fuzzy = []

def pick_candidate(name, unit, cats):
    """Return chosen biosphere3 activity key or None."""
    ck = (name, unit, tuple(cats) if cats else None)
    if ck in cache:
        return cache[ck]

    # 1) Exact-name candidates
    cands = []
    if name:
        # search is fuzzy but we filter exact name first
        res = db_bio.search(name)[:80]
        cands = [a for a in res if a.get("name") == name]

    # filter unit
    if unit:
        cands = [a for a in cands if a.get("unit") == unit]

    # if categories present, enforce exact categories
    if cats:
        cats_t = tuple(cats)
        cands2 = [a for a in cands if tuple(a.get("categories") or []) == cats_t]
        cands = cands2

    if len(cands) == 1:
        cache[ck] = cands[0].key
        return cache[ck]

    if len(cands) > 1 and not cats:
        # ambiguous: choose by preferred top-level compartment if possible
        # note: a.get("categories") is tuple like ('air',) etc.
        for pref in PREF:
            for a in cands:
                if tuple(a.get("categories") or []) == pref:
                    cache[ck] = a.key
                    return cache[ck]
        # otherwise take first
        cache[ck] = cands[0].key
        return cache[ck]

    if len(cands) == 0:
        # 2) Fuzzy fallback: take first search result matching unit (and cats if present)
        if name:
            res = db_bio.search(name)[:80]
            res2 = res
            if unit:
                res2 = [a for a in res2 if a.get("unit") == unit]
            if cats:
                cats_t = tuple(cats)
                res2 = [a for a in res2 if tuple(a.get("categories") or []) == cats_t]
            if len(res2) >= 1:
                cache[ck] = res2[0].key
                return cache[ck]

    cache[ck] = None
    return None

# Iterate and update
for ex in q:
    d = ex.data or {}
    name = d.get("name")
    unit = d.get("unit")
    cats = d.get("categories")  # can be None

    chosen = pick_candidate(name, unit, cats)

    if chosen is None:
        stats["unresolved"] += 1
        if len(samples_unresolved) < 20:
            samples_unresolved.append({
                "old_code": ex.input_code,
                "name": name,
                "unit": unit,
                "categories": cats,
                "output": [ex.output_database, ex.output_code],
            })
        continue

    # track if we resolved ambiguity or used fuzzy
    if cats is None:
        # ambiguous if multiple exact-name matches existed; we approximate this by checking how many exact-name hits exist
        res = db_bio.search(name)[:80] if name else []
        exact = [a for a in res if a.get("name") == name and (not unit or a.get("unit")==unit)]
        if len(exact) > 1:
            stats["ambiguous_resolved"] += 1
            if len(samples_amb) < 10:
                samples_amb.append({
                    "old_code": ex.input_code,
                    "name": name,
                    "unit": unit,
                    "chosen": chosen,
                    "candidates": [a.key for a in exact[:8]],
                })
        if len(exact) == 0:
            stats["fuzzy_used"] += 1
            if len(samples_fuzzy) < 10:
                samples_fuzzy.append({
                    "old_code": ex.input_code,
                    "name": name,
                    "unit": unit,
                    "chosen": chosen,
                })

    # Apply update
    new_db, new_code = chosen
    ex.input_database = new_db
    ex.input_code = new_code

    # keep data in sync (important for downstream tooling)
    d["input"] = [new_db, new_code]
    ex.data = d

    ex.save()
    stats["updated"] += 1

print("Relink done. Stats:", stats)

report = {
    "total_broken": total,
    "stats": stats,
    "samples_unresolved": samples_unresolved,
    "samples_ambiguous_resolved": samples_amb,
    "samples_fuzzy_used": samples_fuzzy,
}
REPORT.write_text(json.dumps(report, indent=2), encoding="utf-8")
print("Wrote report:", str(REPORT))

# Now try processing ecoinvent again
print("Processing ecoinvent 3.11 cutoff ...")
Database("ecoinvent 3.11 cutoff").process()
print("Processing OK.")
