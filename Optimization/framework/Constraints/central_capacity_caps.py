from __future__ import annotations

from typing import Any, Dict


def can_handle(name: str) -> bool:
    return name == "district_biomass_wood_fuel_capacity_max"


def evaluate_one(name: str, sense: str, rhs: float, ctx: Dict[str, Any], settings_constraints: Any) -> float:
    if name != "district_biomass_wood_fuel_capacity_max":
        return 0.0

    caps_cfg = dict(getattr(settings_constraints, "cfg", {}) or {}).get("central_capacity_caps", {}) or {}
    if name not in caps_cfg:
        raise ValueError(f"[constraints] Missing cfg for central capacity constraint '{name}'.")

    payload = dict(caps_cfg[name])
    biomass_kw_th = max(0.0, float(ctx.get("district_biomass_chp_kw_th", 0.0)))
    wood_kw_th = max(0.0, float(ctx.get("district_wood_chip_boiler_kw_th", 0.0)))

    biomass_eta_th = float(payload["district_biomass_chp_eta_th"])
    biomass_flh = float(payload["district_biomass_chp_full_load_hours_per_year"])
    wood_eta_th = float(payload["district_wood_chip_boiler_eta_th"])
    wood_flh = float(payload["district_wood_chip_boiler_full_load_hours_per_year"])

    lhs_fuel_kwh_per_year = (
        biomass_kw_th * biomass_flh / biomass_eta_th
        + wood_kw_th * wood_flh / wood_eta_th
    )
    return float(lhs_fuel_kwh_per_year - float(rhs))
