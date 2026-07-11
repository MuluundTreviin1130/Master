from __future__ import annotations

import unittest
from types import SimpleNamespace

import numpy as np

from Learning.validation.evaluate_gate import evaluate_gate
from Settings.learning import make_learning


class EvaluateGateTest(unittest.TestCase):
    def test_perfect_holdout_predictions_pass_gate(self) -> None:
        settings = SimpleNamespace(learning=make_learning())
        targets = settings.learning.validation_gate.critical_targets[:2]
        y_true = np.array([[1.0, 10.0], [2.0, 20.0], [3.0, 30.0]])

        result = evaluate_gate(
            settings,
            target_names=targets,
            y_true=y_true,
            y_pred=y_true.copy(),
        )

        self.assertTrue(result["eligible"])
        self.assertEqual(result["failed_targets"], [])

    def test_bad_critical_holdout_target_blocks_gate(self) -> None:
        settings = SimpleNamespace(learning=make_learning())
        targets = settings.learning.validation_gate.critical_targets[:1]
        y_true = np.array([[1.0], [2.0], [3.0]])
        y_pred = np.array([[3.0], [2.0], [1.0]])

        result = evaluate_gate(
            settings,
            target_names=targets,
            y_true=y_true,
            y_pred=y_pred,
        )

        self.assertFalse(result["eligible"])
        self.assertEqual(result["failed_critical_targets"], targets)


if __name__ == "__main__":
    unittest.main()
