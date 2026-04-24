from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, Optional

from Data.thermal_archetypes.Vienna.calibrated_v1 import (
    build_calibrated_v1_values as build_calibrated_v1_values_vienna,
)
from Data.thermal_archetypes.Vienna.thermal_archetypes import (
    build_thermal_archetypes_values as build_thermal_archetypes_values_vienna,
)


@dataclass
class ThermalArchetypeConfig:
    key: str
    sector: str
    construction_period: str

    u_wall: Optional[float] = None
    u_window: Optional[float] = None
    u_roof: Optional[float] = None
    u_floor: Optional[float] = None

    wall_area_per_gfa: Optional[float] = None
    window_area_per_gfa: Optional[float] = None
    roof_area_per_gfa: Optional[float] = None
    floor_exposed_per_gfa: Optional[float] = None

    conditioned_floor_share_of_gfa: Optional[float] = None
    c_th_wh_per_m2k: Optional[float] = None
    window_typology_class: Optional[str] = None
    window_pane_count: Optional[int] = None
    window_glazing_family: Optional[str] = None
    window_frame_type: Optional[str] = None
    window_has_low_e: Optional[bool] = None
    window_has_inert_gas_fill: Optional[bool] = None
    window_has_thermal_break: Optional[bool] = None
    window_g_value: Optional[float] = None
    window_visible_transmittance: Optional[float] = None
    glazing_source: Optional[str] = None
    solar_shading_assumption: Optional[str] = None
    window_data_source_note: Optional[str] = None
    calibration_v1: Optional[Dict[str, Any]] = None

    t_min_k: float = 294.15
    t_max_k: float = 300.15


@dataclass
class ThermalArchetypesConfig:
    source: str = "pending_manual_values"
    variant: str = "default"
    location: Optional[str] = None
    base_source: Optional[str] = None
    archetypes: Dict[str, ThermalArchetypeConfig] = field(default_factory=dict)
    notes: list[str] = field(default_factory=list)

def make_thermal_archetypes(location: str, *, variant: str = "default") -> ThermalArchetypesConfig:
    if not isinstance(location, str) or not location.strip():
        raise ValueError("[thermal_archetypes] Explicit non-empty location is required.")
    resolved_location = location.strip()
    if resolved_location != "Vienna":
        raise ValueError(
            f"[thermal_archetypes] No thermal-archetype registry registered for location='{resolved_location}'."
        )
    resolved_variant = str(variant or "").strip()
    if not resolved_variant:
        raise ValueError("[thermal_archetypes] Explicit non-empty variant is required.")
    if resolved_variant == "default":
        raw = build_thermal_archetypes_values_vienna()
    elif resolved_variant == "calibrated_v1":
        raw = build_calibrated_v1_values_vienna()
    else:
        raise ValueError(
            f"[thermal_archetypes] Unknown variant='{resolved_variant}' for location='{resolved_location}'."
        )

    archetypes = {
        key: ThermalArchetypeConfig(**dict(payload))
        for key, payload in dict(raw["archetypes"]).items()
    }
    if resolved_variant == "calibrated_v1":
        missing = [key for key, cfg in archetypes.items() if not isinstance(cfg.calibration_v1, dict)]
        if missing:
            raise ValueError(
                "[thermal_archetypes] calibrated_v1 requires calibration_v1 payload for every archetype. "
                f"Missing={missing}"
            )
    return ThermalArchetypesConfig(
        source=str(raw["source"]),
        variant=resolved_variant,
        location=str(raw["location"]),
        base_source=str(raw.get("base_source")) if raw.get("base_source") is not None else None,
        archetypes=archetypes,
        notes=[str(note) for note in raw.get("notes", [])],
    )
