"""Focused tests for ThermFlex policy identity in native surrogate features."""

from __future__ import annotations

import importlib
import sys
import types
import unittest
from types import SimpleNamespace

import numpy as np


def _load_features_module():
    """Load features.py without importing the full Settings package graph.

    Settings/__init__.py currently requires Settings.validation, which is absent
    on master because ``validation/`` is gitignored. These unit tests only need
    the ThermFlex identity helpers, so we stub the light dependencies.
    """

    settings_pkg = types.ModuleType("Settings")
    settings_pkg.__path__ = []
    surrogate_pkg = types.ModuleType("Settings.surrogate")
    surrogate_pkg.__path__ = []
    train_mod = types.ModuleType("Settings.surrogate.train")

    def make_surrogate_train():
        return SimpleNamespace(
            feature_names=[
                "pv_kwp",
                "bess_kwh",
                "constant_setpoint_c",
                "day_setpoint_c",
                "night_setpoint_c",
                "day_lower_bound_c",
                "night_lower_bound_c",
                "thermflex_max_duration_h",
                "thermflex_max_events_per_day",
            ],
            feature_encoding={},
            targets=["dispatch_operating_cost_eur"],
            target_profile="dispatch_optimization_core",
            target_profiles={"dispatch_optimization_core": ["dispatch_operating_cost_eur"]},
            append_active_technology_targets=False,
            include_objectives=False,
        )

    train_mod.make_surrogate_train = make_surrogate_train
    sys.modules["Settings"] = settings_pkg
    sys.modules["Settings.surrogate"] = surrogate_pkg
    sys.modules["Settings.surrogate.train"] = train_mod

    for name in (
        "Optimization",
        "Optimization.framework",
        "Optimization.framework.engines",
        "Optimization.framework.engines.Surrogat_model",
    ):
        sys.modules.setdefault(name, types.ModuleType(name))

    kpi_mod = types.ModuleType("Optimization.framework.engines.kpi")
    kpi_mod.get_selected_objective_names = lambda settings: ["dispatch_operating_cost_eur"]
    sys.modules["Optimization.framework.engines.kpi"] = kpi_mod

    sig_mod = types.ModuleType("Optimization.framework.engines.signature_utils")

    def build_signature_dict(cfg, surrogate_meta_hint=None, system_context=None):
        system_context = system_context or {}
        return {
            "static_context": dict(system_context.get("static_context", {}) or {}),
            "feature_schema": {"names": list(system_context.get("feature_names", []) or [])},
            "profile_id": str(system_context.get("profile_id") or "unknown"),
            "system_id": str(system_context.get("system_id") or "unknown"),
        }

    def signature_hash(signature_dict):
        import hashlib
        import json

        payload = json.dumps(signature_dict, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()

    sig_mod.build_signature_dict = build_signature_dict
    sig_mod.signature_hash = signature_hash
    sys.modules["Optimization.framework.engines.signature_utils"] = sig_mod

    module_name = "Optimization.framework.engines.Surrogat_model.features"
    sys.modules.pop(module_name, None)
    return importlib.import_module(module_name)


def _settings(*, constant_lower_bound_c, constrain_upper_temperature: bool = False):
    return SimpleNamespace(
        engine=SimpleNamespace(
            system_id="integrated_energy_system",
            features=SimpleNamespace(
                enable_bess=False,
                enable_v2h=False,
                enable_h2=False,
                enable_thermflex=True,
                enable_small_wind=False,
                enable_large_wind=False,
                enable_biogas_engine=False,
                enable_wood_gasifier=False,
            ),
            N_EV_total=0,
            N_EV_bidirectional=0,
            location="Vienna",
        ),
        technology_activation=SimpleNamespace(
            district_external_heat=True,
            district_gas_boiler=True,
            district_heat_pump=True,
            district_thermal_storage=True,
            district_wood_chip_boiler=False,
            district_biomass_chp=True,
            district_biogas_chp=False,
            district_gas_chp=True,
            district_geothermal=False,
            district_solar_thermal=False,
            district_waste_incineration=False,
        ),
        heating_control=SimpleNamespace(
            reference_control_mode="constant",
            control_mode="constant",
            constant_setpoint_c=22.5,
            day_setpoint_c=None,
            night_setpoint_c=None,
        ),
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
        market=SimpleNamespace(active_tariff_arm="flat"),
        district_heating=SimpleNamespace(share=1.0),
        dispatch=SimpleNamespace(mode="milp_day_ahead", stochastic_enabled=False),
        bounds=SimpleNamespace(names=["pv_kwp", "bess_kwh"]),
        objectives=SimpleNamespace(names=["dispatch_operating_cost_eur"], minimize=[True]),
        surrogate_train=SimpleNamespace(
            targets=["dispatch_operating_cost_eur"],
            feature_names=[],
            feature_encoding={},
        ),
    )


class ThermflexPolicyIdentityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.features = _load_features_module()
        cls.signature_utils = sys.modules["Optimization.framework.engines.signature_utils"]

    def test_constant_lower_bound_changes_static_vector_and_signature(self):
        lb21 = _settings(constant_lower_bound_c=21.0, constrain_upper_temperature=False)
        lb22 = _settings(constant_lower_bound_c=22.5, constrain_upper_temperature=True)

        vec21 = self.features.build_static_feature_vector(lb21, "vienna_ref2023")
        vec22 = self.features.build_static_feature_vector(lb22, "vienna_ref2023")
        self.assertFalse(np.array_equal(vec21, vec22))

        payload21 = self.features.build_signature_context_payload(lb21, "vienna_ref2023")
        payload22 = self.features.build_signature_context_payload(lb22, "vienna_ref2023")
        self.assertEqual(payload21["constant_lower_bound_c"], 21.0)
        self.assertEqual(payload22["constant_lower_bound_c"], 22.5)
        self.assertNotEqual(payload21, payload22)

        hash21 = self.signature_utils.signature_hash(
            self.signature_utils.build_signature_dict(
                lb21,
                system_context={
                    "feature_names": self.features.resolve_feature_names(lb21),
                    "profile_id": "vienna_ref2023",
                    "system_id": "integrated_energy_system",
                    "static_context": payload21,
                },
            )
        )
        hash22 = self.signature_utils.signature_hash(
            self.signature_utils.build_signature_dict(
                lb22,
                system_context={
                    "feature_names": self.features.resolve_feature_names(lb22),
                    "profile_id": "vienna_ref2023",
                    "system_id": "integrated_energy_system",
                    "static_context": payload22,
                },
            )
        )
        self.assertNotEqual(hash21, hash22)

    def test_feature_names_include_constant_lower_bound(self):
        names = self.features.resolve_feature_names(_settings(constant_lower_bound_c=21.0))
        self.assertIn("constant_lower_bound_c", names)
        self.assertIn("use_explicit_lower_bounds", names)
        self.assertIn("constrain_upper_temperature", names)

    def test_augment_features_rebuilds_static_columns_from_current_settings(self):
        stale = _settings(constant_lower_bound_c=22.5)
        current = _settings(constant_lower_bound_c=21.0)
        X_design = np.array([[10.0, 20.0], [11.0, 21.0]], dtype=float)
        stale_X = self.features.augment_features(stale, X_design, "vienna_ref2023")
        rebuilt_X = self.features.augment_features(current, X_design, "vienna_ref2023")
        self.assertEqual(stale_X.shape, rebuilt_X.shape)
        self.assertFalse(np.array_equal(stale_X, rebuilt_X))
        self.assertTrue(np.array_equal(stale_X[:, :2], rebuilt_X[:, :2]))

    def test_unset_constant_lower_bound_stays_null_in_identity(self):
        settings = _settings(constant_lower_bound_c=None)
        identity = self.features.thermflex_policy_identity(settings)
        self.assertIsNone(identity["constant_lower_bound_c"])
        payload = self.features.build_signature_context_payload(settings, "vienna_ref2023")
        self.assertIsNone(payload["constant_lower_bound_c"])


if __name__ == "__main__":
    unittest.main()
