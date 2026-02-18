# Technical_model/energy_system/validation/diagnostics.py
from __future__ import annotations
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

def print_basic_diagnostics(hourly: pd.DataFrame, params: dict) -> None:
    """Kurzer Text-Check zu BESS-Limits, PV-Überschuss, EC-Strömen, EV-Netzladung."""
    power_kW = float(params["BESS"]["power_kW"])
    bess_in  = hourly.get("BESS_Charge", pd.Series(0.0)).to_numpy(dtype=float)
    bess_out = hourly.get("BESS_Discharge", pd.Series(0.0)).to_numpy(dtype=float)
    pv_ac    = hourly.get("PV_Production", pd.Series(0.0)).to_numpy(dtype=float)

    post_bess_surplus = pv_ac - bess_in  # grob: PV nach BESS-Ladung (vereinfachte Sicht)

    hrs_at_chg_lim   = int(np.sum(np.isclose(bess_in,  power_kW, atol=1e-6)))
    hrs_at_dis_lim   = int(np.sum(np.isclose(bess_out, power_kW, atol=1e-6)))
    hrs_with_surplus = int(np.sum(post_bess_surplus > 1e-6))

    ec_imp = float(hourly.get("EC_Import_from_PV", pd.Series(0.0)).sum()) \
           + float(hourly.get("EC_Import_from_EV", pd.Series(0.0)).sum())
    ec_exp = float(hourly.get("EC_Export_from_PV", pd.Series(0.0)).sum())

    ev_grid = float(hourly.get("EV_Charge_from_Grid_AC", pd.Series(0.0)).sum())
    ev_ec   = float(hourly.get("EV_Charge_from_EC_AC",   pd.Series(0.0)).sum())

    print("\n[Diagnostics]")
    print(f"BESS power_kW                : {power_kW:.1f}")
    print(f"Stunden am Ladelimit         : {hrs_at_chg_lim}")
    print(f"Stunden am Entladelimit      : {hrs_at_dis_lim}")
    print(f"Stunden mit PV-Überschuss n. BESS: {hrs_with_surplus}")
    print(f"EC Import / Export (Summe)   : {ec_imp:.1f} / {ec_exp:.1f} kWh")
    print(f"EV-Ladung aus Grid / EC      : {ev_grid:.1f} / {ev_ec:.1f} kWh")

def plot_week_overlays(hourly: pd.DataFrame,
                       profiles: dict,
                       params: dict,
                       week_start: str | pd.Timestamp,
                       days: int = 7) -> None:
    """
    Zusatzplot: zeigt in einer Woche
    - EV Availability (Mittelwert über EVs, falls Profil vorhanden)
    - min_SOC * EV-Kapazität (als kWh; mittlerer Wert, wenn min_SOC als Anteil vorliegt)
    - BESS Power Limits (horizontal, in kWh/h ≙ kW)
    """
    idx = hourly.index if isinstance(hourly.index, pd.DatetimeIndex) else pd.to_datetime(hourly["Timestamp"])
    week_start = pd.to_datetime(week_start)
    week_end = week_start + pd.Timedelta(days=days)
    sel = (idx >= week_start) & (idx < week_end)

    fig, ax = plt.subplots(figsize=(12, 3))
    ax.set_title(f"Overlays (Week {week_start.date()} … {week_end.date()})")
    ax.set_ylabel("kWh / h")

    # BESS Power-Limits (als horizontale Linien)
    p = float(params["BESS"]["power_kW"])
    ax.hlines(y=p, xmin=idx[sel][0], xmax=idx[sel][-1], linestyles="--", label="BESS charge/discharge limit")

    # EV-Availability (falls vorhanden) – skaliert als 0..1 und sekundäre Achse
    avail = profiles.get("availability_profile", None)
    if avail is not None:
        avail = np.asarray(avail, dtype=float)
        ax2 = ax.twinx()
        ax2.plot(idx[sel], avail[sel], alpha=0.6, label="EV availability (prob)")
        ax2.set_ylim(0, 1)
        ax2.set_ylabel("prob")

    # min_SOC (falls vorhanden) auf kWh gemittelt (über EVs)
    min_soc = profiles.get("min_SOC", None)
    cap = float(params.get("EV", {}).get("capacity_kWh", 0.0))
    if min_soc is not None and cap > 0:
        min_soc = np.asarray(min_soc, dtype=float)
        ax.plot(idx[sel], min_soc[sel]*cap, alpha=0.6, label="EV min_SOC * capacity (kWh)")

    # hübsche Legenden
    ax.legend(loc="upper left")
    if "ax2" in locals():
        ax2.legend(loc="upper right")
    fig.tight_layout()
