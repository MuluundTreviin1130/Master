# Technical_model/validation/deep_diagnostics_multi.py
# ====================================================
from __future__ import annotations
import os, math, numpy as np, pandas as pd
import matplotlib.pyplot as plt

plt.rcParams.update({"figure.dpi": 110})

# ---- Projektabhängige Importe (wie in deinem bestehenden deep_diagnostics.py) ----
from Data.data import get_parameters, load_profiles
from Technical_model.energy_system.precompute.precompute import prepare_profiles
from Technical_model.energy_system.systems.PV_BESS_HP_EV import simulate_energy_system as run_ev
from Technical_model.energy_system.systems.PV_BESS_HP_V2H import simulate_energy_system_with_v2h as run_v2h

# ------------ kleine Helfer ------------
def ensure_dir(p): os.makedirs(p, exist_ok=True); return p
def eff_split(roundtrip: float):
    eta = math.sqrt(max(1e-6, min(1.0, float(roundtrip))))
    return eta, eta

def to1d(N, arr, agg="sum"):
    a = np.asarray(arr, dtype=float)
    if a.ndim == 1: return a
    if a.ndim == 2:
        return (np.nanmean(a, axis=1) if agg=="mean" else np.nansum(a, axis=1))
    return np.zeros(N)

def hourly_table(res, profiles, params, use_v2h: bool):
    ts = pd.to_datetime(res.get("timestamps", pd.date_range("2023-01-01", periods=len(profiles["load"]), freq="H")))
    N  = len(ts)
    base = to1d(N, profiles["load"]) \
         + to1d(N, profiles.get("hp_elec_heat", 0)) \
         + to1d(N, profiles.get("hp_elec_cool", 0)) \
         + to1d(N, profiles.get("hotwater_HH_kWh", 0))
    pv   = to1d(N, res.get("pv_generation", 0))
    ev_ch_ac  = to1d(N, res.get("ev_charge_ac", 0))
    ev_dis_ac = to1d(N, res.get("ev_discharged", 0)) if use_v2h else np.zeros(N)
    df = pd.DataFrame(index=ts)
    df["Base_Load"] = base; df["PV_Production"] = pv
    df["Grid_Import"]  = to1d(N, res.get("grid_import", 0))
    df["Grid_Export"]  = to1d(N, res.get("grid_export", 0))
    df["BESS_Charge"]  = to1d(N, res.get("bess_charged", 0))
    df["BESS_Discharge"] = to1d(N, res.get("bess_discharged", 0))
    df["BESS_SOC_raw"] = to1d(N, res.get("bess_soc", 0))
    df["EV_Charge_AC"] = ev_ch_ac; df["EV_Discharge_AC"] = ev_dis_ac
    df["EV_Charge_from_PV_AC"]   = to1d(N, res.get("ev_charge_from_pv_ac", 0))
    df["EV_Charge_from_BESS_AC"] = to1d(N, res.get("ev_charge_from_bess_ac", 0))
    df["EV_Charge_from_EC_AC"]   = to1d(N, res.get("ev_charge_from_ec_ac", 0))
    df["EV_Charge_from_Grid_AC"] = to1d(N, res.get("ev_charge_from_grid_ac", 0))
    df["EC_Import_from_PV"] = to1d(N, res.get("ec_import_from_pv", 0))
    df["EC_Import_from_EV"] = to1d(N, res.get("ec_import_from_ev", 0))
    df["EC_Export_from_PV"] = to1d(N, res.get("ec_export_from_pv", 0))
    # EV mean SoC (nur für Diagnose/Plot)
    ev_soc_raw = res.get("ev_soc", None)
    df["EV_SOC_DC_mean_raw"] = to1d(N, ev_soc_raw, agg="mean") if ev_soc_raw is not None else 0.0
    # Total-AC-Last (für Bilanz-Checks)
    df["Total_Load_AC"] = df["Base_Load"] + df["EV_Charge_AC"] - df["EV_Discharge_AC"]
    # vereinfachte Bilanz-Restterme
    covered = (np.minimum(df["PV_Production"], df["Base_Load"])
               + df["BESS_Discharge"]
               + df["EC_Import_from_PV"] + df["EC_Import_from_EV"]
               + df["Grid_Import"])
    df["MassBalance_Load_residual"] = df["Total_Load_AC"] - covered
    pv_used = (np.minimum(df["PV_Production"], df["Base_Load"])
               + df["BESS_Charge"] + df["EV_Charge_from_PV_AC"]
               + df["Grid_Export"] + df["EC_Export_from_PV"])
    df["MassBalance_PV_residual"] = df["PV_Production"] - pv_used
    return df

def normalize_soc(df, params):
    out = df.copy()
    cap_bess = float(params.get("battery_capacity_kWh", params.get("BESS", {}).get("capacity_kWh", 0.0)))
    cap_ev   = float(params.get("EV", {}).get("capacity_kWh", 0.0))
    out["BESS_SOC_kWh"] = out["BESS_SOC_raw"]*cap_bess if cap_bess>0 and out["BESS_SOC_raw"].max()<=2 else out["BESS_SOC_raw"]
    if "EV_SOC_DC_mean_raw" in out:
        out["EV_SOC_DC_mean_kWh"] = out["EV_SOC_DC_mean_raw"]*cap_ev if cap_ev>0 and out["EV_SOC_DC_mean_raw"].max()<=2 else out["EV_SOC_DC_mean_raw"]
    return out

def bess_soc_reconstruction(df, params):
    out = df.copy()
    if "BESS_SOC_kWh" not in out: return out
    cap   = float(params.get("battery_capacity_kWh", params.get("BESS", {}).get("capacity_kWh", 0.0)))
    rt    = float(params.get("BESS", {}).get("efficiency_roundtrip", 0.95))
    eta_c, eta_d = eff_split(rt)
    sd_h  = float(params.get("BESS", {}).get("self_discharge_per_hour", 0.0))
    soc   = out["BESS_SOC_kWh"].to_numpy(float)
    ch    = out["BESS_Charge"].to_numpy(float)
    dis   = out["BESS_Discharge"].to_numpy(float)
    soc_next = np.empty_like(soc)
    soc_next[:-1] = soc[:-1] + ch[:-1]*eta_c - dis[:-1]/max(1e-9, eta_d) - sd_h*soc[:-1]
    soc_next[-1]  = np.nan
    out["BESS_SOC_model_next_kWh"] = soc_next
    out["BESS_SOC_step_residual_kWh"] = out["BESS_SOC_kWh"] - soc_next
    out["BESS_SOC_underflow_kWh"] = np.minimum(0.0, soc)
    out["BESS_SOC_overflow_kWh"]  = np.maximum(0.0, soc - cap)
    return out

def bess_power_utilization(df, bess_power_kw: float):
    pv_surplus   = (df["PV_Production"] - df["Base_Load"]).clip(lower=0)
    load_deficit = (df["Base_Load"] - df["PV_Production"]).clip(lower=0)
    charge_max   = bess_power_kw * int((pv_surplus>1e-9).sum())
    discharge_max= bess_power_kw * int((load_deficit>1e-9).sum())
    return dict(
        hours_pv_surplus=int((pv_surplus>1e-9).sum()),
        hours_load_deficit=int((load_deficit>1e-9).sum()),
        bess_charge_kWh=float(df["BESS_Charge"].sum()),
        bess_discharge_kWh=float(df["BESS_Discharge"].sum()),
        max_charge_possible_kWh=float(charge_max),
        max_discharge_possible_kWh=float(discharge_max),
        charge_util_vs_power=float(df["BESS_Charge"].sum())/max(1e-9,charge_max),
        discharge_util_vs_power=float(df["BESS_Discharge"].sum())/max(1e-9,discharge_max),
        share_of_pv_surplus_stored=float(df["BESS_Charge"].sum())/max(1e-9,float(pv_surplus.sum()))
    )

def plots(df, outdir):
    ensure_dir(outdir)
    # 1) PV vs Load vs Grid
    plt.figure(figsize=(13,4))
    df[["Base_Load","PV_Production","Grid_Import","Grid_Export"]].plot(ax=plt.gca(), lw=0.7, alpha=0.9)
    plt.title("PV vs. Base Load vs. Grid (year)"); plt.ylabel("kWh/h"); plt.tight_layout()
    plt.savefig(os.path.join(outdir,"01_pv_load_grid_year.png")); plt.close()
    # 2) BESS year
    fig, ax1 = plt.subplots(figsize=(13,4))
    ax1.plot(df.index, df["BESS_Charge"], lw=0.6, label="BESS Charge")
    ax1.plot(df.index, df["BESS_Discharge"], lw=0.6, label="BESS Discharge")
    ax1.set_ylabel("kWh/h"); ax2 = ax1.twinx()
    if "BESS_SOC_kWh" in df:
        ax2.plot(df.index, df["BESS_SOC_kWh"], lw=0.8, alpha=0.7, label="BESS SOC (kWh)"); ax2.set_ylabel("kWh")
    ax1.legend(loc="upper left"); ax1.set_title("BESS flows & SOC (year)")
    if len(ax2.lines): ax2.legend(loc="upper right")
    fig.tight_layout(); fig.savefig(os.path.join(outdir,"03_bess_year.png")); plt.close(fig)
    # 3) EV year
    fig, ax1 = plt.subplots(figsize=(13,4))
    cols = ["EV_Charge_from_PV_AC","EV_Charge_from_BESS_AC","EV_Charge_from_EC_AC","EV_Charge_from_Grid_AC","EV_Discharge_AC"]
    for c in cols:
        if c in df: ax1.plot(df.index, df[c], lw=0.6, label=c)
    ax1.set_ylabel("kWh/h"); ax1.legend(loc="upper left")
    ax2 = ax1.twinx()
    if "EV_SOC_DC_mean_kWh" in df:
        ax2.plot(df.index, df["EV_SOC_DC_mean_kWh"], lw=0.8, alpha=0.7, label="EV SOC mean (kWh)")
        ax2.legend(loc="upper right"); ax2.set_ylabel("kWh (mean over EVs)")
    ax1.set_title("EV flows & mean SOC (year)"); fig.tight_layout()
    fig.savefig(os.path.join(outdir,"04_ev_year.png")); plt.close(fig)
    # 4) Monatsbalken BESS
    m = df.resample("ME").sum(numeric_only=True)
    plt.figure(figsize=(10,4))
    m[["BESS_Charge","BESS_Discharge"]].plot(kind="bar", width=0.8, ax=plt.gca())
    plt.title("BESS: Charge / Discharge per month"); plt.ylabel("kWh"); plt.tight_layout()
    plt.savefig(os.path.join(outdir,"06_bess_month_bar.png")); plt.close()

def run_case(location, use_v2h, pv_kwp, bess_kwh, rng_seed=42):
    base_params = get_parameters(location); base_params["location"]=location
    profiles = prepare_profiles(base_params, load_profiles(location), do_hp_electricity=True, do_coeffs=False)
    params = dict(base_params); params["pv_size"]=float(pv_kwp); params["battery_capacity_kWh"]=float(bess_kwh); params["rng_seed"]=rng_seed
    bess = dict(params.get("BESS", {})); bess.setdefault("capacity_kWh", float(bess_kwh)); bess.setdefault("power_kW", 5.0); bess.setdefault("efficiency_roundtrip", 0.95)
    params["BESS"] = bess
    ec = dict(params.get("EC", {})); ec.setdefault("share", 1.0); ec.setdefault("export_share", 1.0); params["EC"]=ec
    sim = run_v2h if use_v2h else run_ev
    res = sim(params, profiles, pv_size=float(pv_kwp))
    df = hourly_table(res, profiles, params, use_v2h); df = normalize_soc(df, params); df = bess_soc_reconstruction(df, params)
    # Ausgabe
    tag = f"PV{int(pv_kwp)}_BESS{int(bess_kwh)}"
    outdir = ensure_dir(os.path.join("results","diagnostics_multi", tag))
    # Summaries
    print(f"\n=== SETTINGS [{tag}] ===")
    print(f"Location: {location}  Variant: {'V2H' if use_v2h else 'NoV2H'}  PV/BESS: {pv_kwp} / {bess_kwh}")
    print(f"Total Load AC: {df['Total_Load_AC'].sum():.3f} kWh  | PV: {df['PV_Production'].sum():.3f} kWh")
    print(f"Grid Import: {df['Grid_Import'].sum():.3f} kWh  | Grid Export: {df['Grid_Export'].sum():.3f} kWh")
    print(f"BESS Charge/Disch.: {df['BESS_Charge'].sum():.3f} / {df['BESS_Discharge'].sum():.3f} kWh")
    # BESS-Power-Nutzung
    util = bess_power_utilization(df, params["BESS"]["power_kW"])
    print("[BESS power-limiting]")
    for k,v in util.items(): print(f"  {k}: {v:.6f}" if isinstance(v,float) else f"  {k}: {v}")
    # Plots + CSV
    plots(df, outdir)
    df_out = df.copy()
    df_out["BESS_SOC_capacity_kWh"] = float(params["BESS"]["capacity_kWh"])
    df_out["BESS_power_kW"] = float(params["BESS"]["power_kW"])
    csv_path = os.path.join(outdir, "hourly_dump.csv"); df_out.to_csv(csv_path, index=True)
    print(f"✅ Plots & CSV gespeichert in: {outdir}")

if __name__ == "__main__":
    LOCATION = "Vienna"
    USE_V2H  = True   # bei Bedarf True
    SCENARIOS = [(500,100),(1000,500),(5000,4000)]  # (PV_kWp, BESS_kWh)
    for pv, bess in SCENARIOS:
        run_case(LOCATION, USE_V2H, pv_kwp=pv, bess_kwh=bess)
