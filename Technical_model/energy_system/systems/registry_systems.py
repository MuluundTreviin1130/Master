from __future__ import annotations

"""Active system registry.

Only active system ids are exposed here. Deprecated systems are moved to legacy/.
"""

from typing import Any, Dict

import numpy as np
import pandas as pd

from Technical_model.energy_system.runners.system_model_precomputed import _hourly_table
from Technical_model.energy_system.systems.EC_FLEX import simulate_energy_system_ec_flex
from Technical_model.energy_system.systems.integrated_energy_system import simulate_integrated_energy_system

SYSTEM_SPECS: Dict[str, Dict[str, Any]] = {
    "ec_flex": {
        "runner": simulate_energy_system_ec_flex,
        "expected": [
            "pv_generation",
            "small_wind_generation",
            "large_wind_generation",
            "run_of_river_hydro_generation",
            "biogas_generation",
            "wood_gasifier_generation",
            "wood_gasifier_fuel_input_kwh",
            "wood_gasifier_fuel_input_kg",
            "total_load",
            "grid_import",
            "grid_export",
            "bess_charged",
            "bess_discharged",
            "ev_charge_ac",
            "ev_charge_from_pv_ac",
            "ev_charge_from_bess_ac",
            "ev_charge_from_ec_ac",
            "ev_charge_from_grid_ac",
            "ev_discharged_total",
            "ec_import_from_pv",
            "ec_import_from_ev",
            "ec_export_from_pv",
            "h2_charge_elec",
            "h2_discharge_elec",
            "h2_soc",
            "hp_base_elec",
            "hp_flex_elec",
        ],
        "generation": [
            "pv_generation",
            "small_wind_generation",
            "large_wind_generation",
            "run_of_river_hydro_generation",
            "biogas_generation",
            "wood_gasifier_generation",
            "bess_discharged",
            "ev_discharged_total",
            "h2_discharge_elec",
        ],
        "consumption": ["total_load", "bess_charged", "h2_charge_elec"],
    },
    "integrated_energy_system": {
        "runner": simulate_integrated_energy_system,
        "expected": [
            "pv_generation",
            "small_wind_generation",
            "large_wind_generation",
            "run_of_river_hydro_generation",
            "biogas_generation",
            "wood_gasifier_generation",
            "wood_gasifier_fuel_input_kwh",
            "wood_gasifier_fuel_input_kg",
            "total_load",
            "grid_import",
            "grid_export",
            "bess_charged",
            "bess_discharged",
            "ev_charge_ac",
            "ev_charge_from_pv_ac",
            "ev_charge_from_bess_ac",
            "ev_charge_from_ec_ac",
            "ev_charge_from_grid_ac",
            "ev_discharged_total",
            "ec_import_from_pv",
            "ec_import_from_ev",
            "ec_export_from_pv",
            "h2_charge_elec",
            "h2_discharge_elec",
            "h2_soc",
            "hp_base_elec",
            "hp_flex_elec",
            "district_geothermal_electric_generation",
            "district_geothermal_thermal_generation",
            "district_geothermal_thermal_spillage",
            "district_solar_thermal_generation",
            "district_solar_thermal_direct_feed",
            "district_solar_thermal_preheat",
            "district_solar_thermal_storage_charge",
            "district_solar_thermal_thermal_spillage",
            "district_waste_incineration_generation",
            "district_waste_incineration_thermal_spillage",
            "district_biomass_chp_electric_generation",
            "district_biomass_chp_thermal_generation",
            "district_biomass_chp_thermal_spillage",
            "district_biomass_chp_fuel_input_kwh",
            "district_biomass_chp_fuel_input_kg",
            "district_biogas_chp_electric_generation",
            "district_biogas_chp_thermal_generation",
            "district_biogas_chp_thermal_spillage",
            "district_biogas_chp_fuel_input_kwh",
            "district_biogas_chp_fuel_input_nm3",
            "district_gas_chp_electric_generation",
            "district_gas_chp_thermal_generation",
            "district_gas_chp_thermal_spillage",
            "district_gas_chp_fuel_input_kwh",
            "district_gas_chp_fuel_input_m3",
            "district_heat_pump_generation",
            "district_heat_pump_electricity",
            "district_wood_chip_boiler_generation",
            "district_wood_chip_boiler_fuel_input_kwh",
            "district_wood_chip_boiler_fuel_input_kg",
            "district_thermal_storage_charge",
            "district_thermal_storage_discharge",
            "district_thermal_storage_losses",
            "district_thermal_storage_soc",
            "dh_total_demand",
            "dh_total_delivered",
            "dh_unserved_heat",
        ],
        "generation": [
            "pv_generation",
            "small_wind_generation",
            "large_wind_generation",
            "run_of_river_hydro_generation",
            "biogas_generation",
            "wood_gasifier_generation",
            "bess_discharged",
            "ev_discharged_total",
            "h2_discharge_elec",
            "district_geothermal_electric_generation",
            "district_solar_thermal_generation",
            "district_waste_incineration_generation",
            "district_biomass_chp_electric_generation",
            "district_biogas_chp_electric_generation",
            "district_gas_chp_electric_generation",
            "district_heat_pump_generation",
            "district_wood_chip_boiler_generation",
            "district_thermal_storage_discharge",
        ],
        "consumption": [
            "total_load",
            "bess_charged",
            "h2_charge_elec",
            "district_heat_pump_electricity",
            "district_thermal_storage_charge",
        ],
    },
}


def _to_series_dict(res: dict, idx: pd.DatetimeIndex) -> dict:
    out = {}
    for k, v in res.items():
        if isinstance(v, pd.Series):
            out[k] = v.reindex(idx)
        elif isinstance(v, (list, tuple, np.ndarray)):
            arr = np.asarray(v)
            if arr.ndim == 1 and arr.size == idx.size:
                out[k] = pd.Series(arr, index=idx, dtype="float64")
            else:
                out[k] = arr
        else:
            out[k] = v
    return out


def _make_index(res: dict, profiles: dict) -> pd.DatetimeIndex:
    ts = res.get("timestamps", profiles.get("timestamps", None))
    if ts is None:
        n = np.asarray(res.get("pv_generation", profiles.get("load"))).size
        return pd.date_range("2023-01-01", periods=int(n), freq="h")
    return pd.to_datetime(ts)


def get(system_id: str):
    sid = (system_id or "").lower()
    if sid not in SYSTEM_SPECS:
        raise ValueError(f"Unknown active system_id: {system_id}. Available: {list(SYSTEM_SPECS)}")
    spec = SYSTEM_SPECS[sid]
    runner = spec["runner"]

    def _fn(params, profiles, pv_size, run_checks: bool = False):
        res = runner(params, profiles, pv_size)
        idx = _make_index(res, profiles)
        res = _to_series_dict(res, idx)
        expected = list(spec["expected"])
        df = _hourly_table(
            res,
            profiles,
            params,
            expected_keys=expected,
            generation_keys=[k for k in spec["generation"] if k in res],
            consumption_keys=[k for k in spec["consumption"] if (k == "load" or k in res)],
            grid_import_key="grid_import",
            grid_export_key="grid_export",
        )
        return res, df

    return _fn
