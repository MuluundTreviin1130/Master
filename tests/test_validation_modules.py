from __future__ import annotations

from types import SimpleNamespace
import unittest

import numpy as np

from Learning.validation import evaluate_gate
from Settings.validation import HoldoutConfig, make_validation


class ValidationModuleTests(unittest.TestCase):
    def test_make_validation_exposes_holdout_contract(self) -> None:
        cfg = make_validation()

        self.assertIsInstance(cfg.holdout, HoldoutConfig)
        self.assertEqual(cfg.holdout.root_dir, "Optimization/run/validation/results")
        self.assertEqual(cfg.holdout.model_id, "")
        self.assertEqual(cfg.holdout.artifact_path, "")

    def test_evaluate_gate_blocks_missing_critical_targets(self) -> None:
        settings = _settings(critical_targets=["critical"])

        result = evaluate_gate(
            settings,
            target_names=["secondary"],
            y_true=np.array([[1.0], [2.0], [3.0]]),
            y_pred=np.array([[1.0], [2.0], [3.0]]),
        )

        self.assertFalse(result["eligible"])
        self.assertEqual(result["reason"], "insufficient_target_coverage")
        self.assertEqual(result["missing_critical_targets"], ["critical"])

    def test_evaluate_gate_passes_exact_critical_holdout(self) -> None:
        settings = _settings(critical_targets=["critical"], min_pass_share=1.0)

        result = evaluate_gate(
            settings,
            target_names=["critical"],
            y_true=np.array([[1.0], [2.0], [3.0]]),
            y_pred=np.array([[1.0], [2.0], [3.0]]),
        )

        self.assertTrue(result["eligible"])
        self.assertEqual(result["failed_critical_targets"], [])
        self.assertAlmostEqual(result["pass_share"], 1.0)


def _settings(**gate_overrides: object) -> SimpleNamespace:
    defaults = {
        "enabled": True,
        "require_full_target_coverage": True,
        "critical_targets": [],
        "critical_target_min_r2": 0.95,
        "critical_target_max_rel_mae_percent": 8.0,
        "secondary_target_min_r2": 0.85,
        "secondary_target_max_rel_mae_percent": 15.0,
        "min_pass_share": 0.9,
    }
    defaults.update(gate_overrides)
    return SimpleNamespace(learning=SimpleNamespace(validation_gate=SimpleNamespace(**defaults)))


if __name__ == "__main__":
    unittest.main()
