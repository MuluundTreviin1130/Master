# Optimization/Vectorized_model/precompute.py

from typing import Dict, Any, Optional, List
import numpy as np
import pandas as pd

# Nur über Heatpump-API importieren – kein direkter heating_and_cooling-Import
from Technical_model.technologies.heatpump_model import (
    simulate_heatpump_heating_system,
    simulate_heatpump_cooling_system,
)
from Data.technology_data.building import get_building_params


def _as_np(a):
    return np.asarray(a, dtype=float)


def prepare_profiles(params: Dict[str, Any],
                     profiles: Dict[str, Any],
                     do_hp_electricity: bool = True,
                     do_coeffs: bool = False,
                     members: Optional[Any] = None) -> Dict[str, Any]:
    """
    Erzeugt das 1-Jahres-Precompute-Paket für das FAST-Modell.
    Erwartete Eingaben in `profiles` (aus Data.load_profiles):
    - 'load' (kWh/h), 'pv_generation' (kWh/h bei Referenz-kWp), 'T_outdoor',
      'usage_profile' (DataFrame), optional: 'timestamps',
      optional (für V2H): 'availability_profile', 'driving_profile', 'min_SOC', 'ev_profiles'.

    Ausgaben (immer als NumPy-Vektoren, außer usage_profile als DF):
    - 'hp_elec_heat', 'hp_elec_cool', 'hotwater_HH_kWh',
      'pv_generation', 'load', 'T_outdoor', 'usage_profile' (+ EV-Profile falls vorhanden).
    """
    out: Dict[str, Any] = {}

    # 1) Pflicht-Pass-Through (pro Haushalt!)
    required = ["load", "pv_generation", "T_outdoor", "usage_profile"]
    missing = [k for k in required if k not in profiles]
    assert not missing, f"Profiles fehlen Keys: {missing}"

    out["load"] = _as_np(profiles["load"])
    out["pv_generation"] = _as_np(profiles["pv_generation"])
    out["T_outdoor"] = _as_np(profiles["T_outdoor"])
    out["usage_profile"] = profiles["usage_profile"]  # als DF belassen

    # Timestamps – falls vorhanden durchreichen, sonst 1 Jahr generieren
    if "timestamps" in profiles:
        out["timestamps"] = profiles["timestamps"]
    else:
        nH = len(out["load"])
        out["timestamps"] = pd.date_range(start="2023-01-01", periods=nH, freq="h")

    # 2) Optional-Pass-Through für V2H
    for k in ["availability_profile", "driving_profile", "min_SOC"]:
        if k in profiles:
            out[k] = _as_np(profiles[k])

    # Check if we have member-level data
    load_member_2d = profiles.get("load_member_2d")
    has_members = load_member_2d is not None and members is not None and hasattr(members, "members")
    
    if has_members and len(members.members) > 0:
        # Member-level mode: compute per building_key, then expand
        usage_df = profiles["usage_profile"]
        assert "Warmwasserbedarf_W_m2" in usage_df.columns, "usage_profile fehlt Spalte 'Warmwasserbedarf_W_m2'"
        hotwater_W_m2 = usage_df["Warmwasserbedarf_W_m2"].to_numpy(dtype=float)
        
        n_steps = len(hotwater_W_m2)
        N_EC = load_member_2d.shape[1]
        
        # Get unique building_keys and their member indices
        building_key_to_indices: Dict[str, List[int]] = {}
        member_idx = 0
        for m in members.members:
            key = m.building_key
            if key not in building_key_to_indices:
                building_key_to_indices[key] = []
            for _ in range(m.count):
                building_key_to_indices[key].append(member_idx)
                member_idx += 1
        
        # Compute HP and hotwater per building_key (once per unique key)
        hp_heat_by_key: Dict[str, np.ndarray] = {}
        hp_cool_by_key: Dict[str, np.ndarray] = {}
        hotwater_by_key: Dict[str, np.ndarray] = {}
        
        for building_key, _indices in building_key_to_indices.items():
            # Get building params for this key
            building_params = get_building_params(building_key)
            A_floor = float(building_params["A_floor"])
            
            # Hotwater (same for all members of this type)
            hotwater_by_key[building_key] = (hotwater_W_m2 * A_floor) / 1000.0  # W → kWh
            
            # HP electricity (compute once per building_key)
            if do_hp_electricity:
                # Temporarily override params["building"] for HP calculation
                params_with_building = dict(params)
                params_with_building["building"] = building_params
                
                hpH = simulate_heatpump_heating_system(params=params_with_building, profiles=profiles)
                hpC = simulate_heatpump_cooling_system(params=params_with_building, profiles=profiles)
                hp_heat_by_key[building_key] = _as_np(hpH["electric_consumption_series"])
                hp_cool_by_key[building_key] = _as_np(hpC["electric_consumption_series"])
            else:
                hp_heat_by_key[building_key] = np.zeros(n_steps, dtype=float)
                hp_cool_by_key[building_key] = np.zeros(n_steps, dtype=float)
        
        # Expand to member-level arrays [T, N_EC]
        out["hp_elec_heat_member_2d"] = np.zeros((n_steps, N_EC), dtype=float)
        out["hp_elec_cool_member_2d"] = np.zeros((n_steps, N_EC), dtype=float)
        out["hotwater_member_2d"] = np.zeros((n_steps, N_EC), dtype=float)
        
        for building_key, indices in building_key_to_indices.items():
            for idx in indices:
                out["hp_elec_heat_member_2d"][:, idx] = hp_heat_by_key[building_key]
                out["hp_elec_cool_member_2d"][:, idx] = hp_cool_by_key[building_key]
                out["hotwater_member_2d"][:, idx] = hotwater_by_key[building_key]
        
        # Legacy aggregated arrays (sum across members)
        out["hp_elec_heat"] = out["hp_elec_heat_member_2d"].sum(axis=1)
        out["hp_elec_cool"] = out["hp_elec_cool_member_2d"].sum(axis=1)
        out["hotwater_HH_kWh"] = out["hotwater_member_2d"].sum(axis=1)
        
        # Use load_member_2d if available, otherwise aggregate
        if load_member_2d is not None:
            out["load_member_2d"] = load_member_2d
            out["load"] = load_member_2d.sum(axis=1)  # Legacy aggregated
    else:
        # Legacy mode: single building type
        usage_df = profiles["usage_profile"]
        assert "Warmwasserbedarf_W_m2" in usage_df.columns, "usage_profile fehlt Spalte 'Warmwasserbedarf_W_m2'"
        hotwater_W_m2 = usage_df["Warmwasserbedarf_W_m2"].to_numpy(dtype=float)
        A_floor = float(params["building"]["A_floor"])
        out["hotwater_HH_kWh"] = (hotwater_W_m2 * A_floor) / 1000.0  # W → kWh

        # 4) Wärmepumpen-Strom vorrechnen (ein Jahr, aktuell pro Haushalt/Gebäude)
        if do_hp_electricity:
            hpH = simulate_heatpump_heating_system(params=params, profiles=profiles)
            hpC = simulate_heatpump_cooling_system(params=params, profiles=profiles)
            out["hp_elec_heat"] = _as_np(hpH["electric_consumption_series"])
            out["hp_elec_cool"] = _as_np(hpC["electric_consumption_series"])
        else:
            nH = len(out["load"])
            out["hp_elec_heat"] = np.zeros(nH, dtype=float)
            out["hp_elec_cool"] = np.zeros(nH, dtype=float)

        # Legacy mode: no longer supported - member-level data required
        raise ValueError(
            "[precompute] Legacy mode (no member-level data) is no longer supported. "
            "Member-level profiles are required. Ensure members.yaml exists and "
            "load_profiles() is called with member_ids."
        )

    # 6) EV-Profile absichern (für NoV2H auch Dummy erzeugen)
    nH = len(out["load"])
    N_EV = int(params.get("N_EV", 1))
    if "ev_profiles" in profiles:
        out["ev_profiles"] = _as_np(profiles["ev_profiles"])
    else:
        # Dummy-Profil: keine zusätzliche EV-Last
        out["ev_profiles"] = np.zeros((nH, N_EV))

    # 7) (Optional) Platzhalter für Koeffizienten
    if do_coeffs:
        out["coeffs"] = {"note": "hier könnten Regressions-Koeffizienten stehen"}

    return out
