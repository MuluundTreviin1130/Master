from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Tuple

import numpy as np
import pandas as pd

from dispatch import DispatchInput, get_dispatch_runner
from dispatch.scenarios import build_ies_historical_scenarios
from dispatch.metrics import compute_series_peak_change_kw, compute_series_peak_kw, compute_thermflex_series_metrics
from market import build_market_bundle
from Technical_model.consumption.heating_anc_cooling_consumption.thermflex_linear_model import (
    build_member_thermflex_linear_inputs,
)
from Technical_model.consumption.heating_anc_cooling_consumption.heating_control import is_night_hour
from Technical_model.technologies.buildings.thermal_building_state import (
    ThermalBuildingState,
    smooth_effective_outdoor_temperature,
)
from Technical_model.technologies.buildings.runtime_building_params import get_runtime_building_params
from Technical_model.technologies.buildings.thermal_flex_controller import thermflex_extra_cap_kwh
from Technical_model.technologies.district_heating.core.dh_buildings import build_dh_buildings
from Technical_model.technologies.district_heating.core.dh_bus import build_dh_bus
from Technical_model.technologies.district_heating.core.dh_demand import build_dh_demand
from Technical_model.technologies.district_heating.core.temperature_curve import (
    get_dh_bus_temperatures,
    get_required_preheat_source_temp_c,
    get_required_source_supply_temp_c,
)
from Technical_model.technologies.district_heating.sources.district_biomass_chp import dispatch_district_biomass_chp
from Technical_model.technologies.district_heating.sources.district_biogas_chp import dispatch_district_biogas_chp
from Technical_model.technologies.district_heating.sources.district_external_heat import dispatch_district_external_heat
from Technical_model.technologies.district_heating.sources.district_gas_boiler import dispatch_district_gas_boiler
from Technical_model.technologies.district_heating.sources.district_gas_chp import dispatch_district_gas_chp
from Technical_model.technologies.district_heating.sources.district_geothermal import dispatch_district_geothermal_orc
from Technical_model.technologies.district_heating.sources.district_heat_pump import (
    calculate_constant_dh_heat_pump_cop,
    dispatch_district_heat_pump,
)
from Technical_model.technologies.district_heating.sources.district_solar_thermal import (
    precompute_district_solar_thermal_series,
)
from Technical_model.technologies.district_heating.sources.district_waste_incineration import (
    dispatch_district_waste_incineration,
)
from Technical_model.technologies.district_heating.sources.district_wood_chip_boiler import (
    dispatch_district_wood_chip_boiler,
)
from Technical_model.technologies.district_heating.storage.district_thermal_storage import (
    initialize_district_thermal_storage_soc,
    step_district_thermal_storage,
)
from Technical_model.technologies.electricity.large_wind import simulate_large_wind_generation
from Technical_model.technologies.electricity.run_of_river_hydro import simulate_run_of_river_hydro_generation
from Technical_model.technologies.electricity.small_wind import simulate_small_wind_generation
from Data.technology_data.run_of_river_hydro.Vienna.vienna import (
    VIENNA_RUN_OF_RIVER_ANNUAL_GENERATION_GWH,
    VIENNA_RUN_OF_RIVER_INSTALLED_KW,
    load_freudenau_hourly_flow_proxy_context,
)
from Technical_model.technologies.gas_and_fuels.biogas_engine import dispatch_biogas_engine
from Technical_model.technologies.gas_and_fuels.wood_gasifier import dispatch_wood_gasifier
from Technical_model.technologies.heatpump_cop import resolve_household_heatpump_cop_series
from Technical_model.technologies.hydrogen.hydrogen_system import HydrogenSystem


def _to_price_per_kwh(values: Any, n_steps: int) -> np.ndarray:
    arr = _align_1d_length(values, n_steps, fill_value=0.0)
    if arr.size == 0:
        return np.zeros(n_steps, dtype=float)
    # Support both EUR/kWh and EUR/MWh style inputs.
    if np.nanmax(np.abs(arr)) > 5.0:
        return arr / 1000.0
    return arr


def _resolve_dispatch_prices(settings_obj: Any, params: Dict[str, Any], profiles: Dict[str, Any], n_steps: int) -> Tuple[np.ndarray, np.ndarray]:
    if "day_ahead_price" in profiles:
        grid_import_price = _to_price_per_kwh(profiles["day_ahead_price"], n_steps)
    else:
        market_bundle = build_market_bundle(settings_obj, params, profiles)
        grid_import_price = np.asarray(market_bundle.tariffs.grid_import_price, dtype=float).reshape(-1)
        if grid_import_price.size != n_steps:
            raise ValueError("[integrated_energy_system] Market import price length mismatch.")

    if "day_ahead_export_price" in profiles:
        grid_export_price = _to_price_per_kwh(profiles["day_ahead_export_price"], n_steps)
    else:
        market_bundle = build_market_bundle(settings_obj, params, profiles)
        grid_export_price = np.asarray(market_bundle.tariffs.grid_export_price, dtype=float).reshape(-1)
        if grid_export_price.size != n_steps:
            raise ValueError("[integrated_energy_system] Market export price length mismatch.")
    return grid_import_price, grid_export_price


def _district_gas_chp_power_priority_signal(config: Any, grid_import_price: np.ndarray) -> np.ndarray | None:
    """Build an explicit power-led CHP gate from settings and DA prices."""

    mode = str(getattr(config, "operating_mode_model", "fixed_ratio") or "fixed_ratio").strip().lower()
    if mode != "piecewise_power_heat_v1":
        return None
    priority_mode = str(getattr(config, "power_priority_mode", "free") or "free").strip().lower()
    if priority_mode == "free":
        return np.ones_like(grid_import_price, dtype=float)
    if priority_mode != "price_spike_gated_v1":
        raise ValueError(
            "[integrated_energy_system] Unsupported district_gas_chp.power_priority_mode "
            f"'{priority_mode}'."
        )
    quantile = float(getattr(config, "power_priority_price_quantile", 0.9) or 0.9)
    if not (0.0 < quantile <= 1.0):
        raise ValueError(
            "[integrated_energy_system] district_gas_chp.power_priority_price_quantile must be within (0, 1]."
        )
    threshold = float(np.quantile(np.asarray(grid_import_price, dtype=float), quantile))
    return (np.asarray(grid_import_price, dtype=float) >= threshold - 1e-12).astype(float)


def _fuel_price_series_eur_per_mwh(
    profiles: Dict[str, Any],
    *,
    profile_key: str,
    fallback_eur_per_m3: float,
    lhv_kwh_per_m3: float,
    n_steps: int,
) -> np.ndarray:
    if profile_key in profiles:
        return _align_1d_length(profiles[profile_key], n_steps, fill_value=0.0)
    lhv = max(1e-9, float(lhv_kwh_per_m3))
    if float(fallback_eur_per_m3) <= 0.0:
        raise ValueError(
            f"[integrated_energy_system] Missing '{profile_key}' and no positive fallback fuel_eur_per_m3 is available."
        )
    fallback = float(fallback_eur_per_m3) * 1000.0 / lhv
    return np.full(n_steps, fallback, dtype=float)


def _optional_price_series_eur_per_mwh(
    profiles: Dict[str, Any],
    *,
    profile_key: str,
    n_steps: int,
) -> np.ndarray | None:
    if profile_key not in profiles:
        return None
    arr = _align_1d_length(profiles[profile_key], n_steps, fill_value=0.0)
    if np.any(~np.isfinite(arr)) or np.any(arr <= 0.0):
        raise ValueError(
            f"[integrated_energy_system] Optional price profile '{profile_key}' must be finite and strictly positive."
        )
    return arr


def _load_daily_price_series_from_csv(
    csv_path: str,
    *,
    timestamps: Any,
    value_candidates: tuple[str, ...],
    error_label: str,
) -> np.ndarray:
    path = Path(str(csv_path or "").strip())
    if not path.exists():
        raise FileNotFoundError(f"[integrated_energy_system] {error_label} file not found: {path}")
    df = pd.read_csv(path)
    normalized = {str(col).strip().lower(): str(col) for col in df.columns}
    date_col = next((normalized[key] for key in ("date", "day", "trading_date") if key in normalized), None)
    value_col = next((normalized[key] for key in value_candidates if key in normalized), None)
    if date_col is None or value_col is None:
        raise KeyError(
            f"[integrated_energy_system] {error_label} CSV requires a date column and one of {list(value_candidates)}."
        )
    work = pd.DataFrame(
        {
            "date": pd.to_datetime(df[date_col], errors="coerce").dt.normalize(),
            "value": pd.to_numeric(df[value_col], errors="coerce"),
        }
    ).dropna(subset=["date", "value"])
    if work.empty:
        raise ValueError(f"[integrated_energy_system] {error_label} CSV has no valid rows after parsing.")
    work = work.sort_values("date").drop_duplicates(subset=["date"], keep="last")
    day_map = {pd.Timestamp(row.date): float(row.value) for row in work.itertuples(index=False)}
    ts_index = pd.to_datetime(np.asarray(timestamps).reshape(-1), errors="coerce")
    if ts_index.size == 0 or pd.isna(ts_index[0]):
        raise ValueError(f"[integrated_energy_system] {error_label} requires valid timestamps.")
    out = np.empty(ts_index.size, dtype=float)
    last_value: float | None = None
    for idx, ts in enumerate(ts_index):
        day = pd.Timestamp(ts).normalize()
        value = day_map.get(day)
        if value is None:
            if last_value is None:
                raise ValueError(
                    f"[integrated_energy_system] {error_label} CSV does not cover the first required timestamp day {day.date()}."
                )
            value = last_value
        out[idx] = float(value)
        last_value = float(value)
    if np.any(~np.isfinite(out)) or np.any(out <= 0.0):
        raise ValueError(f"[integrated_energy_system] {error_label} series must be finite and strictly positive.")
    return out


def _u_a(building: Dict[str, Any]) -> float:
    if "effective_total_loss_coefficient_w_per_k" not in building:
        raise KeyError(
            "[integrated_energy_system] building params must contain 'effective_total_loss_coefficient_w_per_k'."
        )
    value = float(building["effective_total_loss_coefficient_w_per_k"])
    if value <= 0.0:
        raise ValueError(
            f"[integrated_energy_system] effective_total_loss_coefficient_w_per_k must be > 0, got {value}."
        )
    return value


def _distribute(total_kwh: float, caps: np.ndarray) -> np.ndarray:
    caps = np.asarray(caps, dtype=float)
    out = np.zeros_like(caps)
    rem = max(0.0, float(total_kwh))
    for idx in np.argsort(-caps):
        if rem <= 0.0:
            break
        give = min(rem, max(0.0, caps[idx]))
        out[idx] = give
        rem -= give
    return out


def _align_1d_length(values: Any, n_steps: int, fill_value: float = 0.0) -> np.ndarray:
    arr = np.asarray(values, dtype=float).reshape(-1)
    if arr.size == n_steps:
        return arr
    if arr.size > n_steps:
        return arr[:n_steps]
    if arr.size == 0:
        return np.full(n_steps, float(fill_value), dtype=float)
    return np.concatenate([arr, np.full(n_steps - arr.size, float(arr[-1]), dtype=float)])


def _to_celsius_if_kelvin(values: Any) -> np.ndarray:
    arr = np.asarray(values, dtype=float).reshape(-1)
    if arr.size == 0:
        return arr
    finite = arr[np.isfinite(arr)]
    if finite.size == 0:
        return arr
    if float(np.nanmedian(finite)) > 150.0:
        return arr - 273.15
    return arr


def _require_float_attr(obj: Any, attr: str) -> float:
    if obj is None or not hasattr(obj, attr):
        raise ValueError(f"[integrated_energy_system] Missing required config attribute '{attr}'.")
    value = getattr(obj, attr)
    if value is None:
        raise ValueError(f"[integrated_energy_system] Config attribute '{attr}' must not be None.")
    return float(value)


def _district_gas_chp_piecewise_payload(config: Any) -> Dict[str, Any]:
    """Expose the explicit CHP operating-region SSOT for dispatch.

    The payload is only meaningful for the future piecewise gas-CHP mode.
    Keeping this extraction in one helper ensures that the later MILP path
    reads exactly the same point set that lives in Settings and source notes.
    """

    mode = str(getattr(config, "operating_mode_model", "fixed_ratio") or "fixed_ratio").strip().lower()
    power_priority_mode = str(getattr(config, "power_priority_mode", "free") or "free").strip().lower()
    power_priority_price_quantile = float(getattr(config, "power_priority_price_quantile", 0.9) or 0.9)
    points_raw = tuple(getattr(config, "operating_points_v1", ()) or ())
    names: List[str] = []
    eta_el_values: List[float] = []
    eta_th_values: List[float] = []
    for idx, point in enumerate(points_raw):
        name = str(getattr(point, "name", "") or "").strip()
        if not name:
            raise ValueError(
                "[integrated_energy_system] district_gas_chp.operating_points_v1 entries require non-empty names."
            )
        eta_el = float(getattr(point, "eta_el", 0.0) or 0.0)
        eta_th = float(getattr(point, "eta_th", 0.0) or 0.0)
        if eta_el <= 0.0 or eta_th <= 0.0:
            raise ValueError(
                "[integrated_energy_system] district_gas_chp.operating_points_v1 requires strictly positive eta_el and eta_th. "
                f"Point index {idx} has eta_el={eta_el}, eta_th={eta_th}."
            )
        names.append(name)
        eta_el_values.append(eta_el)
        eta_th_values.append(eta_th)
    max_eta_el = max(eta_el_values) if eta_el_values else 0.0
    max_th_ratio = max((eta_th / max_eta_el) for eta_th in eta_th_values) if max_eta_el > 0.0 else 0.0
    return {
        "operating_mode_model": mode,
        "power_priority_mode": power_priority_mode,
        "power_priority_price_quantile": power_priority_price_quantile,
        "operating_point_names": names,
        "operating_point_eta_el": eta_el_values,
        "operating_point_eta_th": eta_th_values,
        "power_led_eta_el_anchor": max_eta_el,
        "max_thermal_ratio_on_el_base": max_th_ratio,
    }


def _is_scheduled_downtime(timestamp: Any, config: Any) -> bool:
    if config is None:
        return False
    days = int(getattr(config, "scheduled_downtime_days_per_year", 0) or 0)
    start_day = int(getattr(config, "scheduled_downtime_start_day_of_year", 1) or 1)
    if days <= 0:
        return False
    if not 1 <= start_day <= 366:
        raise ValueError("[integrated_energy_system] scheduled_downtime_start_day_of_year must be within [1, 366].")
    if not 0 <= days <= 366:
        raise ValueError("[integrated_energy_system] scheduled_downtime_days_per_year must be within [0, 366].")
    day = int(pd.Timestamp(timestamp).dayofyear)
    end_day = start_day + days
    if end_day <= 366:
        return start_day <= day < end_day
    overflow = end_day - 366
    return day >= start_day or day < overflow


def _require_block(params: Dict[str, Any], key: str) -> Dict[str, Any]:
    if key not in params or not isinstance(params[key], dict):
        raise ValueError(f"[integrated_energy_system] Missing required params['{key}'] dict.")
    return params[key]


def _require_attr(obj: Any, attr: str) -> Any:
    if obj is None or not hasattr(obj, attr):
        raise ValueError(f"[integrated_energy_system] Missing required config attribute '{attr}'.")
    return getattr(obj, attr)


def _require_nonnegative_param(params: Dict[str, Any], key: str) -> float:
    if key not in params:
        raise ValueError(f"[integrated_energy_system] Missing required params['{key}'].")
    value = float(params[key])
    if value < 0.0:
        raise ValueError(f"[integrated_energy_system] params['{key}'] must be >= 0, got {value}.")
    return value


def _require_profile(profiles: Dict[str, Any], key: str) -> Any:
    if key not in profiles:
        raise ValueError(f"[integrated_energy_system] Missing required profile '{key}'.")
    return profiles[key]


def _require_tech_economic_value(tech_economics: Dict[str, Any], tech_name: str, key: str) -> float:
    tech_block = tech_economics.get(tech_name)
    if not isinstance(tech_block, dict):
        raise ValueError(
            f"[integrated_energy_system] Missing required economics block params['economics']['technology']['{tech_name}']."
        )
    if key not in tech_block or tech_block[key] is None:
        raise ValueError(
            f"[integrated_energy_system] Missing required economics key "
            f"params['economics']['technology']['{tech_name}']['{key}']."
        )
    return float(tech_block[key])


def _member_count(member: Any) -> int:
    if hasattr(member, "count"):
        return int(member.count)
    if hasattr(member, "n_households"):
        return int(member.n_households)
    raise ValueError("[integrated_energy_system] Member config requires 'count' or 'n_households'.")


def _allocate_surplus(
    surplus_kwh: float,
    ev_charge_cap_kwh: float,
    thermflex_cap_kwh: float,
    bess_charge_cap_kwh: float,
    h2_ely_cap_kwh: float,
) -> dict:
    rem = max(0.0, float(surplus_kwh))
    ev = min(rem, max(0.0, float(ev_charge_cap_kwh)))
    rem -= ev
    thermflex = min(rem, max(0.0, float(thermflex_cap_kwh)))
    rem -= thermflex
    bess = min(rem, max(0.0, float(bess_charge_cap_kwh)))
    rem -= bess
    h2 = min(rem, max(0.0, float(h2_ely_cap_kwh)))
    rem -= h2
    return {"ev_charge": ev, "thermflex": thermflex, "bess_charge": bess, "h2_electrolysis": h2, "export": max(0.0, rem)}


def _allocate_deficit(
    deficit_kwh: float,
    v2h_discharge_cap_kwh: float,
    bess_discharge_cap_kwh: float,
    h2_fc_cap_kwh: float,
) -> dict:
    rem = max(0.0, float(deficit_kwh))
    v2h = min(rem, max(0.0, float(v2h_discharge_cap_kwh)))
    rem -= v2h
    bess = min(rem, max(0.0, float(bess_discharge_cap_kwh)))
    rem -= bess
    h2 = min(rem, max(0.0, float(h2_fc_cap_kwh)))
    rem -= h2
    return {"v2h_discharge": v2h, "bess_discharge": bess, "h2_fuel_cell": h2, "import": max(0.0, rem)}


def _build_member_keys(members_cfg: Any, n_members: int) -> List[str]:
    keys: List[str] = []
    for member in members_cfg.members:
        keys.extend([str(member.building_key)] * _member_count(member))
    if len(keys) != n_members:
        raise ValueError("[integrated_energy_system] Member structure does not match profile dimensionality.")
    return keys


def _thermflex_lower_bound_schedule_c(
    timestamps: Any,
    heating_control_cfg: Any,
    thermflex_constraints_cfg: Any,
) -> np.ndarray | None:
    if thermflex_constraints_cfg is None or not bool(
        getattr(thermflex_constraints_cfg, "use_explicit_lower_bounds", False)
    ):
        return None
    if heating_control_cfg is None:
        raise ValueError(
            "[integrated_energy_system] Explicit thermflex lower bounds require heating_control settings."
        )
    ref_mode = str(getattr(heating_control_cfg, "reference_control_mode", "constant") or "constant").strip().lower()
    ts_index = pd.to_datetime(np.asarray(timestamps))
    lower = np.zeros(ts_index.size, dtype=float)
    if ref_mode == "constant":
        constant_lower = getattr(thermflex_constraints_cfg, "constant_lower_bound_c", None)
        if constant_lower is None:
            constant_lower = getattr(thermflex_constraints_cfg, "day_lower_bound_c", None)
        if constant_lower is None:
            raise ValueError(
                "[integrated_energy_system] use_explicit_lower_bounds=True with constant reference mode "
                "requires constraints.thermflex.constant_lower_bound_c."
            )
        lower[:] = float(constant_lower)
        return lower
    day_lower = getattr(thermflex_constraints_cfg, "day_lower_bound_c", None)
    night_lower = getattr(thermflex_constraints_cfg, "night_lower_bound_c", None)
    if day_lower is None or night_lower is None:
        raise ValueError(
            "[integrated_energy_system] use_explicit_lower_bounds=True with day_night reference mode requires "
            "constraints.thermflex.day_lower_bound_c and night_lower_bound_c."
        )
    for idx, ts in enumerate(ts_index):
        lower[idx] = float(night_lower if is_night_hour(int(pd.Timestamp(ts).hour), heating_control_cfg) else day_lower)
    return lower


def _thermflex_event_bound_payload(
    *,
    input_payload: Dict[str, Any],
    settings_obj: Any,
) -> Dict[str, float]:
    def _require_event_metric(name: str) -> float:
        if name not in event_response:
            raise KeyError(
                "[integrated_energy_system] Event-response thermflex bounds require "
                f"calibration_event_response_v1['{name}']."
            )
        value = float(event_response[name])
        if not np.isfinite(value):
            raise ValueError(
                "[integrated_energy_system] Event-response thermflex bounds require finite "
                f"calibration_event_response_v1['{name}']."
            )
        return value

    event_response = input_payload.get("calibration_event_response_v1")
    if not isinstance(event_response, dict):
        raise ValueError(
            "[integrated_energy_system] Event-response thermflex bounds require calibration_event_response_v1 per thermflex member."
        )
    building_calibration_cfg = getattr(settings_obj, "building_calibration", None)
    if building_calibration_cfg is None:
        raise ValueError(
            "[integrated_energy_system] Event-response thermflex bounds require settings.building_calibration."
        )
    teacher_reference_gfa_m2 = float(getattr(building_calibration_cfg, "teacher_reference_gfa_m2", 0.0) or 0.0)
    if teacher_reference_gfa_m2 <= 0.0:
        raise ValueError(
            "[integrated_energy_system] settings.building_calibration.teacher_reference_gfa_m2 must be > 0 "
            "when event-response thermflex bounds are enabled."
        )
    if "a_floor_m2" not in input_payload:
        raise KeyError(
            "[integrated_energy_system] Thermflex event-response scaling requires input_payload['a_floor_m2']."
        )
    a_floor_m2 = float(input_payload["a_floor_m2"])
    if a_floor_m2 <= 0.0:
        raise ValueError(
            "[integrated_energy_system] Thermflex event-response scaling requires input_payload['a_floor_m2'] > 0."
        )
    area_scale = a_floor_m2 / teacher_reference_gfa_m2
    preheat_added_energy_kwh = _require_event_metric("preheat_added_energy_kwh")
    preheat_peak_excess_kw = _require_event_metric("preheat_peak_excess_kw")
    cutback_shed_energy_kwh = _require_event_metric("cutback_shed_energy_kwh")
    cutback_peak_shed_kw = _require_event_metric("cutback_peak_shed_kw")
    recovery_rebound_energy_kwh = _require_event_metric("recovery_rebound_energy_kwh")
    recovery_time_to_reference_h = _require_event_metric("recovery_time_to_reference_h")
    required_nonnegative = {
        "preheat_added_energy_kwh": preheat_added_energy_kwh,
        "preheat_peak_excess_kw": preheat_peak_excess_kw,
        "cutback_shed_energy_kwh": cutback_shed_energy_kwh,
        "cutback_peak_shed_kw": cutback_peak_shed_kw,
        "recovery_rebound_energy_kwh": recovery_rebound_energy_kwh,
    }
    for label, value in required_nonnegative.items():
        if value < 0.0:
            raise ValueError(
                "[integrated_energy_system] Event-response thermflex bounds require nonnegative "
                f"'{label}', got {value}."
            )
    if recovery_time_to_reference_h <= 0.0:
        raise ValueError(
            "[integrated_energy_system] Event-response thermflex bounds require positive "
            f"'recovery_time_to_reference_h', got {recovery_time_to_reference_h}."
        )
    result = {
        "preheat_event_energy_limit_kwh": preheat_added_energy_kwh * area_scale,
        "preheat_peak_excess_kwh_per_step": preheat_peak_excess_kw * area_scale,
        "cutback_event_energy_limit_kwh": cutback_shed_energy_kwh * area_scale,
        "cutback_peak_shed_kwh_per_step": cutback_peak_shed_kw * area_scale,
        "recovery_rebound_energy_kwh": recovery_rebound_energy_kwh * area_scale,
        "recovery_time_to_reference_h": recovery_time_to_reference_h,
    }
    return result


def _active_dh_source_names(settings_obj: Any) -> List[str]:
    names: List[str] = []
    activation = _require_attr(settings_obj, "technology_activation")
    if bool(getattr(activation, "district_geothermal", False)):
        names.append("district_geothermal")
    if bool(getattr(activation, "district_solar_thermal", False)):
        names.append("district_solar_thermal")
    if bool(getattr(activation, "district_external_heat", False)):
        names.append("district_external_heat")
    if bool(getattr(activation, "district_waste_incineration", False)):
        names.append("district_waste_incineration")
    if bool(getattr(activation, "district_biomass_chp", False)):
        names.append("district_biomass_chp")
    if bool(getattr(activation, "district_biogas_chp", False)):
        names.append("district_biogas_chp")
    if bool(getattr(activation, "district_gas_chp", False)):
        names.append("district_gas_chp")
    if bool(getattr(activation, "district_gas_boiler", False)):
        names.append("district_gas_boiler")
    if bool(getattr(activation, "district_wood_chip_boiler", False)):
        names.append("district_wood_chip_boiler")
    if bool(getattr(activation, "district_heat_pump", False)):
        names.append("district_heat_pump")
    return names


def _build_dh_context(settings_obj: Any, profiles: Dict[str, Any], members_cfg: Any, n_members: int) -> Dict[str, Any] | None:
    dh_cfg = _require_attr(settings_obj, "district_heating")
    if float(dh_cfg.share) <= 0.0:
        return None

    dh_demand = build_dh_demand(settings_obj, profiles)
    dh_buildings = build_dh_buildings(settings_obj, profiles, dh_demand)
    source_names = _active_dh_source_names(settings_obj)
    if not source_names:
        raise ValueError("[integrated_energy_system] district_heating.share > 0 requires at least one active DH source.")
    dh_bus = build_dh_bus(dh_demand, dh_buildings, source_names=source_names)
    dh_bus["meta"]["timestamps"] = profiles.get(
        "timestamps",
        pd.date_range("2023-01-01", periods=int(np.asarray(dh_demand["total"]).shape[0]), freq="h"),
    )
    dh_bus["meta"]["solar_irradiance_w_per_m2"] = np.asarray(profiles.get("irradiance", np.zeros_like(dh_demand["total"])), dtype=float)
    dh_bus["meta"]["ambient_temp_c"] = _to_celsius_if_kelvin(profiles.get("T_outdoor", np.zeros_like(dh_demand["total"])))
    result = {
        "demand": dh_demand,
        "buildings": dh_buildings,
        "bus": dh_bus,
        "member_share_vector": np.asarray(dh_demand["member_share_vector"], dtype=float),
        "source_names": source_names,
    }
    return result


def _aggregate_by_type(values: np.ndarray, member_keys: List[str], known_keys: List[str]) -> Dict[str, float]:
    out = {key: 0.0 for key in known_keys}
    for idx, building_key in enumerate(member_keys):
        out[building_key] = out.get(building_key, 0.0) + float(values[idx])
    return out


def _step_district_heating(
    t: int,
    dh_context: Dict[str, Any] | None,
    settings_obj: Any,
    params: Dict[str, Any],
    member_keys: List[str],
    space_heat_dh_member: np.ndarray,
    hotwater_dh_member: np.ndarray,
    storage_soc_prev_kwh: float,
) -> Tuple[Dict[str, Any], float, float, float]:
    if dh_context is None:
        return {"total_demand_kwh": 0.0, "delivered_kwh": 0.0, "unserved_kwh": 0.0}, 0.0, 0.0, 0.0

    known_keys = list(dh_context["demand"]["space_heat_by_type"].keys())
    step_space = _aggregate_by_type(space_heat_dh_member, member_keys, known_keys)
    step_hotwater = _aggregate_by_type(hotwater_dh_member, member_keys, known_keys)
    total_demand = float(sum(step_space.values()) + sum(step_hotwater.values()))
    remaining_demand_kwh = float(total_demand)

    source_inputs: Dict[str, Dict[str, float]] = {}
    timestamp = dh_context["bus"]["meta"]["timestamps"][t]
    ambient_temp_c = float(dh_context["bus"]["meta"].get("ambient_temp_c", np.zeros_like(dh_context["bus"]["demand"]["total"]))[t])
    network_supply_temp_c, network_return_temp_c = get_dh_bus_temperatures(
        ambient_temp_c,
        _require_attr(settings_obj, "district_heating"),
    )
    required_direct_supply_temp_c = get_required_source_supply_temp_c(
        ambient_temp_c,
        _require_attr(settings_obj, "district_heating"),
    )
    required_preheat_supply_temp_c = get_required_preheat_source_temp_c(
        ambient_temp_c,
        _require_attr(settings_obj, "district_heating"),
    )
    geothermal_dispatch = None
    geothermal_direct_thermal_kwh = 0.0
    geothermal_excess_charge_kwh = 0.0
    geothermal_spillage_kwh = 0.0
    if "district_geothermal" in dh_context["source_names"]:
        geothermal_dispatch = dispatch_district_geothermal_orc(
            installed_kw_el=float(params.get("district_geothermal_kw_el", 0.0)),
            config=_require_attr(settings_obj, "district_geothermal"),
            timestamp=timestamp,
            dt_h=1.0,
        )
        source_inputs["district_geothermal"] = dict(geothermal_dispatch)
        geothermal_direct_thermal_kwh = min(remaining_demand_kwh, float(geothermal_dispatch["thermal_kwh"]))
        remaining_demand_kwh = max(0.0, remaining_demand_kwh - geothermal_direct_thermal_kwh)
        geothermal_excess_charge_kwh = max(0.0, float(geothermal_dispatch["thermal_kwh"]) - geothermal_direct_thermal_kwh)

    solar_thermal_dispatch = None
    solar_thermal_direct_kwh = 0.0
    solar_thermal_preheat_kwh = 0.0
    solar_thermal_excess_charge_kwh = 0.0
    solar_thermal_charge_kwh = 0.0
    solar_thermal_spillage_kwh = 0.0
    if "district_solar_thermal" in dh_context["source_names"]:
        solar_precomputed = dh_context["bus"]["meta"].get("district_solar_thermal_precomputed")
        if solar_precomputed is None:
            raise ValueError(
                "[integrated_energy_system] district_solar_thermal is active, but district_solar_thermal_precomputed "
                "is missing from dh_context['bus']['meta']."
            )
        direct_capacity_kwh = float(np.asarray(solar_precomputed["direct_feed_capacity_kwh"], dtype=float)[t])
        preheat_capacity_kwh = float(np.asarray(solar_precomputed["preheat_capacity_kwh"], dtype=float)[t])
        solar_thermal_direct_kwh = min(remaining_demand_kwh, direct_capacity_kwh)
        remaining_after_solar_direct_kwh = max(0.0, remaining_demand_kwh - solar_thermal_direct_kwh)
        solar_thermal_preheat_kwh = min(
            remaining_after_solar_direct_kwh,
            max(0.0, preheat_capacity_kwh - solar_thermal_direct_kwh),
        )
        remaining_demand_kwh = max(0.0, remaining_after_solar_direct_kwh - solar_thermal_preheat_kwh)
        solar_thermal_excess_charge_kwh = max(
            0.0,
            preheat_capacity_kwh - solar_thermal_direct_kwh - solar_thermal_preheat_kwh,
        )
        solar_thermal_dispatch = {
            "thermal_kwh": float(solar_thermal_direct_kwh + solar_thermal_preheat_kwh),
            "thermal_capacity_kwh": float(direct_capacity_kwh),
            "total_useful_capacity_kwh": float(preheat_capacity_kwh),
            "direct_feed_capacity_kwh": float(direct_capacity_kwh),
            "preheat_capacity_kwh": float(preheat_capacity_kwh),
            "direct_feed_kwh": float(solar_thermal_direct_kwh),
            "preheat_kwh": float(solar_thermal_preheat_kwh),
            "storage_candidate_kwh": float(solar_thermal_excess_charge_kwh),
            "storage_charge_kwh": 0.0,
            "thermal_spillage_kwh": 0.0,
            "direct_feed_feasible": float(direct_capacity_kwh > 0.0),
            "preheat_feasible": float(preheat_capacity_kwh > 0.0),
            "effective_efficiency": float(
                np.asarray(
                    solar_precomputed["preheat_effective_efficiency"]
                    if solar_thermal_preheat_kwh > 0.0
                    else solar_precomputed["direct_effective_efficiency"],
                    dtype=float,
                )[t]
            ),
            "direct_effective_efficiency": float(
                np.asarray(solar_precomputed["direct_effective_efficiency"], dtype=float)[t]
            ),
            "preheat_effective_efficiency": float(
                np.asarray(solar_precomputed["preheat_effective_efficiency"], dtype=float)[t]
            ),
            "max_mass_flow_kg_per_s": float(np.asarray(solar_precomputed["max_mass_flow_kg_per_s"], dtype=float)[t]),
            "collector_area_m2": float(np.asarray(solar_precomputed["collector_area_m2"], dtype=float)[t]),
            "collector_irradiance_w_per_m2": float(np.asarray(solar_precomputed["collector_irradiance_w_per_m2"], dtype=float)[t]),
            "diffuse_irradiance_w_per_m2": float(np.asarray(solar_precomputed["diffuse_irradiance_w_per_m2"], dtype=float)[t]),
            "direct_delta_temp_n_c": float(np.asarray(solar_precomputed["direct_delta_temp_n_c"], dtype=float)[t]),
            "preheat_delta_temp_n_c": float(np.asarray(solar_precomputed["preheat_delta_temp_n_c"], dtype=float)[t]),
        }
        source_inputs["district_solar_thermal"] = dict(solar_thermal_dispatch)

    external_heat_dispatch = None
    external_heat_direct_thermal_kwh = 0.0
    external_heat_excess_charge_kwh = 0.0
    external_heat_spillage_kwh = 0.0
    if "district_external_heat" in dh_context["source_names"]:
        external_heat_dispatch = dispatch_district_external_heat(
            requested_thermal_kwh=remaining_demand_kwh,
            installed_kw_th=_require_nonnegative_param(params, "district_external_heat_kw_th"),
            config=_require_attr(settings_obj, "district_external_heat"),
            dt_h=1.0,
        )
        source_inputs["district_external_heat"] = dict(external_heat_dispatch)
        external_heat_direct_thermal_kwh = min(remaining_demand_kwh, float(external_heat_dispatch["thermal_kwh"]))
        remaining_demand_kwh = max(0.0, remaining_demand_kwh - external_heat_direct_thermal_kwh)
        external_heat_excess_charge_kwh = max(
            0.0,
            float(external_heat_dispatch["thermal_kwh"]) - external_heat_direct_thermal_kwh,
        )

    waste_dispatch = None
    waste_direct_thermal_kwh = 0.0
    waste_excess_charge_kwh = 0.0
    waste_spillage_kwh = 0.0
    if "district_waste_incineration" in dh_context["source_names"]:
        waste_dispatch = dispatch_district_waste_incineration(
            requested_thermal_kwh=remaining_demand_kwh,
            installed_kw_th=_require_nonnegative_param(params, "district_waste_incineration_kw_th"),
            config=_require_attr(settings_obj, "district_waste_incineration"),
            dt_h=1.0,
        )
        source_inputs["district_waste_incineration"] = dict(waste_dispatch)
        waste_direct_thermal_kwh = min(remaining_demand_kwh, float(waste_dispatch["thermal_kwh"]))
        remaining_demand_kwh = max(0.0, remaining_demand_kwh - waste_direct_thermal_kwh)
        waste_excess_charge_kwh = max(0.0, float(waste_dispatch["thermal_kwh"]) - waste_direct_thermal_kwh)

    biomass_chp_dispatch = None
    biomass_chp_direct_thermal_kwh = 0.0
    biomass_chp_excess_charge_kwh = 0.0
    biomass_chp_spillage_kwh = 0.0
    if "district_biomass_chp" in dh_context["source_names"]:
        biomass_chp_dispatch = dispatch_district_biomass_chp(
            requested_thermal_kwh=remaining_demand_kwh,
            installed_kw_th=float(params.get("district_biomass_chp_kw_th", 0.0)),
            config=_require_attr(settings_obj, "district_biomass_chp"),
            timestamp=timestamp,
            dt_h=1.0,
        )
        source_inputs["district_biomass_chp"] = dict(biomass_chp_dispatch)
        biomass_chp_direct_thermal_kwh = min(remaining_demand_kwh, float(biomass_chp_dispatch["thermal_kwh"]))
        remaining_demand_kwh = max(0.0, remaining_demand_kwh - biomass_chp_direct_thermal_kwh)
        biomass_chp_excess_charge_kwh = max(
            0.0,
            float(biomass_chp_dispatch["thermal_kwh"]) - biomass_chp_direct_thermal_kwh,
        )

    biogas_chp_dispatch = None
    biogas_chp_direct_thermal_kwh = 0.0
    biogas_chp_excess_charge_kwh = 0.0
    biogas_chp_spillage_kwh = 0.0
    if "district_biogas_chp" in dh_context["source_names"]:
        biogas_chp_dispatch = dispatch_district_biogas_chp(
            requested_thermal_kwh=remaining_demand_kwh,
            installed_kw_el=float(params.get("district_biogas_chp_kw_el", 0.0)),
            config=_require_attr(settings_obj, "district_biogas_chp"),
            timestamp=timestamp,
            dt_h=1.0,
        )
        source_inputs["district_biogas_chp"] = dict(biogas_chp_dispatch)
        biogas_chp_direct_thermal_kwh = min(remaining_demand_kwh, float(biogas_chp_dispatch["thermal_kwh"]))
        remaining_demand_kwh = max(0.0, remaining_demand_kwh - biogas_chp_direct_thermal_kwh)
        biogas_chp_excess_charge_kwh = max(0.0, float(biogas_chp_dispatch["thermal_kwh"]) - biogas_chp_direct_thermal_kwh)

    gas_chp_dispatch = None
    gas_chp_direct_thermal_kwh = 0.0
    gas_chp_excess_charge_kwh = 0.0
    gas_chp_spillage_kwh = 0.0
    if "district_gas_chp" in dh_context["source_names"]:
        gas_chp_dispatch = dispatch_district_gas_chp(
            requested_thermal_kwh=remaining_demand_kwh,
            installed_kw_el=float(params.get("district_gas_chp_kw_el", 0.0)),
            config=_require_attr(settings_obj, "district_gas_chp"),
            timestamp=timestamp,
            dt_h=1.0,
        )
        source_inputs["district_gas_chp"] = dict(gas_chp_dispatch)
        gas_chp_direct_thermal_kwh = min(remaining_demand_kwh, float(gas_chp_dispatch["thermal_kwh"]))
        remaining_demand_kwh = max(0.0, remaining_demand_kwh - gas_chp_direct_thermal_kwh)
        gas_chp_excess_charge_kwh = max(0.0, float(gas_chp_dispatch["thermal_kwh"]) - gas_chp_direct_thermal_kwh)

    gas_boiler_dispatch = None
    gas_boiler_direct_thermal_kwh = 0.0
    gas_boiler_excess_charge_kwh = 0.0
    gas_boiler_spillage_kwh = 0.0
    if "district_gas_boiler" in dh_context["source_names"]:
        gas_boiler_dispatch = dispatch_district_gas_boiler(
            requested_thermal_kwh=remaining_demand_kwh,
            installed_kw_th=_require_nonnegative_param(params, "district_gas_boiler_kw_th"),
            config=_require_attr(settings_obj, "district_gas_boiler"),
            timestamp=timestamp,
            dt_h=1.0,
        )
        source_inputs["district_gas_boiler"] = dict(gas_boiler_dispatch)
        gas_boiler_direct_thermal_kwh = min(remaining_demand_kwh, float(gas_boiler_dispatch["thermal_kwh"]))
        remaining_demand_kwh = max(0.0, remaining_demand_kwh - gas_boiler_direct_thermal_kwh)
        gas_boiler_excess_charge_kwh = max(0.0, float(gas_boiler_dispatch["thermal_kwh"]) - gas_boiler_direct_thermal_kwh)

    boiler_dispatch = None
    boiler_direct_thermal_kwh = 0.0
    boiler_excess_charge_kwh = 0.0
    boiler_spillage_kwh = 0.0
    if "district_wood_chip_boiler" in dh_context["source_names"]:
        boiler_dispatch = dispatch_district_wood_chip_boiler(
            requested_thermal_kwh=remaining_demand_kwh,
            installed_kw_th=float(params.get("district_wood_chip_boiler_kw_th", 0.0)),
            config=_require_attr(settings_obj, "district_wood_chip_boiler"),
            timestamp=timestamp,
            dt_h=1.0,
        )
        source_inputs["district_wood_chip_boiler"] = dict(boiler_dispatch)
        boiler_direct_thermal_kwh = min(remaining_demand_kwh, float(boiler_dispatch["thermal_kwh"]))
        remaining_demand_kwh = max(0.0, remaining_demand_kwh - boiler_direct_thermal_kwh)
        boiler_excess_charge_kwh = max(0.0, float(boiler_dispatch["thermal_kwh"]) - boiler_direct_thermal_kwh)

    hp_dispatch = None
    hp_direct_thermal_kwh = 0.0
    if "district_heat_pump" in dh_context["source_names"]:
        hp_dispatch = dispatch_district_heat_pump(
            requested_thermal_kwh=remaining_demand_kwh,
            installed_kw_th=float(params.get("district_heat_pump_kw_th", 0.0)),
            config=_require_attr(settings_obj, "district_heat_pump"),
            dt_h=1.0,
        )
        source_inputs["district_heat_pump"] = dict(hp_dispatch)
        hp_direct_thermal_kwh = float(hp_dispatch["thermal_kwh"])
        remaining_demand_kwh = max(0.0, remaining_demand_kwh - hp_direct_thermal_kwh)

    storage_cfg = getattr(settings_obj, "district_thermal_storage", None)
    storage_enabled = bool(getattr(_require_attr(settings_obj, "technology_activation"), "district_thermal_storage", False))
    installed_storage_kwh = float(params.get("district_thermal_storage_kwh_th", 0.0))
    requested_discharge_kwh = max(0.0, remaining_demand_kwh)
    storage_step = {
        "charge_kwh": 0.0,
        "discharge_kwh": 0.0,
        "losses_kwh": 0.0,
        "soc_kwh": float(storage_soc_prev_kwh),
    }
    if storage_enabled and installed_storage_kwh > 0.0:
        hp_available_charge_kwh = (
            max(0.0, float(hp_dispatch["thermal_capacity_kwh"]) - hp_direct_thermal_kwh) if hp_dispatch is not None else 0.0
        )
        storage_step = step_district_thermal_storage(
            available_charge_kwh=(
                geothermal_excess_charge_kwh
                + solar_thermal_excess_charge_kwh
                + external_heat_excess_charge_kwh
                + waste_excess_charge_kwh
                + biomass_chp_excess_charge_kwh
                + biogas_chp_excess_charge_kwh
                + gas_chp_excess_charge_kwh
                + gas_boiler_excess_charge_kwh
                + boiler_excess_charge_kwh
                + hp_available_charge_kwh
            ),
            requested_discharge_kwh=requested_discharge_kwh,
            soc_prev_kwh=storage_soc_prev_kwh,
            installed_capacity_kwh_th=installed_storage_kwh,
            config=storage_cfg,
            dt_h=1.0,
        )
        dh_context["bus"]["storage"]["charge_kwh"][t] = float(storage_step["charge_kwh"])
        dh_context["bus"]["storage"]["discharge_kwh"][t] = float(storage_step["discharge_kwh"])
        dh_context["bus"]["storage"]["soc_kwh"][t] = float(storage_step["soc_kwh"])
        if "losses_kwh" not in dh_context["bus"]["storage"]:
            dh_context["bus"]["storage"]["losses_kwh"] = np.zeros_like(dh_context["bus"]["demand"]["total"], dtype=float)
        dh_context["bus"]["storage"]["losses_kwh"][t] = float(storage_step["losses_kwh"])
        geothermal_charge_kwh = min(geothermal_excess_charge_kwh, float(storage_step["charge_kwh"]))
        residual_charge_after_geothermal = max(0.0, float(storage_step["charge_kwh"]) - geothermal_charge_kwh)
        solar_thermal_charge_kwh = min(solar_thermal_excess_charge_kwh, residual_charge_after_geothermal)
        residual_charge_after_solar_thermal = max(0.0, residual_charge_after_geothermal - solar_thermal_charge_kwh)
        external_heat_charge_kwh = min(external_heat_excess_charge_kwh, residual_charge_after_solar_thermal)
        residual_charge_after_external_heat = max(0.0, residual_charge_after_solar_thermal - external_heat_charge_kwh)
        waste_charge_kwh = min(waste_excess_charge_kwh, residual_charge_after_external_heat)
        residual_charge_after_waste = max(0.0, residual_charge_after_external_heat - waste_charge_kwh)
        biomass_chp_charge_kwh = min(biomass_chp_excess_charge_kwh, residual_charge_after_waste)
        residual_charge_after_biomass_chp = max(0.0, residual_charge_after_waste - biomass_chp_charge_kwh)
        biogas_chp_charge_kwh = min(biogas_chp_excess_charge_kwh, residual_charge_after_biomass_chp)
        residual_charge_after_biogas_chp = max(0.0, residual_charge_after_biomass_chp - biogas_chp_charge_kwh)
        gas_chp_charge_kwh = min(gas_chp_excess_charge_kwh, residual_charge_after_biogas_chp)
        residual_charge_after_gas_chp = max(0.0, residual_charge_after_biogas_chp - gas_chp_charge_kwh)
        gas_boiler_charge_kwh = min(gas_boiler_excess_charge_kwh, residual_charge_after_gas_chp)
        residual_charge_after_gas_boiler = max(0.0, residual_charge_after_gas_chp - gas_boiler_charge_kwh)
        boiler_charge_kwh = min(boiler_excess_charge_kwh, residual_charge_after_gas_boiler)
        residual_charge_after_boiler = max(0.0, residual_charge_after_gas_boiler - boiler_charge_kwh)
        hp_charge_kwh = min(hp_available_charge_kwh, residual_charge_after_boiler)
        geothermal_spillage_kwh = max(0.0, geothermal_excess_charge_kwh - geothermal_charge_kwh)
        solar_thermal_spillage_kwh = max(0.0, solar_thermal_excess_charge_kwh - solar_thermal_charge_kwh)
        external_heat_spillage_kwh = max(0.0, external_heat_excess_charge_kwh - external_heat_charge_kwh)
        waste_spillage_kwh = max(0.0, waste_excess_charge_kwh - waste_charge_kwh)
        biomass_chp_spillage_kwh = max(0.0, biomass_chp_excess_charge_kwh - biomass_chp_charge_kwh)
        biogas_chp_spillage_kwh = max(0.0, biogas_chp_excess_charge_kwh - biogas_chp_charge_kwh)
        gas_chp_spillage_kwh = max(0.0, gas_chp_excess_charge_kwh - gas_chp_charge_kwh)
        gas_boiler_spillage_kwh = max(0.0, gas_boiler_excess_charge_kwh - gas_boiler_charge_kwh)
        boiler_spillage_kwh = max(0.0, boiler_excess_charge_kwh - boiler_charge_kwh)
        if geothermal_dispatch is not None:
            source_inputs["district_geothermal"]["thermal_spillage_kwh"] = float(geothermal_spillage_kwh)
        if solar_thermal_dispatch is not None:
            source_inputs["district_solar_thermal"]["thermal_kwh"] = float(
                solar_thermal_direct_kwh + solar_thermal_preheat_kwh + solar_thermal_charge_kwh
            )
            source_inputs["district_solar_thermal"]["storage_charge_kwh"] = float(solar_thermal_charge_kwh)
            source_inputs["district_solar_thermal"]["thermal_spillage_kwh"] = float(solar_thermal_spillage_kwh)
        if external_heat_dispatch is not None:
            source_inputs["district_external_heat"]["thermal_spillage_kwh"] = float(external_heat_spillage_kwh)
        if waste_dispatch is not None:
            source_inputs["district_waste_incineration"]["thermal_spillage_kwh"] = float(waste_spillage_kwh)
        if biomass_chp_dispatch is not None:
            source_inputs["district_biomass_chp"]["thermal_spillage_kwh"] = float(biomass_chp_spillage_kwh)
        if biogas_chp_dispatch is not None:
            source_inputs["district_biogas_chp"]["thermal_spillage_kwh"] = float(biogas_chp_spillage_kwh)
        if gas_chp_dispatch is not None:
            source_inputs["district_gas_chp"]["thermal_spillage_kwh"] = float(gas_chp_spillage_kwh)
        if gas_boiler_dispatch is not None:
            source_inputs["district_gas_boiler"]["thermal_spillage_kwh"] = float(gas_boiler_spillage_kwh)
        if boiler_dispatch is not None:
            source_inputs["district_wood_chip_boiler"]["thermal_spillage_kwh"] = float(boiler_spillage_kwh)
        if hp_dispatch is not None:
            source_inputs["district_heat_pump"]["thermal_kwh"] = float(hp_dispatch["thermal_kwh"] + hp_charge_kwh)
            source_inputs["district_heat_pump"]["electric_kwh"] = float(source_inputs["district_heat_pump"]["thermal_kwh"] / hp_dispatch["cop"])
    else:
        geothermal_spillage_kwh = geothermal_excess_charge_kwh
        solar_thermal_spillage_kwh = solar_thermal_excess_charge_kwh
        external_heat_spillage_kwh = external_heat_excess_charge_kwh
        waste_spillage_kwh = waste_excess_charge_kwh
        biomass_chp_spillage_kwh = biomass_chp_excess_charge_kwh
        biogas_chp_spillage_kwh = biogas_chp_excess_charge_kwh
        gas_chp_spillage_kwh = gas_chp_excess_charge_kwh
        gas_boiler_spillage_kwh = gas_boiler_excess_charge_kwh
        boiler_spillage_kwh = boiler_excess_charge_kwh
        if geothermal_dispatch is not None:
            source_inputs["district_geothermal"]["thermal_spillage_kwh"] = float(geothermal_spillage_kwh)
        if solar_thermal_dispatch is not None:
            source_inputs["district_solar_thermal"]["storage_charge_kwh"] = 0.0
            source_inputs["district_solar_thermal"]["thermal_spillage_kwh"] = float(solar_thermal_spillage_kwh)
        if external_heat_dispatch is not None:
            source_inputs["district_external_heat"]["thermal_spillage_kwh"] = float(external_heat_spillage_kwh)
        if waste_dispatch is not None:
            source_inputs["district_waste_incineration"]["thermal_spillage_kwh"] = float(waste_spillage_kwh)
        if biomass_chp_dispatch is not None:
            source_inputs["district_biomass_chp"]["thermal_spillage_kwh"] = float(biomass_chp_spillage_kwh)
        if biogas_chp_dispatch is not None:
            source_inputs["district_biogas_chp"]["thermal_spillage_kwh"] = float(biogas_chp_spillage_kwh)
        if gas_chp_dispatch is not None:
            source_inputs["district_gas_chp"]["thermal_spillage_kwh"] = float(gas_chp_spillage_kwh)
        if gas_boiler_dispatch is not None:
            source_inputs["district_gas_boiler"]["thermal_spillage_kwh"] = float(gas_boiler_spillage_kwh)
        if boiler_dispatch is not None:
            source_inputs["district_wood_chip_boiler"]["thermal_spillage_kwh"] = float(boiler_spillage_kwh)

    supply_total = 0.0
    electricity_load = 0.0
    electricity_generation = 0.0
    for source_name in dh_context["source_names"]:
        payload = source_inputs.get(source_name, {"thermal_kwh": 0.0})
        supply_total += float(payload.get("thermal_kwh", 0.0))
        electricity_load += float(payload.get("electric_kwh", 0.0))
        electricity_generation += float(payload.get("electric_generation_kwh", 0.0))
        supply_block = dh_context["bus"]["supply"][source_name]
        for key, value in payload.items():
            if key not in supply_block:
                supply_block[key] = np.zeros_like(dh_context["bus"]["demand"]["total"], dtype=float)
            supply_block[key][t] = float(value)

    delivered_total = 0.0
    delivered_space_total = 0.0
    delivered_hotwater_total = 0.0
    delivered_target_total = min(
        total_demand,
        total_demand - max(0.0, requested_discharge_kwh - float(storage_step["discharge_kwh"])),
    )
    delivery_factor = min(1.0, delivered_target_total / total_demand) if total_demand > 1e-9 else 0.0
    for building_key in known_keys:
        delivered_space = float(step_space[building_key] * delivery_factor)
        delivered_hotwater = float(step_hotwater[building_key] * delivery_factor)
        delivered = delivered_space + delivered_hotwater
        dh_context["bus"]["delivery"]["space_heat_by_type"][building_key][t] = delivered_space
        dh_context["bus"]["delivery"]["hotwater_by_type"][building_key][t] = delivered_hotwater
        dh_context["bus"]["delivery"]["total_by_type"][building_key][t] = delivered
        delivered_space_total += delivered_space
        delivered_hotwater_total += delivered_hotwater
        delivered_total += delivered

    dh_context["bus"]["delivery"]["space_heat_total"][t] = delivered_space_total
    dh_context["bus"]["delivery"]["hotwater_total"][t] = delivered_hotwater_total
    dh_context["bus"]["delivery"]["total"][t] = delivered_total
    result = {
        "total_demand_kwh": total_demand,
        "delivered_kwh": delivered_total,
        "unserved_kwh": max(0.0, total_demand - delivered_total),
        "electric_generation_kwh": electricity_generation,
    }, electricity_load, float(storage_step["soc_kwh"]), electricity_generation


def simulate_integrated_energy_system(params: Dict[str, Any], profiles: Dict[str, Any], pv_size: float) -> Dict[str, Any]:
    eng = params.get("engine_config", None)
    features = getattr(eng, "features", None) if eng is not None else None
    enable_bess = bool(getattr(features, "enable_bess", True))
    enable_v2h = bool(getattr(features, "enable_v2h", True))
    enable_h2 = bool(getattr(features, "enable_h2", False))
    enable_thermflex = bool(getattr(features, "enable_thermflex", False))
    enable_small_wind = bool(getattr(features, "enable_small_wind", False))
    enable_large_wind = bool(getattr(features, "enable_large_wind", False))
    enable_biogas_engine = bool(getattr(features, "enable_biogas_engine", False))
    enable_wood_gasifier = bool(getattr(features, "enable_wood_gasifier", False))

    settings_obj = params.get("settings_obj", None)
    load_member_2d = np.asarray(profiles["load_member_2d"], dtype=float)
    space_heat_member_2d = np.asarray(_require_profile(profiles, "space_heat_member_2d"), dtype=float)
    hp_elec_heat_member_2d = np.asarray(_require_profile(profiles, "hp_elec_heat_member_2d"), dtype=float)
    hp_elec_cool_member_2d = np.asarray(_require_profile(profiles, "hp_elec_cool_member_2d"), dtype=float)
    hotwater_member_2d = np.asarray(_require_profile(profiles, "hotwater_member_2d"), dtype=float)
    t_out = np.asarray(_require_profile(profiles, "T_outdoor"), dtype=float)
    t_out_c = _to_celsius_if_kelvin(t_out)
    thermal_cfg = _require_attr(settings_obj, "thermal")
    t_out_building = smooth_effective_outdoor_temperature(
        t_out,
        float(getattr(thermal_cfg, "outdoor_smoothing_hours", 24.0)),
    )
    solar = np.asarray(_require_profile(profiles, "solargains"), dtype=float)
    irradiance = np.asarray(_require_profile(profiles, "irradiance"), dtype=float)
    solar_member_2d = profiles.get("space_heat_solar_member_2d")
    if solar_member_2d is not None:
        solar_member_2d = np.asarray(solar_member_2d, dtype=float)
        if solar_member_2d.shape != space_heat_member_2d.shape:
            raise ValueError(
                "[integrated_energy_system] space_heat_solar_member_2d must match space_heat_member_2d shape."
            )
    usage = profiles["usage_profile"]
    availability = np.asarray(_require_profile(profiles, "availability_profile"), dtype=float)
    driving = np.asarray(_require_profile(profiles, "driving_profile"), dtype=float)
    min_soc_profile = np.asarray(_require_profile(profiles, "min_SOC"), dtype=float)

    n_steps, n_members = load_member_2d.shape
    dt_h = 1.0
    timestamps = profiles.get("timestamps", pd.date_range("2023-01-01", periods=n_steps, freq="h"))

    if enable_small_wind or enable_large_wind:
        wind_speed_ms = _align_1d_length(_require_profile(profiles, "wind_speed_ms"), n_steps)
        wind_pressure_hpa = _align_1d_length(_require_profile(profiles, "wind_pressure_hpa"), n_steps)
    else:
        wind_speed_ms = np.zeros(n_steps, dtype=float)
        wind_pressure_hpa = np.zeros(n_steps, dtype=float)

    dispatch_cfg = _require_attr(settings_obj, "dispatch")
    dispatch_mode = str(getattr(dispatch_cfg, "mode", "heuristic") or "heuristic").strip().lower()
    use_coupled_dispatch = dispatch_mode in {"milp_day_ahead", "milp_two_stage"}
    district_gas_chp_cfg_guard = _require_attr(settings_obj, "district_gas_chp")
    district_gas_chp_mode_guard = str(
        getattr(district_gas_chp_cfg_guard, "operating_mode_model", "fixed_ratio") or "fixed_ratio"
    ).strip().lower()
    if district_gas_chp_mode_guard == "piecewise_power_heat_v1" and dispatch_mode != "milp_day_ahead":
        raise ValueError(
            "[integrated_energy_system] district_gas_chp.operating_mode_model='piecewise_power_heat_v1' "
            "is currently supported only with dispatch.mode='milp_day_ahead'."
        )
    members_cfg = _require_attr(_require_attr(settings_obj, "engine"), "members")
    member_keys = _build_member_keys(members_cfg, n_members)
    dh_context = _build_dh_context(settings_obj, profiles, members_cfg, n_members)
    dh_share_vector = (
        np.asarray(dh_context["member_share_vector"], dtype=float)
        if dh_context is not None
        else np.zeros(n_members, dtype=float)
    )

    thermal_states: List[ThermalBuildingState] = []
    for member in members_cfg.members:
        building = get_runtime_building_params(member, settings_obj=settings_obj)
        for _ in range(_member_count(member)):
            thermal_states.append(
                ThermalBuildingState(
                    ti_k=float(building["T_min"]),
                    c_th_wh_per_k=max(1.0, float(building["heat_capacity"])),
                    ua_w_per_k=_u_a(building),
                    a_floor_m2=float(building["A_floor"]),
                    t_min_k=float(building["T_min"]),
                    t_max_k=float(building["T_max"]),
                    dt_h=dt_h,
                )
            )

    hp = _require_block(params, "heatpump")
    cop_heat_series, cop_cool_series = resolve_household_heatpump_cop_series(
        heatpump=hp,
        t_outdoor_k=t_out,
    )
    delta_t = float(_require_attr(_require_attr(settings_obj, "thermal"), "delta_T"))

    ev_cfg = _require_block(params, "EV")
    v2h_cfg = _require_attr(settings_obj, "v2h")
    n_ev = int(ev_cfg["N_EV_total"])
    n_ev_bidir = int(ev_cfg["N_EV_bidirectional"])
    ev_cap = float(ev_cfg["capacity_kWh"])
    ev_eta_ch = float(ev_cfg["charging_efficiency"])
    ev_eta_dis = float(ev_cfg["discharging_efficiency"])
    ev_p_max = float(ev_cfg["max_charge_power"]) * dt_h
    ev_p_dis_max = float(ev_cfg["max_discharge_power"]) * dt_h
    ev_reserve_lookahead_h = int(_require_attr(v2h_cfg, "reserve_lookahead_h"))
    ev_reserve_factor = float(_require_attr(v2h_cfg, "reserve_factor"))
    import_sensitive_dispatch = bool(_require_attr(v2h_cfg, "import_sensitive_dispatch"))
    ev_soc = np.zeros((n_steps, n_ev), dtype=float)
    if n_ev > 0:
        ev_soc[0, :] = ev_cap * float(ev_cfg["initial_soc"])
    rng = np.random.default_rng(int(params.get("rng_seed", 0)))

    bess_cap = float(params.get("battery_capacity_kWh", 0.0)) if enable_bess else 0.0
    bess_cfg = _require_attr(settings_obj, "bess")
    bess_soc = np.zeros(n_steps, dtype=float)
    bess_soc[0] = min(1.0, max(0.0, float(_require_attr(bess_cfg, "initial_soc")))) * bess_cap if enable_bess else 0.0
    bess_block = _require_block(params, "BESS")
    bess_p_cap = float(bess_block["power_kW"]) * float(max(1, n_members)) * dt_h if enable_bess else 0.0
    bess_eta = float(bess_block["efficiency"]) if enable_bess else 1.0

    h2 = HydrogenSystem(
        p_ely_max_kw=float(params.get("ely_kw", 0.0) if enable_h2 else 0.0),
        e_h2_max_kwh=float(params.get("h2_tank_kwh", 0.0) if enable_h2 else 0.0),
        p_fc_max_kw=float(params.get("fc_kw", 0.0) if enable_h2 else 0.0),
        eta_ely=float(_require_block(params, "ELY")["eta_ely"]),
        eta_fc=float(_require_block(params, "FC")["eta_fc"]),
        soc_kwh=0.0,
        dt_h=dt_h,
    )
    h2_soc = np.zeros(n_steps, dtype=float)
    h2_soc[0] = h2.soc_kwh

    pv_gen = (np.asarray(profiles["pv_generation"], dtype=float) / 1000.0) * float(max(0.0, pv_size)) * dt_h
    small_wind_kw = float(params.get("small_wind_kw", 0.0)) if enable_small_wind else 0.0
    large_wind_kw = float(params.get("large_wind_kw", 0.0)) if enable_large_wind else 0.0
    biogas_kw = float(params.get("biogas_engine_kw", 0.0)) if enable_biogas_engine else 0.0
    wood_gasifier_kw = float(params.get("wood_gasifier_kw", 0.0)) if enable_wood_gasifier else 0.0
    run_of_river_cfg = getattr(settings_obj, "run_of_river_hydro", None)
    enable_run_of_river_hydro = bool(getattr(run_of_river_cfg, "enabled", False))
    if enable_run_of_river_hydro:
        if str(getattr(settings_obj.engine, "location", "")).strip().lower() != "vienna":
            raise ValueError("[integrated_energy_system] run_of_river_hydro is only configured for Vienna.")
        run_of_river_flow_proxy = load_freudenau_hourly_flow_proxy_context(timestamps)
        run_of_river_hydro_gen = simulate_run_of_river_hydro_generation(
            timestamps=timestamps,
            hourly_flow_proxy=run_of_river_flow_proxy,
            installed_kw=VIENNA_RUN_OF_RIVER_INSTALLED_KW,
            annual_generation_gwh=VIENNA_RUN_OF_RIVER_ANNUAL_GENERATION_GWH,
            dt_h=dt_h,
        )
    else:
        run_of_river_hydro_gen = np.zeros(n_steps, dtype=float)

    small_wind_gen = simulate_small_wind_generation(
        installed_kw=small_wind_kw,
        wind_speed_ms=wind_speed_ms,
        reference_height_m=float(_require_attr(getattr(settings_obj, "small_wind", None), "reference_measurement_height_m")),
        hub_height_m=float(_require_attr(getattr(settings_obj, "small_wind", None), "hub_height_m")),
        shear_exponent=float(_require_attr(getattr(settings_obj, "small_wind", None), "shear_exponent")),
        cut_in_ms=float(_require_attr(getattr(settings_obj, "small_wind", None), "cut_in_ms")),
        rated_ms=float(_require_attr(getattr(settings_obj, "small_wind", None), "rated_ms")),
        cut_out_ms=float(_require_attr(getattr(settings_obj, "small_wind", None), "cut_out_ms")),
        temperature_c=t_out,
        pressure_hpa=wind_pressure_hpa,
        reference_air_density_kg_per_m3=float(_require_attr(getattr(settings_obj, "small_wind", None), "reference_air_density_kg_per_m3")),
        dt_h=dt_h,
    ) if enable_small_wind else np.zeros(n_steps, dtype=float)
    large_wind_gen = simulate_large_wind_generation(
        installed_kw=large_wind_kw,
        wind_speed_ms=wind_speed_ms,
        reference_height_m=float(_require_attr(getattr(settings_obj, "large_wind", None), "reference_measurement_height_m")),
        hub_height_m=float(_require_attr(getattr(settings_obj, "large_wind", None), "hub_height_m")),
        shear_exponent=float(_require_attr(getattr(settings_obj, "large_wind", None), "shear_exponent")),
        cut_in_ms=float(_require_attr(getattr(settings_obj, "large_wind", None), "cut_in_ms")),
        rated_ms=float(_require_attr(getattr(settings_obj, "large_wind", None), "rated_ms")),
        cut_out_ms=float(_require_attr(getattr(settings_obj, "large_wind", None), "cut_out_ms")),
        temperature_c=t_out,
        pressure_hpa=wind_pressure_hpa,
        reference_air_density_kg_per_m3=float(_require_attr(getattr(settings_obj, "large_wind", None), "reference_air_density_kg_per_m3")),
        dt_h=dt_h,
    ) if enable_large_wind else np.zeros(n_steps, dtype=float)

    grid_import = np.zeros(n_steps, dtype=float)
    grid_export = np.zeros(n_steps, dtype=float)
    bess_ch = np.zeros(n_steps, dtype=float)
    bess_dis = np.zeros(n_steps, dtype=float)
    ev_charge_ac = np.zeros(n_steps, dtype=float)
    ev_charge_from_pv = np.zeros(n_steps, dtype=float)
    ev_charge_from_bess = np.zeros(n_steps, dtype=float)
    ev_charge_from_local = np.zeros(n_steps, dtype=float)
    ev_charge_from_grid = np.zeros(n_steps, dtype=float)
    mandatory_ev_charge_ac = np.zeros(n_steps, dtype=float)
    ev_dis_ac = np.zeros((n_steps, n_ev), dtype=float)
    base_load = np.zeros(n_steps, dtype=float)
    total_load = np.zeros(n_steps, dtype=float)
    household_load = load_member_2d.sum(axis=1)
    hp_base_elec = np.zeros(n_steps, dtype=float)
    hp_flex_elec = np.zeros(n_steps, dtype=float)
    local_hp_heat_elec = np.zeros(n_steps, dtype=float)
    local_hp_cool_elec = np.zeros(n_steps, dtype=float)
    hotwater_load = np.zeros(n_steps, dtype=float)
    h2_charge_elec = np.zeros(n_steps, dtype=float)
    h2_discharge_elec = np.zeros(n_steps, dtype=float)
    biogas_generation = np.zeros(n_steps, dtype=float)
    wood_gasifier_generation = np.zeros(n_steps, dtype=float)
    wood_gasifier_fuel_input_kwh = np.zeros(n_steps, dtype=float)
    wood_gasifier_fuel_input_kg = np.zeros(n_steps, dtype=float)
    h2_used_kwh = np.zeros(n_steps, dtype=float)
    v2h_allowed = np.zeros(n_steps, dtype=float)
    v2h_used = np.zeros(n_steps, dtype=float)
    v2h_avoided_import = np.zeros(n_steps, dtype=float)
    district_heat_pump_generation = np.zeros(n_steps, dtype=float)
    district_heat_pump_electricity = np.zeros(n_steps, dtype=float)
    district_heat_pump_cop = np.zeros(n_steps, dtype=float)
    pv_spillage = np.zeros(n_steps, dtype=float)
    small_wind_spillage = np.zeros(n_steps, dtype=float)
    large_wind_spillage = np.zeros(n_steps, dtype=float)
    run_of_river_hydro_spillage = np.zeros(n_steps, dtype=float)
    district_geothermal_electric_generation = np.zeros(n_steps, dtype=float)
    district_geothermal_electric_spillage = np.zeros(n_steps, dtype=float)
    district_geothermal_thermal_generation = np.zeros(n_steps, dtype=float)
    district_geothermal_thermal_spillage = np.zeros(n_steps, dtype=float)
    district_solar_thermal_available_thermal = np.zeros(n_steps, dtype=float)
    district_solar_thermal_direct_available_thermal = np.zeros(n_steps, dtype=float)
    district_solar_thermal_total_useful_available_thermal = np.zeros(n_steps, dtype=float)
    district_solar_thermal_generation = np.zeros(n_steps, dtype=float)
    district_solar_thermal_direct_feed = np.zeros(n_steps, dtype=float)
    district_solar_thermal_preheat = np.zeros(n_steps, dtype=float)
    district_solar_thermal_storage_charge = np.zeros(n_steps, dtype=float)
    district_solar_thermal_thermal_spillage = np.zeros(n_steps, dtype=float)
    district_external_heat_available_thermal = np.zeros(n_steps, dtype=float)
    district_external_heat_generation = np.zeros(n_steps, dtype=float)
    district_external_heat_thermal_spillage = np.zeros(n_steps, dtype=float)
    district_waste_incineration_available_thermal = np.zeros(n_steps, dtype=float)
    district_waste_incineration_generation = np.zeros(n_steps, dtype=float)
    district_waste_incineration_thermal_spillage = np.zeros(n_steps, dtype=float)
    district_biomass_chp_available_thermal = np.zeros(n_steps, dtype=float)
    district_biomass_chp_available_electric = np.zeros(n_steps, dtype=float)
    district_biomass_chp_electric_generation = np.zeros(n_steps, dtype=float)
    district_biomass_chp_thermal_generation = np.zeros(n_steps, dtype=float)
    district_biomass_chp_thermal_spillage = np.zeros(n_steps, dtype=float)
    district_biomass_chp_fuel_input_kwh = np.zeros(n_steps, dtype=float)
    district_biomass_chp_fuel_input_kg = np.zeros(n_steps, dtype=float)
    district_biogas_chp_available_thermal = np.zeros(n_steps, dtype=float)
    district_biogas_chp_available_electric = np.zeros(n_steps, dtype=float)
    district_biogas_chp_electric_generation = np.zeros(n_steps, dtype=float)
    district_biogas_chp_thermal_generation = np.zeros(n_steps, dtype=float)
    district_biogas_chp_thermal_spillage = np.zeros(n_steps, dtype=float)
    district_biogas_chp_fuel_input_kwh = np.zeros(n_steps, dtype=float)
    district_biogas_chp_fuel_input_nm3 = np.zeros(n_steps, dtype=float)
    district_gas_chp_available_thermal = np.zeros(n_steps, dtype=float)
    district_gas_chp_available_electric = np.zeros(n_steps, dtype=float)
    district_gas_chp_electric_generation = np.zeros(n_steps, dtype=float)
    district_gas_chp_thermal_generation = np.zeros(n_steps, dtype=float)
    district_gas_chp_thermal_spillage = np.zeros(n_steps, dtype=float)
    district_gas_chp_fuel_input_kwh = np.zeros(n_steps, dtype=float)
    district_gas_chp_fuel_input_m3 = np.zeros(n_steps, dtype=float)
    # This sidecar export is only populated when the new piecewise CHP mode is
    # explicitly active. Keeping it optional avoids changing the legacy result
    # schema while still preserving the per-hour CHP mode mix for debugging and
    # later paper analysis.
    district_gas_chp_mode_share: np.ndarray | None = None
    district_gas_chp_mode_names: List[str] = []
    district_gas_boiler_available_thermal = np.zeros(n_steps, dtype=float)
    district_gas_boiler_generation = np.zeros(n_steps, dtype=float)
    district_gas_boiler_thermal_spillage = np.zeros(n_steps, dtype=float)
    district_gas_boiler_fuel_input_kwh = np.zeros(n_steps, dtype=float)
    district_gas_boiler_fuel_input_m3 = np.zeros(n_steps, dtype=float)
    district_wood_chip_boiler_available_thermal = np.zeros(n_steps, dtype=float)
    district_wood_chip_boiler_generation = np.zeros(n_steps, dtype=float)
    district_wood_chip_boiler_fuel_input_kwh = np.zeros(n_steps, dtype=float)
    district_wood_chip_boiler_fuel_input_kg = np.zeros(n_steps, dtype=float)
    district_thermal_storage_charge = np.zeros(n_steps, dtype=float)
    district_thermal_storage_discharge = np.zeros(n_steps, dtype=float)
    district_thermal_storage_losses = np.zeros(n_steps, dtype=float)
    district_thermal_storage_soc = np.zeros(n_steps, dtype=float)
    district_space_heat_demand = np.zeros(n_steps, dtype=float)
    district_space_heat_demand_ref = np.zeros(n_steps, dtype=float)
    district_hotwater_demand = np.zeros(n_steps, dtype=float)
    dh_total_demand = np.zeros(n_steps, dtype=float)
    dh_total_delivered = np.zeros(n_steps, dtype=float)
    dh_unserved_heat = np.zeros(n_steps, dtype=float)
    unserved_el = np.zeros(n_steps, dtype=float)
    dispatch_diagnostics: Dict[str, Any] = {"mode": dispatch_mode}
    district_geothermal_available_electric = np.zeros(n_steps, dtype=float)
    district_geothermal_available_thermal = np.zeros(n_steps, dtype=float)

    if use_coupled_dispatch:
        unsupported_features = []
        if enable_v2h:
            unsupported_features.append("enable_v2h")
        if enable_biogas_engine:
            unsupported_features.append("enable_biogas_engine")
        if enable_wood_gasifier:
            unsupported_features.append("enable_wood_gasifier")
        if unsupported_features:
            raise NotImplementedError(
                "[integrated_energy_system] dispatch MILP path does not yet support these feature toggles: "
                f"{unsupported_features}"
            )

    biogas_cfg = getattr(settings_obj, "biogas_engine", None)
    wood_cfg = getattr(settings_obj, "wood_gasifier", None)
    wood_params = _require_block(params, "WOOD_GASIFIER") if enable_wood_gasifier else {}
    district_biomass_chp_cfg = getattr(settings_obj, "district_biomass_chp", None)
    district_biogas_chp_cfg = getattr(settings_obj, "district_biogas_chp", None)
    district_external_heat_cfg = getattr(settings_obj, "district_external_heat", None)
    district_gas_boiler_cfg = getattr(settings_obj, "district_gas_boiler", None)
    district_gas_chp_cfg = getattr(settings_obj, "district_gas_chp", None)
    district_solar_thermal_cfg = getattr(settings_obj, "district_solar_thermal", None)
    district_waste_incineration_cfg = getattr(settings_obj, "district_waste_incineration", None)
    district_wood_chip_boiler_cfg = getattr(settings_obj, "district_wood_chip_boiler", None)
    storage_cfg = getattr(settings_obj, "district_thermal_storage", None)
    storage_enabled = bool(getattr(_require_attr(settings_obj, "technology_activation"), "district_thermal_storage", False))
    installed_storage_kwh = float(params.get("district_thermal_storage_kwh_th", 0.0))
    storage_soc_kwh = (
        initialize_district_thermal_storage_soc(installed_storage_kwh, storage_cfg)
        if storage_enabled and installed_storage_kwh > 0.0
        else 0.0
    )
    district_solar_thermal_precomputed = None
    if dh_context is not None and "district_solar_thermal" in dh_context["source_names"]:
        dh_cfg = _require_attr(settings_obj, "district_heating")
        solar_supply_curve = np.zeros(n_steps, dtype=float)
        solar_return_curve = np.zeros(n_steps, dtype=float)
        solar_required_direct = np.zeros(n_steps, dtype=float)
        solar_required_preheat = np.zeros(n_steps, dtype=float)
        for i in range(n_steps):
            solar_supply_curve[i], solar_return_curve[i] = get_dh_bus_temperatures(float(t_out_c[i]), dh_cfg)
            solar_required_direct[i] = get_required_source_supply_temp_c(float(t_out_c[i]), dh_cfg)
            solar_required_preheat[i] = get_required_preheat_source_temp_c(float(t_out_c[i]), dh_cfg)
        district_solar_thermal_precomputed = precompute_district_solar_thermal_series(
            installed_kw_th=_require_nonnegative_param(params, "district_solar_thermal_kw_th"),
            timestamps=timestamps,
            ghi_w_per_m2=irradiance,
            ambient_temp_c=t_out_c,
            network_supply_temp_c=solar_supply_curve,
            network_return_temp_c=solar_return_curve,
            required_direct_supply_temp_c=solar_required_direct,
            required_preheat_supply_temp_c=solar_required_preheat,
            config=district_solar_thermal_cfg,
            dt_h=1.0,
        )
        dh_context["bus"]["meta"]["district_solar_thermal_precomputed"] = district_solar_thermal_precomputed
        district_solar_thermal_available_thermal[:] = np.asarray(
            district_solar_thermal_precomputed["thermal_capacity_kwh"],
            dtype=float,
        )
        district_solar_thermal_direct_available_thermal[:] = np.asarray(
            district_solar_thermal_precomputed["direct_feed_capacity_kwh"],
            dtype=float,
        )
        district_solar_thermal_total_useful_available_thermal[:] = np.asarray(
            district_solar_thermal_precomputed["preheat_capacity_kwh"],
            dtype=float,
        )
    if n_steps > 0:
        district_thermal_storage_soc[0] = storage_soc_kwh

    thermflex_dispatch_inputs: list[dict[str, Any]] = []
    thermflex_member_ids: list[str] = []
    thermflex_member_building_keys: list[str] = []
    thermflex_member_archetype_keys: list[str] = []
    thermflex_member_floor_area_m2: list[float] = []
    thermflex_member_stock_scale: list[float] = []
    thermflex_t_in_prev_c: np.ndarray | None = None
    if use_coupled_dispatch and enable_thermflex:
        member_col = 0
        for member in members_cfg.members:
            repeats = _member_count(member)
            for _ in range(repeats):
                share = float(dh_share_vector[member_col])
                if share > 1e-9:
                    if solar_member_2d is None:
                        raise ValueError(
                            "[integrated_energy_system] Coupled thermflex with cohort members requires "
                            "profiles['space_heat_solar_member_2d'] from precompute."
                        )
                    member_input = build_member_thermflex_linear_inputs(
                        member,
                        settings_obj=settings_obj,
                        timestamps=timestamps,
                        t_outdoor_k=t_out,
                        solar_gains_w_m2=solar_member_2d[:, member_col],
                        usage_df=usage,
                        q_heat_ref_kwh=space_heat_member_2d[:, member_col],
                        stock_scale=share,
                    )
                    thermflex_dispatch_inputs.append(member_input)
                    thermflex_member_ids.append(str(member_input["member_id"]))
                    thermflex_member_building_keys.append(str(getattr(member, "building_key", "")))
                    thermflex_member_archetype_keys.append(str(member_input["thermal_archetype_key"]))
                    thermflex_member_floor_area_m2.append(float(member_input["a_floor_m2"]))
                    thermflex_member_stock_scale.append(float(member_input["stock_scale"]))
                member_col += 1
        if member_col != n_members:
            raise ValueError("[integrated_energy_system] Thermflex dispatch input build did not consume all members.")
        if thermflex_dispatch_inputs:
            thermflex_t_in_prev_c = np.array(
                [float(inp["initial_t_in_c"]) for inp in thermflex_dispatch_inputs],
                dtype=float,
            )

    thermflex_member_q_heat = None
    thermflex_member_q_heat_ref = None
    thermflex_member_flex_active = None
    thermflex_member_event_start = None
    thermflex_member_temp_violation = None
    thermflex_member_t_in = None
    thermflex_member_event_preheat_extra = None
    thermflex_member_event_cutback_shed = None
    if use_coupled_dispatch and enable_thermflex and thermflex_dispatch_inputs:
        n_thermflex_members = len(thermflex_dispatch_inputs)
        thermflex_member_q_heat = np.zeros((n_thermflex_members, n_steps), dtype=float)
        thermflex_member_q_heat_ref = np.zeros((n_thermflex_members, n_steps), dtype=float)
        thermflex_member_flex_active = np.zeros((n_thermflex_members, n_steps), dtype=float)
        thermflex_member_event_start = np.zeros((n_thermflex_members, n_steps), dtype=float)
        thermflex_member_temp_violation = np.zeros((n_thermflex_members, n_steps), dtype=float)
        thermflex_member_t_in = np.zeros((n_thermflex_members, n_steps), dtype=float)
        thermflex_member_event_preheat_extra = np.zeros((n_thermflex_members, n_steps), dtype=float)
        thermflex_member_event_cutback_shed = np.zeros((n_thermflex_members, n_steps), dtype=float)

    for t in range(n_steps):
        if t > 0:
            bess_soc[t] = bess_soc[t - 1]
            if n_ev > 0:
                ev_soc[t, :] = ev_soc[t - 1, :]
            h2_soc[t] = h2.soc_kwh

        local_share_vector = 1.0 - dh_share_vector
        cop_heat_t = float(cop_heat_series[t])
        cop_cool_t = float(cop_cool_series[t])
        if enable_thermflex and not use_coupled_dispatch:
            heat_member = np.zeros(n_members, dtype=float)
            cool_member = np.zeros(n_members, dtype=float)
            internal_w_m2 = usage["Qi Winter W/m2"].to_numpy(dtype=float)[t] if "Qi Winter W/m2" in usage.columns else 0.0
            for m_idx, st in enumerate(thermal_states):
                st.passive_step(t_out_building[t], internal_w_m2, solar[t])
                heat_member[m_idx], cool_member[m_idx] = st.base_hvac_energy()

            local_heat_member = heat_member * local_share_vector
            dh_space_heat_member = heat_member * dh_share_vector
            local_heat_elec_member = local_heat_member / max(1e-9, cop_heat_t)
            local_cool_elec_member = cool_member / max(1e-9, cop_cool_t)
        else:
            heat_member = np.asarray(space_heat_member_2d[t, :], dtype=float)
            local_heat_member = heat_member * local_share_vector
            dh_space_heat_member = heat_member * dh_share_vector
            local_heat_elec_member = np.asarray(hp_elec_heat_member_2d[t, :], dtype=float) * local_share_vector
            local_cool_elec_member = np.asarray(hp_elec_cool_member_2d[t, :], dtype=float)

        local_hotwater_member = hotwater_member_2d[t, :] * local_share_vector
        dh_hotwater_member = hotwater_member_2d[t, :] * dh_share_vector

        local_hp_heat_elec[t] = float(np.sum(local_heat_elec_member))
        local_hp_cool_elec[t] = float(np.sum(local_cool_elec_member))
        hp_base_elec[t] = local_hp_heat_elec[t] + local_hp_cool_elec[t]
        hotwater_load[t] = float(np.sum(local_hotwater_member))

        if use_coupled_dispatch:
            district_space_heat_demand[t] = float(np.sum(dh_space_heat_member))
            district_space_heat_demand_ref[t] = float(np.sum(dh_space_heat_member))
            district_hotwater_demand[t] = float(np.sum(dh_hotwater_member))
            dh_total_demand[t] = float(district_space_heat_demand[t] + district_hotwater_demand[t])
            if dh_context is not None and "district_geothermal" in dh_context["source_names"]:
                geothermal_dispatch = dispatch_district_geothermal_orc(
                    installed_kw_el=float(params.get("district_geothermal_kw_el", 0.0)),
                    config=_require_attr(settings_obj, "district_geothermal"),
                    timestamp=timestamps[t],
                    dt_h=1.0,
                )
                district_geothermal_available_electric[t] = float(geothermal_dispatch["electric_generation_kwh"])
                district_geothermal_available_thermal[t] = float(geothermal_dispatch["thermal_kwh"])
                district_geothermal_electric_generation[t] = district_geothermal_available_electric[t]
                district_geothermal_thermal_generation[t] = district_geothermal_available_thermal[t]
            if dh_context is not None and "district_solar_thermal" in dh_context["source_names"]:
                if district_solar_thermal_precomputed is None:
                    raise ValueError(
                        "[integrated_energy_system] district_solar_thermal is active, but precomputed solar availability "
                        "is missing."
                    )
                district_solar_thermal_available_thermal[t] = float(
                    np.asarray(district_solar_thermal_precomputed["thermal_capacity_kwh"], dtype=float)[t]
                )
                district_solar_thermal_direct_available_thermal[t] = float(
                    np.asarray(district_solar_thermal_precomputed["direct_feed_capacity_kwh"], dtype=float)[t]
                )
                district_solar_thermal_total_useful_available_thermal[t] = float(
                    np.asarray(district_solar_thermal_precomputed["preheat_capacity_kwh"], dtype=float)[t]
                )
            if dh_context is not None and "district_external_heat" in dh_context["source_names"]:
                external_heat_dispatch = dispatch_district_external_heat(
                    requested_thermal_kwh=1e18,
                    installed_kw_th=_require_nonnegative_param(params, "district_external_heat_kw_th"),
                    config=district_external_heat_cfg,
                    dt_h=1.0,
                )
                district_external_heat_available_thermal[t] = float(external_heat_dispatch["thermal_capacity_kwh"])
            if dh_context is not None and "district_waste_incineration" in dh_context["source_names"]:
                waste_dispatch = dispatch_district_waste_incineration(
                    requested_thermal_kwh=1e18,
                    installed_kw_th=_require_nonnegative_param(params, "district_waste_incineration_kw_th"),
                    config=district_waste_incineration_cfg,
                    dt_h=1.0,
                )
                district_waste_incineration_available_thermal[t] = float(waste_dispatch["thermal_capacity_kwh"])
            if dh_context is not None and "district_biomass_chp" in dh_context["source_names"]:
                biomass_eta_el = _require_float_attr(district_biomass_chp_cfg, "eta_el")
                biomass_eta_th = _require_float_attr(district_biomass_chp_cfg, "eta_th")
                biomass_th_cap = float(params.get("district_biomass_chp_kw_th", 0.0)) * dt_h
                if not _is_scheduled_downtime(timestamps[t], district_biomass_chp_cfg) and biomass_th_cap > 0.0:
                    district_biomass_chp_available_thermal[t] = biomass_th_cap
                    district_biomass_chp_available_electric[t] = biomass_th_cap * (biomass_eta_el / biomass_eta_th)
            if dh_context is not None and "district_biogas_chp" in dh_context["source_names"]:
                biogas_eta_el = _require_float_attr(district_biogas_chp_cfg, "eta_el")
                biogas_eta_th = _require_float_attr(district_biogas_chp_cfg, "eta_th")
                biogas_el_cap = float(params.get("district_biogas_chp_kw_el", 0.0)) * dt_h
                if not _is_scheduled_downtime(timestamps[t], district_biogas_chp_cfg) and biogas_el_cap > 0.0:
                    district_biogas_chp_available_electric[t] = biogas_el_cap
                    district_biogas_chp_available_thermal[t] = biogas_el_cap * (biogas_eta_th / biogas_eta_el)
            if dh_context is not None and "district_gas_chp" in dh_context["source_names"]:
                gas_eta_el = _require_float_attr(district_gas_chp_cfg, "eta_el")
                gas_eta_th = _require_float_attr(district_gas_chp_cfg, "eta_th")
                gas_piecewise_payload = _district_gas_chp_piecewise_payload(district_gas_chp_cfg)
                gas_mode = str(gas_piecewise_payload["operating_mode_model"])
                gas_el_cap = float(params.get("district_gas_chp_kw_el", 0.0)) * dt_h
                if not _is_scheduled_downtime(timestamps[t], district_gas_chp_cfg) and gas_el_cap > 0.0:
                    district_gas_chp_available_electric[t] = gas_el_cap
                    if gas_mode == "piecewise_power_heat_v1":
                        district_gas_chp_available_thermal[t] = (
                            gas_el_cap * float(gas_piecewise_payload["max_thermal_ratio_on_el_base"])
                        )
                    else:
                        district_gas_chp_available_thermal[t] = gas_el_cap * (gas_eta_th / gas_eta_el)
            if dh_context is not None and "district_gas_boiler" in dh_context["source_names"]:
                gas_boiler_th_cap = _require_nonnegative_param(params, "district_gas_boiler_kw_th") * dt_h
                if not _is_scheduled_downtime(timestamps[t], district_gas_boiler_cfg) and gas_boiler_th_cap > 0.0:
                    district_gas_boiler_available_thermal[t] = gas_boiler_th_cap
            if dh_context is not None and "district_wood_chip_boiler" in dh_context["source_names"]:
                wood_boiler_th_cap = float(params.get("district_wood_chip_boiler_kw_th", 0.0)) * dt_h
                if not _is_scheduled_downtime(timestamps[t], district_wood_chip_boiler_cfg) and wood_boiler_th_cap > 0.0:
                    district_wood_chip_boiler_available_thermal[t] = wood_boiler_th_cap
            if dh_context is not None and "district_heat_pump" in dh_context["source_names"]:
                district_heat_pump_cop[t] = float(calculate_constant_dh_heat_pump_cop(_require_attr(settings_obj, "district_heat_pump")))
        else:
            dh_step, dh_el, storage_soc_kwh, _dh_electric_generation_total = _step_district_heating(
                t=t,
                dh_context=dh_context,
                settings_obj=settings_obj,
                params=params,
                member_keys=member_keys,
                space_heat_dh_member=dh_space_heat_member,
                hotwater_dh_member=dh_hotwater_member,
                storage_soc_prev_kwh=storage_soc_kwh,
            )
            dh_total_demand[t] = float(dh_step["total_demand_kwh"])
            dh_total_delivered[t] = float(dh_step["delivered_kwh"])
            dh_unserved_heat[t] = float(dh_step["unserved_kwh"])
            district_heat_pump_electricity[t] = float(dh_el)
            if dh_context is not None and "district_geothermal" in dh_context["bus"]["supply"]:
                district_geothermal_electric_generation[t] = float(
                    dh_context["bus"]["supply"]["district_geothermal"].get("electric_generation_kwh", np.zeros(n_steps))[t]
                )
                district_geothermal_thermal_generation[t] = float(
                    dh_context["bus"]["supply"]["district_geothermal"]["thermal_kwh"][t]
                )
                district_geothermal_thermal_spillage[t] = float(
                    dh_context["bus"]["supply"]["district_geothermal"].get("thermal_spillage_kwh", np.zeros(n_steps))[t]
                )
            if dh_context is not None and "district_solar_thermal" in dh_context["bus"]["supply"]:
                district_solar_thermal_generation[t] = float(
                    dh_context["bus"]["supply"]["district_solar_thermal"].get("thermal_kwh", np.zeros(n_steps))[t]
                )
                district_solar_thermal_direct_feed[t] = float(
                    dh_context["bus"]["supply"]["district_solar_thermal"].get("direct_feed_kwh", np.zeros(n_steps))[t]
                )
                district_solar_thermal_preheat[t] = float(
                    dh_context["bus"]["supply"]["district_solar_thermal"].get("preheat_kwh", np.zeros(n_steps))[t]
                )
                district_solar_thermal_storage_charge[t] = float(
                    dh_context["bus"]["supply"]["district_solar_thermal"].get("storage_charge_kwh", np.zeros(n_steps))[t]
                )
                district_solar_thermal_thermal_spillage[t] = float(
                    dh_context["bus"]["supply"]["district_solar_thermal"].get("thermal_spillage_kwh", np.zeros(n_steps))[t]
                )
            if dh_context is not None and "district_external_heat" in dh_context["bus"]["supply"]:
                district_external_heat_generation[t] = float(
                    dh_context["bus"]["supply"]["district_external_heat"].get("thermal_kwh", np.zeros(n_steps))[t]
                )
                district_external_heat_thermal_spillage[t] = float(
                    dh_context["bus"]["supply"]["district_external_heat"].get("thermal_spillage_kwh", np.zeros(n_steps))[t]
                )
            if dh_context is not None and "district_waste_incineration" in dh_context["bus"]["supply"]:
                district_waste_incineration_generation[t] = float(
                    dh_context["bus"]["supply"]["district_waste_incineration"].get("thermal_kwh", np.zeros(n_steps))[t]
                )
                district_waste_incineration_thermal_spillage[t] = float(
                    dh_context["bus"]["supply"]["district_waste_incineration"].get("thermal_spillage_kwh", np.zeros(n_steps))[t]
                )
            if dh_context is not None and "district_biomass_chp" in dh_context["bus"]["supply"]:
                district_biomass_chp_electric_generation[t] = float(
                    dh_context["bus"]["supply"]["district_biomass_chp"].get("electric_generation_kwh", np.zeros(n_steps))[t]
                )
                district_biomass_chp_thermal_generation[t] = float(
                    dh_context["bus"]["supply"]["district_biomass_chp"]["thermal_kwh"][t]
                )
                district_biomass_chp_thermal_spillage[t] = float(
                    dh_context["bus"]["supply"]["district_biomass_chp"].get("thermal_spillage_kwh", np.zeros(n_steps))[t]
                )
                district_biomass_chp_fuel_input_kwh[t] = float(
                    dh_context["bus"]["supply"]["district_biomass_chp"].get("fuel_input_kwh", np.zeros(n_steps))[t]
                )
                district_biomass_chp_fuel_input_kg[t] = float(
                    dh_context["bus"]["supply"]["district_biomass_chp"].get("fuel_input_kg", np.zeros(n_steps))[t]
                )
            if dh_context is not None and "district_biogas_chp" in dh_context["bus"]["supply"]:
                district_biogas_chp_electric_generation[t] = float(
                    dh_context["bus"]["supply"]["district_biogas_chp"].get("electric_generation_kwh", np.zeros(n_steps))[t]
                )
                district_biogas_chp_thermal_generation[t] = float(
                    dh_context["bus"]["supply"]["district_biogas_chp"]["thermal_kwh"][t]
                )
                district_biogas_chp_thermal_spillage[t] = float(
                    dh_context["bus"]["supply"]["district_biogas_chp"].get("thermal_spillage_kwh", np.zeros(n_steps))[t]
                )
                district_biogas_chp_fuel_input_kwh[t] = float(
                    dh_context["bus"]["supply"]["district_biogas_chp"].get("fuel_input_kwh", np.zeros(n_steps))[t]
                )
                district_biogas_chp_fuel_input_nm3[t] = float(
                    dh_context["bus"]["supply"]["district_biogas_chp"].get("fuel_input_nm3", np.zeros(n_steps))[t]
                )
            if dh_context is not None and "district_gas_chp" in dh_context["bus"]["supply"]:
                district_gas_chp_electric_generation[t] = float(
                    dh_context["bus"]["supply"]["district_gas_chp"].get("electric_generation_kwh", np.zeros(n_steps))[t]
                )
                district_gas_chp_thermal_generation[t] = float(
                    dh_context["bus"]["supply"]["district_gas_chp"]["thermal_kwh"][t]
                )
                district_gas_chp_thermal_spillage[t] = float(
                    dh_context["bus"]["supply"]["district_gas_chp"].get("thermal_spillage_kwh", np.zeros(n_steps))[t]
                )
                district_gas_chp_fuel_input_kwh[t] = float(
                    dh_context["bus"]["supply"]["district_gas_chp"].get("fuel_input_kwh", np.zeros(n_steps))[t]
                )
                district_gas_chp_fuel_input_m3[t] = float(
                    dh_context["bus"]["supply"]["district_gas_chp"].get("fuel_input_m3", np.zeros(n_steps))[t]
                )
            if dh_context is not None and "district_gas_boiler" in dh_context["bus"]["supply"]:
                district_gas_boiler_generation[t] = float(
                    dh_context["bus"]["supply"]["district_gas_boiler"].get("thermal_kwh", np.zeros(n_steps))[t]
                )
                district_gas_boiler_thermal_spillage[t] = float(
                    dh_context["bus"]["supply"]["district_gas_boiler"].get("thermal_spillage_kwh", np.zeros(n_steps))[t]
                )
                district_gas_boiler_fuel_input_kwh[t] = float(
                    dh_context["bus"]["supply"]["district_gas_boiler"].get("fuel_input_kwh", np.zeros(n_steps))[t]
                )
                district_gas_boiler_fuel_input_m3[t] = float(
                    dh_context["bus"]["supply"]["district_gas_boiler"].get("fuel_input_m3", np.zeros(n_steps))[t]
                )
            if dh_context is not None and "district_heat_pump" in dh_context["bus"]["supply"]:
                district_heat_pump_generation[t] = float(dh_context["bus"]["supply"]["district_heat_pump"]["thermal_kwh"][t])
                district_heat_pump_cop[t] = float(dh_context["bus"]["supply"]["district_heat_pump"].get("cop", np.zeros(n_steps))[t])
            if dh_context is not None and "district_wood_chip_boiler" in dh_context["bus"]["supply"]:
                district_wood_chip_boiler_generation[t] = float(
                    dh_context["bus"]["supply"]["district_wood_chip_boiler"]["thermal_kwh"][t]
                )
                district_wood_chip_boiler_fuel_input_kwh[t] = float(
                    dh_context["bus"]["supply"]["district_wood_chip_boiler"].get("fuel_input_kwh", np.zeros(n_steps))[t]
                )
                district_wood_chip_boiler_fuel_input_kg[t] = float(
                    dh_context["bus"]["supply"]["district_wood_chip_boiler"].get("fuel_input_kg", np.zeros(n_steps))[t]
                )
            if dh_context is not None:
                district_thermal_storage_charge[t] = float(dh_context["bus"]["storage"]["charge_kwh"][t])
                district_thermal_storage_discharge[t] = float(dh_context["bus"]["storage"]["discharge_kwh"][t])
                district_thermal_storage_soc[t] = float(dh_context["bus"]["storage"]["soc_kwh"][t])
                if "losses_kwh" in dh_context["bus"]["storage"]:
                    district_thermal_storage_losses[t] = float(dh_context["bus"]["storage"]["losses_kwh"][t])

        base_load_t = float(np.sum(load_member_2d[t, :] + local_hotwater_member + local_heat_elec_member + local_cool_elec_member))
        base_load[t] = base_load_t

        mandatory_ev_charge = 0.0
        opt_ev_charge_cap = np.zeros(n_ev, dtype=float)
        opt_ev_dis_cap = np.zeros(n_ev, dtype=float)
        for i in range(n_ev):
            available = bool(rng.random() <= availability[t])
            if not available:
                ev_soc[t, i] = max(0.0, ev_soc[t, i] - (driving[t] * ev_cap))
                continue
            min_soc = ev_cap * min_soc_profile[t]
            max_soc = ev_cap * float(ev_cfg["max_soc"])
            if ev_soc[t, i] < min_soc:
                need_dc = min_soc - ev_soc[t, i]
                mandatory_ev_charge += need_dc / max(1e-9, ev_eta_ch)
                ev_soc[t, i] += need_dc
            headroom = max(0.0, max_soc - ev_soc[t, i])
            opt_ev_charge_cap[i] = min(headroom / max(1e-9, ev_eta_ch), ev_p_max)
            if enable_v2h and i < n_ev_bidir:
                t_end = min(n_steps, t + max(1, ev_reserve_lookahead_h))
                reserve_dc = ev_reserve_factor * float(np.sum((np.asarray(driving[t:t_end]) * ev_cap) * np.clip(1.0 - np.asarray(availability[t:t_end]), 0.0, 1.0)))
                reserve_dc = min(max(0.0, reserve_dc), max(0.0, max_soc - min_soc))
                discharge_margin_dc = max(0.0, ev_soc[t, i] - (min_soc + reserve_dc))
                opt_ev_dis_cap[i] = min(discharge_margin_dc * ev_eta_dis, ev_p_dis_max)

        demand = base_load_t + mandatory_ev_charge
        if not use_coupled_dispatch:
            demand += dh_el
        mandatory_ev_charge_ac[t] = mandatory_ev_charge
        ev_charge_ac[t] += mandatory_ev_charge
        pv_t = float(pv_gen[t])
        small_wind_t = float(small_wind_gen[t])
        large_wind_t = float(large_wind_gen[t])
        run_of_river_hydro_t = float(run_of_river_hydro_gen[t])
        local_gen_t = (
            pv_t
            + small_wind_t
            + large_wind_t
            + run_of_river_hydro_t
            + district_geothermal_electric_generation[t]
            + district_biomass_chp_electric_generation[t]
            + district_biogas_chp_electric_generation[t]
            + district_gas_chp_electric_generation[t]
        )
        provisional_deficit = max(0.0, demand - local_gen_t)

        if enable_biogas_engine:
            biogas_generation[t] = dispatch_biogas_engine(
                capacity_kw=biogas_kw,
                deficit_kwh=provisional_deficit,
                min_partload=float(_require_attr(biogas_cfg, "min_partload")),
                max_partload=float(_require_attr(biogas_cfg, "max_partload")),
                fixed_output_fraction=float(_require_attr(biogas_cfg, "fixed_output_fraction")),
                dispatch_mode=str(_require_attr(biogas_cfg, "dispatch_mode")),
                dt_h=dt_h,
            )
        if enable_wood_gasifier:
            wood_dispatch = dispatch_wood_gasifier(
                capacity_kw=wood_gasifier_kw,
                deficit_kwh=provisional_deficit,
                min_partload=float(_require_attr(wood_cfg, "min_partload")),
                max_partload=float(_require_attr(wood_cfg, "max_partload")),
                dispatch_mode=str(_require_attr(wood_cfg, "dispatch_mode")),
                eta_el=float(wood_params["eta_el"]),
                fuel_lhv_kwh_per_kg=float(wood_params["fuel_lhv_kwh_per_kg"]),
                dt_h=dt_h,
            )
            wood_gasifier_generation[t] = float(wood_dispatch["electric_output_kwh"])
            wood_gasifier_fuel_input_kwh[t] = float(wood_dispatch["fuel_input_kwh"])
            wood_gasifier_fuel_input_kg[t] = float(wood_dispatch["fuel_input_kg"])

        local_gen_t += biogas_generation[t] + wood_gasifier_generation[t]
        if use_coupled_dispatch:
            total_load[t] = base_load_t + mandatory_ev_charge
            ev_charge_from_grid[t] += mandatory_ev_charge
            h2_soc[t] = h2.soc_kwh
            continue

        surplus = max(0.0, local_gen_t - demand)
        deficit = max(0.0, demand - local_gen_t)
        mandatory_share = mandatory_ev_charge / demand if demand > 1e-9 else 0.0

        therm_cap = 0.0
        therm_mode = "heat"
        if enable_thermflex:
            for m_idx, st in enumerate(thermal_states):
                local_share = float(local_share_vector[m_idx])
                if local_share <= 1e-9:
                    continue
                cap, mode = thermflex_extra_cap_kwh(st, t_out[t], delta_t, cop_heat_t, cop_cool_t)
                therm_cap += cap * local_share
                therm_mode = mode

        bess_charge_cap = min(bess_p_cap, max(0.0, (bess_cap - bess_soc[t]) / max(1e-9, bess_eta)))
        bess_discharge_cap = min(bess_p_cap, max(0.0, bess_soc[t] * bess_eta))
        h2_ely_cap = h2.p_ely_max_kw * dt_h if enable_h2 else 0.0
        h2_fc_cap = min(h2.p_fc_max_kw * dt_h, max(0.0, h2.soc_kwh * h2.eta_fc)) if enable_h2 else 0.0

        if surplus > 0.0:
            ev_charge_from_pv[t] += mandatory_ev_charge
            alloc = _allocate_surplus(surplus, float(np.sum(opt_ev_charge_cap)), therm_cap if enable_thermflex else 0.0, bess_charge_cap if enable_bess else 0.0, h2_ely_cap)
            ev_add = _distribute(alloc["ev_charge"], opt_ev_charge_cap)
            ev_charge_ac[t] += float(np.sum(ev_add))
            ev_charge_from_pv[t] += float(np.sum(ev_add))
            if n_ev > 0:
                ev_soc[t, :] += ev_add * ev_eta_ch
            hp_flex_elec[t] = float(alloc["thermflex"])
            if enable_thermflex and alloc["thermflex"] > 0.0:
                local_weight_sum = max(1e-9, float(np.sum(local_share_vector)))
                for m_idx, st in enumerate(thermal_states):
                    local_share = float(local_share_vector[m_idx])
                    if local_share <= 1e-9:
                        continue
                    per_member = alloc["thermflex"] * local_share / local_weight_sum
                    if therm_mode == "heat":
                        st.ti_k = min(st.t_max_k + delta_t, st.ti_k + (per_member * cop_heat_t * 1000.0) / max(1e-9, st.c_th_wh_per_k))
                    else:
                        st.ti_k = max(st.t_min_k - delta_t, st.ti_k - (per_member * cop_cool_t * 1000.0) / max(1e-9, st.c_th_wh_per_k))
            if enable_bess:
                bch = min(alloc["bess_charge"], bess_charge_cap)
                bess_ch[t] = bch
                bess_soc[t] = min(bess_cap, bess_soc[t] + (bch * bess_eta))
            if enable_h2:
                h2_in, _ = h2.charge(alloc["h2_electrolysis"])
                h2_charge_elec[t] = h2_in
            grid_export[t] = alloc["export"]
        else:
            v2h_cap_total = float(np.sum(opt_ev_dis_cap)) if enable_v2h else 0.0
            v2h_gate_cap = min(v2h_cap_total, max(0.0, deficit - ((bess_discharge_cap if enable_bess else 0.0) + h2_fc_cap))) if import_sensitive_dispatch else v2h_cap_total
            if v2h_gate_cap > 1e-9:
                v2h_allowed[t] = 1.0
            alloc = _allocate_deficit(deficit, v2h_gate_cap, bess_discharge_cap if enable_bess else 0.0, h2_fc_cap)
            v2h_to_def = 0.0
            if enable_v2h and n_ev > 0:
                ev_dis = _distribute(alloc["v2h_discharge"], opt_ev_dis_cap)
                ev_dis_ac[t, :] = ev_dis
                ev_soc[t, :] = np.maximum(0.0, ev_soc[t, :] - (ev_dis / max(1e-9, ev_eta_dis)))
                v2h_to_def = float(np.sum(ev_dis))
                if v2h_to_def > 1e-9:
                    v2h_used[t] = 1.0
            bdis = 0.0
            if enable_bess:
                bdis = min(alloc["bess_discharge"], bess_discharge_cap)
                bess_dis[t] = bdis
                bess_soc[t] = max(0.0, bess_soc[t] - (bdis / max(1e-9, bess_eta)))
            h2_to_def = 0.0
            if enable_h2:
                h2_to_def, h2_used = h2.discharge(alloc["h2_fuel_cell"])
                h2_discharge_elec[t] = h2_to_def
                h2_used_kwh[t] = h2_used
            grid_import[t] = max(0.0, deficit - v2h_to_def - bdis - h2_to_def)
            if v2h_to_def > 1e-9:
                v2h_avoided_import[t] = max(0.0, min(v2h_to_def, max(0.0, deficit - bdis - h2_to_def) - grid_import[t]))
            ev_charge_from_pv[t] += mandatory_share * min(local_gen_t, demand)
            ev_charge_from_grid[t] += mandatory_share * grid_import[t]
            ev_charge_from_bess[t] += mandatory_share * bdis
            ev_charge_from_local[t] += mandatory_share * (v2h_to_def + h2_to_def)

        total_load[t] = base_load_t + ev_charge_ac[t] + hp_flex_elec[t] + dh_el
        h2_soc[t] = h2.soc_kwh

    bess_cyclic_violation_kwh = 0.0
    if enable_bess and bool(_require_attr(bess_cfg, "cyclic_soc")):
        tol = float(_require_attr(bess_cfg, "cyclic_soc_rtol")) * max(1.0, bess_cap)
        bess_cyclic_violation_kwh = max(0.0, abs(bess_soc[-1] - bess_soc[0]) - tol)

    h2_cyclic_violation_kwh = 0.0
    hydrogen_cfg = _require_attr(settings_obj, "hydrogen")
    if enable_h2 and bool(_require_attr(hydrogen_cfg, "cyclic_soc")):
        tol = float(_require_attr(hydrogen_cfg, "cyclic_soc_rtol")) * max(1.0, h2.e_h2_max_kwh)
        h2_cyclic_violation_kwh = max(0.0, abs(h2.soc_kwh) - tol)

    if use_coupled_dispatch:
        grid_import_price, grid_export_price = _resolve_dispatch_prices(settings_obj, params, profiles, n_steps)
        district_gas_chp_power_priority_signal = _district_gas_chp_power_priority_signal(
            district_gas_chp_cfg,
            grid_import_price,
        )
        tech_economics = dict((params.get("economics") or {}).get("technology") or {})
        gas_day_ahead_price_eur_per_mwh = None
        if "district_gas_day_ahead_price_eur_per_mwh_fuel" in profiles:
            gas_day_ahead_price_eur_per_mwh = _fuel_price_series_eur_per_mwh(
                profiles,
                profile_key="district_gas_day_ahead_price_eur_per_mwh_fuel",
                fallback_eur_per_m3=float(
                    ((tech_economics.get("district_gas_boiler") or {}).get("fuel_eur_per_m3", 0.0) or 0.0)
                ),
                lhv_kwh_per_m3=float(getattr(district_gas_boiler_cfg, "fuel_lhv_kwh_per_m3", 10.0) or 10.0),
                n_steps=n_steps,
            )
        elif "district_gas_price_eur_per_mwh_fuel" in profiles:
            gas_day_ahead_price_eur_per_mwh = _fuel_price_series_eur_per_mwh(
                profiles,
                profile_key="district_gas_price_eur_per_mwh_fuel",
                fallback_eur_per_m3=float(
                    ((tech_economics.get("district_gas_boiler") or {}).get("fuel_eur_per_m3", 0.0) or 0.0)
                ),
                lhv_kwh_per_m3=float(getattr(district_gas_boiler_cfg, "fuel_lhv_kwh_per_m3", 10.0) or 10.0),
                n_steps=n_steps,
            )
        else:
            gas_csv_path = str(getattr(dispatch_cfg, "historical_gas_day_ahead_price_csv", "") or getattr(dispatch_cfg, "historical_gas_price_csv", "") or "").strip()
            if gas_csv_path:
                gas_day_ahead_price_eur_per_mwh = _load_daily_price_series_from_csv(
                    gas_csv_path,
                    timestamps=timestamps,
                    value_candidates=("price_eur_per_mwh", "ceghix_eur_per_mwh", "gas_price_eur_per_mwh", "cegh_day_ahead_eur_per_mwh", "price"),
                    error_label="Historical gas day-ahead price",
                )
            else:
                gas_day_ahead_price_eur_per_mwh = _fuel_price_series_eur_per_mwh(
                    profiles,
                    profile_key="district_gas_day_ahead_price_eur_per_mwh_fuel",
                    fallback_eur_per_m3=float(
                        ((tech_economics.get("district_gas_boiler") or {}).get("fuel_eur_per_m3", 0.0) or 0.0)
                    ),
                    lhv_kwh_per_m3=float(getattr(district_gas_boiler_cfg, "fuel_lhv_kwh_per_m3", 10.0) or 10.0),
                    n_steps=n_steps,
                )
        gas_balance_price_eur_per_mwh = None
        if "district_gas_balance_price_eur_per_mwh_fuel" in profiles:
            gas_balance_price_eur_per_mwh = _optional_price_series_eur_per_mwh(
                profiles,
                profile_key="district_gas_balance_price_eur_per_mwh_fuel",
                n_steps=n_steps,
            )
        else:
            gas_balance_csv_path = str(getattr(dispatch_cfg, "historical_gas_balance_price_csv", "") or "").strip()
            if gas_balance_csv_path:
                gas_balance_price_eur_per_mwh = _load_daily_price_series_from_csv(
                    gas_balance_csv_path,
                    timestamps=timestamps,
                    value_candidates=("price_eur_per_mwh", "ceghix_eur_per_mwh", "gas_price_eur_per_mwh", "cegh_day_ahead_eur_per_mwh", "price"),
                    error_label="Historical gas balance price",
                )
        co2_price_eur_per_t = None
        if "co2_price_eur_per_tco2" in profiles:
            co2_price_eur_per_t = _optional_price_series_eur_per_mwh(
                profiles,
                profile_key="co2_price_eur_per_tco2",
                n_steps=n_steps,
            )
        else:
            co2_csv_path = str(getattr(dispatch_cfg, "historical_co2_price_csv", "") or "").strip()
            if co2_csv_path:
                co2_price_eur_per_t = _load_daily_price_series_from_csv(
                    co2_csv_path,
                    timestamps=timestamps,
                    value_candidates=("price_eur_per_tco2", "co2_price_eur_per_tco2", "price"),
                    error_label="Historical CO2 price",
                )
        electric_non_dispatch_demand = base_load + mandatory_ev_charge_ac
        runner = get_dispatch_runner(dispatch_mode)
        horizon_h = max(1, int(getattr(dispatch_cfg, "horizon_h", 24)))
        bess_soc_prev = float(bess_soc[0]) if n_steps > 0 else 0.0
        h2_soc_prev = float(h2_soc[0]) if n_steps > 0 else 0.0
        dh_soc_prev = float(storage_soc_kwh)
        objective_terms_total = {name: 0.0 for name in getattr(dispatch_cfg, "objective_components", [])}
        objective_terms_total["unserved_penalty"] = 0.0
        objective_terms_total["variable_opex"] = 0.0
        biomass_feedstock_used_total_kwh = 0.0
        biogas_feedstock_used_total_kwh = 0.0
        solar_thermal_used_total_kwh = 0.0
        waste_incineration_used_total_kwh = 0.0
        dispatch_days: list[dict[str, Any]] = []
        total_blocks = int(np.ceil(n_steps / horizon_h))

        print(
            "[integrated_energy_system] coupled dispatch start | "
            f"mode={dispatch_mode} | hours={n_steps} | horizon_h={horizon_h} | blocks={total_blocks}",
            flush=True,
        )

        for start in range(0, n_steps, horizon_h):
            stop = min(n_steps, start + horizon_h)
            block_idx = int(start // horizon_h) + 1
            block_t0 = pd.Timestamp.now()
            print(
                "[integrated_energy_system] dispatch block "
                f"{block_idx}/{total_blocks} | start={pd.Timestamp(timestamps[start])} | hours={stop - start}",
                flush=True,
            )
            dispatch_constraints_cfg = getattr(getattr(settings_obj, "constraints", None), "dispatch", None)
            thermflex_constraints_cfg = getattr(getattr(settings_obj, "constraints", None), "thermflex", None)
            thermflex_series: Dict[str, Any] = {}
            thermflex_params: Dict[str, Any] = {}
            thermflex_initial_state: Dict[str, Any] = {}
            if enable_thermflex:
                if thermflex_t_in_prev_c is None or not thermflex_dispatch_inputs:
                    raise ValueError(
                        "[integrated_energy_system] Coupled thermflex dispatch requires prepared thermflex inputs. "
                        f"thermflex_dispatch_inputs={len(thermflex_dispatch_inputs)} | "
                        f"thermflex_t_in_prev_c_is_none={thermflex_t_in_prev_c is None} | "
                        f"dh_share_sum={float(np.sum(dh_share_vector)):.6f} | "
                        f"n_members={int(n_members)}"
                    )
                thermflex_series = {
                    "thermflex_t_ref_c": np.vstack(
                        [np.asarray(inp["t_ref_c"], dtype=float)[start:stop] for inp in thermflex_dispatch_inputs]
                    ),
                    "thermflex_t_outdoor_c": np.vstack(
                        [np.asarray(inp["t_outdoor_c"], dtype=float)[start:stop] for inp in thermflex_dispatch_inputs]
                    ),
                    "thermflex_internal_gains_w_m2": np.vstack(
                        [np.asarray(inp["internal_gains_w_m2"], dtype=float)[start:stop] for inp in thermflex_dispatch_inputs]
                    ),
                    "thermflex_solar_gains_w_m2": np.vstack(
                        [np.asarray(inp["solar_gains_w_m2"], dtype=float)[start:stop] for inp in thermflex_dispatch_inputs]
                    ),
                    "thermflex_q_heat_ref_kwh": np.vstack(
                        [np.asarray(inp["q_heat_ref_kwh"], dtype=float)[start:stop] for inp in thermflex_dispatch_inputs]
                    ),
                    "thermflex_residual_c": np.vstack(
                        [np.asarray(inp["residual_c"], dtype=float)[start:stop] for inp in thermflex_dispatch_inputs]
                    ),
                }
                heating_control_cfg = getattr(settings_obj, "heating_control", None)
                lower_bound_schedule_c = _thermflex_lower_bound_schedule_c(
                    timestamps=timestamps[start:stop],
                    heating_control_cfg=heating_control_cfg,
                    thermflex_constraints_cfg=thermflex_constraints_cfg,
                )
                if lower_bound_schedule_c is not None:
                    thermflex_series["thermflex_t_lower_bound_c"] = np.tile(
                        np.asarray(lower_bound_schedule_c, dtype=float).reshape(1, -1),
                        (len(thermflex_dispatch_inputs), 1),
                    )
                use_event_response_bounds = bool(
                    getattr(thermflex_constraints_cfg, "use_event_response_bounds", False)
                )
                event_bound_payloads: list[Dict[str, float]] = []
                if use_event_response_bounds:
                    event_bound_payloads = [
                        _thermflex_event_bound_payload(
                            input_payload=inp,
                            settings_obj=settings_obj,
                        )
                        for inp in thermflex_dispatch_inputs
                    ]
                comfort_band_k = float(getattr(thermflex_constraints_cfg, "comfort_band_k", getattr(heating_control_cfg, "comfort_band_k", 0.0)) or 0.0)
                reference_deadband_k = float(
                    getattr(
                        thermflex_constraints_cfg,
                        "reference_deadband_k",
                        0.5 * float(getattr(heating_control_cfg, "hysteresis_band_k", 0.0) or 0.0),
                    )
                    or 0.0
                )
                thermflex_params = {
                    "thermflex_enabled": True,
                    "thermflex_member_count": int(len(thermflex_dispatch_inputs)),
                    "thermflex_member_ids": list(thermflex_member_ids),
                    "thermflex_member_building_keys": list(thermflex_member_building_keys),
                    "thermflex_member_archetype_keys": list(thermflex_member_archetype_keys),
                    "thermflex_member_floor_area_m2": np.array(thermflex_member_floor_area_m2, dtype=float),
                    "thermflex_member_stock_scale": np.array(thermflex_member_stock_scale, dtype=float),
                    "thermflex_alpha": np.array([float(inp["alpha"]) for inp in thermflex_dispatch_inputs], dtype=float),
                    "thermflex_beta_out": np.array([float(inp["beta_out"]) for inp in thermflex_dispatch_inputs], dtype=float),
                    "thermflex_gamma_internal": np.array(
                        [float(inp["gamma_internal"]) for inp in thermflex_dispatch_inputs], dtype=float
                    ),
                    "thermflex_gamma_solar": np.array(
                        [float(inp["gamma_solar"]) for inp in thermflex_dispatch_inputs], dtype=float
                    ),
                    "thermflex_gamma_heat": np.array([float(inp["gamma_heat"]) for inp in thermflex_dispatch_inputs], dtype=float),
                    "thermflex_q_heat_max_kwh": np.array(
                        [float(inp["q_heat_max_kwh"]) for inp in thermflex_dispatch_inputs], dtype=float
                    ),
                    "thermflex_use_explicit_lower_bounds": bool(lower_bound_schedule_c is not None),
                    "thermflex_comfort_band_k": comfort_band_k,
                    "thermflex_reference_deadband_k": reference_deadband_k,
                    "thermflex_constrain_upper_temperature": bool(
                        getattr(thermflex_constraints_cfg, "constrain_upper_temperature", False)
                    ),
                    "thermflex_max_duration_h": int(
                        getattr(
                            thermflex_constraints_cfg,
                            "max_flex_duration_h",
                            getattr(heating_control_cfg, "max_flex_duration_h", 0),
                        )
                        or 0
                    ),
                    "thermflex_max_events_per_day": int(
                        getattr(
                            thermflex_constraints_cfg,
                            "max_flex_events_per_day",
                            getattr(heating_control_cfg, "max_flex_events_per_day", 0),
                        )
                        or 0
                    ),
                    "thermflex_activation_penalty_eur_per_member_h": float(
                        getattr(thermflex_constraints_cfg, "activation_penalty_eur_per_member_h", 1e-4) or 0.0
                    ),
                    "thermflex_temp_violation_penalty_eur_per_degree_h": float(
                        getattr(thermflex_constraints_cfg, "temperature_violation_penalty_eur_per_degree_h", 1e6) or 0.0
                    ),
                    "thermflex_allow_terminal_deviation": bool(
                        getattr(thermflex_constraints_cfg, "allow_terminal_deviation", True)
                    ),
                    "thermflex_terminal_band_k": float(
                        getattr(thermflex_constraints_cfg, "terminal_band_k", comfort_band_k) or 0.0
                    ),
                    "thermflex_use_event_response_bounds": use_event_response_bounds,
                    "thermflex_event_response_enforce_peak_bounds": bool(
                        getattr(thermflex_constraints_cfg, "enforce_event_peak_bounds", True)
                    ),
                    "thermflex_event_response_enforce_energy_bounds": bool(
                        getattr(thermflex_constraints_cfg, "enforce_event_energy_bounds", True)
                    ),
                    "thermflex_event_response_enforce_recovery_cooldown": bool(
                        getattr(thermflex_constraints_cfg, "enforce_recovery_cooldown", True)
                    ),
                }
                if use_event_response_bounds:
                    thermflex_params.update(
                        {
                            "thermflex_preheat_event_energy_limit_kwh": np.array(
                                [float(item["preheat_event_energy_limit_kwh"]) for item in event_bound_payloads],
                                dtype=float,
                            ),
                            "thermflex_preheat_peak_excess_kwh_per_step": np.array(
                                [float(item["preheat_peak_excess_kwh_per_step"]) for item in event_bound_payloads],
                                dtype=float,
                            ),
                            "thermflex_cutback_event_energy_limit_kwh": np.array(
                                [float(item["cutback_event_energy_limit_kwh"]) for item in event_bound_payloads],
                                dtype=float,
                            ),
                            "thermflex_cutback_peak_shed_kwh_per_step": np.array(
                                [float(item["cutback_peak_shed_kwh_per_step"]) for item in event_bound_payloads],
                                dtype=float,
                            ),
                            "thermflex_recovery_rebound_energy_kwh": np.array(
                                [float(item["recovery_rebound_energy_kwh"]) for item in event_bound_payloads],
                                dtype=float,
                            ),
                            "thermflex_recovery_time_to_reference_h": np.array(
                                [float(item["recovery_time_to_reference_h"]) for item in event_bound_payloads],
                                dtype=float,
                            ),
                        }
                    )
                thermflex_initial_state = {
                    "thermflex_t_in_initial_c": np.asarray(thermflex_t_in_prev_c, dtype=float),
                }
            dispatch_input = DispatchInput(
                series={
                    "electric_non_dispatch_demand": electric_non_dispatch_demand[start:stop],
                    "pv_available": pv_gen[start:stop],
                    "solar_irradiance": irradiance[start:stop],
                    "small_wind_available": small_wind_gen[start:stop],
                    "large_wind_available": large_wind_gen[start:stop],
                    "run_of_river_hydro_available": run_of_river_hydro_gen[start:stop],
                    "ambient_temperature_c": t_out[start:stop],
                    "wind_speed_ms": wind_speed_ms[start:stop],
                    "wind_pressure_hpa": wind_pressure_hpa[start:stop],
                    "grid_import_price": grid_import_price[start:stop],
                    "grid_export_price": grid_export_price[start:stop],
                    "district_gas_chp_power_priority_signal": (
                        district_gas_chp_power_priority_signal[start:stop]
                        if district_gas_chp_power_priority_signal is not None
                        else np.ones(stop - start, dtype=float)
                    ),
                    "district_gas_price_eur_per_mwh_fuel": gas_day_ahead_price_eur_per_mwh[start:stop],
                    "district_gas_day_ahead_price_eur_per_mwh_fuel": gas_day_ahead_price_eur_per_mwh[start:stop],
                    **(
                        {"co2_price_eur_per_tco2": co2_price_eur_per_t[start:stop]}
                        if co2_price_eur_per_t is not None
                        else {}
                    ),
                    **(
                        {
                            "district_gas_balance_price_eur_per_mwh_fuel": gas_balance_price_eur_per_mwh[start:stop]
                        }
                        if gas_balance_price_eur_per_mwh is not None
                        else {}
                    ),
                    "district_space_heat_demand": district_space_heat_demand[start:stop],
                    "district_hotwater_demand": district_hotwater_demand[start:stop],
                    "district_heat_demand": dh_total_demand[start:stop],
                    "district_heat_pump_cop": district_heat_pump_cop[start:stop],
                    "district_geothermal_available_el": district_geothermal_available_electric[start:stop],
                    "district_geothermal_available_th": district_geothermal_available_thermal[start:stop],
                    "district_solar_thermal_available_th": district_solar_thermal_available_thermal[start:stop],
                    "district_solar_thermal_direct_available_th": district_solar_thermal_direct_available_thermal[start:stop],
                    "district_solar_thermal_total_useful_available_th": district_solar_thermal_total_useful_available_thermal[start:stop],
                    "district_external_heat_available_th": district_external_heat_available_thermal[start:stop],
                    "district_waste_incineration_available_th": district_waste_incineration_available_thermal[start:stop],
                    "district_biomass_chp_available_th": district_biomass_chp_available_thermal[start:stop],
                    "district_biogas_chp_available_th": district_biogas_chp_available_thermal[start:stop],
                    "district_gas_chp_available_el": district_gas_chp_available_electric[start:stop],
                    "district_gas_chp_available_th": district_gas_chp_available_thermal[start:stop],
                    "district_gas_boiler_available_th": district_gas_boiler_available_thermal[start:stop],
                    "district_wood_chip_boiler_available_th": district_wood_chip_boiler_available_thermal[start:stop],
                    **thermflex_series,
                },
                assets={
                    "pv_kwp": float(max(0.0, pv_size)),
                    "small_wind_kw": float(small_wind_kw),
                    "large_wind_kw": float(large_wind_kw),
                    "battery_capacity_kwh": float(bess_cap),
                    "battery_power_kwh_per_step": float(bess_p_cap),
                    "h2_tank_kwh": float(h2.e_h2_max_kwh if enable_h2 else 0.0),
                    "ely_power_kwh_per_step": float(h2.p_ely_max_kw * dt_h if enable_h2 else 0.0),
                    "fc_power_kwh_per_step": float(h2.p_fc_max_kw * dt_h if enable_h2 else 0.0),
                    "district_heat_pump_kw_th": float(params.get("district_heat_pump_kw_th", 0.0)),
                    "district_thermal_storage_kwh_th": float(params.get("district_thermal_storage_kwh_th", 0.0)),
                },
                params={
                    "dispatch_mode": dispatch_mode,
                    "dispatch_stochastic_enabled": bool(getattr(dispatch_cfg, "stochastic_enabled", False)),
                    "dispatch_scenario_source": str(getattr(dispatch_cfg, "scenario_source", "historical") or "historical"),
                    "dispatch_n_raw_scenarios": int(getattr(dispatch_cfg, "n_raw_scenarios", 0) or 0),
                    "dispatch_n_reduced_scenarios": int(getattr(dispatch_cfg, "n_reduced_scenarios", 0) or 0),
                    "dispatch_reduction_method": str(getattr(dispatch_cfg, "reduction_method", "fast_forward") or "fast_forward"),
                    "dispatch_distance_metric": str(getattr(dispatch_cfg, "distance_metric", "standardized_euclidean") or "standardized_euclidean"),
                    "dispatch_scenario_feature_keys": list(
                        getattr(
                            dispatch_cfg,
                            "scenario_feature_keys",
                            [
                                "ambient_temperature_c",
                                "grid_import_price",
                                "district_space_heat_demand",
                                "co2_price_eur_per_tco2",
                            ],
                        )
                    ),
                    "dispatch_risk_measure": str(getattr(dispatch_cfg, "risk_measure", "expected_value") or "expected_value"),
                    "dispatch_objective_components": list(
                        getattr(
                            dispatch_cfg,
                            "objective_components",
                            [
                                "grid_import_cost",
                                "grid_export_revenue",
                                "fuel_cost",
                                "co2_cost",
                                "variable_opex",
                            ],
                        )
                    ),
                    "dispatch_unserved_penalty_eur_per_kwh": float(
                        getattr(dispatch_constraints_cfg, "unserved_penalty_eur_per_kwh", 1e6) or 0.0
                    ),
                    "dispatch_spill_penalty_eur_per_kwh": float(
                        getattr(dispatch_constraints_cfg, "spill_penalty_eur_per_kwh", 1e-6) or 0.0
                    ),
                    "dispatch_enable_gas_procurement_model": bool(
                        getattr(dispatch_constraints_cfg, "enable_gas_procurement_model", False)
                    ),
                    "dispatch_enable_co2_cost_model": bool(
                        getattr(dispatch_constraints_cfg, "enable_co2_cost_model", True)
                    ),
                    "bess_eta_charge": float(bess_eta),
                    "bess_eta_discharge": float(bess_eta),
                    "eta_ely": float(h2.eta_ely),
                    "eta_fc": float(h2.eta_fc),
                    "dh_storage_eta_charge": float(getattr(storage_cfg, "charge_efficiency", 1.0) or 1.0),
                    "dh_storage_eta_discharge": float(getattr(storage_cfg, "discharge_efficiency", 1.0) or 1.0),
                    "dh_storage_loss_kwh_per_h": float((getattr(storage_cfg, "standing_loss_kwh_per_day", 0.0) or 0.0) / 24.0),
                    "district_biomass_chp_eta_el": float(getattr(district_biomass_chp_cfg, "eta_el", 0.0) or 0.0),
                    "district_biomass_chp_eta_th": float(getattr(district_biomass_chp_cfg, "eta_th", 0.0) or 0.0),
                    "district_biomass_chp_min_partload": float(getattr(district_biomass_chp_cfg, "min_partload", 0.0) or 0.0),
                    "district_biomass_chp_fuel_lhv_kwh_per_kg": float(getattr(district_biomass_chp_cfg, "fuel_lhv_kwh_per_kg", 1.0) or 1.0),
                    "district_biomass_chp_fuel_cost_eur_per_kg": float(
                        ((tech_economics.get("district_biomass_chp") or {}).get("fuel_eur_per_kg", 0.0) or 0.0)
                    ),
                    "district_biogas_chp_eta_el": float(getattr(district_biogas_chp_cfg, "eta_el", 0.0) or 0.0),
                    "district_biogas_chp_eta_th": float(getattr(district_biogas_chp_cfg, "eta_th", 0.0) or 0.0),
                    "district_biogas_chp_min_partload": float(getattr(district_biogas_chp_cfg, "min_partload", 0.0) or 0.0),
                    "district_biogas_chp_fuel_lhv_kwh_per_nm3": float(getattr(district_biogas_chp_cfg, "fuel_lhv_kwh_per_nm3", 1.0) or 1.0),
                    "district_biogas_chp_fuel_cost_eur_per_nm3": float(
                        ((tech_economics.get("district_biogas_chp") or {}).get("fuel_eur_per_nm3", 0.0) or 0.0)
                    ),
                    "district_external_heat_variable_cost_eur_per_kwh_th": _require_tech_economic_value(
                        tech_economics,
                        "district_external_heat",
                        "variable_opex_eur_per_kwh_th",
                    ),
                    "district_external_heat_min_partload": float(
                        getattr(district_external_heat_cfg, "min_partload", 0.0) or 0.0
                    ),
                    "district_gas_chp_eta_el": float(getattr(district_gas_chp_cfg, "eta_el", 0.0) or 0.0),
                    "district_gas_chp_eta_th": float(getattr(district_gas_chp_cfg, "eta_th", 0.0) or 0.0),
                    "district_gas_chp_operating_mode_model": str(
                        getattr(district_gas_chp_cfg, "operating_mode_model", "fixed_ratio") or "fixed_ratio"
                    ),
                    "district_gas_chp_power_priority_mode": str(
                        getattr(district_gas_chp_cfg, "power_priority_mode", "free") or "free"
                    ),
                    "district_gas_chp_power_priority_price_quantile": float(
                        getattr(district_gas_chp_cfg, "power_priority_price_quantile", 0.9) or 0.9
                    ),
                    "district_gas_chp_operating_point_names": list(
                        _district_gas_chp_piecewise_payload(district_gas_chp_cfg)["operating_point_names"]
                    ),
                    "district_gas_chp_operating_point_eta_el": list(
                        _district_gas_chp_piecewise_payload(district_gas_chp_cfg)["operating_point_eta_el"]
                    ),
                    "district_gas_chp_operating_point_eta_th": list(
                        _district_gas_chp_piecewise_payload(district_gas_chp_cfg)["operating_point_eta_th"]
                    ),
                    "district_gas_chp_min_partload": float(getattr(district_gas_chp_cfg, "min_partload", 0.0) or 0.0),
                    "district_gas_chp_fuel_lhv_kwh_per_m3": float(getattr(district_gas_chp_cfg, "fuel_lhv_kwh_per_m3", 1.0) or 1.0),
                    "district_gas_chp_fuel_cost_eur_per_m3": float(
                        ((tech_economics.get("district_gas_chp") or {}).get("fuel_eur_per_m3", 0.0) or 0.0)
                    ),
                    "district_gas_chp_co2_t_per_mwh_fuel": float(
                        ((tech_economics.get("district_gas_chp") or {}).get("co2_t_per_mwh_fuel", 0.0) or 0.0)
                    ),
                    "district_gas_boiler_eta_th": float(getattr(district_gas_boiler_cfg, "eta_th", 0.0) or 0.0),
                    "district_gas_boiler_min_partload": float(getattr(district_gas_boiler_cfg, "min_partload", 0.0) or 0.0),
                    "district_gas_boiler_max_partload": float(getattr(district_gas_boiler_cfg, "max_partload", 0.0) or 0.0),
                    "district_gas_boiler_fuel_lhv_kwh_per_m3": float(
                        getattr(district_gas_boiler_cfg, "fuel_lhv_kwh_per_m3", 1.0) or 1.0
                    ),
                    "district_gas_boiler_fuel_cost_eur_per_m3": _require_tech_economic_value(
                        tech_economics,
                        "district_gas_boiler",
                        "fuel_eur_per_m3",
                    ),
                    "district_gas_boiler_co2_t_per_mwh_fuel": _require_tech_economic_value(
                        tech_economics,
                        "district_gas_boiler",
                        "co2_t_per_mwh_fuel",
                    ),
                    "district_gas_boiler_variable_cost_eur_per_kwh_th": float(
                        ((tech_economics.get("district_gas_boiler") or {}).get("variable_opex_eur_per_kwh_th", 0.0) or 0.0)
                    ),
                    "district_wood_chip_boiler_eta_th": float(getattr(district_wood_chip_boiler_cfg, "eta_th", 0.0) or 0.0),
                    "district_wood_chip_boiler_min_partload": float(getattr(district_wood_chip_boiler_cfg, "min_partload", 0.0) or 0.0),
                    "district_wood_chip_boiler_max_partload": float(getattr(district_wood_chip_boiler_cfg, "max_partload", 0.0) or 0.0),
                    "district_wood_chip_boiler_fuel_lhv_kwh_per_kg": float(
                        getattr(district_wood_chip_boiler_cfg, "fuel_lhv_kwh_per_kg", 1.0) or 1.0
                    ),
                    "district_wood_chip_boiler_fuel_cost_eur_per_kg": float(
                        ((tech_economics.get("district_wood_chip_boiler") or {}).get("fuel_eur_per_kg", 0.0) or 0.0)
                    ),
                    **thermflex_params,
                },
                initial_state={
                    "bess_soc_initial": float(bess_soc_prev),
                    "h2_soc_initial": float(h2_soc_prev),
                    "district_thermal_storage_soc_initial": float(dh_soc_prev),
                    **thermflex_initial_state,
                },
            )
            if (
                dispatch_mode == "milp_two_stage"
                and bool(getattr(dispatch_cfg, "stochastic_enabled", False))
                and str(getattr(dispatch_cfg, "scenario_source", "historical") or "historical").strip().lower() == "historical"
            ):
                dispatch_input.params["historical_scenarios"] = build_ies_historical_scenarios(
                    dispatch_input,
                    settings_obj=settings_obj,
                    timestamps=timestamps[start:stop],
                )
            dispatch_result = runner(dispatch_input)
            block_walltime_s = (pd.Timestamp.now() - block_t0).total_seconds()
            print(
                "[integrated_energy_system] dispatch block "
                f"{block_idx}/{total_blocks} done | walltime_s={block_walltime_s:.1f}",
                flush=True,
            )
            hourly = dispatch_result.hourly
            grid_import[start:stop] = np.asarray(hourly["grid_import"], dtype=float)
            grid_export[start:stop] = np.asarray(hourly["grid_export"], dtype=float)
            pv_gen[start:stop] = np.asarray(hourly.get("pv_used", pv_gen[start:stop]), dtype=float)
            pv_spillage[start:stop] = np.asarray(hourly.get("pv_spillage", np.zeros(stop - start)), dtype=float)
            small_wind_gen[start:stop] = np.asarray(hourly.get("small_wind_used", small_wind_gen[start:stop]), dtype=float)
            small_wind_spillage[start:stop] = np.asarray(hourly.get("small_wind_spillage", np.zeros(stop - start)), dtype=float)
            large_wind_gen[start:stop] = np.asarray(hourly.get("large_wind_used", large_wind_gen[start:stop]), dtype=float)
            large_wind_spillage[start:stop] = np.asarray(hourly.get("large_wind_spillage", np.zeros(stop - start)), dtype=float)
            run_of_river_hydro_gen[start:stop] = np.asarray(
                hourly.get("run_of_river_hydro_used", run_of_river_hydro_gen[start:stop]),
                dtype=float,
            )
            run_of_river_hydro_spillage[start:stop] = np.asarray(
                hourly.get("run_of_river_hydro_spillage", np.zeros(stop - start)),
                dtype=float,
            )
            bess_ch[start:stop] = np.asarray(hourly["bess_charged"], dtype=float)
            bess_dis[start:stop] = np.asarray(hourly["bess_discharged"], dtype=float)
            bess_soc[start:stop] = np.asarray(hourly["bess_soc"], dtype=float)
            h2_charge_elec[start:stop] = np.asarray(hourly["h2_charge_elec"], dtype=float)
            h2_discharge_elec[start:stop] = np.asarray(hourly["h2_discharge_elec"], dtype=float)
            h2_soc[start:stop] = np.asarray(hourly["h2_soc"], dtype=float)
            unserved_el[start:stop] = np.asarray(hourly.get("unserved_el", np.zeros(stop - start)), dtype=float)
            district_heat_pump_generation[start:stop] = np.asarray(hourly["district_heat_pump_generation"], dtype=float)
            district_heat_pump_electricity[start:stop] = np.asarray(hourly["district_heat_pump_electricity"], dtype=float)
            district_heat_pump_cop[start:stop] = np.asarray(hourly["district_heat_pump_cop"], dtype=float)
            district_thermal_storage_charge[start:stop] = np.asarray(hourly["district_thermal_storage_charge"], dtype=float)
            district_thermal_storage_discharge[start:stop] = np.asarray(hourly["district_thermal_storage_discharge"], dtype=float)
            district_thermal_storage_soc[start:stop] = np.asarray(hourly["district_thermal_storage_soc"], dtype=float)
            district_thermal_storage_losses[start:stop] = np.asarray(hourly["district_thermal_storage_losses"], dtype=float)
            district_geothermal_electric_generation[start:stop] = np.asarray(hourly["district_geothermal_electric_generation"], dtype=float)
            district_geothermal_electric_spillage[start:stop] = np.asarray(
                hourly.get("district_geothermal_electric_spillage", np.zeros(stop - start)),
                dtype=float,
            )
            district_geothermal_thermal_generation[start:stop] = np.asarray(hourly["district_geothermal_thermal_generation"], dtype=float)
            district_geothermal_thermal_spillage[start:stop] = np.asarray(hourly["district_geothermal_thermal_spillage"], dtype=float)
            district_solar_thermal_generation[start:stop] = np.asarray(
                hourly.get("district_solar_thermal_generation", np.zeros(stop - start)),
                dtype=float,
            )
            district_solar_thermal_direct_feed[start:stop] = np.asarray(
                hourly.get("district_solar_thermal_direct_feed", np.zeros(stop - start)),
                dtype=float,
            )
            district_solar_thermal_preheat[start:stop] = np.asarray(
                hourly.get("district_solar_thermal_preheat", np.zeros(stop - start)),
                dtype=float,
            )
            district_solar_thermal_storage_charge[start:stop] = np.asarray(
                hourly.get("district_solar_thermal_storage_charge", np.zeros(stop - start)),
                dtype=float,
            )
            district_solar_thermal_thermal_spillage[start:stop] = np.asarray(
                hourly.get("district_solar_thermal_thermal_spillage", np.zeros(stop - start)),
                dtype=float,
            )
            district_external_heat_generation[start:stop] = np.asarray(
                hourly.get("district_external_heat_generation", np.zeros(stop - start)),
                dtype=float,
            )
            district_external_heat_thermal_spillage[start:stop] = np.asarray(
                hourly.get("district_external_heat_thermal_spillage", np.zeros(stop - start)),
                dtype=float,
            )
            district_waste_incineration_generation[start:stop] = np.asarray(
                hourly.get("district_waste_incineration_generation", np.zeros(stop - start)),
                dtype=float,
            )
            district_waste_incineration_thermal_spillage[start:stop] = np.asarray(
                hourly.get("district_waste_incineration_thermal_spillage", np.zeros(stop - start)),
                dtype=float,
            )
            district_biomass_chp_electric_generation[start:stop] = np.asarray(
                hourly.get("district_biomass_chp_electric_generation", np.zeros(stop - start)),
                dtype=float,
            )
            district_biomass_chp_thermal_generation[start:stop] = np.asarray(
                hourly.get("district_biomass_chp_thermal_generation", np.zeros(stop - start)),
                dtype=float,
            )
            district_biomass_chp_thermal_spillage[start:stop] = np.asarray(
                hourly.get("district_biomass_chp_thermal_spillage", np.zeros(stop - start)),
                dtype=float,
            )
            district_biomass_chp_fuel_input_kwh[start:stop] = np.asarray(
                hourly.get("district_biomass_chp_fuel_input_kwh", np.zeros(stop - start)),
                dtype=float,
            )
            district_biomass_chp_fuel_input_kg[start:stop] = np.asarray(
                hourly.get("district_biomass_chp_fuel_input_kg", np.zeros(stop - start)),
                dtype=float,
            )
            district_biogas_chp_electric_generation[start:stop] = np.asarray(
                hourly.get("district_biogas_chp_electric_generation", np.zeros(stop - start)),
                dtype=float,
            )
            district_biogas_chp_thermal_generation[start:stop] = np.asarray(
                hourly.get("district_biogas_chp_thermal_generation", np.zeros(stop - start)),
                dtype=float,
            )
            district_biogas_chp_thermal_spillage[start:stop] = np.asarray(
                hourly.get("district_biogas_chp_thermal_spillage", np.zeros(stop - start)),
                dtype=float,
            )
            district_biogas_chp_fuel_input_kwh[start:stop] = np.asarray(
                hourly.get("district_biogas_chp_fuel_input_kwh", np.zeros(stop - start)),
                dtype=float,
            )
            district_biogas_chp_fuel_input_nm3[start:stop] = np.asarray(
                hourly.get("district_biogas_chp_fuel_input_nm3", np.zeros(stop - start)),
                dtype=float,
            )
            district_gas_chp_electric_generation[start:stop] = np.asarray(
                hourly.get("district_gas_chp_electric_generation", np.zeros(stop - start)),
                dtype=float,
            )
            district_gas_chp_thermal_generation[start:stop] = np.asarray(
                hourly.get("district_gas_chp_thermal_generation", np.zeros(stop - start)),
                dtype=float,
            )
            district_gas_chp_thermal_spillage[start:stop] = np.asarray(
                hourly.get("district_gas_chp_thermal_spillage", np.zeros(stop - start)),
                dtype=float,
            )
            district_gas_chp_fuel_input_kwh[start:stop] = np.asarray(
                hourly.get("district_gas_chp_fuel_input_kwh", np.zeros(stop - start)),
                dtype=float,
            )
            district_gas_chp_fuel_input_m3[start:stop] = np.asarray(
                hourly.get("district_gas_chp_fuel_input_m3", np.zeros(stop - start)),
                dtype=float,
            )
            if "district_gas_chp_mode_share" in hourly:
                block_mode_share = np.asarray(hourly["district_gas_chp_mode_share"], dtype=float)
                if block_mode_share.ndim != 2:
                    raise ValueError(
                        "[integrated_energy_system] Coupled gas-CHP dispatch returned "
                        "hourly['district_gas_chp_mode_share'] with invalid rank."
                    )
                block_mode_names = [str(name) for name in hourly.get("district_gas_chp_mode_names", [])]
                if not block_mode_names:
                    raise KeyError(
                        "[integrated_energy_system] Coupled gas-CHP dispatch must return "
                        "hourly['district_gas_chp_mode_names'] when mode shares are exported."
                    )
                if block_mode_share.shape[0] != len(block_mode_names):
                    raise ValueError(
                        "[integrated_energy_system] Coupled gas-CHP dispatch returned "
                        "inconsistent mode share rows and mode names."
                    )
                if block_mode_share.shape[1] != (stop - start):
                    raise ValueError(
                        "[integrated_energy_system] Coupled gas-CHP dispatch returned "
                        f"hourly['district_gas_chp_mode_share'] with shape {block_mode_share.shape}, "
                        f"expected ({len(block_mode_names)}, {stop - start})."
                    )
                if district_gas_chp_mode_share is None:
                    district_gas_chp_mode_share = np.zeros((len(block_mode_names), n_steps), dtype=float)
                    district_gas_chp_mode_names = list(block_mode_names)
                else:
                    if list(block_mode_names) != district_gas_chp_mode_names:
                        raise ValueError(
                            "[integrated_energy_system] Coupled gas-CHP dispatch returned "
                            "changing operating mode names across dispatch blocks."
                        )
                district_gas_chp_mode_share[:, start:stop] = block_mode_share
            district_gas_boiler_generation[start:stop] = np.asarray(
                hourly.get("district_gas_boiler_generation", np.zeros(stop - start)),
                dtype=float,
            )
            district_gas_boiler_thermal_spillage[start:stop] = np.asarray(
                hourly.get("district_gas_boiler_thermal_spillage", np.zeros(stop - start)),
                dtype=float,
            )
            district_gas_boiler_fuel_input_kwh[start:stop] = np.asarray(
                hourly.get("district_gas_boiler_fuel_input_kwh", np.zeros(stop - start)),
                dtype=float,
            )
            district_gas_boiler_fuel_input_m3[start:stop] = np.asarray(
                hourly.get("district_gas_boiler_fuel_input_m3", np.zeros(stop - start)),
                dtype=float,
            )
            district_wood_chip_boiler_generation[start:stop] = np.asarray(
                hourly.get("district_wood_chip_boiler_generation", np.zeros(stop - start)),
                dtype=float,
            )
            district_wood_chip_boiler_fuel_input_kwh[start:stop] = np.asarray(
                hourly.get("district_wood_chip_boiler_fuel_input_kwh", np.zeros(stop - start)),
                dtype=float,
            )
            district_wood_chip_boiler_fuel_input_kg[start:stop] = np.asarray(
                hourly.get("district_wood_chip_boiler_fuel_input_kg", np.zeros(stop - start)),
                dtype=float,
            )
            district_space_heat_demand[start:stop] = np.asarray(
                hourly.get("district_space_heat_demand", district_space_heat_demand[start:stop]),
                dtype=float,
            )
            district_space_heat_demand_ref[start:stop] = np.asarray(
                hourly.get("district_space_heat_demand_ref", district_space_heat_demand_ref[start:stop]),
                dtype=float,
            )
            district_hotwater_demand[start:stop] = np.asarray(
                hourly.get("district_hotwater_demand", district_hotwater_demand[start:stop]),
                dtype=float,
            )
            dh_total_demand[start:stop] = np.asarray(hourly["dh_total_demand"], dtype=float)
            dh_total_delivered[start:stop] = np.asarray(hourly["dh_total_delivered"], dtype=float)
            dh_unserved_heat[start:stop] = np.asarray(hourly["dh_unserved_heat"], dtype=float)
            if enable_thermflex and thermflex_member_q_heat is not None:
                # Member-level thermflex detail is required for the later
                # cohort-utilization analysis. The coupled dispatch path should
                # therefore fail immediately if a day block forgets to return it.
                required_member_hourly = {
                    "thermflex_member_q_heat_kwh": thermflex_member_q_heat,
                    "thermflex_member_q_heat_ref_kwh": thermflex_member_q_heat_ref,
                    "thermflex_member_flex_active": thermflex_member_flex_active,
                    "thermflex_member_event_start": thermflex_member_event_start,
                    "thermflex_member_temp_violation_degree_h": thermflex_member_temp_violation,
                    "thermflex_member_t_in_c": thermflex_member_t_in,
                    "thermflex_member_event_preheat_extra_kwh": thermflex_member_event_preheat_extra,
                    "thermflex_member_event_cutback_shed_kwh": thermflex_member_event_cutback_shed,
                }
                for key, target in required_member_hourly.items():
                    if key not in hourly:
                        raise KeyError(
                            "[integrated_energy_system] Coupled thermflex dispatch must return "
                            f"hourly['{key}'] for member-level utilization analysis."
                        )
                    block_arr = np.asarray(hourly[key], dtype=float)
                    expected_shape = (target.shape[0], stop - start)
                    if block_arr.shape != expected_shape:
                        raise ValueError(
                            "[integrated_energy_system] Coupled thermflex dispatch returned "
                            f"hourly['{key}'] with shape {block_arr.shape}, expected {expected_shape}."
                        )
                    target[:, start:stop] = block_arr
            h2_used_kwh[start:stop] = (
                h2_discharge_elec[start:stop] / max(1e-9, h2.eta_fc) if enable_h2 else 0.0
            )
            total_load[start:stop] = electric_non_dispatch_demand[start:stop] + district_heat_pump_electricity[start:stop]
            if stop > start:
                bess_soc_prev = float(bess_soc[stop - 1])
                h2_soc_prev = float(h2_soc[stop - 1])
                dh_soc_prev = float(district_thermal_storage_soc[stop - 1])
                if enable_thermflex:
                    terminal_c = np.asarray(
                        dispatch_result.diagnostics.get("thermflex_t_in_terminal_c"),
                        dtype=float,
                    ).reshape(-1)
                    if terminal_c.size != len(thermflex_dispatch_inputs):
                        raise ValueError(
                            "[integrated_energy_system] Coupled thermflex dispatch must return "
                            "diagnostics['thermflex_t_in_terminal_c'] for all thermflex members."
                        )
                    thermflex_t_in_prev_c = terminal_c
            biomass_feedstock_used_day_kwh = float(
                np.sum(district_biomass_chp_fuel_input_kwh[start:stop] + district_wood_chip_boiler_fuel_input_kwh[start:stop])
            )
            biogas_feedstock_used_day_kwh = float(np.sum(district_biogas_chp_fuel_input_kwh[start:stop]))
            solar_thermal_used_day_kwh = float(np.sum(district_solar_thermal_generation[start:stop]))
            waste_incineration_used_day_kwh = float(np.sum(district_waste_incineration_generation[start:stop]))
            biomass_feedstock_used_total_kwh += biomass_feedstock_used_day_kwh
            biogas_feedstock_used_total_kwh += biogas_feedstock_used_day_kwh
            solar_thermal_used_total_kwh += solar_thermal_used_day_kwh
            waste_incineration_used_total_kwh += waste_incineration_used_day_kwh
            for key, value in dispatch_result.objective_terms.items():
                objective_terms_total[key] = float(objective_terms_total.get(key, 0.0) + float(value))
            dispatch_days.append(dict(dispatch_result.diagnostics))

        dispatch_diagnostics.update(
            {
                "solver_backend": str(dispatch_days[0].get("solver", "unknown")) if dispatch_days else "unknown",
                "scenario_source": dispatch_days[0].get("scenario_source") if dispatch_days else None,
                "reduction_method": dispatch_days[0].get("reduction_method") if dispatch_days else None,
                "district_gas_chp_operating_mode_model": (
                    dispatch_days[0].get("district_gas_chp_operating_mode_model") if dispatch_days else None
                ),
                "n_day_blocks": int(len(dispatch_days)),
                "biomass_feedstock_used_total_kwh": float(biomass_feedstock_used_total_kwh),
                "biogas_feedstock_used_total_kwh": float(biogas_feedstock_used_total_kwh),
                "solar_thermal_used_total_kwh": float(solar_thermal_used_total_kwh),
                "waste_incineration_used_total_kwh": float(waste_incineration_used_total_kwh),
                "objective_terms": objective_terms_total,
                "day_blocks": dispatch_days,
            }
        )
        if dispatch_days and dispatch_days[0].get("district_gas_chp_operating_point_names") is not None:
            dispatch_diagnostics["district_gas_chp_operating_point_names"] = list(
                dispatch_days[0].get("district_gas_chp_operating_point_names", [])
            )
        if dispatch_days:
            def _sum_diag(key: str) -> float:
                return float(
                    np.sum(
                        [
                            float(day[key])
                            for day in dispatch_days
                            if key in day and day[key] is not None
                        ]
                    )
                )

            def _mean_diag(key: str) -> float:
                values = [float(day[key]) for day in dispatch_days if key in day and day[key] is not None]
                if not values:
                    raise KeyError(f"[integrated_energy_system] dispatch day_blocks missing mean diagnostic '{key}'.")
                return float(np.mean(values))

            def _min_diag(key: str) -> float:
                values = [float(day[key]) for day in dispatch_days if key in day and day[key] is not None]
                if not values:
                    raise KeyError(f"[integrated_energy_system] dispatch day_blocks missing min diagnostic '{key}'.")
                return float(np.min(values))

            def _max_diag(key: str) -> float:
                values = [float(day[key]) for day in dispatch_days if key in day and day[key] is not None]
                if not values:
                    raise KeyError(f"[integrated_energy_system] dispatch day_blocks missing max diagnostic '{key}'.")
                return float(np.max(values))

            def _any_diag(key: str) -> bool:
                values = [bool(day[key]) for day in dispatch_days if key in day and day[key] is not None]
                if not values:
                    raise KeyError(f"[integrated_energy_system] dispatch day_blocks missing boolean diagnostic '{key}'.")
                return bool(any(values))

            def _constant_diag(key: str) -> Any:
                values = [day[key] for day in dispatch_days if key in day and day[key] is not None]
                if not values:
                    raise KeyError(
                        f"[integrated_energy_system] dispatch day_blocks missing constant diagnostic '{key}'."
                    )
                first = values[0]
                if any(value != first for value in values[1:]):
                    raise ValueError(
                        f"[integrated_energy_system] dispatch day_blocks disagree on constant diagnostic '{key}'."
                    )
                return first

            top_level_aggregates = {
                "district_gas_chp_co2_t_total": _sum_diag("district_gas_chp_co2_t_total"),
                "district_gas_boiler_co2_t_total": _sum_diag("district_gas_boiler_co2_t_total"),
                "district_gas_boiler_peak_kw": compute_series_peak_kw(district_gas_boiler_generation),
            }
            if enable_thermflex:
                thermflex_metrics_total = compute_thermflex_series_metrics(
                    district_space_heat_demand,
                    district_space_heat_demand_ref,
                )
                dh_total_demand_ref = district_space_heat_demand_ref + district_hotwater_demand
                top_level_aggregates.update(
                    {
                        "thermflex_member_count": int(_constant_diag("thermflex_member_count")),
                        "thermflex_active_member_hours_total": _sum_diag("thermflex_active_member_hours_total"),
                        "thermflex_temperature_violation_degree_hours_total": _sum_diag(
                            "thermflex_temperature_violation_degree_hours_total"
                        ),
                        "thermflex_shifted_space_heat_kwh": float(
                            thermflex_metrics_total["thermflex_shifted_space_heat_kwh"]
                        ),
                        "thermflex_additional_space_heat_kwh": float(
                            thermflex_metrics_total["thermflex_additional_space_heat_kwh"]
                        ),
                        "thermflex_rebound_kwh": float(thermflex_metrics_total["thermflex_rebound_kwh"]),
                        "thermflex_peak_change_kw": float(thermflex_metrics_total["thermflex_peak_change_kw"]),
                        "dh_total_peak_change_kw": compute_series_peak_change_kw(
                            dh_total_demand,
                            dh_total_demand_ref,
                        ),
                        "thermflex_heat_up_ramp_kw_per_h": float(
                            thermflex_metrics_total["thermflex_heat_up_ramp_kw_per_h"]
                        ),
                        "thermflex_heat_down_ramp_kw_per_h": float(
                            thermflex_metrics_total["thermflex_heat_down_ramp_kw_per_h"]
                        ),
                        "thermflex_effective_thermal_storage_kwh": float(
                            thermflex_metrics_total["thermflex_effective_thermal_storage_kwh"]
                        ),
                        "thermflex_max_preheat_headroom_kwh": float(
                            thermflex_metrics_total["thermflex_max_preheat_headroom_kwh"]
                        ),
                        "thermflex_t_in_min_c": _min_diag("thermflex_t_in_min_c"),
                        "thermflex_t_in_max_c": _max_diag("thermflex_t_in_max_c"),
                        "thermflex_t_in_terminal_c": dispatch_days[-1].get("thermflex_t_in_terminal_c"),
                        "thermflex_event_response_bounds_active": _any_diag("thermflex_event_response_bounds_active"),
                        "thermflex_event_peak_bounds_active": _any_diag("thermflex_event_peak_bounds_active"),
                        "thermflex_event_energy_bounds_active": _any_diag("thermflex_event_energy_bounds_active"),
                        "thermflex_event_recovery_cooldown_active": _any_diag(
                            "thermflex_event_recovery_cooldown_active"
                        ),
                    }
                )
                if top_level_aggregates["thermflex_event_response_bounds_active"]:
                    top_level_aggregates.update(
                        {
                            "thermflex_preheat_event_energy_limit_kwh_total": _sum_diag(
                                "thermflex_preheat_event_energy_limit_kwh_total"
                            ),
                            "thermflex_cutback_event_energy_limit_kwh_total": _sum_diag(
                                "thermflex_cutback_event_energy_limit_kwh_total"
                            ),
                            "thermflex_recovery_rebound_energy_kwh_total": _sum_diag(
                                "thermflex_recovery_rebound_energy_kwh_total"
                            ),
                            "thermflex_recovery_time_to_reference_h_mean": _mean_diag(
                                "thermflex_recovery_time_to_reference_h_mean"
                            ),
                            "thermflex_recovery_time_to_reference_h_max": _max_diag(
                                "thermflex_recovery_time_to_reference_h_max"
                            ),
                            "thermflex_preheat_peak_excess_kwh_per_step_max": _max_diag(
                                "thermflex_preheat_peak_excess_kwh_per_step_max"
                            ),
                            "thermflex_cutback_peak_shed_kwh_per_step_max": _max_diag(
                                "thermflex_cutback_peak_shed_kwh_per_step_max"
                            ),
                            "thermflex_event_preheat_extra_realized_kwh": _sum_diag(
                                "thermflex_event_preheat_extra_realized_kwh"
                            ),
                            "thermflex_event_cutback_shed_realized_kwh": _sum_diag(
                                "thermflex_event_cutback_shed_realized_kwh"
                            ),
                        }
                    )
            dispatch_diagnostics.update(top_level_aggregates)
        bess_cyclic_violation_kwh = 0.0
        if enable_bess and bool(_require_attr(bess_cfg, "cyclic_soc")) and n_steps > 0:
            tol = float(_require_attr(bess_cfg, "cyclic_soc_rtol")) * max(1.0, bess_cap)
            bess_cyclic_violation_kwh = max(0.0, abs(bess_soc[-1] - bess_soc[0]) - tol)
        h2_cyclic_violation_kwh = 0.0
        if enable_h2 and bool(_require_attr(hydrogen_cfg, "cyclic_soc")) and n_steps > 0:
            tol = float(_require_attr(hydrogen_cfg, "cyclic_soc_rtol")) * max(1.0, h2.e_h2_max_kwh)
            h2_cyclic_violation_kwh = max(0.0, abs(h2_soc[-1] - h2_soc[0]) - tol)

    dispatch_diagnostics["thermflex_member_export_active"] = bool(thermflex_member_q_heat is not None)
    if thermflex_member_q_heat is not None:
        dispatch_diagnostics["thermflex_member_export_shape"] = [
            int(thermflex_member_q_heat.shape[0]),
            int(thermflex_member_q_heat.shape[1]),
        ]

    result = {
        "pv_generation": pv_gen,
        "pv_spillage": pv_spillage,
        "small_wind_generation": small_wind_gen,
        "small_wind_spillage": small_wind_spillage,
        "large_wind_generation": large_wind_gen,
        "large_wind_spillage": large_wind_spillage,
        "run_of_river_hydro_generation": run_of_river_hydro_gen,
        "run_of_river_hydro_spillage": run_of_river_hydro_spillage,
        "biogas_generation": biogas_generation,
        "wood_gasifier_generation": wood_gasifier_generation,
        "wood_gasifier_fuel_input_kwh": wood_gasifier_fuel_input_kwh,
        "wood_gasifier_fuel_input_kg": wood_gasifier_fuel_input_kg,
        "grid_import": grid_import,
        "grid_export": grid_export,
        "bess_charged": bess_ch,
        "bess_discharged": bess_dis,
        "bess_soc": bess_soc,
        "bess_cyclic_violation_kwh": float(bess_cyclic_violation_kwh),
        "ev_charge_ac": ev_charge_ac,
        "ev_charge_mandatory_ac": mandatory_ev_charge_ac,
        "ev_charge_from_pv_ac": ev_charge_from_pv,
        "ev_charge_from_bess_ac": ev_charge_from_bess,
        "ev_charge_from_ec_ac": ev_charge_from_local,
        "ev_charge_from_grid_ac": ev_charge_from_grid,
        "ev_discharged": ev_dis_ac,
        "ev_discharged_total": ev_dis_ac.sum(axis=1) if n_ev > 0 else np.zeros(n_steps, dtype=float),
        "ev_soc": ev_soc,
        "ec_import_from_pv": np.zeros(n_steps, dtype=float),
        "ec_import_from_ev": np.zeros(n_steps, dtype=float),
        "ec_export_from_pv": np.zeros(n_steps, dtype=float),
        "base_load": base_load,
        "total_load": total_load,
        "household_load": household_load,
        "hotwater_load": hotwater_load,
        "hp_base_elec": hp_base_elec,
        "hp_flex_elec": hp_flex_elec,
        "local_hp_heat_elec": local_hp_heat_elec,
        "local_hp_cool_elec": local_hp_cool_elec,
        "h2_charge_elec": h2_charge_elec,
        "h2_discharge_elec": h2_discharge_elec,
        "h2_used_kwh": h2_used_kwh,
        "h2_soc": h2_soc,
        "h2_cyclic_violation_kwh": float(h2_cyclic_violation_kwh),
        "unserved_el": unserved_el,
        "v2h_allowed": v2h_allowed,
        "v2h_used": v2h_used,
        "v2h_avoided_import_kwh_step": v2h_avoided_import,
        "district_heat_pump_generation": district_heat_pump_generation,
        "district_heat_pump_electricity": district_heat_pump_electricity,
        "district_heat_pump_cop": district_heat_pump_cop,
        "district_geothermal_electric_generation": district_geothermal_electric_generation,
        "district_geothermal_electric_spillage": district_geothermal_electric_spillage,
        "district_geothermal_thermal_generation": district_geothermal_thermal_generation,
        "district_geothermal_thermal_spillage": district_geothermal_thermal_spillage,
        "district_solar_thermal_generation": district_solar_thermal_generation,
        "district_solar_thermal_direct_feed": district_solar_thermal_direct_feed,
        "district_solar_thermal_preheat": district_solar_thermal_preheat,
        "district_solar_thermal_storage_charge": district_solar_thermal_storage_charge,
        "district_solar_thermal_thermal_spillage": district_solar_thermal_thermal_spillage,
        "district_external_heat_generation": district_external_heat_generation,
        "district_external_heat_thermal_spillage": district_external_heat_thermal_spillage,
        "district_waste_incineration_generation": district_waste_incineration_generation,
        "district_waste_incineration_thermal_spillage": district_waste_incineration_thermal_spillage,
        "district_biomass_chp_electric_generation": district_biomass_chp_electric_generation,
        "district_biomass_chp_thermal_generation": district_biomass_chp_thermal_generation,
        "district_biomass_chp_thermal_spillage": district_biomass_chp_thermal_spillage,
        "district_biomass_chp_fuel_input_kwh": district_biomass_chp_fuel_input_kwh,
        "district_biomass_chp_fuel_input_kg": district_biomass_chp_fuel_input_kg,
        "district_biogas_chp_electric_generation": district_biogas_chp_electric_generation,
        "district_biogas_chp_thermal_generation": district_biogas_chp_thermal_generation,
        "district_biogas_chp_thermal_spillage": district_biogas_chp_thermal_spillage,
        "district_biogas_chp_fuel_input_kwh": district_biogas_chp_fuel_input_kwh,
        "district_biogas_chp_fuel_input_nm3": district_biogas_chp_fuel_input_nm3,
        "district_gas_chp_electric_generation": district_gas_chp_electric_generation,
        "district_gas_chp_thermal_generation": district_gas_chp_thermal_generation,
        "district_gas_chp_thermal_spillage": district_gas_chp_thermal_spillage,
        "district_gas_chp_fuel_input_kwh": district_gas_chp_fuel_input_kwh,
        "district_gas_chp_fuel_input_m3": district_gas_chp_fuel_input_m3,
        "district_gas_boiler_generation": district_gas_boiler_generation,
        "district_gas_boiler_thermal_spillage": district_gas_boiler_thermal_spillage,
        "district_gas_boiler_fuel_input_kwh": district_gas_boiler_fuel_input_kwh,
        "district_gas_boiler_fuel_input_m3": district_gas_boiler_fuel_input_m3,
        "district_wood_chip_boiler_generation": district_wood_chip_boiler_generation,
        "district_wood_chip_boiler_fuel_input_kwh": district_wood_chip_boiler_fuel_input_kwh,
        "district_wood_chip_boiler_fuel_input_kg": district_wood_chip_boiler_fuel_input_kg,
        "district_space_heat_demand": district_space_heat_demand,
        "district_space_heat_demand_ref": district_space_heat_demand_ref,
        "district_hotwater_demand": district_hotwater_demand,
        "district_thermal_storage_charge": district_thermal_storage_charge,
        "district_thermal_storage_discharge": district_thermal_storage_discharge,
        "district_thermal_storage_losses": district_thermal_storage_losses,
        "district_thermal_storage_soc": district_thermal_storage_soc,
        "dh_total_demand": dh_total_demand,
        "dh_total_delivered": dh_total_delivered,
        "dh_unserved_heat": dh_unserved_heat,
        "dh_bus": dh_context["bus"] if dh_context is not None else None,
        "dispatch_diagnostics": dispatch_diagnostics,
        "timestamps": timestamps,
    }
    if district_gas_chp_mode_share is not None:
        result.update(
            {
                "district_gas_chp_mode_share": district_gas_chp_mode_share,
                "district_gas_chp_mode_names": list(district_gas_chp_mode_names),
            }
        )
    if thermflex_member_q_heat is not None:
        # This explicit sidecar export keeps the member-level thermflex detail
        # available for cohort-utilization analysis without changing the main
        # KPI schema used by the paper and surrogate pipelines.
        result.update(
            {
                "thermflex_member_ids": list(thermflex_member_ids),
                "thermflex_member_building_keys": list(thermflex_member_building_keys),
                "thermflex_member_archetype_keys": list(thermflex_member_archetype_keys),
                "thermflex_member_floor_area_m2": np.asarray(thermflex_member_floor_area_m2, dtype=float),
                "thermflex_member_stock_scale": np.asarray(thermflex_member_stock_scale, dtype=float),
                "thermflex_member_q_heat_kwh": thermflex_member_q_heat,
                "thermflex_member_q_heat_ref_kwh": thermflex_member_q_heat_ref,
                "thermflex_member_flex_active": thermflex_member_flex_active,
                "thermflex_member_event_start": thermflex_member_event_start,
                "thermflex_member_temp_violation_degree_h": thermflex_member_temp_violation,
                "thermflex_member_t_in_c": thermflex_member_t_in,
                "thermflex_member_event_preheat_extra_kwh": thermflex_member_event_preheat_extra,
                "thermflex_member_event_cutback_shed_kwh": thermflex_member_event_cutback_shed,
            }
        )
    return result
