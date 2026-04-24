from __future__ import annotations

from typing import Any, Dict

import numpy as np

from Technical_model.technologies.buildings.runtime_building_params import get_runtime_building_params


def _require_dh_key(dh_demand: Dict[str, Any], key: str) -> Any:
    if key not in dh_demand:
        raise ValueError(f"[dh_buildings] Missing required dh_demand key '{key}'.")
    return dh_demand[key]


def build_dh_buildings(settings_obj: Any, profiles: Dict[str, Any], dh_demand: Dict[str, Any]) -> Dict[str, Any]:
    """
    Represent the building-side view of the DH layer without creating a second
    thermal-flexibility model.

    The module only reshapes already existing information:
    - building groups remain separated by ``building_key``
    - space heat remains the flexible thermal component
    - hot water remains a non-flexible thermal demand
    """

    engine_cfg = getattr(settings_obj, "engine", None)
    members_cfg = getattr(engine_cfg, "members", None) if engine_cfg is not None else None
    if members_cfg is None or not hasattr(members_cfg, "members"):
        raise ValueError("[dh_buildings] settings.engine.members is required.")

    space_heat_by_type = _require_dh_key(dh_demand, "space_heat_by_type")
    hotwater_by_type = _require_dh_key(dh_demand, "hotwater_by_type")
    connected_equivalent_units_by_type = _require_dh_key(dh_demand, "connected_equivalent_units_by_type")
    connected_share_by_type = _require_dh_key(dh_demand, "connected_share_by_type")

    thermal_states = profiles.get("thermal_states")
    thermflex_meta = profiles.get("thermflex_meta")

    buildings_by_type: Dict[str, Dict[str, Any]] = {}
    for member in members_cfg.members:
        building_key = str(member.building_key)
        building_params = get_runtime_building_params(member, settings_obj=settings_obj)
        buildings_by_type[building_key] = {
            "member_id": str(member.member_id),
            "label": str(getattr(member, "label", "")),
            "runtime_count": int(member.n_households),
            "connected_equivalent_units": float(connected_equivalent_units_by_type[building_key]),
            "connected_share_realized": float(connected_share_by_type[building_key]),
            "building_params": dict(building_params),
            # Existing thermflex logic remains authoritative. This layer only records
            # which thermal stream is flexible once the DH supply side gets attached.
            "space_heat_flexible": True,
            "hotwater_flexible": False,
            "space_heat_demand_kwh": np.asarray(space_heat_by_type[building_key], dtype=float),
            "hotwater_demand_kwh": np.asarray(hotwater_by_type[building_key], dtype=float),
            "thermal_state_ref": thermal_states.get(building_key) if isinstance(thermal_states, dict) else None,
            "thermflex_ref": thermflex_meta.get(building_key) if isinstance(thermflex_meta, dict) else None,
        }

    return {"by_type": buildings_by_type}
