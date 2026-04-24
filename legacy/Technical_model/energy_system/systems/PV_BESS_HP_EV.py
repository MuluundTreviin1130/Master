from __future__ import annotations

import numpy as np
import pandas as pd

from Technical_model.technologies.PV_model import simulate_pv_system
from Technical_model.technologies.battery_model import simulate_battery_flow
from Technical_model.energy_system.ec_clearing import (
    clear_ec,
    split_trade_by_source,
)


def simulate_energy_system(params: dict, profiles: dict, pv_size: float) -> dict:
    """
    PV + BESS + HP + EV (nur Laden, kein V2H).

    Designziele:
    - Alle Lasten innerhalb der EC (HH + HP + WW + EV) werden als total_load erfasst.
    - PV, BESS und Grid decken diese total_load.
    - AC-Energiebilanz stimmt per Konstruktion:
        pv_generation + bess_discharged + grid_import
        = total_load + bess_charged + grid_export
    - EV-Batterie wird nur geladen (keine Entladung ins Haus).
    """

    # --- Grundlast AC ---
    # Check if we have member-level data
    load_member_2d = profiles.get("load_member_2d")
    hp_heat_member_2d = profiles.get("hp_elec_heat_member_2d")
    hp_cool_member_2d = profiles.get("hp_elec_cool_member_2d")
    hotwater_member_2d = profiles.get("hotwater_member_2d")
    
    has_member_level = (
        load_member_2d is not None and 
        hp_heat_member_2d is not None and 
        hp_cool_member_2d is not None and 
        hotwater_member_2d is not None
    )
    
    if has_member_level:
        load_member_2d = np.asarray(load_member_2d, dtype=float)
        hp_heat_member_2d = np.asarray(hp_heat_member_2d, dtype=float)
        hp_cool_member_2d = np.asarray(hp_cool_member_2d, dtype=float)
        hotwater_member_2d = np.asarray(hotwater_member_2d, dtype=float)
        base_load_member_2d = load_member_2d + hp_heat_member_2d + hp_cool_member_2d + hotwater_member_2d
        base_load_ac = base_load_member_2d.sum(axis=1)
        N_EC = base_load_member_2d.shape[1]
        
        # Aggregate loads for result dict (sum over all members)
        load = load_member_2d.sum(axis=1)
        hp_heat = hp_heat_member_2d.sum(axis=1)
        hp_cool = hp_cool_member_2d.sum(axis=1)
        hotwater = hotwater_member_2d.sum(axis=1)
    else:
        # No member-level data: this is an error (no legacy fallback)
        raise ValueError(
            "[PV_BESS_HP_EV] Member-level profiles required but missing. "
            "Expected keys in profiles: 'load_member_2d', 'hp_elec_heat_member_2d', "
            "'hp_elec_cool_member_2d', 'hotwater_member_2d'. "
            "Ensure members.yaml exists and load_profiles() is called with member_ids."
        )

    T_outdoor = np.asarray(profiles["T_outdoor"], dtype=float)

    n_steps = len(base_load_ac)
    N_HH = int(params.get("N_HH", -1))
    if N_HH < 0:
        raise ValueError("[PV_BESS_HP_EV] N_HH must be set in params (no fallback). Check settings.engine.N_HH.")
    if N_HH > N_EC:
        raise ValueError(f"[PV_BESS_HP_EV] N_HH ({N_HH}) cannot exceed N_EC ({N_EC}). Check household_ids in members.yaml.")

    # --- EV-Parameter ---
    ev_params = dict(params.get("EV", {}))

    if "N_EV_total" in params:
        ev_params["N_EV_total"] = int(params["N_EV_total"])
    if "N_EV_total" not in ev_params:
        ev_params["N_EV_total"] = 0

    N_EV_total = int(ev_params.get("N_EV_total", 0))
    
    # EV assignment: deterministic per run (not per evaluate)
    rng_seed = int(params.get("rng_seed", 0))
    rng = np.random.default_rng(rng_seed)
    ev_to_member = rng.choice(N_EC, size=N_EV_total, replace=True) if N_EV_total > 0 else np.zeros(0, dtype=int)

    cap = float(ev_params.get("capacity_kWh", 0.0))
    eta_ch = float(ev_params.get("charging_efficiency", 1.0))
    self_dis_ev = float(ev_params.get("self_discharge_EV", 0.0))
    max_soc_frac = float(ev_params.get("max_soc", 1.0))
    init_soc_frac = float(ev_params.get("initial_soc", 0.5))
    max_chg_power = float(ev_params.get("max_charge_power", 0.0))

    availability_profile = np.asarray(
        profiles.get("availability_profile", np.ones(n_steps)),
        dtype=float,
    )
    driving_profile = np.asarray(
        profiles.get("driving_profile", np.zeros(n_steps)),
        dtype=float,
    )
    min_soc_data = np.asarray(
        profiles.get("min_SOC", np.zeros(n_steps)),
        dtype=float,
    )
    
    # rng already created above for EV assignment (deterministic per run)

    # --- PV (AC) ---
    pv_results = simulate_pv_system(
        pv_size=float(pv_size),
        load_demand=base_load_ac,
        pv_generation=np.asarray(profiles["pv_generation"], dtype=float),
        params=params,
    )
    pv_generation_ac = np.asarray(pv_results["pv_production"], dtype=float)

    # --- EV Zustände ---
    ev_soc_dc = np.zeros((n_steps, N_EV_total), dtype=float)
    if N_EV_total > 0:
        ev_soc_dc[0, :] = cap * init_soc_frac

    ev_charged_dc = np.zeros((n_steps, N_EV_total), dtype=float)
    ev_discharged_ac = np.zeros((n_steps, N_EV_total), dtype=float)  # bleibt 0 (kein V2H)
    trip_loss_dc = np.zeros((n_steps, N_EV_total), dtype=float)
    driving_energy_dc = np.zeros((n_steps, N_EV_total), dtype=float)
    ev_availability = np.zeros((n_steps, N_EV_total), dtype=bool)
    ev_is_active_series = np.zeros((n_steps, N_EV_total), dtype=bool)

    # --- EV-Ladequellen (nur Monitoring) ---
    ev_charge_from_grid_ac = np.zeros(n_steps, dtype=float)
    ev_charge_from_pv_ac = np.zeros(n_steps, dtype=float)

    # --- BESS-Requests ---
    battery_in_request_ac = np.zeros(n_steps, dtype=float)
    battery_out_request_ac = np.zeros(n_steps, dtype=float)

    # --- Netz (wird nach BESS-Sim final bestimmt) ---
    grid_import_ac = np.zeros(n_steps, dtype=float)
    grid_export_ac = np.zeros(n_steps, dtype=float)

    timestep_h = 1.0

    # Hilfsvektor EV-AC-Ladung pro Stunde
    ev_charge_ac_series = np.zeros(n_steps, dtype=float)
    ev_charge_ac_by_ev = np.zeros((n_steps, N_EV_total), dtype=float)

    # ---------------- EV & BESS-Requests ----------------
    for t in range(n_steps):
        if t > 0 and N_EV_total > 0:
            ev_soc_dc[t, :] = ev_soc_dc[t - 1, :]

        base_load_t = float(base_load_ac[t])
        pv_t = float(pv_generation_ac[t])

        ev_charge_ac_t = 0.0  # gesamte EV-Ladung AC in dieser Stunde

        # --- EV-Loop (nur Laden) ---
        if N_EV_total > 0:
            for i in range(N_EV_total):
                is_available = bool(rng.random() <= availability_profile[t])
                ev_availability[t, i] = is_available
                ev_is_active_series[t, i] = is_available

                drive_dc = driving_profile[t] * cap
                driving_energy_dc[t, i] = drive_dc

                if not is_available:
                    used_dc = min(ev_soc_dc[t, i], drive_dc)
                    ev_soc_dc[t, i] -= used_dc
                    trip_loss_dc[t, i] = used_dc
                    if self_dis_ev > 0.0:
                        ev_soc_dc[t, i] *= (1.0 - self_dis_ev)
                    continue

                # Fahrzeug steht in der EC
                min_soc_dc = cap * min_soc_data[t]
                max_soc_dc = cap * max_soc_frac

                # 1) Mindest-SOC sicherstellen (Ladung aus Grid, nicht flexibel)
                if ev_soc_dc[t, i] < min_soc_dc:
                    need_dc = min_soc_dc - ev_soc_dc[t, i]
                    need_ac = min(
                        need_dc / max(eta_ch, 1e-9),
                        max_chg_power * timestep_h,
                    )
                    ev_soc_dc[t, i] += need_ac * eta_ch
                    ev_charged_dc[t, i] += need_ac * eta_ch
                    ev_charge_from_grid_ac[t] += need_ac
                    ev_charge_ac_t += need_ac
                    ev_charge_ac_by_ev[t, i] += need_ac

                # 2) Optionaler PV-Überschuss in EV laden
                #    (PV-Überschuss relativ zu Basislast + EV-Ladung bisher)
                if pv_t > base_load_t + ev_charge_ac_t and ev_soc_dc[t, i] < max_soc_dc:
                    pv_surplus_now = pv_t - (base_load_t + ev_charge_ac_t)
                    room_dc = max(0.0, max_soc_dc - ev_soc_dc[t, i])
                    max_ac_by_soc = room_dc / max(eta_ch, 1e-9)
                    max_ac_by_power = max_chg_power * timestep_h
                    take_ac = min(pv_surplus_now, max_ac_by_soc, max_ac_by_power)
                    if take_ac > 1e-12:
                        ev_soc_dc[t, i] += take_ac * eta_ch
                        ev_charged_dc[t, i] += take_ac * eta_ch
                        ev_charge_from_pv_ac[t] += take_ac
                        ev_charge_ac_t += take_ac
                        ev_charge_ac_by_ev[t, i] += take_ac

                if self_dis_ev > 0.0:
                    ev_soc_dc[t, i] *= (1.0 - self_dis_ev)

        # EV-Ladung (AC) für diese Stunde speichern
        ev_charge_ac_series[t] = ev_charge_ac_t

        # Gesamtlast der EC in dieser Stunde
        total_load_t = base_load_t + ev_charge_ac_t

        # PV-Bilanz ohne BESS:
        if pv_t >= total_load_t:
            # Überschuss → BESS-Ladeanfrage
            battery_in_request_ac[t] = pv_t - total_load_t
            battery_out_request_ac[t] = 0.0
        else:
            # Defizit → BESS-Entladeanfrage
            battery_out_request_ac[t] = total_load_t - pv_t
            battery_in_request_ac[t] = 0.0

    # --- BESS-Simulation ---
    base_bess_power_kw = float(params["BESS"]["power_kW"])
    bess_power_kw_eff = base_bess_power_kw * N_EC

    battery_results = simulate_battery_flow(
        battery_in_request=battery_in_request_ac,
        battery_out_request=battery_out_request_ac,
        capacity_kWh=float(params["battery_capacity_kWh"]),
        power_kW=bess_power_kw_eff,
        efficiency=float(params["BESS"]["efficiency"]),
        self_discharge=float(params["BESS"]["self_discharge"]),
        max_cycles=float(params["BESS"]["max_cycles"]),
        battery_eol_capacity=float(params["BESS"]["eol_capacity"]),
        DoD=float(params["BESS"]["DoD"]),
    )

    bess_in_ac = np.asarray(battery_results["battery_in_series"], dtype=float)
    bess_out_ac = np.asarray(battery_results["battery_out_series"], dtype=float)

    # --- Finale AC-Bilanz: EC-Clearing + Grid-Import/-Export + total_load ---
    ev_charge_ac = ev_charge_ac_series
    gross_load_ac = base_load_ac + ev_charge_ac
    total_load_out_ac = np.zeros(n_steps, dtype=float)

    ev_charge_member = np.zeros((n_steps, N_EC), dtype=float)
    if N_EV_total > 0:
        for i in range(N_EV_total):
            ev_charge_member[:, ev_to_member[i]] += ev_charge_ac_by_ev[:, i]

    if has_member_level:
        base_load_member = base_load_member_2d.copy()
        pv_member = pv_generation_ac[:, None] / float(N_EC)
        bess_out_member = bess_out_ac[:, None] / float(N_EC)
        bess_in_member = bess_in_ac[:, None] / float(N_EC)
    else:
        base_load_member = base_load_ac[:, None] / float(N_EC)
        pv_member = pv_generation_ac[:, None] / float(N_EC)
        bess_out_member = bess_out_ac[:, None] / float(N_EC)
        bess_in_member = bess_in_ac[:, None] / float(N_EC)

    gross_load_member = base_load_member + ev_charge_member
    demand_member = gross_load_member + bess_in_member
    supply_member = pv_member + bess_out_member
    net_member = supply_member - demand_member

    grid_import_ac, grid_export_ac, _ec_sell_member, _ec_buy_member, T_ec = clear_ec(net_member)

    net_pos = np.clip(net_member, 0.0, None)
    denom = pv_member + bess_out_member + 1e-9
    pv_surplus_member = net_pos * (pv_member / denom)
    ev_surplus_member = np.zeros_like(pv_surplus_member)  # No V2H in this system

    ec_import_from_pv_ac, ec_import_from_ev_ac, ec_export_from_pv_ac = split_trade_by_source(
        T_ec, pv_surplus_member, ev_surplus_member
    )

    for t in range(n_steps):
        total_load_out_ac[t] = gross_load_ac[t]

    if not hasattr(simulate_energy_system, "_ec_printed"):
        simulate_energy_system._ec_printed = True
        surplus_member = np.clip(net_member, 0.0, None)
        deficit_member = np.clip(-net_member, 0.0, None)
        S_t = np.sum(surplus_member, axis=1)
        D_t = np.sum(deficit_member, axis=1)
        T_t = np.minimum(S_t, D_t)
        print(
            "[EC CLEARING] REMOVE AFTER CHECK "
            f"S_total={float(np.sum(S_t)):.6g} "
            f"D_total={float(np.sum(D_t)):.6g} "
            f"T_total={float(np.sum(T_t)):.6g} "
            f"trade_hours={int(np.sum(T_t > 0.0))} "
            f"grid_import_total={float(np.sum(grid_import_ac)):.6g} "
            f"grid_export_total={float(np.sum(grid_export_ac)):.6g}"
        )

    bess_out_to_ev_ac = np.zeros_like(bess_out_ac)
    bess_out_to_load_ac = bess_out_ac.copy()

    result = {
        # WP/WW/PV
        "heatpump_results_heating": hp_heat,
        "heatpump_results_cooling": hp_cool,
        "thermal_output_heating": np.zeros(n_steps, dtype=float),
        "thermal_output_cooling": np.zeros(n_steps, dtype=float),
        "pv_results": pv_results,
        # EV
        "ev_charged": ev_charged_dc,
        "ev_discharged": ev_discharged_ac,
        "ev_soc": ev_soc_dc,
        "trip_loss": trip_loss_dc,
        "driving_energy": driving_energy_dc,
        "ev_availability": ev_availability,
        "ev_active": ev_is_active_series,
        # EV-Quellen (informativ)
        "ev_charge_ac": ev_charge_ac,
        "ev_charge_from_pv_ac": ev_charge_from_pv_ac,
        "ev_charge_from_bess_ac": np.zeros(n_steps, dtype=float),
        "ev_charge_from_ec_ac": np.zeros(n_steps, dtype=float),
        "ev_charge_from_grid_ac": ev_charge_from_grid_ac,
        # BESS
        "bess_charged": bess_in_ac,
        "bess_discharged": bess_out_ac,
        "bess_soc": np.asarray(battery_results["soc_history"], dtype=float),
        "BESS_replacements": battery_results.get("BESS_replacements", 0),
        "bess_to_ev_ac": bess_out_to_ev_ac,
        "bess_to_load_ac": bess_out_to_load_ac,
        # Netz / EC (EC-Clearing aktiv)
        "grid_import": grid_import_ac,
        "grid_export": grid_export_ac,
        "ec_import_from_pv": ec_import_from_pv_ac,
        "ec_import_from_ev": ec_import_from_ev_ac,
        "ec_export_from_pv": ec_export_from_pv_ac,
        # Lasten/Gesamtflüsse
        "total_load": total_load_out_ac,
        "pv_generation": pv_generation_ac,
        "hotwater_load": hotwater,
        "base_load": base_load_ac,
        "household_load": load,
        # Zeitachse
        "timestamps": profiles.get(
            "timestamps",
            pd.date_range(start="2023-01-01", periods=n_steps, freq="h"),
        ),
    }

    return result
