from __future__ import annotations

from typing import Any, Dict

from Learning.families.resolve_family_status import resolve_family_status
from Learning.registry.load_registry import load_registry
from Learning.runtime.resolve_dataset import resolve_dataset
from Learning.runtime.resolve_model import resolve_model
from Learning.families.build_family import build_family


def resolve_retrain(settings: Any, force_native: bool = False) -> Dict[str, Any]:
    learning = getattr(settings, "learning", None)
    force_native = bool(force_native or getattr(learning, "force_native_retrain", False))
    force_append = bool(getattr(learning, "force_append_then_train", False))
    registry_path = getattr(learning, "registry_path", "Learning/registry/registry.json")
    registry = load_registry(registry_path)
    family = build_family(settings)
    family_hash = family.family_hash
    families = registry.get("families", {}) or {}
    family_exists = family_hash in families
    resolved_model = resolve_model(settings)
    resolved_dataset = resolve_dataset(settings)
    found_model = bool(resolved_model.get("found"))
    family_status = None
    if family_exists:
        existing_spec = dict(families[family_hash].get("spec", {}) or {})
        family_status = resolve_family_status(family, existing_spec)

    model_source = str((resolved_model.get("entry") or {}).get("source", "") or "")
    has_native_model = bool(found_model and model_source == "native_training")
    has_dataset = bool(resolved_dataset.get("found"))

    if force_append and has_dataset:
        status = "append_only"
        action = "append_then_train"
    elif force_native and not has_native_model:
        if family_status is not None and family_status.status == "append_only":
            status = "append_only"
            action = "append_then_train"
        elif family_exists:
            status = "refit_required"
            action = "train_model"
        else:
            status = "new_family_required"
            action = "register_and_train"
    elif family_status is not None and family_status.status == "append_only":
        status = "append_only"
        action = "append_then_train"
    elif found_model and not has_native_model and not has_dataset:
        status = "bootstrap_only"
        action = "load_bootstrap_model"
    elif found_model:
        status = "reusable"
        action = "load_model"
    elif family_exists:
        status = "refit_required"
        action = "train_model"
    else:
        status = "new_family_required"
        action = "register_and_train"

    return {
        "status": status,
        "action": action,
        "family_hash": family_hash,
        "family_exists": family_exists,
        "family_status": None
        if family_status is None
        else {
            "status": family_status.status,
            "family_changed": family_status.family_changed,
            "append_changed": family_status.append_changed,
            "refit_changed": family_status.refit_changed,
            "provenance_changed": family_status.provenance_changed,
        },
        "resolved_model": resolved_model,
        "resolved_dataset": resolved_dataset,
        "has_native_model": has_native_model,
        "has_dataset": has_dataset,
    }
