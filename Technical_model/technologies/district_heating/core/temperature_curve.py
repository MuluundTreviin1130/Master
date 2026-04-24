from __future__ import annotations

from bisect import bisect_left
from typing import Iterable


CurvePoint = tuple[float, float]


def _normalize_curve_points(points: Iterable[CurvePoint], *, label: str) -> list[CurvePoint]:
    normalized: list[CurvePoint] = []
    for item in points:
        if not isinstance(item, (list, tuple)) or len(item) != 2:
            raise ValueError(f"[temperature_curve] {label} entries must be (outdoor_temp_c, network_temp_c).")
        x = float(item[0])
        y = float(item[1])
        normalized.append((x, y))
    if len(normalized) < 2:
        raise ValueError(f"[temperature_curve] {label} must contain at least two support points.")
    normalized.sort(key=lambda row: row[0])
    xs = [row[0] for row in normalized]
    if len(xs) != len(set(xs)):
        raise ValueError(f"[temperature_curve] {label} must not contain duplicate outdoor temperatures.")
    return normalized


def interpolate_curve(points: Iterable[CurvePoint], outdoor_temp_c: float, *, label: str = "curve") -> float:
    curve = _normalize_curve_points(points, label=label)
    x = float(outdoor_temp_c)

    xs = [row[0] for row in curve]
    ys = [row[1] for row in curve]

    if x <= xs[0]:
        return float(ys[0])
    if x >= xs[-1]:
        return float(ys[-1])

    idx = bisect_left(xs, x)
    x0, y0 = curve[idx - 1]
    x1, y1 = curve[idx]
    if x1 == x0:
        return float(y0)
    alpha = (x - x0) / (x1 - x0)
    return float(y0 + alpha * (y1 - y0))


def get_dh_bus_temperatures(outdoor_temp_c: float, district_heating_cfg: object) -> tuple[float, float]:
    if district_heating_cfg is None:
        raise ValueError("[temperature_curve] district_heating config is required.")
    supply_points = getattr(district_heating_cfg, "supply_curve_points_c", None)
    return_points = getattr(district_heating_cfg, "return_curve_points_c", None)
    if not supply_points:
        raise ValueError("[temperature_curve] district_heating.supply_curve_points_c is missing.")
    if not return_points:
        raise ValueError("[temperature_curve] district_heating.return_curve_points_c is missing.")

    supply_temp_c = interpolate_curve(supply_points, outdoor_temp_c, label="district_heating.supply_curve_points_c")
    return_temp_c = interpolate_curve(return_points, outdoor_temp_c, label="district_heating.return_curve_points_c")
    if return_temp_c >= supply_temp_c:
        raise ValueError(
            "[temperature_curve] Interpolated DH return temperature must stay below supply temperature, "
            f"got supply={supply_temp_c:.3f} C, return={return_temp_c:.3f} C."
        )
    return float(supply_temp_c), float(return_temp_c)


def get_required_source_supply_temp_c(outdoor_temp_c: float, district_heating_cfg: object) -> float:
    supply_temp_c, _ = get_dh_bus_temperatures(outdoor_temp_c, district_heating_cfg)
    pinch_point_c = float(getattr(district_heating_cfg, "pinch_point_c", 0.0))
    if pinch_point_c < 0.0:
        raise ValueError(f"[temperature_curve] district_heating.pinch_point_c must be >= 0, got {pinch_point_c}.")
    return float(supply_temp_c + pinch_point_c)


def get_required_preheat_source_temp_c(outdoor_temp_c: float, district_heating_cfg: object) -> float:
    _, return_temp_c = get_dh_bus_temperatures(outdoor_temp_c, district_heating_cfg)
    pinch_point_c = float(getattr(district_heating_cfg, "pinch_point_c", 0.0))
    if pinch_point_c < 0.0:
        raise ValueError(f"[temperature_curve] district_heating.pinch_point_c must be >= 0, got {pinch_point_c}.")
    return float(return_temp_c + pinch_point_c)
