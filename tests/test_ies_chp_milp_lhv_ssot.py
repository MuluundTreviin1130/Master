"""Regression tests: MILP must not invent CHP fuel LHV=1.0."""

from __future__ import annotations

import sys
import types
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def _load_ies_chp_helpers():
    """Load CHP MILP scalar helpers without importing the full technology stack."""

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


class TestActiveChpMilpScalars(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.ies = _load_ies_chp_helpers()

    def test_active_gas_chp_none_lhv_fails_fast(self):
        cfg = types.SimpleNamespace(
            eta_el=0.55,
            eta_th=0.30,
            min_partload=0.4,
            fuel_lhv_kwh_per_m3=None,
        )
        with self.assertRaisesRegex(ValueError, "must not be None"):
            self.ies._active_chp_milp_scalars(
                cfg,
                active=True,
                tech_name="district_gas_chp",
                lhv_settings_attr="fuel_lhv_kwh_per_m3",
            )

    def test_active_biomass_chp_resolves_explicit_lhv(self):
        cfg = types.SimpleNamespace(
            eta_el=0.25,
            eta_th=0.55,
            min_partload=0.3,
            fuel_lhv_kwh_per_kg=4.2,
        )
        scalars = self.ies._active_chp_milp_scalars(
            cfg,
            active=True,
            tech_name="district_biomass_chp",
            lhv_settings_attr="fuel_lhv_kwh_per_kg",
        )
        self.assertEqual(scalars["fuel_lhv"], 4.2)
        self.assertEqual(scalars["eta_el"], 0.25)
        self.assertEqual(scalars["eta_th"], 0.55)
        self.assertEqual(scalars["min_partload"], 0.3)

    def test_inactive_chp_contributes_explicit_zeros(self):
        cfg = types.SimpleNamespace(
            eta_el=None,
            eta_th=None,
            min_partload=None,
            fuel_lhv_kwh_per_nm3=None,
        )
        inactive = self.ies._active_chp_milp_scalars(
            cfg,
            active=False,
            tech_name="district_biogas_chp",
            lhv_settings_attr="fuel_lhv_kwh_per_nm3",
        )
        self.assertEqual(inactive["eta_el"], 0.0)
        self.assertEqual(inactive["eta_th"], 0.0)
        self.assertEqual(inactive["min_partload"], 0.0)
        self.assertEqual(inactive["fuel_lhv"], 0.0)


class TestActivatedChpSettingsValidation(unittest.TestCase):
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

        ns["_require_positive_float"] = _require_positive_float
        start = source.index("def _validate_activated_district_chps")
        end = source.index("\ndef _validate_dispatch_objective_components", start)
        exec(source[start:end], ns)
        cls.validate = staticmethod(ns["_validate_activated_district_chps"])

    def test_activated_gas_chp_without_lhv_fails_fast(self):
        cfg = types.SimpleNamespace(
            technology_activation=types.SimpleNamespace(
                district_biomass_chp=False,
                district_biogas_chp=False,
                district_gas_chp=True,
            ),
            district_biomass_chp=None,
            district_biogas_chp=None,
            district_gas_chp=types.SimpleNamespace(
                eta_el=0.55,
                eta_th=0.30,
                min_partload=0.4,
                fuel_lhv_kwh_per_m3=None,
            ),
        )
        with self.assertRaisesRegex(ValueError, "district_gas_chp.fuel_lhv_kwh_per_m3"):
            self.validate(cfg)

    def test_activated_biomass_chp_complete_ssot_passes(self):
        cfg = types.SimpleNamespace(
            technology_activation=types.SimpleNamespace(
                district_biomass_chp=True,
                district_biogas_chp=False,
                district_gas_chp=False,
            ),
            district_biomass_chp=types.SimpleNamespace(
                eta_el=0.25,
                eta_th=0.55,
                min_partload=0.3,
                fuel_lhv_kwh_per_kg=4.2,
            ),
            district_biogas_chp=None,
            district_gas_chp=None,
        )
        self.validate(cfg)


if __name__ == "__main__":
    unittest.main()
