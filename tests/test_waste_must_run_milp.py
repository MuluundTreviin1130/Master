"""Regression tests for district waste incineration must-run on MILP paths."""

from __future__ import annotations

import unittest

import numpy as np

from dispatch.core import DispatchInput
from dispatch.modes.milp_day_ahead import run_milp_day_ahead_dispatch


def _minimal_waste_day_ahead_input(
    *,
    must_run: bool,
    waste_available_kwh: float,
    dh_demand_kwh: float,
    include_must_run_param: bool = True,
) -> DispatchInput:
    """Build a one-hour DispatchInput that isolates waste must-run semantics."""
    n = 1
    params = {
        # Cheap grid import so the electric balance stays feasible without storage.
        "dispatch_spill_penalty_eur_per_kwh": 1e-3,
        "dispatch_unserved_penalty_eur_per_kwh": 1e6,
        "dispatch_enable_co2_cost_model": False,
        "district_external_heat_variable_cost_eur_per_kwh_th": 0.0,
        "district_external_heat_min_partload": 0.0,
        "district_gas_boiler_fuel_cost_eur_per_m3": 0.5,
        "district_gas_boiler_fuel_lhv_kwh_per_m3": 10.0,
        "district_gas_chp_fuel_cost_eur_per_m3": 0.5,
        "district_gas_chp_fuel_lhv_kwh_per_m3": 10.0,
        "district_waste_incineration_min_partload": 0.0,
    }
    if include_must_run_param:
        params["district_waste_incineration_must_run"] = must_run
    return DispatchInput(
        series={
            "electric_non_dispatch_demand": np.zeros(n, dtype=float),
            "district_heat_demand": np.full(n, dh_demand_kwh, dtype=float),
            "district_space_heat_demand": np.full(n, dh_demand_kwh, dtype=float),
            "district_hotwater_demand": np.zeros(n, dtype=float),
            "grid_import_price": np.full(n, 0.05, dtype=float),
            "grid_export_price": np.full(n, 0.01, dtype=float),
            "district_gas_day_ahead_price_eur_per_mwh_fuel": np.full(n, 40.0, dtype=float),
            "district_waste_incineration_available_th": np.full(n, waste_available_kwh, dtype=float),
        },
        assets={},
        params=params,
        initial_state={},
    )


class WasteMustRunMilpTests(unittest.TestCase):
    def test_missing_must_run_param_fails_with_positive_availability(self) -> None:
        dispatch_input = _minimal_waste_day_ahead_input(
            must_run=True,
            waste_available_kwh=100.0,
            dh_demand_kwh=10.0,
            include_must_run_param=False,
        )
        with self.assertRaisesRegex(ValueError, "district_waste_incineration_must_run"):
            run_milp_day_ahead_dispatch(dispatch_input)

    def test_must_run_forces_full_available_output(self) -> None:
        # Concrete trigger: low DH demand, high must-run waste availability.
        # Before the fix, MILP could set waste_on=0 and drop generation entirely.
        waste_available = 160.0
        dispatch_input = _minimal_waste_day_ahead_input(
            must_run=True,
            waste_available_kwh=waste_available,
            dh_demand_kwh=10.0,
        )
        result = run_milp_day_ahead_dispatch(dispatch_input)
        generation = float(np.asarray(result.hourly["district_waste_incineration_generation"])[0])
        spillage = float(np.asarray(result.hourly["district_waste_incineration_thermal_spillage"])[0])
        self.assertAlmostEqual(generation + spillage, waste_available, places=6)
        self.assertGreater(generation, 0.0)
        self.assertGreater(spillage, 0.0)

    def test_optional_waste_can_stay_off_when_must_run_false(self) -> None:
        # With must_run disabled and zero DH demand, optional waste should remain off
        # because spill carries a positive penalty.
        waste_available = 160.0
        dispatch_input = _minimal_waste_day_ahead_input(
            must_run=False,
            waste_available_kwh=waste_available,
            dh_demand_kwh=0.0,
        )
        result = run_milp_day_ahead_dispatch(dispatch_input)
        generation = float(np.asarray(result.hourly["district_waste_incineration_generation"])[0])
        spillage = float(np.asarray(result.hourly["district_waste_incineration_thermal_spillage"])[0])
        self.assertAlmostEqual(generation + spillage, 0.0, places=6)


if __name__ == "__main__":
    unittest.main()
