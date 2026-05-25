from __future__ import annotations

import importlib.util
from pathlib import Path
import sys
from types import SimpleNamespace
import unittest

from Learning.validation.evaluate_gate import evaluate_gate


REPO_ROOT = Path(__file__).resolve().parents[1]


def _load_module(name: str, relative_path: str):
    spec = importlib.util.spec_from_file_location(name, REPO_ROOT / relative_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Could not load module from {relative_path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def _settings_with_gate(**overrides):
    gate_defaults = {
        "enabled": True,
        "require_full_target_coverage": True,
        "fail_on_nan_predictions": True,
        "min_pass_share": 0.9,
        "critical_target_min_r2": 0.95,
        "critical_target_max_rel_mae_percent": 8.0,
        "secondary_target_min_r2": 0.85,
        "secondary_target_max_rel_mae_percent": 15.0,
        "critical_targets": ["critical"],
    }
    gate_defaults.update(overrides)
    return SimpleNamespace(learning=SimpleNamespace(validation_gate=SimpleNamespace(**gate_defaults)))


class ValidationRecoveryTests(unittest.TestCase):
    def test_evaluate_gate_passes_exact_critical_holdout(self) -> None:
        result = evaluate_gate(
            _settings_with_gate(),
            target_names=["critical"],
            y_true=[[1.0], [2.0], [3.0]],
            y_pred=[[1.0], [2.0], [3.0]],
        )

        self.assertTrue(result["eligible"])
        self.assertEqual(result["reason"], "passed")
        self.assertEqual(result["failed_targets"], [])

    def test_evaluate_gate_blocks_missing_critical_target_coverage(self) -> None:
        result = evaluate_gate(
            _settings_with_gate(critical_targets=["critical", "missing"]),
            target_names=["critical"],
            y_true=[[1.0], [2.0], [3.0]],
            y_pred=[[1.0], [2.0], [3.0]],
        )

        self.assertFalse(result["eligible"])
        self.assertEqual(result["reason"], "insufficient_target_coverage")
        self.assertEqual(result["failed_critical_targets"], ["missing"])

    def test_settings_validation_config_exposes_holdout_override_fields(self) -> None:
        module = _load_module("settings_validation_holdout_test", "Settings/validation/holdout.py")
        cfg = module.make_validation()

        self.assertEqual(cfg.holdout.model_id, "")
        self.assertEqual(cfg.holdout.artifact_path, "")

    def test_dispatch_price_defaults_point_to_repo_csvs(self) -> None:
        module = _load_module("dispatch_config_test", "Settings/dispatch/dispatch.py")
        cfg = module.make_dispatch()

        self.assertTrue(Path(cfg.historical_gas_day_ahead_price_csv).is_file())
        self.assertTrue(Path(cfg.historical_co2_price_csv).is_file())

    def test_learning_teacher_targets_do_not_use_zero_fallback(self) -> None:
        source = (REPO_ROOT / "Learning/training/train_surrogate.py").read_text(encoding="utf-8")

        self.assertIn("missing required surrogate targets", source)
        self.assertNotIn("flows_L.get(t, 0.0)", source)
        self.assertNotIn("flows_L.get(target, 0.0)", source)


if __name__ == "__main__":
    unittest.main()
