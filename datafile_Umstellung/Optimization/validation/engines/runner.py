# Optimization/validation/engines/runner.py
from __future__ import annotations

from typing import Tuple
import numpy as np
import pandas as pd

from V2H_energy_community_surrogat_datafilenew.datafile_Umstellung.Optimization.framework.Settings.settings import get_settings
from V2H_energy_community_surrogat_datafilenew.datafile_Umstellung.Optimization.framework.Settings import settings as settings_mod
from V2H_energy_community_surrogat_datafilenew.datafile_Umstellung.Optimization.validation.sampling.strategies import select_subset

# ---- Engines robust importieren ----
try:
    # Variante mit Unterordnern Fast/Gold
    from V2H_energy_community_surrogat_datafilenew.datafile_Umstellung.Optimization.framework.engines.Vectorized_model.fast_engine import FastEngine
except Exception:
    try:
        # Variante: fast_engine.py direkt im engines-Paket
        from V2H_energy_community_surrogat_datafilenew.datafile_Umstellung.Optimization.framework.engines.Vectorized_model.fast_engine import FastEngine
    except Exception:
        # Fallback: als Submodul importieren
        from V2H_energy_community_surrogat_datafilenew.datafile_Umstellung.Optimization.framework.engines import fast_engine as _fast_mod
        FastEngine = _fast_mod.FastEngine  # type: ignore


try:
    from V2H_energy_community_surrogat_datafilenew.datafile_Umstellung.Optimization.framework.engines.Gold.gold_engine import GoldEngine
except Exception:
    try:
        from V2H_energy_community_surrogat_datafilenew.datafile_Umstellung.Optimization.framework.engines.Gold.gold_engine import GoldEngine
    except Exception:
        from V2H_energy_community_surrogat_datafilenew.datafile_Umstellung.Optimization.framework.engines import gold_engine as _gold_mod
        GoldEngine = _gold_mod.GoldEngine  # type: ignore


def _get_settings():
    """
    Holt das zentrale Settings-Objekt und hängt, falls nötig,
    die Validation-/Pfad-Configs aus Optimization.framework.Settings.settings an.
    """
    S = get_settings()

    if not hasattr(S, "validation") and hasattr(settings_mod, "validation"):
        setattr(S, "validation", settings_mod.validation)

    if not hasattr(S, "paths") and hasattr(settings_mod, "paths"):
        setattr(S, "paths", settings_mod.paths)

    return S


def _run_generic(
    which: str,
    X: pd.DataFrame,
    xschema_names,
    bounds_dict,
    meta,
    eng_cfg,
) -> Tuple[pd.DataFrame, pd.DataFrame]:
    """
    Gemeinsame Logik für FAST und GOLD:

      - Settings + Validation-Config holen
      - Subset der Zeilen gem. validation.fast_subset / validation.gold_subset
      - passende Engine (FastEngine / GoldEngine) instanziieren
      - engine.evaluate(X_subset) aufrufen
      - Ergebnisse als DataFrames mit Ziel-/Constraintnamen aus Settings zurückgeben
    """
    S = _get_settings()

    # Nur die Spalten nehmen, die zur X-Schema gehören (z.B. ["pv_kwp","bess_kwh"])
    if xschema_names:
        X = X.loc[:, list(xschema_names)]

    # Subset für FAST / GOLD gemäß Settings.validation
    X_sel = select_subset(X, which=which, xschema_names=xschema_names)

    # Passende Engine auswählen
    if which == "fast":
        engine = FastEngine(S)
    elif which == "gold":
        engine = GoldEngine(S)
    else:
        raise ValueError(f"[validation] unknown teacher label '{which}' (expected 'fast' or 'gold').")

    # Engines arbeiten auf numpy-Arrays; Reihenfolge entspricht settings.bounds.names
    X_np = np.asarray(X_sel.to_numpy(dtype=float))
    F_np, G_np = engine.evaluate(X_np)

    # Ziel-/Constraintnamen aus zentralem Settings
    obj_names = list(getattr(getattr(S, "objectives", None), "names", []))
    con_names = list(getattr(getattr(S, "constraints", None), "names", []))

    # DataFrames mit denselben Indizes wie X_sel
    if obj_names and F_np.shape[1] == len(obj_names):
        F = pd.DataFrame(F_np, index=X_sel.index, columns=obj_names)
    else:
        F = pd.DataFrame(
            F_np,
            index=X_sel.index,
            columns=[f"obj_{i}" for i in range(F_np.shape[1])],
        )

    if G_np.size == 0:
        K = pd.DataFrame(index=X_sel.index)
    else:
        if con_names and G_np.shape[1] == len(con_names):
            K = pd.DataFrame(G_np, index=X_sel.index, columns=con_names)
        else:
            K = pd.DataFrame(
                G_np,
                index=X_sel.index,
                columns=[f"con_{i}" for i in range(G_np.shape[1])],
            )

    return F, K


def run_fast(X: pd.DataFrame, xschema_names, bounds_dict, meta, eng_cfg):
    return _run_generic("fast", X, xschema_names, bounds_dict, meta, eng_cfg)


def run_gold(X: pd.DataFrame, xschema_names, bounds_dict, meta, eng_cfg):
    return _run_generic("gold", X, xschema_names, bounds_dict, meta, eng_cfg)
