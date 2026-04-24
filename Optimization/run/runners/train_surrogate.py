from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

# Project-root bootstrap like run_optimization.py: project root with Optimization + Data
current = Path(__file__).resolve()
project_root = None
for parent in current.parents:
    if (parent / "Optimization").is_dir() and (parent / "Data").is_dir():
        project_root = parent
        break
if project_root is None:
    raise RuntimeError(
        f"[train_surrogate] project root (with Optimization + Data) not found.\n"
        f"  cwd: {Path.cwd()}\n"
        f"  script: {current}"
    )
project_root_str = str(project_root.resolve())
if project_root_str not in sys.path:
    sys.path.insert(0, project_root_str)

from Settings import get_settings
from Optimization.framework.engines.Surrogat_model.features import (
    build_signature_context_payload,
    build_signature_system_flags,
    resolve_feature_encoding,
    resolve_feature_names,
    resolve_surrogate_family,
    resolve_surrogate_targets,
)
from Optimization.framework.engines.Surrogat_model.training import auto_train_surrogate
from Optimization.framework.engines.signature_utils import build_signature_dict, signature_hash
from Optimization.framework.engines.profiles_meta import get_profile_id
from Optimization.framework.engines.Gated.io import promote_surrogate_version
from Technical_model.energy_system.precompute.adapter import prepare_profiles_adapter

CLICK_TRAIN_DEFAULT_OVERRIDES = (
    Path("Optimization")
    / "validation"
    / "model_validation"
    / "overrides"
    / "thermflex"
    / "vienna_ref2023_dh_day_night_thermflex_surrogate_train.json"
)


def _parse_args() -> argparse.Namespace:
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--overrides-json",
        type=str,
        default=None,
        help="Path to JSON overrides passed to get_settings(overrides=...).",
    )
    return ap.parse_args()


def _load_overrides(path: str | None) -> dict:
    if not path:
        if len(sys.argv) <= 1 and CLICK_TRAIN_DEFAULT_OVERRIDES.exists():
            print(
                "[train_surrogate] No CLI arguments provided. "
                f"Using click-train default overrides: {CLICK_TRAIN_DEFAULT_OVERRIDES}",
                flush=True,
            )
            path = str(CLICK_TRAIN_DEFAULT_OVERRIDES)
        else:
            return {}
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"[train_surrogate] overrides file not found: {p}")
    return json.loads(p.read_text(encoding="utf-8-sig"))


def _build_signature_hash(settings) -> str:
    targets = resolve_surrogate_targets(settings)
    if not targets:
        raise ValueError("[train_surrogate] surrogate_train.targets is empty.")

    prep = prepare_profiles_adapter(settings)
    profile_id = get_profile_id(prep.profiles, settings)
    system_id = str(getattr(getattr(settings, "engine", None), "system_id", "unknown"))
    feature_names = resolve_feature_names(settings)
    feature_encoding = resolve_feature_encoding(settings)
    surrogate_family = resolve_surrogate_family(settings)
    engine_version_tag = f"ec_flex_surrogate_family_{surrogate_family}_20260318"
    system_flags = build_signature_system_flags(settings, prep.params_base)
    signature_system_flags = dict(system_flags)
    signature_system_flags["surrogate_family"] = surrogate_family

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
            "static_context": build_signature_context_payload(settings, profile_id),
            "system_flags": signature_system_flags,
            "engine_version": engine_version_tag,
        },
    )
    return signature_hash(signature_dict)


if __name__ == "__main__":
    args = _parse_args()
    overrides = _load_overrides(args.overrides_json)
    s = get_settings(overrides=overrides)
    artifact_path = auto_train_surrogate(s)
    out_dir = Path(artifact_path).resolve().parent
    sig_hash = _build_signature_hash(s)
    promote_surrogate_version(sig_hash, out_dir, run_dir=str(out_dir))
    print(f"[train_surrogate] artifact: {artifact_path}")
    print(f"[train_surrogate] promoted to: Optimization/run/artifacts/surrogates/{sig_hash}/")
