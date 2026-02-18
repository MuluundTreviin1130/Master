# Optimization/framework/engines/Surrogat_model/teacher/evaluate_teacher.py
from __future__ import annotations
import numpy as np
from typing import Dict, Any, List, Tuple

from V2H_energy_community_surrogat_datafilenew.datafile_Umstellung.Technical_model.energy_system.precompute.adapter import prepare_profiles_adapter
from V2H_energy_community_surrogat_datafilenew.datafile_Umstellung.Technical_model.energy_system.systems.registry_systems import get as get_system


from tqdm.auto import tqdm


# ---- helpers ----

def _sum(result: Dict[str, Any], key: str) -> float:
    arr = result.get(key, None)
    if arr is None:
        return 0.0
    a = np.asarray(arr)
    return float(np.sum(a))


def _year_flows(
    params: Dict[str, Any],
    profiles: Dict[str, Any],
    run_system,
    pv_kwp: float,
    bess_kwh: float,
) -> Dict[str, float]:
    """
    Simuliere 1 Jahr und gib Jahres-Summen der relevanten Flüsse zurück.
    Systemwahl (EV vs V2H etc.) erfolgt über run_system (Registry).
    """
    p = dict(params)
    p["pv_size"] = float(pv_kwp)
    p["battery_capacity_kWh"] = float(bess_kwh)

    res, _hourly = run_system(p, profiles, float(pv_kwp), run_checks=False)

    flows_year = {
        "E_import_grid_kWh":      _sum(res, "grid_import"),
        "E_export_grid_kWh":      _sum(res, "grid_export"),
        "E_import_ec_pv_kWh":     _sum(res, "ec_import_from_pv"),
        "E_import_ec_ev_kWh":     _sum(res, "ec_import_from_ev"),
        "E_bess_throughput_kWh":  _sum(res, "bess_charged"),
        # optional:
        "E_ev_charged_kWh":       _sum(res, "ev_charged"),
        "E_ev_discharged_kWh":    _sum(res, "ev_discharged"),
        "E_hp_heat_kWh":          _sum(res, "heatpump_results_heating"),
        "E_hp_cool_kWh":          _sum(res, "heatpump_results_cooling"),
        "E_pv_gen_kWh":           _sum(res, "pv_generation"),
    }
    return flows_year



# ---- main API ----

def evaluate_teacher_dataset(
    settings,
    X: np.ndarray,
    targets: List[str] | None = None,
    batch_size: int | None = None,   # aktuell ungenutzt, Interface-kompatibel
) -> Tuple[np.ndarray, np.ndarray]:
    """
    Liefert:
      YF: Matrix der LEBENSDAUER-SUMMEN der angeforderten Flow-Targets
          (Spaltenreihenfolge = targets)
      YG: (derzeit leer) Constraints-Säulen, falls du später welche als
          Surrogates lernst.
    """
    eng = settings.engine
    loc = eng.location
    system_id = eng.system_id

    # Basis-Parameter + Profile über Adapter laden
    base_params, profiles = prepare_profiles_adapter(loc)
    base_params["location"] = loc

    # EC-Shares aus Settings überschreiben
    if "EC" not in base_params:
        base_params["EC"] = {}
    base_params["EC"]["share"] = float(eng.ec_share_import)
    base_params["EC"]["export_share"] = float(eng.ec_share_export)

    # Skalierungen aus Settings
    base_params["N_HH"] = int(eng.N_HH)
    base_params["N_EC"] = int(eng.N_EC)  # Required for member-level processing
    base_params["N_EV"] = int(eng.N_EV_total)
    base_params["N_EV_bidirectional"] = int(eng.N_EV_bidirectional)

    # EV-Parameter auch im EV-Subdict spiegeln (für V2H-Modell)
    ev_cfg = base_params.setdefault("EV", {})
    ev_cfg["N_EV_total"] = int(eng.N_EV_total)
    ev_cfg["N_EV_bidirectional"] = int(eng.N_EV_bidirectional)

    # Zentrales System aus Registry
    run_system = get_system(system_id)


    # Lebensdauer (Jahre)
    L = int(base_params["lifetime"])

    # Zielspalten (Flows, die das Surrogat lernen soll)
    tnames = list(targets or settings.surrogate_train.targets)

    # Eingabematrix sauber machen
    X = np.asarray(X, float)
    if X.ndim == 1:
        X = X.reshape(1, -1)

    n_pts = X.shape[0]
    n_targets = len(tnames)
    YF = np.zeros((n_pts, n_targets), dtype=float)

    # Annahme: Bounds.names = ["pv_kwp", "bess_kwh"] → X[:, 0], X[:, 1]
    for i, (pv, bess) in enumerate(
        tqdm(X, desc="[teacher] sim", unit="pt")
    ):
        year = _year_flows(
            base_params,
            profiles,
            run_system,
            pv_kwp=float(pv),
            bess_kwh=float(bess),
        )

        # Jahresflüsse → Lebensdauer-Summen
        life = {k: float(v) * L for k, v in year.items()}
        YF[i, :] = [life.get(t, 0.0) for t in tnames]

    # Aktuell keine gelernten Constraints
    YG = np.zeros((n_pts, 0), dtype=float)
    return YF, YG
