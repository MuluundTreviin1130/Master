import json
from pathlib import Path

import bw2data as bd
from bw2data import Database
from bw2data.backends.schema import ExchangeDataset

bd.projects.set_current("my_lca_project")

DEBUG_DIR = Path("Data/LCA_data/debug")
DEBUG_DIR.mkdir(parents=True, exist_ok=True)
REPORT = DEBUG_DIR / "step46_biosphere3_extra_report.json"

eco_name = "ecoinvent 3.11 cutoff"
base_bio = Database("biosphere3")
base_codes = set(a.key[1] for a in base_bio)

extra_name = "biosphere3_extra"

# Recreate extra DB cleanly
if extra_name in bd.databases:
    del bd.databases[extra_name]
extra = Database(extra_name)
extra.register()
print("Created DB:", extra_name)

# Find invalid biosphere refs in ecoinvent (input_code not in biosphere3)
q = (ExchangeDataset
     .select()
     .where((ExchangeDataset.output_database == eco_name) &
            (ExchangeDataset.input_database == "biosphere3")))

invalid = []
for ex in q:
    if ex.input_code not in base_codes:
        invalid.append(ex)

print("Invalid refs to move:", len(invalid))

# Build datasets for extra DB and relink exchanges
datasets = {}
sample = []
moved = 0

for ex in invalid:
    code = ex.input_code  # UUID-like
    d = ex.data or {}
    name = d.get("name") or "Unknown flow"
    unit = d.get("unit") or "kilogram"
    cats = d.get("categories")
    cats = tuple(cats) if cats else ("air",)

    key = (extra_name, code)
    if key not in datasets:
        data = {
            "name": name,
            "unit": unit,
            "type": "biosphere",
            "categories": cats,
        }
        for fld in ["CAS number", "chemical formula", "comment", "classifications"]:
            if d.get(fld) is not None:
                data[fld] = d.get(fld)
        datasets[key] = data

    # relink exchange to extra DB
    ex.input_database = extra_name
    ex.input_code = code
    d["input"] = [extra_name, code]
    ex.data = d
    ex.save()
    moved += 1

    if len(sample) < 10:
        sample.append((code, name, unit))

print("Unique flows written to extra DB:", len(datasets))
print("Exchanges moved to extra DB:", moved)

# Write datasets in one go (OK; it's a new DB)
extra.write(datasets)

print("extra DB size:", len(Database(extra_name)))

REPORT.write_text(json.dumps({
    "invalid_refs_moved": moved,
    "unique_flows_created": len(datasets),
    "sample": sample,
}, indent=2), encoding="utf-8")
print("Wrote report:", str(REPORT))

# Now process ecoinvent again
print("Processing ecoinvent 3.11 cutoff ...")
Database(eco_name).process()
print("Processing OK.")
