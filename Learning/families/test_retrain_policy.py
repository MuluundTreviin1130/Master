from __future__ import annotations

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
        from Learning.policies import resolve_retrain as policy

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

        with (
            patch.object(policy, "load_registry", return_value=registry),
            patch.object(policy, "build_family", return_value=current),
            patch.object(policy, "resolve_model", return_value=resolved_model),
            patch.object(policy, "resolve_dataset", return_value=resolved_dataset),
        ):
            decision = policy.resolve_retrain(settings=object())

        self.assertEqual(decision["status"], "refit_required")
        self.assertEqual(decision["action"], "train_model")


if __name__ == "__main__":
    unittest.main()
