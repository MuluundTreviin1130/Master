import re
import json
from pathlib import Path

import bw2data as bd
from bw2data import Database
from bw2data.backends.schema import ExchangeDataset

bd.projects.set_current("my_lca_project")

DEBUG_DIR = Path("Data/LCA_data/debug")
DEBUG_DIR.mkdir(parents=True, exist_ok=True)
REPORT = DEBUG_DIR / "step39_repair_report.json"

bio = Database("biosphere3")
eco_name = "ecoinvent 3.11 cutoff"

# Build set of existing biosphere3 codes (small, fast membership test)
bio_codes = set()
for a in bio:
    # a.key = ('biosphere3', code)
    bio_codes.add(a.key[1])

print("biosphere3 codes:", len(bio_codes))

# Find ecoinvent exchanges that reference biosphere3 codes that don't exist
q = (ExchangeDataset
     .select()
     .where((ExchangeDataset.output_database == eco_name) &
            (ExchangeDataset.input_database == "biosphere3")))

total = q.count()
print("Total ecoinvent->biosphere exchanges:", total)

# UUID pattern
uuid_re = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$", re.I)

def guess_categories(d):
    c = (d.get("comment") or "").lower()
    if "water" in c and "air" not in c:
        return ("water",)
    if "air" in c and "water" not in c:
        return ("air",)
    return ("air",)

# Collect invalid exchanges
invalid = []
for ex in q:
    if ex.input_code not in bio_codes:
        invalid.append(ex)

print("Invalid biosphere inputs (input_code not in biosphere3):", len(invalid))
if invalid:
    print("Example invalid input_code:", invalid[0].input_code)

# Create missing flows (batch) and relink if possible
to_create = {}
updated = 0
created = 0
used_flow_field = 0
used_existing_code = 0

samples = []

for ex in invalid:
    d = ex.data or {}
    name = d.get("name") or "Unknown flow"
    unit = d.get("unit") or "kilogram"
    cats = tuple(d.get("categories") or guess_categories(d))

    # Prefer data['flow'] if it looks like UUID
    flow = d.get("flow")
    target_code = None

    if isinstance(flow, str) and uuid_re.match(flow):
        target_code = flow
        used_flow_field += 1
    else:
        # Otherwise keep current input_code as target (create stub with that code)
        target_code = ex.input_code
        used_existing_code += 1

    # Ensure target exists in biosphere3
    if target_code not in bio_codes:
        key = ("biosphere3", target_code)
        if key not in to_create:
            data = {
                "name": name,
                "unit": unit,
                "type": "biosphere",
                "categories": cats,
            }
            for fld in ["CAS number", "chemical formula", "comment", "classifications"]:
                if d.get(fld) is not None:
                    data[fld] = d.get(fld)
            to_create[key] = data

    # Relink exchange to target_code
    ex.input_database = "biosphere3"
    ex.input_code = target_code
    d["input"] = ["biosphere3", target_code]
    ex.data = d
    ex.save()
    updated += 1

    if len(samples) < 10:
        samples.append({
            "old_code": ex.input_code,  # note: after save this is target; fine for traceability via flow/name
            "target_code": target_code,
            "name": name,
            "unit": unit,
            "flow_field": flow,
        })

print("Will create missing biosphere3 flows:", len(to_create))

if to_create:
    bio.write(to_create)
    created = len(to_create)
    # refresh biosphere code set
    for k in to_create.keys():
        bio_codes.add(k[1])

print("Updated exchanges:", updated)
print("Created flows:", created)
print("Used data['flow'] as target:", used_flow_field)
print("Used existing input_code as target:", used_existing_code)

REPORT.write_text(json.dumps({
    "total_biosphere_exchanges": total,
    "invalid_before": len(invalid),
    "updated_exchanges": updated,
    "created_flows": created,
    "used_flow_field": used_flow_field,
    "used_existing_input_code": used_existing_code,
    "samples": samples,
}, indent=2), encoding="utf-8")
print("Wrote report:", str(REPORT))

print("Processing ecoinvent 3.11 cutoff ...")
Database(eco_name).process()
print("Processing OK.")
