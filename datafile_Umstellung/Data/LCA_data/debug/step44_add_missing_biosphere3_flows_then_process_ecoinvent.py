import json
from pathlib import Path

import bw2data as bd
from bw2data import Database
from bw2data.backends.schema import ExchangeDataset

bd.projects.set_current("my_lca_project")

DEBUG_DIR = Path("Data/LCA_data/debug")
DEBUG_DIR.mkdir(parents=True, exist_ok=True)
REPORT = DEBUG_DIR / "step44_add_missing_biosphere3_report.json"

eco_name = "ecoinvent 3.11 cutoff"
bio = Database("biosphere3")

# Existing biosphere3 codes
bio_codes = set(a.key[1] for a in bio)
print("biosphere3 length (before):", len(bio_codes))

# Find invalid refs (input_code not in biosphere3)
q = (ExchangeDataset
     .select()
     .where((ExchangeDataset.output_database == eco_name) &
            (ExchangeDataset.input_database == "biosphere3")))

total = q.count()
missing = {}
sample_missing = []

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
        # conservative default; enough to be processable
        cats = ("air",)

    data = {
        "name": name,
        "unit": unit,
        "type": "biosphere",
        "categories": cats,
    }
    # keep useful metadata if present
    for fld in ["CAS number", "chemical formula", "comment", "classifications"]:
        if d.get(fld) is not None:
            data[fld] = d.get(fld)

    missing[("biosphere3", code)] = data

    if len(sample_missing) < 10:
        sample_missing.append((code, name, unit, d.get("flow")))

print("Total ecoinvent->biosphere exchanges:", total)
print("Unique missing biosphere3 codes to add:", len(missing))
print("Sample missing (code, name, unit, flow):")
for row in sample_missing:
    print(" ", row)

# Write in batches to avoid huge single transaction
BATCH = 2000
items = list(missing.items())
created = 0

for i in range(0, len(items), BATCH):
    chunk = dict(items[i:i+BATCH])
    bio.write(chunk)
    created += len(chunk)
    print(f"  wrote {created}/{len(items)}")

# Recompute validity after write
bio_codes2 = set(a.key[1] for a in bio)

invalid_after = 0
for ex in q:
    if ex.input_code not in bio_codes2:
        invalid_after += 1

print("biosphere3 length (after):", len(bio_codes2))
print("Invalid refs after adding flows:", invalid_after)

REPORT.write_text(json.dumps({
    "biosphere3_len_before": len(bio_codes),
    "unique_missing_added": len(items),
    "biosphere3_len_after": len(bio_codes2),
    "invalid_refs_after": invalid_after,
    "sample_missing": sample_missing,
}, indent=2), encoding="utf-8")
print("Wrote report:", str(REPORT))

# Now try processing ecoinvent
print("Processing ecoinvent 3.11 cutoff ...")
Database(eco_name).process()
print("Processing OK.")
