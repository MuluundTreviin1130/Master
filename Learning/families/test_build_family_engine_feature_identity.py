"""Family hash must separate SH/GIW engine feature-flag arms."""

from __future__ import annotations

import importlib
import sys
import types
import unittest
from pathlib import Path
from types import SimpleNamespace


REPO_ROOT = Path(__file__).resolve().parents[2]


def _install_stub(name: str, module: types.ModuleType) -> None:
    sys.modules[name] = module
    parent_name, _, child_name = name.rpartition(".")
    if parent_name:
        parent = sys.modules.get(parent_name)
        if parent is None:
            parent = types.ModuleType(parent_name)
            parent.__path__ = []  # type: ignore[attr-defined]
            _install_stub(parent_name, parent)
        setattr(parent, child_name, module)


def _load_build_family():
    """Import-light load: stub feature helpers so Settings/pandas chains stay out."""
    features_mod = types.ModuleType(
        "Optimization.framework.engines.Surrogat_model.features"
    )

    def resolve_feature_names(_settings):
        return ["pv_kwp", "enable_thermflex", "enable_h2", "enable_bess"]

    def resolve_feature_encoding(_settings):
        return {}

    def resolve_surrogate_targets(_settings):
        return ["npc_eur"]

    def heating_control_policy_identity(_settings):
        return {
            "reference_control_mode": "constant",
            "control_mode": "constant",
            "constant_setpoint_c": 22.0,
            "day_setpoint_c": 22.0,
            "night_setpoint_c": 19.0,
        }

    def thermflex_event_response_policy_identity(_settings):
        return {
            "use_event_response_bounds": False,
            "enforce_event_peak_bounds": True,
            "enforce_event_energy_bounds": True,
            "enforce_recovery_cooldown": True,
        }

    def engine_feature_policy_identity(settings):
        features = getattr(getattr(settings, "engine", None), "features", None)
        activation = getattr(settings, "technology_activation", None)
        return {
            "enable_bess": bool(getattr(features, "enable_bess", False)),
            "enable_v2h": bool(getattr(features, "enable_v2h", False)),
            "enable_h2": bool(getattr(features, "enable_h2", False)),
            "enable_thermflex": bool(getattr(features, "enable_thermflex", False)),
            "enable_small_wind": bool(getattr(features, "enable_small_wind", False)),
            "enable_large_wind": bool(getattr(features, "enable_large_wind", False)),
            "enable_biogas_engine": bool(getattr(features, "enable_biogas_engine", False)),
            "enable_wood_gasifier": bool(getattr(features, "enable_wood_gasifier", False)),
            "district_external_heat": bool(
                getattr(activation, "district_external_heat", False)
            ),
            "district_gas_boiler": bool(getattr(activation, "district_gas_boiler", False)),
            "district_heat_pump": bool(getattr(activation, "district_heat_pump", False)),
            "district_thermal_storage": bool(
                getattr(activation, "district_thermal_storage", False)
            ),
            "district_wood_chip_boiler": bool(
                getattr(activation, "district_wood_chip_boiler", False)
            ),
            "district_biomass_chp": bool(getattr(activation, "district_biomass_chp", False)),
            "district_biogas_chp": bool(getattr(activation, "district_biogas_chp", False)),
            "district_gas_chp": bool(getattr(activation, "district_gas_chp", False)),
            "district_geothermal": bool(getattr(activation, "district_geothermal", False)),
            "district_solar_thermal": bool(
                getattr(activation, "district_solar_thermal", False)
            ),
            "district_waste_incineration": bool(
                getattr(activation, "district_waste_incineration", False)
            ),
        }

    features_mod.resolve_feature_names = resolve_feature_names
    features_mod.resolve_feature_encoding = resolve_feature_encoding
    features_mod.resolve_surrogate_targets = resolve_surrogate_targets
    features_mod.heating_control_policy_identity = heating_control_policy_identity
    features_mod.thermflex_event_response_policy_identity = (
        thermflex_event_response_policy_identity
    )
    features_mod.engine_feature_policy_identity = engine_feature_policy_identity

    for name in (
        "Optimization",
        "Optimization.framework",
        "Optimization.framework.engines",
        "Optimization.framework.engines.Surrogat_model",
    ):
        if name not in sys.modules:
            mod = types.ModuleType(name)
            mod.__path__ = []  # type: ignore[attr-defined]
            _install_stub(name, mod)
    _install_stub(
        "Optimization.framework.engines.Surrogat_model.features",
        features_mod,
    )

    module_name = "Learning.families.build_family_engine_feature_identity_under_test"
    sys.modules.pop(module_name, None)
    spec = importlib.util.spec_from_file_location(
        module_name,
        REPO_ROOT / "Learning" / "families" / "build_family.py",
    )
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = mod
    spec.loader.exec_module(mod)
    return mod


def _settings(*, enable_thermflex: bool, enable_h2: bool = False) -> SimpleNamespace:
    return SimpleNamespace(
        engine=SimpleNamespace(
            system_id="integrated_energy_system",
            features=SimpleNamespace(
                enable_bess=False,
                enable_v2h=False,
                enable_h2=enable_h2,
                enable_thermflex=enable_thermflex,
                enable_small_wind=False,
                enable_large_wind=False,
                enable_biogas_engine=False,
                enable_wood_gasifier=False,
            ),
        ),
        technology_activation=SimpleNamespace(
            district_external_heat=False,
            district_gas_boiler=False,
            district_heat_pump=False,
            district_thermal_storage=False,
            district_wood_chip_boiler=False,
            district_biomass_chp=False,
            district_biogas_chp=False,
            district_gas_chp=False,
            district_geothermal=False,
            district_solar_thermal=False,
            district_waste_incineration=False,
        ),
        run=SimpleNamespace(tag="test"),
        surrogate=SimpleNamespace(model="rf"),
        surrogate_train=SimpleNamespace(model_params={}),
        market=SimpleNamespace(active_tariff_arm="flat"),
        learning=SimpleNamespace(
            resolution="1h",
            horizon_type="full_year",
            time_series_schema=[],
            location_mode="dataset_context",
            dispatch_model_id="default",
        ),
        bounds=SimpleNamespace(names=["pv_kwp"], steps=[1.0], caps={}),
    )


class TestEngineFeatureFamilyIdentity(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.mod = _load_build_family()

    def test_enable_thermflex_changes_family_hash(self):
        # Concrete SH trigger: bess0_v2h0_h2{0}_tf0 vs …_tf1 share design-bound
        # names and feature *names*, but ThermFlex on/off changes teacher KPIs.
        tf0 = self.mod.build_family(_settings(enable_thermflex=False))
        tf1 = self.mod.build_family(_settings(enable_thermflex=True))
        self.assertNotEqual(tf0.family_hash, tf1.family_hash)
        self.assertFalse(tf0.dispatch_signature["dispatch_params"]["enable_thermflex"])
        self.assertTrue(tf1.dispatch_signature["dispatch_params"]["enable_thermflex"])

    def test_enable_h2_changes_family_hash(self):
        # Same arm matrix also toggles H2; family identity must separate those
        # portfolios even when ThermFlex stays off.
        h2_off = self.mod.build_family(_settings(enable_thermflex=False, enable_h2=False))
        h2_on = self.mod.build_family(_settings(enable_thermflex=False, enable_h2=True))
        self.assertNotEqual(h2_off.family_hash, h2_on.family_hash)
        self.assertFalse(h2_off.dispatch_signature["dispatch_params"]["enable_h2"])
        self.assertTrue(h2_on.dispatch_signature["dispatch_params"]["enable_h2"])


if __name__ == "__main__":
    unittest.main()
