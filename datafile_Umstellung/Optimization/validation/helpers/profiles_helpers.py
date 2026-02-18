# Optimization/validation/helpers/profiles_helpers.py
from __future__ import annotations

from typing import Dict, Any

from V2H_energy_community_surrogat_datafilenew.datafile_Umstellung.Optimization.framework.Settings.settings import Settings
from V2H_energy_community_surrogat_datafilenew.datafile_Umstellung.Data.data import get_parameters, load_profiles
from V2H_energy_community_surrogat_datafilenew.datafile_Umstellung.Technical_model.energy_system.precompute.precompute import prepare_profiles


def build_base_params(S: Settings) -> Dict[str, Any]:
    """
    Basis-Params analog FastEngine:
      - Standort-Parameter
      - EC-Shares
      - N_HH, N_EV_total, N_EV_bidirectional
    """
    eng = S.engine

    base_params: Dict[str, Any] = get_parameters(eng.location)
    base_params["location"] = eng.location

    # EC-Shares spiegeln
    base_params.setdefault("EC", {})
    base_params["EC"]["share"] = float(eng.ec_share_import)
    base_params["EC"]["export_share"] = float(eng.ec_share_export)

    # Community-Zähler spiegeln
    base_params["N_HH"] = int(eng.N_HH)
    base_params["N_EC"] = int(eng.N_EC)  # Required for member-level processing

    # Legacy-Keys wie im technischen Modell
    base_params["N_EV"] = int(eng.N_EV_total)
    base_params["N_EV_bidirectional"] = int(eng.N_EV_bidirectional)

    # Strukturierter EV-Block
    base_params.setdefault("EV", {})
    base_params["EV"]["N_EV_total"] = int(eng.N_EV_total)
    base_params["EV"]["N_EV_bidirectional"] = int(eng.N_EV_bidirectional)


    return base_params


def get_profiles_for_validation(S: Settings) -> Dict[str, Any]:
    """
    Profiles für die Validation – 1:1 an FastEngine angelehnt.
    """
    eng = S.engine
    base_params = build_base_params(S)

    profiles_raw = load_profiles(eng.location)
    profiles = prepare_profiles(
        base_params,
        profiles_raw,
        do_hp_electricity=True,
        do_coeffs=False,
    )
    return profiles
