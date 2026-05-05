from __future__ import annotations

import os
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

from .registry import (
    location_loadprofiles,
    location_PVprofiles,
    location_temp_profiles,
    location_wind_profiles,
    location_solarirradiation_profiles,
    location_solargains_profiles,
    location_usage_profiles,
    location_V2H_profiles,
)


def _numeric_profile_array(values: Any, label: str) -> np.ndarray:
    """Convert one source column to float and fail fast on missing/non-numeric cells."""
    arr = np.asarray(pd.to_numeric(values, errors="coerce"), dtype=float)
    invalid = ~np.isfinite(arr)
    if bool(invalid.any()):
        first_idx = int(np.flatnonzero(invalid)[0])
        raise ValueError(
            f"[profiles] {label} contains {int(invalid.sum())} non-finite/non-numeric values; "
            f"first invalid row index={first_idx}. Clean the source data before simulation."
        )
    return arr


def _unit_interval_profile_array(values: Any, label: str) -> np.ndarray:
    """Validate profile fractions explicitly instead of clipping corrupt source values."""
    arr = _numeric_profile_array(values, label)
    outside = (arr < 0.0) | (arr > 1.0)
    if bool(outside.any()):
        first_idx = int(np.flatnonzero(outside)[0])
        raise ValueError(
            f"[profiles] {label} contains {int(outside.sum())} values outside [0, 1]; "
            f"first invalid row index={first_idx}. Source profiles must be fractional values."
        )
    return arr


def _require_same_length(reference_len: int, label: str, arr: np.ndarray) -> None:
    """Keep all hourly source profiles on the same horizon before downstream broadcasting."""
    if len(arr) != int(reference_len):
        raise ValueError(
            f"[profiles] {label} length mismatch: expected {int(reference_len)} rows from load profiles, "
            f"got {len(arr)} rows."
        )


def _matching_profile_column(columns: Any, name_substr: str, exclude_substrs: Tuple[str, ...] = ()) -> str:
    """Resolve one source column explicitly so overlapping V2H headers cannot be misread."""
    matches = [
        c
        for c in columns
        if name_substr in str(c).strip().lower()
        and not any(excl in str(c).strip().lower() for excl in exclude_substrs)
    ]
    if len(matches) == 1:
        return matches[0]
    if not matches:
        raise KeyError(f"[profiles] Missing ENTSOE-Profiles column containing: '{name_substr}'")
    raise KeyError(
        f"[profiles] Ambiguous ENTSOE-Profiles column containing '{name_substr}': {matches}. "
        "Use a more specific source header."
    )


def load_v2h_profiles(file_path: str, n_steps: int) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Build yearly V2H profiles directly from ENTSOE weekday/weekend templates."""
    if not file_path or not os.path.exists(file_path):
        raise FileNotFoundError(f"[profiles] V2H profile file not found: {file_path}")

    xls = pd.ExcelFile(file_path)
    if "ENTSOE-Profiles" not in xls.sheet_names:
        raise KeyError("[profiles] Missing required sheet 'ENTSOE-Profiles'.")

    src = pd.read_excel(file_path, sheet_name="ENTSOE-Profiles", header=1)
    src_cols = {str(c).strip().lower(): c for c in src.columns}
    hour_col = src_cols.get("hour")
    if hour_col is None:
        raise KeyError("[profiles] ENTSOE-Profiles requires an 'Hour' column.")

    src["_hour"] = pd.to_numeric(src[hour_col], errors="coerce")
    src = src.dropna(subset=["_hour"]).copy()
    src["_hour"] = src["_hour"].astype(int)
    src = src[(src["_hour"] >= 1) & (src["_hour"] <= 24)].sort_values("_hour")

    # Prosumer (min_SOC + availability), Passenger (driving).
    c_min_weekday = _matching_profile_column(src.columns, "prosumer weekday 2030")
    c_min_weekend = _matching_profile_column(src.columns, "street weekday 2030")
    c_drv_weekday = _matching_profile_column(src.columns, "passenger weekday")
    c_drv_weekend = _matching_profile_column(src.columns, "passenger weekend")
    c_av_weekday = _matching_profile_column(src.columns, "prosumer weekday", exclude_substrs=("2030",))
    c_av_weekend = _matching_profile_column(src.columns, "prosumer weekend")

    expected_hours = list(range(1, 25))
    actual_hours = src["_hour"].tolist()
    if actual_hours != expected_hours:
        raise ValueError(
            f"[profiles] ENTSOE-Profiles must provide each hour 1..24 exactly once; got {actual_hours}."
        )

    min_weekday = _unit_interval_profile_array(src[c_min_weekday], f"V2H column '{c_min_weekday}'")
    min_weekend = _unit_interval_profile_array(src[c_min_weekend], f"V2H column '{c_min_weekend}'")
    drv_weekday = _unit_interval_profile_array(src[c_drv_weekday], f"V2H column '{c_drv_weekday}'")
    drv_weekend = _unit_interval_profile_array(src[c_drv_weekend], f"V2H column '{c_drv_weekend}'")
    av_weekday = _unit_interval_profile_array(src[c_av_weekday], f"V2H column '{c_av_weekday}'")
    av_weekend = _unit_interval_profile_array(src[c_av_weekend], f"V2H column '{c_av_weekend}'")

    if not all(arr.size == 24 for arr in [min_weekday, min_weekend, drv_weekday, drv_weekend, av_weekday, av_weekend]):
        raise ValueError("[profiles] ENTSOE-Profiles must provide 24 hourly rows.")

    idx = pd.date_range("2023-01-01", periods=int(n_steps), freq="h")
    h = idx.hour.to_numpy(dtype=int)
    is_weekend = np.asarray(idx.weekday >= 5, dtype=bool)

    min_soc = np.where(is_weekend, min_weekend[h], min_weekday[h]).astype(float)
    driving = np.where(is_weekend, drv_weekend[h], drv_weekday[h]).astype(float)
    availability = np.where(is_weekend, av_weekend[h], av_weekday[h]).astype(float)

    return min_soc, availability, driving


def load_profiles(
    location: str,
    member_ids: Optional[List[str]] = None,
    member_counts: Optional[List[int]] = None,
    members: Optional[List[Any]] = None,
    require_wind: bool = True,
) -> Dict[str, object]:
    """
    Load profiles for a location.

    Args:
        location: Location name (e.g., "Vienna")
        member_ids: Required list of member profile IDs in legacy mode
        member_counts: Optional list of counts per member_id (must match member_ids length)
        members: Optional runtime member configs with load_profile_mix/load_profile_key

    Returns:
        Dict with profiles:
            - 'load_member_2d': [T, N_EC] array with per-member load profiles
            - 'load': [T] aggregated load (sum across all members)
    """
    if location not in location_loadprofiles:
        raise KeyError(f"Lastprofil fuer Standort '{location}' nicht definiert.")
    if location not in location_PVprofiles:
        raise KeyError(f"PV-Profil fuer Standort '{location}' nicht definiert.")
    if location not in location_temp_profiles:
        raise KeyError(f"Temperaturprofil fuer Standort '{location}' nicht definiert.")
    if require_wind and location not in location_wind_profiles:
        raise KeyError(f"Windprofil fuer Standort '{location}' nicht definiert.")
    if location not in location_solarirradiation_profiles:
        raise KeyError(f"Einstrahlungsprofil fuer Standort '{location}' nicht definiert.")
    if location not in location_solargains_profiles:
        raise KeyError(f"Solargewinne fuer Standort '{location}' nicht definiert.")

    df_load = pd.read_excel(location_loadprofiles[location], sheet_name="loadprofiles")

    n_steps = len(df_load)
    if members is not None:
        active_members = [m for m in members if int(getattr(m, "count", 0)) > 0]
        if not active_members:
            raise ValueError("[profiles] At least one active member is required.")
        n_ec = sum(int(getattr(m, "count", 0)) for m in active_members)
        load_member_2d = np.zeros((n_steps, n_ec), dtype=float)
        col_idx = 0
        for member in active_members:
            count = int(getattr(member, "count", 0))
            profile_mix = dict(getattr(member, "load_profile_mix", {}) or {})
            if profile_mix:
                missing = [key for key in profile_mix if key not in df_load.columns]
                if missing:
                    raise KeyError(
                        f"[profiles] Load-profile mix keys not found in Excel columns: {missing}. "
                        f"Available: {list(df_load.columns)}"
                    )
                mixed_profile = np.zeros(n_steps, dtype=float)
                for key, weight in profile_mix.items():
                    member_part = _numeric_profile_array(df_load[str(key)], f"load-profile mix column '{key}'")
                    mixed_profile += float(weight) * member_part
                member_profile = mixed_profile
            else:
                profile_key = str(getattr(member, "load_profile_key", "") or getattr(member, "member_id", ""))
                if profile_key not in df_load.columns:
                    raise KeyError(
                        f"[profiles] Member load_profile_key '{profile_key}' not found. "
                        f"Available: {list(df_load.columns)}"
                    )
                member_profile = _numeric_profile_array(df_load[profile_key], f"load-profile column '{profile_key}'")
            for _ in range(count):
                load_member_2d[:, col_idx] = member_profile
                col_idx += 1
    else:
        if member_ids is None or len(member_ids) == 0:
            raise ValueError(
                "member_ids or members must be provided. No legacy fallback available."
            )

        if member_counts is None:
            member_counts = [1] * len(member_ids)
        if len(member_counts) != len(member_ids):
            raise ValueError(
                f"member_counts length ({len(member_counts)}) must match member_ids length ({len(member_ids)})"
            )

        missing = [mid for mid in member_ids if mid not in df_load.columns]
        if missing:
            raise KeyError(f"Member IDs not found in Excel columns: {missing}. Available: {list(df_load.columns)}")

        n_ec = sum(member_counts)
        load_member_2d = np.zeros((n_steps, n_ec), dtype=float)
        col_idx = 0
        for member_id, count in zip(member_ids, member_counts):
            member_profile = _numeric_profile_array(df_load[member_id], f"load-profile column '{member_id}'")
            for _ in range(count):
                load_member_2d[:, col_idx] = member_profile
                col_idx += 1

    load_array = load_member_2d.sum(axis=1)

    df_pv = pd.read_csv(location_PVprofiles[location], sep=";", decimal=",")
    pv_array = _numeric_profile_array(df_pv["PPV"], "PV column 'PPV'")

    df_temp = pd.read_csv(location_temp_profiles[location], sep=";", decimal=",")
    temp_array = _numeric_profile_array(df_temp["T2m"], "temperature column 'T2m'")
    temp_series = pd.Series(temp_array, index=df_temp["time"])

    if require_wind:
        df_wind = pd.read_csv(location_wind_profiles[location])
        if "p" not in df_wind.columns:
            raise KeyError(f"[profiles] Wind profile for location '{location}' is missing required pressure column 'p'.")
        wind_speed_array = _numeric_profile_array(df_wind["ff"], "wind column 'ff'")
        wind_pressure_array = _numeric_profile_array(df_wind["p"], "wind column 'p'")

    df_irr = pd.read_csv(location_solarirradiation_profiles[location], sep=";", decimal=",")
    irr_array = _numeric_profile_array(df_irr["solar_irradiance_total"], "irradiance column 'solar_irradiance_total'")

    df_solargains = pd.read_csv(location_solargains_profiles[location], sep=";", decimal=",")
    solargains_array = _numeric_profile_array(df_solargains["solar_gains_(W/m2)"], "solar-gains column 'solar_gains_(W/m2)'")

    n_steps = len(load_array)
    _require_same_length(n_steps, "PV profile", pv_array)
    _require_same_length(n_steps, "temperature profile", temp_array)
    _require_same_length(n_steps, "irradiance profile", irr_array)
    _require_same_length(n_steps, "solar-gains profile", solargains_array)
    if require_wind:
        _require_same_length(n_steps, "wind-speed profile", wind_speed_array)
        _require_same_length(n_steps, "wind-pressure profile", wind_pressure_array)
    min_soc, availability_profile, driving_profile = load_v2h_profiles(location_V2H_profiles, n_steps)

    result = {
        "load": np.asarray(load_array),
        "load_member_2d": load_member_2d,
        "pv_generation": np.asarray(pv_array),
        "T_outdoor": np.asarray(temp_series),
        "irradiance": np.asarray(irr_array),
        "solargains": np.asarray(solargains_array),
        "min_SOC": np.asarray(min_soc),
        "availability_profile": np.asarray(availability_profile),
        "driving_profile": np.asarray(driving_profile),
        "usage_profile": pd.read_excel(location_usage_profiles, sheet_name=0),
    }
    if require_wind:
        result["wind_speed_ms"] = np.asarray(wind_speed_array)
        result["wind_pressure_hpa"] = np.asarray(wind_pressure_array)

    return result
