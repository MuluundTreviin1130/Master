from __future__ import annotations

import unittest
from types import SimpleNamespace

import numpy as np

from Learning.validation.evaluate_gate import evaluate_gate


def _settings() -> SimpleNamespace:
    return SimpleNamespace(
        learning=SimpleNamespace(
            validation_gate=SimpleNamespace(
                enabled=True,
                require_full_target_coverage=True,
                fail_on_nan_predictions=True,
                min_pass_share=0.9,
                critical_target_min_r2=0.95,
                critical_target_max_rel_mae_percent=8.0,
                secondary_target_min_r2=0.85,
                secondary_target_max_rel_mae_percent=15.0,
                critical_targets=["cost"],
            )
        )
    )


class EvaluateGateTest(unittest.TestCase):
    def test_exact_holdout_predictions_are_eligible(self) -> None:
        y_true = np.array([[1.0, 2.0], [2.0, 4.0], [3.0, 6.0]])

        result = evaluate_gate(
            _settings(),
            target_names=["cost", "co2"],
            y_true=y_true,
            y_pred=y_true.copy(),
        )

        self.assertTrue(result["eligible"])
        self.assertEqual(result["reason"], "passed")
        self.assertEqual(result["pass_share"], 1.0)
        self.assertEqual(result["failed_targets"], [])

    def test_failed_critical_target_blocks_eligibility(self) -> None:
        y_true = np.array([[10.0, 2.0], [20.0, 4.0], [30.0, 6.0]])
        y_pred = np.array([[0.0, 2.0], [0.0, 4.0], [0.0, 6.0]])

        result = evaluate_gate(
            _settings(),
            target_names=["cost", "co2"],
            y_true=y_true,
            y_pred=y_pred,
        )

        self.assertFalse(result["eligible"])
        self.assertEqual(result["reason"], "metrics_below_threshold")
        self.assertEqual(result["failed_critical_targets"], ["cost"])
        self.assertIn("cost", result["failed_targets"])

    def test_shape_mismatch_fails_fast(self) -> None:
        with self.assertRaises(ValueError):
            evaluate_gate(
                _settings(),
                target_names=["cost"],
                y_true=np.array([[1.0], [2.0]]),
                y_pred=np.array([[1.0, 2.0], [2.0, 3.0]]),
            )

    def test_surrogate_training_module_imports_gate(self) -> None:
        import Learning.training.train_surrogate as train_surrogate

        self.assertTrue(hasattr(train_surrogate, "evaluate_gate"))

    def test_missing_teacher_target_fails_fast(self) -> None:
        import Learning.training.train_surrogate as train_surrogate

        class Teacher:
            def evaluate_one_with_details(self, _row):
                return None, None, {"present_target": 1.0}, {"raw": "ok"}

        old_compute_kpis = train_surrogate.compute_kpis
        old_is_objective = train_surrogate.is_supported_objective_name
        try:
            train_surrogate.compute_kpis = lambda *args, **kwargs: ({}, {}, {})
            train_surrogate.is_supported_objective_name = lambda _params, _target: False
            with self.assertRaises(KeyError):
                train_surrogate._evaluate_teacher_targets(
                    teacher=Teacher(),
                    settings=SimpleNamespace(),
                    profiles=SimpleNamespace(),
                    profile_id="profile",
                    targets=["missing_target"],
                    build_design_vars_fn=lambda _row: {"params": {}},
                    X_design_new=np.array([[1.0]]),
                )
        finally:
            train_surrogate.compute_kpis = old_compute_kpis
            train_surrogate.is_supported_objective_name = old_is_objective

    def test_existing_dataset_features_are_reaugmented(self) -> None:
        import Learning.training.train_surrogate as train_surrogate

        old_augment = train_surrogate.augment_features
        try:
            train_surrogate.augment_features = lambda _settings, x_design, _profile_id: np.column_stack(
                [x_design, np.full(x_design.shape[0], 99.0)]
            )
            x_design, x, y = train_surrogate._reaugment_existing_dataset(
                settings=SimpleNamespace(),
                profile_id="profile",
                existing_dataset={
                    "X_design": np.array([[1.0], [2.0]]),
                    "X": np.array([[1.0, -1.0], [2.0, -1.0]]),
                    "Y": np.array([[10.0], [20.0]]),
                },
            )
        finally:
            train_surrogate.augment_features = old_augment

        np.testing.assert_allclose(x_design, np.array([[1.0], [2.0]]))
        np.testing.assert_allclose(x, np.array([[1.0, 99.0], [2.0, 99.0]]))
        np.testing.assert_allclose(y, np.array([[10.0], [20.0]]))


if __name__ == "__main__":
    unittest.main()

