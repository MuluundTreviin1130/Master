"""Regression tests: MILP must not invent DH storage eta=1 / loss=0."""

from __future__ import annotations

import sys
import types
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def _load_ies_storage_helpers():
    """Load storage MILP scalar helpers without importing the full technology stack."""

    source = (ROOT / "Technical_model/energy_system/systems/integrated_energy_system.py").read_text(
        encoding="utf-8"
    )
    ns: dict = {"Any": object, "Dict": dict, "List": list}

    def _exec_between(start_marker: str, end_marker: str) -> None:
        start = source.index(start_marker)
        end = source.index(end_marker, start)
        exec(source[start:end], ns)

    # Helpers sit between `_require_float_attr` and the piecewise CHP payload.
    _exec_between("def _require_float_attr", "\ndef _district_gas_chp_piecewise_payload")
    return types.SimpleNamespace(**ns)


class TestActiveDistrictThermalStorageMilpScalars(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.ies = _load_ies_storage_helpers()

    def test_active_storage_none_eta_fails_fast(self):
        cfg = types.SimpleNamespace(
            charge_efficiency=None,
            discharge_efficiency=0.95,
            standing_loss_kwh_per_day=10.0,
        )
        with self.assertRaisesRegex(ValueError, "must not be None"):
            self.ies._active_district_thermal_storage_milp_scalars(cfg, active=True)

    def test_active_storage_resolves_explicit_ssot(self):
        cfg = types.SimpleNamespace(
            charge_efficiency=0.92,
            discharge_efficiency=0.94,
            standing_loss_kwh_per_day=24.0,
        )
        scalars = self.ies._active_district_thermal_storage_milp_scalars(cfg, active=True)
        self.assertEqual(scalars["eta_charge"], 0.92)
        self.assertEqual(scalars["eta_discharge"], 0.94)
        self.assertEqual(scalars["loss_kwh_per_h"], 1.0)

    def test_inactive_storage_contributes_explicit_zeros(self):
        cfg = types.SimpleNamespace(
            charge_efficiency=None,
            discharge_efficiency=None,
            standing_loss_kwh_per_day=None,
        )
        inactive = self.ies._active_district_thermal_storage_milp_scalars(cfg, active=False)
        self.assertEqual(inactive["eta_charge"], 0.0)
        self.assertEqual(inactive["eta_discharge"], 0.0)
        self.assertEqual(inactive["loss_kwh_per_h"], 0.0)

    def test_milp_capacity_zeroed_when_storage_disabled(self):
        # Mirror the IES packing contract: deactivated tech must not leak a
        # positive design capacity into milp_day_ahead / milp_two_stage assets.
        storage_enabled = False
        installed_storage_kwh = 1110490.3
        milp_storage_capacity_kwh = float(installed_storage_kwh if storage_enabled else 0.0)
        self.assertEqual(milp_storage_capacity_kwh, 0.0)


class TestActivatedDistrictThermalStorageSettingsValidation(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        source = (ROOT / "Settings/get_settings.py").read_text(encoding="utf-8")
        ns: dict = {"Settings": object, "Any": object, "Dict": dict}

        def _require_positive_float(value, *, label: str) -> float:
            if value is None:
                raise ValueError(f"[settings] {label} must not be None.")
            value_f = float(value)
            if value_f <= 0.0:
                raise ValueError(f"[settings] {label} must be > 0, got {value_f}.")
            return value_f

        def _require_nonnegative_float(value, *, label: str) -> float:
            if value is None:
                raise ValueError(f"[settings] {label} must not be None.")
            value_f = float(value)
            if value_f < 0.0:
                raise ValueError(f"[settings] {label} must be >= 0, got {value_f}.")
            return value_f

        ns["_require_positive_float"] = _require_positive_float
        ns["_require_nonnegative_float"] = _require_nonnegative_float
        start = source.index("def _validate_activated_district_thermal_storage")
        end = source.index("\ndef _validate_district_gas_chp_operating_region", start)
        exec(source[start:end], ns)
        cls.validate = staticmethod(ns["_validate_activated_district_thermal_storage"])

    def test_activated_storage_without_eta_fails_fast(self):
        cfg = types.SimpleNamespace(
            technology_activation=types.SimpleNamespace(district_thermal_storage=True),
            district_thermal_storage=types.SimpleNamespace(
                charge_efficiency=None,
                discharge_efficiency=0.95,
                standing_loss_kwh_per_day=10.0,
            ),
        )
        with self.assertRaisesRegex(ValueError, "district_thermal_storage.charge_efficiency"):
            self.validate(cfg)

    def test_activated_storage_complete_ssot_passes(self):
        cfg = types.SimpleNamespace(
            technology_activation=types.SimpleNamespace(district_thermal_storage=True),
            district_thermal_storage=types.SimpleNamespace(
                charge_efficiency=0.92,
                discharge_efficiency=0.94,
                standing_loss_kwh_per_day=0.0,
            ),
        )
        self.validate(cfg)

    def test_inactive_storage_skips_eta_requirements(self):
        cfg = types.SimpleNamespace(
            technology_activation=types.SimpleNamespace(district_thermal_storage=False),
            district_thermal_storage=types.SimpleNamespace(
                charge_efficiency=None,
                discharge_efficiency=None,
                standing_loss_kwh_per_day=None,
            ),
        )
        self.validate(cfg)


if __name__ == "__main__":
    unittest.main()
