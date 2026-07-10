from __future__ import annotations

import unittest
from types import SimpleNamespace

import numpy as np

from Learning.validation.evaluate_gate import evaluate_gate


def _settings(*, require_full_target_coverage: bool = False) -> SimpleNamespace:
    return SimpleNamespace(
        learning=SimpleNamespace(
            validation_gate=SimpleNamespace(
                enabled=True,
                require_full_target_coverage=require_full_target_coverage,
                fail_on_nan_predictions=True,
                min_pass_share=1.0,
                critical_target_min_r2=0.99,
                critical_target_max_rel_mae_percent=1.0,
                secondary_target_min_r2=0.5,
                secondary_target_max_rel_mae_percent=20.0,
                critical_targets=["critical_target", "missing_critical_target"],
            )
        )
    )


class EvaluateGateTest(unittest.TestCase):
    def test_perfect_holdout_prediction_is_eligible(self) -> None:
        y_true = np.array([[1.0], [2.0], [3.0]])
        y_pred = np.array([[1.0], [2.0], [3.0]])

        result = evaluate_gate(
            _settings(require_full_target_coverage=False),
            target_names=["critical_target"],
            y_true=y_true,
            y_pred=y_pred,
        )

        self.assertTrue(result["eligible"])
        self.assertEqual(result["reason"], "passed")
        self.assertEqual(result["failed_targets"], [])

    def test_missing_configured_critical_target_blocks_full_coverage_gate(self) -> None:
        y_true = np.array([[1.0], [2.0], [3.0]])
        y_pred = np.array([[1.0], [2.0], [3.0]])

        result = evaluate_gate(
            _settings(require_full_target_coverage=True),
            target_names=["critical_target"],
            y_true=y_true,
            y_pred=y_pred,
        )

        self.assertFalse(result["eligible"])
        self.assertEqual(result["reason"], "insufficient_target_coverage")
        self.assertEqual(result["failed_critical_targets"], ["missing_critical_target"])

    def test_nonfinite_holdout_values_block_gate(self) -> None:
        y_true = np.array([[1.0], [2.0], [3.0]])
        y_pred = np.array([[1.0], [np.nan], [3.0]])

        result = evaluate_gate(
            _settings(require_full_target_coverage=False),
            target_names=["critical_target"],
            y_true=y_true,
            y_pred=y_pred,
        )

        self.assertFalse(result["eligible"])
        self.assertEqual(result["reason"], "nonfinite_holdout_values")
        self.assertEqual(result["failed_critical_targets"], ["critical_target"])


if __name__ == "__main__":
    unittest.main()
