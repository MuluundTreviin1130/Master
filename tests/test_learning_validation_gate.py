from __future__ import annotations

import unittest
from types import SimpleNamespace

import numpy as np

from Learning.validation.evaluate_gate import evaluate_gate
from Settings.learning import ValidationGateConfig


def _settings(*, critical_targets: list[str] | None = None) -> SimpleNamespace:
    gate = ValidationGateConfig(
        critical_targets=list(critical_targets or ["critical_flow"]),
        min_pass_share=0.5,
        critical_target_min_r2=0.9,
        critical_target_max_rel_mae_percent=10.0,
        secondary_target_min_r2=0.5,
        secondary_target_max_rel_mae_percent=50.0,
    )
    return SimpleNamespace(learning=SimpleNamespace(validation_gate=gate))


class ValidationGateTest(unittest.TestCase):
    def test_blocks_missing_critical_target_coverage(self) -> None:
        result = evaluate_gate(
            _settings(critical_targets=["critical_flow"]),
            target_names=["secondary_flow"],
            y_true=np.array([[1.0], [2.0], [3.0]]),
            y_pred=np.array([[1.0], [2.0], [3.0]]),
        )

        self.assertFalse(result["eligible"])
        self.assertEqual(result["reason"], "insufficient_target_coverage")
        self.assertEqual(result["missing_critical_targets"], ["critical_flow"])

    def test_blocks_nan_predictions(self) -> None:
        result = evaluate_gate(
            _settings(critical_targets=["critical_flow"]),
            target_names=["critical_flow"],
            y_true=np.array([[1.0], [2.0], [3.0]]),
            y_pred=np.array([[1.0], [np.nan], [3.0]]),
        )

        self.assertFalse(result["eligible"])
        self.assertEqual(result["reason"], "nan_predictions")
        self.assertEqual(result["nan_targets"], ["critical_flow"])

    def test_marks_high_quality_predictions_eligible(self) -> None:
        result = evaluate_gate(
            _settings(critical_targets=["critical_flow"]),
            target_names=["critical_flow", "secondary_flow"],
            y_true=np.array([[10.0, 3.0], [20.0, 4.0], [30.0, 5.0]]),
            y_pred=np.array([[10.0, 3.0], [20.0, 4.0], [30.0, 5.0]]),
        )

        self.assertTrue(result["eligible"])
        self.assertEqual(result["reason"], "eligible")
        self.assertEqual(result["failed_targets"], [])

    def test_allows_secondary_failure_when_pass_share_threshold_is_met(self) -> None:
        result = evaluate_gate(
            _settings(critical_targets=["critical_flow"]),
            target_names=["critical_flow", "secondary_flow"],
            y_true=np.array([[10.0, 1.0], [20.0, 2.0], [30.0, 3.0]]),
            y_pred=np.array([[10.0, 100.0], [20.0, 100.0], [30.0, 100.0]]),
        )

        self.assertTrue(result["eligible"])
        self.assertEqual(result["reason"], "eligible")
        self.assertEqual(result["failed_secondary_targets"], ["secondary_flow"])


if __name__ == "__main__":
    unittest.main()

