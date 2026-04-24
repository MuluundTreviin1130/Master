from __future__ import annotations

from typing import Any, Dict, Iterable

import numpy as np


def _zeros_like_series_map(series_by_type: Dict[str, np.ndarray]) -> Dict[str, np.ndarray]:
    return {key: np.zeros_like(np.asarray(values, dtype=float)) for key, values in series_by_type.items()}


def build_dh_bus(
    dh_demand: Dict[str, Any],
    dh_buildings: Dict[str, Any],
    source_names: Iterable[str],
) -> Dict[str, Any]:
    """
    Create the neutral DH interface object.

    The bus is intentionally dispatch-agnostic:
    - demand enters already separated by thermal end-use and building type
    - supply is prepared source-by-source, but remains empty until technologies are wired
    - storage is represented structurally so a central DH store can be attached later
    """

    demand_space_by_type = dh_demand["space_heat_by_type"]
    demand_hotwater_by_type = dh_demand["hotwater_by_type"]
    demand_total_by_type = dh_demand["total_by_type"]
    demand_total = np.asarray(dh_demand["total"], dtype=float)
    n_steps = demand_total.shape[0]

    delivery_space_by_type = _zeros_like_series_map(demand_space_by_type)
    delivery_hotwater_by_type = _zeros_like_series_map(demand_hotwater_by_type)
    delivery_total_by_type = _zeros_like_series_map(demand_total_by_type)

    supply: Dict[str, Dict[str, np.ndarray]] = {}
    for source_name in source_names:
        source_key = str(source_name)
        supply[source_key] = {"thermal_kwh": np.zeros(n_steps, dtype=float)}

    return {
        "demand": {
            "space_heat_by_type": demand_space_by_type,
            "hotwater_by_type": demand_hotwater_by_type,
            "total_by_type": demand_total_by_type,
            "space_heat_total": np.asarray(dh_demand["space_heat_total"], dtype=float),
            "hotwater_total": np.asarray(dh_demand["hotwater_total"], dtype=float),
            "total": demand_total,
        },
        "supply": supply,
        "storage": {
            "charge_kwh": np.zeros(n_steps, dtype=float),
            "discharge_kwh": np.zeros(n_steps, dtype=float),
            "losses_kwh": np.zeros(n_steps, dtype=float),
            "soc_kwh": np.zeros(n_steps, dtype=float),
        },
        "delivery": {
            "space_heat_by_type": delivery_space_by_type,
            "hotwater_by_type": delivery_hotwater_by_type,
            "total_by_type": delivery_total_by_type,
            "space_heat_total": np.zeros(n_steps, dtype=float),
            "hotwater_total": np.zeros(n_steps, dtype=float),
            "total": np.zeros(n_steps, dtype=float),
        },
        "meta": {
            "connected_equivalent_units_by_type": dict(dh_demand["connected_equivalent_units_by_type"]),
            "connected_share_by_type": dict(dh_demand["connected_share_by_type"]),
            "building_types": list(dh_buildings["by_type"].keys()),
            "source_names": [str(name) for name in source_names],
        },
    }
