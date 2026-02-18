# Technical_model/energy_system/systems/PV_BESS_HP_V2H.py
"""
Vereinfachtes PV + BESS + HP + (V2H)-EV-System.

- Alle Lasten innerhalb der Energiegemeinschaft (Haushalt, WW, HP, EV) werden
  als gemeinsame "total_load" behandelt.
- PV, BESS und bidirektionale EVs decken diese Last zuerst.
- Restliche Unterdeckung → Grid-Import, Überschüsse → Grid-Export.
- EC-Flüsse werden über internes Clearing bestimmt (Residual geht ans Grid).
"""

from __future__ import annotations

from typing import Dict, Any

import numpy as np
import pandas as pd

from Technical_model.technologies.PV_model import simulate_pv_system
from Technical_model.technologies.battery_model import simulate_battery_flow
from Technical_model.technologies.V2H_model import simulate_v2h_battery
from Technical_model.energy_system.ec_clearing import (
    clear_ec,
    split_trade_by_source,
)


def simulate_energy_system_with_v2h(
    params: Dict[str, Any],
    profiles: Dict[str, Any],
    pv_size: float,
) -> Dict[str, Any]:
    # --- Grundlasten (Haushalt + HP + WW) ---
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
        # Member-level mode: use 2D arrays (required if load_member_2d is present)
        load_member_2d = np.asarray(load_member_2d, dtype=float)
        hp_heat_member_2d = np.asarray(hp_heat_member_2d, dtype=float)
        hp_cool_member_2d = np.asarray(hp_cool_member_2d, dtype=float)
        hotwater_member_2d = np.asarray(hotwater_member_2d, dtype=float)
        base_load_member_2d = load_member_2d + hp_heat_member_2d + hp_cool_member_2d + hotwater_member_2d
        base_load_ac = base_load_member_2d.sum(axis=1)  # Aggregate for compatibility
        N_EC = base_load_member_2d.shape[1]
        
        # Aggregate loads for result dict (sum over all members)
        load = load_member_2d.sum(axis=1)
        hp_heat = hp_heat_member_2d.sum(axis=1)
        hp_cool = hp_cool_member_2d.sum(axis=1)
        hotwater = hotwater_member_2d.sum(axis=1)
    else:
        # No member-level data: this is an error (no legacy fallback)
        raise ValueError(
            "[PV_BESS_HP_V2H] Member-level profiles required but missing. "
            "Expected keys in profiles: 'load_member_2d', 'hp_elec_heat_member_2d', "
            "'hp_elec_cool_member_2d', 'hotwater_member_2d'. "
            "Ensure members.yaml exists and load_profiles() is called with member_ids."
        )

    T_outdoor = np.asarray(profiles["T_outdoor"], dtype=float)
    availability_profile = np.asarray(profiles["availability_profile"], dtype=float)
    driving_profile = np.asarray(profiles["driving_profile"], dtype=float)
    min_soc_data = np.asarray(profiles["min_SOC"], dtype=float)

    n_steps = len(base_load_ac)
    N_HH = int(params.get("N_HH", -1))
    if N_HH < 0:
        raise ValueError("[PV_BESS_HP_V2H] N_HH must be set in params (no fallback). Check settings.engine.N_HH.")
    if N_HH > N_EC:
        raise ValueError(f"[PV_BESS_HP_V2H] N_HH ({N_HH}) cannot exceed N_EC ({N_EC}). Check household_ids in members.yaml.")

    # --- EV-Parameter ---
    ev_params = dict(params.get("EV", {}))  # lokale Kopie

    # Szenario-Parameter (Top-Level) in den EV-Block spiegeln
    if "N_EV" in params:
        ev_params["N_EV_total"] = int(params["N_EV"])
    if "N_EV_total" in params:
        ev_params["N_EV_total"] = int(params["N_EV_total"])
    if "N_EV_total" not in ev_params:
        ev_params["N_EV_total"] = 0

    if "N_EV_bidirectional" in params:
        ev_params["N_EV_bidirectional"] = int(params["N_EV_bidirectional"])
    if "N_EV_bidirectional" not in ev_params:
        # Default: alle EVs sind bidirektional
        ev_params["N_EV_bidirectional"] = int(ev_params.get("N_EV_total", 0))

    N_EV_total = int(ev_params.get("N_EV_total", 0))
    N_EV_bidir = int(ev_params.get("N_EV_bidirectional", 0))
    # Clamp: bidirektionale EVs können nicht mehr sein als Gesamt-EVs
    if N_EV_bidir > N_EV_total:
        N_EV_bidir = N_EV_total
    
    # EV assignment: deterministic per run (not per evaluate)
    rng_seed = int(params.get("rng_seed", 0))
    rng = np.random.default_rng(rng_seed)
    ev_to_member = rng.choice(N_EC, size=N_EV_total, replace=True) if N_EV_total > 0 else np.zeros(0, dtype=int)

    cap = float(ev_params.get("capacity_kWh", 0.0))
    eta_ch = float(ev_params.get("charging_efficiency", 1.0))
    eta_dis = float(ev_params.get("discharging_efficiency", 1.0))
    self_dis_ev = float(ev_params.get("self_discharge_EV", 0.0))
    max_soc_frac = float(ev_params.get("max_soc", 1.0))
    init_soc_frac = float(ev_params.get("initial_soc", 0.5))
    max_chg_power = float(ev_params.get("max_charge_power", 0.0))
    
    # rng already created above for EV assignment (deterministic per run)

    # --- PV (AC) ---
    pv_results = simulate_pv_system(
        pv_size=float(pv_size),
        load_demand=base_load_ac,
        pv_generation=np.asarray(profiles["pv_generation"], dtype=float),
        params=params,
    )
    pv_generation_ac = np.asarray(pv_results["pv_production"], dtype=float)

    # --- EV-Leistungsgrenzen (temperaturabhängig, falls Modell vorhanden) ---
    if N_EV_total > 0:
        ev_sim = simulate_v2h_battery(temperature=T_outdoor, params=ev_params)
        charge_limit_series = np.asarray(
            ev_sim.get("charge_power_limit_capped", max_chg_power), dtype=float
        )
        discharge_limit_series = np.asarray(
            ev_sim.get("discharge_power_limit", 0.0), dtype=float
        )
    else:
        charge_limit_series = np.zeros(n_steps, dtype=float)
        discharge_limit_series = np.zeros(n_steps, dtype=float)

    # --- EV-Zustände / Container ---
    ev_soc_dc = np.zeros((n_steps, N_EV_total), dtype=float)
    if N_EV_total > 0:
        ev_soc_dc[0, :] = cap * init_soc_frac

    ev_charged_dc = np.zeros((n_steps, N_EV_total), dtype=float)
    ev_discharged_ac = np.zeros((n_steps, N_EV_total), dtype=float)
    trip_loss_dc = np.zeros((n_steps, N_EV_total), dtype=float)
    driving_energy_dc = np.zeros((n_steps, N_EV_total), dtype=float)
    ev_availability = np.zeros((n_steps, N_EV_total), dtype=bool)
    ev_is_active_series = np.zeros((n_steps, N_EV_total), dtype=bool)

    # optionale Speicherkapazitäten je Zeitschritt
    opt_charge_cap_ac = np.zeros((n_steps, N_EV_total), dtype=float)
    opt_discharge_cap_ac = np.zeros((n_steps, N_EV_total), dtype=float)

    # EV-Energieflüsse (Detail nur kosmetisch; für Surrogate reicht Total)
    ev_charge_from_pv_ac = np.zeros(n_steps, dtype=float)
    ev_charge_from_bess_ac = np.zeros(n_steps, dtype=float)
    ev_charge_from_ec_ac = np.zeros(n_steps, dtype=float)
    ev_charge_from_grid_ac = np.zeros(n_steps, dtype=float)

    # BESS-Requests
    battery_in_request_ac = np.zeros(n_steps, dtype=float)
    battery_out_request_ac = np.zeros(n_steps, dtype=float)
    bess_out_req_load_ac = np.zeros(n_steps, dtype=float)
    bess_out_req_ev_ac = np.zeros(n_steps, dtype=float)  # hier ungenutzt

    # Netz / EC
    grid_import_ac = np.zeros(n_steps, dtype=float)
    grid_export_ac = np.zeros(n_steps, dtype=float)
    ec_import_from_pv_ac = np.zeros(n_steps, dtype=float)
    ec_import_from_ev_ac = np.zeros(n_steps, dtype=float)
    ec_export_from_pv_ac = np.zeros(n_steps, dtype=float)

    timestep_h = 1.0

    # ---------------- Haupt-Zeitschleife ----------------
    for t in range(n_steps):
        if t > 0 and N_EV_total > 0:
            ev_soc_dc[t, :] = ev_soc_dc[t - 1, :]

        base_load_t = float(base_load_ac[t])
        pv_t = float(pv_generation_ac[t])

        # 1) EV-Verhalten (Fahrten + Mindest-SOC für Mobilität)
        ev_must_charge_ac_t = 0.0  # AC-Energie, die EVs MINDESTENS brauchen
        opt_charge_cap_ac_t = 0.0  # optionale Ladekapazität aller EVs
        opt_discharge_cap_ac_t = 0.0  # optionale V2H-Kapazität

        if N_EV_total > 0:
            for i in range(N_EV_total):
                # Verfügbarkeit
                is_available = bool(rng.random() <= availability_profile[t])
                ev_availability[t, i] = is_available
                ev_is_active_series[t, i] = is_available

                drive_dc = driving_profile[t] * cap
                driving_energy_dc[t, i] = drive_dc

                if not is_available:
                    # Fahrzeug unterwegs → SOC sinkt durch Fahrt
                    used_dc = min(ev_soc_dc[t, i], drive_dc)
                    ev_soc_dc[t, i] -= used_dc
                    trip_loss_dc[t, i] = used_dc
                    if self_dis_ev > 0.0:
                        ev_soc_dc[t, i] *= 1.0 - self_dis_ev
                    opt_charge_cap_ac[t, i] = 0.0
                    opt_discharge_cap_ac[t, i] = 0.0
                    continue

                # Fahrzeug steht in der EC
                min_soc_dc = cap * min_soc_data[t]
                max_soc_dc = cap * max_soc_frac

                # a) Mindest-SOC sicherstellen
                if ev_soc_dc[t, i] < min_soc_dc:
                    need_dc = min_soc_dc - ev_soc_dc[t, i]
                    need_ac = need_dc / max(eta_ch, 1e-9)
                    ev_soc_dc[t, i] += need_dc
                    ev_charged_dc[t, i] += need_dc
                    ev_must_charge_ac_t += need_ac

                # b) optionale Speicherkapazität zum Laden (PV-Überschuss)
                headroom_dc = max(0.0, max_soc_dc - ev_soc_dc[t, i])
                max_charge_ac_power = charge_limit_series[t] * timestep_h
                opt_charge_i = min(headroom_dc / max(eta_ch, 1e-9), max_charge_ac_power)
                opt_charge_cap_ac[t, i] = opt_charge_i
                opt_charge_cap_ac_t += opt_charge_i

                # c) optionale V2H-Kapazität (nur bidirektionale EVs)
                if i < N_EV_bidir:
                    room_above_min_dc = max(0.0, ev_soc_dc[t, i] - min_soc_dc)
                    max_dis_ac_power = discharge_limit_series[t] * timestep_h
                    opt_dis_i = min(room_above_min_dc * eta_dis, max_dis_ac_power)
                else:
                    opt_dis_i = 0.0
                opt_discharge_cap_ac[t, i] = opt_dis_i
                opt_discharge_cap_ac_t += opt_dis_i

                if self_dis_ev > 0.0:
                    ev_soc_dc[t, i] *= 1.0 - self_dis_ev

        # 2) Grundbilanz ohne optionale EV-Speicher
        demand0 = base_load_t + ev_must_charge_ac_t
        surplus0 = max(0.0, pv_t - demand0)   # PV-Überschuss
        deficit0 = max(0.0, demand0 - pv_t)   # Lastdefizit

        # 3) V2H: EVs decken Lastdefizit
        remaining_deficit = deficit0
        if N_EV_bidir > 0 and remaining_deficit > 1e-12:
            for i in range(N_EV_bidir):
                if remaining_deficit <= 1e-12:
                    break
                give_ac = min(remaining_deficit, opt_discharge_cap_ac[t, i])
                if give_ac <= 1e-12:
                    continue
                ev_soc_dc[t, i] -= give_ac / max(eta_dis, 1e-9)
                ev_discharged_ac[t, i] += give_ac
                remaining_deficit -= give_ac

        # v2h_used_ac_t = deficit0 - remaining_deficit  # nur fürs Verständnis
        deficit1 = remaining_deficit

        # 4) PV-Überschuss in EVs (optional) und BESS laden
        remaining_surplus = surplus0
        if N_EV_total > 0 and remaining_surplus > 1e-12:
            for i in range(N_EV_total):
                if remaining_surplus <= 1e-12:
                    break
                take_ac = min(remaining_surplus, opt_charge_cap_ac[t, i])
                if take_ac <= 1e-12:
                    continue
                ev_soc_dc[t, i] += take_ac * eta_ch
                ev_charged_dc[t, i] += take_ac * eta_ch
                remaining_surplus -= take_ac
                ev_charge_from_pv_ac[t] += take_ac  # rein informativ

        # Restlicher PV-Überschuss als BESS-Ladewunsch
        battery_in_request_ac[t] = max(0.0, remaining_surplus)
        bess_out_req_ev_ac[t] = 0.0
        bess_out_req_load_ac[t] = deficit1
        battery_out_request_ac[t] = deficit1

        # EV-Laden (als AC) fürs Monitoring – hier nutzen wir die DC-Lademenge:
        if N_EV_total > 0:
            total_ev_charged_dc_t = float(np.sum(ev_charged_dc[t, :]))
            ev_charge_total_ac_t = total_ev_charged_dc_t / max(eta_ch, 1e-9)
            # falls du hier eine explizite Aufteilung PV/BESS/Grid/EC willst,
            # müsste man die Quellenverfolgung differenzierter machen.
            ev_charge_from_pv_ac[t] = ev_charge_total_ac_t

    # --- BESS-Simulation (mit N_EC-skalierter Leistung) ---
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

    # Simple Aufteilung: gesamte BESS-Entladung geht an die Last
    bess_out_to_ev_ac = np.zeros_like(bess_out_ac)
    bess_out_to_load_ac = bess_out_ac.copy()
    ev_charge_from_bess_ac[:] = 0.0

    # --- Endbilanz: EC-Clearing + Grid-Import/-Export & total_load ---

    # gesamte EV-Ladung (AC) aus den DC-Lademengen rekonstruiert
    ev_charge_ac = np.zeros(n_steps, dtype=float)
    if N_EV_total > 0:
        ev_charge_ac = np.sum(ev_charged_dc, axis=1) / max(eta_ch, 1e-9)

    # Brutto-Last innerhalb der EC (Haushalt + WW + HP + EV-Ladung)
    gross_load_ac = base_load_ac + ev_charge_ac

    total_load_out_ac = np.zeros(n_steps, dtype=float)

    # EC-Clearing: member-level arrays
    ev_charge_member = np.zeros((n_steps, N_EC), dtype=float)
    ev_discharge_member = np.zeros((n_steps, N_EC), dtype=float)
    if N_EV_total > 0:
        ev_charge_ac_by_ev = ev_charged_dc / max(eta_ch, 1e-9)
        for i in range(N_EV_total):
            ev_charge_member[:, ev_to_member[i]] += ev_charge_ac_by_ev[:, i]
            ev_discharge_member[:, ev_to_member[i]] += ev_discharged_ac[:, i]

    if has_member_level:
        # Use member-level base_load
        base_load_member = base_load_member_2d.copy()
        pv_member = pv_generation_ac[:, None] / float(N_EC)  # PV shared uniformly
        bess_out_member = bess_out_ac[:, None] / float(N_EC)  # BESS shared uniformly
        bess_in_member = bess_in_ac[:, None] / float(N_EC)  # BESS shared uniformly
    else:
        # Legacy: distribute evenly
        base_load_member = base_load_ac[:, None] / float(N_EC)
        pv_member = pv_generation_ac[:, None] / float(N_EC)
        bess_out_member = bess_out_ac[:, None] / float(N_EC)
        bess_in_member = bess_in_ac[:, None] / float(N_EC)

    gross_load_member = base_load_member + ev_charge_member
    demand_member = gross_load_member + bess_in_member
    supply_member = pv_member + bess_out_member + ev_discharge_member
    net_member = supply_member - demand_member

    grid_import_ac, grid_export_ac, _ec_sell_member, _ec_buy_member, T_ec = clear_ec(net_member)

    net_pos = np.clip(net_member, 0.0, None)
    denom = pv_member + bess_out_member + ev_discharge_member + 1e-9
    pv_surplus_member = net_pos * (pv_member / denom)
    ev_surplus_member = net_pos * (ev_discharge_member / denom)

    ec_import_from_pv_ac, ec_import_from_ev_ac, ec_export_from_pv_ac = split_trade_by_source(
        T_ec, pv_surplus_member, ev_surplus_member
    )

    for t in range(n_steps):
        total_load_out_ac[t] = gross_load_ac[t]

    if not hasattr(simulate_energy_system_with_v2h, "_ec_printed"):
        simulate_energy_system_with_v2h._ec_printed = True
        surplus_member = np.clip(net_member, 0.0, None)
        deficit_member = np.clip(-net_member, 0.0, None)
        S_t = np.sum(surplus_member, axis=1)
        D_t = np.sum(deficit_member, axis=1)
        T_t = np.minimum(S_t, D_t)
        print(
            "[EC CLEARING] [REMOVE AFTER CHECK] "
            f"N_EC={N_EC} "
            f"S_total={float(np.sum(S_t)):.6g} "
            f"D_total={float(np.sum(D_t)):.6g} "
            f"T_total={float(np.sum(T_t)):.6g} "
            f"trade_hours={int(np.sum(T_t > 0.0))} "
            f"grid_import_total={float(np.sum(grid_import_ac)):.6g} "
            f"grid_export_total={float(np.sum(grid_export_ac)):.6g}"
        )

    result: Dict[str, Any] = {
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
        # EV-Quellen (vereinfachte Buchung)
        "ev_charge_ac": ev_charge_ac,
        "ev_charge_from_pv_ac": ev_charge_from_pv_ac,
        "ev_charge_from_bess_ac": ev_charge_from_bess_ac,
        "ev_charge_from_ec_ac": ev_charge_from_ec_ac,
        "ev_charge_from_grid_ac": ev_charge_from_grid_ac,
        # BESS
        "bess_charged": bess_in_ac,
        "bess_discharged": bess_out_ac,
        "bess_soc": np.asarray(battery_results["soc_history"], dtype=float),
        "BESS_replacements": battery_results.get("BESS_replacements", 0),
        "bess_to_ev_ac": bess_out_to_ev_ac,
        "bess_to_load_ac": bess_out_to_load_ac,
        # Netz / EC / Basis
        "grid_import": grid_import_ac,
        "grid_export": grid_export_ac,
        "ec_import_from_pv": ec_import_from_pv_ac,
        "ec_import_from_ev": ec_import_from_ev_ac,
        "ec_export_from_pv": ec_export_from_pv_ac,
        "total_load": total_load_out_ac,
        "pv_generation": pv_generation_ac,
        # NEU: Base-Load der EC (Haushalt + HP + WW) für Bilanzchecks
        "base_load": base_load_ac,
        "timestamps": profiles.get(
            "timestamps",
            pd.date_range(start="2023-01-01", periods=n_steps, freq="h"),
        ),
        "hotwater_load": hotwater,
        "household_load": load,  # reine Haushaltslast
    }

    return result
