from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Tuple

import numpy as np
from joblib import dump
from sklearn.model_selection import train_test_split

from Learning.datasets.load_dataset import load_dataset
from Learning.datasets.save_dataset import save_dataset
from Learning.families.build_family import build_family
from Learning.registry.register_dataset import register_dataset
from Learning.registry.register_model import register_model
from Learning.registry.update_model_status import update_model_status
from Learning.training.targets import resolve_target_values
from Learning.validation.evaluate_gate import evaluate_gate
from Optimization.framework.engines.Surrogat_model.features import augment_features
from Optimization.framework.engines.Surrogat_model.fit.model_factory import make_model
from Optimization.framework.engines.kpi import compute_kpis, is_supported_objective_name


def _artifact_filenames(settings: Any) -> Dict[str, str]:
    learning = getattr(settings, "learning", None)
    primary_artifact = str(getattr(learning, "primary_artifact_filename", "surrogate_bundle.joblib"))
    primary_meta = str(getattr(learning, "primary_meta_filename", "surrogate_bundle.meta.json"))
    legacy_artifact = str(getattr(learning, "legacy_artifact_filename", "surrogate_rf.joblib"))
    legacy_meta = str(getattr(learning, "legacy_meta_filename", "surrogate_rf.meta.json"))
    return {
        "primary_artifact": primary_artifact,
        "primary_meta": primary_meta,
        "legacy_artifact": legacy_artifact,
        "legacy_meta": legacy_meta,
    }


def _evaluate_teacher_targets(
    teacher: Any,
    settings: Any,
    profiles: Any,
    profile_id: str,
    targets: List[str],
    build_design_vars_fn,
    X_design_new: np.ndarray,
) -> Tuple[np.ndarray, np.ndarray]:
    X_new = augment_features(settings, X_design_new, profile_id)
    Y_list: List[np.ndarray] = []
    for i in range(len(X_design_new)):
        _F, _G, flows_L, raw_results = teacher.evaluate_one_with_details(X_design_new[i, :])
        design_vars = build_design_vars_fn(X_design_new[i, :])
        design_vars["raw_results"] = raw_results
        requested_objective_names = [t for t in targets if is_supported_objective_name(design_vars.get("params", {}), t)]
        objectives, _constraints, _ctx = compute_kpis(
            flows_L,
            design_vars,
            settings,
            profiles,
            requested_objective_names=requested_objective_names,
        )
        y = np.array(
            resolve_target_values(targets=targets, objectives=objectives, flows_L=flows_L),
            dtype=float,
        )
        Y_list.append(y)
    return X_new, np.vstack(Y_list)


def _resolve_training_arrays(
    settings: Any,
    resolved_model_info: Dict[str, Any],
    retrain_decision: Dict[str, Any],
    profile_id: str,
    targets: List[str],
    profiles: Any,
    build_design_vars_fn,
    teacher: Any,
    sample_from_settings_fn,
) -> Tuple[np.ndarray, np.ndarray, np.ndarray, int]:
    action = str((retrain_decision or {}).get("action", "") or "")
    learning = getattr(settings, "learning", None)
    dataset_root = getattr(learning, "active_dataset_root", "Learning/datasets")
    family_hash = resolved_model_info.get("family_hash") or ""
    existing_dataset = load_dataset(dataset_root, family_hash)

    if action == "train_model" and existing_dataset is not None:
        return (
            np.asarray(existing_dataset["X_design"], dtype=float),
            np.asarray(existing_dataset["X"], dtype=float),
            np.asarray(existing_dataset["Y"], dtype=float),
            0,
        )

    if action == "append_then_train" and existing_dataset is not None:
        sampler = getattr(settings, "sampler", None)
        old_n = int(getattr(sampler, "n_samples", 0))
        old_seed = int(getattr(sampler, "seed", 42))
        max_append = int(getattr(learning, "max_auto_append_samples", 50))
        sampler.n_samples = max(1, min(max_append, old_n if old_n > 0 else max_append))
        sampler.seed = old_seed + int(existing_dataset["X_design"].shape[0])
        try:
            X_design_new = sample_from_settings_fn(settings)
        finally:
            sampler.n_samples = old_n
            sampler.seed = old_seed
        X_design_existing = np.asarray(existing_dataset["X_design"], dtype=float)
        existing_rows = {tuple(row) for row in np.round(X_design_existing, 8)}
        filtered = [row for row in np.asarray(X_design_new, dtype=float) if tuple(np.round(row, 8)) not in existing_rows]
        X_design_new = np.asarray(filtered, dtype=float)
    else:
        X_design_new = sample_from_settings_fn(settings)

    if X_design_new.size == 0 and existing_dataset is not None:
        return (
            np.asarray(existing_dataset["X_design"], dtype=float),
            np.asarray(existing_dataset["X"], dtype=float),
            np.asarray(existing_dataset["Y"], dtype=float),
            0,
        )

    X_new, Y_new = _evaluate_teacher_targets(
        teacher=teacher,
        settings=settings,
        profiles=profiles,
        profile_id=profile_id,
        targets=targets,
        build_design_vars_fn=build_design_vars_fn,
        X_design_new=X_design_new,
    )

    if existing_dataset is not None and action == "append_then_train":
        X_design = np.vstack([np.asarray(existing_dataset["X_design"], dtype=float), X_design_new])
        X = np.vstack([np.asarray(existing_dataset["X"], dtype=float), X_new])
        Y = np.vstack([np.asarray(existing_dataset["Y"], dtype=float), Y_new])
    else:
        X_design = X_design_new
        X = X_new
        Y = Y_new
    return X_design, X, Y, int(len(X_design_new))


def train_surrogate_model(
    *,
    settings: Any,
    resolved_model_info: Dict[str, Any],
    retrain_decision: Dict[str, Any],
    targets: List[str],
    feature_names: List[str],
    feature_encoding: Dict[str, str],
    profile_id: str,
    system_id: str,
    signature_hash: str,
    signature_dict: Dict[str, Any],
    artifact_dir: Path,
    artifact_path: Path,
    profiles: Any,
    build_design_vars_fn,
    teacher: Any,
    sample_from_settings_fn,
) -> Tuple[List[Any], Path, Path]:
    X_design, X, Y, n_new_samples = _resolve_training_arrays(
        settings=settings,
        resolved_model_info=resolved_model_info,
        retrain_decision=retrain_decision,
        profile_id=profile_id,
        targets=targets,
        profiles=profiles,
        build_design_vars_fn=build_design_vars_fn,
        teacher=teacher,
        sample_from_settings_fn=sample_from_settings_fn,
    )

    st = getattr(settings, "surrogate_train", None)
    holdout_frac = float(getattr(st, "holdout_frac", 0.2)) if st else 0.2
    sampler = getattr(settings, "sampler", None)
    seed = int(getattr(sampler, "seed", 42)) if sampler else 42
    X_train, X_test, Y_train, Y_test = train_test_split(X, Y, test_size=holdout_frac, random_state=seed)

    surrogate_cfg = getattr(settings, "surrogate", None)
    model_name = str(getattr(surrogate_cfg, "model", "rf"))
    model_params = dict(getattr(st, "model_params", {}) or {}) if st else {}

    models: List[Any] = []
    for j in range(Y.shape[1]):
        m = make_model(model_name, model_params, random_state=seed)
        m.fit(X_train, Y_train[:, j])
        models.append(m)
    Y_pred_test = np.column_stack([m.predict(X_test) for m in models]) if len(X_test) else np.zeros((0, Y.shape[1]), float)

    learning = getattr(settings, "learning", None)
    model_root = Path(getattr(learning, "active_model_root", "Learning/models")).resolve()
    native_artifact_dir = model_root / str(signature_hash)
    filenames = _artifact_filenames(settings)
    native_artifact_path = native_artifact_dir / filenames["primary_artifact"]
    legacy_artifact_path = native_artifact_dir / filenames["legacy_artifact"]
    native_meta_path = native_artifact_dir / filenames["primary_meta"]
    legacy_meta_path = native_artifact_dir / filenames["legacy_meta"]

    native_artifact_dir.mkdir(parents=True, exist_ok=True)
    payload = {
        "targets": targets,
        "models": models,
        "feature_names": feature_names,
        "feature_encoding": feature_encoding,
        "profile_id": profile_id,
        "system_id": system_id,
    }
    dump(payload, native_artifact_path)
    if legacy_artifact_path != native_artifact_path:
        dump(payload, legacy_artifact_path)
    meta = {
        "targets": targets,
        "feature_names": feature_names,
        "feature_encoding": feature_encoding,
        "profile_id": profile_id,
        "system_id": system_id,
        "signature_hash": signature_hash,
        "signature_dict": signature_dict,
    }
    native_meta_path.write_text(json.dumps(meta, indent=2), encoding="utf-8")
    if legacy_meta_path != native_meta_path:
        legacy_meta_path.write_text(json.dumps(meta, indent=2), encoding="utf-8")

    dataset_root = getattr(learning, "active_dataset_root", "Learning/datasets")
    family_hash = resolved_model_info.get("family_hash") or signature_hash
    action = str((retrain_decision or {}).get("action", "") or "")
    dataset_meta = {
        "targets": targets,
        "target_names": targets,
        "bounds_names": list(getattr(settings.bounds, "names", []) or []),
        "feature_names": feature_names,
        "profile_id": profile_id,
        "system_id": system_id,
        "family_hash": family_hash,
        "action": action,
        "n_samples": int(X_design.shape[0]),
        "n_new_samples": int(n_new_samples),
    }
    dataset_info = save_dataset(
        dataset_root,
        family_hash,
        X_design,
        X,
        Y,
        dataset_meta,
        bounds_names=list(getattr(settings.bounds, "names", []) or []),
        target_names=targets,
        family_spec=build_family(settings).to_dict(),
        source_runs=[
            {
                "source": "native_training",
                "signature_hash": str(signature_hash),
                "artifact_dir": str(native_artifact_dir),
                "action": action,
            }
        ],
    )
    register_dataset(
        settings,
        family_hash,
        f"dataset_{family_hash}",
        {
            "source": "native_training",
            "artifact_path": str(dataset_info["data_path"]),
            "meta_path": str(dataset_info["meta_path"]),
            "truth_csv_path": str(dataset_info["truth_csv_path"]),
            "truth_meta_path": str(dataset_info["truth_meta_path"]),
            "family_spec_path": str(dataset_info["family_spec_path"]) if dataset_info["family_spec_path"] else "",
            "source_runs_path": str(dataset_info["source_runs_path"]) if dataset_info["source_runs_path"] else "",
            "n_samples": int(X_design.shape[0]),
            "n_new_samples": int(n_new_samples),
            "is_active": True,
        },
    )
    model_id = f"native_{signature_hash}"
    register_model(
        settings,
        family_hash,
        model_id,
        {
            "source": "native_training",
            "backend_name": str(getattr(getattr(settings, "surrogate", None), "model", "rf")),
            "artifact_path": str(native_artifact_path),
            "meta_path": str(native_meta_path),
            "is_active": True,
            "is_preferred": False,
            "validation_stage": "candidate",
            "signature_hash": signature_hash,
        },
    )
    gate_result = evaluate_gate(
        settings,
        target_names=targets,
        y_true=Y_test,
        y_pred=Y_pred_test,
    )
    validation_stage = "eligible" if gate_result.get("eligible") else "blocked"
    extra_fields = {
        "gate_result": gate_result,
        "holdout_n_test": int(len(X_test)),
        "holdout_n_train": int(len(X_train)),
    }
    update_model_status(
        settings,
        family_hash,
        model_id,
        validation_stage=validation_stage,
        is_active=True,
        is_preferred=False,
        extra_fields=extra_fields,
    )
    return models, native_artifact_dir, native_artifact_path, {
        "model_id": model_id,
        "family_hash": family_hash,
        "gate_result": gate_result,
        "validation_stage": validation_stage,
        "n_train": int(len(X_train)),
        "n_test": int(len(X_test)),
        "n_samples": int(X_design.shape[0]),
        "n_new_samples": int(n_new_samples),
    }
