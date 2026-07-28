"""Family hash must separate constant ThermFlex lower-bound policies."""

from __future__ import annotations

import importlib
import sys
import types
import unittest
from types import SimpleNamespace


def _load_build_family_module():
    """Load build_family with a features stub that still exposes ThermFlex identity."""

    features_mod = types.ModuleType("Optimization.framework.engines.Surrogat_model.features")
    features_mod.resolve_feature_encoding = lambda settings: {"mode": "raw"}
    features_mod.resolve_feature_names = lambda settings: list(getattr(settings.bounds, "names", []) or [])
    features_mod.resolve_surrogate_targets = lambda settings: ["dispatch_operating_cost_eur"]

    def thermflex_policy_identity(settings):
        thermflex_cfg = getattr(getattr(settings, "constraints", None), "thermflex", None)

        def optional_float(value):
            return None if value is None else float(value)

        return {
            "constant_lower_bound_c": optional_float(
                getattr(thermflex_cfg, "constant_lower_bound_c", None)
            ),
            "day_lower_bound_c": optional_float(getattr(thermflex_cfg, "day_lower_bound_c", None)),
            "night_lower_bound_c": optional_float(
                getattr(thermflex_cfg, "night_lower_bound_c", None)
            ),
            "use_explicit_lower_bounds": bool(
                getattr(thermflex_cfg, "use_explicit_lower_bounds", False)
            ),
            "constrain_upper_temperature": bool(
                getattr(thermflex_cfg, "constrain_upper_temperature", False)
            ),
            "max_flex_duration_h": float(getattr(thermflex_cfg, "max_flex_duration_h", 0.0) or 0.0),
            "max_flex_events_per_day": float(
                getattr(thermflex_cfg, "max_flex_events_per_day", 0.0) or 0.0
            ),
        }

    features_mod.thermflex_policy_identity = thermflex_policy_identity

    for name in (
        "Optimization",
        "Optimization.framework",
        "Optimization.framework.engines",
        "Optimization.framework.engines.Surrogat_model",
    ):
        sys.modules.setdefault(name, types.ModuleType(name))
    sys.modules["Optimization.framework.engines.Surrogat_model.features"] = features_mod

    module_name = "Learning.families.build_family"
    sys.modules.pop(module_name, None)
    return importlib.import_module(module_name)


def _settings(*, constant_lower_bound_c, constrain_upper_temperature: bool = False):
    return SimpleNamespace(
        engine=SimpleNamespace(system_id="integrated_energy_system"),
        run=SimpleNamespace(tag="test"),
        surrogate=SimpleNamespace(model="rf"),
        surrogate_train=SimpleNamespace(model_params={}),
        market=SimpleNamespace(active_tariff_arm="flat"),
        learning=SimpleNamespace(
            dispatch_model_id="default",
            resolution="1h",
            horizon_type="full_year",
            time_series_schema=[],
            location_mode="dataset_context",
        ),
        bounds=SimpleNamespace(names=["pv_kwp"], steps=[1.0], caps={}),
        constraints=SimpleNamespace(
            thermflex=SimpleNamespace(
                use_explicit_lower_bounds=True,
                constant_lower_bound_c=constant_lower_bound_c,
                day_lower_bound_c=None,
                night_lower_bound_c=None,
                constrain_upper_temperature=constrain_upper_temperature,
                max_flex_duration_h=24,
                max_flex_events_per_day=24,
            )
        ),
    )


class FamilyThermflexPolicyIdentityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.mod = _load_build_family_module()

    def test_constant_lower_bound_changes_family_hash(self):
        # Concrete trigger: lb21 lower-relax vs lb22.5 upper-only with otherwise
        # identical schemas must not share a family_hash / curated dataset path.
        lb21 = self.mod.build_family(_settings(constant_lower_bound_c=21.0))
        lb22 = self.mod.build_family(
            _settings(constant_lower_bound_c=22.5, constrain_upper_temperature=True)
        )
        self.assertNotEqual(lb21.family_hash, lb22.family_hash)
        self.assertEqual(lb21.dispatch_signature["dispatch_params"]["constant_lower_bound_c"], 21.0)
        self.assertEqual(lb22.dispatch_signature["dispatch_params"]["constant_lower_bound_c"], 22.5)


if __name__ == "__main__":
    unittest.main()
