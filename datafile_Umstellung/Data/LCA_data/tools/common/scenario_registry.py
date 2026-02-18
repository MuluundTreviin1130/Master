from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Optional

from .project_root import find_project_root


@dataclass(frozen=True)
class ScenarioRef:
    country: str
    iam: str
    scenario: str
    year: int

    def key(self) -> str:
        return f"{self.country}/{self.iam}/{self.scenario}/{int(self.year)}"


@dataclass(frozen=True)
class ScenarioMeta:
    ref: ScenarioRef
    bw_project: str
    bw_database_name: str
    source_db: str | None = None
    ecoinvent_version: str | None = None
    premise_version: str | None = None
    created_at: str | None = None
    meta_path: Path | None = None


def _base_lca_data_dir() -> Path:
    return find_project_root() / "Data" / "LCA_data"


def iter_bw_db_meta_files() -> Iterable[Path]:
    root = _base_lca_data_dir() / "proxies" / "prospective"
    if not root.exists():
        return []
    return root.glob("**/bw_db_meta.json")


def load_scenario_meta(meta_path: Path) -> ScenarioMeta:
    with meta_path.open("r", encoding="utf-8") as f:
        d = json.load(f)

    ref = ScenarioRef(
        country=str(d.get("country") or d.get("Country") or "").strip(),
        iam=str(d.get("iam") or d.get("IAM") or "").strip(),
        scenario=str(d.get("scenario") or d.get("pathway") or d.get("Scenario") or "").strip(),
        year=int(d.get("year")),
    )

    return ScenarioMeta(
        ref=ref,
        bw_project=str(d.get("bw_project") or d.get("brightway_project") or "").strip(),
        bw_database_name=str(d.get("bw_database_name") or d.get("database") or "").strip(),
        source_db=d.get("source_db"),
        ecoinvent_version=d.get("ecoinvent_version"),
        premise_version=d.get("premise_version"),
        created_at=d.get("created_at"),
        meta_path=meta_path,
    )


def list_scenarios(country: str | None = None) -> list[ScenarioMeta]:
    out: list[ScenarioMeta] = []
    for p in iter_bw_db_meta_files():
        try:
            meta = load_scenario_meta(p)
        except Exception:
            continue
        if country and meta.ref.country != country:
            continue
        if meta.ref.country and meta.bw_database_name:
            out.append(meta)
    out.sort(key=lambda m: (m.ref.country, m.ref.iam, m.ref.scenario, m.ref.year))
    return out


def resolve_scenario(country: str, iam: str, scenario: str, year: int) -> ScenarioMeta:
    for meta in list_scenarios(country=country):
        if (meta.ref.country == country and meta.ref.iam == iam and meta.ref.scenario == scenario and int(meta.ref.year) == int(year)):
            return meta
    raise FileNotFoundError(
        f"No bw_db_meta.json found for {country}/{iam}/{scenario}/{int(year)} under Data/LCA_data/proxies/prospective/"
    )


def lca_data_dir() -> Path:
    return _base_lca_data_dir()


def effects_root_from_pointer(country: str) -> Optional[str]:
    """Return active_root string from static/<country>/active_effects.json if present."""
    p = _base_lca_data_dir() / "static" / country / "active_effects.json"
    if not p.exists():
        return None
    try:
        with p.open("r", encoding="utf-8") as f:
            d = json.load(f)
        return d.get("active_root")
    except Exception:
        return None
