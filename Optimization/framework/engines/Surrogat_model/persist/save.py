# Optimization/framework/engines/Surrogat_model/persist/save.py
from __future__ import annotations

import json
import os
import shutil
from datetime import datetime
from typing import Any, Dict, List, Optional

import joblib
import numpy as np
import pandas as pd


def _ts() -> str:
    return datetime.now().strftime("%Y%m%d_%H%M%S")


def _join(*parts: str) -> str:
    return os.path.join(*parts)


def _learning_io_from_settings(settings: Any) -> Dict[str, str]:
    learning = getattr(settings, "learning", None)
    return {
        "primary_artifact": str(getattr(learning, "primary_artifact_filename", "surrogate_bundle.joblib")),
        "primary_meta": str(getattr(learning, "primary_meta_filename", "surrogate_bundle.meta.json")),
        "legacy_artifact": str(getattr(learning, "legacy_artifact_filename", "surrogate_rf.joblib")),
        "legacy_meta": str(getattr(learning, "legacy_meta_filename", "surrogate_rf.meta.json")),
        "validation_root": str(getattr(learning, "validation_root", "Optimization/run/validation")),
        "legacy_validation_root": str(getattr(learning, "legacy_validation_root", "Optimization/run/validation_old")),
    }


def _learning_io_from_meta(meta: Dict[str, Any]) -> Dict[str, str]:
    learning_meta = meta.get("learning", {}) if isinstance(meta.get("learning"), dict) else {}
    return {
        "primary_artifact": str(learning_meta.get("primary_artifact_filename", "surrogate_bundle.joblib")),
        "primary_meta": str(learning_meta.get("primary_meta_filename", "surrogate_bundle.meta.json")),
        "legacy_artifact": str(learning_meta.get("legacy_artifact_filename", "surrogate_rf.joblib")),
        "legacy_meta": str(learning_meta.get("legacy_meta_filename", "surrogate_rf.meta.json")),
        "validation_root": str(learning_meta.get("validation_root", "Optimization/run/validation")),
        "legacy_validation_root": str(learning_meta.get("legacy_validation_root", "Optimization/run/validation_old")),
    }


def make_outdir(settings) -> str:
    """
    Artefakt-Ordner:
      {settings.reporting.output_root}/{location}/{tag}/surrogate_{timestamp}/
    """
    base = str(settings.reporting.output_root)
    loc = str(settings.engine.location)
    tag = str(settings.run.tag)
    outdir = _join(base, loc, tag, f"surrogate_{_ts()}")
    os.makedirs(outdir, exist_ok=True)
    return outdir


def _write_json(path: str, obj: Dict[str, Any]) -> None:
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(obj, fh, indent=2, ensure_ascii=False)


def build_meta_dict(settings, holdout_metrics: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """
    Schlankes Meta fuer Persistenz und spaetere Validierung.
    """
    io_cfg = _learning_io_from_settings(settings)
    return {
        "engine": {
            "name": settings.engine.name,
            "system_id": settings.engine.system_id,
            "location": settings.engine.location,
            "ec_share_import": float(settings.engine.ec_share_import),
            "ec_share_export": float(settings.engine.ec_share_export),
            "N_HH": int(settings.engine.N_HH),
            "N_EV_total": int(settings.engine.N_EV_total),
            "N_EV_bidirectional": int(settings.engine.N_EV_bidirectional),
            "rng_seed": int(settings.engine.rng_seed),
        },
        "bounds": {
            "names": list(settings.bounds.names),
            "lower": list(settings.bounds.lower),
            "upper": list(settings.bounds.upper),
            "steps": list(settings.bounds.steps or [None] * len(settings.bounds.names)),
        },
        "objectives": {
            "names": list(settings.objectives.names),
            "minimize": list(settings.objectives.minimize),
        },
        "constraints": {
            "names": list(settings.constraints.names or []),
            "senses": list(settings.constraints.senses or []),
            "rhs": list(settings.constraints.rhs or []),
        },
        "sampler": {
            "name": settings.sampler.name,
            "n_samples": int(settings.sampler.n_samples),
            "seed": int(settings.sampler.seed),
            "kwargs": dict(settings.sampler.kwargs or {}),
        },
        "surrogate_train": {
            "model": str(getattr(getattr(settings, "surrogate", None), "model", "rf")),
            "model_params": dict(settings.surrogate_train.model_params or {}),
            "holdout_frac": float(settings.surrogate_train.holdout_frac),
            "feature_names": list(getattr(settings.surrogate_train, "feature_names", []) or []),
            "feature_encoding": dict(getattr(settings.surrogate_train, "feature_encoding", {}) or {}),
        },
        "optimizer": {
            "name": settings.optimizer.name,
            "kwargs": dict(settings.optimizer.kwargs or {}),
            "seed": int(settings.optimizer.seed),
            "n_jobs": int(settings.optimizer.n_jobs),
        },
        "learning": {
            "primary_artifact_filename": io_cfg["primary_artifact"],
            "primary_meta_filename": io_cfg["primary_meta"],
            "legacy_artifact_filename": io_cfg["legacy_artifact"],
            "legacy_meta_filename": io_cfg["legacy_meta"],
            "validation_root": io_cfg["validation_root"],
            "legacy_validation_root": io_cfg["legacy_validation_root"],
        },
        "reporting": {
            "output_root": settings.reporting.output_root,
        },
        "run": {
            "tag": settings.run.tag,
        },
        "teacher_eval": {},
        "holdout": holdout_metrics or {},
        "created_at": datetime.now().isoformat(timespec="seconds"),
    }


def write_teacher_eval_audit(artifact_dir: str, summary: Dict[str, Any], failed_points: List[Dict[str, Any]]) -> None:
    teacher_eval_dir = _join(artifact_dir, "teacher_eval")
    os.makedirs(teacher_eval_dir, exist_ok=True)
    _write_json(_join(teacher_eval_dir, "summary.json"), summary)
    if failed_points:
        pd.DataFrame(failed_points).to_csv(_join(teacher_eval_dir, "infeasible_points.csv"), index=False)


def _write_holdout_files(artifact_dir: str, holdout: Dict[str, Any]) -> None:
    """
    Schreibt Holdout-Metriken ins Artefakt:
      surrogate_.../holdout/metrics_F_objectives.csv
      surrogate_.../holdout/metrics_G_constraints.csv
      surrogate_.../holdout/metrics.json
      surrogate_.../holdout/summary.md
    """
    if not holdout:
        return

    holdout_dir = _join(artifact_dir, "holdout")
    os.makedirs(holdout_dir, exist_ok=True)
    _write_json(_join(holdout_dir, "metrics.json"), holdout)

    def _df_from_metrics(metrics_obj: Any) -> pd.DataFrame:
        if isinstance(metrics_obj, dict) and "targets" in metrics_obj:
            return pd.DataFrame(
                {
                    "target": metrics_obj["targets"],
                    "r2": metrics_obj["r2"],
                    "rmse": metrics_obj["rmse"],
                    "mae": metrics_obj["mae"],
                    "rel_mae_percent": metrics_obj["rel_mae_percent"],
                }
            )
        if isinstance(metrics_obj, list):
            return pd.DataFrame(metrics_obj)
        raise ValueError("[persist] Unknown metrics format for holdout.")

    if holdout.get("F"):
        _df_from_metrics(holdout["F"]).to_csv(_join(holdout_dir, "metrics_F_objectives.csv"), index=False)
    if holdout.get("G"):
        _df_from_metrics(holdout["G"]).to_csv(_join(holdout_dir, "metrics_G_constraints.csv"), index=False)

    with open(_join(holdout_dir, "summary.md"), "w", encoding="utf-8") as fh:
        fh.write("# Holdout Validation\n\n")
        if holdout.get("F"):
            fh.write("## Objectives (F)\n")
            fh.write("- Targets: " + ", ".join(holdout["F"].get("targets", [])) + "\n")
            fh.write(f"- R2 (median): {np.nanmedian(holdout['F'].get('r2', [])):.3f}\n")
            fh.write(f"- RMSE (median): {np.nanmedian(holdout['F'].get('rmse', [])):.3f}\n\n")
        if holdout.get("G"):
            fh.write("## Constraints (G)\n")
            fh.write("- Targets: " + ", ".join(holdout["G"].get("targets", [])) + "\n")
            fh.write(f"- R2 (median): {np.nanmedian(holdout['G'].get('r2', [])):.3f}\n")
            fh.write(f"- RMSE (median): {np.nanmedian(holdout['G'].get('rmse', [])):.3f}\n\n")


def persist_artifact(
    artifact_dir: str,
    models_F: List[Any],
    models_G: List[Any],
    meta: Dict[str, Any],
) -> str:
    """
    Speichert ein modellagnostisches Primarbundle und zusaetzlich das Legacy-RF-Bundle.
    """
    targets = list(meta.get("surrogate_targets") or meta.get("targets") or [])
    feature_names = list(meta.get("feature_names") or meta.get("surrogate_train", {}).get("feature_names", []) or [])
    feature_encoding = dict(meta.get("feature_encoding") or meta.get("surrogate_train", {}).get("feature_encoding", {}) or {})
    profile_id = meta.get("profile_id")
    system_id = meta.get("system_id") or meta.get("engine", {}).get("system_id")
    io_cfg = _learning_io_from_meta(meta)

    bundle = {
        "targets": targets,
        "models": models_F,
        "feature_names": feature_names,
        "feature_encoding": feature_encoding,
        "profile_id": profile_id,
        "system_id": system_id,
        "F": models_F,
        "G": models_G,
        "meta": meta,
    }

    primary_artifact_path = _join(artifact_dir, io_cfg["primary_artifact"])
    legacy_artifact_path = _join(artifact_dir, io_cfg["legacy_artifact"])
    primary_meta_path = _join(artifact_dir, io_cfg["primary_meta"])
    legacy_meta_path = _join(artifact_dir, io_cfg["legacy_meta"])

    joblib.dump(bundle, primary_artifact_path)
    if legacy_artifact_path != primary_artifact_path:
        joblib.dump(bundle, legacy_artifact_path)

    _write_json(primary_meta_path, meta)
    if legacy_meta_path != primary_meta_path:
        _write_json(legacy_meta_path, meta)
    _write_json(_join(artifact_dir, "meta.json"), meta)

    _write_holdout_files(artifact_dir, meta.get("holdout", {}))

    print(f"[surrogate] artifact saved: {primary_artifact_path}")
    return primary_artifact_path


def _validation_roots(settings) -> List[str]:
    io_cfg = _learning_io_from_settings(settings)
    roots: List[str] = []
    for base in [io_cfg["validation_root"], io_cfg["legacy_validation_root"]]:
        root = _join(base, settings.engine.location, settings.run.tag)
        if root not in roots:
            roots.append(root)
    return roots


def _copy_if_exists(src: str, dst: str) -> None:
    if os.path.exists(src):
        shutil.copy2(src, dst)


def mirror_holdout_to_validation(settings, artifact_dir: str, meta: Dict[str, Any]) -> None:
    """
    Spiegelt Holdout-CSV(s) in den neuen Validation-Pfad und parallel in den Legacy-Pfad.
    """
    base = os.path.basename(artifact_dir)
    ts = base.replace("surrogate_", "") if base.startswith("surrogate_") else _ts()

    src_f = _join(artifact_dir, "holdout", "metrics_F_objectives.csv")
    src_g = _join(artifact_dir, "holdout", "metrics_G_constraints.csv")

    for validation_root in _validation_roots(settings):
        os.makedirs(validation_root, exist_ok=True)

        dst_f = _join(validation_root, f"{settings.engine.location}.{settings.run.tag}_{ts}_metrics_F.csv")
        dst_g = _join(validation_root, f"{settings.engine.location}.{settings.run.tag}_{ts}_metrics_G.csv")
        _copy_if_exists(src_f, dst_f)
        _copy_if_exists(src_g, dst_g)

        index_path = _join(validation_root, "runs_index.csv")
        row = {
            "timestamp": ts,
            "location": settings.engine.location,
            "tag": settings.run.tag,
            "sampler": meta["sampler"]["name"],
            "n_samples": meta["sampler"]["n_samples"],
            "seed": meta["sampler"]["seed"],
            "model": meta["surrogate_train"]["model"],
            "model_params": json.dumps(meta["surrogate_train"]["model_params"], ensure_ascii=False, sort_keys=True),
            "holdout_frac": meta["surrogate_train"]["holdout_frac"],
            "artifact_dir": os.path.abspath(artifact_dir),
            "metrics_F_csv": os.path.abspath(dst_f) if os.path.exists(dst_f) else "",
            "metrics_G_csv": os.path.abspath(dst_g) if os.path.exists(dst_g) else "",
        }

        if os.path.exists(index_path):
            df = pd.read_csv(index_path)
            df = pd.concat([df, pd.DataFrame([row])], ignore_index=True)
        else:
            df = pd.DataFrame([row])

        df.to_csv(index_path, index=False)
        print(f"[surrogate] validation mirror: {validation_root}")


def write_holdout_csv(validation_dir: str, location: str, tag: str, rows: List[dict], kind: str) -> str:
    """
    Schreibt eine Holdout-CSV in den Validation-Ordner.
    """
    import csv

    os.makedirs(validation_dir, exist_ok=True)
    out_path = os.path.join(validation_dir, f"{location}.{tag}_holdout_{kind}.csv")
    fieldnames = ["target", "r2", "rmse", "mae", "rel_mae_percent"]

    with open(out_path, "w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows or []:
            writer.writerow(row)
    return out_path
