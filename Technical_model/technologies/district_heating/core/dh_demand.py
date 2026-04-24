from __future__ import annotations

from typing import Any, Dict, List

import numpy as np


def _require_settings_attr(settings_obj: Any, attr: str) -> Any:
    if settings_obj is None or not hasattr(settings_obj, attr):
        raise ValueError(f"[dh_demand] Missing required settings attribute '{attr}'.")
    return getattr(settings_obj, attr)


def _require_profile_array(profiles: Dict[str, Any], key: str) -> np.ndarray:
    if key not in profiles:
        raise ValueError(f"[dh_demand] Missing required profile '{key}'.")
    return np.asarray(profiles[key], dtype=float)


def _validate_share(value: Any, *, label: str) -> float:
    share = float(value)
    if not 0.0 <= share <= 1.0:
        raise ValueError(f"[dh_demand] {label} must be within [0, 1], got {share}.")
    return share


def _member_dh_share(member: Any, global_share: float) -> float:
    override = getattr(member, "dh_connected_share_override", None)
    if override is None:
        return global_share
    return _validate_share(override, label=f"{member.member_id}.dh_connected_share_override")


def _member_dh_share_vector(members_cfg: Any, global_share: float, n_members: int) -> np.ndarray:
    shares = np.zeros(n_members, dtype=float)
    cursor = 0
    for member in members_cfg.members:
        count = int(member.count)
        share = _member_dh_share(member, global_share)
        shares[cursor : cursor + count] = share
        cursor += count
    if cursor != n_members:
        raise ValueError("[dh_demand] Member/profile dimensionality mismatch.")
    return shares


def build_dh_demand(settings_obj: Any, profiles: Dict[str, Any]) -> Dict[str, Any]:
    """
    Derive district-heating demand from the existing member/cohort structure.

    The split is energy-based:
    - each member/cohort keeps its own hourly thermal demand profile
    - the DH-connected part is taken as ``share * hourly_demand``
    - no rounding to integer households is used in the new cohort path
    """

    engine_cfg = _require_settings_attr(settings_obj, "engine")
    members_cfg = _require_settings_attr(engine_cfg, "members")
    dh_cfg = _require_settings_attr(settings_obj, "district_heating")
    global_share = _validate_share(dh_cfg.share, label="district_heating.share")

    space_heat_member_2d = _require_profile_array(profiles, "space_heat_member_2d")
    hotwater_member_2d = _require_profile_array(profiles, "hotwater_member_2d")
    if space_heat_member_2d.shape != hotwater_member_2d.shape:
        raise ValueError("[dh_demand] 'space_heat_member_2d' and 'hotwater_member_2d' must share the same shape.")

    n_steps, n_members = space_heat_member_2d.shape
    member_share_vector = _member_dh_share_vector(members_cfg, global_share, n_members)

    demand_space_by_type: Dict[str, np.ndarray] = {}
    demand_hotwater_by_type: Dict[str, np.ndarray] = {}
    demand_total_by_type: Dict[str, np.ndarray] = {}
    connected_share_by_type: Dict[str, float] = {}
    connected_equivalent_units_by_type: Dict[str, float] = {}
    member_meta: List[Dict[str, Any]] = []

    cursor = 0
    for member in members_cfg.members:
        count = int(member.count)
        building_key = str(member.building_key)
        if cursor + count > n_members:
            raise ValueError("[dh_demand] Member/profile dimensionality mismatch.")

        member_slice = slice(cursor, cursor + count)
        cursor += count

        share = _member_dh_share(member, global_share)
        aggregated_space = space_heat_member_2d[:, member_slice].sum(axis=1) if count > 0 else np.zeros(n_steps)
        aggregated_hotwater = hotwater_member_2d[:, member_slice].sum(axis=1) if count > 0 else np.zeros(n_steps)

        demand_space = aggregated_space * share
        demand_hotwater = aggregated_hotwater * share
        demand_total = demand_space + demand_hotwater

        demand_space_by_type[building_key] = demand_space
        demand_hotwater_by_type[building_key] = demand_hotwater
        demand_total_by_type[building_key] = demand_total
        connected_share_by_type[building_key] = share
        connected_equivalent_units_by_type[building_key] = float(count) * share
        member_meta.append(
            {
                "member_id": str(member.member_id),
                "building_key": building_key,
                "runtime_count": count,
                "connected_share_realized": share,
                "connected_equivalent_units": float(count) * share,
            }
        )

    if cursor != n_members:
        raise ValueError("[dh_demand] Member/profile dimensionality mismatch after processing all members.")

    return {
        "space_heat_by_type": demand_space_by_type,
        "hotwater_by_type": demand_hotwater_by_type,
        "total_by_type": demand_total_by_type,
        "space_heat_total": sum(demand_space_by_type.values(), np.zeros(n_steps, dtype=float)),
        "hotwater_total": sum(demand_hotwater_by_type.values(), np.zeros(n_steps, dtype=float)),
        "total": sum(demand_total_by_type.values(), np.zeros(n_steps, dtype=float)),
        "connected_share_by_type": connected_share_by_type,
        "connected_equivalent_units_by_type": connected_equivalent_units_by_type,
        "member_share_vector": member_share_vector,
        "members": member_meta,
    }
