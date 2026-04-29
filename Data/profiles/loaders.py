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

    def _col_exact(column_name: str) -> str:
        """Resolve a spreadsheet column by exact normalized header.

        The V2H workbook contains both "PROSUMER WEEKDAY 2030 [%]" (minimum
        SOC) and "PROSUMER WEEKDAY [%]" (availability).  A substring lookup for
        "prosumer weekday" therefore silently binds availability to the minimum
        SOC column and suppresses weekday V2H availability.  Exact lookup keeps
        the workbook schema explicit and fails fast if the header changes.
        """

        key = str(column_name).strip().lower()
        if key not in src_cols:
            raise KeyError(
                f"[profiles] Missing ENTSOE-Profiles column '{column_name}'. "
                f"Available: {list(src.columns)}"
            )
        return src_cols[key]

    # Prosumer (min_SOC + availability), Passenger (driving).
    c_min_weekday = _col_exact("PROSUMER WEEKDAY 2030 [%]")
    c_min_weekend = _col_exact("STREET WEEKDAY 2030 [%]")
    c_drv_weekday = _col_exact("PASSENGER WEEKDAY [%]")
    c_drv_weekend = _col_exact("PASSENGER WEEKEND [%]")
    c_av_weekday = _col_exact("PROSUMER WEEKDAY [%]")
    c_av_weekend = _col_exact("PROSUMER WEEKEND [%]")

    min_weekday = pd.to_numeric(src[c_min_weekday], errors="coerce").to_numpy(dtype=float)
    min_weekend = pd.to_numeric(src[c_min_weekend], errors="coerce").to_numpy(dtype=float)
    drv_weekday = pd.to_numeric(src[c_drv_weekday], errors="coerce").to_numpy(dtype=float)
    drv_weekend = pd.to_numeric(src[c_drv_weekend], errors="coerce").to_numpy(dtype=float)
    av_weekday = pd.to_numeric(src[c_av_weekday], errors="coerce").to_numpy(dtype=float)
    av_weekend = pd.to_numeric(src[c_av_weekend], errors="coerce").to_numpy(dtype=float)

    if not all(arr.size == 24 for arr in [min_weekday, min_weekend, drv_weekday, drv_weekend, av_weekday, av_weekend]):
        raise ValueError("[profiles] ENTSOE-Profiles must provide 24 hourly rows.")

    idx = pd.date_range("2023-01-01", periods=int(n_steps), freq="h")
    h = idx.hour.to_numpy(dtype=int)
    is_weekend = np.asarray(idx.weekday >= 5, dtype=bool)

    min_soc = np.where(is_weekend, min_weekend[h], min_weekday[h]).astype(float)
    driving = np.where(is_weekend, drv_weekend[h], drv_weekday[h]).astype(float)
    availability = np.where(is_weekend, av_weekend[h], av_weekday[h]).astype(float)

    min_soc = np.clip(np.nan_to_num(min_soc, nan=0.3), 0.0, 1.0)
    driving = np.clip(np.nan_to_num(driving, nan=0.0), 0.0, 1.0)
    availability = np.clip(np.nan_to_num(availability, nan=0.0), 0.0, 1.0)
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
                    mixed_profile += float(weight) * pd.to_numeric(df_load[str(key)], errors="coerce").to_numpy(dtype=float)
                member_profile = mixed_profile
            else:
                profile_key = str(getattr(member, "load_profile_key", "") or getattr(member, "member_id", ""))
                if profile_key not in df_load.columns:
                    raise KeyError(
                        f"[profiles] Member load_profile_key '{profile_key}' not found. "
                        f"Available: {list(df_load.columns)}"
                    )
                member_profile = pd.to_numeric(df_load[profile_key], errors="coerce").to_numpy(dtype=float)
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
            member_profile = pd.to_numeric(df_load[member_id], errors="coerce").to_numpy(dtype=float)
            for _ in range(count):
                load_member_2d[:, col_idx] = member_profile
                col_idx += 1

    load_array = load_member_2d.sum(axis=1)

    df_pv = pd.read_csv(location_PVprofiles[location], sep=";", decimal=",")
    pv_array = pd.to_numeric(df_pv["PPV"], errors="coerce").to_numpy()

    df_temp = pd.read_csv(location_temp_profiles[location], sep=";", decimal=",")
    temp_series = pd.Series(pd.to_numeric(df_temp["T2m"], errors="coerce").values, index=df_temp["time"])

    if require_wind:
        df_wind = pd.read_csv(location_wind_profiles[location])
        if "p" not in df_wind.columns:
            raise KeyError(f"[profiles] Wind profile for location '{location}' is missing required pressure column 'p'.")
        wind_speed_array = pd.to_numeric(df_wind["ff"], errors="coerce").to_numpy(dtype=float)
        wind_pressure_array = pd.to_numeric(df_wind["p"], errors="coerce").to_numpy(dtype=float)
        n_nan_speed = int(np.isnan(wind_speed_array).sum())
        n_nan_pressure = int(np.isnan(wind_pressure_array).sum())
        if n_nan_speed > 0 or n_nan_pressure > 0:
            raise ValueError(
                f"[profiles] Wind profile for location '{location}' contains NaNs: "
                f"ff={n_nan_speed}, p={n_nan_pressure}. Clean the source data before using wind-enabled runs."
            )

    df_irr = pd.read_csv(location_solarirradiation_profiles[location], sep=";", decimal=",")
    irr_array = pd.to_numeric(df_irr["solar_irradiance_total"], errors="coerce").to_numpy()

    df_solargains = pd.read_csv(location_solargains_profiles[location], sep=";", decimal=",")
    solargains_array = pd.to_numeric(df_solargains["solar_gains_(W/m2)"], errors="coerce").to_numpy()

    n_steps = len(load_array)
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
