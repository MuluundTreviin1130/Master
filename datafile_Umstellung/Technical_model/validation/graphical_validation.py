# Technical_model/energy_system/validation/visual_inspection.py
# -----------------------------------------------------------------------------
# Grafische Jahresprüfung der Energieflüsse (NoV2H oder V2H)
# - lädt Daten, macht Precompute
# - rechnet System (NoV2H/V2H)
# - baut stündliche Tabelle
# - erzeugt mehrere Plot-Figuren für eine visuelle Plausibilitätsprüfung
# -----------------------------------------------------------------------------

from __future__ import annotations
from typing import Dict, Any
import os
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

from Data.data import get_parameters, load_profiles
from Technical_model.energy_system.precompute.precompute import prepare_profiles
from Technical_model.energy_system.systems.PV_BESS_HP_EV import simulate_energy_system as run_ev
from Technical_model.energy_system.systems.PV_BESS_HP_V2H import simulate_energy_system_with_v2h as run_v2h
from Technical_model.validation_if_correct.diagnostics import print_basic_diagnostics, plot_week_overlays

# ---------------------------------------------------------e--------------------
# Helper: hourly table (identisch zur Logik im Proof, minimal gehalten)
# -----------------------------------------------------------------------------
def _hourly_table(res: dict, profiles: dict, params: dict, use_v2h: bool) -> pd.DataFrame:
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
        # 2D → über EVs summieren
        if agg == "mean":
            arr = np.nanmean(arr, axis=1)
        else:
            arr = np.nansum(arr, axis=1)
        return arr if arr.size == N else np.resize(arr, N).astype(float, copy=False)

    base_load = (
        _to1d(profiles.get("load")) +
        _to1d(profiles.get("hp_elec_heat")) +
        _to1d(profiles.get("hp_elec_cool")) +
        _to1d(profiles.get("hotwater_HH_kWh"))
    )
    pv_ac = _to1d(res.get("pv_generation"))

    ev_charge_ac    = _to1d(res.get("ev_charge_ac"))
    ev_discharge_ac = _to1d(res.get("ev_discharged"), agg="sum") if use_v2h else np.zeros(N)

    ev_from_pv   = _to1d(res.get("ev_charge_from_pv_ac"))
    ev_from_bess = _to1d(res.get("ev_charge_from_bess_ac"))
    ev_from_ec   = _to1d(res.get("ev_charge_from_ec_ac"))
    ev_from_grid = _to1d(res.get("ev_charge_from_grid_ac"))

    bess_charge    = _to1d(res.get("bess_charged"))
    bess_discharge = _to1d(res.get("bess_discharged"))
    grid_import    = _to1d(res.get("grid_import"))
    grid_export    = _to1d(res.get("grid_export"))
    ec_imp_pv      = _to1d(res.get("ec_import_from_pv"))
    ec_imp_ev      = _to1d(res.get("ec_import_from_ev"))
    ec_exp_pv      = _to1d(res.get("ec_export_from_pv"))

    bess_to_ev = _to1d(res.get("bess_to_ev_ac")) if use_v2h or ("bess_to_ev_ac" in res) else np.zeros(N)
    bess_to_load = np.maximum(bess_discharge - bess_to_ev, 0.0)

    total_load_ac = base_load + ev_charge_ac - ev_discharge_ac
    covered_ac = (
        np.minimum(pv_ac, base_load) +
        ev_from_pv +
        bess_to_load +
        bess_to_ev +
        ec_imp_pv + ec_imp_ev +
        grid_import
    )
    mb_load_res = total_load_ac - covered_ac

    pv_used_ac = (
        np.minimum(pv_ac, base_load) +
        bess_charge + ev_from_pv + grid_export + ec_exp_pv
    )
    mb_pv_res = pv_ac - pv_used_ac

    df = pd.DataFrame({
        "Timestamp": ts,
        "Base_Load": base_load,
        "PV_Production": pv_ac,
        "Grid_Import": grid_import,
        "Grid_Export": grid_export,
        "BESS_Charge": bess_charge,
        "BESS_Discharge": bess_discharge,
        "BESS_to_Load": bess_to_load,
        "BESS_to_EV": bess_to_ev,
        "EC_Import_from_PV": ec_imp_pv,
        "EC_Import_from_EV": ec_imp_ev,
        "EC_Export_from_PV": ec_exp_pv,
        "EV_Charge_AC": ev_charge_ac,
        "EV_Charge_from_PV_AC": ev_from_pv,
        "EV_Charge_from_BESS_AC": ev_from_bess,
        "EV_Charge_from_EC_AC": ev_from_ec,
        "EV_Charge_from_Grid_AC": ev_from_grid,
        "EV_Discharge_AC": ev_discharge_ac,
        "Total_Load_AC": total_load_ac,
        "Covered_AC": covered_ac,
        "MassBalance_Load_residual": mb_load_res,
        "MassBalance_PV_residual": mb_pv_res,
        "BESS_SOC": _to1d(res.get("bess_soc")),
        "EV_SOC_DC_mean": _to1d(res.get("ev_soc"), agg="mean"),
    }).set_index("Timestamp")
    return df

# -----------------------------------------------------------------------------
# Plots
# -----------------------------------------------------------------------------
def _ensure_outdir(path="results/plots"):
    os.makedirs(path, exist_ok=True)
    return path

def plot_year_timeseries(df: pd.DataFrame, outdir: str):
    # 1) PV vs BaseLoad vs Grid
    plt.figure(figsize=(13, 4))
    df[["Base_Load", "PV_Production"]].plot(ax=plt.gca(), linewidth=0.7)
    df[["Grid_Import", "Grid_Export"]].plot(ax=plt.gca(), linewidth=0.7, alpha=0.6)
    plt.title("PV vs. Base Load vs. Grid (year)")
    plt.ylabel("kWh/h")
    plt.tight_layout()
    plt.savefig(os.path.join(outdir, "01_pv_load_grid_year.png"), dpi=150)

    # 2) Heat/Cool/Hotwater – falls in Base_Load enthalten, hier separat aus Profiles besser;
    #    für schnelle Sichtbarkeit: gleitender Tagesmittelwert von Base_Load
    plt.figure(figsize=(13, 4))
    df["Base_Load"].rolling(24, min_periods=1).mean().plot(linewidth=0.9)
    plt.title("Base Load (24h rolling mean)")
    plt.ylabel("kWh/h")
    plt.tight_layout()
    plt.savefig(os.path.join(outdir, "02_baseload_rolling_year.png"), dpi=150)

    # 3) BESS: Charge/Discharge + SOC
    fig, ax1 = plt.subplots(figsize=(13, 4))
    ax1.plot(df.index, df["BESS_Charge"], label="BESS Charge", linewidth=0.6)
    ax1.plot(df.index, df["BESS_Discharge"], label="BESS Discharge", linewidth=0.6)
    ax1.set_ylabel("kWh/h")
    ax2 = ax1.twinx()
    ax2.plot(df.index, df["BESS_SOC"], label="BESS SOC", linewidth=0.8, alpha=0.7)
    ax2.set_ylabel("kWh")
    ax1.set_title("BESS flows & SOC (year)")
    ax1.legend(loc="upper left")
    ax2.legend(loc="upper right")
    fig.tight_layout()
    fig.savefig(os.path.join(outdir, "03_bess_year.png"), dpi=150)

    # 4) EV: Charge (sources) + Discharge + mean SOC
    fig, ax1 = plt.subplots(figsize=(13, 4))
    for col in ["EV_Charge_from_PV_AC", "EV_Charge_from_BESS_AC", "EV_Charge_from_EC_AC", "EV_Charge_from_Grid_AC"]:
        if col in df:
            ax1.plot(df.index, df[col], label=col, linewidth=0.6)
    if "EV_Discharge_AC" in df.columns:
        ax1.plot(df.index, df["EV_Discharge_AC"], label="EV_Discharge_AC", linewidth=0.6, alpha=0.7)
    ax1.set_ylabel("kWh/h")
    ax2 = ax1.twinx()
    if "EV_SOC_DC_mean" in df.columns:
        ax2.plot(df.index, df["EV_SOC_DC_mean"], label="EV_SOC_DC_mean", linewidth=0.8, alpha=0.7)
        ax2.set_ylabel("kWh (mean over EVs)")
    ax1.set_title("EV flows & mean SOC (year)")
    ax1.legend(loc="upper left")
    ax2.legend(loc="upper right")
    fig.tight_layout()
    fig.savefig(os.path.join(outdir, "04_ev_year.png"), dpi=150)

    # 5) Gestapelter Energiefluss (vereinfachte Sicht)
    stack = pd.DataFrame(index=df.index)
    stack["Load_covered_by_PV_direct"] = np.minimum(df["PV_Production"], df["Base_Load"])
    stack["BESS_to_Load"] = df["BESS_to_Load"]
    stack["BESS_to_EV"] = df["BESS_to_EV"]
    stack["EV_from_PV"] = df["EV_Charge_from_PV_AC"]
    stack["EV_from_BESS"] = df["EV_Charge_from_BESS_AC"]
    stack["EC_import_total"] = df["EC_Import_from_PV"] + df["EC_Import_from_EV"]
    stack["Grid_Import"] = df["Grid_Import"]
    plt.figure(figsize=(13, 4))
    stack.clip(lower=0).rolling(24, min_periods=1).mean().plot.area(ax=plt.gca(), linewidth=0)
    plt.title("Covered AC (24h rolling area, simplified sources)")
    plt.ylabel("kWh/h")
    plt.tight_layout()
    plt.savefig(os.path.join(outdir, "05_area_covered_year.png"), dpi=150)

    # 6) Histogramme der Residuen
    plt.figure(figsize=(10, 4))
    df["MassBalance_Load_residual"].hist(bins=100, alpha=0.7)
    plt.title("Histogram: MassBalance Load residual")
    plt.tight_layout()
    plt.savefig(os.path.join(outdir, "06_hist_mb_load.png"), dpi=150)

    plt.figure(figsize=(10, 4))
    df["MassBalance_PV_residual"].hist(bins=100, alpha=0.7)
    plt.title("Histogram: MassBalance PV residual")
    plt.tight_layout()
    plt.savefig(os.path.join(outdir, "07_hist_mb_pv.png"), dpi=150)


def plot_week_zoom(df: pd.DataFrame, outdir: str, start_day: str | None = None):
    """Zoom auf eine Woche (Startdatum als 'YYYY-MM-DD')."""
    if start_day is None:
        start = df.index.min().normalize()
    else:
        start = pd.to_datetime(start_day)
    end = start + pd.Timedelta(days=7)
    w = df.loc[(df.index >= start) & (df.index < end)]

    def _line(columns, title, fname):
        plt.figure(figsize=(13, 4))
        w[columns].plot(ax=plt.gca(), linewidth=1.0)
        plt.title(title + f"  [{start.date()} … {end.date()}]")
        plt.ylabel("kWh/h")
        plt.tight_layout()
        plt.savefig(os.path.join(outdir, fname), dpi=150)

    _line(["Base_Load", "PV_Production", "Grid_Import", "Grid_Export"],
          "Week: PV vs BaseLoad vs Grid", "w1_pv_load_grid.png")

    cols_ev = [c for c in ["EV_Charge_from_PV_AC","EV_Charge_from_BESS_AC","EV_Charge_from_EC_AC","EV_Charge_from_Grid_AC","EV_Discharge_AC"] if c in w]
    if cols_ev:
        _line(cols_ev, "Week: EV flows", "w2_ev.png")

    _line(["BESS_Charge","BESS_Discharge"], "Week: BESS flows", "w3_bess_flows.png")

    plt.figure(figsize=(13, 3))
    if "BESS_SOC" in w.columns:
        w["BESS_SOC"].plot(linewidth=1.0)
        plt.title(f"Week: BESS SOC [{start.date()} … {end.date()}]")
        plt.ylabel("kWh")
        plt.tight_layout()
        plt.savefig(os.path.join(outdir, "w4_bess_soc.png"), dpi=150)


# -----------------------------------------------------------------------------
# Main – zentral editierbare Settings (wie im Proof)
# -----------------------------------------------------------------------------
if __name__ == "__main__":
    # ===== Settings =====
    LOCATION = "Vienna"
    USE_V2H  = True         # True → V2H, False → NoV2H
    PV_KWP   = 1000.0
    BESS_KWH = 1000.0

    EC_SHARE_IMPORT  = 1.0
    EC_EXPORT_SHARE  = 1.0

    RNG_SEED = 42
    np.random.seed(RNG_SEED)

    # ===== Daten laden / Precompute =====
    base_params: Dict[str, Any] = get_parameters(LOCATION)
    base_params["location"] = LOCATION
    profiles_raw = load_profiles(LOCATION)
    profiles = prepare_profiles(base_params, profiles_raw, do_hp_electricity=True, do_coeffs=False)

    # params zusammenstellen (gleich wie Proof)
    params: Dict[str, Any] = dict(base_params)
    params["pv_size"] = float(PV_KWP)
    params["battery_capacity_kWh"] = float(BESS_KWH)
    params["EC"] = dict(params.get("EC", {}))
    params["EC"]["share"] = float(EC_SHARE_IMPORT)
    params["EC"]["export_share"] = float(EC_EXPORT_SHARE)
    params["rng_seed"] = RNG_SEED

    # ===== Simulation =====
    sim = run_v2h if USE_V2H else run_ev
    res = sim(params, profiles, pv_size=float(PV_KWP))
    df = _hourly_table(res, profiles, params, use_v2h=USE_V2H)

    # ===== Plots =====
    outdir = _ensure_outdir("results/plots")
    plot_year_timeseries(df, outdir)
    plot_week_zoom(df, outdir, start_day=None)   # ggf. "2023-07-01" o.ä.

    print(f"✅ Plots geschrieben nach: {outdir}")

    # === GANZ AM ENDE: Diagnostics & Overlay ===
    print_basic_diagnostics(df, params)
    plot_week_overlays(df, profiles, params, week_start="2023-01-01", days=7)
    plt.show()
