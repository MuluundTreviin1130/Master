# Optimization/framework/engines/Surrogat_model/training.py
from __future__ import annotations

from typing import Any, List, Tuple, Optional
import numpy as np
from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor

from V2H_energy_community_surrogat_datafilenew.datafile_Umstellung.Optimization.framework.engines.Surrogat_model.samplers.factory import sample_from_settings
from V2H_energy_community_surrogat_datafilenew.datafile_Umstellung.Optimization.framework.engines.Surrogat_model.teacher.evaluate_teacher import evaluate_teacher_dataset
from V2H_energy_community_surrogat_datafilenew.datafile_Umstellung.Optimization.framework.engines.Surrogat_model.split.split import train_holdout_split
from V2H_energy_community_surrogat_datafilenew.datafile_Umstellung.Optimization.framework.engines.Surrogat_model.fit.fit_models import fit_random_forest_per_column
from V2H_energy_community_surrogat_datafilenew.datafile_Umstellung.Optimization.framework.engines.Surrogat_model.validate.holdout import metrics_by_column
from V2H_energy_community_surrogat_datafilenew.datafile_Umstellung.Optimization.framework.engines.Surrogat_model.persist.save import (
    make_outdir,
    build_meta_dict,
    persist_artifact,
    mirror_holdout_to_validation,
)


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
def _teacher_eval_serial(settings: Any, X: np.ndarray) -> Tuple[np.ndarray, Optional[np.ndarray]]:
    """
    Serieller Teacher-Call für alle Punkte in X.
    evaluate_teacher_dataset gibt (YF, YG) zurück.
    """
    st = getattr(settings, "surrogate_train", None)
    targets: Optional[List[str]] = list(getattr(st, "targets", [])) if st is not None else None

    YF, YG = evaluate_teacher_dataset(settings, X, targets=targets, batch_size=None)
    YF = np.asarray(YF, float)
    YG = None if YG is None else np.asarray(YG, float)
    return YF, YG


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
        return np.zeros((0, 0), float), None

    chunks = [X[i:i + batch_size] for i in range(0, n, batch_size)]

    YF_chunks: List[np.ndarray] = []
    YG_chunks: List[np.ndarray] = []

    st = getattr(settings, "surrogate_train", None)
    targets: Optional[List[str]] = list(getattr(st, "targets", [])) if st is not None else None

    print(f"[surrogate] teacher eval parallel: backend={backend}, "
          f"n_workers={n_workers}, batch_size={batch_size}, n={n}")

    with Executor(max_workers=n_workers) as ex:
        futures = [
            ex.submit(evaluate_teacher_dataset, settings, chunk, targets, None)
            for chunk in chunks
        ]
        for fut in futures:
            YF_chunk, YG_chunk = fut.result()
            YF_chunks.append(np.asarray(YF_chunk, float))
            if YG_chunk is not None and np.asarray(YG_chunk).size:
                YG_chunks.append(np.asarray(YG_chunk, float))

    YF = np.vstack(YF_chunks)
    YG = np.vstack(YG_chunks) if YG_chunks else None
    return YF, YG


# ---------------------------------------------------------
# Hauptfunktion: auto_train_surrogate
# ---------------------------------------------------------
def auto_train_surrogate(settings) -> str:
    """
    End-to-end:
      1) Sampling X
      2) Teacher-Auswertung (seriell oder parallel)
      3) Train/Holdout-Split
      4) Random-Forest pro Target fitten
      5) Holdout-Metriken berechnen
      6) Artefakt + Meta persistieren
    """
    # 1) Sampling
    X = sample_from_settings(settings)
    X = np.asarray(X, float)
    print(f"[surrogate] sample: {settings.sampler.name} n={len(X)}")


    # 2) Teacher-Auswertung (ggf. parallel)
    backend, n_workers, batch_size = _resolve_teacher_parallel_cfg(settings)

    if backend == "none" or n_workers == 1 or len(X) <= batch_size:
        print(f"[surrogate] teacher eval serial (backend={backend}, n={len(X)})")
        YF, YG = _teacher_eval_serial(settings, X)
    else:
        YF, YG = _teacher_eval_parallel(settings, X, backend, n_workers, batch_size)

    # 3) Train/Holdout-Split
    sampler = getattr(settings, "sampler", None)
    seed = int(getattr(sampler, "seed", 0))

    holdout_frac = float(getattr(getattr(settings, "surrogate_train", None), "holdout_frac", 0.2))

    X_train, X_hold, YF_train, YF_hold, YG_train, YG_hold = train_holdout_split(
        X=X,
        YF=YF,
        YG=YG,
        holdout_frac=holdout_frac,
        seed=seed,
    )

    # 4) Modelle fitten (Random Forest pro Spalte)
    st = settings.surrogate_train
    target_names = list(getattr(st, "targets", []))
    rf_n_estimators = int(getattr(st, "rf_n_estimators", 300))
    rf_n_jobs = int(getattr(st, "rf_n_jobs", -1))

    models_F = fit_random_forest_per_column(
        X_train,
        YF_train,
        n_estimators=rf_n_estimators,
        n_jobs=rf_n_jobs,
        seed=seed,
    )

    # 5) Holdout-Metriken
    holdout: dict = {}
    if X_hold is not None and YF_hold is not None and X_hold.shape[0] and YF_hold.shape[0]:
        YF_pred = np.column_stack([m.predict(X_hold) for m in models_F])
        holdout["F"] = metrics_by_column(YF_hold, YF_pred, target_names=target_names)
    print("[surrogate] holdout: ok")

    # 6) Persist + Mirror
    outdir = make_outdir(settings)
    meta = build_meta_dict(settings, holdout_metrics=holdout)
    meta["surrogate_targets"] = target_names
    artifact = persist_artifact(outdir, models_F, [], meta)
    mirror_holdout_to_validation(settings, artifact_dir=outdir, meta=meta)
    return artifact
