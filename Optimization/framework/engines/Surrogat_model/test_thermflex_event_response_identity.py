"""Signature/static features must encode ThermFlex event-response policy."""

from __future__ import annotations

import importlib.util
import sys
import types
import unittest
from pathlib import Path
from types import SimpleNamespace


REPO_ROOT = Path(__file__).resolve().parents[4]


def _load_features_module():
    """Import-light: stub kpi + Settings.surrogate.train to avoid heavy imports."""
    if "numpy" not in sys.modules:
        # numpy is required by features.py; fail clearly if absent.
        import numpy  # noqa: F401

    kpi_mod = types.ModuleType("Optimization.framework.engines.kpi")
    kpi_mod.get_selected_objective_names = lambda *_a, **_k: []
    sys.modules["Optimization.framework.engines.kpi"] = kpi_mod

    train_mod = types.ModuleType("Settings.surrogate.train")

    def make_surrogate_train():
        return SimpleNamespace(feature_names=[], feature_encoding={})

    train_mod.make_surrogate_train = make_surrogate_train
    # Ensure Settings.surrogate package stubs exist without importing Settings.
    for name in ("Settings", "Settings.surrogate"):
        if name not in sys.modules:
            pkg = types.ModuleType(name)
            pkg.__path__ = []  # type: ignore[attr-defined]
            sys.modules[name] = pkg
    sys.modules["Settings.surrogate.train"] = train_mod

    module_name = "surrogat_features_event_response_under_test"
    sys.modules.pop(module_name, None)
    spec = importlib.util.spec_from_file_location(
        module_name,
        REPO_ROOT
        / "Optimization"
        / "framework"
        / "engines"
        / "Surrogat_model"
        / "features.py",
    )
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = mod
    spec.loader.exec_module(mod)
    return mod


def _settings(*, use_event_response_bounds: bool) -> SimpleNamespace:
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
        heating_control=SimpleNamespace(
            reference_control_mode="constant",
            control_mode="constant",
            constant_setpoint_c=22.0,
            day_setpoint_c=22.0,
            night_setpoint_c=19.0,
        ),
        constraints=SimpleNamespace(
            thermflex=SimpleNamespace(
                day_lower_bound_c=None,
                night_lower_bound_c=None,
                max_flex_duration_h=4,
                max_flex_events_per_day=1,
                use_event_response_bounds=use_event_response_bounds,
                enforce_event_peak_bounds=True,
                enforce_event_energy_bounds=True,
                enforce_recovery_cooldown=True,
            )
        ),
        market=SimpleNamespace(active_tariff_arm="flat"),
        dispatch=SimpleNamespace(mode="milp_day_ahead", stochastic_enabled=False),
        district_heating=SimpleNamespace(share=0.35),
        surrogate_train=SimpleNamespace(feature_names=[], feature_encoding={}),
    )


class TestThermflexEventResponseIdentity(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.features = _load_features_module()

    def test_event_response_changes_static_vector_and_signature(self):
        off = _settings(use_event_response_bounds=False)
        on = _settings(use_event_response_bounds=True)
        vec_off = self.features.build_static_feature_vector(off, "profile")
        vec_on = self.features.build_static_feature_vector(on, "profile")
        self.assertNotEqual(list(vec_off), list(vec_on))
        payload_off = self.features.build_signature_context_payload(off, "profile")
        payload_on = self.features.build_signature_context_payload(on, "profile")
        self.assertFalse(payload_off["use_event_response_bounds"])
        self.assertTrue(payload_on["use_event_response_bounds"])

    def test_feature_names_include_event_response_fields(self):
        names = self.features.resolve_feature_names(
            _settings(use_event_response_bounds=False)
        )
        self.assertIn("thermflex_use_event_response_bounds", names)
        self.assertIn("thermflex_enforce_event_peak_bounds", names)
        self.assertIn("thermflex_enforce_event_energy_bounds", names)
        self.assertIn("thermflex_enforce_recovery_cooldown", names)


if __name__ == "__main__":
    unittest.main()
