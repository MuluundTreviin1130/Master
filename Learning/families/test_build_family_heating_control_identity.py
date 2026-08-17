"""Family hash must separate heating-control setpoint / control_mode policies."""

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
        return ["pv_kwp", "constant_setpoint_c", "control_mode"]

    def resolve_feature_encoding(_settings):
        return {}

    def resolve_surrogate_targets(_settings):
        return ["npc_eur"]

    def heating_control_policy_identity(settings):
        heating_control = getattr(settings, "heating_control", None)
        return {
            "reference_control_mode": str(
                getattr(heating_control, "reference_control_mode", "constant")
            ),
            "control_mode": str(getattr(heating_control, "control_mode", "constant")),
            "constant_setpoint_c": float(
                getattr(heating_control, "constant_setpoint_c", 0.0) or 0.0
            ),
            "day_setpoint_c": float(getattr(heating_control, "day_setpoint_c", 0.0) or 0.0),
            "night_setpoint_c": float(
                getattr(heating_control, "night_setpoint_c", 0.0) or 0.0
            ),
        }

    def thermflex_event_response_policy_identity(_settings):
        # Heating-control tests keep event-response fixed so hash diffs isolate
        # setpoint / control_mode identity only.
        return {
            "use_event_response_bounds": False,
            "enforce_event_peak_bounds": True,
            "enforce_event_energy_bounds": True,
            "enforce_recovery_cooldown": True,
        }

    def engine_feature_policy_identity(_settings):
        # Fixed baseline so heating-control tests isolate only that policy axis.
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

    module_name = "Learning.families.build_family_heating_control_identity_under_test"
    sys.modules.pop(module_name, None)
    spec = importlib.util.spec_from_file_location(
        module_name,
        REPO_ROOT / "Learning" / "families" / "build_family.py",
    )
    if spec is None or spec.loader is None:
        raise RuntimeError("Unable to load build_family.py for heating-control identity test.")
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


def _settings(
    *,
    constant_setpoint_c: float = 22.0,
    control_mode: str = "constant",
    day_setpoint_c: float = 22.0,
    night_setpoint_c: float = 19.0,
) -> SimpleNamespace:
    return SimpleNamespace(
        engine=SimpleNamespace(system_id="integrated_energy_system"),
        run=SimpleNamespace(tag="test"),
        surrogate=SimpleNamespace(model="rf"),
        surrogate_train=SimpleNamespace(model_params={}),
        bounds=SimpleNamespace(names=["pv_kwp"], steps=[1.0], caps={}),
        market=SimpleNamespace(active_tariff_arm="flat"),
        learning=SimpleNamespace(
            resolution="1h",
            horizon_type="full_year",
            time_series_schema=[],
            location_mode="dataset_context",
            dispatch_model_id="default",
        ),
        heating_control=SimpleNamespace(
            reference_control_mode="constant",
            control_mode=control_mode,
            constant_setpoint_c=constant_setpoint_c,
            day_setpoint_c=day_setpoint_c,
            night_setpoint_c=night_setpoint_c,
        ),
    )


class BuildFamilyHeatingControlIdentityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.mod = _load_build_family()

    def test_constant_setpoint_changes_family_hash(self):
        # Concrete trigger: Settings default 22.0 C vs ThermFlex-paper 22.5 C
        # with otherwise identical schemas must not share a family_hash, otherwise
        # auto_train reuses cached Y / resolve_model loads the wrong artifact.
        sp22 = self.mod.build_family(_settings(constant_setpoint_c=22.0))
        sp225 = self.mod.build_family(_settings(constant_setpoint_c=22.5))
        self.assertNotEqual(sp22.family_hash, sp225.family_hash)
        self.assertEqual(
            sp22.dispatch_signature["dispatch_params"]["constant_setpoint_c"],
            22.0,
        )
        self.assertEqual(
            sp225.dispatch_signature["dispatch_params"]["constant_setpoint_c"],
            22.5,
        )

    def test_control_mode_changes_family_hash(self):
        constant = self.mod.build_family(_settings(control_mode="constant"))
        day_night = self.mod.build_family(_settings(control_mode="day_night"))
        self.assertNotEqual(constant.family_hash, day_night.family_hash)
        self.assertEqual(
            constant.dispatch_signature["dispatch_params"]["control_mode"],
            "constant",
        )
        self.assertEqual(
            day_night.dispatch_signature["dispatch_params"]["control_mode"],
            "day_night",
        )


if __name__ == "__main__":
    unittest.main()
