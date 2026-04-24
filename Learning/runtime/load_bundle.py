from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List

from joblib import load


def _artifact_filenames(settings: Any | None = None) -> Dict[str, str]:
    learning = getattr(settings, "learning", None) if settings is not None else None
    return {
        "primary_artifact": str(getattr(learning, "primary_artifact_filename", "surrogate_bundle.joblib")),
        "legacy_artifact": str(getattr(learning, "legacy_artifact_filename", "surrogate_rf.joblib")),
    }


def choose_artifact_path(
    signature_hash: str,
    resolved_model_info: Dict[str, Any],
    settings: Any | None = None,
) -> Dict[str, Path]:
    filenames = _artifact_filenames(settings)
    learning_root = (Path("Learning") / "models").resolve()
    artifact_root = learning_root
    scoped_dir = artifact_root / str(signature_hash)
    scoped_path = scoped_dir / filenames["primary_artifact"]
    scoped_legacy_path = scoped_dir / filenames["legacy_artifact"]
    legacy_artifact_root = (Path("Optimization") / "run" / "artifacts").resolve()
    legacy_scoped_dir = legacy_artifact_root / "surrogates" / str(signature_hash)
    legacy_scoped_primary_path = legacy_scoped_dir / filenames["primary_artifact"]
    legacy_scoped_path = legacy_scoped_dir / filenames["legacy_artifact"]
    legacy_path = legacy_artifact_root / filenames["legacy_artifact"]

    resolved_path = resolved_model_info.get("artifact_path")
    if resolved_model_info.get("found") and resolved_path is not None:
        artifact_path = Path(resolved_path)
        return {
            "artifact_root": artifact_root,
            "artifact_dir": artifact_path.parent,
            "artifact_path": artifact_path,
        }
    if scoped_path.exists():
        return {
            "artifact_root": artifact_root,
            "artifact_dir": scoped_dir,
            "artifact_path": scoped_path,
        }
    if scoped_legacy_path.exists():
        return {
            "artifact_root": artifact_root,
            "artifact_dir": scoped_dir,
            "artifact_path": scoped_legacy_path,
        }
    if legacy_scoped_primary_path.exists():
        return {
            "artifact_root": legacy_artifact_root,
            "artifact_dir": legacy_scoped_dir,
            "artifact_path": legacy_scoped_primary_path,
        }
    if legacy_scoped_path.exists():
        return {
            "artifact_root": legacy_artifact_root,
            "artifact_dir": legacy_scoped_dir,
            "artifact_path": legacy_scoped_path,
        }
    if legacy_path.exists():
        return {
            "artifact_root": legacy_artifact_root,
            "artifact_dir": legacy_artifact_root,
            "artifact_path": legacy_path,
        }
    return {
        "artifact_root": artifact_root,
        "artifact_dir": scoped_dir,
        "artifact_path": scoped_path,
    }


def load_bundle(
    artifact_path: Path,
    required_targets: List[str],
    feature_names: List[str],
    expected_input_dim: int,
    profile_id: str,
    system_id: str,
) -> Dict[str, Any]:
    if not artifact_path.exists():
        return {
            "status": "missing",
            "reason": "artifact_missing",
            "models": [],
            "targets": list(required_targets),
        }

    payload = load(artifact_path)
    meta = payload.get("meta", {}) if isinstance(payload.get("meta"), dict) else {}
    meta_engine = meta.get("engine", {}) if isinstance(meta.get("engine"), dict) else {}
    meta_train = meta.get("surrogate_train", {}) if isinstance(meta.get("surrogate_train"), dict) else {}

    loaded_targets = list(
        payload.get("targets", [])
        or meta.get("surrogate_targets", [])
        or meta.get("targets", [])
        or []
    )
    loaded_models = list(payload.get("models", []) or payload.get("F", []) or [])
    loaded_features = list(
        payload.get("feature_names", [])
        or meta.get("feature_names", [])
        or meta_train.get("feature_names", [])
        or []
    )
    loaded_profile_id = payload.get("profile_id", None) or meta.get("profile_id", None)
    loaded_system_id = payload.get("system_id", None) or meta.get("system_id", None) or meta_engine.get("system_id", None)
    loaded_n_features = getattr(loaded_models[0], "n_features_in_", None) if loaded_models else None

    missing_targets = set(required_targets) - set(loaded_targets)
    feature_mismatch = list(loaded_features) != list(feature_names)
    profile_mismatch = loaded_profile_id is not None and str(loaded_profile_id) != str(profile_id)
    system_mismatch = loaded_system_id is not None and str(loaded_system_id) != str(system_id)
    feature_count_mismatch = loaded_n_features is not None and int(loaded_n_features) != int(expected_input_dim)
    count_mismatch = len(loaded_models) != len(required_targets)
    critical_missing = any(t not in loaded_targets for t in required_targets)

    if (
        missing_targets
        or count_mismatch
        or feature_mismatch
        or profile_mismatch
        or system_mismatch
        or feature_count_mismatch
        or critical_missing
    ):
        reason = "artifact_mismatch"
        if critical_missing:
            reason = "missing_critical_targets"
        return {
            "status": "mismatch",
            "reason": reason,
            "models": [],
            "targets": list(required_targets),
            "payload": payload,
        }

    for model in loaded_models:
        if hasattr(model, "n_jobs"):
            try:
                setattr(model, "n_jobs", 1)
            except Exception:
                pass

    return {
        "status": "loaded",
        "reason": "ok",
        "models": loaded_models,
        "targets": loaded_targets,
        "payload": payload,
    }
