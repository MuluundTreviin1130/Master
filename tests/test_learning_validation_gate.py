from __future__ import annotations

import importlib.util
from pathlib import Path
import sys
from types import SimpleNamespace
import unittest

import numpy as np

from Learning.validation.evaluate_gate import evaluate_gate


def _load_make_validation():
    module_path = Path(__file__).resolve().parents[1] / "Settings" / "validation" / "holdout.py"
    spec = importlib.util.spec_from_file_location("settings_validation_holdout_under_test", module_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Could not load validation settings module from {module_path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module.make_validation


def _settings_with_gate(**overrides):
    defaults = {
        "enabled": True,
        "fail_on_nan_predictions": True,
        "min_pass_share": 0.9,
        "critical_targets": ["critical_target"],
        "critical_target_min_r2": 0.95,
        "critical_target_max_rel_mae_percent": 8.0,
        "secondary_target_min_r2": 0.85,
        "secondary_target_max_rel_mae_percent": 15.0,
    }
    defaults.update(overrides)
    return SimpleNamespace(learning=SimpleNamespace(validation_gate=SimpleNamespace(**defaults)))


class ValidationGateTests(unittest.TestCase):
    def test_perfect_holdout_passes(self) -> None:
        settings = _settings_with_gate()
        y_true = np.array([[1.0, 10.0], [2.0, 20.0], [3.0, 30.0]])
        y_pred = y_true.copy()

        result = evaluate_gate(
            settings,
            target_names=["critical_target", "secondary_target"],
            y_true=y_true,
            y_pred=y_pred,
        )

        self.assertTrue(result["eligible"])
        self.assertEqual(result["reason"], "ok")
        self.assertEqual(result["failed_targets"], [])

    def test_critical_target_failure_blocks_model(self) -> None:
        settings = _settings_with_gate()
        y_true = np.array([[1.0, 10.0], [2.0, 20.0], [3.0, 30.0]])
        y_pred = np.array([[0.0, 10.0], [0.0, 20.0], [0.0, 30.0]])

        result = evaluate_gate(
            settings,
            target_names=["critical_target", "secondary_target"],
            y_true=y_true,
            y_pred=y_pred,
        )

        self.assertFalse(result["eligible"])
        self.assertEqual(result["reason"], "metrics_below_threshold")
        self.assertEqual(result["failed_critical_targets"], ["critical_target"])

    def test_non_finite_holdout_blocks_model(self) -> None:
        settings = _settings_with_gate()
        y_true = np.array([[1.0], [2.0], [3.0]])
        y_pred = np.array([[1.0], [float("nan")], [3.0]])

        result = evaluate_gate(
            settings,
            target_names=["critical_target"],
            y_true=y_true,
            y_pred=y_pred,
        )

        self.assertFalse(result["eligible"])
        self.assertEqual(result["reason"], "non_finite_holdout_values")

    def test_holdout_validation_settings_have_explicit_defaults(self) -> None:
        make_validation = _load_make_validation()
        validation = make_validation()

        self.assertEqual(validation.holdout.model_id, "")
        self.assertEqual(validation.holdout.artifact_path, "")


if __name__ == "__main__":
    unittest.main()
