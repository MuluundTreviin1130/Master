from __future__ import annotations

import os
from typing import Dict, List, Optional, Tuple
import numpy as np
import pandas as pd

from .profile_paths import (
    location_loadprofiles,
    location_PVprofiles,
    location_temp_profiles,
    location_solarirradiation_profiles,
    location_solargains_profiles,
    location_usage_profiles,
    location_V2H_profiles,
)

def load_v2h_profiles(file_path: str, n_steps: int) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Versucht V2H-Profile zu laden; wenn Datei fehlt → Dummies der Länge n_steps.

    Verhalten identisch zu deinem aktuellen Data/data.py.
    """
    if file_path and os.path.exists(file_path):
        v2h_df = pd.read_excel(file_path, sheet_name="Yearly_profiles")
        min_SOC = v2h_df['min_SOC'].to_numpy(dtype=float)
        availability_profile = v2h_df['availability_profile'].to_numpy(dtype=float)
        driving_profile = v2h_df['driving_profile'].to_numpy(dtype=float)
        return min_SOC, availability_profile, driving_profile

    zeros = np.zeros(int(n_steps), dtype=float)
    return zeros, zeros.copy(), zeros.copy()


def load_profiles(
    location: str,
    member_ids: Optional[List[str]] = None,
    member_counts: Optional[List[int]] = None,
) -> Dict[str, object]:
    """
    Load profiles for a location.
    
    Args:
        location: Location name (e.g., "Vienna")
        member_ids: Required list of member profile IDs (e.g., ["H0", "G0", "G1"])
        member_counts: Optional list of counts per member_id (must match member_ids length)
    
    Returns:
        Dict with profiles:
            - 'load_member_2d': [T, N_EC] array with per-member load profiles
            - 'load': [T] aggregated load (sum across all members)
    """
    # Checks
    if location not in location_loadprofiles:
        raise KeyError(f"Lastprofil für Standort '{location}' nicht definiert.")
    if location not in location_PVprofiles:
        raise KeyError(f"PV-Profil für Standort '{location}' nicht definiert.")
    if location not in location_temp_profiles:
        raise KeyError(f"Temperaturprofil für Standort '{location}' nicht definiert.")
    if location not in location_solarirradiation_profiles:
        raise KeyError(f"Einstrahlungsprofil für Standort '{location}' nicht definiert.")
    if location not in location_solargains_profiles:
        raise KeyError(f"Solargewinne für Standort '{location}' nicht definiert.")

    # Load profile(s) - member_ids required (no legacy fallback)
    if member_ids is None or len(member_ids) == 0:
        raise ValueError(
            "member_ids must be provided. No legacy fallback available. "
            "Ensure members.yaml exists and load_profiles() is called with member_ids."
        )
    
    if member_counts is None:
        member_counts = [1] * len(member_ids)
    if len(member_counts) != len(member_ids):
        raise ValueError(f"member_counts length ({len(member_counts)}) must match member_ids length ({len(member_ids)})")

    # Load all member columns from Excel
    df_load = pd.read_excel(
        location_loadprofiles[location],
        sheet_name="loadprofiles"
    )
    
    # Verify all member_ids exist as columns
    missing = [mid for mid in member_ids if mid not in df_load.columns]
    if missing:
        raise KeyError(f"Member IDs not found in Excel columns: {missing}. Available: {list(df_load.columns)}")

    # Build load_member_2d: [T, N_EC]
    n_steps = len(df_load)
    N_EC = sum(member_counts)
    load_member_2d = np.zeros((n_steps, N_EC), dtype=float)
    
    col_idx = 0
    for member_id, count in zip(member_ids, member_counts):
        member_profile = pd.to_numeric(df_load[member_id], errors='coerce').to_numpy()
        # Expand this member type to 'count' columns
        for _ in range(count):
            load_member_2d[:, col_idx] = member_profile
            col_idx += 1
    
    # Aggregated load (sum across all members)
    load_array = load_member_2d.sum(axis=1)

    # PV, Wetter, Einstrahlung
    df_pv = pd.read_csv(location_PVprofiles[location], sep=';', decimal=',')
    pv_array = pd.to_numeric(df_pv["PPV"], errors='coerce').to_numpy()

    df_temp = pd.read_csv(location_temp_profiles[location], sep=';', decimal=',')
    temp_series = pd.Series(pd.to_numeric(df_temp["T2m"], errors='coerce').values, index=df_temp['time'])

    df_irr = pd.read_csv(location_solarirradiation_profiles[location], sep=';', decimal=',')
    irr_array = pd.to_numeric(df_irr["solar_irradiance_total"], errors='coerce').to_numpy()

    df_solargains = pd.read_csv(location_solargains_profiles[location], sep=';', decimal=',')
    solargains_array = pd.to_numeric(df_solargains["solar_gains_(W/m2)"], errors='coerce').to_numpy()

    # V2H-Profile (robust, ggf. Dummy)
    n_steps = len(load_array)
    min_SOC, availability_profile, driving_profile = load_v2h_profiles(location_V2H_profiles, n_steps)

    result = {
        'load': np.asarray(load_array),  # Aggregated load (sum across all members)
        'load_member_2d': load_member_2d,  # Member-level load [T, N_EC]
        'pv_generation': np.asarray(pv_array),
        'T_outdoor': np.asarray(temp_series),
        'irradiance': np.asarray(irr_array),
        'solargains': np.asarray(solargains_array),
        'min_SOC': np.asarray(min_SOC),
        'availability_profile': np.asarray(availability_profile),
        'driving_profile': np.asarray(driving_profile),
        'usage_profile': pd.read_excel(location_usage_profiles, sheet_name=0),
    }
    
    return result