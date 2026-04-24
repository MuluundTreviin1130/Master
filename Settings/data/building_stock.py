from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional

from Data.building_stock.Vienna.building_stock import (
    build_building_stock_values as build_building_stock_values_vienna,
)


@dataclass
class BuildingStockCohortConfig:
    cohort_id: str
    sector: str
    construction_period: str
    load_profile_mix: Dict[str, float]
    thermal_archetype_key: str
    represented_gfa_m2: float
    represented_volume_m3: float
    annual_heat_target_kwh: float
    annual_space_heat_target_kwh: float
    annual_hotwater_target_kwh: float
    annual_electricity_official_kwh: float
    annual_electricity_target_kwh: float
    dh_connected_share_override: Optional[float] = None
    include_hotwater: bool = True


@dataclass
class BuildingStockConfig:
    source: str = "manual_snapshot"
    location: Optional[str] = None
    source_file_paths: List[str] = field(default_factory=list)
    space_heat_distribution_mode: str = "per_cohort_targets"

    annual_heat_total_kwh: float = 0.0
    annual_heat_residential_kwh: float = 0.0
    annual_heat_non_residential_kwh: float = 0.0
    annual_space_heat_total_kwh: float = 0.0
    annual_hotwater_total_kwh: float = 0.0
    annual_electricity_residential_kwh: float = 0.0
    annual_electricity_non_residential_buildings_kwh: float = 0.0
    annual_electricity_exogenous_residential_kwh: float = 0.0
    annual_electricity_exogenous_non_residential_buildings_kwh: float = 0.0

    gross_floor_area_total_m2: float = 0.0
    gross_floor_area_residential_m2: float = 0.0
    gross_floor_area_non_residential_m2: float = 0.0
    building_volume_total_m3: float = 0.0
    building_volume_residential_m3: float = 0.0
    building_volume_non_residential_m3: float = 0.0

    construction_period_shares: Dict[str, float] = field(default_factory=dict)
    reference_2023_non_dh_electric_shares: Dict[str, float] = field(default_factory=dict)
    cohorts: List[BuildingStockCohortConfig] = field(default_factory=list)


def _coerce_building_stock(cfg: dict[str, object]) -> BuildingStockConfig:
    raw_cohorts = list(cfg.get("cohorts", []))
    cohorts = [
        BuildingStockCohortConfig(
            cohort_id=str(row["cohort_id"]),
            sector=str(row["sector"]),
            construction_period=str(row["construction_period"]),
            load_profile_mix={str(k): float(v) for k, v in dict(row["load_profile_mix"]).items()},
            thermal_archetype_key=str(row["thermal_archetype_key"]),
            represented_gfa_m2=float(row["represented_gfa_m2"]),
            represented_volume_m3=float(row["represented_volume_m3"]),
            annual_heat_target_kwh=float(row["annual_heat_target_kwh"]),
            annual_space_heat_target_kwh=float(row["annual_space_heat_target_kwh"]),
            annual_hotwater_target_kwh=float(row["annual_hotwater_target_kwh"]),
            annual_electricity_official_kwh=float(row["annual_electricity_official_kwh"]),
            annual_electricity_target_kwh=float(row["annual_electricity_target_kwh"]),
            dh_connected_share_override=(
                None if row.get("dh_connected_share_override") is None else float(row["dh_connected_share_override"])
            ),
            include_hotwater=bool(row.get("include_hotwater", True)),
        )
        for row in raw_cohorts
    ]
    out = dict(cfg)
    out["construction_period_shares"] = {
        str(k): float(v) for k, v in dict(cfg.get("construction_period_shares", {})).items()
    }
    out["reference_2023_non_dh_electric_shares"] = {
        str(k): float(v) for k, v in dict(cfg.get("reference_2023_non_dh_electric_shares", {})).items()
    }
    out["cohorts"] = cohorts
    return BuildingStockConfig(**out)


def make_building_stock(location: str) -> BuildingStockConfig:
    if not isinstance(location, str) or not location.strip():
        raise ValueError("[building_stock] Explicit non-empty location is required.")
    resolved_location = location.strip()
    if resolved_location == "Vienna":
        return _coerce_building_stock(build_building_stock_values_vienna())
    raise ValueError(
        f"[building_stock] No hardcoded building-stock snapshot registered for location='{resolved_location}'. "
        "Add a dedicated file under Data/building_stock/<Location>/."
    )
