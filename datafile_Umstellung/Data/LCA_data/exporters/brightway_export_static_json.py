from __future__ import annotations

from paths import ensure_lca_data_on_syspath, lca_data_dir

# IMPORTANT: must run before importing modules that import "calculators"
ensure_lca_data_on_syspath()

from activity_map_io import load_activity_map
from export_static import export_from_activity_map


# Fixed production settings (no CLI)
PROJECT = "my_lca_project"
COUNTRY = "AT"

# Which technologies to export from activity_map.json
# Set to None to export all
EXPORT_TECHS = {"PV"}   # e.g. {"PV"} or {"Grid", "PV"}


def main() -> None:
    base = lca_data_dir()

    activity_map_path = base / "mappings" / "activity_map.json"
    method_map_path = base / "mappings" / "method_map_efv3_noLT.json"
    out_dir = base / "static" / COUNTRY

    # Debug: Zeige was in der JSON-Datei steht
    import json
    raw_json = json.loads(activity_map_path.read_text(encoding="utf-8"))
    print(f"[DEBUG] Raw JSON BESS infra amount: {raw_json.get('BESS', {}).get('infra', {}).get('amount', 'NOT FOUND')}")

    activity_map = load_activity_map(activity_map_path)
    
    # Debug: Zeige was geladen wurde
    print(f"[DEBUG] After load_activity_map, BESS infra: {activity_map.get('BESS', {}).get('infra', {})}")
    print(f"[DEBUG] Full activity_map for BESS: {activity_map.get('BESS', {})}")

    if EXPORT_TECHS is not None:
        missing = sorted(set(EXPORT_TECHS) - set(activity_map.keys()))
        if missing:
            raise ValueError(f"EXPORT_TECHS contains keys not in activity_map.json: {missing}")

        activity_map = {k: v for k, v in activity_map.items() if k in EXPORT_TECHS}
        print(f"[DEBUG] After filtering, BESS infra: {activity_map.get('BESS', {}).get('infra', {})}")

    export_from_activity_map(
        project=PROJECT,
        activity_map=activity_map,
        method_map_path=method_map_path,
        out_dir=out_dir,
        skip_existing=False,  # overwrite always
    )


if __name__ == "__main__":
    main()
