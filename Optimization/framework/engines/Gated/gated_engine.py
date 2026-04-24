from __future__ import annotations

import json
import math
import time
from dataclasses import asdict
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
from joblib import dump

from Optimization.framework.hypervolume import compute_hv, hv_mode, resolve_reference_point
from ..Gold.gold_engine import GoldEngine
from ..Surrogat_model.surrogate_engine import SurrogateEngine
from ..kpi import compute_kpis, get_selected_objective_names
from .control import BudgetController, BudgetState
from .guards import FidelityGuard
from .io import append_csv, promote_surrogate_version, update_manifest_json, write_summary_line
from .signature import build_signature_dict, is_compatible, signature_hash, summarize_mismatch


def _now_iso() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%S")


class GatedEngine:
    """Surrogate -> Gold gating engine.

    Surrogate predicts all points and Gold evaluates a selected subset
    based on gating config.
    """

    def __init__(self, settings, run_dir: Optional[str] = None, **kwargs: Any) -> None:
        self.s = settings
        self.run_dir = run_dir
        self.run_id = Path(run_dir).name if run_dir else "unknown_run"
        self.gating = getattr(settings, "gating", None)
        if self.gating is None:
            raise ValueError("[gated] settings.gating fehlt.")

        self._batch_idx = 0
        self._last_retrain_batch = 0
        self._truth_X: List[np.ndarray] = []
        self._truth_Y: List[np.ndarray] = []
        self._truth_source: List[str] = []
        self._surrogate_versions: List[str] = []
        self.hv_ref_point: Optional[np.ndarray] = None

        self._surrogate = SurrogateEngine(settings, run_dir=run_dir)
        self._gold = GoldEngine(settings) if self.gating.gold.enabled else None

        baseline_surrogate = float(getattr(self.gating.surrogate, "fraction_max", 0.05))
        baseline_gold = int(getattr(self.gating.gold, "min_points", 1))
        self.baseline_budget = BudgetState(surrogate_fraction=baseline_surrogate, gold_min_points=baseline_gold)
        self.budget_state = BudgetState(surrogate_fraction=baseline_surrogate, gold_min_points=baseline_gold)
        self.control_cfg = getattr(self.gating, "control", None) or self._default_control_cfg()
        self.guard_cfg = getattr(self.gating, "guard", None) or self._default_guard_cfg()
        self.control_enabled = bool(getattr(self.control_cfg, "enabled", False))
        self.guard_enabled = bool(getattr(self.guard_cfg, "enabled", True))
        self.controller = BudgetController(self.control_cfg, self.baseline_budget)
        self.guard = FidelityGuard(self.guard_cfg)

        self._n_obj = int(len(getattr(getattr(self.s, "objectives", None), "names", []) or []))
        self._gate_header = ["run_id", "batch_idx", "n_total", "n_gold", "n_surrogate_only", "t_surrogate", "t_gold"]
        self._audit_header = ["run_id", "batch_idx", "n_total", "n_gold", "gold_indices_json", "t_gold_s", "hv_before", "hv_gold", "hv_error", "hv_valid", "hv_reason"]
        self.signature_dict = build_signature_dict(
            self.s,
            surrogate_meta_hint={"targets": list(getattr(self._surrogate, "_targets", []) or [])},
            system_context={"runtime_targets": list(getattr(self._surrogate, "_targets", []) or [])},
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

    def evaluate(self, X: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
        X = np.asarray(X, float)
        if X.ndim == 1:
            X = X.reshape(1, -1)
        self._batch_idx += 1
        n_total = X.shape[0]

        t0 = time.perf_counter()
        if self.surrogate_compatible:
            F, G = self._surrogate.evaluate(X)
        else:
            # Explicit failure trigger: full Gold batch.
            F, G = self._evaluate_subset_with_flows(self._gold, X, np.arange(n_total, dtype=int), source="gold")
        t_sur = time.perf_counter() - t0

        gold_indices = np.array([], dtype=int)
        t_gold = 0.0
        if self.gating.enabled and self.gating.gold.enabled and self._gold is not None and self._gold_triggered():
            gold_indices = self._select_gold_indices(F)
            min_points = min(int(self.budget_state.gold_min_points), int(n_total))
            if gold_indices.size < min_points:
                gold_indices = self._pad_gold_indices(gold_indices, n_total=n_total, F=F, min_points=min_points)
            if gold_indices.size:
                F_before = F[gold_indices, :].copy()
                t0 = time.perf_counter()
                F_gold, G_gold = self._evaluate_subset_with_flows(self._gold, X, gold_indices, source="gold")
                t_gold = time.perf_counter() - t0
                F[gold_indices, :] = F_gold
                if G.shape[1]:
                    G[gold_indices, :] = G_gold
                self._write_audit_row(F_before, F_gold, n_total=n_total, gold_indices=gold_indices, t_gold=t_gold)

        self._append_gate_log(
            {
                "run_id": self.run_id,
                "batch_idx": self._batch_idx,
                "n_total": int(n_total),
                "n_gold": int(gold_indices.size),
                "n_surrogate_only": int(max(0, n_total - gold_indices.size)),
                "t_surrogate": float(t_sur),
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
        self._surrogate.run(run_dir)
        self._write_manifest()
        return {"ok": True, "run_dir": str(run_dir)}

    def _evaluate_subset_with_flows(self, engine: Any, X: np.ndarray, indices: np.ndarray, source: str) -> Tuple[np.ndarray, np.ndarray]:
        f_rows: List[np.ndarray] = []
        g_rows: List[np.ndarray] = []
        for idx in indices:
            F_i, G_i, flows = engine.evaluate_one_with_flows(X[idx, :])
            f_rows.append(F_i.reshape(-1))
            g_rows.append(G_i.reshape(-1))
            self._record_truth_point(X[idx, :], flows, source=source)
        obj_names = list(getattr(getattr(self.s, "objectives", None), "names", []))
        con_names = list(getattr(getattr(self.s, "constraints", None), "names", []))
        F_out = np.vstack(f_rows) if f_rows else np.zeros((0, len(obj_names)), float)
        G_out = np.vstack(g_rows) if con_names and g_rows else np.zeros((F_out.shape[0], 0), float)
        return F_out, G_out

    def _record_truth_point(self, x: np.ndarray, flows: Dict[str, float], source: str) -> None:
        targets = list(getattr(self._surrogate, "_targets", []))
        objectives: Dict[str, float] = {}
        if any(t in set(get_selected_objective_names(self.s)) for t in targets):
            design_vars = self._surrogate._build_design_vars(x)
            objectives, _constraints, _ctx = compute_kpis(flows, design_vars, self.s, getattr(self._surrogate, "profiles", None))
        y = np.array([float(objectives[t]) if t in objectives else float(flows.get(t, 0.0)) for t in targets], dtype=float)
        self._truth_X.append(np.array(x, copy=True))
        self._truth_Y.append(y)
        self._truth_source.append(source)
        if self.run_dir:
            names = list(getattr(getattr(self.s, "bounds", None), "names", [])) or [f"x{i}" for i in range(len(x))]
            row = {names[i]: float(x[i]) for i in range(len(x))}
            row.update({"run_id": self.run_id, "signature_hash": self.signature_hash, "source": source})
            for i, t in enumerate(targets):
                row[t] = float(y[i])
            append_csv(Path(self.run_dir) / "truth_dataset.csv", ["run_id", "signature_hash", "source", *names, *targets], row)

    def _select_gold_indices(self, F: np.ndarray) -> np.ndarray:
        nd = self._nondominated_indices(F)
        if nd.size == 0:
            return np.array([], dtype=int)
        n_total = F.shape[0]
        k = int(math.ceil(float(self.gating.gold.fraction_max) * n_total))
        k = max(int(self.budget_state.gold_min_points), k)
        if int(self.gating.gold.finalists_k) > 0:
            k = min(k, int(self.gating.gold.finalists_k))
        k = min(k, int(nd.size))
        return self._lexicographic_select(F, nd, k)

    def _gold_triggered(self) -> bool:
        mode = str(self.gating.gold.mode).lower()
        if mode == "periodic":
            period = int(self.gating.gold.period_batches)
            return period > 0 and (self._batch_idx % period) == 0
        if mode in {"finalists", "periodic+finalists"}:
            return True
        raise ValueError(f"[gated] unknown gold.mode='{self.gating.gold.mode}'")

    def _to_minimization(self, F: np.ndarray) -> np.ndarray:
        minimize = list(getattr(getattr(self.s, "objectives", None), "minimize", [])) or [True] * F.shape[1]
        signs = np.array([1.0 if m else -1.0 for m in minimize], dtype=float)
        return F * signs.reshape(1, -1)

    def _nondominated_indices(self, F: np.ndarray) -> np.ndarray:
        if F.size == 0:
            return np.array([], dtype=int)
        Fm = self._to_minimization(F)
        n = Fm.shape[0]
        mask = np.ones(n, dtype=bool)
        for i in range(n):
            if not mask[i]:
                continue
            for j in range(n):
                if i != j and mask[j] and np.all(Fm[j] <= Fm[i]) and np.any(Fm[j] < Fm[i]):
                    mask[i] = False
                    break
        return np.where(mask)[0]

    def _lexicographic_select(self, F: np.ndarray, indices: np.ndarray, k: int) -> np.ndarray:
        if k <= 0 or indices.size == 0:
            return np.array([], dtype=int)
        Fm = self._to_minimization(F[indices, :])
        keys = [Fm[:, j] for j in reversed(range(Fm.shape[1]))]
        order = np.lexsort(keys)
        return indices[order[:k]]

    def _pad_gold_indices(self, gold_indices: np.ndarray, n_total: int, F: np.ndarray, min_points: int) -> np.ndarray:
        gold = set(int(i) for i in gold_indices.tolist())
        if len(gold) >= min_points:
            return gold_indices
        rem = [i for i in range(n_total) if i not in gold]
        if rem:
            chosen = self._lexicographic_select(F, np.asarray(rem, dtype=int), min_points - len(gold))
            gold.update(int(i) for i in chosen.tolist())
        return np.asarray(sorted(gold), dtype=int)

    def _maybe_retrain(self) -> None:
        if str(self.gating.retrain.source).lower() != "gold":
            raise ValueError("[gated] retrain.source must be 'gold'.")
        if not self._truth_X:
            return
        if len(self._truth_X) < int(self.gating.retrain.min_truth_points):
            return
        every_n_batches = int(self.gating.retrain.every_n_batches)
        if every_n_batches <= 0 or (self._batch_idx - self._last_retrain_batch) < every_n_batches:
            return
        from Optimization.framework.engines.Surrogat_model.fit.model_factory import make_model

        idx = [i for i, src in enumerate(self._truth_source) if src == "gold"]
        if not idx:
            return
        X = np.vstack([self._truth_X[i] for i in idx])
        Y = np.vstack([self._truth_Y[i] for i in idx])
        Xf = self._surrogate._augment_features(X)
        models: List[Any] = []
        st = getattr(self.s, "surrogate_train", None)
        surrogate_cfg = getattr(self.s, "surrogate", None)
        model_name = str(getattr(surrogate_cfg, "model", "rf"))
        model_params = dict(getattr(st, "model_params", {}) or {}) if st else {}
        seed = int(getattr(getattr(self.s, "engine", None), "rng_seed", 0))
        for j in range(Y.shape[1]):
            m = make_model(model_name, model_params, random_state=seed)
            m.fit(Xf, Y[:, j])
            models.append(m)
        self._surrogate._models_F = models
        self._last_retrain_batch = self._batch_idx
        if self.gating.retrain.save_artifacts and self.run_dir:
            version_dir = Path(self.run_dir) / str(self.gating.retrain.artifact_dirname) / f"v{len(self._surrogate_versions)+1:03d}"
            version_dir.mkdir(parents=True, exist_ok=True)
            dump({"targets": self._surrogate._targets, "models": models}, version_dir / "surrogate_rf.joblib")
            self._surrogate_versions.append(str(version_dir))
            promote_surrogate_version(self.signature_hash, version_dir, self.run_dir)

    def _write_audit_row(self, F_before: np.ndarray, F_gold: np.ndarray, n_total: int, gold_indices: np.ndarray, t_gold: float) -> None:
        Fb = self._to_minimization(F_before)
        Fg = self._to_minimization(F_gold)
        hv_mode_name = hv_mode(self.s)
        if hv_mode_name == "fixed":
            self.hv_ref_point = resolve_reference_point(self.s, n_obj=Fb.shape[1])
        else:
            ref = resolve_reference_point(
                self.s,
                n_obj=Fb.shape[1],
                F_seen=np.vstack([Fb, Fg]),
                feasible_mask=np.ones(Fb.shape[0] + Fg.shape[0], dtype=bool),
                current_ref_point=self.hv_ref_point,
            )
            self.hv_ref_point = ref
        hv_before = float("nan")
        hv_gold = float("nan")
        hv_error = float("nan")
        hv_valid = bool(F_gold.shape[0] >= 2)
        hv_reason = ""
        if hv_valid:
            try:
                hv_before = compute_hv(Fb, feasible_mask=np.ones(Fb.shape[0], dtype=bool), ref_point=self.hv_ref_point)
                hv_gold = compute_hv(Fg, feasible_mask=np.ones(Fg.shape[0], dtype=bool), ref_point=self.hv_ref_point)
                hv_error = float(abs(hv_gold - hv_before) / max(abs(hv_gold), 1e-9))
            except Exception:
                hv_valid = False
                hv_reason = "hv_failed_exception"
        else:
            hv_reason = "too_few_gold"
        row = {
            "run_id": self.run_id,
            "batch_idx": self._batch_idx,
            "n_total": int(n_total),
            "n_gold": int(gold_indices.size),
            "gold_indices_json": json.dumps([int(i) for i in gold_indices.tolist()]),
            "t_gold_s": float(t_gold),
            "hv_before": hv_before,
            "hv_gold": hv_gold,
            "hv_error": hv_error,
            "hv_valid": int(hv_valid),
            "hv_reason": hv_reason,
        }
        append_csv(Path(self.run_dir) / "audit_log.csv", self._audit_header, row)

    def _ensure_run_dir(self) -> None:
        if self.run_dir:
            Path(self.run_dir).mkdir(parents=True, exist_ok=True)

    def _write_manifest(self) -> None:
        if not self.run_dir:
            return
        payload = {
            "created_at": _now_iso(),
            "gating": asdict(self.gating),
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
        }
        out = Path(self.run_dir) / "gating_manifest.json"
        out.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    def _check_signature_and_compatibility(self) -> None:
        if not self.run_dir:
            return
        meta_path = Path(self.run_dir) / "surrogate_meta_hint.json"
        meta = json.loads(meta_path.read_text(encoding="utf-8")) if meta_path.exists() else {}
        self._artifact_signature_hash = meta.get("signature_hash")
        if self._artifact_signature_hash:
            self.surrogate_compatible = is_compatible(self.signature_hash, self._artifact_signature_hash)
            if not self.surrogate_compatible:
                self._signature_mismatch_msg = summarize_mismatch(self.signature_dict, meta.get("signature_dict"))
                write_summary_line(self.run_dir, f"[gated][signature] {self._signature_mismatch_msg}")
        else:
            self.surrogate_compatible = False
            self._signature_mismatch_msg = "SURROGATE_SIGNATURE missing."
        update_manifest_json(
            self.run_dir,
            {"signature": {"hash": self.signature_hash, "artifact_hash": self._artifact_signature_hash, "surrogate_compatible": bool(self.surrogate_compatible), "mismatch": self._signature_mismatch_msg}},
        )

    def _apply_mismatch_fallbacks(self) -> None:
        gold_cap = int(getattr(self.control_cfg, "gold_cap_points", self.budget_state.gold_min_points))
        gold_min = min(max(self.budget_state.gold_min_points, 20), gold_cap)
        self.budget_state = BudgetState(surrogate_fraction=self.budget_state.surrogate_fraction, gold_min_points=gold_min)

    def _default_control_cfg(self):
        class _Cfg:
            enabled = False
            metric = "hv_error"
            target = 0.25
            patience = 2
            surrogate_step = 0.05
            surrogate_cap = 0.40
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
