# Optimization/framework/engines/Surrogat_model/surrogate_engine.py
from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
from joblib import dump, load
from sklearn.ensemble import RandomForestRegressor
from sklearn.model_selection import train_test_split

from Optimization.framework.engines.kpi import compute_kpis, get_selected_objective_names
from Optimization.framework.engines.profiles_meta import get_profile_id
from Optimization.framework.engines.signature_utils import build_signature_dict, signature_hash
from Optimization.framework.Settings.surrogate_train import make_surrogate_train
from Technical_model.energy_system.precompute.adapter import prepare_profiles_adapter



def _hash_to_int(value: str) -> int:
    return int.from_bytes(value.encode("utf-8"), "little") % 1_000_000_000


class SurrogateEngine:
    """
    Surrogate predicts a small set of lifetime energy flows (targets).
    Objectives/constraints are then computed from:
      - predicted flows
      - canonical params (incl. LCA dicts) from Data.params
      - settings (names only)
    """

    def __init__(self, settings, run_dir: str | None = None):

        self.s = settings
        self.run_dir = run_dir

        eng = getattr(settings, "engine", None)
        location = getattr(eng, "location", None) or getattr(settings, "location", None)
        if not isinstance(location, str) or not location.strip():
            raise TypeError("[surrogate] Could not extract location string from settings.")

        # optional: data_source, falls vorhanden
        data = getattr(settings, "data", None)
        data_source = getattr(data, "source", None) if data is not None else None

        # Pass settings object (not location string) so members can be extracted
        if isinstance(data_source, str) and data_source.strip():
            prep = prepare_profiles_adapter(settings, data_source=data_source)
        else:
            prep = prepare_profiles_adapter(settings)

        # Adapter liefert PrecomputePackage
        self.base_params = prep.params_base
        self.profiles = prep.profiles
        self._year_load_kwh = float(prep.year_load_kwh)
        self._lifetime = int(prep.lifetime_years)
        self.profile_id = get_profile_id(self.profiles, self.s)

        self.obj_names: List[str] = list(getattr(settings.objectives, "names", []))
        self.con_names: List[str] = list(getattr(settings.constraints, "names", []))

        # Surrogate training config (SSOT: settings.surrogate_train.targets)
        train_cfg = getattr(settings, "surrogate_train", None)
        base_targets = list(getattr(train_cfg, "targets", []) or [])
        if not base_targets:
            base_targets = list(getattr(make_surrogate_train(), "targets", []) or [])
        if not base_targets:
            raise ValueError("[surrogate] surrogate_train.targets is empty.")

        include_objectives = bool(getattr(train_cfg, "include_objectives", False))
        obj_targets = get_selected_objective_names(self.s) if include_objectives else []
        targets_ordered: List[str] = []
        seen = set()
        for t in list(base_targets) + list(obj_targets):
            if t not in seen:
                targets_ordered.append(t)
                seen.add(t)

        self._targets = targets_ordered
        self._objective_targets = obj_targets
        self._objectives_in_targets = bool(obj_targets and all(o in self._targets for o in obj_targets))
        self.feature_names = [
            "pv_kwp",
            "bess_kwh",
            "system_id",
            "profile_id",
            "N_EV_total",
            "N_EV_bidirectional",
        ]
        self.feature_encoding = {
            "system_id": "hash32",
            "profile_id": "hash32",
        }
        eng_cfg = getattr(settings, "engine", None)
        self.system_id = str(getattr(eng_cfg, "system_id", "unknown"))
        self._static_feature_vec = np.array(
            [
                float(_hash_to_int(self.system_id)),
                float(_hash_to_int(self.profile_id)),
                float(getattr(eng_cfg, "N_EV_total", 0)),
                float(getattr(eng_cfg, "N_EV_bidirectional", 0)),
            ],
            dtype=float,
        )
        self.signature_dict = build_signature_dict(
            self.s,
            surrogate_meta_hint={
                "targets": self._targets,
                "feature_names": self.feature_names,
                "feature_encoding": self.feature_encoding,
                "profile_id": self.profile_id,
                "system_id": self.system_id,
            },
            system_context={
                "runtime_targets": self._targets,
                "feature_names": self.feature_names,
                "feature_encoding": self.feature_encoding,
                "profile_id": self.profile_id,
                "system_id": self.system_id,
            },
        )
        self.signature_hash = signature_hash(self.signature_dict)

        # Artifact locations (signature-scoped baseline)
        self._artifact_dir = (Path("Optimization") / "run" / "artifacts").resolve()
        self._scoped_dir = self._artifact_dir / "surrogates" / str(self.signature_hash)
        self._scoped_path = self._scoped_dir / "surrogate_rf.joblib"
        legacy_path = self._artifact_dir / "surrogate_rf.joblib"
        if self._scoped_path.exists():
            self._artifact_path = self._scoped_path
            self._artifact_dir = self._scoped_dir
        elif legacy_path.exists():
            self._artifact_path = legacy_path
        else:
            self._artifact_path = self._scoped_path
            self._artifact_dir = self._scoped_dir

        # Load or train models
        self._models_F: List[Any] = []
        if self._artifact_path.exists():
            payload = load(self._artifact_path)
            loaded_targets = payload.get("targets", [])
            loaded_models = payload.get("models", [])
            loaded_features = payload.get("feature_names", [])
            loaded_profile_id = payload.get("profile_id", None)
            loaded_system_id = payload.get("system_id", None)
            loaded_n_features = None
            if loaded_models:
                loaded_n_features = getattr(loaded_models[0], "n_features_in_", None)
            
            # Ensure required targets are always present for correct constraint calculation
            required_targets = list(self._targets)
            
            # Check if all required targets are present and models match
            missing_targets = set(required_targets) - set(loaded_targets)
            feature_mismatch = list(loaded_features) != list(self.feature_names)
            profile_mismatch = (loaded_profile_id is not None and str(loaded_profile_id) != str(self.profile_id))
            system_mismatch = (loaded_system_id is not None and str(loaded_system_id) != str(self.system_id))
            feature_count_mismatch = loaded_n_features is not None and int(loaded_n_features) != len(self.feature_names)
            if missing_targets or len(loaded_models) != len(required_targets) or feature_mismatch or profile_mismatch or system_mismatch or feature_count_mismatch:
                # Old artifact or mismatch: retrain
                self._targets = required_targets
                self._models_F = []
                self._train_from_teacher()
            else:
                # Double-check: ensure E_total_load_kWh and PV_generation_kWh are present
                if any(t not in loaded_targets for t in required_targets):
                    # Critical targets missing: retrain
                    self._targets = required_targets
                    self._models_F = []
                    self._train_from_teacher()
                else:
                    self._targets = loaded_targets
                    self._models_F = loaded_models
        else:
            # If no artifact: train quickly from scratch using teacher (fast engine).
            # This matches your current pipeline: surrogate uses teacher eval.
            self._train_from_teacher()

    def _train_from_teacher(self) -> None:
        # teacher is gold engine by registry
        from Optimization.framework.Orchestrator.registry import resolve_engine
        from Optimization.framework.engines.Surrogat_model.samplers.factory import sample_from_settings

        Teacher = resolve_engine("gold")
        teacher = Teacher(self.s)

        # Use sample_from_settings instead of hardcoded random sampling
        X_design = sample_from_settings(self.s)
        X = self._augment_features(X_design)

        Y_list: List[np.ndarray] = []
        for i in range(len(X_design)):
            F, _G, flows_L = teacher.evaluate_one_with_flows(X_design[i, :])
            design_vars = self._build_design_vars(float(X_design[i, 0]), float(X_design[i, 1]))
            objectives, _constraints, _ctx = compute_kpis(flows_L, design_vars, self.s, self.profiles)
            y = np.array(
                [float(objectives[t]) if t in objectives else float(flows_L.get(t, 0.0)) for t in self._targets],
                dtype=float,
            )
            Y_list.append(y)

        Y = np.vstack(Y_list)

        # Use settings for holdout_frac and seed
        st = getattr(self.s, "surrogate_train", None)
        holdout_frac = float(getattr(st, "holdout_frac", 0.2)) if st else 0.2
        sampler = getattr(self.s, "sampler", None)
        seed = int(getattr(sampler, "seed", 42)) if sampler else 42
        
        X_train, X_test, Y_train, Y_test = train_test_split(X, Y, test_size=holdout_frac, random_state=seed)

        # Use settings for Random Forest parameters
        rf_n_estimators = int(getattr(st, "rf_n_estimators", 200)) if st else 200
        rf_n_jobs = int(getattr(st, "rf_n_jobs", -1)) if st else -1

        models: List[Any] = []
        for j in range(Y.shape[1]):
            m = RandomForestRegressor(n_estimators=rf_n_estimators, n_jobs=rf_n_jobs, random_state=seed)
            m.fit(X_train, Y_train[:, j])
            models.append(m)

        self._models_F = models

        self._artifact_dir.mkdir(parents=True, exist_ok=True)
        dump(
            {
                "targets": self._targets,
                "models": self._models_F,
                "feature_names": self.feature_names,
                "feature_encoding": self.feature_encoding,
                "profile_id": self.profile_id,
                "system_id": self.system_id,
            },
            self._artifact_path,
        )
        meta = {
            "targets": self._targets,
            "feature_names": self.feature_names,
            "feature_encoding": self.feature_encoding,
            "profile_id": self.profile_id,
            "system_id": self.system_id,
            "signature_hash": self.signature_hash,
            "signature_dict": self.signature_dict,
        }
        (self._artifact_dir / "surrogate_rf.meta.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")

    def _flows_dict(self, y_row: np.ndarray) -> Dict[str, float]:
        flows = {self._targets[i]: float(y_row[i]) for i in range(len(self._targets))}
        # Safety check: ensure critical targets are present
        if "E_total_load_kWh" not in flows:
            raise ValueError(
                f"[surrogate] 'E_total_load_kWh' fehlt in _flows_dict. "
                f"Targets: {self._targets}, Flows keys: {list(flows.keys())}"
            )
        if "PV_generation_kWh" not in flows:
            raise ValueError(
                f"[surrogate] 'PV_generation_kWh' fehlt in _flows_dict. "
                f"Targets: {self._targets}, Flows keys: {list(flows.keys())}"
            )
        return flows

    def _build_design_vars(self, pv_kwp: float, bess_kwh: float) -> Dict[str, Any]:
        return {
            "pv_kwp": float(pv_kwp),
            "bess_kwh": float(bess_kwh),
            "params": self.base_params,
            "lifetime_years": self._lifetime,
        }

    def _augment_features(self, X_design: np.ndarray) -> np.ndarray:
        X_design = np.asarray(X_design, float)
        if X_design.ndim == 1:
            X_design = X_design.reshape(1, -1)
        static = np.tile(self._static_feature_vec.reshape(1, -1), (X_design.shape[0], 1))
        return np.hstack([X_design, static])

    def _compute_objectives(self, flows_L: Dict[str, float], pv_kwp: float, bess_kwh: float) -> Dict[str, float]:
        raise RuntimeError("[surrogate] _compute_objectives is deprecated; use compute_kpis.")
        params = self.base_params
        L = int(params.get("lifetime", self._lifetime))

        def Y(k: str) -> float:
            return float(flows_L.get(k, 0.0)) / float(L)

        # energy flows (year)
        e_import_grid_Y = Y("E_import_grid_kWh")
        e_export_grid_Y = Y("E_export_grid_kWh")
        e_import_ec_pv_Y = Y("E_import_ec_pv_kWh")
        e_import_ec_ev_Y = Y("E_import_ec_ev_kWh")

        # lifetime
        E_import_grid_L = float(flows_L.get("E_import_grid_kWh", 0.0))
        E_export_grid_L = float(flows_L.get("E_export_grid_kWh", 0.0))
        if "E_total_load_kWh" not in flows_L:
            raise KeyError(
                "[surrogate] 'E_total_load_kWh' fehlt in den Surrogat-Flows – Autarkie-Nenner wäre potenziell falsch."
            )
        E_load_L = float(flows_L.get("E_total_load_kWh", 0.0))

        # NPC
        npc_val: Optional[float] = None
        if "npc_eur" in self.obj_names:
            from Cost_model.financial_model import calculate_npc_yearly

            params_fin = dict(params)
            params_fin["pv_size"] = float(pv_kwp)
            params_fin["battery_capacity_kWh"] = float(bess_kwh)

            eng = self.s.engine
            params_fin.setdefault("EV", {})
            params_fin["EV"]["N_EV_total"] = int(getattr(eng, "N_EV_total", 0))
            params_fin["EV"]["N_EV_bidirectional"] = int(getattr(eng, "N_EV_bidirectional", 0))

            npc_val = float(
                calculate_npc_yearly(
                    params_fin,
                    e_import_grid_year=e_import_grid_Y,
                    e_import_ec_pv_year=e_import_ec_pv_Y,
                    e_import_ec_ev_year=e_import_ec_ev_Y,
                    e_export_grid_year=e_export_grid_Y,
                    e_export_pv_ec_year=0.0,
                    e_export_ev_ec_year=0.0,
                )
            )

        # autarky
        autarky_val: Optional[float] = None
        if "autarky" in self.obj_names:
            autarky = 1.0 - (E_import_grid_L / E_load_L) if E_load_L > 0 else 0.0
            autarky_val = float(max(0.0, min(1.0, autarky)))

        out: Dict[str, float] = {}
        for name in self.obj_names:
            if name == "npc_eur":
                out[name] = float(npc_val or 0.0)
            elif name == "autarky":
                out[name] = float(autarky_val or 0.0)
            elif name == "grid_import_kwh":
                out[name] = float(E_import_grid_L)
            elif name == "grid_export_kwh":
                out[name] = float(E_export_grid_L)
            elif name == "grid_interaction_kwh":
                out[name] = float(E_import_grid_L + E_export_grid_L)
            elif _lca_metric_exists(params, name):
                out[name] = _total_lca_metric(params, name, pv_kwp, bess_kwh, E_import_grid_L)
            else:
                raise ValueError(
                    f"[surrogate] unknown objective '{name}'. "
                    f"Supported: npc_eur, autarky, grid_import_kwh, grid_export_kwh, grid_interaction_kwh, "
                    f"or any LCA metric present in params[tech]['LCA']."
                )
        return out

    def _compute_constraints(self, flows_L: Dict[str, float], pv_kwp: float, bess_kwh: float) -> List[float]:
        raise RuntimeError("[surrogate] _compute_constraints is deprecated; use compute_kpis.")
        if not self.con_names:
            return []

        E_import_grid_L = float(flows_L.get("E_import_grid_kWh", 0.0))
        if "E_total_load_kWh" not in flows_L:
            raise KeyError(
                "[surrogate] 'E_total_load_kWh' fehlt in den Surrogat-Flows – Autarkie-Nenner wäre potenziell falsch."
            )
        E_load_L = float(flows_L.get("E_total_load_kWh", 0.0))

        ctx = {
            "params": self.base_params,
            "E_import_grid_L": E_import_grid_L,
            "E_load_L": E_load_L,
            "E_export_grid_L": float(flows_L.get("E_export_grid_kWh", 0.0)),
            "PV_generation_L": float(flows_L.get("PV_generation_kWh", 0.0)),
            "pv_kwp": pv_kwp,
            "bess_kwh": bess_kwh,
        }
        return evaluate_constraints(self.s.constraints, ctx)

    # ---------------- API ----------------
    def evaluate(self, X: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
        X = np.asarray(X, float)
        if X.ndim == 1:
            X = X.reshape(1, -1)

        X_feat = self._augment_features(X)
        if self._models_F:
            expected = getattr(self._models_F[0], "n_features_in_", None)
            if expected is not None and int(expected) != X_feat.shape[1]:
                # Stale artifact (feature schema mismatch): retrain on-the-fly
                self._models_F = []
                self._train_from_teacher()
                X_feat = self._augment_features(X)
        Y_pred = np.column_stack([m.predict(X_feat) for m in self._models_F])

        F_rows: List[List[float]] = []
        G_rows: List[List[float]] = []

        target_index = {t: idx for idx, t in enumerate(self._targets)}
        for i in range(X.shape[0]):
            pv, bess = float(X[i, 0]), float(X[i, 1])
            flows_L = self._flows_dict(Y_pred[i, :])

            design_vars = self._build_design_vars(pv, bess)
            objectives, constraints, _ctx = compute_kpis(flows_L, design_vars, self.s, self.profiles)
            if self._objectives_in_targets and all(n in target_index for n in self.obj_names):
                F_rows.append([float(Y_pred[i, target_index[n]]) for n in self.obj_names])
            else:
                F_rows.append([float(objectives[n]) for n in self.obj_names])

            if self.con_names:
                G_rows.append(constraints)

        F = np.asarray(F_rows, float)
        if self.con_names:
            G = np.asarray(G_rows, float)
        else:
            G = np.zeros((F.shape[0], 0), float)

        return F, G

    def run(self, run_dir: str | Path) -> Dict[str, Any]:
        out = Path(run_dir).resolve()
        out.mkdir(parents=True, exist_ok=True)

        # Copy artifact(s) into run folder
        # Copy ONLY the surrogate model artifact into run folder (avoid recursive self-copy)
        art_out = out / "artifact"
        art_out.mkdir(parents=True, exist_ok=True)

        if self._artifact_path.exists():
            shutil.copy2(str(self._artifact_path), str(art_out / self._artifact_path.name))


        meta_hint = {
            "surrogate_targets": self._targets,
            "targets": self._targets,
            "feature_names": self.feature_names,
            "feature_encoding": self.feature_encoding,
            "profile_id": self.profile_id,
            "system_id": self.system_id,
            "signature_hash": self.signature_hash,
            "signature_dict": self.signature_dict,
            "artifact_path": str(self._artifact_path),
            "artifact_source_dir": str(self._artifact_dir),
        }
        (out / "surrogate_meta_hint.json").write_text(json.dumps(meta_hint, indent=2), encoding="utf-8")
        return {"ok": True, "run_dir": str(out), "n_models": len(self._models_F), "targets": self._targets}
