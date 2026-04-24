# Brightway static LCA setup

This folder contains a minimal Brightway (Brightway2/3) toolchain to:

1. Bootstrap a Brightway project
2. Install `biosphere3` and LCIA methods (EF v3) with patch
3. Import ecoinvent (ecoSpold2)
4. Search and inspect activities
5. Calculate EF16 category results for any activity
6. Export per-technology JSONs for the optimization model

## Directory layout

```text
Data/LCA_data/
  categories.json                # impact category definitions
  lca_facade.py                  # loader for optimizer (static/<country>/*.json)
  mappings/
    activity_map.json             # ecoinvent activity mapping (db, code, amount per tech)
    method_map_efv3_noLT.json    # category -> Brightway method tuple
  static/AT/                      # LCA results used by optimizer
    BESS.json
    Grid.json
    PV.json
  scripts/
    bootstrap_brightway_project.py
    install_ef_methods_patched.py
    import_ecoinvent_database.py
    build_impact_method_map.py
    check_brightway_environment.py
    run_full_setup.ps1
  tools/
    brightway/brightway_search.py
    brightway/brightway_inspect_activity.py
    brightway/brightway_list_methods.py
  calculators/
    brightway_calculate_activity_ef16.py
  exporters/
    brightway_export_static_json.py
```

## Brightway-Pakete installieren (vor der Nutzung)

Die LCA-Tools benötigen `bw2data`, `bw2io`, `bw2calc`. Im Projekt-venv installieren:

```powershell
.\.venv\Scripts\pip install -r Data\LCA_data\requirements-lca.txt
```

Oder für Cursor/IDE: Als Python-Interpreter das venv auswählen (`.venv\Scripts\python.exe`).

## Setup (fresh project)

Run from repo root. Or use the PowerShell script:

```powershell
& "Data\LCA_data\scripts\run_full_setup.ps1"
```

Manual steps:

1) **Bootstrap project + biosphere3**
```powershell
python "Data\LCA_data\scripts\bootstrap_brightway_project.py" --project my_lca_project
```

2) **Install LCIA methods**
```powershell
python "Data\LCA_data\scripts\install_ef_methods_patched.py" --project my_lca_project --ensure_biosphere3
```

3) **Import ecoinvent** (ecoSpold2 directory)
```powershell
python "Data\LCA_data\scripts\import_ecoinvent_database.py" --project my_lca_project --db "ecoinvent 3.11 cutoff" --ecospold "C:\path\to\ecospold_datasets"
```

4) **Check environment**
```powershell
python "Data\LCA_data\scripts\check_brightway_environment.py" --project my_lca_project
```

## Search and inspect activities

**Suche** (immer venv-Python verwenden – sonst `ModuleNotFoundError: bw2data`):

```powershell
# Mit venv (empfohlen):
.\.venv\Scripts\python.exe "Data\LCA_data\tools\brightway\brightway_search.py" --project my_lca_project --db "ecoinvent 3.11 cutoff" --query "photovoltaic" --location AT --limit 50

# Oder mit run_search.ps1 (nutzt automatisch venv):
. "Data\LCA_data\tools\brightway\run_search.ps1" --query "photovoltaic" --location AT --limit 50
```

**Inspect** (code aus der Suche verwenden):
```powershell
.\.venv\Scripts\python.exe "Data\LCA_data\tools\brightway\brightway_inspect_activity.py" --project my_lca_project --db "ecoinvent 3.11 cutoff" --code "<activity_code>" --n 20
```

## Export JSONs for the optimizer

1) Edit `mappings/activity_map.json` – add ecoinvent activities (db, code, amount) per technology.
2) Run exporter:
```powershell
python "Data\LCA_data\exporters\brightway_export_static_json.py"
```
(Adjust `EXPORT_TECHS` and `COUNTRY` in the script if needed.)

Creates `Data/LCA_data/static/AT/{PV,BESS,Grid}.json` – these are loaded by `lca_facade` and injected into `params` via `Data/params.py`.
