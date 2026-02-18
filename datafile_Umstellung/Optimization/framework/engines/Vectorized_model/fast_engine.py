# Optimization/framework/engines/Vectorized_model/fast_engine.py
from __future__ import annotations

from typing import Any, Dict, List, Tuple

import numpy as np

from Optimization.framework.engines.kpi import compute_kpis
from Technical_model.energy_system.precompute.adapter import prepare_profiles_adapter


def _as_1d(v: Any) -> np.ndarray:
    """
    Convert flow to 1D time series.
    If v is scalar -> length-1 array.
    If v is 2D (T, N) -> sum across N to 1D.
    If higher dims -> flatten all non-time dims and sum.
    """
    a = np.asarray(v, float)
    if a.ndim == 0:
        return a.reshape(1)
    if a.ndim == 1:
        return a
    return a.reshape(a.shape[0], -1).sum(axis=1)


def _sum_pos(res: Dict[str, Any], key: str) -> float:
    if key not in res:
        return 0.0
    a = _as_1d(res[key])
    return float(np.sum(np.clip(a, 0.0, None)))


def _sum_neg_as_pos(res: Dict[str, Any], key: str) -> float:
    """Sum negative parts as positive value (e.g., export embedded as negative in net-flow)."""
    if key not in res:
        return 0.0
    a = _as_1d(res[key])
    return float(np.sum(np.clip(-a, 0.0, None)))




class FastEngine:
    def __init__(self, settings):
        self.s = settings

        prep = prepare_profiles_adapter(settings)
        self.profiles = prep.profiles
        self.params_base = prep.params_base
        self.year_load_kwh = float(prep.year_load_kwh)
        self.lifetime_years = int(prep.lifetime_years)

        self.obj_names: List[str] = list(getattr(settings.objectives, "names", []))
        self.con_names: List[str] = list(getattr(settings.constraints, "names", []))

        from Technical_model.energy_system.systems.registry_systems import get as get_system  # type: ignore

        system_id = getattr(getattr(settings, "engine", None), "system_id", None)
        if not isinstance(system_id, str) or not system_id.strip():
            raise ValueError("[fast] settings.engine.system_id fehlt oder ist leer.")

        self._run_system = get_system(system_id)

    def evaluate_one_with_flows(self, x: np.ndarray) -> Tuple[np.ndarray, np.ndarray, Dict[str, float]]:
        x = np.asarray(x, float).reshape(-1)
        pv_kwp, bess_kwh = float(x[0]), float(x[1])

        params = dict(self.params_base)
        params["pv_size"] = pv_kwp
        params["battery_capacity_kWh"] = bess_kwh
        
        # Ensure N_EC and N_HH are set (from settings.engine)
        eng = getattr(self.s, "engine", None)
        if eng:
            params["N_HH"] = int(eng.N_HH)
            params["N_EC"] = int(eng.N_EC)
            params["rng_seed"] = int(eng.rng_seed)

        res, _hourly = self._run_system(params, self.profiles, pv_kwp, run_checks=False)

        # -----------------------------
        # Robust: Grid Import/Export
        # -----------------------------
        if "grid_import" in res or "grid_export" in res:
            E_imp_grid_Y = _sum_pos(res, "grid_import")
            E_exp_grid_Y = max(_sum_pos(res, "grid_export"), _sum_neg_as_pos(res, "grid_import"))
        elif "grid_net" in res:
            E_imp_grid_Y = _sum_pos(res, "grid_net")
            E_exp_grid_Y = _sum_neg_as_pos(res, "grid_net")
        else:
            raise KeyError(
                "[fast] No grid flow key found. Expected one of: 'grid_import'/'grid_export' or 'grid_net'. "
                f"Available keys: {sorted(res.keys())}"
            )

        # -----------------------------
        # EC imports
        # -----------------------------
        E_imp_ec_pv_Y = _sum_pos(res, "ec_import_from_pv")
        E_imp_ec_ev_Y = _sum_pos(res, "ec_import_from_ev")

        pv_gen_Y = _sum_pos(res, "pv_generation")
        bess_throughput_Y = _sum_pos(res, "bess_charged") + _sum_pos(res, "bess_discharged")

        # -----------------------------
        # Total load (CORRECT autarky denominator)
        # -----------------------------
        if "total_load" in res:
            total_load_Y = _sum_pos(res, "total_load")
        else:
            # Fail-fast: do NOT silently fall back to year_load_kwh (would reintroduce the bug)
            raise KeyError(
                "[fast] 'total_load' fehlt im Systemresult – Autarkie-Nenner wäre potenziell falsch. "
                f"Available keys: {sorted(res.keys())}"
            )

        L = int(params.get("lifetime", self.lifetime_years))

        flows_L: Dict[str, float] = {
            "E_import_grid_kWh": float(E_imp_grid_Y * L),
            "E_export_grid_kWh": float(E_exp_grid_Y * L),
            "E_import_ec_pv_kWh": float(E_imp_ec_pv_Y * L),
            "E_import_ec_ev_kWh": float(E_imp_ec_ev_Y * L),
            "PV_generation_kWh": float(pv_gen_Y * L),
            "BESS_throughput_kWh": float(bess_throughput_Y * L),
            "E_total_load_kWh": float(total_load_Y * L),
        }

        design_vars = {
            "pv_kwp": float(pv_kwp),
            "bess_kwh": float(bess_kwh),
            "params": params,
            "lifetime_years": int(self.lifetime_years),
        }
        objectives, constraints, _ctx = compute_kpis(flows_L, design_vars, self.s, self.profiles)
        F = np.array([float(objectives[n]) for n in self.obj_names], dtype=float).reshape(1, -1)

        if self.con_names:
            G = np.array(constraints, dtype=float).reshape(1, -1)
        else:
            G = np.zeros((1, 0), dtype=float)

        return F, G, flows_L

    def evaluate(self, X: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
        X = np.asarray(X, float)
        if X.ndim == 1:
            X = X.reshape(1, -1)

        F_rows: List[np.ndarray] = []
        G_rows: List[np.ndarray] = []

        for i in range(X.shape[0]):
            F, G, _flows = self.evaluate_one_with_flows(X[i, :])
            F_rows.append(F)
            G_rows.append(G)

        F_out = np.vstack(F_rows) if F_rows else np.zeros((0, len(self.obj_names)), float)
        if self.con_names:
            G_out = np.vstack(G_rows) if G_rows else np.zeros((0, len(self.con_names)), float)
        else:
            G_out = np.zeros((F_out.shape[0], 0), float)
        return F_out, G_out

    def run(self, run_dir: str) -> Dict[str, Any]:
        return {"ok": True, "run_dir": str(run_dir)}
