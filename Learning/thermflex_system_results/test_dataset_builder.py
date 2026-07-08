from __future__ import annotations

import json
import sys
import tempfile
import types
import unittest
from pathlib import Path

import pandas as pd


def _unused_context_loader_stub(*args: object, **kwargs: object) -> object:
    raise AssertionError("system-results row-count tests must not load canonical context")


def _unused_daily_feature_stub(*args: object, **kwargs: object) -> pd.DataFrame:
    raise AssertionError("system-results row-count tests must not build daily features")


_context_module = types.ModuleType("Optimization.run.analysis.dh_thermflex_inputs")
_context_module.load_vienna_dh_thermflex_full_year_context = _unused_context_loader_stub
sys.modules["Optimization.run.analysis.dh_thermflex_inputs"] = _context_module

_daily_module = types.ModuleType("Optimization.run.analysis.select_vienna_dh_thermflex_representative_days")
_daily_module._build_daily_features = _unused_daily_feature_stub
sys.modules["Optimization.run.analysis.select_vienna_dh_thermflex_representative_days"] = _daily_module

from Learning.thermflex_system_results.dataset_builder import load_system_results_truth_table
from Learning.thermflex_system_results.schema import DISPATCH_KPI_TARGET_COLUMNS, REQUIRED_COMMON_COLUMNS


def _system_truth_row(*, signature_hash: str, pv_kwp: float) -> dict[str, object]:
    row: dict[str, object] = {
        "run_id": signature_hash,
        "signature_hash": signature_hash,
        "source": "unit-test",
        "pv_kwp": pv_kwp,
        "bess_kwh": 0.0,
        "ely_kw": 0.0,
        "h2_tank_kwh": 0.0,
        "fc_kw": 0.0,
        "small_wind_kw": 0.0,
        "large_wind_kw": 0.0,
        "district_heat_pump_kw_th": 100.0,
        "district_thermal_storage_kwh_th": 200.0,
        "district_wood_chip_boiler_kw_th": 0.0,
        "district_biomass_chp_kw_th": 0.0,
        "district_geothermal_kw_el": 0.0,
        "district_gas_chp_kw_el": 10.0,
        "district_biogas_chp_kw_el": 0.0,
        "biogas_engine_kw": 0.0,
        "wood_gasifier_kw": 0.0,
        "E_import_grid_kWh": 1.0,
        "E_export_grid_kWh": 0.0,
        "E_total_load_kWh": 1.0,
        "E_district_heat_pump_thermal_generation_kWh": 2.0,
        "E_district_heat_pump_electricity_kWh": 1.0,
        "E_district_thermal_storage_charge_kWh": 0.0,
        "E_district_thermal_storage_discharge_kWh": 0.0,
        "E_district_thermal_storage_losses_kWh": 0.0,
        "E_district_external_heat_generation_kWh": 0.0,
        "E_district_biomass_chp_electric_generation_kWh": 0.0,
        "E_district_biomass_chp_thermal_generation_kWh": 0.0,
        "E_district_biomass_chp_fuel_input_kWh": 0.0,
        "E_district_gas_chp_electric_generation_kWh": 0.0,
        "E_district_gas_chp_thermal_generation_kWh": 2.0,
        "E_district_gas_chp_fuel_input_kWh": 3.0,
        "E_district_gas_boiler_generation_kWh": 0.0,
        "E_district_gas_boiler_fuel_input_kWh": 0.0,
        "bess_cyclic_violation_kwh": 0.0,
        "h2_cyclic_violation_kwh": 0.0,
        "M_district_biomass_chp_fuel_input_kg": 0.0,
        "V_district_gas_chp_fuel_input_m3": 0.0,
        "V_district_gas_boiler_fuel_input_m3": 0.0,
        "dispatch_cost_eur": 10.0,
    }
    missing = set(REQUIRED_COMMON_COLUMNS).difference(row)
    if missing:
        raise AssertionError(f"test fixture missing required columns: {sorted(missing)}")
    return row


def _write_dispatch_kpis(run_dir: Path) -> None:
    latest_point = {column: 1.0 for column in DISPATCH_KPI_TARGET_COLUMNS}
    (run_dir / "dispatch_kpis.json").write_text(
        json.dumps({"latest_point": latest_point}),
        encoding="utf-8",
    )


class SystemResultsLatestPointTest(unittest.TestCase):
    def test_latest_point_rejects_multirow_truth_dataset(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            run_dir = Path(tmp) / "20260708_110000_vienna_ref2023_dh_baseline_constant_lb21p5_dur4_evt24_paper_day_ahead"
            run_dir.mkdir()
            truth_csv = run_dir / "truth_dataset.csv"
            pd.DataFrame(
                [
                    _system_truth_row(signature_hash="row-a", pv_kwp=1.0),
                    _system_truth_row(signature_hash="row-b", pv_kwp=2.0),
                ]
            ).to_csv(truth_csv, index=False)
            _write_dispatch_kpis(run_dir)

            with self.assertRaisesRegex(ValueError, "latest_point.*single-row"):
                load_system_results_truth_table(
                    truth_csv_paths=[truth_csv],
                    dispatch_kpi_mode="latest_point",
                )


if __name__ == "__main__":
    unittest.main()
