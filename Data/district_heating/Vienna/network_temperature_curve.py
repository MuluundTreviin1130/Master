from __future__ import annotations

from dataclasses import dataclass


UBA_REP_0074_URL = "https://www.umweltbundesamt.at/fileadmin/site/publikationen/REP0074.pdf"
WIEN_ENERGIE_AUSLEGUNGSBEDINGUNGEN_2013_URL = (
    "https://dokumente.wienenergie.at/wp-content/uploads/technische-auslegungsbedingungen-2013.pdf"
)
WIEN_ENERGIE_TAB_FW_2025_URL = (
    "https://dokumente.wienenergie.at/link/technische-anschlussbedingungen-fernwaerme-tab-fw/"
)


@dataclass(frozen=True)
class NetworkTemperatureCurvePoint:
    outdoor_temp_c: float
    network_temp_c: float


# Vienna v1 legacy reference curve.
# We intentionally keep this minimal and document-based:
# - summer/network minimum from UBA REP-0074: 95 C supply, typical lower return around 55 C
# - winter/network maximum from UBA REP-0074: 150 C supply, typical upper return around 75 C
# - the 2013 Wien-Energie curve sheets justify weather-guided operation over outdoor temperature
# - the x-axis on those sheets spans down to -15 C, so we map the historical winter maximum to -15 C
VIENNA_V1_SUPPLY_CURVE_POINTS_C: tuple[NetworkTemperatureCurvePoint, ...] = (
    NetworkTemperatureCurvePoint(outdoor_temp_c=-15.0, network_temp_c=150.0),
    NetworkTemperatureCurvePoint(outdoor_temp_c=20.0, network_temp_c=95.0),
)

VIENNA_V1_RETURN_CURVE_POINTS_C: tuple[NetworkTemperatureCurvePoint, ...] = (
    NetworkTemperatureCurvePoint(outdoor_temp_c=-15.0, network_temp_c=75.0),
    NetworkTemperatureCurvePoint(outdoor_temp_c=20.0, network_temp_c=55.0),
)


def build_network_temperature_curve_values() -> dict[str, object]:
    return {
        "source": "manual_vienna_legacy_reference_curve_v1",
        "location": "Vienna",
        "source_urls": [
            UBA_REP_0074_URL,
            WIEN_ENERGIE_AUSLEGUNGSBEDINGUNGEN_2013_URL,
            WIEN_ENERGIE_TAB_FW_2025_URL,
        ],
        "note": (
            "Vienna v1 effective DH bus curve. Linear interpolation between documented legacy anchors "
            "(95 C summer minimum / 150 C winter maximum, 55-75 C return band). "
            "The 2013 Wien-Energie temperature curve sheets justify weather-guided operation; "
            "more detailed support points can replace this snapshot later."
        ),
        "supply_curve_points_c": tuple(
            (float(point.outdoor_temp_c), float(point.network_temp_c))
            for point in VIENNA_V1_SUPPLY_CURVE_POINTS_C
        ),
        "return_curve_points_c": tuple(
            (float(point.outdoor_temp_c), float(point.network_temp_c))
            for point in VIENNA_V1_RETURN_CURVE_POINTS_C
        ),
    }
