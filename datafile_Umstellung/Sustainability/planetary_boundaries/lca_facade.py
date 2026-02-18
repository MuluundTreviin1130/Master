from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict


@dataclass(frozen=True)
class LcaDbConfig:
    mode: str = "static"          # "static" | "prospective"
    country: str = "AT"
    iam: str = "REMIND"           # only used if mode="prospective"
    scenario: str = "SSP2-Base"   # only used if mode="prospective"
    year: int = 2030              # only used if mode="prospective"
    debug_print: bool = False


# -----------------------------------------------------------------------------
# Path resolution helpers
# -----------------------------------------------------------------------------

def _project_root() -> Path:
    """Walk upwards until we find a folder containing 'Data/'.

    This makes the code robust regardless of where this module lives.
    """
    here = Path(__file__).resolve()
    for p in [here.parent, *here.parents]:
        if (p / "Data").exists():
            return p
    # Fallback: assume repo root is two levels above Sustainability/
    return here.parents[2]


def _base_dir() -> Path:
    return _project_root() / "Data" / "LCA_data"


def _read_active_effects_pointer(country: str) -> str | None:
    """Return active dataset root (relative to Data/LCA_data/) if configured.

    Supported pointer locations (checked in this order):
      1) Data/LCA_data/effects/<mode>/<country>/active_effects.json   (new, preferred)
      2) Data/LCA_data/static/<country>/active_effects.json          (legacy)
    """
    root = _base_dir()

    # Preferred (your new structure): Data/LCA_data/effects/static/AT/active_effects.json
    p_new = root / "effects" / "static" / country / "active_effects.json"
    candidates = [p_new]

    # Legacy location (backwards-compatible)
    p_legacy = root / "static" / country / "active_effects.json"
    candidates.append(p_legacy)

    for p in candidates:
        if not p.exists():
            continue
        try:
            with p.open("r", encoding="utf-8") as f:
                d = json.load(f)
            active_root = d.get("active_root")
            if isinstance(active_root, str) and active_root.strip():
                return active_root.strip()
        except Exception:
            continue

    return None



def _tech_path(cfg: LcaDbConfig, tech: str) -> Path:
    tech = str(tech).strip()
    root = _base_dir()

    if cfg.mode == "static":
        # OPTION 3: If a pointer exists, resolve "static" via the active dataset root.
        active_root = _read_active_effects_pointer(cfg.country)
        if active_root:
            p_active = root / active_root / f"{tech}.json"
            if p_active.exists():
                return p_active
            # If pointer exists but file doesn't, fall back to legacy, but keep it obvious in debug.
            if cfg.debug_print:
                print(f"[LCA] active_root set but missing file: {p_active}")

        # Prefer exported results in _out/ (keeps proxies separate)
        p_out = root / "static" / cfg.country / "_out" / f"{tech}.json"
        if p_out.exists():
            return p_out

        # Fallback to legacy path
        return root / "static" / cfg.country / f"{tech}.json"

    if cfg.mode == "prospective":
        # Kept for backwards-compatibility if you still want direct prospective paths.
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


# -----------------------------------------------------------------------------
# Loaders
# -----------------------------------------------------------------------------

def load_tech_lca(cfg: LcaDbConfig, tech: str) -> Dict[str, Any]:
    p = _tech_path(cfg, tech)
    if not p.exists():
        raise FileNotFoundError(f"LCA file not found: {p}")
    with p.open("r", encoding="utf-8") as f:
        d = json.load(f)

    if "infra" not in d or "op" not in d:
        raise ValueError(f"Unexpected LCA JSON schema in {p}; expected keys: 'infra', 'op'")

    if cfg.debug_print:
        # Zeige nur die letzten 4 Ordner des Pfads
        path_parts = p.parts
        if len(path_parts) >= 4:
            short_path = Path(*path_parts[-4:])
        else:
            short_path = p
        print(f"[LCA] loaded tech={tech} from {short_path}")

    return d


def apply_lca_to_params(params: Dict[str, Any], cfg: LcaDbConfig) -> Dict[str, Any]:
    """
    Inject LCA dicts into params so engines/constraints can use:
      params[tech]["LCA"] = {"infra": {...}, "op": {...}, "meta": {...}}

    Keeps legacy scalar keys as a convenience (optional).
    """
    # Ensure tech dicts exist
    params.setdefault("PV", {})
    params.setdefault("BESS", {})
    params.setdefault("Grid", {})

    pv = load_tech_lca(cfg, "PV")
    bess = load_tech_lca(cfg, "BESS")
    grid = load_tech_lca(cfg, "Grid")

    # Canonical structure used by engines/constraints
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

    # Optional: keep a few legacy scalar keys (only if present)
    pv_infra = params["PV"]["LCA"]["infra"]
    bess_infra = params["BESS"]["LCA"]["infra"]
    grid_op = params["Grid"]["LCA"]["op"]

    if "climate_change" in pv_infra:
        params["PV"]["GWP_kgco2eq_per_kwp"] = float(pv_infra["climate_change"])
    if "climate_change" in bess_infra:
        params["BESS"]["GWP_kgco2eq_per_kwhcap"] = float(bess_infra["climate_change"])
    if "climate_change" in grid_op:
        params["Grid"]["GWP_kgco2eq_per_kwh"] = float(grid_op["climate_change"])

    return params


if __name__ == "__main__":
    cfg = LcaDbConfig(mode="static", country="AT", debug_print=True)
    for t in ("PV", "BESS", "Grid"):
        d = load_tech_lca(cfg, t)
        print(f"[OK] {t}: climate_change infra={d['infra'].get('climate_change')} op={d['op'].get('climate_change')}")
