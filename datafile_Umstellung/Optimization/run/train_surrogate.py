from __future__ import annotations

import sys
from pathlib import Path
from typing import List

from Optimization.framework.Settings.get_settings import get_settings
from Optimization.framework.Settings.surrogate_train import make_surrogate_train
from Optimization.framework.engines.Surrogat_model.training import auto_train_surrogate
from Optimization.framework.engines.signature_utils import build_signature_dict, signature_hash
from Optimization.framework.engines.profiles_meta import get_profile_id
from Optimization.framework.engines.Gated.io import promote_surrogate_version
from Technical_model.energy_system.precompute.adapter import prepare_profiles_adapter


def _resolve_targets(settings) -> List[str]:
    train_cfg = getattr(settings, "surrogate_train", None)
    targets = list(getattr(train_cfg, "targets", []) or [])
    if targets:
        return targets
    return list(getattr(make_surrogate_train(), "targets", []) or [])


def _build_signature_hash(settings) -> str:
    targets = _resolve_targets(settings)
    if not targets:
        raise ValueError("[train_surrogate] surrogate_train.targets is empty.")

    prep = prepare_profiles_adapter(settings)
    profile_id = get_profile_id(prep.profiles, settings)
    system_id = str(getattr(getattr(settings, "engine", None), "system_id", "unknown"))

    # Get feature_names and feature_encoding from settings instead of hardcoding
    train_cfg = getattr(settings, "surrogate_train", None)
    if train_cfg:
        feature_names = list(getattr(train_cfg, "feature_names", []) or [])
        feature_encoding = dict(getattr(train_cfg, "feature_encoding", {}) or {})
    else:
        default_cfg = make_surrogate_train()
        feature_names = list(getattr(default_cfg, "feature_names", []) or [])
        feature_encoding = dict(getattr(default_cfg, "feature_encoding", {}) or {})

    signature_dict = build_signature_dict(
        settings,
        surrogate_meta_hint={
            "targets": targets,
            "feature_names": feature_names,
            "feature_encoding": feature_encoding,
            "profile_id": profile_id,
            "system_id": system_id,
        },
        system_context={
            "runtime_targets": targets,
            "feature_names": feature_names,
            "feature_encoding": feature_encoding,
            "profile_id": profile_id,
            "system_id": system_id,
        },
    )
    return signature_hash(signature_dict)


if __name__ == "__main__":
    # Path bootstrap wie run_optimization.py
    current = Path(__file__).resolve()
    workspace_root = None
    datafile_umstellung_dir = None

    for parent in current.parents:
        v2h_dir = parent / "V2H_energy_community_surrogat_datafilenew"
        if v2h_dir.exists():
            workspace_root = parent
            datafile_umstellung_dir = v2h_dir / "datafile_Umstellung"
            break

    if workspace_root is None:
        workspace_root = current.parent.parent.parent.parent.parent
        datafile_umstellung_dir = workspace_root / "V2H_energy_community_surrogat_datafilenew" / "datafile_Umstellung"

    workspace_root_str = str(workspace_root.resolve())
    if workspace_root_str not in sys.path:
        sys.path.insert(0, workspace_root_str)

    if datafile_umstellung_dir and datafile_umstellung_dir.exists():
        datafile_umstellung_str = str(datafile_umstellung_dir.resolve())
        if datafile_umstellung_str not in sys.path:
            sys.path.insert(0, datafile_umstellung_str)
    else:
        raise RuntimeError(
            f"[train_surrogate] datafile_Umstellung Ordner nicht gefunden!\n"
            f"  Gesucht in: {workspace_root / 'V2H_energy_community_surrogat_datafilenew' / 'datafile_Umstellung'}\n"
            f"  Aktuelles Verzeichnis: {Path.cwd()}\n"
            f"  Script-Pfad: {current}"
        )

    s = get_settings()
    artifact_path = auto_train_surrogate(s)
    out_dir = Path(artifact_path).resolve().parent
    sig_hash = _build_signature_hash(s)
    promote_surrogate_version(sig_hash, out_dir, run_dir=str(out_dir))
    print(f"[train_surrogate] artifact: {artifact_path}")
    print(f"[train_surrogate] promoted to: Optimization/run/artifacts/surrogates/{sig_hash}/")
