from __future__ import annotations

import json
import unittest

import numpy as np

from Learning.validation.evaluate_gate import evaluate_gate
from Settings.learning import make_learning


class EvaluateGateTest(unittest.TestCase):
    def _settings(self):
        class Settings:
            pass

        settings = Settings()
        settings.learning = make_learning()
        gate = settings.learning.validation_gate
        gate.critical_targets = ["critical_target"]
        gate.min_pass_share = 1.0
        return settings

    def test_marks_model_eligible_when_all_targets_pass(self) -> None:
        settings = self._settings()
        y_true = np.array(
            [
                [10.0, 100.0],
                [20.0, 200.0],
                [30.0, 300.0],
                [40.0, 400.0],
            ]
        )
        y_pred = y_true.copy()

        result = evaluate_gate(
            settings,
            target_names=["critical_target", "secondary_target"],
            y_true=y_true,
            y_pred=y_pred,
        )

        self.assertTrue(result["eligible"])
        self.assertEqual(result["reason"], "metrics_passed")
        self.assertEqual(result["failed_targets"], [])
        json.dumps(result, allow_nan=False)

    def test_blocks_when_critical_target_fails(self) -> None:
        settings = self._settings()
        settings.learning.validation_gate.min_pass_share = 0.0
        y_true = np.array(
            [
                [10.0, 100.0],
                [20.0, 200.0],
                [30.0, 300.0],
                [40.0, 400.0],
            ]
        )
        y_pred = np.array(
            [
                [40.0, 100.0],
                [30.0, 200.0],
                [20.0, 300.0],
                [10.0, 400.0],
            ]
        )

        result = evaluate_gate(
            settings,
            target_names=["critical_target", "secondary_target"],
            y_true=y_true,
            y_pred=y_pred,
        )

        self.assertFalse(result["eligible"])
        self.assertEqual(result["reason"], "metrics_below_threshold")
        self.assertEqual(result["failed_critical_targets"], ["critical_target"])
        json.dumps(result, allow_nan=False)

    def test_blocks_missing_target_coverage_without_crashing(self) -> None:
        settings = self._settings()
        y_true = np.array([[1.0], [2.0], [3.0]])
        y_pred = y_true.copy()

        result = evaluate_gate(
            settings,
            target_names=["critical_target", "secondary_target"],
            y_true=y_true,
            y_pred=y_pred,
        )

        self.assertFalse(result["eligible"])
        self.assertEqual(result["reason"], "insufficient_target_coverage")
        self.assertEqual(result["observed_target_columns"], 1)
        self.assertEqual(result["expected_target_columns"], 2)
        json.dumps(result, allow_nan=False)


if __name__ == "__main__":
    unittest.main()
