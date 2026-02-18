from __future__ import annotations
import os
import json
import numpy as np
import pandas as pd

from Optimization.framework.engines.Vectorized_model.fast_engine import FastEngine

from Data.data import get_parameters, load_profiles
from Technical_model.energy_system.precompute.precompute import prepare_profiles

# Direkt die Systemmodelle importieren
from Technical_model.energy_system.systems.PV_BESS_HP_V2H import (
    simulate_energy_system_with_v2h,
)

from Technical_model.energy_system.systems.PV_BESS_HP_EV import (
    simulate_energy_system as simulate_energy_system_ev,   # ← Funktionsnamen ggf. anpassen!
)


def export_load_flows_timeseries(
    run_dir: str,
    settings,
    X_opt: np.ndarray,
    max_points: int = 5,   # zur Sicherheit begrenzen, kannst du auf None/all ändern
) -> None:
    """
    Zweiter Export: stündliche Lastflüsse (wie Sanity-File), aber für Optimierungspunkte.
    Schreibt: <run_dir>/load_flows_timeseries.csv

    Spalten:
      point_idx, pv_kwp, bess_kwh, t_idx, timestamp,
      grid_import, grid_export, bess_charged, bess_discharged,
      ev_charged_total (DC), ev_discharged_total (AC),
      ev_charge_ac (AC-Ladung ins EV),
      base_load, pv_generation, total_load
    """

    if X_opt is None or len(X_opt) == 0:
        return

    X_arr = np.asarray(X_opt, float)
    if X_arr.ndim == 1:
        X_arr = X_arr.reshape(1, -1)

    eng = settings.engine

    # --- Basis-Params & Profile wie im Teacher/Surrogat ---
    params = get_parameters(eng.location)
    params["location"] = eng.location

    # EC-Parameter aus Settings übernehmen
    params.setdefault("EC", {})
    params["EC"]["share"] = float(eng.ec_share_import)
    params["EC"]["export_share"] = float(eng.ec_share_export)

    # Community-Zähler
    params["N_HH"] = int(eng.N_HH)
    params["N_EV"] = int(eng.N_EV_total)  # legacy
    params["N_EV_bidirectional"] = int(eng.N_EV_bidirectional)

    params.setdefault("EV", {})
    params["EV"]["N_EV_total"] = int(eng.N_EV_total)
    params["EV"]["N_EV_bidirectional"] = int(eng.N_EV_bidirectional)
    
    # Add N_EC and rng_seed from settings
    params["N_EC"] = int(eng.N_EC)
    params["rng_seed"] = int(eng.rng_seed)

    # Profile vorbereiten (with member_ids)
    members = getattr(eng, "members", None)
    member_ids = None
    member_counts = None
    if members is not None and hasattr(members, "members") and len(members.members) > 0:
        member_ids = [m.id for m in members.members]
        member_counts = [m.count for m in members.members]
    
    profiles_raw = load_profiles(eng.location, member_ids=member_ids, member_counts=member_counts)
    profiles = prepare_profiles(params, profiles_raw, do_hp_electricity=True, do_coeffs=False, members=members)

    # Mapping Bounds → Spalten in X
    name_to_idx = {n: i for i, n in enumerate(settings.bounds.names)}
    idx_pv = name_to_idx.get("pv_kwp", 0)
    idx_bess = name_to_idx.get("bess_kwh", 1)

    n_points = X_arr.shape[0]
    if max_points is None or max_points <= 0 or max_points > n_points:
        sel_idx = range(n_points)
    else:
        sel_idx = range(max_points)

    rows = []

    def _to_1d(res_dict, key):
        """Hole 1D-Zeitreihe aus result[key]; 2D (EV-Matrix) → Summe über EVs."""
        arr = res_dict.get(key, None)
        if arr is None:
            return None
        a = np.asarray(arr, float)
        if a.ndim == 1:
            return a
        elif a.ndim == 2:
            return a.sum(axis=1)
        else:
            # zur Sicherheit: alles auf (T,-1) flatten und über alle außer Zeit summieren
            return a.reshape(a.shape[0], -1).sum(axis=1)

    for j in sel_idx:
        pv_kwp = float(X_arr[j, idx_pv])
        bess_kwh = float(X_arr[j, idx_bess])

        p = dict(params)
        p["pv_size"] = pv_kwp
        p["battery_capacity_kWh"] = bess_kwh

        # --- Systemmodell je nach Szenario aufrufen ---
        if eng.system_id == "PV_BESS_HP_V2H":
            res = simulate_energy_system_with_v2h(p, profiles, pv_kwp)

        elif eng.system_id == "PV_BESS_HP_EV":
            res = simulate_energy_system_ev(p, profiles, pv_kwp)

        else:
            raise ValueError(
                f"export_load_flows_timeseries: system_id '{eng.system_id}' "
                f"wird hier noch nicht unterstützt."
            )

        timestamps = res.get("timestamps", None)

        if timestamps is not None:
            ts_arr = np.asarray(timestamps)
            n_steps = ts_arr.shape[0]
        else:
            grid_import = _to_1d(res, "grid_import")
            if grid_import is None:
                continue
            n_steps = grid_import.shape[0]
            ts_arr = None

        # --- relevante Zeitreihen (alle als 1D) ---
        grid_import        = _to_1d(res, "grid_import")
        grid_export        = _to_1d(res, "grid_export")
        bess_charged       = _to_1d(res, "bess_charged")
        bess_discharged    = _to_1d(res, "bess_discharged")
        ev_charged_total   = _to_1d(res, "ev_charged")       # DC-Energie ins EV
        ev_discharged_total= _to_1d(res, "ev_discharged")    # AC-Energie aus EV (V2H)
        pv_generation      = _to_1d(res, "pv_generation")
        total_load         = _to_1d(res, "total_load")

        # NEU: base_load und ev_charge_ac explizit ziehen
        base_load          = _to_1d(res, "base_load")        # HH + HP + WW (AC)
        ev_charge_ac       = _to_1d(res, "ev_charge_ac")     # gesamte EV-Ladung (AC)

        base_load = _to_1d(res, "base_load")  # HH + HP + WW
        household_load = _to_1d(res, "household_load")  # reine Haushaltslast
        hp_elec_heat = _to_1d(res, "heatpump_results_heating")  # WP-Heizen
        hp_elec_cool = _to_1d(res, "heatpump_results_cooling")  # WP-Kühlen
        hotwater_load = _to_1d(res, "hotwater_load")  # Warmwasser


        for t in range(n_steps):
            row = {
                "point_idx": int(j),
                "pv_kwp": pv_kwp,
                "bess_kwh": bess_kwh,
                "t_idx": t,
            }
            if ts_arr is not None:
                row["timestamp"] = str(ts_arr[t])

            if grid_import is not None:
                row["grid_import"] = float(grid_import[t])
            if grid_export is not None:
                row["grid_export"] = float(grid_export[t])
            if bess_charged is not None:
                row["bess_charged"] = float(bess_charged[t])
            if bess_discharged is not None:
                row["bess_discharged"] = float(bess_discharged[t])
            if ev_charged_total is not None:
                row["ev_charged_total"] = float(ev_charged_total[t])      # DC
            if ev_discharged_total is not None:
                row["ev_discharged_total"] = float(ev_discharged_total[t])# AC
            if ev_charge_ac is not None:
                row["ev_charge_ac"] = float(ev_charge_ac[t])              # AC-Ladung
            if base_load is not None:
                row["base_load"] = float(base_load[t])
            if pv_generation is not None:
                row["pv_generation"] = float(pv_generation[t])
            if total_load is not None:
                row["total_load"] = float(total_load[t])
            # NEU: Basis-Last + Komponenten
            if base_load is not None:
                row["base_load"] = float(base_load[t])
            if household_load is not None:
                row["household_load"] = float(household_load[t])
            if hp_elec_heat is not None:
                row["hp_elec_heat"] = float(hp_elec_heat[t])
            if hp_elec_cool is not None:
                row["hp_elec_cool"] = float(hp_elec_cool[t])
            if hotwater_load is not None:
                row["hotwater_load"] = float(hotwater_load[t])


            rows.append(row)

    if rows:
        df = pd.DataFrame(rows)
        out_csv = os.path.join(run_dir, "load_flows_timeseries.csv")
        df.to_csv(out_csv, index=False)



def export_pareto_csv(
    run_dir: str,
    settings,
    X_opt: np.ndarray,
    F_opt: np.ndarray,
    G_opt: np.ndarray | None = None,
    use_teacher_for_details: bool = True,
) -> None:
    if X_opt is None or len(X_opt) == 0:
        raise ValueError("X_opt ist leer – kein CSV-Export möglich.")

    X = np.asarray(X_opt, float)
    F = np.asarray(F_opt, float) if F_opt is not None else None
    G = np.asarray(G_opt, float) if G_opt is not None else None

    cols = list(settings.bounds.names)  # ["pv_kwp", "bess_kwh"]
    df = pd.DataFrame(X, columns=cols)

    # F/G-Spalten (NPC/PEF + Constraints)
    if F is not None:
        for j, name in enumerate(settings.objectives.names):
            df[f"F_{name}"] = F[:, j]
            # Autarkiegrad aus F + Settings ableiten (falls grid_import_kwh als Ziel vorhanden ist)
            try:
                obj_names = list(settings.objectives.names)
                if F is not None and "grid_import_kwh" in obj_names:
                    j_imp = obj_names.index("grid_import_kwh")

                    # Basis-Parameter und Profile wie im Teacher/FastEngine
                    eng = settings.engine
                    base_params = get_parameters(eng.location)
                    base_params["location"] = eng.location

                    # EC-Shares aus Settings
                    if "EC" not in base_params:
                        base_params["EC"] = {}
                    base_params["EC"]["share"] = float(eng.ec_share_import)
                    base_params["EC"]["export_share"] = float(eng.ec_share_export)

                    # Skalierungen (Haushalte, EVs)
                    base_params["N_HH"] = int(eng.N_HH)
                    base_params["N_EV"] = int(eng.N_EV_total)
                    base_params["N_EV_bidirectional"] = int(eng.N_EV_bidirectional)

                    # Profile vorbereiten und Jahreslast bestimmen
                    profiles_raw = load_profiles(eng.location)
                    profiles = prepare_profiles(base_params, profiles_raw,
                                                do_hp_electricity=True,
                                                do_coeffs=False)
                    year_load = float(np.sum(np.asarray(profiles["load"], float)))
                    L = int(base_params["lifetime"])
                    E_load_L = year_load * L if L > 0 else None

                    if E_load_L and E_load_L > 0.0:
                        E_imp_L = F[:, j_imp]
                        autarky = 1.0 - (E_imp_L / E_load_L)
                        df["autarky"] = autarky
            except Exception as e:
                # Falls irgendetwas schiefgeht, Export nicht abbrechen,
                # sondern Hinweis in eine kleine Warnungsdatei schreiben.
                with open(os.path.join(run_dir, "autarky_warning.txt"), "w", encoding="utf-8") as f:
                    f.write(f"Autarkie-Berechnung im CSV fehlgeschlagen: {e}\n")

    if G is not None and G.size:
        for j, name in enumerate(settings.constraints.names):
            df[f"G_{name}"] = G[:, j]

    # Optional: Detail-KPIs/Flows via FAST (für Reporting), ohne Fallbacks
    if use_teacher_for_details:
        teacher = FastEngine(settings)
        F_t, G_t = teacher.evaluate(X)  # konsistenter Check (nicht zwingend benutzt)
        # Beispielhafte ~15 relevante Größen aus dem Teacher für Kontext/Debug
        # → Wir nehmen an, dass teacher.additional() einen dict je X liefert.
        #   Falls nicht vorhanden, kommentiere diese Zeilen und nutze nur F/G.
        try:
            details_rows = []
            for i in range(len(X)):
                # Implementiere in deinem FastEngine optional eine Methode .flows(X[i])
                # die ein dict mit Schlüssel/Wert zurückgibt.
                flows = teacher.flows(X[i])  # <— falls nicht vorhanden, Exception (keine Fallbacks)
                details_rows.append(flows)
            df_details = pd.DataFrame(details_rows)
            # Auswahl auf ~15
            wanted = [
                "E_import_grid_kWh",
                "E_export_grid_kWh",
                "E_bess_throughput_kWh",
                "E_hp_heat_kWh",
                "E_hp_cool_kWh",
                "E_pv_gen_kWh",
                "E_ev_charged_kWh",
                "E_ev_discharged_kWh",
                "E_ev_trip_loss_kWh",
                "EC_import_from_pv_kWh",
                "EC_import_from_ev_kWh",
                "EC_export_to_grid_kWh",
                "autarky",           # als informative KPI
                "self_consumption",  # optional falls vorhanden
                "peak_import_kW"     # optional falls vorhanden
            ]
            existing = [c for c in wanted if c in df_details.columns]
            df = pd.concat([df, df_details[existing]], axis=1)
        except Exception as e:
            # Explizit: keine stillen Fallbacks – klare Meldung ins results.json.appendix
            with open(os.path.join(run_dir, "export_warning.txt"), "w", encoding="utf-8") as f:
                f.write(f"Detail-Export via FAST fehlgeschlagen: {e}\n")

    out_csv = os.path.join(run_dir, "pareto_points.csv")
    df.to_csv(out_csv, index=False)

    # Zusätzlich die Roh-Results (zur Nachvollziehbarkeit)
    with open(os.path.join(run_dir, "results_plus.csvmeta.json"), "w", encoding="utf-8") as f:
        json.dump({
            "objectives": settings.objectives.names,
            "constraints": settings.constraints.names,
            "bounds": {"names": settings.bounds.names, "lower": settings.bounds.lower, "upper": settings.bounds.upper},
        }, f, indent=2)
