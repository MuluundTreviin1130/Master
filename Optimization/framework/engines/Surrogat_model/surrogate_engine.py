# Optimization/framework/engines/Surrogat_model/surrogate_engine.py
from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Any, Dict, List

import numpy as np

from Learning.runtime.load_bundle import choose_artifact_path, load_bundle
from Learning.policies.resolve_retrain import resolve_retrain
from Learning.runtime.resolve_model import resolve_model
from Learning.training.train_surrogate import train_surrogate_model
from Optimization.framework.engines.Surrogat_model.features import (
    augment_features,
    build_static_feature_vector,
    build_signature_context_payload,
    build_signature_system_flags,
    get_active_tariff_arm,
    resolve_surrogate_family,
    resolve_feature_encoding,
    resolve_feature_names,
    resolve_surrogate_targets,
)
from Optimization.framework.engines.Surrogat_model.feasibility_screen import (
    SurrogateFeasibilityScreen,
    build_surrogate_feasibility_screen,
)
from Optimization.framework.engines.kpi import compute_kpis, compute_objectives, get_selected_objective_names
from Optimization.framework.engines.profiles_meta import get_profile_id
from Optimization.framework.engines.signature_utils import build_signature_dict, signature_hash
from Technical_model.energy_system.precompute.adapter import prepare_profiles_adapter
from Settings.problem.bounds import vector_to_named_dict

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
        active_tariff_arm = get_active_tariff_arm(settings)

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

        self._targets = resolve_surrogate_targets(self.s)
        self._surrogate_family = resolve_surrogate_family(self.s)
        obj_targets = get_selected_objective_names(self.s)
        self._objective_targets = obj_targets
        self._objectives_in_targets = bool(obj_targets and all(o in self._targets for o in obj_targets))
        self.feature_names = resolve_feature_names(self.s)
        self.feature_encoding = resolve_feature_encoding(self.s)
        eng_cfg = getattr(settings, "engine", None)
        self.system_id = str(getattr(eng_cfg, "system_id", "unknown"))
        self.system_flags = build_signature_system_flags(self.s, self.base_params)
        self.signature_system_flags = dict(self.system_flags)
        self.signature_system_flags["surrogate_family"] = self._surrogate_family
        self._static_feature_vec = build_static_feature_vector(self.s, self.profile_id)
        # Bump when dispatch/profile handling changes and old surrogate artifacts must be invalidated.
        self._engine_version_tag = f"ec_flex_surrogate_family_{self._surrogate_family}_20260318"
        self.signature_dict = build_signature_dict(
            self.s,
            surrogate_meta_hint={
                "targets": self._targets,
                "feature_names": self.feature_names,
                "feature_encoding": self.feature_encoding,
                "profile_id": self.profile_id,
                "system_id": self.system_id,
                "system_flags": self.system_flags,
                "active_tariff_arm": active_tariff_arm,
            },
            system_context={
                "runtime_targets": self._targets,
                "feature_names": self.feature_names,
                "feature_encoding": self.feature_encoding,
                "profile_id": self.profile_id,
                "system_id": self.system_id,
                "static_context": build_signature_context_payload(self.s, self.profile_id),
                "system_flags": self.signature_system_flags,
                "active_tariff_arm": self._surrogate_family,
                "engine_version": self._engine_version_tag,
            },
        )
        self.signature_hash = signature_hash(self.signature_dict)
        self._resolved_model_info = resolve_model(self.s)
        self._retrain_decision = resolve_retrain(self.s)
        learning = getattr(self.s, "learning", None)
        self._force_native_retrain = bool(getattr(learning, "force_native_retrain", False))
        self._force_append_then_train = bool(getattr(learning, "force_append_then_train", False))
        self._validate_runtime_contract()

        artifact_info = choose_artifact_path(self.signature_hash, self._resolved_model_info, settings=self.s)
        self._artifact_dir = artifact_info["artifact_dir"]
        self._artifact_path = artifact_info["artifact_path"]
        self._last_training_info: Dict[str, Any] | None = None
        self._feasibility_screen: SurrogateFeasibilityScreen | None = None

        # Load or train models
        self._models_F: List[Any] = []
        if self._force_native_retrain or self._force_append_then_train:
            self._targets = list(self._targets)
            self._models_F = []
            self._train_or_fail("force_native_retrain" if self._force_native_retrain else "force_append_then_train")
            self._initialize_feasibility_screen()
            return
        bundle = load_bundle(
            artifact_path=self._artifact_path,
            required_targets=list(self._targets),
            feature_names=self.feature_names,
            expected_input_dim=int(len(getattr(self.s.bounds, "names", []) or [])) + int(self._static_feature_vec.size),
            profile_id=self.profile_id,
            system_id=self.system_id,
        )
        if bundle["status"] == "loaded":
            self._targets = list(bundle["targets"])
            self._models_F = list(bundle["models"])
        else:
            self._targets = list(self._targets)
            self._models_F = []
            self._train_or_fail(str(bundle["reason"]))
        self._initialize_feasibility_screen()

    def _validate_runtime_contract(self) -> None:
        surrogate_cfg = getattr(self.s, "surrogate", None)
        model_name = str(getattr(surrogate_cfg, "model", "rf") or "rf").strip().lower()
        feas_cfg = getattr(self.s, "feasibility", None)
        feas_mode = str(getattr(feas_cfg, "mode", "hybrid") or "hybrid").strip().lower()

        if model_name == "xgb" and feas_mode in {"hybrid", "uncertainty_conservative"}:
            raise RuntimeError(
                "[surrogate] model='xgb' is installed, but the active feasibility mode requires "
                "ensemble-based uncertainty from predict_constraints_with_uncertainty(...). "
                "Choose an explicit settings SSOT path before switching the default: "
                "either set feasibility.mode='gold_recheck' for xgb runs or implement an xgb-compatible "
                "uncertainty path."
            )

    def _initialize_feasibility_screen(self) -> None:
        self._feasibility_screen = build_surrogate_feasibility_screen(self.s)
        if self._feasibility_screen is None:
            return

        expected_name = str(self._feasibility_screen.constraint_name)
        if expected_name not in self.con_names:
            raise RuntimeError(
                "[surrogate] surrogate feasibility screen is enabled, but the matching constraint name "
                f"'{expected_name}' is missing from settings.constraints.names."
            )
        unsupported = [name for name in self.con_names if str(name) != expected_name]
        if unsupported:
            raise RuntimeError(
                "[surrogate] explicit surrogate feasibility screen currently supports only its own screen "
                f"constraint '{expected_name}'. Unsupported additional constraints: {', '.join(unsupported)}."
            )

    def _can_score_direct_objectives(self) -> bool:
        """Allow direct target-backed objective scoring even with the explicit screen.

        The screen supplies its own constraint values from audited family data.
        As long as there are no other runtime constraints to reconstruct, the
        engine may still score objectives directly from target columns.
        """
        direct_objective_targets = self._direct_objective_target_names()
        if direct_objective_targets is None:
            return False
        if not self.con_names:
            return True
        if self._feasibility_screen is None:
            return False
        return set(str(name) for name in self.con_names) == {str(self._feasibility_screen.constraint_name)}

    def _train_or_fail(self, reason: str) -> None:
        learning = getattr(self.s, "learning", None)
        mode = str(getattr(learning, "auto_retrain_mode", "assist") or "assist").strip().lower()
        allow_auto_refit = bool(getattr(learning, "allow_auto_refit", True))
        allow_auto_new_family = bool(getattr(learning, "allow_auto_new_family", False))
        allow_auto_full_rebuild = bool(getattr(learning, "allow_auto_full_rebuild", False))

        decision = dict(self._retrain_decision or {})
        action = str(decision.get("action", "") or "")
        status = str(decision.get("status", "") or "")

        # The repo has an explicit native retrain entrypoint
        # (`Learning/scripts/run_retrain.py --execute --force-native`) that
        # intentionally asks the engine to rebuild the current family artifact.
        # In that explicit path we must not block on the normal strict runtime
        # loader rule, otherwise the documented retrain workflow becomes
        # impossible to execute.
        if self._force_native_retrain or self._force_append_then_train:
            self._train_from_teacher()
            return

        if mode == "strict":
            raise RuntimeError(
                f"[surrogate] No reusable Learning model available ({reason}). "
                f"status={status}, action={action}. Run Learning/scripts/run_retrain.py first."
            )

        if action == "register_and_train" and not (allow_auto_new_family or allow_auto_full_rebuild):
            raise RuntimeError(
                f"[surrogate] Learning policy blocks automatic training for new family ({reason}). "
                f"status={status}, action={action}. Run Learning/scripts/run_retrain.py explicitly."
            )

        if action in {"train_model", "append_then_train"} and not allow_auto_refit:
            raise RuntimeError(
                f"[surrogate] Learning policy blocks automatic retraining ({reason}). "
                f"status={status}, action={action}. Run Learning/scripts/run_retrain.py explicitly."
            )

        self._train_from_teacher()

    def _train_from_teacher(self) -> None:
        # teacher is gold engine by registry
        from Optimization.framework.Orchestrator.registry import resolve_engine
        from Optimization.framework.engines.Surrogat_model.samplers.factory import sample_from_settings

        Teacher = resolve_engine("gold")
        teacher = Teacher(self.s)
        self._models_F, self._artifact_dir, self._artifact_path, self._last_training_info = train_surrogate_model(
            settings=self.s,
            resolved_model_info=self._resolved_model_info,
            retrain_decision=self._retrain_decision,
            targets=self._targets,
            feature_names=self.feature_names,
            feature_encoding=self.feature_encoding,
            profile_id=self.profile_id,
            system_id=self.system_id,
            signature_hash=self.signature_hash,
            signature_dict=self.signature_dict,
            artifact_dir=self._artifact_dir,
            artifact_path=self._artifact_path,
            profiles=self.profiles,
            build_design_vars_fn=self._build_design_vars,
            teacher=teacher,
            sample_from_settings_fn=sample_from_settings,
        )

    def _direct_objective_target_names(self) -> List[str] | None:
        """Resolve explicit objective->target aliases for surrogate-only scoring.

        We keep this mapping intentionally tiny and explicit. The goal is not to
        invent missing KPI reconstructions, but to acknowledge one SSOT-backed
        equivalence that already exists in the dispatch cost breakdown:

        - ``dispatch_cost_eur`` and ``dispatch_objective_eur`` are the same scalar.

        This helper is used only when:
        - the runtime has no explicit constraints to evaluate, and
        - every requested objective can be read directly from surrogate targets.

        If any objective cannot be resolved from the active surrogate target set,
        we return ``None`` and the engine falls back to the full KPI path.
        """
        direct_names: List[str] = []
        available = set(str(t) for t in self._targets)
        alias_to_target = {
            # ``dispatch_cost_eur`` is kept as the public optimization objective
            # name in existing overrides, while the focused surrogate target slice
            # stores the numerically identical ``dispatch_objective_eur`` target.
            "dispatch_cost_eur": "dispatch_objective_eur",
        }
        for objective_name in self.obj_names:
            normalized = str(objective_name)
            if normalized in available:
                direct_names.append(normalized)
                continue
            aliased = alias_to_target.get(normalized)
            if aliased and aliased in available:
                direct_names.append(str(aliased))
                continue
            return None
        return direct_names

    def _can_score_direct_from_targets(self) -> bool:
        """Return ``True`` only for an explicit, fully target-backed fast path.

        We do *not* use this as a silent fallback. The optimization path may skip
        full KPI reconstruction only when there are no runtime constraints and the
        requested objectives map completely to surrogate targets via the explicit
        SSOT-backed alias helper above.
        """
        if self.con_names:
            return False
        return self._direct_objective_target_names() is not None

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

    def _build_design_vars(self, x_row: np.ndarray | list[float]) -> Dict[str, Any]:
        named = vector_to_named_dict(np.asarray(x_row, float).reshape(-1), self.s.bounds)
        return {
            "pv_kwp": float(named.get("pv_kwp", 0.0)),
            "bess_kwh": float(named.get("bess_kwh", 0.0)),
            "ely_kw": float(named.get("ely_kw", 0.0)),
            "h2_tank_kwh": float(named.get("h2_tank_kwh", 0.0)),
            "fc_kw": float(named.get("fc_kw", 0.0)),
            "small_wind_kw": float(named.get("small_wind_kw", 0.0)),
            "large_wind_kw": float(named.get("large_wind_kw", 0.0)),
            "district_heat_pump_kw_th": float(named.get("district_heat_pump_kw_th", 0.0)),
            "district_thermal_storage_kwh_th": float(named.get("district_thermal_storage_kwh_th", 0.0)),
            "district_external_heat_kw_th": float(self.base_params.get("district_external_heat_kw_th", 0.0)),
            "district_gas_boiler_kw_th": float(self.base_params.get("district_gas_boiler_kw_th", 0.0)),
            "district_wood_chip_boiler_kw_th": float(named.get("district_wood_chip_boiler_kw_th", 0.0)),
            "district_biomass_chp_kw_th": float(named.get("district_biomass_chp_kw_th", 0.0)),
            "district_geothermal_kw_el": float(named.get("district_geothermal_kw_el", 0.0)),
            "district_gas_chp_kw_el": float(named.get("district_gas_chp_kw_el", 0.0)),
            "district_biogas_chp_kw_el": float(named.get("district_biogas_chp_kw_el", 0.0)),
            "district_solar_thermal_kw_th": float(self.base_params.get("district_solar_thermal_kw_th", 0.0)),
            "district_waste_incineration_kw_th": float(self.base_params.get("district_waste_incineration_kw_th", 0.0)),
            "biogas_engine_kw": float(named.get("biogas_engine_kw", 0.0)),
            "wood_gasifier_kw": float(named.get("wood_gasifier_kw", 0.0)),
            "params": self.base_params,
            "lifetime_years": self._lifetime,
        }

    def _augment_features(self, X_design: np.ndarray) -> np.ndarray:
        return augment_features(self.s, X_design, self.profile_id)

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

    def predict_constraints_with_uncertainty(self, X: np.ndarray) -> Dict[str, Any]:
        cfg = getattr(self.s, "feasibility", None)
        source = str(getattr(cfg, "uncertainty_source", "quantile") or "quantile").strip().lower()
        if source not in {"quantile", "ensemble"}:
            raise RuntimeError(f"[surrogate] Unsupported feasibility uncertainty_source='{source}'.")

        X = np.asarray(X, float)
        if X.ndim == 1:
            X = X.reshape(1, -1)
        X_feat = self._augment_features(X)
        if not self._models_F:
            raise RuntimeError("[surrogate] No fitted surrogate models available for uncertainty prediction.")
        surrogate_cfg = getattr(self.s, "surrogate", None)
        model_name = str(getattr(surrogate_cfg, "model", "rf") or "rf").strip().lower()
        if not all(hasattr(model, "estimators_") for model in self._models_F):
            raise RuntimeError(
                f"[surrogate] predict_constraints_with_uncertainty currently requires ensemble models exposing "
                f"'estimators_'. Active surrogate model='{model_name}' is not supported by this uncertainty path."
            )

        q = float(getattr(cfg, "uncertainty_quantile", 0.90) or 0.90)
        lower_q = max(0.0, min(0.5, (1.0 - q) / 2.0))
        upper_q = min(1.0, max(0.5, 1.0 - lower_q))
        n_points = X.shape[0]
        n_targets = len(self._targets)
        n_trees = min(len(getattr(model, "estimators_", []) or []) for model in self._models_F)
        if n_trees <= 0:
            raise RuntimeError("[surrogate] Ensemble models do not contain base estimators for uncertainty prediction.")

        target_samples = np.zeros((n_points, n_targets, n_trees), dtype=float)
        for j, model in enumerate(self._models_F):
            estimators = list(getattr(model, "estimators_", []) or [])
            for t_idx, tree in enumerate(estimators[:n_trees]):
                target_samples[:, j, t_idx] = np.asarray(tree.predict(X_feat), dtype=float).reshape(-1)

        constraint_names = list(getattr(getattr(self.s, "constraints", None), "names", []) or [])
        n_constraints = len(constraint_names)
        g_pred = np.zeros((n_points, n_constraints), dtype=float)
        g_lower = np.zeros((n_points, n_constraints), dtype=float)
        g_upper = np.zeros((n_points, n_constraints), dtype=float)

        target_index = {t: idx for idx, t in enumerate(self._targets)}
        for i in range(n_points):
            design_vars = self._build_design_vars(X[i, :])
            g_tree = np.zeros((n_trees, n_constraints), dtype=float)
            for t_idx in range(n_trees):
                flows_L = self._flows_dict(target_samples[i, :, t_idx])
                objectives, constraints, _ctx = compute_kpis(flows_L, dict(design_vars), self.s, self.profiles)
                if len(constraints) != n_constraints:
                    raise RuntimeError(
                        f"[surrogate] Constraint length mismatch in uncertainty prediction: "
                        f"expected {n_constraints}, got {len(constraints)}."
                    )
                g_tree[t_idx, :] = np.asarray(constraints, dtype=float)
            g_pred[i, :] = np.mean(g_tree, axis=0)
            g_lower[i, :] = np.quantile(g_tree, lower_q, axis=0)
            g_upper[i, :] = np.quantile(g_tree, upper_q, axis=0)

        return {
            "constraint_names": constraint_names,
            "g_pred": g_pred,
            "g_lower": g_lower,
            "g_upper": g_upper,
            "meta": {
                "uncertainty_source": source,
                "uncertainty_quantile": q,
                "n_base_estimators_used": int(n_trees),
            },
        }

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
        direct_objective_targets = self._direct_objective_target_names()
        use_direct_objective_targets = self._can_score_direct_objectives()
        screen_constraints = (
            self._feasibility_screen.constraint_values(X) if self._feasibility_screen is not None else None
        )

        target_index = {t: idx for idx, t in enumerate(self._targets)}
        for i in range(X.shape[0]):
            # Fast path for surrogate-only optimization:
            # When the requested objectives are explicitly represented by surrogate
            # targets and there are no constraints to reconstruct, we avoid calling
            # ``compute_kpis``. That function expects raw dispatch objective terms
            # which do not exist in a pure surrogate run. Skipping it here is an
            # explicit runtime contract, not a hidden fallback.
            if use_direct_objective_targets:
                F_rows.append([float(Y_pred[i, target_index[name]]) for name in direct_objective_targets])
            else:
                flows_L = self._flows_dict(Y_pred[i, :])
                design_vars = self._build_design_vars(X[i, :])
                if screen_constraints is not None:
                    # The explicit surrogate screen is not a normal KPI constraint
                    # provider.  When it is active, evaluate only objectives here
                    # and source the single constraint row from the screen below.
                    objectives = compute_objectives(flows_L, design_vars, self.s, self.profiles)
                    constraints = []
                else:
                    objectives, constraints, _ctx = compute_kpis(flows_L, design_vars, self.s, self.profiles)
                if self._objectives_in_targets and all(n in target_index for n in self.obj_names):
                    F_rows.append([float(Y_pred[i, target_index[n]]) for n in self.obj_names])
                else:
                    F_rows.append([float(objectives[n]) for n in self.obj_names])

                if self.con_names and screen_constraints is None:
                    G_rows.append(constraints)

            if screen_constraints is not None:
                G_rows.append(np.asarray(screen_constraints[i, :], dtype=float).reshape(-1).tolist())

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
        if self._feasibility_screen is not None:
            meta_hint["feasibility_screen"] = {
                "constraint_name": self._feasibility_screen.constraint_name,
                "family_hash": self._feasibility_screen.family_hash,
                "n_feasible": int(self._feasibility_screen.n_feasible),
                "n_infeasible": int(self._feasibility_screen.n_infeasible),
                "neighbors": int(self._feasibility_screen.neighbors),
                "min_feasible_probability": float(self._feasibility_screen.min_feasible_probability),
            }
        (out / "surrogate_meta_hint.json").write_text(json.dumps(meta_hint, indent=2), encoding="utf-8")
        return {"ok": True, "run_dir": str(out), "n_models": len(self._models_F), "targets": self._targets}
