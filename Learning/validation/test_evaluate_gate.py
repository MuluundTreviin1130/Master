from __future__ import annotations

import unittest
from types import SimpleNamespace

import numpy as np

from Learning.validation.evaluate_gate import evaluate_gate


def _settings() -> SimpleNamespace:
    gate = SimpleNamespace(
        enabled=True,
        fail_on_nan_predictions=True,
        min_pass_share=0.9,
        critical_target_min_r2=0.95,
        critical_target_max_rel_mae_percent=8.0,
        secondary_target_min_r2=0.85,
        secondary_target_max_rel_mae_percent=15.0,
        critical_targets=["critical_kpi"],
    )
    return SimpleNamespace(learning=SimpleNamespace(validation_gate=gate))


class EvaluateGateTests(unittest.TestCase):
    def test_exact_predictions_are_eligible(self) -> None:
        y = np.array([[1.0, 10.0], [2.0, 20.0], [3.0, 30.0]], dtype=float)

        result = evaluate_gate(
            _settings(),
            target_names=["critical_kpi", "secondary_kpi"],
            y_true=y,
            y_pred=y.copy(),
        )

        self.assertTrue(result["eligible"])
        self.assertEqual(result["reason"], "ok")
        self.assertEqual(result["failed_targets"], [])

    def test_failed_critical_target_blocks_even_when_pass_share_is_high(self) -> None:
        y_true = np.array(
            [
                [10.0, 100.0, 200.0, 300.0],
                [20.0, 110.0, 210.0, 310.0],
                [30.0, 120.0, 220.0, 320.0],
                [40.0, 130.0, 230.0, 330.0],
            ],
            dtype=float,
        )
        y_pred = y_true.copy()
        y_pred[:, 0] = 1000.0

        result = evaluate_gate(
            _settings(),
            target_names=["critical_kpi", "a", "b", "c"],
            y_true=y_true,
            y_pred=y_pred,
        )

        self.assertFalse(result["eligible"])
        self.assertEqual(result["reason"], "metrics_below_threshold")
        self.assertEqual(result["failed_critical_targets"], ["critical_kpi"])

    def test_nonfinite_predictions_fail_fast(self) -> None:
        y_true = np.array([[1.0], [2.0]], dtype=float)
        y_pred = np.array([[1.0], [np.nan]], dtype=float)

        result = evaluate_gate(
            _settings(),
            target_names=["critical_kpi"],
            y_true=y_true,
            y_pred=y_pred,
        )

        self.assertFalse(result["eligible"])
        self.assertEqual(result["reason"], "nonfinite_values")

    def test_target_column_mismatch_reports_insufficient_coverage(self) -> None:
        y = np.array([[1.0, 2.0], [2.0, 3.0]], dtype=float)

        result = evaluate_gate(
            _settings(),
            target_names=["critical_kpi"],
            y_true=y,
            y_pred=y.copy(),
        )

        self.assertFalse(result["eligible"])
        self.assertEqual(result["reason"], "insufficient_target_coverage")


if __name__ == "__main__":
    unittest.main()
