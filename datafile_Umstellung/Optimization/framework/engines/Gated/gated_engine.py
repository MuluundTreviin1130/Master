from __future__ import annotations

import json
import math
import time
from dataclasses import asdict
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
from joblib import dump

from ..Surrogat_model.surrogate_engine import SurrogateEngine
from ..Vectorized_model.fast_engine import FastEngine
from ..Gold.gold_engine import GoldEngine
from ..kpi import compute_kpis, get_selected_objective_names
from .control import BudgetController, BudgetState
from .guards import FidelityGuard
from .io import append_csv, promote_surrogate_version, update_manifest_json, write_summary_line
from .signature import build_signature_dict, is_compatible, signature_hash, summarize_mismatch


def _now_iso() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%S")


class GatedEngine:
    def __init__(self, settings, run_dir: Optional[str] = None, **kwargs: Any) -> None:
        self.s = settings
        self.run_dir = run_dir
        self.run_id = Path(run_dir).name if run_dir else "unknown_run"

        self.gating = getattr(settings, "gating", None)
        if self.gating is None:
            raise ValueError("[gated] settings.gating fehlt.")

        self._batch_idx = 0
        self._audit_idx = 0

        self._n_fast_total = 0
        self._n_gold_total = 0
        self._last_retrain_fast_count = 0
        self._last_retrain_batch = 0

        self._truth_X: List[np.ndarray] = []
        self._truth_Y: List[np.ndarray] = []
        self._truth_source: List[str] = []

        self._surrogate_versions: List[str] = []
        self.hv_ref_point: Optional[np.ndarray] = None
        self._parity_printed = False

        self._surrogate = SurrogateEngine(settings, run_dir=run_dir)
        self._fast = FastEngine(settings)
        self._gold = GoldEngine(settings) if self.gating.gold.enabled else None

        self._n_obj = int(len(getattr(getattr(self.s, "objectives", None), "names", []) or []))
        self._gate_header = [
            "run_id",
            "batch_idx",
            "n_total",
            "n_fast",
            "n_gold",
            "n_fast_only",
            "n_gold_from_fast",
            "n_gold_from_surrogate",
            "n_surrogate_only",
            "gold_padded",
            "gold_pad_count",
            "fast_rule",
            "uncertainty_quantile",
            "fraction_max",
            "fast_fraction_eff",
            "gold_min_points_eff",
            "surrogate_compatible",
            "t_surrogate",
            "t_fast",
            "t_gold",
        ]
        hv_cols = [f"hv_ref_{j}" for j in range(self._n_obj)]
        self._audit_header = [
            "run_id",
            "batch_idx",
            "audit_mode",
            "n_total",
            "n_fast",
            "n_gold",
            "n_gold_from_fast",
            "n_gold_from_surrogate",
            "gold_indices_json",
            "t_gold_s",
            *hv_cols,
            "hv_before",
            "hv_gold",
            "hv_error",
            "hv_valid",
            "hv_reason",
            "epsilon_before_to_gold",
            "abs_err_mean",
            "abs_err_max",
            "rel_err_mean",
            "rel_err_max",
            "abs_err_mean_by_obj_json",
            "rel_err_mean_by_obj_json",
            "rank_corr",
            "rank_valid",
            "control_enabled",
            "metric_value",
            "control_target",
            "fast_fraction_before",
            "fast_fraction_after",
            "gold_min_points_before",
            "gold_min_points_after",
            "control_action",
            "guard_threshold",
            "guard_bad_streak",
            "guard_triggered",
        ]

        self.control_cfg = getattr(self.gating, "control", None) or self._default_control_cfg()
        self.guard_cfg = getattr(self.gating, "guard", None) or self._default_guard_cfg()
        self.control_enabled = bool(getattr(self.control_cfg, "enabled", False))
        self.guard_enabled = bool(getattr(self.guard_cfg, "enabled", True))

        baseline_fast = float(getattr(self.gating.fast, "fraction_max", 0.05))
        baseline_gold = int(getattr(self.gating.gold, "min_points", 1))
        self.baseline_budget = BudgetState(fast_fraction=baseline_fast, gold_min_points=baseline_gold)
        self.budget_state = BudgetState(fast_fraction=baseline_fast, gold_min_points=baseline_gold)
        self.controller = BudgetController(self.control_cfg, self.baseline_budget)
        self.guard = FidelityGuard(self.guard_cfg)

        self.signature_dict = build_signature_dict(
            self.s,
            surrogate_meta_hint={
                "targets": list(getattr(self._surrogate, "_targets", []) or []),
                "feature_names": list(getattr(self._surrogate, "feature_names", []) or []),
                "feature_encoding": dict(getattr(self._surrogate, "feature_encoding", {}) or {}),
                "profile_id": getattr(self._surrogate, "profile_id", None),
                "system_id": getattr(self._surrogate, "system_id", None),
            },
            system_context={
                "runtime_targets": list(getattr(self._surrogate, "_targets", []) or []),
                "feature_names": list(getattr(self._surrogate, "feature_names", []) or []),
                "feature_encoding": dict(getattr(self._surrogate, "feature_encoding", {}) or {}),
                "profile_id": getattr(self._surrogate, "profile_id", None),
                "system_id": getattr(self._surrogate, "system_id", None),
            },
        )
        self.signature_hash = signature_hash(self.signature_dict)
        self._artifact_signature_hash: Optional[str] = None
        self._artifact_status = "unknown"
        self._signature_mismatch_msg = ""
        self.surrogate_compatible = True

        if self.run_dir:
            self._ensure_run_dir()
            self._write_manifest()
            self._check_signature_and_compatibility()

        if not self.surrogate_compatible:
            self._apply_mismatch_fallbacks()

    # -------------------- public API --------------------
    def evaluate(self, X: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
        X = np.asarray(X, float)
        if X.ndim == 1:
            X = X.reshape(1, -1)

        self._batch_idx += 1

        if self.surrogate_compatible:
            t0 = time.perf_counter()
            F_s, G_s = self._surrogate.evaluate(X)
            t_sur = time.perf_counter() - t0
        else:
            t_sur = 0.0
            F_s, G_s = self._evaluate_subset_with_flows(self._fast, X, np.arange(X.shape[0], dtype=int), source="fast")

        F = np.array(F_s, copy=True)
        G = np.array(G_s, copy=True)

        n_total = X.shape[0]
        n_fast = 0
        n_gold = 0
        t_fast = 0.0
        t_gold = 0.0

        fast_indices: np.ndarray = np.array([], dtype=int)
        gold_indices: np.ndarray = np.array([], dtype=int)
        u_scores: Optional[np.ndarray] = None
        fast_idx_set: set[int] = set()
        gold_padded = 0
        gold_pad_count = 0

        fast_active = self.gating.enabled and self.gating.fast.enabled and n_total > 0 and self.surrogate_compatible
        if fast_active:
            fast_indices, u_scores = self._select_fast_indices(X, F_s, fast_fraction=self.budget_state.fast_fraction)
            if fast_indices.size:
                t0 = time.perf_counter()
                F_fast, G_fast = self._evaluate_subset_with_flows(self._fast, X, fast_indices, source="fast")
                t_fast = time.perf_counter() - t0

                F[fast_indices, :] = F_fast
                if G.shape[1]:
                    G[fast_indices, :] = G_fast

                n_fast = int(fast_indices.size)
                self._n_fast_total += n_fast
                fast_idx_set = set(int(i) for i in fast_indices.tolist())

        gold_active = self.gating.enabled and self.gating.gold.enabled and n_total > 0
        gold_triggered = gold_active and self._gold_triggered()
        if gold_triggered:
            gold_indices = self._select_gold_indices(X, F)
            min_points_eff = min(int(self.budget_state.gold_min_points), int(n_total))
            if gold_indices.size < min_points_eff:
                gold_padded = 1
                gold_pad_count = int(min_points_eff - gold_indices.size)
                gold_indices = self._pad_gold_indices(
                    gold_indices,
                    n_total=n_total,
                    fast_indices=fast_indices,
                    u_scores=u_scores,
                    F=F,
                    min_points=min_points_eff,
                )
            if gold_indices.size and self._gold is not None:
                F_before = F[gold_indices, :].copy()

                t0 = time.perf_counter()
                F_gold, G_gold = self._evaluate_subset_with_flows(self._gold, X, gold_indices, source="gold")
                t_gold = time.perf_counter() - t0

                F[gold_indices, :] = F_gold
                if G.shape[1]:
                    G[gold_indices, :] = G_gold

                n_gold = int(gold_indices.size)
                self._n_gold_total += n_gold

                if self.gating.audit is not None and self.gating.audit.enabled:
                    audit = self._compute_audit_metrics(F_before, F_gold)
                    gold_idx_list = [int(i) for i in gold_indices.tolist()]
                    n_gold_from_fast = sum(1 for i in gold_idx_list if i in fast_idx_set)
                    n_gold_from_surrogate = int(n_gold) - int(n_gold_from_fast)

                    metric_value = float(audit["hv_error"])
                    budget_before = BudgetState(
                        fast_fraction=float(self.budget_state.fast_fraction),
                        gold_min_points=int(self.budget_state.gold_min_points),
                    )
                    control_action = "none"
                    if self.control_enabled and not math.isnan(metric_value):
                        budget_after, _ctrl_state, control_action = self.controller.update(metric_value, self.budget_state)
                        self.budget_state = budget_after
                    budget_after = BudgetState(
                        fast_fraction=float(self.budget_state.fast_fraction),
                        gold_min_points=int(self.budget_state.gold_min_points),
                    )

                    guard_threshold = float(getattr(self.guard_cfg, "threshold", 0.40))
                    guard_bad_streak = int(getattr(self.guard.state, "bad_streak", 0))
                    guard_triggered = 0
                    if self.guard_enabled and not math.isnan(metric_value):
                        guard_state, triggered, message = self.guard.update(metric_value, run_id=self.run_id)
                        guard_bad_streak = int(guard_state.bad_streak)
                        guard_triggered = int(triggered)
                        if triggered and message:
                            print(message)
                            write_summary_line(self.run_dir, message)
                            update_manifest_json(
                                self.run_dir,
                                {
                                    "guard_last": {
                                        "metric": "hv_error",
                                        "value": metric_value,
                                        "threshold": guard_threshold,
                                        "bad_streak": guard_bad_streak,
                                        "triggered": bool(triggered),
                                    }
                                },
                            )

                    row = {
                        "run_id": self.run_id,
                        "batch_idx": self._batch_idx,
                        "audit_mode": str(self.gating.gold.mode),
                        "n_total": int(n_total),
                        "n_fast": int(n_fast),
                        "n_gold": int(n_gold),
                        "n_gold_from_fast": int(n_gold_from_fast),
                        "n_gold_from_surrogate": int(n_gold_from_surrogate),
                        "gold_indices_json": json.dumps(gold_idx_list),
                        "t_gold_s": float(t_gold),
                    }
                    for j, v in enumerate(audit["hv_ref_point"].tolist()):
                        row[f"hv_ref_{j}"] = float(v)
                    row.update(
                        {
                            "hv_before": float(audit["hv_before"]),
                            "hv_gold": float(audit["hv_gold"]),
                            "hv_error": float(audit["hv_error"]),
                            "hv_valid": int(audit["hv_valid"]),
                            "hv_reason": str(audit["hv_reason"]),
                            "epsilon_before_to_gold": float(audit["epsilon_before_to_gold"]),
                            "abs_err_mean": float(audit["abs_err_mean"]),
                            "abs_err_max": float(audit["abs_err_max"]),
                            "rel_err_mean": float(audit["rel_err_mean"]),
                            "rel_err_max": float(audit["rel_err_max"]),
                            "abs_err_mean_by_obj_json": audit["abs_err_mean_by_obj_json"],
                            "rel_err_mean_by_obj_json": audit["rel_err_mean_by_obj_json"],
                            "rank_corr": float(audit["rank_corr"]),
                            "rank_valid": int(audit["rank_valid"]),
                            "control_enabled": int(self.control_enabled),
                            "metric_value": metric_value,
                            "control_target": float(getattr(self.control_cfg, "target", 0.25)),
                            "fast_fraction_before": float(budget_before.fast_fraction),
                            "fast_fraction_after": float(budget_after.fast_fraction),
                            "gold_min_points_before": int(budget_before.gold_min_points),
                            "gold_min_points_after": int(budget_after.gold_min_points),
                            "control_action": control_action,
                            "guard_threshold": guard_threshold,
                            "guard_bad_streak": int(guard_bad_streak),
                            "guard_triggered": int(guard_triggered),
                        }
                    )
                    self._append_audit_log(row)

        # Disjoint fidelity counts per batch (correct under FAST-GOLD overlap)
        fast_set = set(int(i) for i in fast_indices.tolist())
        gold_set = set(int(i) for i in gold_indices.tolist())
        inter_set = fast_set & gold_set
        union_set = fast_set | gold_set

        n_fast = int(len(fast_set))
        n_gold = int(len(gold_set))
        n_gold_from_fast = int(len(inter_set))
        n_gold_from_surrogate = int(n_gold - n_gold_from_fast)
        n_fast_only = int(n_fast - n_gold_from_fast)
        n_surrogate_only = int(n_total - len(union_set))

        self._append_gate_log(
            {
                "run_id": self.run_id,
                "batch_idx": self._batch_idx,
                "n_total": int(n_total),
                "n_fast": int(n_fast),
                "n_gold": int(n_gold),
                "n_fast_only": n_fast_only,
                "n_gold_from_fast": n_gold_from_fast,
                "n_gold_from_surrogate": n_gold_from_surrogate,
                "n_surrogate_only": n_surrogate_only,
                "gold_padded": int(gold_padded),
                "gold_pad_count": int(gold_pad_count),
                "fast_rule": str(self.gating.fast.rule),
                "uncertainty_quantile": float(self.gating.fast.uncertainty_quantile),
                "fraction_max": float(self.gating.fast.fraction_max),
                "fast_fraction_eff": float(self.budget_state.fast_fraction),
                "gold_min_points_eff": int(self.budget_state.gold_min_points),
                "surrogate_compatible": int(self.surrogate_compatible),
                "t_surrogate": float(t_sur),
                "t_fast": float(t_fast),
                "t_gold": float(t_gold),
            }
        )

        if self.gating.retrain.enabled:
            self._maybe_retrain()

        return F, G

    def run(self, run_dir: str) -> Dict[str, Any]:
        self.run_dir = run_dir
        self.run_id = Path(run_dir).name if run_dir else "unknown_run"
        self._ensure_run_dir()
        try:
            self._surrogate.run(run_dir)
        except Exception:
            pass
        self._write_manifest()
        self._check_signature_and_compatibility()
        if not self.surrogate_compatible:
            self._apply_mismatch_fallbacks()
        return {"ok": True, "run_dir": str(run_dir)}

    # -------------------- gating helpers --------------------
    def _select_fast_indices(self, X: np.ndarray, F: np.ndarray, fast_fraction: float) -> Tuple[np.ndarray, Optional[np.ndarray]]:
        rule = str(self.gating.fast.rule).lower()
        n = X.shape[0]
        if n == 0:
            return np.array([], dtype=int), None

        u_scores: Optional[np.ndarray] = None
        mask = np.zeros(n, dtype=bool)

        if "uncertainty" in rule:
            u_scores = self._uncertainty_scores(X)
            q = float(self.gating.fast.uncertainty_quantile)
            thresh = np.quantile(u_scores, q) if n > 0 else np.inf
            mask |= u_scores >= thresh

        if "pareto" in rule:
            F_min = self._to_minimization(F)
            mask |= self._nondominated_mask(F_min)

        indices = np.where(mask)[0]
        indices = self._apply_fast_caps(indices, u_scores, n, fast_fraction=fast_fraction)
        return indices, u_scores

    def _select_gold_indices(self, X: np.ndarray, F: np.ndarray) -> np.ndarray:
        mode = str(self.gating.gold.mode).lower()
        n = X.shape[0]
        if n == 0:
            return np.array([], dtype=int)

        if mode == "periodic":
            period = int(self.gating.gold.period_batches)
            if period <= 0 or (self._batch_idx % period) != 0:
                return np.array([], dtype=int)
        elif mode in {"finalists", "periodic+finalists"}:
            pass
        else:
            raise ValueError(f"[gated] unknown gold.mode='{self.gating.gold.mode}'")

        nd_indices = self._nondominated_indices(F)
        if nd_indices.size == 0:
            return np.array([], dtype=int)

        n_gold_target = int(math.ceil(float(self.gating.gold.fraction_max) * n))
        n_gold_target = max(int(self.budget_state.gold_min_points), n_gold_target)

        finalists_k = int(self.gating.gold.finalists_k)
        if finalists_k > 0:
            n_gold_target = min(n_gold_target, finalists_k)

        n_gold_target = min(n_gold_target, int(nd_indices.size))
        if n_gold_target <= 0:
            return np.array([], dtype=int)

        return self._lexicographic_select(F, nd_indices, n_gold_target)

    def _gold_triggered(self) -> bool:
        mode = str(self.gating.gold.mode).lower()
        if mode == "periodic":
            period = int(self.gating.gold.period_batches)
            return period > 0 and (self._batch_idx % period) == 0
        if mode in {"finalists", "periodic+finalists"}:
            return True
        return False

    def _pad_gold_indices(
        self,
        gold_indices: np.ndarray,
        n_total: int,
        fast_indices: np.ndarray,
        u_scores: Optional[np.ndarray],
        F: np.ndarray,
        min_points: int,
    ) -> np.ndarray:
        gold_set = set(int(i) for i in gold_indices.tolist())
        if len(gold_set) >= min_points:
            return gold_indices

        remaining = [i for i in range(int(n_total)) if i not in gold_set]
        padded: List[int] = []

        fast_list = [int(i) for i in fast_indices.tolist() if int(i) in remaining]
        if fast_list:
            take = min(len(fast_list), max(0, min_points - len(gold_set)))
            padded.extend(fast_list[:take])
            gold_set.update(padded)
            remaining = [i for i in remaining if i not in gold_set]

        if len(gold_set) < min_points and u_scores is not None:
            remaining_sorted = sorted(remaining, key=lambda i: float(u_scores[i]), reverse=True)
            take = min(len(remaining_sorted), max(0, min_points - len(gold_set)))
            padded.extend(remaining_sorted[:take])
            gold_set.update(remaining_sorted[:take])
            remaining = [i for i in remaining if i not in gold_set]

        if len(gold_set) < min_points and remaining:
            F_min = self._to_minimization(F)
            rem = np.array(remaining, dtype=int)
            F_rem = F_min[rem, :]
            keys = [F_rem[:, j] for j in reversed(range(F_rem.shape[1]))]
            order = np.lexsort(keys)
            take = min(len(order), max(0, min_points - len(gold_set)))
            padded.extend([int(rem[i]) for i in order[:take]])
            gold_set.update(int(rem[i]) for i in order[:take])

        return np.array(sorted(gold_set), dtype=int)

    def _apply_fast_caps(
        self,
        indices: np.ndarray,
        u_scores: Optional[np.ndarray],
        n_total: int,
        fast_fraction: float,
    ) -> np.ndarray:
        idx = list(indices.tolist())
        idx_set = set(idx)

        min_points = max(0, int(self.gating.fast.min_points))
        min_points = min(min_points, n_total)

        max_allowed = n_total
        fraction_max = float(fast_fraction)
        if fraction_max > 0.0:
            max_allowed = min(max_allowed, int(np.floor(fraction_max * n_total)))
        if self.gating.fast.max_points is not None:
            max_allowed = min(max_allowed, int(self.gating.fast.max_points))

        if max_allowed < min_points:
            max_allowed = min_points

        if len(idx) < min_points:
            remaining = [i for i in range(n_total) if i not in idx_set]
            if u_scores is not None:
                remaining = sorted(remaining, key=lambda i: u_scores[i], reverse=True)
            idx.extend(remaining[: max(0, min_points - len(idx))])

        if len(idx) > max_allowed:
            if u_scores is not None:
                idx = sorted(idx, key=lambda i: u_scores[i], reverse=True)[:max_allowed]
            else:
                idx = sorted(idx)[:max_allowed]

        return np.array(sorted(set(idx)), dtype=int)

    def _uncertainty_scores(self, X: np.ndarray) -> np.ndarray:
        models = list(getattr(self._surrogate, "_models_F", []))
        if not models:
            return np.zeros((X.shape[0],), dtype=float)

        X_feat = X
        augment = getattr(self._surrogate, "_augment_features", None)
        if callable(augment):
            X_feat = augment(X)

        variances: List[np.ndarray] = []
        for m in models:
            estimators = getattr(m, "estimators_", None)
            if not estimators:
                return np.zeros((X.shape[0],), dtype=float)
            preds = np.column_stack([t.predict(X_feat) for t in estimators])
            variances.append(np.var(preds, axis=1))

        return np.mean(np.column_stack(variances), axis=1)

    def _nondominated_mask(self, F_min: np.ndarray) -> np.ndarray:
        n = F_min.shape[0]
        mask = np.ones(n, dtype=bool)
        for i in range(n):
            if not mask[i]:
                continue
            for j in range(n):
                if i == j or not mask[j]:
                    continue
                if np.all(F_min[j] <= F_min[i]) and np.any(F_min[j] < F_min[i]):
                    mask[i] = False
                    break
        return mask

    def _top_k_indices(self, F: np.ndarray, k: int) -> np.ndarray:
        if k <= 0 or F.size == 0:
            return np.array([], dtype=int)
        F_min = self._to_minimization(F)
        scores = np.sum(F_min, axis=1)
        order = np.argsort(scores)
        return order[:k]

    def _to_minimization(self, F: np.ndarray) -> np.ndarray:
        minimize = list(getattr(getattr(self.s, "objectives", None), "minimize", []))
        if not minimize:
            minimize = [True] * F.shape[1]
        signs = np.array([1.0 if m else -1.0 for m in minimize], dtype=float)
        return F * signs.reshape(1, -1)

    def _nondominated_indices(self, F: np.ndarray) -> np.ndarray:
        if F.size == 0:
            return np.array([], dtype=int)
        F_min = self._to_minimization(F)
        mask = self._nondominated_mask(F_min)
        return np.where(mask)[0]

    def _lexicographic_select(self, F: np.ndarray, indices: np.ndarray, k: int) -> np.ndarray:
        if k <= 0 or indices.size == 0:
            return np.array([], dtype=int)
        F_min = self._to_minimization(F[indices, :])
        keys = [F_min[:, j] for j in reversed(range(F_min.shape[1]))]
        order = np.lexsort(keys)
        return indices[order[:k]]

    # -------------------- truth + retrain --------------------
    def _evaluate_subset_with_flows(
        self,
        engine: Any,
        X: np.ndarray,
        indices: np.ndarray,
        source: str,
    ) -> Tuple[np.ndarray, np.ndarray]:
        F_rows: List[np.ndarray] = []
        G_rows: List[np.ndarray] = []

        for idx in indices:
            F_i, G_i, flows = engine.evaluate_one_with_flows(X[idx, :])
            F_rows.append(F_i.reshape(-1))
            G_rows.append(G_i.reshape(-1))
            self._record_truth_point(X[idx, :], flows, source=source)

        obj_names = list(getattr(getattr(self.s, "objectives", None), "names", []))
        con_names = list(getattr(getattr(self.s, "constraints", None), "names", []))

        F_out = np.vstack(F_rows) if F_rows else np.zeros((0, len(obj_names)), float)
        if con_names:
            G_out = np.vstack(G_rows) if G_rows else np.zeros((0, len(con_names)), float)
        else:
            G_out = np.zeros((F_out.shape[0], 0), float)
        return F_out, G_out

    def _record_truth_point(self, x: np.ndarray, flows: Dict[str, float], source: str) -> None:
        targets = list(getattr(self._surrogate, "_targets", []))
        obj_names = set(get_selected_objective_names(self.s))
        objectives: Dict[str, float] = {}
        if any(t in obj_names for t in targets):
            design_vars = self._surrogate._build_design_vars(float(x[0]), float(x[1]))
            objectives, _constraints, _ctx = compute_kpis(flows, design_vars, self.s, getattr(self._surrogate, "profiles", None))
        y = np.array([float(objectives[t]) if t in objectives else float(flows.get(t, 0.0)) for t in targets], dtype=float)

        self._truth_X.append(np.array(x, copy=True))
        self._truth_Y.append(y)
        self._truth_source.append(source)

        if self.run_dir:
            self._append_truth_csv(x, y, targets, source)

    def _maybe_retrain(self) -> None:
        if not self.gating.retrain.enabled:
            return

        sources = str(self.gating.retrain.source).lower()
        allowed = {"fast", "gold", "fast+gold"}
        if sources not in allowed:
            raise ValueError(f"[gated] unknown retrain.source='{self.gating.retrain.source}'")

        use_sources = {"gold"}
        X, Y = self._truth_dataset(use_sources)
        if X is None or Y is None:
            return

        n_truth = X.shape[0]
        if n_truth < int(self.gating.retrain.min_truth_points):
            return

        every_n_fast = int(self.gating.retrain.every_n_fast)
        every_n_batches = int(self.gating.retrain.every_n_batches)

        trigger = False
        if every_n_fast > 0 and (self._n_fast_total - self._last_retrain_fast_count) >= every_n_fast:
            trigger = True
        if every_n_batches > 0 and (self._batch_idx - self._last_retrain_batch) >= every_n_batches:
            trigger = True

        if trigger:
            self._retrain_surrogate(reason="schedule")

    def _truth_dataset(self, sources: set[str]) -> Tuple[Optional[np.ndarray], Optional[np.ndarray]]:
        if not self._truth_X:
            return None, None

        idx = [i for i, s in enumerate(self._truth_source) if s in sources]
        if not idx:
            return None, None
        X = np.vstack([self._truth_X[i] for i in idx])
        Y = np.vstack([self._truth_Y[i] for i in idx])
        return X, Y

    def _retrain_surrogate(self, reason: str) -> None:
        from sklearn.ensemble import RandomForestRegressor

        sources = str(self.gating.retrain.source).lower()
        use_sources = {"gold"}
        X, Y = self._truth_dataset(use_sources)
        if X is None or Y is None:
            return

        n_truth = X.shape[0]
        if n_truth < int(self.gating.retrain.min_truth_points):
            return

        targets = list(getattr(self._surrogate, "_targets", []))
        st = getattr(self.s, "surrogate_train", None)
        n_estimators = int(getattr(st, "rf_n_estimators", 300))
        n_jobs = int(getattr(st, "rf_n_jobs", -1))
        seed = int(getattr(getattr(self.s, "engine", None), "rng_seed", 0))

        X_feat = self._surrogate._augment_features(X)
        models: List[Any] = []
        for j in range(Y.shape[1]):
            m = RandomForestRegressor(n_estimators=n_estimators, n_jobs=n_jobs, random_state=seed)
            m.fit(X_feat, Y[:, j])
            models.append(m)

        self._surrogate._models_F = models
        self._surrogate._targets = targets
        print(f"[gated][retrain] RETRAIN TRIGGERED reason={reason} n_truth={int(n_truth)} n_features={int(X_feat.shape[1])} HOTSWAP DONE")

        self._last_retrain_fast_count = self._n_fast_total
        self._last_retrain_batch = self._batch_idx

        if self.gating.retrain.save_artifacts and self.run_dir:
            version_dir = self._next_surrogate_version_dir()
            version_dir.mkdir(parents=True, exist_ok=True)
            artifact_path = version_dir / "surrogate_rf.joblib"
            dump({"targets": targets, "models": models}, artifact_path)

            meta = {
                "created_at": _now_iso(),
                "reason": reason,
                "n_truth": int(n_truth),
                "sources": sorted(use_sources),
                "targets": targets,
                "signature_hash": self.signature_hash,
                "signature_dict": self.signature_dict,
                "feature_names": list(getattr(self._surrogate, "feature_names", []) or []),
                "feature_encoding": dict(getattr(self._surrogate, "feature_encoding", {}) or {}),
                "profile_id": getattr(self._surrogate, "profile_id", None),
                "system_id": getattr(self._surrogate, "system_id", None),
            }
            (version_dir / "meta.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")

            self._surrogate._artifact_path = artifact_path
            self._surrogate._artifact_dir = version_dir
            self._surrogate_versions.append(str(version_dir))
            self._artifact_signature_hash = self.signature_hash
            self._write_manifest()
            promote_surrogate_version(self.signature_hash, version_dir, self.run_dir)

    # -------------------- audit --------------------
    def _compute_audit_metrics(self, F_before: np.ndarray, F_gold: np.ndarray) -> Dict[str, float]:
        F_b = self._to_minimization(F_before)
        F_g = self._to_minimization(F_gold)

        ref_candidate = np.max(np.vstack([F_b, F_g]), axis=0)
        ref_point = (1.0 + float(self.gating.audit.ref_margin)) * ref_candidate
        if self.hv_ref_point is None:
            self.hv_ref_point = ref_point
        else:
            self.hv_ref_point = np.maximum(self.hv_ref_point, ref_point)

        hv_before = float("nan")
        hv_gold = float("nan")
        hv_error = float("nan")
        hv_reason = ""
        hv_valid = bool(F_gold.shape[0] >= 2)
        if not hv_valid:
            hv_reason = "too_few_gold"
        elif not np.all(np.isfinite(self.hv_ref_point)):
            hv_valid = False
            hv_reason = "ref_point_invalid"
        else:
            try:
                from pymoo.indicators.hv import HV

                hv = HV(ref_point=self.hv_ref_point)
                hv_before = float(hv(F_b))
                hv_gold = float(hv(F_g))
                hv_error = float(abs(hv_gold - hv_before) / max(abs(hv_gold), 1e-9))
            except Exception:
                hv_valid = False
                hv_reason = "hv_failed_exception"

        epsilon_before_to_gold = float(self._epsilon_indicator(F_b, F_g))

        score_before = np.sum(F_before, axis=1)
        score_gold = np.sum(F_gold, axis=1)
        rank_method = str(self.gating.audit.rank_method).lower()
        rank_valid = bool(F_gold.shape[0] >= 2)
        if rank_valid:
            if rank_method == "kendall":
                rank_corr = float(self._kendall_tau_b(score_before, score_gold))
            else:
                rank_corr = float(self._spearman_corr(score_before, score_gold))
        else:
            rank_corr = float("nan")

        absD = np.abs(F_gold - F_before)
        abs_err_mean = float(np.mean(absD)) if absD.size else float("nan")
        abs_err_max = float(np.max(absD)) if absD.size else float("nan")
        denom = np.maximum(np.abs(F_gold), 1e-9)
        relD = absD / denom
        rel_err_mean = float(np.mean(relD)) if relD.size else float("nan")
        rel_err_max = float(np.max(relD)) if relD.size else float("nan")

        abs_err_mean_by_obj = np.mean(absD, axis=0) if absD.size else np.array([], dtype=float)
        rel_err_mean_by_obj = np.mean(relD, axis=0) if relD.size else np.array([], dtype=float)

        return {
            "hv_ref_point": self.hv_ref_point.copy(),
            "hv_before": hv_before,
            "hv_gold": hv_gold,
            "hv_error": hv_error,
            "hv_valid": hv_valid,
            "hv_reason": hv_reason,
            "epsilon_before_to_gold": epsilon_before_to_gold,
            "abs_err_mean": abs_err_mean,
            "abs_err_max": abs_err_max,
            "rel_err_mean": rel_err_mean,
            "rel_err_max": rel_err_max,
            "abs_err_mean_by_obj_json": json.dumps([float(v) for v in abs_err_mean_by_obj.tolist()]),
            "rel_err_mean_by_obj_json": json.dumps([float(v) for v in rel_err_mean_by_obj.tolist()]),
            "rank_corr": rank_corr,
            "rank_valid": rank_valid,
        }

    def _epsilon_indicator(self, A: np.ndarray, B: np.ndarray) -> float:
        if A.size == 0 or B.size == 0:
            return float("nan")
        eps = -float("inf")
        for i in range(B.shape[0]):
            eps_i = float("inf")
            for j in range(A.shape[0]):
                eps_j = float(np.max(A[j, :] - B[i, :]))
                if eps_j < eps_i:
                    eps_i = eps_j
            if eps_i > eps:
                eps = eps_i
        return float(eps)

    def _spearman_corr(self, x: np.ndarray, y: np.ndarray) -> float:
        if x.size == 0 or y.size == 0:
            return float("nan")
        rx = self._rankdata(x)
        ry = self._rankdata(y)
        mx = float(np.mean(rx))
        my = float(np.mean(ry))
        sx = float(np.sum((rx - mx) ** 2))
        sy = float(np.sum((ry - my) ** 2))
        denom = math.sqrt(sx * sy)
        if denom == 0.0:
            return 0.0
        return float(np.sum((rx - mx) * (ry - my)) / denom)

    def _kendall_tau_b(self, x: np.ndarray, y: np.ndarray) -> float:
        n = int(x.size)
        if n < 2:
            return 1.0
        concordant = 0
        discordant = 0
        ties_x = 0
        ties_y = 0
        for i in range(n - 1):
            for j in range(i + 1, n):
                dx = np.sign(x[i] - x[j])
                dy = np.sign(y[i] - y[j])
                if dx == 0 and dy == 0:
                    continue
                if dx == 0:
                    ties_x += 1
                    continue
                if dy == 0:
                    ties_y += 1
                    continue
                if dx == dy:
                    concordant += 1
                else:
                    discordant += 1
        denom = math.sqrt((concordant + discordant + ties_x) * (concordant + discordant + ties_y))
        if denom == 0.0:
            return 0.0
        return float((concordant - discordant) / denom)

    def _rankdata(self, values: np.ndarray) -> np.ndarray:
        n = int(values.size)
        order = np.argsort(values, kind="mergesort")
        ranks = np.empty(n, dtype=float)
        i = 0
        while i < n:
            j = i
            v = values[order[i]]
            while j + 1 < n and values[order[j + 1]] == v:
                j += 1
            rank = 0.5 * (i + j) + 1.0
            ranks[order[i : j + 1]] = rank
            i = j + 1
        return ranks

    # -------------------- logging + manifest --------------------
    def _ensure_run_dir(self) -> None:
        if self.run_dir:
            Path(self.run_dir).mkdir(parents=True, exist_ok=True)

    def _write_manifest(self) -> None:
        if not self.run_dir:
            return
        out = Path(self.run_dir) / "gating_manifest.json"

        payload = {
            "created_at": _now_iso(),
            "gating": asdict(self.gating),
            "seeds": {
                "engine_rng_seed": int(getattr(getattr(self.s, "engine", None), "rng_seed", 0)),
                "sampler_seed": int(getattr(getattr(self.s, "sampler", None), "seed", 0)),
                "optimizer_seed": int(getattr(getattr(self.s, "optimizer", None), "seed", 0)),
            },
            "surrogate_targets": list(getattr(self._surrogate, "_targets", [])),
            "surrogate_versions": list(self._surrogate_versions),
            "signature": {
                "hash": self.signature_hash,
                "dict": self.signature_dict,
                "artifact_hash": self._artifact_signature_hash,
                "artifact_status": self._artifact_status,
                "surrogate_compatible": bool(self.surrogate_compatible),
                "mismatch": self._signature_mismatch_msg,
            },
            "budgets": {
                "baseline_fast_fraction": float(self.baseline_budget.fast_fraction),
                "baseline_gold_min_points": int(self.baseline_budget.gold_min_points),
                "fast_fraction": float(self.budget_state.fast_fraction),
                "gold_min_points": int(self.budget_state.gold_min_points),
            },
        }
        existing = self._load_json(out) if out.exists() else {}
        existing.update(payload)
        out.write_text(json.dumps(existing, indent=2), encoding="utf-8")

    def _append_gate_log(self, row: Dict[str, Any]) -> None:
        if not self.run_dir:
            return
        path = Path(self.run_dir) / "gate_log.csv"
        append_csv(path, self._gate_header, row)

    def _append_audit_log(self, row: Dict[str, Any]) -> None:
        if not self.run_dir:
            return
        path = Path(self.run_dir) / "audit_log.csv"
        append_csv(path, self._audit_header, row)

    def _append_truth_csv(self, x: np.ndarray, y: np.ndarray, targets: List[str], source: str) -> None:
        if not self.run_dir:
            return
        path = Path(self.run_dir) / "truth_dataset.csv"

        names = list(getattr(getattr(self.s, "bounds", None), "names", []))
        if not names:
            names = [f"x{i}" for i in range(len(x))]

        header = ["run_id", "signature_hash", "source", *names, *targets]
        row = {names[i]: float(x[i]) for i in range(len(x))}
        row["run_id"] = self.run_id
        row["signature_hash"] = self.signature_hash
        row["source"] = source
        for i, t in enumerate(targets):
            row[t] = float(y[i])

        append_csv(path, header, row)

    def _next_surrogate_version_dir(self) -> Path:
        base = Path(self.run_dir) / str(self.gating.retrain.artifact_dirname)
        base.mkdir(parents=True, exist_ok=True)
        idx = len(self._surrogate_versions) + 1
        return base / f"v{idx:03d}"

    # -------------------- control + guards + signature --------------------
    def _default_control_cfg(self):
        class _Cfg:
            enabled = False
            metric = "hv_error"
            target = 0.25
            patience = 2
            fast_step = 0.05
            fast_cap = 0.40
            gold_step_points = 5
            gold_cap_points = 30

        return _Cfg()

    def _default_guard_cfg(self):
        class _Cfg:
            enabled = True
            metric = "hv_error"
            threshold = 0.40
            patience = 3
            action = "warn"
            print_every = 1

        return _Cfg()

    def _load_json(self, path: Path) -> Dict[str, Any]:
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            return {}

    def _latest_surrogate_meta(self) -> Dict[str, Any]:
        if not self.run_dir:
            return {}
        base = Path(self.run_dir) / str(getattr(self.gating.retrain, "artifact_dirname", "surrogate_versions"))
        if not base.exists():
            return {}
        metas = sorted(base.glob("v*/meta.json"))
        if not metas:
            return {}
        return self._load_json(metas[-1])

    def _check_signature_and_compatibility(self) -> None:
        if not self.run_dir:
            return
        meta_hint_path = Path(self.run_dir) / "surrogate_meta_hint.json"
        meta_hint = self._load_json(meta_hint_path) if meta_hint_path.exists() else {}
        latest_meta = self._latest_surrogate_meta()

        artifact_hash = latest_meta.get("signature_hash") or meta_hint.get("signature_hash")
        artifact_dict = latest_meta.get("signature_dict") or meta_hint.get("signature_dict")
        if not artifact_hash and isinstance(artifact_dict, dict):
            artifact_hash = signature_hash(artifact_dict)
        self._artifact_signature_hash = str(artifact_hash) if artifact_hash else None

        artifact_exists = bool(getattr(self._surrogate, "_artifact_path", None)) and Path(self._surrogate._artifact_path).exists()
        mismatch_msg = ""
        status = "unknown"
        compatible = True

        if not artifact_exists:
            compatible = False
            status = "missing_artifact"
            mismatch_msg = "SURROGATE_MISSING artifact not found; running truth-heavier."
        elif self._artifact_signature_hash:
            compatible = is_compatible(self.signature_hash, self._artifact_signature_hash)
            status = "checked"
            if not compatible:
                mismatch_msg = summarize_mismatch(self.signature_dict, artifact_dict if isinstance(artifact_dict, dict) else None)
        else:
            compatible = False
            status = "no_signature"
            mismatch_msg = "SURROGATE_SIGNATURE missing; compatibility not verified. Retrain recommended."

        self.surrogate_compatible = bool(compatible)
        self._artifact_status = status
        self._signature_mismatch_msg = mismatch_msg

        if mismatch_msg:
            warn = f"[gated][signature] run={self.run_id} status={status} {mismatch_msg}"
            print(warn)
            write_summary_line(self.run_dir, warn)

        update_manifest_json(
            self.run_dir,
            {
                "signature": {
                    "hash": self.signature_hash,
                    "dict": self.signature_dict,
                    "artifact_hash": self._artifact_signature_hash,
                    "artifact_status": status,
                    "surrogate_compatible": bool(self.surrogate_compatible),
                    "mismatch": mismatch_msg,
                }
            },
        )

    def _apply_mismatch_fallbacks(self) -> None:
        fast_cap = float(getattr(self.control_cfg, "fast_cap", self.budget_state.fast_fraction))
        gold_cap = int(getattr(self.control_cfg, "gold_cap_points", self.budget_state.gold_min_points))
        fast_fraction = min(max(self.budget_state.fast_fraction, 0.30), fast_cap)
        gold_min_points = min(max(self.budget_state.gold_min_points, 20), gold_cap)
        self.budget_state = BudgetState(fast_fraction=fast_fraction, gold_min_points=gold_min_points)
