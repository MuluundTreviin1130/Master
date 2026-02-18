# Optimization/framework/engines/Gold/gold_engine.py
from __future__ import annotations

from typing import Any, Dict, List, Tuple, Optional

import time
from pathlib import Path
import numpy as np

from Technical_model.energy_system.precompute.adapter import prepare_profiles_adapter
from Optimization.framework.engines.kpi import compute_kpis
from Optimization.framework.engines.Gated.io import append_csv, write_summary_line
from Optimization.framework.engines.profiles_meta import get_profile_id
from Optimization.framework.engines.signature_utils import build_signature_dict, signature_hash
from Optimization.framework.Settings.surrogate_train import make_surrogate_train

def _sum(flows: Dict[str, Any], k: str) -> float:
    v = flows.get(k, 0.0)
    if isinstance(v, (list, tuple, np.ndarray)):
        return float(np.sum(v))
    try:
        return float(v)
    except Exception:
        return 0.0

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





class GoldEngine:
    def __init__(self, settings, run_dir: Optional[str] = None):
        self.s = settings
        self.run_dir = run_dir
        self.run_id = Path(run_dir).name if run_dir else "unknown_run"

        prep = prepare_profiles_adapter(settings)
        self.profiles = prep.profiles
        self.params_base = prep.params_base
        self.year_load_kwh = prep.year_load_kwh
        self.lifetime_years = prep.lifetime_years

        self.obj_names: List[str] = list(getattr(settings.objectives, "names", []))
        self.con_names: List[str] = list(getattr(settings.constraints, "names", []))
        self.profile_id = get_profile_id(self.profiles, self.s)

        # SSOT targets for truth_dataset schema
        train_cfg = getattr(settings, "surrogate_train", None)
        self._targets = list(getattr(train_cfg, "targets", []) or [])
        if not self._targets:
            self._targets = list(getattr(make_surrogate_train(), "targets", []) or [])
        if not self._targets:
            raise ValueError("[gold] surrogate_train.targets is empty.")

        self.signature_dict = build_signature_dict(
            self.s,
            surrogate_meta_hint={
                "targets": self._targets,
                "profile_id": self.profile_id,
                "system_id": str(getattr(getattr(settings, "engine", None), "system_id", "unknown")),
            },
            system_context={
                "runtime_targets": self._targets,
                "profile_id": self.profile_id,
                "system_id": str(getattr(getattr(settings, "engine", None), "system_id", "unknown")),
            },
        )
        self.signature_hash = signature_hash(self.signature_dict)
        self._timings: List[float] = []

        # System function via registry
        from Technical_model.energy_system.systems.registry_systems import get as get_system  # type: ignore

        system_id = getattr(getattr(settings, "engine", None), "system_id", None)
        if not isinstance(system_id, str) or not system_id.strip():
            raise ValueError("[gold] settings.engine.system_id fehlt oder ist leer.")

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
        # Robust: Grid Import/Export (same logic as FAST)
        # -----------------------------
        if "grid_import" in res or "grid_export" in res:
            E_imp_grid_Y = _sum_pos(res, "grid_import")
            E_exp_grid_Y = max(_sum_pos(res, "grid_export"), _sum_neg_as_pos(res, "grid_import"))
        elif "grid_net" in res:
            E_imp_grid_Y = _sum_pos(res, "grid_net")
            E_exp_grid_Y = _sum_neg_as_pos(res, "grid_net")
        else:
            raise KeyError(
                "[gold] No grid flow key found. Expected one of: 'grid_import'/'grid_export' or 'grid_net'. "
                f"Available keys: {sorted(res.keys())}"
            )

        # -----------------------------
        # EC imports (allow missing -> 0)
        # -----------------------------
        E_imp_ec_pv_Y = _sum_pos(res, "ec_import_from_pv")
        E_imp_ec_ev_Y = _sum_pos(res, "ec_import_from_ev")
        E_exp_ec_pv_Y = _sum_pos(res, "ec_export_from_pv")

        # PV / BESS (allow missing -> 0)
        pv_gen_Y = _sum_pos(res, "pv_generation")
        bess_ch_Y = _sum_pos(res, "bess_charged") + _sum_pos(res, "bess_discharged")

        # -----------------------------
        # Total load (fail-fast if missing)
        # -----------------------------
        if "total_load" not in res:
            raise KeyError(
                "[gold] 'total_load' fehlt im Systemresult – Autarkie-Nenner wäre potenziell falsch. "
                f"Available keys: {sorted(res.keys())}"
            )
        total_load_Y = _sum_pos(res, "total_load")

        # EV flows (optional, allow missing -> 0)
        ev_charged_Y = _sum_pos(res, "ev_charged")
        ev_discharged_Y = _sum_pos(res, "ev_discharged")

        L = int(self.lifetime_years) # Lebensdauer in Jahren  changed from params.get("lifetime", self.lifetime_years)  

        flows_L = {
            "E_import_grid_kWh": float(E_imp_grid_Y * L),
            "E_export_grid_kWh": float(E_exp_grid_Y * L),
            "E_import_ec_pv_kWh": float(E_imp_ec_pv_Y * L),
            "E_import_ec_ev_kWh": float(E_imp_ec_ev_Y * L),
            "E_export_ec_pv_kWh": float(E_exp_ec_pv_Y * L),
            "PV_generation_kWh": float(pv_gen_Y * L),
            "BESS_throughput_kWh": float(bess_ch_Y * L),
            "E_ev_charged_kWh": float(ev_charged_Y * L),
            "E_ev_discharged_kWh": float(ev_discharged_Y * L),
            "E_total_load_kWh": float(total_load_Y * L),
        }

        # -----------------------------
        # Objectives + Constraints (single KPI entry-point)
        # -----------------------------
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
            t0 = time.perf_counter()
            F, G, flows = self.evaluate_one_with_flows(X[i, :])
            self._append_truth_csv(X[i, :], flows, source="gold")
            self._append_timing(i, time.perf_counter() - t0)
            F_rows.append(F)
            G_rows.append(G)

        F_out = np.vstack(F_rows) if F_rows else np.zeros((0, len(self.obj_names)), float)
        if self.con_names:
            G_out = np.vstack(G_rows) if G_rows else np.zeros((0, len(self.con_names)), float)
        else:
            G_out = np.zeros((F_out.shape[0], 0), float)
        self._flush_timing_summary()
        return F_out, G_out

    def _append_truth_csv(self, x: np.ndarray, flows: Dict[str, float], source: str) -> None:
        if not self.run_dir:
            return
        path = Path(self.run_dir) / "truth_dataset.csv"

        names = list(getattr(getattr(self.s, "bounds", None), "names", []))
        if not names:
            names = [f"x{i}" for i in range(len(x))]

        header = ["run_id", "signature_hash", "source", *names, *self._targets]
        row = {names[i]: float(x[i]) for i in range(len(x))}
        row["run_id"] = self.run_id
        row["signature_hash"] = self.signature_hash
        row["source"] = source
        for t in self._targets:
            row[t] = float(flows.get(t, 0.0))
        append_csv(path, header, row)

    def _append_timing(self, idx: int, elapsed_s: float) -> None:
        if not self.run_dir:
            return
        path = Path(self.run_dir) / "gold_timing.csv"
        header = ["run_id", "point_idx", "eval_s"]
        row = {"run_id": self.run_id, "point_idx": int(idx), "eval_s": float(elapsed_s)}
        append_csv(path, header, row)
        self._timings.append(float(elapsed_s))

    def _flush_timing_summary(self) -> None:
        if not self.run_dir or not self._timings:
            return
        arr = np.asarray(self._timings, float)
        total = float(np.sum(arr))
        mean = float(np.mean(arr))
        median = float(np.median(arr))
        n_eval = int(arr.size)
        write_summary_line(self.run_dir, f"[gold_timing] n_eval={n_eval}")
        write_summary_line(self.run_dir, f"[gold_timing] total_s={total:.6f}")
        write_summary_line(self.run_dir, f"[gold_timing] mean_s={mean:.6f}")
        write_summary_line(self.run_dir, f"[gold_timing] median_s={median:.6f}")

    def run(self, run_dir: str) -> Dict[str, Any]:
        # gold has no artifact – keep interface
        return {"ok": True, "run_dir": str(run_dir)}
