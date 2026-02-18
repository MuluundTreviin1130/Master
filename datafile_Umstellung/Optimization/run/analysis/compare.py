# Optimization/run/analysis/compare_ev_v2h_basic.py

from __future__ import annotations

from pathlib import Path
import json
from typing import Dict, Any

import numpy as np
import pandas as pd

# Alles über das zentrale Settings-File
from Optimization.framework.Settings.settings import get_settings
# gleiche Logik für runs_root wie im Orchestrator
from Optimization.framework.Orchestrator.optimize import _resolve_runs_root

# Für die Jahreslast / Lifetime-Last (optional, für Autarkie)
from system_id_Umstellung.Data.data import get_parameters, load_profiles
from system_id_Umstellung.Technical_model.energy_system.precompute.precompute import prepare_profiles


# ---------------------------------------------------------------------------
# Konfiguration – NUR Dinge, die nicht im Settings-File stehen
# ---------------------------------------------------------------------------

# Folder-Namen analog zu deinen Optimierungs-Runs
EV_MODE = "EV"
V2H_MODE = "V2H"

# Name der Pareto-CSV, die csv_exports.py schreibt:
# → HIER ggf. anpassen: z.B. "pareto_points.csv" oder "pareto_front.csv"
PARETO_CSV_NAME = "pareto_points.csv"

# Spaltennamen im Pareto-CSV – bitte mit deiner CSV prüfen
NPC_COL = "npc_eur"
PEF_COL = "pef_pt"
GRID_IMPORT_COL = "grid_import_kwh"   # lebensdauer- oder jahresweise import


# ---------------------------------------------------------------------------
# Hilfsfunktionen
# ---------------------------------------------------------------------------

def _load_year_and_lifetime_load_kwh(settings) -> Dict[str, float]:
    """
    Repliziert die Logik aus dem Surrogate-Engine-Init:
    - Parameter & Profile laden
    - prepare_profiles() anwenden
    - Jahreslast (inkl. N_HH, HP etc.) summieren
    - Lifetime aus params["lifetime"]
    """
    eng = settings.engine

    # Parameter + Profile analog zur SurrogateEngine
    params = get_parameters(eng.location)
    params["location"] = eng.location

    # EC-Shares aus Settings
    if "EC" not in params:
        params["EC"] = {}
    params["EC"]["share"] = float(eng.ec_share_import)
    params["EC"]["export_share"] = float(eng.ec_share_export)

    # Community-Zähler
    params["N_HH"] = int(eng.N_HH)
    params["N_EV"] = int(eng.N_EV_total)
    params["N_EV_bidirectional"] = int(eng.N_EV_bidirectional)

    params.setdefault("EV", {})
    params["EV"]["N_EV_total"] = int(eng.N_EV_total)
    params["EV"]["N_EV_bidirectional"] = int(eng.N_EV_bidirectional)

    lifetime = int(params.get("lifetime", 1))

    profiles_raw = load_profiles(eng.location)
    profiles = prepare_profiles(params, profiles_raw,
                                do_hp_electricity=True,
                                do_coeffs=False)

    load_arr = np.asarray(profiles.get("load", []), dtype=float)
    year_load_kwh = float(np.sum(load_arr)) if load_arr.size else 0.0
    lifetime_load_kwh = year_load_kwh * lifetime

    return {
        "year_load_kwh": year_load_kwh,
        "lifetime_load_kwh": lifetime_load_kwh,
        "lifetime": lifetime,
    }


def _get_runs_root_and_engine(settings) -> tuple[Path, str, str]:
    """Bestimmt runs_root, location und engine-name konsistent zum Orchestrator."""
    reporting = getattr(settings, "reporting", None)
    output_root = getattr(reporting, "output_root", None)

    runs_root = _resolve_runs_root(output_root)
    eng_cfg = getattr(settings, "engine", None)
    eng_name = str(getattr(eng_cfg, "name", "surrogate")).lower().strip() or "surrogate"
    location = str(getattr(eng_cfg, "location", "UnknownLocation"))

    return runs_root, eng_name, location


def _load_latest_pareto(runs_root: Path, location: str,
                        mode: str, engine_name: str) -> pd.DataFrame:
    """
    Holt den letzten Run über _LATEST_RUN.json und lädt das Pareto-CSV.
    """
    eng_root = (runs_root / location / mode / engine_name).resolve()
    latest_path = eng_root / "_LATEST_RUN.json"
    if not latest_path.exists():
        raise FileNotFoundError(f"_LATEST_RUN.json nicht gefunden: {latest_path}")

    latest = json.loads(latest_path.read_text(encoding="utf-8"))
    run_dir_str = latest.get("path")
    run_id = latest.get("run_id")

    if run_dir_str:
        run_dir = Path(run_dir_str).resolve()
    else:
        run_dir = (eng_root / run_id).resolve()

    if not run_dir.exists():
        raise FileNotFoundError(f"Run-Verzeichnis nicht gefunden: {run_dir}")

    # Standard: CSV liegt in run_dir / analysis / PARETO_CSV_NAME
    csv_path = run_dir / "analysis" / PARETO_CSV_NAME
    if not csv_path.exists():
        # Fallback: direkt im Run-Verzeichnis
        alt_path = run_dir / PARETO_CSV_NAME
        if not alt_path.exists():
            raise FileNotFoundError(
                f"Pareto-CSV nicht gefunden unter {csv_path} oder {alt_path}. "
                f"Bitte PARETO_CSV_NAME oben anpassen."
            )
        csv_path = alt_path

    df = pd.read_csv(csv_path)
    return df


def _add_autarky(df: pd.DataFrame,
                 lifetime_load_kwh: float,
                 grid_import_col: str,
                 new_col: str = "autarky") -> pd.DataFrame:
    """
    Autarkie = 1 - E_import_L / E_load_L,
    wobei E_load_L = lifetime_load_kwh.
    Wenn das CSV jährliche Importe enthält, ist lifetime_load_kwh
    einfach die Jahreslast → gleiche Formel.
    """
    if grid_import_col not in df.columns:
        raise KeyError(f"Spalte '{grid_import_col}' nicht im Pareto-CSV.")

    df = df.copy()
    denom = float(lifetime_load_kwh) if lifetime_load_kwh > 0 else np.nan
    df[new_col] = 1.0 - df[grid_import_col] / denom
    return df


def _summarize_basic(df: pd.DataFrame) -> Dict[str, Any]:
    """Min NPC, min PEF, max Autarkie."""
    return {
        "npc_min": float(df[NPC_COL].min()),
        "pef_min": float(df[PEF_COL].min()),
        "autarky_max": float(df["autarky"].max()),
    }


# ---------------------------------------------------------------------------
# Hauptlogik
# ---------------------------------------------------------------------------

def main() -> None:
    # 1) Settings laden
    s = get_settings()

    # 2) runs_root, Engine-Name, Location aus Settings ableiten
    runs_root, eng_name, location = _get_runs_root_and_engine(s)

    print(f"[compare] runs_root = {runs_root}")
    print(f"[compare] location  = {location}")
    print(f"[compare] engine    = {eng_name}")

    # 3) Jahres- und Lifetime-Last berechnen (für Autarkie)
    load_info = _load_year_and_lifetime_load_kwh(s)
    lifetime_load_kwh = load_info["lifetime_load_kwh"]
    print(f"[compare] lifetime load = {lifetime_load_kwh:.1f} kWh")

    # 4) Pareto-Daten EV & V2H laden
    df_ev = _load_latest_pareto(runs_root, location, EV_MODE, eng_name)
    df_v2h = _load_latest_pareto(runs_root, location, V2H_MODE, eng_name)

    # 5) Autarkie-Spalte ergänzen
    df_ev = _add_autarky(df_ev, lifetime_load_kwh, GRID_IMPORT_COL)
    df_v2h = _add_autarky(df_v2h, lifetime_load_kwh, GRID_IMPORT_COL)

    # 6) Basis-Kennzahlen
    ev_sum = _summarize_basic(df_ev)
    v2h_sum = _summarize_basic(df_v2h)

    # 7) Differenzen berechnen
    npc_red_abs = ev_sum["npc_min"] - v2h_sum["npc_min"]
    npc_red_rel = npc_red_abs / ev_sum["npc_min"] if ev_sum["npc_min"] else np.nan

    pef_red_abs = ev_sum["pef_min"] - v2h_sum["pef_min"]
    pef_red_rel = pef_red_abs / ev_sum["pef_min"] if ev_sum["pef_min"] else np.nan

    aut_inc_abs = v2h_sum["autarky_max"] - ev_sum["autarky_max"]

    print("\n[compare] --- EV ---")
    print(f"  NPC_min      : {ev_sum['npc_min']:.2f} EUR")
    print(f"  PEF_min      : {ev_sum['pef_min']:.2f} pt")
    print(f"  Autarky_max  : {ev_sum['autarky_max']:.4f}")

    print("\n[compare] --- V2H ---")
    print(f"  NPC_min      : {v2h_sum['npc_min']:.2f} EUR")
    print(f"  PEF_min      : {v2h_sum['pef_min']:.2f} pt")
    print(f"  Autarky_max  : {v2h_sum['autarky_max']:.4f}")

    print("\n[compare] --- Differenzen (V2H vs. EV) ---")
    print(f"  ΔNPC   (abs) : {npc_red_abs:.2f} EUR  (negativ = V2H günstiger)")
    print(f"  ΔNPC   (rel) : {npc_red_rel * 100:.2f} %")

    print(f"  ΔPEF   (abs) : {pef_red_abs:.2f} pt   (negativ = V2H ökologischer)")
    print(f"  ΔPEF   (rel) : {pef_red_rel * 100:.2f} %")

    print(f"  ΔAutarkie    : {aut_inc_abs:.4f}  (positiv = V2H autarker)")


if __name__ == "__main__":
    main()
