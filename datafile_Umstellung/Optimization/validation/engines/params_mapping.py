from __future__ import annotations

import inspect
from typing import Dict, Any

from V2H_energy_community_surrogat_datafilenew.datafile_Umstellung.Optimization.framework.Settings import settings as settings_mod
from V2H_energy_community_surrogat_datafilenew.datafile_Umstellung.Optimization.validation.helpers.profiles_helpers import (
    get_profiles_for_validation,
    build_base_params,
)


def get_param_aliases(S) -> Dict[str, str]:
    """
    Aliases für Parameternamen kommen aus dem Settings-Modul.

    Quellen (in dieser Reihenfolge, spätere überschreiben frühere):
      1) S.validation.param_aliases
      2) settings_mod.validation.param_aliases
      3) settings_mod.validation_aliases (legacy)
    """
    aliases: Dict[str, str] = {}

    V = getattr(S, "validation", None)
    if V is not None:
        maybe = getattr(V, "param_aliases", None)
        if isinstance(maybe, dict):
            aliases.update(maybe)

    V_mod = getattr(settings_mod, "validation", None)
    if V_mod is not None:
        maybe2 = getattr(V_mod, "param_aliases", None)
        if isinstance(maybe2, dict):
            aliases.update(maybe2)

    maybe_global = getattr(settings_mod, "validation_aliases", None)
    if isinstance(maybe_global, dict):
        aliases.update(maybe_global)

    return aliases


def analyze_signature(sim_fn):
    sig = inspect.signature(sim_fn)
    params = list(sig.parameters.values())

    settings_param = next((p.name for p in params if p.name in ("S", "settings", "cfg", "config")), None)
    dict_param = next((p.name for p in params if p.name in ("params", "x", "design", "inputs")), None)
    return sig, settings_param, dict_param


def _maybe_get_profiles(S):
    """
    Holt ein profiles-Objekt.

    Reihenfolge:
      1) Validation-Helper (get_profiles_for_validation)
      2) S.profiles / S.engine.profiles
      3) S.get_profiles() / S.engine.get_profiles()
    """
    # 1) expliziter Helper
    try:
        prof = get_profiles_for_validation(S)
        if prof is not None:
            return prof
    except Exception:
        prof = None

    # 2) direkt angehängtes Objekt
    prof = getattr(S, "profiles", None)
    if prof is None and hasattr(S, "engine"):
        prof = getattr(S.engine, "profiles", None)

    # 3) generische Loader-Methoden
    if prof is None:
        loader = getattr(S, "get_profiles", None)
        if loader is None and hasattr(S, "engine"):
            loader = getattr(S.engine, "get_profiles", None)
        if callable(loader):
            prof = loader()

    return prof


def build_kwargs_for_row(sim_fn, row_dict, S, aliases: Dict[str, str]) -> Dict[str, Any]:
    """
    Baut **kwargs für einen row-wise Call.
    Spezieller Fall für dein Systemmodell:
      simulate_energy_system_with_v2h(params, profiles, pv_size)
    """
    sig, settings_param, dict_param = analyze_signature(sim_fn)
    kwargs: Dict[str, Any] = {}

    # Settings-Objekt injizieren (falls vorgesehen)
    if settings_param is not None:
        kwargs[settings_param] = S

    # Basis-Params wie im FastEngine
    base_params = None
    if dict_param == "params":
        try:
            base_params = build_base_params(S)
        except Exception:
            base_params = None

    # komplettes Row-Dict als "params"/"x"/"design"/"inputs" übergeben (falls vorgesehen)
    if dict_param is not None:
        if dict_param == "params" and base_params is not None:
            # Start mit Basis-Params
            params_dict = dict(base_params)

            # Design-Variablen mappen (PV/BESS)
            pv_raw = row_dict.get("pv_kwp")
            bess_raw = row_dict.get("bess_kwh")
            if pv_raw is not None:
                params_dict["pv_size"] = float(pv_raw)
            if bess_raw is not None:
                params_dict["battery_capacity_kWh"] = float(bess_raw)

            # Rest der Spalten ebenfalls mitnehmen (falls du später mehr Designvariablen hast)
            params_dict.update(row_dict)

            kwargs["params"] = params_dict
        else:
            kwargs[dict_param] = row_dict

    # Jetzt *immer* alle übrigen Parameter durchgehen
    for p in sig.parameters.values():
        name = p.name

        if name == settings_param or name == dict_param:
            continue

        # 1) Spalte mit identischem Namen?
        if name in row_dict:
            kwargs[name] = row_dict[name]
            continue

        # 2) Alias-Mapping aus Settings?
        src = aliases.get(name)

        # Harte Fallbacks, falls Aliases aus irgendeinem Grund leer sind
        if src is None and name == "pv_size" and "pv_kwp" in row_dict:
            src = "pv_kwp"
        if src is None and name == "bess_capacity_kwh" and "bess_kwh" in row_dict:
            src = "bess_kwh"

        if src is not None and src in row_dict:
            kwargs[name] = row_dict[src]
            continue

        # 3) Spezialfall: Profiles
        if name in ("profiles", "profile_dict", "prof", "prof_dict"):
            prof = _maybe_get_profiles(S)
            if prof is None:
                raise ValueError(
                    "[teacher] konnte kein 'profiles'-Objekt ableiten. "
                    "Bitte entweder Validation-Helper get_profiles_for_validation(S) "
                    "implementieren oder S.profiles / S.engine.profiles bzw. "
                    "S.get_profiles() / S.engine.get_profiles() bereitstellen."
                )
            kwargs[name] = prof
            continue

        # 4) Required-Parameter ohne Default → harter Fehler mit klarer Message
        if p.default is inspect.Parameter.empty:
            raise ValueError(
                f"[teacher] required-Parameter '{name}' kann nicht befüllt werden. "
                f"Spalte '{name}' in X ergänzen oder Alias in "
                f"validation.param_aliases['{name}'] = '<spaltenname>' setzen."
            )

    return kwargs
