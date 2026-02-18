import re
import json
from pathlib import Path

import bw2data as bd
from bw2data import Database
from bw2data.backends.schema import ExchangeDataset
from peewee import fn

bd.projects.set_current("my_lca_project")

DEBUG_DIR = Path("Data/LCA_data/debug")
DEBUG_DIR.mkdir(parents=True, exist_ok=True)
REPORT = DEBUG_DIR / "step38_stub_biosphere_and_relink_report.json"

# Remaining broken exchanges (still 32-hex codes)
q = (ExchangeDataset
     .select()
     .where((ExchangeDataset.output_database == "ecoinvent 3.11 cutoff") &
            (ExchangeDataset.input_database == "biosphere3") &
            (fn.length(ExchangeDataset.input_code) == 32)))

total = q.count()
print("Remaining broken exchanges (len(code)==32):", total)

uuid_re = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$", re.I)

bio = Database("biosphere3")

def guess_categories(d):
    # conservative heuristic; categories aren't needed for processing, but nice to have
    c = (d.get("comment") or "").lower()
    if "water" in c and "air" not in c:
        return ("water",)
    if "air" in c and "water" not in c:
        return ("air",)
    # default
    return ("air",)

# Collect unique missing flow UUIDs and metadata
missing = {}
bad_flow = 0

for ex in q:
    d = ex.data or {}
    f = d.get("flow")
    if not (isinstance(f, str) and uuid_re.match(f)):
        bad_flow += 1
        continue

    key = ("biosphere3", f)
    if key in missing:
        continue

    # Skip if it already exists
    try:
        bd.get_activity(key)
        continue
    except Exception:
        pass

    # build minimal flow dataset
    data = {
        "name": d.get("name") or "Unknown flow",
        "unit": d.get("unit") or "kilogram",
        "type": "biosphere",
        "categories": tuple(d.get("categories") or guess_categories(d)),
    }
    # keep useful metadata if present
    for fld in ["CAS number", "chemical formula", "comment", "classifications"]:
        if d.get(fld) is not None:
            data[fld] = d.get(fld)

    missing[key] = data

print("Unique missing flow UUIDs to create:", len(missing))
print("Broken exchanges with missing/invalid data['flow']:", bad_flow)

# Create missing flows in biosphere3
if missing:
    bio.write(missing)
    print("Created missing biosphere3 flows:", len(missing))
else:
    print("No missing flows to create.")

# Now relink exchanges: input_code -> data['flow']
updated = 0
still_missing = 0

for ex in q:
    d = ex.data or {}
    f = d.get("flow")
    if not (isinstance(f, str) and uuid_re.match(f)):
        continue
    key = ("biosphere3", f)
    try:
        bd.get_activity(key)
    except Exception:
        still_missing += 1
        continue

    ex.input_database = "biosphere3"
    ex.input_code = f
    d["input"] = ["biosphere3", f]
    ex.data = d
    ex.save()
    updated += 1

print("Relinked exchanges to flow UUID:", updated)
print("Still missing after create (should be 0):", still_missing)

# Save report
REPORT.write_text(json.dumps({
    "remaining_broken_before": total,
    "missing_flows_created": len(missing),
    "updated_exchanges": updated,
    "still_missing": still_missing,
    "bad_flow_field": bad_flow,
}, indent=2), encoding="utf-8")
print("Wrote report:", str(REPORT))

# Try processing ecoinvent again
print("Processing ecoinvent 3.11 cutoff ...")
Database("ecoinvent 3.11 cutoff").process()
print("Processing OK.")
