# Technical_model/energy_system/validation/proof_loadflows.py
# -----------------------------------------------------------------------------
# Proof-of-Loadflows (Stand-alone):
# - Lädt Params/Profiles
# - 1-Jahres-Precompute
# - Setzt EC-Shares direkt ins params["EC"]
# - Rechnet System (NoV2H oder V2H)
# - Baut hourly-Tabelle + strikte Bilanzchecks
# - Druckt Summaries
# - Optional: Äquivalenztest (V2H mit N_bidir=0 ≙ NoV2H)
# -----------------------------------------------------------------------------

from __future__ import annotations
import sys
from typing import Dict, Any
import numpy as np
import pandas as pd

# Daten/Zugriffe aus deiner Struktur
from Data.data import get_parameters, load_profiles
from Technical_model.energy_system.precompute.precompute import prepare_profiles

# System-Runner (neue, gesplittete Systeme)
from Technical_model.energy_system.systems.PV_BESS_HP_EV import (
    simulate_energy_system as run_ev
)
from Technical_model.energy_system.systems.PV_BESS_HP_V2H import (
    simulate_energy_system_with_v2h as run_v2h
)

# =============================================================================
# Helpers (lokal eingebettet, damit alles in EINER Datei ist)
# =============================================================================

def _hourly_table(res: dict, profiles: dict, params: dict, use_v2h: bool) -> pd.DataFrame:
    """Stündliche Tabelle der AC-Energieflüsse + Bilanz-Checks (robust ggü. 1D/2D)."""
    ts = res.get("timestamps", profiles.get("timestamp", None))
    if ts is None:
        N = len(np.asarray(profiles["load"]))
        ts = pd.date_range("2000-01-01", periods=N, freq="H")
    ts = pd.to_datetime(ts)
    N = len(ts)

    def _to1d(a, agg="sum", fill=0.0):
        if a is None:
            return np.full(N, fill, dtype=float)
        arr = np.asarray(a, dtype=float)
        if arr.ndim == 0:
            return np.full(N, float(arr), dtype=float)
        if arr.ndim == 1:
            return arr if arr.size == N else np.resize(arr, N).astype(float, copy=False)
        # 2D+: Summe (oder Mittel) über EVs/Komponenten je Stunde
        if agg == "mean":
            arr = np.nanmean(arr, axis=1)
        else:
            arr = np.nansum(arr, axis=1)
        return arr if arr.size == N else np.resize(arr, N).astype(float, copy=False)

    # Basis AC
    base_load = (
        _to1d(profiles.get("load")) +
        _to1d(profiles.get("hp_elec_heat")) +
        _to1d(profiles.get("hp_elec_cool")) +
        _to1d(profiles.get("hotwater_HH_kWh"))
    )
    pv_ac = _to1d(res.get("pv_generation"))

    # EV (AC)
    ev_charge_ac     = _to1d(res.get("ev_charge_ac"))
    ev_discharge_ac  = _to1d(res.get("ev_discharged"), agg="sum") if use_v2h else np.zeros(N)

    # EV-Quellen (AC)
    ev_from_pv   = _to1d(res.get("ev_charge_from_pv_ac"))
    ev_from_bess = _to1d(res.get("ev_charge_from_bess_ac"))
    ev_from_ec   = _to1d(res.get("ev_charge_from_ec_ac"))
    ev_from_grid = _to1d(res.get("ev_charge_from_grid_ac"))

    # Speicher/Netz/EC (AC)
    bess_charge    = _to1d(res.get("bess_charged"))
    bess_discharge = _to1d(res.get("bess_discharged"))
    grid_import    = _to1d(res.get("grid_import"))
    grid_export    = _to1d(res.get("grid_export"))
    ec_imp_pv      = _to1d(res.get("ec_import_from_pv"))
    ec_imp_ev      = _to1d(res.get("ec_import_from_ev"))
    ec_exp_pv      = _to1d(res.get("ec_export_from_pv"))

    # BESS→Load separieren (keine Doppelzählung)
    bess_to_ev = _to1d(res.get("bess_to_ev_ac")) if use_v2h or ("bess_to_ev_ac" in res) else np.zeros(N)
    bess_to_load = bess_discharge - bess_to_ev
    bess_to_load = np.maximum(bess_to_load, 0.0)

    # Lastseite (AC)
    total_load_ac = base_load + ev_charge_ac - ev_discharge_ac

    # Deckung durch echte Quellen
    covered_ac = (
        np.minimum(pv_ac, base_load) +
        ev_from_pv +
        bess_to_load +
        bess_to_ev +          # EV lädt am AC-Knoten (BESS→EV zählt als Quelle)
        ec_imp_pv +
        ec_imp_ev +
        grid_import
    )
    mb_load_res = total_load_ac - covered_ac

    # PV-Bilanz: PV = PV→Basis + PV→BESS + PV→EV + PV→Grid + PV→EC
    pv_used_ac = (
        np.minimum(pv_ac, base_load) +
        bess_charge +
        ev_from_pv +
        grid_export +
        ec_exp_pv
    )
    mb_pv_res = pv_ac - pv_used_ac

    df = pd.DataFrame({
        "Timestamp": ts,
        "Grid_Import": grid_import,
        "Grid_Export": grid_export,
        "BESS_Charge": bess_charge,
        "BESS_Discharge": bess_discharge,
        "BESS_to_Load": bess_to_load,
        "BESS_to_EV": bess_to_ev,
        "PV_Production": pv_ac,
        # EC
        "EC_Import_from_PV": ec_imp_pv,
        "EC_Import_from_EV": ec_imp_ev,
        "EC_Export_from_PV": ec_exp_pv,
        # EV (AC)
        "EV_Charge_AC": ev_charge_ac,
        "EV_Charge_from_PV_AC": ev_from_pv,
        "EV_Charge_from_BESS_AC": ev_from_bess,
        "EV_Charge_from_EC_AC": ev_from_ec,
        "EV_Charge_from_Grid_AC": ev_from_grid,
        "EV_Discharge_AC": ev_discharge_ac,
        # Bilanzen
        "MassBalance_Load_residual": mb_load_res,
        "MassBalance_PV_residual": mb_pv_res,
        # Transparenz
        "Total_Load_AC": total_load_ac,
        "Covered_AC": covered_ac,
        "BESS_SOC": _to1d(res.get("bess_soc")),
        "EV_SOC_DC": _to1d(res.get("ev_soc"), agg="mean"),
    })
    return df


def check_mass_balances(df: pd.DataFrame, tol_sum=1e-6, tol_hour=1e-6, tol_bess=-1e-6):
    mb_load = df["MassBalance_Load_residual"]
    mb_pv   = df["MassBalance_PV_residual"]

    mb_load_sum = float(mb_load.sum())
    mb_pv_sum   = float(mb_pv.sum())
    max_mb_load = float(np.abs(mb_load).max())
    max_mb_pv   = float(np.abs(mb_pv).max())

    print("\n--- MASS BALANCE CHECK ---")
    print(f"Sum residual LOAD: {mb_load_sum:.6e}  (tol {tol_sum})")
    print(f"Sum residual PV:   {mb_pv_sum:.6e}  (tol {tol_sum})")
    print(f"Max hourly LOAD residual: {max_mb_load:.6e}  (tol {tol_hour})")
    print(f"Max hourly PV residual:   {max_mb_pv:.6e}  (tol {tol_hour})")

    ec_imp = float(df.get("EC_Import_from_PV", pd.Series(0.0)).sum()) + \
             float(df.get("EC_Import_from_EV", pd.Series(0.0)).sum())
    ec_exp = float(df.get("EC_Export_from_PV", pd.Series(0.0)).sum())
    ec_gap = ec_imp - ec_exp
    print(f"EC neutrality (internal match imp-exp): {ec_gap:.6f} kWh")
    if abs(ec_gap) > 1e-6:
        print(f"[warn] EC neutrality small gap: {ec_gap:.6f} kWh")

    # BESS-Verluste = in - out - ΔSOC (>= 0 erwartet)
    bess_in  = float(df["BESS_Charge"].sum())
    bess_out = float(df["BESS_Discharge"].sum())
    bess_soc = np.asarray(df["BESS_SOC"], dtype=float)
    d_soc    = float(bess_soc[-1] - bess_soc[0]) if len(bess_soc) > 1 else 0.0
    bess_losses = bess_in - bess_out - d_soc
    print(f"BESS losses (in - out - ΔSOC): {bess_losses:.6f} kWh "
          f"(in={bess_in:.6f}, out={bess_out:.6f}, ΔSOC={d_soc:.6f})")

    errs = []
    if abs(mb_load_sum) > tol_sum:
        t_idx = int(np.argmax(np.abs(mb_load)))
        t = df["Timestamp"].iloc[t_idx]
        val = mb_load.iloc[t_idx]
        errs.append(f"LOAD sum residual {mb_load_sum:.3e} (exceeds {tol_sum}); worst @ {t}: {val:.3e}")
    if abs(mb_pv_sum) > tol_sum:
        t_idx = int(np.argmax(np.abs(mb_pv)))
        t = df["Timestamp"].iloc[t_idx]
        val = mb_pv.iloc[t_idx]
        errs.append(f"PV sum residual {mb_pv_sum:.3e} (exceeds {tol_sum}); worst @ {t}: {val:.3e}")
    if max_mb_load > tol_hour:
        t_idx = int(np.argmax(np.abs(mb_load)))
        t = df["Timestamp"].iloc[t_idx]
        val = mb_load.iloc[t_idx]
        errs.append(f"Max hourly LOAD residual {val:.3e} @ {t} (exceeds {tol_hour})")
    if max_mb_pv > tol_hour:
        t_idx = int(np.argmax(np.abs(mb_pv)))
        t = df["Timestamp"].iloc[t_idx]
        val = mb_pv.iloc[t_idx]
        errs.append(f"Max hourly PV residual {val:.3e} @ {t} (exceeds {tol_hour})")

    if bess_losses < tol_bess:
        errs.append(f"BESS losses negative ({bess_losses:.3e} kWh) – check efficiency/self-discharge conventions")

    if errs:
        msg = "Mass/flux checks failed:\n  - " + "\n  - ".join(errs)
        raise RuntimeError(msg)

# =============================================================================
# Main (keine CLI-Args, zentral editierbare Settings)
# =============================================================================
if __name__ == "__main__":
    # ===== Settings =====
    LOCATION = "Vienna"
    USE_V2H  = True          # True → V2H, False → NoV2H
    PV_KWP   = 100.0
    BESS_KWH = 100.0

    # EC-Anteile
    EC_SHARE_IMPORT  = 1.0
    EC_EXPORT_SHARE  = 1.0

    # Toleranzen
    TOL_SUM    = 1e-6
    TOL_HOUR   = 1e-6
    TOL_EN     = 1e-4
    TOL_EQ_ABS = 1e-6
    TOL_EQ_REL = 1e-6
    PRINT_FIRST_H = 0

    # RNG
    RNG_SEED = 42
    np.random.seed(RNG_SEED)

    # ===== Daten laden / vorbereiten =====
    base_params: Dict[str, Any] = get_parameters(LOCATION)
    base_params["location"] = LOCATION
    profiles_raw = load_profiles(LOCATION)
    profiles = prepare_profiles(base_params, profiles_raw, do_hp_electricity=True, do_coeffs=False)

    # Parameter zusammenstellen
    params: Dict[str, Any] = dict(base_params)
    params["pv_size"] = float(PV_KWP)
    params["battery_capacity_kWh"] = float(BESS_KWH)

    # EC (neu: deine Systemfunktionen erwarten params["EC"]["share"/"export_share"])
    params["EC"] = dict(params.get("EC", {}))
    params["EC"]["share"] = float(EC_SHARE_IMPORT)
    params["EC"]["export_share"] = float(EC_EXPORT_SHARE)

    # RNG-Seed deterministisch in die Sim-Funktionen geben
    params["rng_seed"] = RNG_SEED

    # ===== Simulation (gewählte Variante) =====
    sim = run_v2h if USE_V2H else run_ev
    res = sim(params, profiles, pv_size=float(PV_KWP))
    df = _hourly_table(res, profiles, params, use_v2h=USE_V2H)

    print("\n=== SETTINGS ===")
    print(f"Location               : {LOCATION}")
    print(f"Variant                : {'V2H' if USE_V2H else 'NoV2H'}")
    print(f"PV [kWp] / BESS [kWh]  : {PV_KWP:.3f} / {BESS_KWH:.3f}")
    print(f"EC_SHARE (import)      : {EC_SHARE_IMPORT:.3f}")
    print(f"EC_EXPORT_SHARE        : {EC_EXPORT_SHARE:.3f}")

    if PRINT_FIRST_H > 0:
        print("\n--- First hours ---")
        print(df.head(int(PRINT_FIRST_H)).to_string(index=False))

    # ===== Summen / Reporting =====
    s = df.sum(numeric_only=True)
    total_load_ac = float(s.get("Total_Load_AC", 0.0))
    pv_sum        = float(s.get("PV_Production", 0.0))
    grid_imp      = float(s.get("Grid_Import", 0.0))
    grid_exp      = float(s.get("Grid_Export", 0.0))
    bess_chg      = float(s.get("BESS_Charge", 0.0))
    bess_dis      = float(s.get("BESS_Discharge", 0.0))
    ev_charge_ac  = float(s.get("EV_Charge_AC", 0.0))
    ev_from_sum   = float(
        s.get("EV_Charge_from_PV_AC", 0.0) +
        s.get("EV_Charge_from_BESS_AC", 0.0) +
        s.get("EV_Charge_from_EC_AC", 0.0) +
        s.get("EV_Charge_from_Grid_AC", 0.0)
    )
    ec_imp_int    = float(s.get("EC_Import_from_PV", 0.0) + s.get("EC_Import_from_EV", 0.0))
    ec_exp_int    = float(s.get("EC_Export_from_PV", 0.0))
    ec_autarky    = 1.0 - (grid_imp / max(total_load_ac, 1e-12))

    print("\n=== ANNUAL SUMMARY ===")
    print(f"Total Load AC          : {total_load_ac:12.3f} kWh")
    print(f"PV Production          : {pv_sum:12.3f} kWh")
    print(f"Grid Import            : {grid_imp:12.3f} kWh")
    print(f"Grid Export            : {grid_exp:12.3f} kWh")
    print(f"BESS Charge / Disch.   : {bess_chg:12.3f} / {bess_dis:12.3f} kWh")
    print(f"EV charge total (AC)   : {ev_charge_ac:12.3f} kWh")
    print(f"EV charge by sources   : {ev_from_sum:12.3f} kWh")
    print(f"EC Import (internal)   : {ec_imp_int:12.3f} kWh")
    print(f"EC Export (internal)   : {ec_exp_int:12.3f} kWh")
    print(f"EC Neutrality (imp-exp): {(ec_imp_int - ec_exp_int): .6f} kWh")
    print(f"EC Autarky (1-Grid/Load): {ec_autarky:.4f}")

    # ===== Zusatz-Infos EV =====
    ev_dis_total = 0.0
    n_ev_discharged_once = 0
    if "ev_discharged" in res:
        ev_dis_arr = np.asarray(res["ev_discharged"], dtype=float)
        if ev_dis_arr.ndim == 2:
            ev_dis_total = float(ev_dis_arr.sum())
            n_ev_discharged_once = int(np.sum(np.any(ev_dis_arr > 1e-9, axis=0)))
        else:
            ev_dis_total = float(np.sum(ev_dis_arr))
            n_ev_discharged_once = int((ev_dis_arr > 1e-9).any())

    n_ev_charged_once = 0
    if "ev_soc" in res:
        ev_soc = np.asarray(res["ev_soc"], dtype=float)
        if ev_soc.ndim == 2 and ev_soc.shape[0] >= 2:
            dsoc = np.diff(ev_soc, axis=0)
            n_ev_charged_once = int(np.sum(np.any(dsoc > 1e-9, axis=0)))

    print(f"EV discharge total         : {ev_dis_total:12.3f} kWh")
    print(f"EVs charged at least 1x    : {n_ev_charged_once:d}")
    print(f"EVs discharged at least 1x : {n_ev_discharged_once:d}")

    # ===== Harte Bilanzprüfungen =====
    errors = []
    try:
        check_mass_balances(df, tol_sum=TOL_SUM, tol_hour=TOL_HOUR)
    except RuntimeError as e:
        errors.append(str(e))

    # Konsistenz EV-Quellen
    if abs(ev_from_sum - ev_charge_ac) > TOL_EN:
        errors.append(
            f"EV charge source mismatch: sources={ev_from_sum:.6f} vs EV_Charge_AC={ev_charge_ac:.6f} (tol {TOL_EN})"
        )

    # BESS-Verluste >= 0
    bess_soc = np.asarray(res.get("bess_soc"), dtype=float).ravel()
    if bess_soc.size >= 1:
        delta_soc = float(bess_soc[-1] - bess_soc[0])
        bess_losses = (bess_chg - bess_dis) - delta_soc
        if bess_losses < -max(TOL_EN, 10*TOL_SUM):
            errors.append(
                f"BESS losses negative (={bess_losses:.6f} kWh). "
                f"(in={bess_chg:.6f}, out={bess_dis:.6f}, ΔSOC={delta_soc:.6f})"
            )

    # ===== Äquivalenztest: V2H mit N_bidir=0 ≙ NoV2H (optional automatisch)
    try:
        n_bidir = int(params.get("EV", {}).get("N_EV_bidirectional", 0))
    except Exception:
        n_bidir = 0

    if USE_V2H and n_bidir == 0:
        # Referenz: NoV2H mit gleicher RNG-Reihe
        np.random.seed(RNG_SEED)
        res_ref = run_ev(params, profiles, pv_size=float(PV_KWP))
        df_ref  = _hourly_table(res_ref, profiles, params, use_v2h=False)

        s_ref = df_ref.sum(numeric_only=True)
        def _close(a, b):
            if max(abs(a), abs(b), 1.0) == 0.0:
                return True
            return (abs(a - b) <= TOL_EQ_ABS) or (abs(a - b) <= TOL_EQ_REL * max(abs(a), abs(b), 1.0))

        for name in ["Grid_Import", "Grid_Export", "Total_Load_AC"]:
            if name in df.columns and name in df_ref.columns:
                a = float(df[name].sum()); b = float(df_ref[name].sum())
                if not _close(a, b):
                    errors.append(f"Equivalence check failed (n_bidir=0): {name} differs "
                                  f"(V2H={a:.6f}, NoV2H={b:.6f}).")

    # ===== Ergebnis =====
    if errors:
        print("\n✖ MASS/FLUX CHECKS FAILED:")
        for e in errors:
            print("  - " + e)
        sys.exit(2)
    else:
        print("\n✔ All mass/flux checks passed.")
