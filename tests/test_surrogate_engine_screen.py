from __future__ import annotations

from types import SimpleNamespace

import numpy as np

from Optimization.framework.engines.Surrogat_model import surrogate_engine as surrogate_module
from Optimization.framework.engines.Surrogat_model.surrogate_engine import SurrogateEngine


class _ConstantTargetModel:
    def __init__(self, values: list[float]) -> None:
        self._values = np.asarray(values, dtype=float)

    def predict(self, X: np.ndarray) -> np.ndarray:
        assert X.shape[0] == self._values.shape[0]
        return self._values


class _Screen:
    def constraint_values(self, X: np.ndarray) -> np.ndarray:
        assert X.shape[0] == 2
        return np.asarray([[0.25], [-0.10]], dtype=float)


def test_evaluate_uses_screen_constraint_without_kpi_constraint_lookup(monkeypatch) -> None:
    engine = SurrogateEngine.__new__(SurrogateEngine)
    engine._models_F = [_ConstantTargetModel([100.0, 200.0])]
    engine._targets = ["E_import_grid_kWh"]
    engine.obj_names = ["grid_import_kwh"]
    engine.con_names = ["surrogate_feasible_probability_guard"]
    engine._objectives_in_targets = False
    engine._feasibility_screen = _Screen()
    engine.s = SimpleNamespace()
    engine.profiles = {}
    engine._augment_features = lambda X: X
    engine._direct_objective_target_names = lambda: None
    engine._can_score_direct_objectives = lambda: False
    engine._flows_dict = lambda row: {"E_import_grid_kWh": float(row[0])}
    engine._build_design_vars = lambda row: {"params": {"lifetime": 1}}

    def _fail_if_kpi_constraints_are_evaluated(*args, **kwargs):
        raise AssertionError("screen constraints must not be sent through compute_kpis")

    monkeypatch.setattr(surrogate_module, "compute_kpis", _fail_if_kpi_constraints_are_evaluated)
    monkeypatch.setattr(
        surrogate_module,
        "compute_objectives",
        lambda flows, design_vars, settings, profiles: {"grid_import_kwh": flows["E_import_grid_kWh"]},
    )

    F, G = engine.evaluate(np.asarray([[1.0], [2.0]], dtype=float))

    np.testing.assert_allclose(F, np.asarray([[100.0], [200.0]], dtype=float))
    np.testing.assert_allclose(G, np.asarray([[0.25], [-0.10]], dtype=float))
    assert F.shape[0] == G.shape[0] == 2
