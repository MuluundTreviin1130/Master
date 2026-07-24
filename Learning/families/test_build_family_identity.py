from __future__ import annotations

import importlib
import sys
import types
import unittest
from types import SimpleNamespace

from Learning.families.resolve_family_status import resolve_family_status


def _load_build_family_module():
    """
    Load build_family with stubbed feature/target resolvers.

    The production module imports Optimization feature helpers that pull pandas
    through Data/. Focused identity tests only need the hashing contract, so we
    stub those resolvers instead of installing the full runtime stack.
    """
    features_mod = types.ModuleType("Optimization.framework.engines.Surrogat_model.features")
    features_mod.resolve_feature_encoding = lambda settings: {"mode": "raw"}
    features_mod.resolve_feature_names = lambda settings: list(getattr(settings.bounds, "names", []) or [])
    features_mod.resolve_surrogate_targets = lambda settings: ["npc_eur"]

    # Ensure parent packages exist as ordinary modules so importlib can bind the stub.
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


def _settings(*, delta_T: float = 0.0, active_tariff_arm: str = "flat") -> SimpleNamespace:
    return SimpleNamespace(
        engine=SimpleNamespace(system_id="integrated_energy_system"),
        run=SimpleNamespace(tag="unit"),
        surrogate=SimpleNamespace(model="rf"),
        surrogate_train=SimpleNamespace(model_params={}),
        bounds=SimpleNamespace(names=["pv_kwp"], steps=[1.0], caps={"pv_kwp": 10.0}),
        learning=SimpleNamespace(
            resolution="1h",
            horizon_type="full_year",
            time_series_schema=[],
            location_mode="dataset_context",
            dispatch_model_id="default",
        ),
        thermal=SimpleNamespace(delta_T=delta_T),
        market=SimpleNamespace(active_tariff_arm=active_tariff_arm),
    )


class BuildFamilyIdentityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.mod = _load_build_family_module()

    def test_delta_t_change_creates_new_family_hash(self) -> None:
        # Concrete trigger: switch ThermFlex comfort band from 0K to 2K while
        # every other schema field stays identical. Teacher labels change, so
        # the dataset/model family must change too.
        base = self.mod.build_family(_settings(delta_T=0.0))
        flexed = self.mod.build_family(_settings(delta_T=2.0))
        self.assertNotEqual(base.family_hash, flexed.family_hash)
        self.assertEqual(base.dispatch_signature["dispatch_params"]["delta_T"], 0.0)
        self.assertEqual(flexed.dispatch_signature["dispatch_params"]["delta_T"], 2.0)
        resolved = resolve_family_status(flexed, base)
        self.assertEqual(resolved.status, "new_family_required")
        self.assertIn("dispatch_signature", resolved.family_changed)

    def test_active_tariff_arm_change_creates_new_family_hash(self) -> None:
        # Concrete trigger: keep thermal fixed but switch market tariff arm.
        # Economic teacher targets such as npc_eur then belong to another family.
        flat = self.mod.build_family(_settings(active_tariff_arm="flat"))
        dynamic = self.mod.build_family(_settings(active_tariff_arm="dynamic"))
        self.assertNotEqual(flat.family_hash, dynamic.family_hash)
        self.assertEqual(flat.dispatch_signature["active_tariff_arm"], "flat")
        self.assertEqual(dynamic.dispatch_signature["active_tariff_arm"], "dynamic")
        resolved = resolve_family_status(dynamic, flat)
        self.assertEqual(resolved.status, "new_family_required")
        self.assertIn("dispatch_signature", resolved.family_changed)

    def test_missing_thermal_fails_fast(self) -> None:
        settings = _settings()
        delattr(settings, "thermal")
        with self.assertRaisesRegex(ValueError, "settings.thermal is required"):
            self.mod.build_family(settings)

    def test_missing_market_fails_fast(self) -> None:
        settings = _settings()
        delattr(settings, "market")
        with self.assertRaisesRegex(ValueError, "settings.market is required"):
            self.mod.build_family(settings)

    def test_hardcoded_zero_delta_t_no_longer_masks_settings(self) -> None:
        # Regression lock: dispatch_signature must mirror Settings.thermal.delta_T
        # instead of a silent 0.0 placeholder.
        spec = self.mod.build_family(_settings(delta_T=1.5, active_tariff_arm="tou"))
        self.assertEqual(spec.dispatch_signature["dispatch_params"]["delta_T"], 1.5)
        self.assertEqual(spec.dispatch_signature["active_tariff_arm"], "tou")
        self.assertEqual(spec.provenance["active_tariff_arm"], "tou")


if __name__ == "__main__":
    unittest.main()
