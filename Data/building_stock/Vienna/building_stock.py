from __future__ import annotations

from pathlib import Path


CITIWATT_SOURCE_FILE_PATH = Path(
    r"C:\Users\Philipp Thunshirn\Desktop\PhD\Daten\Citiwatt_indicators_Vienna.txt"
)
ENERGY_REPORT_SOURCE_FILE_PATH = Path(
    r"C:\Users\Philipp Thunshirn\Downloads\2025.pdf"
)


TOTAL_HEAT_GWH = 17_535.85
RESIDENTIAL_HEAT_GWH = 11_618.11
NON_RESIDENTIAL_HEAT_GWH = 5_917.75

TOTAL_GFA_M2 = 134_556_538.4
RESIDENTIAL_GFA_M2 = 89_024_897.46
NON_RESIDENTIAL_GFA_M2 = 45_531_640.93

TOTAL_VOLUME_M3 = 403_669_443.4
RESIDENTIAL_VOLUME_M3 = 267_075_676.5
NON_RESIDENTIAL_VOLUME_M3 = 136_593_766.8

RESIDENTIAL_ELECTRICITY_OFFICIAL_GWH = 3_423.0
NON_RESIDENTIAL_BUILDINGS_ELECTRICITY_OFFICIAL_GWH = 2_887.0

RESIDENTIAL_HOTWATER_INTENSITY_KWH_PER_M2A = 15.5
RESIDENTIAL_HOTWATER_GWH = (RESIDENTIAL_GFA_M2 * RESIDENTIAL_HOTWATER_INTENSITY_KWH_PER_M2A) / 1_000_000.0
NON_RESIDENTIAL_HOTWATER_GWH = 0.0
TOTAL_HOTWATER_GWH = RESIDENTIAL_HOTWATER_GWH + NON_RESIDENTIAL_HOTWATER_GWH

RESIDENTIAL_SPACE_HEAT_GWH = RESIDENTIAL_HEAT_GWH - RESIDENTIAL_HOTWATER_GWH
NON_RESIDENTIAL_SPACE_HEAT_GWH = NON_RESIDENTIAL_HEAT_GWH - NON_RESIDENTIAL_HOTWATER_GWH
TOTAL_SPACE_HEAT_GWH = RESIDENTIAL_SPACE_HEAT_GWH + NON_RESIDENTIAL_SPACE_HEAT_GWH

# 2023 calibration proxy:
# exogenous profile anchors are kept explicit and separate from the official
# sector electricity anchors. They are calibrated from the 2023 Vienna
# building-sector end-use proxy:
# exogenous = official - modeled local thermal electricity proxy.
RESIDENTIAL_ELECTRICITY_EXOGENOUS_GWH = 2_737.7784174886034
NON_RESIDENTIAL_BUILDINGS_ELECTRICITY_EXOGENOUS_GWH = 2_264.098809953804

CONSTRUCTION_PERIOD_SHARES_RAW = {
    "pre1975": 0.54,
    "1975_1990": 0.24,
    "1990_2000": 0.04,
    "2000_2014": 0.17,
}

RESIDENTIAL_LOAD_MIX = {"H0": 1.0}
NON_RESIDENTIAL_LOAD_MIX = {
    "G0": 0.25,
    "G1": 0.25,
    "G2": 0.25,
    "G3": 0.25,
}

# 2023 reference proxy used for anchor-calibration only.
# The values describe the electric share within the non-DH block and are
# derived from Vienna status-quo sources documented in Documentation/Sources/.
REFERENCE_2023_NON_DH_ELECTRIC_SHARES = {
    "residential_space_heat": 0.076,
    "residential_hotwater": 0.223,
    "non_residential_space_heat": 0.249,
    # Current repo v1 keeps non-residential hot water excluded on purpose.
    "non_residential_hotwater": 0.0,
}


def _normalize_shares(raw: dict[str, float]) -> dict[str, float]:
    total = float(sum(float(v) for v in raw.values()))
    if total <= 0.0:
        raise ValueError("[building_stock_vienna] Construction-period shares must sum to > 0.")
    return {str(k): float(v) / total for k, v in raw.items()}


def _sector_rows(
    *,
    sector: str,
    total_gfa_m2: float,
    total_volume_m3: float,
    total_heat_gwh: float,
    total_space_heat_gwh: float,
    total_hotwater_gwh: float,
    total_electricity_official_gwh: float,
    total_electricity_exogenous_gwh: float,
    include_hotwater: bool,
    load_profile_mix: dict[str, float],
    dh_connected_share_override: float | None = None,
) -> list[dict[str, object]]:
    shares = _normalize_shares(CONSTRUCTION_PERIOD_SHARES_RAW)
    out: list[dict[str, object]] = []
    for period, share in shares.items():
        cohort_id = f"{sector}_{period}"
        out.append(
            {
                "cohort_id": cohort_id,
                "sector": sector,
                "construction_period": period,
                "load_profile_mix": dict(load_profile_mix),
                "thermal_archetype_key": cohort_id,
                "represented_gfa_m2": float(total_gfa_m2) * share,
                "represented_volume_m3": float(total_volume_m3) * share,
                "annual_heat_target_kwh": float(total_heat_gwh) * 1_000_000.0 * share,
                "annual_space_heat_target_kwh": float(total_space_heat_gwh) * 1_000_000.0 * share,
                "annual_hotwater_target_kwh": float(total_hotwater_gwh) * 1_000_000.0 * share,
                "annual_electricity_official_kwh": float(total_electricity_official_gwh) * 1_000_000.0 * share,
                "annual_electricity_target_kwh": float(total_electricity_exogenous_gwh) * 1_000_000.0 * share,
                "dh_connected_share_override": dh_connected_share_override,
                "include_hotwater": bool(include_hotwater),
            }
        )
    return out


def build_building_stock_values() -> dict[str, object]:
    cohorts: list[dict[str, object]] = []
    cohorts.extend(
        _sector_rows(
            sector="residential",
            total_gfa_m2=RESIDENTIAL_GFA_M2,
            total_volume_m3=RESIDENTIAL_VOLUME_M3,
            total_heat_gwh=RESIDENTIAL_HEAT_GWH,
            total_space_heat_gwh=RESIDENTIAL_SPACE_HEAT_GWH,
            total_hotwater_gwh=RESIDENTIAL_HOTWATER_GWH,
            total_electricity_official_gwh=RESIDENTIAL_ELECTRICITY_OFFICIAL_GWH,
            total_electricity_exogenous_gwh=RESIDENTIAL_ELECTRICITY_EXOGENOUS_GWH,
            include_hotwater=True,
            load_profile_mix=RESIDENTIAL_LOAD_MIX,
        )
    )
    cohorts.extend(
        _sector_rows(
            sector="non_residential",
            total_gfa_m2=NON_RESIDENTIAL_GFA_M2,
            total_volume_m3=NON_RESIDENTIAL_VOLUME_M3,
            total_heat_gwh=NON_RESIDENTIAL_HEAT_GWH,
            total_space_heat_gwh=NON_RESIDENTIAL_SPACE_HEAT_GWH,
            total_hotwater_gwh=NON_RESIDENTIAL_HOTWATER_GWH,
            total_electricity_official_gwh=NON_RESIDENTIAL_BUILDINGS_ELECTRICITY_OFFICIAL_GWH,
            total_electricity_exogenous_gwh=NON_RESIDENTIAL_BUILDINGS_ELECTRICITY_EXOGENOUS_GWH,
            include_hotwater=False,
            load_profile_mix=NON_RESIDENTIAL_LOAD_MIX,
        )
    )
    return {
        "source": "manual_citiwatt_energy_report_snapshot",
        "location": "Vienna",
        "space_heat_distribution_mode": "sector_total_from_modeled_raw_profiles",
        "source_file_paths": [
            str(CITIWATT_SOURCE_FILE_PATH),
            str(ENERGY_REPORT_SOURCE_FILE_PATH),
        ],
        "annual_heat_total_kwh": TOTAL_HEAT_GWH * 1_000_000.0,
        "annual_heat_residential_kwh": RESIDENTIAL_HEAT_GWH * 1_000_000.0,
        "annual_heat_non_residential_kwh": NON_RESIDENTIAL_HEAT_GWH * 1_000_000.0,
        "annual_space_heat_total_kwh": TOTAL_SPACE_HEAT_GWH * 1_000_000.0,
        "annual_hotwater_total_kwh": TOTAL_HOTWATER_GWH * 1_000_000.0,
        "annual_electricity_residential_kwh": RESIDENTIAL_ELECTRICITY_OFFICIAL_GWH * 1_000_000.0,
        "annual_electricity_non_residential_buildings_kwh": NON_RESIDENTIAL_BUILDINGS_ELECTRICITY_OFFICIAL_GWH * 1_000_000.0,
        "annual_electricity_exogenous_residential_kwh": RESIDENTIAL_ELECTRICITY_EXOGENOUS_GWH * 1_000_000.0,
        "annual_electricity_exogenous_non_residential_buildings_kwh": NON_RESIDENTIAL_BUILDINGS_ELECTRICITY_EXOGENOUS_GWH * 1_000_000.0,
        "gross_floor_area_total_m2": TOTAL_GFA_M2,
        "gross_floor_area_residential_m2": RESIDENTIAL_GFA_M2,
        "gross_floor_area_non_residential_m2": NON_RESIDENTIAL_GFA_M2,
        "building_volume_total_m3": TOTAL_VOLUME_M3,
        "building_volume_residential_m3": RESIDENTIAL_VOLUME_M3,
        "building_volume_non_residential_m3": NON_RESIDENTIAL_VOLUME_M3,
        "construction_period_shares": _normalize_shares(CONSTRUCTION_PERIOD_SHARES_RAW),
        "reference_2023_non_dh_electric_shares": dict(REFERENCE_2023_NON_DH_ELECTRIC_SHARES),
        "cohorts": cohorts,
    }
