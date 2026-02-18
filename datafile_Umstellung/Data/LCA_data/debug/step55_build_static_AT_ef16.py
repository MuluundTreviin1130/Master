import json
from pathlib import Path

import bw2data as bd
from bw2calc import LCA

bd.projects.set_current("my_lca_project")

BASE = Path("Data/LCA_data/static/AT")
MAP_PATH = Path("Data/LCA_data/mappings/method_map_efv3.json")

mp_obj = json.loads(MAP_PATH.read_text(encoding="utf-8"))
method_map = mp_obj.get("method_map", mp_obj)

def calc_ef16(activity_key, amount=1.0):
    act = bd.get_activity(activity_key)
    out = {
        "activity_db": activity_key[0],
        "activity_code": activity_key[1],
        "name": act.get("name"),
        "reference_product": act.get("reference product") or act.get("product"),
        "location": act.get("location"),
        "unit": act.get("unit"),
        "amount": amount,
        "ef16": {}
    }
    for cat, m_list in method_map.items():
        m = tuple(m_list)
        lca = LCA({act: amount}, m)
        lca.lci()
        lca.lcia()
        out["ef16"][cat] = float(lca.score)
    return out

def load_activity_key(proxy_json):
    obj = json.loads(proxy_json.read_text(encoding="utf-8"))
    # allow both old/new shapes
    db = obj.get("activity_db") or obj.get("db") or obj.get("database")
    code = obj.get("activity_code") or obj.get("code")
    if not (db and code):
        raise ValueError(f"Missing activity_db/activity_code in {proxy_json}")
    return (db, code), obj

targets = ["PV.json", "BESS.json", "Grid.json"]

BASE.mkdir(parents=True, exist_ok=True)

for fn in targets:
    p = BASE / fn
    key, old = load_activity_key(p)
    res = calc_ef16(key, amount=1.0)

    # keep any extra metadata from old file (e.g. technology tags), but overwrite ef results
    merged = dict(old)
    merged.update({k: res[k] for k in ["activity_db","activity_code","name","reference_product","location","unit","amount"]})
    merged["ef16"] = res["ef16"]

    p.write_text(json.dumps(merged, indent=2, ensure_ascii=False), encoding="utf-8")
    print("[OK] wrote", p)

print("Done.")
