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


def _settings(
    *,
    dispatch_mode: str = "milp_day_ahead",
    horizon_h: int = 24,
    stochastic_enabled: bool = False,
    district_heating_share: float = 0.0,
    dispatch_model_id: str = "default",
) -> SimpleNamespace:
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
            dispatch_model_id=dispatch_model_id,
        ),
        market=SimpleNamespace(active_tariff_arm="flat"),
        dispatch=SimpleNamespace(
            mode=dispatch_mode,
            horizon_h=horizon_h,
            stochastic_enabled=stochastic_enabled,
        ),
        district_heating=SimpleNamespace(share=district_heating_share),
    )


class BuildFamilyDispatchContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.mod = _load_build_family_module()

    def test_dispatch_mode_change_creates_new_family_hash(self) -> None:
        # Concrete trigger: train under milp_day_ahead, then switch to
        # milp_two_stage while leaving learning.dispatch_model_id="default".
        # Teacher labels change, but the old family_hash would otherwise keep
        # resolve_model / choose_artifact_path on the previous native artifact.
        day_ahead = self.mod.build_family(_settings(dispatch_mode="milp_day_ahead"))
        two_stage = self.mod.build_family(_settings(dispatch_mode="milp_two_stage"))
        self.assertNotEqual(day_ahead.family_hash, two_stage.family_hash)
        self.assertEqual(day_ahead.dispatch_signature["dispatch_mode"], "milp_day_ahead")
        self.assertEqual(two_stage.dispatch_signature["dispatch_mode"], "milp_two_stage")
        resolved = resolve_family_status(two_stage, day_ahead)
        self.assertEqual(resolved.status, "new_family_required")
        self.assertIn("dispatch_signature", resolved.family_changed)

    def test_horizon_change_creates_new_family_hash(self) -> None:
        # Concrete trigger: keep mode fixed but widen the commitment horizon.
        h24 = self.mod.build_family(_settings(horizon_h=24))
        h48 = self.mod.build_family(_settings(horizon_h=48))
        self.assertNotEqual(h24.family_hash, h48.family_hash)
        self.assertEqual(h24.dispatch_signature["dispatch_horizon_h"], 24)
        self.assertEqual(h48.dispatch_signature["dispatch_horizon_h"], 48)

    def test_stochastic_flag_change_creates_new_family_hash(self) -> None:
        # Concrete trigger: enable stochastic scenarios under the same mode.
        deterministic = self.mod.build_family(_settings(stochastic_enabled=False))
        stochastic = self.mod.build_family(_settings(stochastic_enabled=True))
        self.assertNotEqual(deterministic.family_hash, stochastic.family_hash)
        self.assertFalse(deterministic.dispatch_signature["dispatch_stochastic_enabled"])
        self.assertTrue(stochastic.dispatch_signature["dispatch_stochastic_enabled"])

    def test_district_heating_share_change_creates_new_family_hash(self) -> None:
        # Concrete trigger: change the EC/DH demand split while schemas stay
        # identical. Coupled teacher costs then belong to another family.
        share0 = self.mod.build_family(_settings(district_heating_share=0.0))
        share1 = self.mod.build_family(_settings(district_heating_share=1.0))
        self.assertNotEqual(share0.family_hash, share1.family_hash)
        self.assertEqual(share0.dispatch_signature["district_heating_share"], 0.0)
        self.assertEqual(share1.dispatch_signature["district_heating_share"], 1.0)

    def test_missing_dispatch_fails_fast(self) -> None:
        settings = _settings()
        delattr(settings, "dispatch")
        with self.assertRaisesRegex(ValueError, "settings.dispatch is required"):
            self.mod.build_family(settings)

    def test_missing_district_heating_fails_fast(self) -> None:
        settings = _settings()
        delattr(settings, "district_heating")
        with self.assertRaisesRegex(ValueError, "settings.district_heating is required"):
            self.mod.build_family(settings)

    def test_invalid_horizon_fails_fast(self) -> None:
        with self.assertRaisesRegex(ValueError, "horizon_h must be a positive integer"):
            self.mod.build_family(_settings(horizon_h=0))

    def test_invalid_share_fails_fast(self) -> None:
        with self.assertRaisesRegex(ValueError, "share must be in \\[0, 1\\]"):
            self.mod.build_family(_settings(district_heating_share=1.5))


if __name__ == "__main__":
    unittest.main()
