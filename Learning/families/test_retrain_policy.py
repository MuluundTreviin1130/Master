from __future__ import annotations

import importlib
import sys
import types
import unittest
from unittest.mock import patch

from Learning.families.compare_families import compare_families
from Learning.families.resolve_family_status import resolve_family_status


class _Family:
    """Minimal family object used to isolate policy decisions from runtime I/O."""

    family_hash = "family-hash"

    def __init__(self, model_name: str, model_params: dict[str, object]) -> None:
        self._spec = {
            "system": {"system_id": "ec"},
            "input_schema": {"names": ["pv_kwp"]},
            "feature_schema": {"names": ["pv_kwp"]},
            "target_schema": {"names": ["npc_eur"]},
            "search_space": {"names": ["pv_kwp"]},
            "training_spec": {
                "model_name": model_name,
                "model_params": model_params,
            },
            "time_model": {"resolution": "1h"},
            "dispatch_signature": {"dispatch_model_id": "default"},
            "provenance": {},
            "family_hash": self.family_hash,
        }

    def to_dict(self) -> dict[str, object]:
        return dict(self._spec)


class RetrainPolicyTests(unittest.TestCase):
    def test_training_spec_change_requires_refit(self) -> None:
        old = _Family("rf", {"n_estimators": 100})
        current = _Family("xgb", {"n_estimators": 300})

        differences = compare_families(current, old)
        status = resolve_family_status(current, old)

        self.assertEqual(differences["refit_changed"], ["training_spec"])
        self.assertEqual(differences["family_changed"], [])
        self.assertEqual(status.status, "refit_required")

    def test_existing_model_does_not_override_refit_decision(self) -> None:
        old = _Family("rf", {"n_estimators": 100})
        current = _Family("xgb", {"n_estimators": 300})
        registry = {
            "families": {
                current.family_hash: {
                    "spec": old.to_dict(),
                }
            }
        }
        resolved_model = {
            "found": True,
            "entry": {"source": "native_training"},
        }
        resolved_dataset = {"found": True}

        # Isolate this pure policy test from the heavyweight runtime imports.
        # The base revision currently lacks Settings.validation, which is an
        # independent import defect handled by its own fix.
        build_family_module = types.ModuleType("Learning.families.build_family")
        build_family_module.build_family = lambda _settings: current
        resolve_model_module = types.ModuleType("Learning.runtime.resolve_model")
        resolve_model_module.resolve_model = lambda _settings: resolved_model
        resolve_dataset_module = types.ModuleType("Learning.runtime.resolve_dataset")
        resolve_dataset_module.resolve_dataset = lambda _settings: resolved_dataset

        with patch.dict(
            sys.modules,
            {
                "Learning.families.build_family": build_family_module,
                "Learning.runtime.resolve_model": resolve_model_module,
                "Learning.runtime.resolve_dataset": resolve_dataset_module,
            },
        ):
            sys.modules.pop("Learning.policies.resolve_retrain", None)
            policy = importlib.import_module("Learning.policies.resolve_retrain")
            with patch.object(policy, "load_registry", return_value=registry):
                decision = policy.resolve_retrain(settings=object())

        self.assertEqual(decision["status"], "refit_required")
        self.assertEqual(decision["action"], "train_model")


if __name__ == "__main__":
    unittest.main()
