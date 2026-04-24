"""LCA data loader for the optimizer. Loads per-technology JSON from static/<country>/."""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict

from Data.LCA_data.pedigree.load_pedigree import load_all_records, load_record


@dataclass(frozen=True)
class LcaDbConfig:
    mode: str = "static"          # "static" | "prospective"
    country: str = "AT"
    iam: str = "REMIND"           # only used if mode="prospective"
    scenario: str = "SSP2-Base"   # only used if mode="prospective"
    year: int = 2030              # only used if mode="prospective"
    debug_print: bool = False


def _project_root() -> Path:
    """Walk upwards until we find a folder containing 'Data/'."""
    here = Path(__file__).resolve()
    for p in [here.parent, *here.parents]:
        if (p / "Data").exists():
            return p
    return here.parents[2]


def _base_dir() -> Path:
    return _project_root() / "Data" / "LCA_data"


def _tech_path(cfg: LcaDbConfig, tech: str) -> Path:
    """Return path to tech JSON. Static mode: static/<country>/<tech>.json"""
    tech = str(tech).strip()
    root = _base_dir()

    if cfg.mode == "static":
        return root / "static" / cfg.country / f"{tech}.json"

    if cfg.mode == "prospective":
        return (
            root
            / "prospective"
            / cfg.country
            / cfg.iam
            / cfg.scenario
            / str(int(cfg.year))
            / f"{tech}.json"
        )

    raise ValueError(f"Unknown LCA DB mode: {cfg.mode!r}")


def load_tech_lca(cfg: LcaDbConfig, tech: str) -> Dict[str, Any]:
    p = _tech_path(cfg, tech)
    if not p.exists():
        raise FileNotFoundError(f"LCA file not found: {p}")
    with p.open("r", encoding="utf-8") as f:
        d = json.load(f)

    if "infra" not in d or "op" not in d:
        raise ValueError(f"Unexpected LCA JSON schema in {p}; expected keys: 'infra', 'op'")

    if cfg.debug_print:
        path_parts = p.parts
        short_path = Path(*path_parts[-4:]) if len(path_parts) >= 4 else p
        print(f"[LCA] loaded tech={tech} from {short_path}")

    return d


def load_tech_pedigree(cfg: LcaDbConfig, tech: str) -> Dict[str, Any]:
    """
    Load pedigree metadata for one technology.

    This is intentionally separate from the runtime LCA injection path so the
    optimizer remains deterministic unless a dedicated analysis workflow asks
    for pedigree information explicitly.
    """
    return load_record(cfg.country, tech)


def load_country_pedigree(cfg: LcaDbConfig) -> Dict[str, Dict[str, Any]]:
    """Load all pedigree records available for one country."""
    return load_all_records(cfg.country)


def apply_lca_to_params(params: Dict[str, Any], cfg: LcaDbConfig) -> Dict[str, Any]:
    """
    Inject LCA dicts into params so engines/constraints can use:
      params[tech]["LCA"] = {"infra": {...}, "op": {...}, "meta": {...}}
    """
    params.setdefault("PV", {})
    params.setdefault("BESS", {})
    params.setdefault("Grid", {})
    params.setdefault("FC", {})
    params.setdefault("ELY", {})
    params.setdefault("H2_TANK", {})

    pv = load_tech_lca(cfg, "PV")
    bess = load_tech_lca(cfg, "BESS")
    grid = load_tech_lca(cfg, "Grid")
    fc = load_tech_lca(cfg, "fuel_cell_PEM")
    ely = load_tech_lca(cfg, "ELY")
    h2_tank = load_tech_lca(cfg, "H2_TANK")

    params["PV"]["LCA"] = {
        "infra": dict(pv.get("infra", {}) or {}),
        "op": dict(pv.get("op", {}) or {}),
        "meta": dict(pv.get("meta", {}) or {}),
    }
    params["BESS"]["LCA"] = {
        "infra": dict(bess.get("infra", {}) or {}),
        "op": dict(bess.get("op", {}) or {}),
        "meta": dict(bess.get("meta", {}) or {}),
    }
    params["Grid"]["LCA"] = {
        "infra": dict(grid.get("infra", {}) or {}),
        "op": dict(grid.get("op", {}) or {}),
        "meta": dict(grid.get("meta", {}) or {}),
    }
    params["FC"]["LCA"] = {
        "infra": dict(fc.get("infra", {}) or {}),
        "op": dict(fc.get("op", {}) or {}),
        "meta": dict(fc.get("meta", {}) or {}),
    }
    params["ELY"]["LCA"] = {
        "infra": dict(ely.get("infra", {}) or {}),
        "op": dict(ely.get("op", {}) or {}),
        "meta": dict(ely.get("meta", {}) or {}),
    }
    params["H2_TANK"]["LCA"] = {
        "infra": dict(h2_tank.get("infra", {}) or {}),
        "op": dict(h2_tank.get("op", {}) or {}),
        "meta": dict(h2_tank.get("meta", {}) or {}),
    }

    pv_infra = params["PV"]["LCA"]["infra"]
    bess_infra = params["BESS"]["LCA"]["infra"]
    grid_op = params["Grid"]["LCA"]["op"]

    if "climate_change" in pv_infra:
        params["PV"]["GWP_kgco2eq_per_kwp"] = float(pv_infra["climate_change"])
    if "climate_change" in bess_infra:
        params["BESS"]["GWP_kgco2eq_per_kwhcap"] = float(bess_infra["climate_change"])
    if "climate_change" in grid_op:
        params["Grid"]["GWP_kgco2eq_per_kwh"] = float(grid_op["climate_change"])
    if "climate_change" in params["FC"]["LCA"]["infra"]:
        params["FC"]["GWP_kgco2eq_per_kw"] = float(params["FC"]["LCA"]["infra"]["climate_change"])

    return params


if __name__ == "__main__":
    cfg = LcaDbConfig(mode="static", country="AT", debug_print=True)
    for t in ("PV", "BESS", "Grid", "fuel_cell_PEM", "ELY", "H2_TANK"):
        d = load_tech_lca(cfg, t)
        print(f"[OK] {t}: climate_change infra={d['infra'].get('climate_change')} op={d['op'].get('climate_change')}")
