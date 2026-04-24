from __future__ import annotations

from dataclasses import dataclass, field
from typing import Tuple

from Data.district_heating.Vienna.network_temperature_curve import (
    build_network_temperature_curve_values as build_network_temperature_curve_values_vienna,
)


CurvePoint = Tuple[float, float]


@dataclass
class DistrictHeatingConfig:
    """Single source of truth for the runtime district-heating bus settings."""

    share: float = 0.0
    pinch_point_c: float = 10.0
    curve_source: str = "unset"
    curve_source_urls: list[str] = field(default_factory=list)
    curve_note: str = ""
    supply_curve_points_c: tuple[CurvePoint, ...] = ()
    return_curve_points_c: tuple[CurvePoint, ...] = ()


def make_district_heating(location: str | None = None) -> DistrictHeatingConfig:
    cfg = DistrictHeatingConfig()
    if location == "Vienna":
        raw = build_network_temperature_curve_values_vienna()
        cfg.curve_source = str(raw["source"])
        cfg.curve_source_urls = [str(x) for x in raw.get("source_urls", [])]
        cfg.curve_note = str(raw.get("note", ""))
        cfg.supply_curve_points_c = tuple(
            (float(t_out), float(t_supply)) for t_out, t_supply in raw.get("supply_curve_points_c", ())
        )
        cfg.return_curve_points_c = tuple(
            (float(t_out), float(t_return)) for t_out, t_return in raw.get("return_curve_points_c", ())
        )
    return cfg
