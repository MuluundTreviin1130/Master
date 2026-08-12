"""Family hash must separate ThermFlex event-response policy cuts."""

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
        return [
            "pv_kwp",
            "thermflex_use_event_response_bounds",
            "thermflex_enforce_event_peak_bounds",
            "thermflex_enforce_event_energy_bounds",
            "thermflex_enforce_recovery_cooldown",
        ]

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

    def thermflex_event_response_policy_identity(settings):
        thermflex_cfg = getattr(getattr(settings, "constraints", None), "thermflex", None)
        return {
            "use_event_response_bounds": bool(
                getattr(thermflex_cfg, "use_event_response_bounds", False)
            ),
            "enforce_event_peak_bounds": bool(
                getattr(thermflex_cfg, "enforce_event_peak_bounds", True)
            ),
            "enforce_event_energy_bounds": bool(
                getattr(thermflex_cfg, "enforce_event_energy_bounds", True)
            ),
            "enforce_recovery_cooldown": bool(
                getattr(thermflex_cfg, "enforce_recovery_cooldown", True)
            ),
        }

    def engine_feature_policy_identity(_settings):
        # Fixed baseline so event-response tests isolate only that policy axis.
        return {
            "enable_bess": False,
            "enable_v2h": False,
            "enable_h2": False,
            "enable_thermflex": False,
            "enable_small_wind": False,
            "enable_large_wind": False,
            "enable_biogas_engine": False,
            "enable_wood_gasifier": False,
            "district_external_heat": False,
            "district_gas_boiler": False,
            "district_heat_pump": False,
            "district_thermal_storage": False,
            "district_wood_chip_boiler": False,
            "district_biomass_chp": False,
            "district_biogas_chp": False,
            "district_gas_chp": False,
            "district_geothermal": False,
            "district_solar_thermal": False,
            "district_waste_incineration": False,
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

    module_name = "Learning.families.build_family_event_response_identity_under_test"
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


def _settings(*, use_event_response_bounds: bool) -> SimpleNamespace:
    return SimpleNamespace(
        engine=SimpleNamespace(system_id="integrated_energy_system"),
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
        heating_control=SimpleNamespace(
            reference_control_mode="constant",
            control_mode="constant",
            constant_setpoint_c=22.0,
            day_setpoint_c=22.0,
            night_setpoint_c=19.0,
        ),
        constraints=SimpleNamespace(
            thermflex=SimpleNamespace(
                use_event_response_bounds=use_event_response_bounds,
                enforce_event_peak_bounds=True,
                enforce_event_energy_bounds=True,
                enforce_recovery_cooldown=True,
            )
        ),
    )


class TestEventResponseFamilyIdentity(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.mod = _load_build_family()

    def test_event_response_flag_changes_family_hash(self):
        # Settings default keeps event-response off; Vienna ThermFlex paper cuts
        # turn it on. Those policies must not share a family_hash, otherwise
        # auto_train reuses incompatible teacher labels / artifacts.
        default_off = self.mod.build_family(_settings(use_event_response_bounds=False))
        paper_on = self.mod.build_family(_settings(use_event_response_bounds=True))
        self.assertNotEqual(default_off.family_hash, paper_on.family_hash)
        self.assertFalse(
            default_off.dispatch_signature["dispatch_params"]["use_event_response_bounds"]
        )
        self.assertTrue(
            paper_on.dispatch_signature["dispatch_params"]["use_event_response_bounds"]
        )


if __name__ == "__main__":
    unittest.main()
