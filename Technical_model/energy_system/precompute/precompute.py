# Technical_model/energy_system/precompute/precompute.py

from typing import Dict, Any, Optional, List
import numpy as np
import pandas as pd

# Nur über Heatpump-API importieren – kein direkter heating_and_cooling-Import
from Technical_model.technologies.heatpump_model import (
    simulate_heatpump_heating_system,
    simulate_heatpump_cooling_system,
)
from Technical_model.technologies.household_hotwater import (
    compute_household_hotwater_load_kwh,
)
from Data.technology_data.building import get_building_params
from Technical_model.technologies.buildings.runtime_building_params import get_runtime_building_params
from Technical_model.technologies.buildings.runtime_space_heat import (
    build_reference_space_heat_profile_kwh,
    resolve_runtime_solar_gains_w_per_m2,
)


def _as_np(a):
    return np.asarray(a, dtype=float)


def _is_cohort_member(member: Any) -> bool:
    return bool(
        getattr(member, "thermal_archetype_key", None)
        or getattr(member, "represented_gfa_m2", None) is not None
        or getattr(member, "annual_heat_target_kwh", None) is not None
        or getattr(member, "annual_electricity_target_kwh", None) is not None
    )


def prepare_profiles(params: Dict[str, Any],
                     profiles: Dict[str, Any],
                     do_hp_electricity: bool = True,
                     do_coeffs: bool = False,
                     members: Optional[Any] = None) -> Dict[str, Any]:
    """
    Erzeugt das 1-Jahres-Precompute-Paket für das aktive Systemmodell.
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
    required = ["load", "pv_generation", "T_outdoor", "usage_profile", "solargains"]
    missing = [k for k in required if k not in profiles]
    assert not missing, f"Profiles fehlen Keys: {missing}"

    out["load"] = _as_np(profiles["load"])
    out["pv_generation"] = _as_np(profiles["pv_generation"])
    out["T_outdoor"] = _as_np(profiles["T_outdoor"])
    out["solargains"] = _as_np(profiles["solargains"])
    out["usage_profile"] = profiles["usage_profile"]  # als DF belassen
    thermal_profiles = dict(profiles)
    if "settings_obj" in params:
        out["settings_obj"] = params["settings_obj"]
        thermal_profiles["settings_obj"] = params["settings_obj"]
    if "irradiance" in profiles:
        out["irradiance"] = _as_np(profiles["irradiance"])

    if "wind_speed_ms" in profiles:
        out["wind_speed_ms"] = _as_np(profiles["wind_speed_ms"])
    if "wind_pressure_hpa" in profiles:
        out["wind_pressure_hpa"] = _as_np(profiles["wind_pressure_hpa"])

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
        n_steps = len(usage_df)
        N_EC = load_member_2d.shape[1]
        settings_obj = params.get("settings_obj", None)
        active_members = [m for m in members.members if int(m.count) > 0]
        cohort_mode = any(_is_cohort_member(m) for m in active_members)

        if cohort_mode:
            out["hp_elec_heat_member_2d"] = np.zeros((n_steps, N_EC), dtype=float)
            out["hp_elec_cool_member_2d"] = np.zeros((n_steps, N_EC), dtype=float)
            out["hotwater_member_2d"] = np.zeros((n_steps, N_EC), dtype=float)
            out["space_heat_member_2d"] = np.zeros((n_steps, N_EC), dtype=float)
            out["space_heat_solar_member_2d"] = np.zeros((n_steps, N_EC), dtype=float)
            out["load_member_2d"] = np.zeros((n_steps, N_EC), dtype=float)
            raw_space_heat_member_2d = np.zeros((n_steps, N_EC), dtype=float)
            space_heat_targets_by_sector: Dict[str, float] = {}
            member_sector_by_index: Dict[int, str] = {}

            member_idx = 0
            for member in active_members:
                count = int(member.count)
                if count != 1:
                    raise ValueError(
                        "[precompute] Cohort-mode members must use count=1. "
                        f"Member '{member.member_id}' has count={count}."
                    )
                if member_idx >= N_EC:
                    raise ValueError("[precompute] Cohort/member dimensionality mismatch.")

                building_params = get_runtime_building_params(member, settings_obj=settings_obj)
                params_with_building = dict(params)
                params_with_building["building"] = building_params

                raw_load = np.asarray(load_member_2d[:, member_idx], dtype=float)
                # This is the exogenous profile anchor for the cohort load shape.
                # Official sector electricity totals remain in building_stock and
                # are not silently mixed into the runtime scaling here.
                annual_electricity_target = getattr(member, "annual_electricity_target_kwh", None)
                if annual_electricity_target is not None:
                    raw_load_sum = float(np.sum(raw_load))
                    if raw_load_sum <= 0.0:
                        raise ValueError(
                            f"[precompute] Member '{member.member_id}' has non-positive raw electricity profile sum."
                        )
                    elec_scale = float(annual_electricity_target) / raw_load_sum
                    raw_load = raw_load * elec_scale
                out["load_member_2d"][:, member_idx] = raw_load

                if bool(getattr(member, "include_hotwater", True)):
                    hotwater_raw = compute_household_hotwater_load_kwh(
                        usage_profile=usage_df,
                        a_floor_m2=float(building_params["A_floor"]),
                    )
                else:
                    hotwater_raw = np.zeros(n_steps, dtype=float)

                # Build the active reference space-heat demand directly from the
                # teacher-derived runtime parameters. This avoids routing the
                # cohort path back through the deprecated legacy helper.
                member_solar_gains_w_m2 = _as_np(
                    resolve_runtime_solar_gains_w_per_m2(
                        legacy_solar_gains_w_m2=thermal_profiles["solargains"],
                        irradiance_w_m2=thermal_profiles.get("irradiance"),
                        building_params=building_params,
                        thermal_cfg=settings_obj.thermal,
                    )
                )
                space_heat_raw = _as_np(
                    build_reference_space_heat_profile_kwh(
                        timestamps=out["timestamps"],
                        t_outdoor_k=thermal_profiles["T_outdoor"],
                        solar_gains_w_m2=member_solar_gains_w_m2,
                        usage_df=usage_df,
                        building_params=building_params,
                        heating_control=settings_obj.heating_control,
                    )
                )

                annual_space_heat_target = getattr(member, "annual_space_heat_target_kwh", None)
                annual_hotwater_target = getattr(member, "annual_hotwater_target_kwh", None)
                sector = str(getattr(member, "sector", "")).strip()
                if not sector:
                    raise ValueError(
                        f"[precompute] Cohort-mode member '{member.member_id}' is missing the required sector label."
                    )
                member_sector_by_index[member_idx] = sector
                if annual_space_heat_target is not None:
                    space_heat_targets_by_sector[sector] = (
                        float(space_heat_targets_by_sector.get(sector, 0.0)) + float(annual_space_heat_target)
                    )

                hotwater_scale = 1.0
                if annual_hotwater_target is not None:
                    raw_hotwater = float(np.sum(hotwater_raw))
                    if float(annual_hotwater_target) <= 0.0:
                        hotwater_scale = 0.0
                    else:
                        if raw_hotwater <= 0.0:
                            raise ValueError(
                                f"[precompute] Member '{member.member_id}' has non-positive raw hotwater demand sum."
                            )
                        hotwater_scale = float(annual_hotwater_target) / raw_hotwater

                raw_space_heat_member_2d[:, member_idx] = space_heat_raw
                out["space_heat_solar_member_2d"][:, member_idx] = member_solar_gains_w_m2
                out["hotwater_member_2d"][:, member_idx] = hotwater_raw * hotwater_scale

                if do_hp_electricity:
                    hp_profiles = dict(thermal_profiles)
                    hp_profiles["space_heat_demand_override_kwh"] = space_heat_raw
                    hpH = simulate_heatpump_heating_system(params=params_with_building, profiles=hp_profiles)
                    hpC = simulate_heatpump_cooling_system(params=params_with_building, profiles=thermal_profiles)
                    out["hp_elec_heat_member_2d"][:, member_idx] = _as_np(hpH["electric_consumption_series"])
                    out["hp_elec_cool_member_2d"][:, member_idx] = _as_np(
                        hpC["electric_consumption_series"]
                    )
                member_idx += 1

            if member_idx != N_EC:
                raise ValueError("[precompute] Cohort/member dimensionality mismatch after processing all members.")

            # Keep the sector totals from the explicit building-stock SSOT, but
            # let the modeled raw cohort profiles determine how that sector
            # total is distributed across construction periods. This avoids
            # silently forcing identical kWh/m²a onto all residential cohorts
            # when the Vienna building stock only provides sector totals plus
            # construction-period floor-area shares.
            distribution_mode = str(
                getattr(
                    getattr(settings_obj, "building_stock", None),
                    "space_heat_distribution_mode",
                    "per_cohort_targets",
                )
            ).strip()
            if distribution_mode == "sector_total_from_modeled_raw_profiles":
                for sector, sector_target_kwh in space_heat_targets_by_sector.items():
                    member_indices = [idx for idx, member_sector in member_sector_by_index.items() if member_sector == sector]
                    if not member_indices:
                        raise ValueError(
                            f"[precompute] No cohort members found for sector='{sector}' during sector-total normalization."
                        )
                    raw_sector_total = float(np.sum(raw_space_heat_member_2d[:, member_indices]))
                    if raw_sector_total <= 0.0:
                        raise ValueError(
                            f"[precompute] Raw modeled space-heat total for sector='{sector}' must be positive."
                        )
                    sector_scale = float(sector_target_kwh) / raw_sector_total
                    out["space_heat_member_2d"][:, member_indices] = (
                        raw_space_heat_member_2d[:, member_indices] * sector_scale
                    )
                    out["hp_elec_heat_member_2d"][:, member_indices] = (
                        out["hp_elec_heat_member_2d"][:, member_indices] * sector_scale
                    )
            elif distribution_mode == "per_cohort_targets":
                for member_col in range(N_EC):
                    member = active_members[member_col]
                    annual_space_heat_target = getattr(member, "annual_space_heat_target_kwh", None)
                    space_heat_scale = 1.0
                    if annual_space_heat_target is not None:
                        raw_space_heat = float(np.sum(raw_space_heat_member_2d[:, member_col]))
                        if raw_space_heat <= 0.0:
                            raise ValueError(
                                f"[precompute] Member '{member.member_id}' has non-positive raw space-heat demand sum."
                            )
                        space_heat_scale = float(annual_space_heat_target) / raw_space_heat
                    out["space_heat_member_2d"][:, member_col] = raw_space_heat_member_2d[:, member_col] * space_heat_scale
                    out["hp_elec_heat_member_2d"][:, member_col] = (
                        out["hp_elec_heat_member_2d"][:, member_col] * space_heat_scale
                    )
            else:
                raise ValueError(
                    "[precompute] Unsupported building_stock.space_heat_distribution_mode="
                    f"'{distribution_mode}'."
                )

            out["hp_elec_heat"] = out["hp_elec_heat_member_2d"].sum(axis=1)
            out["hp_elec_cool"] = out["hp_elec_cool_member_2d"].sum(axis=1)
            out["hotwater_HH_kWh"] = out["hotwater_member_2d"].sum(axis=1)
            out["space_heat_HH_kWh"] = out["space_heat_member_2d"].sum(axis=1)
            out["load"] = out["load_member_2d"].sum(axis=1)
            return out
        
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
        
        # Compute thermal and electric demand per building_key (once per unique key).
        hp_heat_by_key: Dict[str, np.ndarray] = {}
        hp_cool_by_key: Dict[str, np.ndarray] = {}
        hotwater_by_key: Dict[str, np.ndarray] = {}
        space_heat_by_key: Dict[str, np.ndarray] = {}
        
        for building_key, _indices in building_key_to_indices.items():
            # Get building params for this key
            building_params = get_building_params(building_key)
            A_floor = float(building_params["A_floor"])
            
            # DHW remains a direct household electrical load derived from the common usage profile.
            hotwater_by_key[building_key] = compute_household_hotwater_load_kwh(
                usage_profile=usage_df,
                a_floor_m2=A_floor,
            )

            # DH demand needs the underlying thermal space-heating demand, not only HP electricity.
            # Keep it explicit in the precompute package so downstream layers do not need to
            # reconstruct it from a specific supply technology.
            # Non-cohort legacy building-key members still use the existing helper
            # until they are migrated onto the same teacher-derived runtime path.
            from Technical_model.consumption.heating_anc_cooling_consumption.heating_and_cooling import (
                get_heating_load_on_days,
            )

            space_heat_by_key[building_key] = _as_np(
                get_heating_load_on_days(profiles=thermal_profiles, building_params=building_params)
            )
            
            # HP electricity (compute once per building_key)
            if do_hp_electricity:
                # Temporarily override params["building"] for HP calculation
                params_with_building = dict(params)
                params_with_building["building"] = building_params

                hp_profiles = dict(thermal_profiles)
                hp_profiles["space_heat_demand_override_kwh"] = space_heat_by_key[building_key]
                hpH = simulate_heatpump_heating_system(params=params_with_building, profiles=hp_profiles)
                hpC = simulate_heatpump_cooling_system(params=params_with_building, profiles=thermal_profiles)
                hp_heat_by_key[building_key] = _as_np(hpH["electric_consumption_series"])
                hp_cool_by_key[building_key] = _as_np(hpC["electric_consumption_series"])
            else:
                hp_heat_by_key[building_key] = np.zeros(n_steps, dtype=float)
                hp_cool_by_key[building_key] = np.zeros(n_steps, dtype=float)
        
        # Expand to member-level arrays [T, N_EC]
        out["hp_elec_heat_member_2d"] = np.zeros((n_steps, N_EC), dtype=float)
        out["hp_elec_cool_member_2d"] = np.zeros((n_steps, N_EC), dtype=float)
        out["hotwater_member_2d"] = np.zeros((n_steps, N_EC), dtype=float)
        out["space_heat_member_2d"] = np.zeros((n_steps, N_EC), dtype=float)
        
        for building_key, indices in building_key_to_indices.items():
            for idx in indices:
                out["hp_elec_heat_member_2d"][:, idx] = hp_heat_by_key[building_key]
                out["hp_elec_cool_member_2d"][:, idx] = hp_cool_by_key[building_key]
                out["hotwater_member_2d"][:, idx] = hotwater_by_key[building_key]
                out["space_heat_member_2d"][:, idx] = space_heat_by_key[building_key]
        
        # Legacy aggregated arrays (sum across members)
        out["hp_elec_heat"] = out["hp_elec_heat_member_2d"].sum(axis=1)
        out["hp_elec_cool"] = out["hp_elec_cool_member_2d"].sum(axis=1)
        out["hotwater_HH_kWh"] = out["hotwater_member_2d"].sum(axis=1)
        out["space_heat_HH_kWh"] = out["space_heat_member_2d"].sum(axis=1)
        
        # Use load_member_2d if available, otherwise aggregate
        if load_member_2d is not None:
            out["load_member_2d"] = load_member_2d
            out["load"] = load_member_2d.sum(axis=1)  # Legacy aggregated
    else:
        # Legacy mode: single building type
        usage_df = profiles["usage_profile"]
        A_floor = float(params["building"]["A_floor"])
        out["hotwater_HH_kWh"] = compute_household_hotwater_load_kwh(
            usage_profile=usage_df,
            a_floor_m2=A_floor,
        )

        # 4) Wärmepumpen-Strom vorrechnen (ein Jahr, aktuell pro Haushalt/Gebäude)
        if do_hp_electricity:
            hpH = simulate_heatpump_heating_system(params=params, profiles=thermal_profiles)
            hpC = simulate_heatpump_cooling_system(params=params, profiles=thermal_profiles)
            out["hp_elec_heat"] = _as_np(hpH["electric_consumption_series"])
            out["hp_elec_cool"] = _as_np(hpC["electric_consumption_series"])
        else:
            nH = len(out["load"])
            out["hp_elec_heat"] = np.zeros(nH, dtype=float)
            out["hp_elec_cool"] = np.zeros(nH, dtype=float)

        # Legacy mode: no longer supported - member-level data required
        raise ValueError(
            "[precompute] Legacy mode (no member-level data) is no longer supported. "
            "Member-level profiles are required. Ensure settings.engine.members "
            "is configured and load_profiles() is called with member_ids."
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
