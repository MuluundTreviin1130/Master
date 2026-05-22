from __future__ import annotations

import unittest

import numpy as np

from Learning.validation.evaluate_gate import evaluate_gate
from Settings.learning import make_learning


class _Settings:
    def __init__(self) -> None:
        self.learning = make_learning()


class EvaluateGateTest(unittest.TestCase):
    def test_perfect_predictions_are_eligible(self) -> None:
        settings = _Settings()
        targets = ["dispatch_operating_cost_eur", "secondary_target"]
        y_true = np.array([[100.0, 5.0], [200.0, 5.0], [300.0, 5.0]], dtype=float)

        result = evaluate_gate(settings, target_names=targets, y_true=y_true, y_pred=y_true.copy())

        self.assertTrue(result["eligible"])
        self.assertEqual(result["failed_targets"], [])
        self.assertEqual(result["pass_share"], 1.0)

    def test_bad_critical_target_blocks_model(self) -> None:
        settings = _Settings()
        targets = ["dispatch_operating_cost_eur", "secondary_target"]
        y_true = np.array([[100.0, 5.0], [200.0, 5.0], [300.0, 5.0]], dtype=float)
        y_pred = np.array([[0.0, 5.0], [0.0, 5.0], [0.0, 5.0]], dtype=float)

        result = evaluate_gate(settings, target_names=targets, y_true=y_true, y_pred=y_pred)

        self.assertFalse(result["eligible"])
        self.assertEqual(result["failed_critical_targets"], ["dispatch_operating_cost_eur"])

    def test_nonfinite_prediction_blocks_when_configured(self) -> None:
        settings = _Settings()
        targets = ["secondary_target"]
        y_true = np.array([[1.0], [2.0], [3.0]], dtype=float)
        y_pred = np.array([[1.0], [np.nan], [3.0]], dtype=float)

        result = evaluate_gate(settings, target_names=targets, y_true=y_true, y_pred=y_pred)

        self.assertFalse(result["eligible"])
        self.assertEqual(result["failed_targets"], ["secondary_target"])
        self.assertIn("nonfinite_prediction", result["target_results"][0]["reasons"])


if __name__ == "__main__":
    unittest.main()
