from __future__ import annotations

import sys
import types
import unittest
from types import SimpleNamespace

import numpy as np


class _ModelStub:
    def __init__(self, *_args: object, **_kwargs: object) -> None:
        pass


class _KernelStub:
    def __init__(self, *_args: object, **_kwargs: object) -> None:
        pass

    def __mul__(self, _other: object) -> "_KernelStub":
        return self


def _install_optional_ml_stubs() -> None:
    """Keep these focused tests independent of optional local ML packages."""
    joblib = types.ModuleType("joblib")
    joblib.dump = lambda *_args, **_kwargs: None
    sklearn = types.ModuleType("sklearn")
    model_selection = types.ModuleType("sklearn.model_selection")
    model_selection.train_test_split = lambda *arrays, **_kwargs: arrays
    ensemble = types.ModuleType("sklearn.ensemble")
    ensemble.RandomForestRegressor = _ModelStub
    gaussian_process = types.ModuleType("sklearn.gaussian_process")
    gaussian_process.GaussianProcessRegressor = _ModelStub
    kernels = types.ModuleType("sklearn.gaussian_process.kernels")
    kernels.RBF = _KernelStub
    kernels.ConstantKernel = _KernelStub
    sys.modules.setdefault("joblib", joblib)
    sys.modules.setdefault("sklearn", sklearn)
    sys.modules.setdefault("sklearn.model_selection", model_selection)
    sys.modules.setdefault("sklearn.ensemble", ensemble)
    sys.modules.setdefault("sklearn.gaussian_process", gaussian_process)
    sys.modules.setdefault("sklearn.gaussian_process.kernels", kernels)


_install_optional_ml_stubs()

from Learning.training.train_surrogate import _evaluate_teacher_targets
from Learning.validation.evaluate_gate import evaluate_gate
from Optimization.framework.engines.kpi import compute_objectives


def _settings(objectives: list[str] | None = None) -> SimpleNamespace:
    return SimpleNamespace(
        objectives=SimpleNamespace(names=list(objectives or [])),
        constraints=SimpleNamespace(names=[]),
        learning=SimpleNamespace(
            validation_gate=SimpleNamespace(
                enabled=True,
                require_full_target_coverage=True,
                fail_on_nan_predictions=True,
                min_pass_share=0.9,
                critical_targets=["critical_target"],
                critical_target_min_r2=0.95,
                critical_target_max_rel_mae_percent=8.0,
                secondary_target_min_r2=0.85,
                secondary_target_max_rel_mae_percent=15.0,
            )
        ),
    )


class _TeacherWithMissingTarget:
    def evaluate_one_with_details(self, _row: np.ndarray) -> tuple[None, None, dict[str, float], dict[str, float]]:
        return None, None, {"known_target": 1.0}, {}


class CriticalBugFixTests(unittest.TestCase):
    def test_teacher_target_extraction_rejects_missing_targets(self) -> None:
        with self.assertRaisesRegex(KeyError, "missing required surrogate targets"):
            _evaluate_teacher_targets(
                teacher=_TeacherWithMissingTarget(),
                settings=_settings(),
                profiles={},
                profile_id="test_profile",
                targets=["known_target", "missing_target"],
                build_design_vars_fn=lambda _row: {"params": {"lifetime": 25}},
                X_design_new=np.array([[1.0]], dtype=float),
            )

    def test_validation_gate_import_path_accepts_perfect_holdout(self) -> None:
        result = evaluate_gate(
            _settings(),
            target_names=["critical_target"],
            y_true=np.array([[1.0], [2.0], [3.0]], dtype=float),
            y_pred=np.array([[1.0], [2.0], [3.0]], dtype=float),
        )

        self.assertIs(result["eligible"], True)
        self.assertEqual(result["reason"], "passed")
        self.assertEqual(result["failed_targets"], [])

    def test_lca_objective_rejects_active_h2_placeholder_data(self) -> None:
        params = {
            "lifetime": 25,
            "PV": {"LCA": {"infra": {"climate_change": 1.0}, "op": {}, "meta": {}}},
            "BESS": {"LCA": {"infra": {}, "op": {}, "meta": {}}},
            "Grid": {"LCA": {"infra": {}, "op": {"climate_change": 0.1}, "meta": {}}},
            "FC": {"LCA": {"infra": {"climate_change": 2.0}, "op": {}, "meta": {}}},
            "ELY": {
                "LCA": {
                    "infra": {"climate_change": 0.0},
                    "op": {"climate_change": 0.0},
                    "meta": {"placeholder": True},
                }
            },
            "H2_TANK": {"LCA": {"infra": {"climate_change": 0.0}, "op": {}, "meta": {}}},
        }

        with self.assertRaisesRegex(ValueError, "placeholder LCA data for electrolyzer"):
            compute_objectives(
                flows_L={"E_import_grid_kWh": 1.0, "E_total_load_kWh": 1.0},
                design_vars={"params": params, "ely_kw": 1.0},
                settings=_settings(objectives=["climate_change"]),
            )


if __name__ == "__main__":
    unittest.main()
