from __future__ import annotations

from dataclasses import dataclass


NHESS_SUPPLEMENT_URL = (
    "https://nhess.copernicus.org/articles/25/4807/2025/nhess-25-4807-2025-supplement.pdf"
)
ECAD_STATION_DETAIL_URL = "https://www.ecad.eu/utils/stationdetail.php?stationid=16"


@dataclass(frozen=True)
class SolarThermalReferenceSite:
    name: str
    latitude_deg: float
    longitude_deg: float
    source_urls: tuple[str, ...]
    note: str


VIENNA_HOHE_WARTE_REFERENCE_SITE = SolarThermalReferenceSite(
    name="Wien-Hohe Warte (WMO 11035)",
    latitude_deg=48.2486,
    longitude_deg=16.3564,
    source_urls=(
        NHESS_SUPPLEMENT_URL,
        ECAD_STATION_DETAIL_URL,
    ),
    note=(
        "Representative Vienna v1 solar-thermal transposition site. "
        "Coordinates are rounded from the documented Hohe Warte station location."
    ),
)


def build_solar_thermal_reference_site_values() -> dict[str, object]:
    site = VIENNA_HOHE_WARTE_REFERENCE_SITE
    return {
        "name": str(site.name),
        "latitude_deg": float(site.latitude_deg),
        "longitude_deg": float(site.longitude_deg),
        "source_urls": list(site.source_urls),
        "note": str(site.note),
    }
