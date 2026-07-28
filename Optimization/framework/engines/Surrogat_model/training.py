# Optimization/framework/engines/Surrogat_model/training.py
from __future__ import annotations

import json
from typing import Any, List, Tuple, Optional
import numpy as np
import pandas as pd
from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor

from Learning.datasets.load_dataset import load_dataset
from Learning.datasets.save_dataset import save_dataset
from Learning.families.build_family import build_family
from Learning.registry.register_dataset import register_dataset
from Optimization.framework.engines.Surrogat_model.features import augment_features, resolve_feature_encoding, resolve_feature_names, resolve_surrogate_targets
from Optimization.framework.engines.Surrogat_model.samplers.factory import sample_from_settings
from Optimization.framework.engines.Surrogat_model.teacher.evaluate_teacher import evaluate_teacher_dataset
from Optimization.framework.engines.Surrogat_model.split.split import train_holdout_split
from Optimization.framework.engines.Surrogat_model.fit.fit_models import fit_models_per_column
from Optimization.framework.engines.Surrogat_model.validate.holdout import metrics_by_column
from Optimization.framework.engines.Surrogat_model.persist.save import (
    make_outdir,
    build_meta_dict,
    persist_artifact,
    mirror_holdout_to_validation,
    write_teacher_eval_audit,
)
from Optimization.framework.engines.profiles_meta import get_profile_id
from Technical_model.energy_system.precompute.adapter import prepare_profiles_adapter


def _design_row_key(row: np.ndarray) -> tuple[float, ...]:
    arr = np.asarray(row, dtype=float).reshape(-1)
    return tuple(np.round(arr, 8).tolist())


# ---------------------------------------------------------
# Helpers für Parallel-Konfig
# ---------------------------------------------------------
def _resolve_teacher_parallel_cfg(settings: Any) -> Tuple[str, int, int]:
    """
    Holt Parallelisierungs-Settings aus settings.surrogate_train.
    Fällt auf sinnvolle Defaults zurück, falls Felder fehlen.
    """
    st = getattr(settings, "surrogate_train", None)

    backend = getattr(st, "teacher_backend", "processes") if st is not None else "processes"
    n_workers = getattr(st, "teacher_n_workers", 0) if st is not None else 0
    batch_size = getattr(st, "teacher_batch_size", 32) if st is not None else 32

    if n_workers is None or n_workers <= 0:
        try:
            import multiprocessing as mp
            cpu = mp.cpu_count()
        except Exception:
            cpu = 1
        n_workers = max(1, cpu - 1)

    return backend, int(n_workers), int(batch_size)


# ---------------------------------------------------------
# Teacher-Eval (seriell / parallel)
# ---------------------------------------------------------
def _teacher_eval_serial(settings: Any, X: np.ndarray) -> Tuple[np.ndarray, Optional[np.ndarray], dict]:
    """
    Serieller Teacher-Call für alle Punkte in X.
    evaluate_teacher_dataset gibt (YF, YG) zurück.
    """
    st = getattr(settings, "surrogate_train", None)
    targets: Optional[List[str]] = resolve_surrogate_targets(settings)

    YF, YG, audit = evaluate_teacher_dataset(settings, X, targets=targets, batch_size=None, row_offset=0)
    YF = np.asarray(YF, float)
    YG = None if YG is None else np.asarray(YG, float)
    return YF, YG, audit


def _teacher_eval_parallel(
    settings: Any,
    X: np.ndarray,
    backend: str,
    n_workers: int,
    batch_size: int,
) -> Tuple[np.ndarray, Optional[np.ndarray]]:
    """
    Parallele Teacher-Auswertung: X in Chunks teilen, evaluate_teacher_dataset je Chunk.
    """
    if backend == "processes":
        Executor = ProcessPoolExecutor
    elif backend == "threads":
        Executor = ThreadPoolExecutor
    else:
        raise ValueError(f"[surrogate] unknown teacher_backend='{backend}'")

    X = np.asarray(X, float)
    n = X.shape[0]
    if n == 0:
        return np.zeros((0, 0), float), None, {
            "n_requested": 0,
            "n_feasible": 0,
            "n_infeasible": 0,
            "feasible_indices": [],
            "failed_points": [],
        }

    chunks = [X[i:i + batch_size] for i in range(0, n, batch_size)]

    YF_chunks: List[np.ndarray] = []
    YG_chunks: List[np.ndarray] = []
    feasible_indices: List[int] = []
    failed_points: List[dict] = []

    targets: Optional[List[str]] = resolve_surrogate_targets(settings)

    print(f"[surrogate] teacher eval parallel: backend={backend}, "
          f"n_workers={n_workers}, batch_size={batch_size}, n={n}")

    with Executor(max_workers=n_workers) as ex:
        futures = []
        row_offset = 0
        for chunk in chunks:
            futures.append(
                ex.submit(evaluate_teacher_dataset, settings, chunk, targets, None, row_offset)
            )
            row_offset += int(chunk.shape[0])
        for fut in futures:
            YF_chunk, YG_chunk, audit_chunk = fut.result()
            YF_chunks.append(np.asarray(YF_chunk, float))
            if YG_chunk is not None and np.asarray(YG_chunk).size:
                YG_chunks.append(np.asarray(YG_chunk, float))
            feasible_indices.extend(list(audit_chunk.get("feasible_indices", []) or []))
            failed_points.extend(list(audit_chunk.get("failed_points", []) or []))

    YF = np.vstack(YF_chunks)
    YG = np.vstack(YG_chunks) if YG_chunks else None
    audit = {
        "n_requested": int(n),
        "n_feasible": int(YF.shape[0]),
        "n_infeasible": int(len(failed_points)),
        "feasible_indices": feasible_indices,
        "failed_points": failed_points,
    }
    return YF, YG, audit


def _teacher_eval_policy(settings: Any) -> Tuple[str, int, float]:
    st = getattr(settings, "surrogate_train", None)
    policy = str(getattr(st, "teacher_infeasible_policy", "drop_and_audit")).strip().lower()
    min_feasible_samples = int(getattr(st, "teacher_min_feasible_samples", 8))
    max_infeasible_share = float(getattr(st, "teacher_max_infeasible_share", 0.5))
    return policy, min_feasible_samples, max_infeasible_share


def _teacher_eval_summary(
    teacher_eval: dict,
    *,
    policy: str,
    min_feasible_samples: int,
    max_infeasible_share: float,
) -> dict:
    n_requested = int(teacher_eval.get("n_requested", 0))
    n_feasible = int(teacher_eval.get("n_feasible", 0))
    n_infeasible = int(teacher_eval.get("n_infeasible", 0))
    infeasible_share = float(n_infeasible / n_requested) if n_requested > 0 else 0.0
    return {
        "policy": policy,
        "n_requested": n_requested,
        "n_feasible": n_feasible,
        "n_infeasible": n_infeasible,
        "infeasible_share": infeasible_share,
        "min_feasible_samples_required": int(min_feasible_samples),
        "max_infeasible_share_allowed": float(max_infeasible_share),
    }


def _require_teacher_eval_viability(settings: Any, teacher_eval: dict, artifact_dir: str) -> dict:
    policy, min_feasible_samples, max_infeasible_share = _teacher_eval_policy(settings)
    summary = _teacher_eval_summary(
        teacher_eval,
        policy=policy,
        min_feasible_samples=min_feasible_samples,
        max_infeasible_share=max_infeasible_share,
    )
    write_teacher_eval_audit(artifact_dir, summary, list(teacher_eval.get("failed_points", []) or []))

    if policy not in {"drop_and_audit", "fail"}:
        raise ValueError(
            f"[surrogate] unknown teacher_infeasible_policy='{policy}'. "
            "Allowed: 'drop_and_audit', 'fail'."
        )

    if policy == "fail" and int(summary["n_infeasible"]) > 0:
        raise RuntimeError(
            "[surrogate] teacher produced infeasible points and policy='fail'. "
            f"See {artifact_dir}\\teacher_eval\\infeasible_points.csv"
        )
    if int(summary["n_feasible"]) < int(summary["min_feasible_samples_required"]):
        raise RuntimeError(
            "[surrogate] teacher produced too few feasible samples after explicit filtering: "
            f"{summary['n_feasible']} < {summary['min_feasible_samples_required']}. "
            f"See {artifact_dir}\\teacher_eval\\summary.json"
        )
    if float(summary["infeasible_share"]) > float(summary["max_infeasible_share_allowed"]):
        raise RuntimeError(
            "[surrogate] teacher infeasible share exceeds allowed threshold: "
            f"{summary['infeasible_share']:.3f} > {summary['max_infeasible_share_allowed']:.3f}. "
            f"See {artifact_dir}\\teacher_eval\\summary.json"
        )
    return summary


# ---------------------------------------------------------
# Hauptfunktion: auto_train_surrogate
# ---------------------------------------------------------
def auto_train_surrogate(settings) -> str:
    """
    End-to-end:
      1) Sampling X
      2) Teacher-Auswertung (seriell oder parallel)
      3) Train/Holdout-Split
      4) Modell pro Target ueber die Modellfabrik fitten
      5) Holdout-Metriken berechnen
      6) Artefakt + Meta persistieren
    """
    target_names = resolve_surrogate_targets(settings)
    if not target_names:
        raise ValueError("[surrogate] surrogate targets are empty.")
    feature_names = resolve_feature_names(settings)
    feature_encoding = resolve_feature_encoding(settings)
    bounds_names = list(getattr(settings.bounds, "names", []) or [])
    if not bounds_names:
        raise ValueError("[surrogate] settings.bounds.names ist leer.")

    prep = prepare_profiles_adapter(settings)
    profile_id = get_profile_id(prep.profiles, settings)
    expected_feature_width = int(
        augment_features(settings, np.zeros((1, len(bounds_names)), dtype=float), profile_id).shape[1]
    )
    family_spec = build_family(settings)
    family_hash = str(family_spec.family_hash)
    learning = getattr(settings, "learning", None)
    dataset_root = str(getattr(learning, "active_dataset_root", "Learning/datasets"))
    existing_dataset = load_dataset(dataset_root, family_hash)

    # 1) Sampling
    X_requested = sample_from_settings(settings)
    X_requested = np.asarray(X_requested, float)
    print(f"[surrogate] sample: {settings.sampler.name} n={len(X_requested)}")
    outdir = make_outdir(settings)

    X_design_existing = np.zeros((0, len(bounds_names)), float)
    X_feat_existing = np.zeros((0, expected_feature_width), float)
    YF_existing = np.zeros((0, len(target_names)), float)
    existing_source_runs: List[dict] = []
    existing_failed_points: List[dict] = []
    if existing_dataset is not None:
        X_design_existing = np.asarray(existing_dataset["X_design"], dtype=float)
        # Rebuild augmented features from design columns under the *current*
        # settings. Cached `X` embeds static ThermFlex/policy columns that can
        # change without changing family feature names; reusing them would train
        # under a new signature with stale static context.
        if X_design_existing.size:
            X_feat_existing = augment_features(settings, X_design_existing, profile_id)
        else:
            X_feat_existing = np.zeros((0, expected_feature_width), float)
        YF_existing = np.asarray(existing_dataset["Y"], dtype=float)
        if X_design_existing.shape[1] != len(bounds_names):
            raise ValueError(
                f"[surrogate] existing dataset design width {X_design_existing.shape[1]} != {len(bounds_names)}."
            )
        if YF_existing.shape[1] != len(target_names):
            raise ValueError(
                f"[surrogate] existing dataset target width {YF_existing.shape[1]} != {len(target_names)}."
            )
        if X_feat_existing.shape[1] != expected_feature_width:
            raise ValueError(
                "[surrogate] rebuilt dataset feature width passt nicht zur aktiven Feature-Spezifikation."
            )
        source_runs_path = existing_dataset.get("source_runs_path")
        if source_runs_path is not None and source_runs_path.exists():
            existing_source_runs = list(json.loads(source_runs_path.read_text(encoding="utf-8")))
        failed_points_path = existing_dataset.get("teacher_eval_failed_path")
        if failed_points_path is not None and failed_points_path.exists():
            failed_df = pd.read_csv(failed_points_path)
            missing_failed_cols = [name for name in bounds_names if name not in failed_df.columns]
            if missing_failed_cols:
                raise KeyError(
                    "[surrogate] cached infeasible-point audit fehlt Bound-Spalten: "
                    + ", ".join(missing_failed_cols)
                )
            existing_failed_points = failed_df.to_dict(orient="records")

    existing_keys = {_design_row_key(row) for row in X_design_existing}
    existing_failed_keys = {
        _design_row_key(np.array([float(point[name]) for name in bounds_names], dtype=float))
        for point in existing_failed_points
    }
    pending_rows = [
        row
        for row in X_requested
        if _design_row_key(row) not in existing_keys and _design_row_key(row) not in existing_failed_keys
    ]
    X_pending = np.asarray(pending_rows, dtype=float)
    if X_requested.size and X_pending.size == 0 and X_requested.shape[1] != len(bounds_names):
        raise ValueError(
            f"[surrogate] sampled design width {X_requested.shape[1]} != {len(bounds_names)}."
        )

    teacher_failed_points: List[dict] = []
    if X_pending.size == 0:
        teacher_eval_summary = {
            "policy": "reuse_existing_dataset",
            "n_requested": 0,
            "n_feasible": 0,
            "n_infeasible": 0,
            "infeasible_share": 0.0,
            "min_feasible_samples_required": int(getattr(settings.surrogate_train, "teacher_min_feasible_samples", 8)),
            "max_infeasible_share_allowed": float(getattr(settings.surrogate_train, "teacher_max_infeasible_share", 0.5)),
            "reused_existing_samples": int(X_design_existing.shape[0]),
            "reused_known_infeasible_samples": int(len(existing_failed_keys)),
            "n_new_samples": 0,
        }
        write_teacher_eval_audit(outdir, teacher_eval_summary, [])
        X_design = X_design_existing
        X_feat = X_feat_existing
        YF = YF_existing
        print(f"[surrogate] reuse dataset: family={family_hash} n_existing={len(X_design_existing)} n_new=0")
    else:
        X_pending = X_pending.reshape(-1, len(bounds_names))
        print(f"[surrogate] dataset cache: family={family_hash} n_existing={len(X_design_existing)} n_new={len(X_pending)}")

        # 2) Teacher-Auswertung (ggf. parallel)
        backend, n_workers, batch_size = _resolve_teacher_parallel_cfg(settings)

        if backend == "none" or n_workers == 1 or len(X_pending) <= batch_size:
            print(f"[surrogate] teacher eval serial (backend={backend}, n={len(X_pending)})")
            YF_new, YG, teacher_eval = _teacher_eval_serial(settings, X_pending)
        else:
            YF_new, YG, teacher_eval = _teacher_eval_parallel(settings, X_pending, backend, n_workers, batch_size)

        teacher_eval_summary = _require_teacher_eval_viability(settings, teacher_eval, outdir)
        feasible_indices = np.asarray(teacher_eval.get("feasible_indices", []) or [], dtype=int)
        if feasible_indices.shape[0] != YF_new.shape[0]:
            raise RuntimeError(
                "[surrogate] teacher feasible index count does not match teacher output rows. "
                f"indices={feasible_indices.shape[0]} rows={YF_new.shape[0]}"
            )
        X_feasible_new = X_pending[feasible_indices]
        X_feat_new = augment_features(settings, X_feasible_new, profile_id)
        teacher_failed_points = list(teacher_eval.get("failed_points", []) or [])
        print(
            "[surrogate] teacher eval: "
            f"requested={teacher_eval_summary['n_requested']} "
            f"feasible={teacher_eval_summary['n_feasible']} "
            f"infeasible={teacher_eval_summary['n_infeasible']}"
        )
        if X_design_existing.size:
            X_design = np.vstack([X_design_existing, X_feasible_new])
            X_feat = np.vstack([X_feat_existing, X_feat_new])
            YF = np.vstack([YF_existing, YF_new])
        else:
            X_design = X_feasible_new
            X_feat = X_feat_new
            YF = YF_new

    if X_design.shape[0] != X_feat.shape[0] or X_design.shape[0] != YF.shape[0]:
        raise RuntimeError("[surrogate] combined dataset arrays haben unterschiedliche Zeilenanzahl.")
    if X_design.shape[0] == 0:
        raise RuntimeError("[surrogate] combined dataset ist leer.")

    # 3) Train/Holdout-Split
    sampler = getattr(settings, "sampler", None)
    seed = int(getattr(sampler, "seed", 0))

    holdout_frac = float(getattr(getattr(settings, "surrogate_train", None), "holdout_frac", 0.2))

    X_train, X_hold, YF_train, YF_hold, YG_train, YG_hold = train_holdout_split(
        X=X_feat,
        YF=YF,
        YG=None,
        holdout_frac=holdout_frac,
        seed=seed,
    )

    # 4) Modelle fitten (modellagnostisch pro Spalte)
    st = settings.surrogate_train
    surrogate_cfg = getattr(settings, "surrogate", None)
    model_name = str(getattr(surrogate_cfg, "model", "rf"))
    model_params = dict(getattr(st, "model_params", {}) or {})

    models_F = fit_models_per_column(
        X_train,
        YF_train,
        model_name=model_name,
        model_params=model_params,
        seed=int(seed),
    )

    # 5) Holdout-Metriken
    holdout: dict = {}
    if X_hold is not None and YF_hold is not None and X_hold.shape[0] and YF_hold.shape[0]:
        YF_pred = np.column_stack([m.predict(X_hold) for m in models_F])
        holdout["F"] = metrics_by_column(YF_hold, YF_pred, target_names=target_names)
    print("[surrogate] holdout: ok")

    # 6) Persist + Mirror
    meta = build_meta_dict(settings, holdout_metrics=holdout)
    meta["teacher_eval"] = teacher_eval_summary
    meta["surrogate_targets"] = target_names
    meta["feature_names"] = feature_names
    meta["feature_encoding"] = feature_encoding
    meta["profile_id"] = profile_id
    meta["system_id"] = str(getattr(getattr(settings, "engine", None), "system_id", "unknown"))
    meta["dataset"] = {
        "family_hash": family_hash,
        "n_samples": int(X_design.shape[0]),
        "n_existing_samples": int(X_design_existing.shape[0]),
        "n_new_samples": int(X_design.shape[0] - X_design_existing.shape[0]),
        "target_names": list(target_names),
        "bounds_names": list(bounds_names),
    }
    artifact = persist_artifact(outdir, models_F, [], meta)
    mirror_holdout_to_validation(settings, artifact_dir=outdir, meta=meta)

    combined_failed_points_by_key: dict[tuple[float, ...], dict] = {}
    for point in existing_failed_points + teacher_failed_points:
        row_key = _design_row_key(np.array([float(point[name]) for name in bounds_names], dtype=float))
        combined_failed_points_by_key[row_key] = dict(point)

    source_runs = list(existing_source_runs)
    source_runs.append(
        {
            "source": "optimization_auto_train",
            "run_dir": str(outdir),
            "family_hash": family_hash,
            "n_requested_samples": int(X_requested.shape[0]),
            "n_new_samples": int(X_design.shape[0] - X_design_existing.shape[0]),
            "n_known_infeasible_samples": int(len(combined_failed_points_by_key)),
            "n_total_samples": int(X_design.shape[0]),
        }
    )
    dataset_meta = {
        "family_hash": family_hash,
        "targets": list(target_names),
        "target_names": list(target_names),
        "bounds_names": list(bounds_names),
        "feature_names": list(feature_names),
        "feature_encoding": dict(feature_encoding),
        "profile_id": profile_id,
        "system_id": str(getattr(getattr(settings, "engine", None), "system_id", "unknown")),
        "run_dir": str(outdir),
        "n_samples": int(X_design.shape[0]),
        "n_existing_samples": int(X_design_existing.shape[0]),
        "n_new_samples": int(X_design.shape[0] - X_design_existing.shape[0]),
        "n_known_infeasible_samples": int(len(combined_failed_points_by_key)),
        "teacher_eval": teacher_eval_summary,
    }
    dataset_info = save_dataset(
        dataset_root,
        family_hash,
        X_design,
        X_feat,
        YF,
        dataset_meta,
        bounds_names=bounds_names,
        target_names=target_names,
        family_spec=family_spec.to_dict(),
        source_runs=source_runs,
        teacher_eval_summary=teacher_eval_summary,
        teacher_failed_points=list(combined_failed_points_by_key.values()),
    )
    register_dataset(
        settings,
        family_hash,
        f"dataset_{family_hash}",
        {
            "source": "optimization_auto_train",
            "artifact_path": str(dataset_info["data_path"]),
            "meta_path": str(dataset_info["meta_path"]),
            "truth_csv_path": str(dataset_info["truth_csv_path"]),
            "truth_meta_path": str(dataset_info["truth_meta_path"]),
            "family_spec_path": str(dataset_info["family_spec_path"]) if dataset_info["family_spec_path"] else "",
            "source_runs_path": str(dataset_info["source_runs_path"]) if dataset_info["source_runs_path"] else "",
            "teacher_eval_summary_path": str(dataset_info["teacher_eval_summary_path"]) if dataset_info["teacher_eval_summary_path"] else "",
            "teacher_eval_failed_path": str(dataset_info["teacher_eval_failed_path"]) if dataset_info["teacher_eval_failed_path"] else "",
            "n_samples": int(X_design.shape[0]),
            "n_existing_samples": int(X_design_existing.shape[0]),
            "n_new_samples": int(X_design.shape[0] - X_design_existing.shape[0]),
            "n_known_infeasible_samples": int(len(combined_failed_points_by_key)),
            "is_active": True,
        },
    )
    return artifact
