from __future__ import annotations

"""CSV exports for optimization results.

This module intentionally avoids any Fast-engine dependency.
"""

import json
import os
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from Data.assembly.replacements import compute_bess_replacement, compute_fc_replacement
from Cost_model.dispatch_cost_model import build_dispatch_cost_breakdown
from Optimization.framework.engines.Gated.io import append_csv


def _metadata_from_settings(settings: Any) -> dict:
    eng = settings.engine
    feat = getattr(eng, "features", None)
    sched = getattr(settings, "scheduler", None)
    meta = {
        "system_id": str(getattr(eng, "system_id", "")),
        "location": str(getattr(eng, "location", "")),
        "country_code": str(getattr(eng, "country_code", "")),
        "features": {
            "enable_bess": bool(getattr(feat, "enable_bess", False)),
            "enable_v2h": bool(getattr(feat, "enable_v2h", False)),
            "enable_h2": bool(getattr(feat, "enable_h2", False)),
            "enable_thermflex": bool(getattr(feat, "enable_thermflex", False)),
            "enable_small_wind": bool(getattr(feat, "enable_small_wind", False)),
            "enable_large_wind": bool(getattr(feat, "enable_large_wind", False)),
            "enable_biogas_engine": bool(getattr(feat, "enable_biogas_engine", False)),
            "enable_wood_gasifier": bool(getattr(feat, "enable_wood_gasifier", False)),
        },
        "counts": {
            "N_EC": int(getattr(eng, "N_EC", 0)),
            "N_HH": int(getattr(eng, "N_HH", 0)),
            "N_EV_total": int(getattr(eng, "N_EV_total", 0)),
            "N_EV_bidirectional": int(getattr(eng, "N_EV_bidirectional", 0)),
        },
        "scheduler": {
            "enabled": bool(getattr(sched, "enabled", False)) if sched is not None else False,
            "pruner": str(getattr(sched, "pruner", "")) if sched is not None else "",
        },
    }
    runtime_meta = getattr(settings, "_runtime_meta", None)
    if isinstance(runtime_meta, dict) and runtime_meta:
        meta.update(runtime_meta)
    return meta


def _as_1d(v: Any) -> np.ndarray:
    a = np.asarray(v, float)
    if a.ndim == 0:
        return a.reshape(1)
    if a.ndim == 1:
        return a
    return a.reshape(a.shape[0], -1).sum(axis=1)


def _require_mapping(value: Any, label: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise TypeError(f"[dispatch_export] {label} fehlt oder ist kein Dict.")
    return value


def _require_key(mapping: dict[str, Any], key: str, label: str) -> Any:
    if key not in mapping:
        raise KeyError(f"[dispatch_export] Pflichtwert '{key}' fehlt in {label}.")
    return mapping[key]


def _require_reporting_attr(reporting: Any, attr: str) -> Any:
    if reporting is None:
        raise ValueError("[dispatch_export] settings.reporting fehlt.")
    value = getattr(reporting, attr, None)
    if value in (None, ""):
        raise ValueError(f"[dispatch_export] settings.reporting.{attr} fehlt oder ist leer.")
    return value


def _feature_enabled(settings: Any, attr: str) -> bool:
    features = getattr(getattr(settings, "engine", None), "features", None)
    return bool(getattr(features, attr, False))


def _technology_enabled(settings: Any, attr: str) -> bool:
    activation = getattr(settings, "technology_activation", None)
    return bool(getattr(activation, attr, False))


def _thermflex_cfg(settings: Any) -> Any:
    constraints = getattr(settings, "constraints", None)
    if constraints is None or not hasattr(constraints, "thermflex"):
        raise ValueError("[dispatch_export] settings.constraints.thermflex fehlt.")
    return constraints.thermflex


def _sum_series_required(raw_results: dict[str, Any], key: str) -> float:
    return float(np.sum(_as_1d(_require_key(raw_results, key, "raw_results"))))


def _sum_series_for_technology(
    *,
    raw_results: dict[str, Any],
    key: str,
    settings: Any,
    technology_attr: str,
) -> float:
    if not _technology_enabled(settings, technology_attr):
        return 0.0
    return _sum_series_required(raw_results, key)


def _diag_float_required(dispatch_diag: dict[str, Any], key: str) -> float:
    value = _require_key(dispatch_diag, key, "dispatch_diagnostics")
    try:
        return float(value)
    except Exception as exc:
        raise TypeError(f"[dispatch_export] dispatch_diagnostics['{key}'] ist nicht numerisch.") from exc


def _diag_int_required(dispatch_diag: dict[str, Any], key: str) -> int:
    value = _require_key(dispatch_diag, key, "dispatch_diagnostics")
    try:
        return int(value)
    except Exception as exc:
        raise TypeError(f"[dispatch_export] dispatch_diagnostics['{key}'] ist nicht ganzzahlig.") from exc


def _diag_list_required(dispatch_diag: dict[str, Any], key: str) -> list[Any]:
    value = _require_key(dispatch_diag, key, "dispatch_diagnostics")
    if isinstance(value, np.ndarray):
        return value.tolist()
    if not isinstance(value, list):
        raise TypeError(f"[dispatch_export] dispatch_diagnostics['{key}'] ist keine Liste.")
    return value


def _series_required(raw_results: dict[str, Any], key: str, *, expected_size: int | None = None) -> np.ndarray:
    arr = _as_1d(_require_key(raw_results, key, "raw_results"))
    if expected_size is not None and int(arr.size) != int(expected_size):
        raise ValueError(
            f"[dispatch_export] Serie '{key}' hat Laenge {arr.size}, erwartet {expected_size}."
        )
    return arr


def _run_hours(raw_results: dict[str, Any], settings: Any) -> float:
    timestamps = raw_results.get("timestamps")
    if timestamps is not None:
        try:
            n_steps = int(len(np.asarray(timestamps)))
            if n_steps > 0:
                return float(n_steps)
        except Exception:
            pass
    run_cfg = getattr(settings, "run", None)
    hours = getattr(run_cfg, "profile_hours", None) if run_cfg is not None else None
    if hours is None:
        raise ValueError("[dispatch_export] Laufdauer unbekannt: weder timestamps noch settings.run.profile_hours vorhanden.")
    return float(hours)


def build_dispatch_kpi_payload(
    *,
    settings: Any,
    flows_L: dict[str, float],
    raw_results: dict[str, Any],
    point_idx: int,
) -> dict[str, Any]:
    reporting = getattr(settings, "reporting", None)
    normalization_windows = list(_require_reporting_attr(reporting, "dispatch_kpi_normalization_windows_h"))
    raw_results = _require_mapping(raw_results, "raw_results")
    dispatch_diag = _require_mapping(
        _require_key(raw_results, "dispatch_diagnostics", "raw_results"),
        "raw_results['dispatch_diagnostics']",
    )
    objective_terms = _require_mapping(
        _require_key(dispatch_diag, "objective_terms", "dispatch_diagnostics"),
        "dispatch_diagnostics['objective_terms']",
    )
    dispatch_costs = build_dispatch_cost_breakdown(objective_terms, strict=True)
    run_hours = max(0.0, _run_hours(raw_results, settings))
    thermflex_enabled = _feature_enabled(settings, "enable_thermflex")
    thermflex_cfg = _thermflex_cfg(settings)
    thermal_variant = str(getattr(getattr(settings, "thermal_archetypes", None), "variant", "") or "")
    use_event_response_bounds = bool(getattr(thermflex_cfg, "use_event_response_bounds", False))
    gas_boiler_co2_t = _diag_float_required(dispatch_diag, "district_gas_boiler_co2_t_total")
    gas_chp_co2_t = _diag_float_required(dispatch_diag, "district_gas_chp_co2_t_total")
    co2_total = gas_boiler_co2_t + gas_chp_co2_t
    if thermflex_enabled:
        thermflex_member_count = _diag_int_required(dispatch_diag, "thermflex_member_count")
        thermflex_shifted = _diag_float_required(dispatch_diag, "thermflex_shifted_space_heat_kwh")
        thermflex_additional = _diag_float_required(dispatch_diag, "thermflex_additional_space_heat_kwh")
        thermflex_rebound = _diag_float_required(dispatch_diag, "thermflex_rebound_kwh")
        thermflex_peak_change = _diag_float_required(dispatch_diag, "thermflex_peak_change_kw")
        dh_total_peak_change = _diag_float_required(dispatch_diag, "dh_total_peak_change_kw")
        thermflex_heat_up_ramp = _diag_float_required(dispatch_diag, "thermflex_heat_up_ramp_kw_per_h")
        thermflex_heat_down_ramp = _diag_float_required(dispatch_diag, "thermflex_heat_down_ramp_kw_per_h")
        thermflex_effective_storage = _diag_float_required(dispatch_diag, "thermflex_effective_thermal_storage_kwh")
        thermflex_preheat_headroom = _diag_float_required(dispatch_diag, "thermflex_max_preheat_headroom_kwh")
        thermflex_active_hours = _diag_float_required(dispatch_diag, "thermflex_active_member_hours_total")
        thermflex_violation = _diag_float_required(
            dispatch_diag,
            "thermflex_temperature_violation_degree_hours_total",
        )
        thermflex_t_in_min = _diag_float_required(dispatch_diag, "thermflex_t_in_min_c")
        thermflex_t_in_max = _diag_float_required(dispatch_diag, "thermflex_t_in_max_c")
        thermflex_terminal_c = _diag_list_required(dispatch_diag, "thermflex_t_in_terminal_c")
        if use_event_response_bounds:
            thermflex_preheat_event_energy_limit_total = _diag_float_required(
                dispatch_diag,
                "thermflex_preheat_event_energy_limit_kwh_total",
            )
            thermflex_cutback_event_energy_limit_total = _diag_float_required(
                dispatch_diag,
                "thermflex_cutback_event_energy_limit_kwh_total",
            )
            thermflex_recovery_rebound_energy_total = _diag_float_required(
                dispatch_diag,
                "thermflex_recovery_rebound_energy_kwh_total",
            )
            thermflex_recovery_time_mean = _diag_float_required(
                dispatch_diag,
                "thermflex_recovery_time_to_reference_h_mean",
            )
            thermflex_recovery_time_max = _diag_float_required(
                dispatch_diag,
                "thermflex_recovery_time_to_reference_h_max",
            )
            thermflex_preheat_peak_excess_max = _diag_float_required(
                dispatch_diag,
                "thermflex_preheat_peak_excess_kwh_per_step_max",
            )
            thermflex_cutback_peak_shed_max = _diag_float_required(
                dispatch_diag,
                "thermflex_cutback_peak_shed_kwh_per_step_max",
            )
            thermflex_event_preheat_extra_realized = _diag_float_required(
                dispatch_diag,
                "thermflex_event_preheat_extra_realized_kwh",
            )
            thermflex_event_cutback_shed_realized = _diag_float_required(
                dispatch_diag,
                "thermflex_event_cutback_shed_realized_kwh",
            )
        else:
            thermflex_preheat_event_energy_limit_total = 0.0
            thermflex_cutback_event_energy_limit_total = 0.0
            thermflex_recovery_rebound_energy_total = 0.0
            thermflex_recovery_time_mean = 0.0
            thermflex_recovery_time_max = 0.0
            thermflex_preheat_peak_excess_max = 0.0
            thermflex_cutback_peak_shed_max = 0.0
            thermflex_event_preheat_extra_realized = 0.0
            thermflex_event_cutback_shed_realized = 0.0
    else:
        thermflex_member_count = 0
        thermflex_shifted = 0.0
        thermflex_additional = 0.0
        thermflex_rebound = 0.0
        thermflex_peak_change = 0.0
        dh_total_peak_change = 0.0
        thermflex_heat_up_ramp = 0.0
        thermflex_heat_down_ramp = 0.0
        thermflex_effective_storage = 0.0
        thermflex_preheat_headroom = 0.0
        thermflex_active_hours = 0.0
        thermflex_violation = 0.0
        thermflex_t_in_min = None
        thermflex_t_in_max = None
        thermflex_terminal_c = []
        thermflex_preheat_event_energy_limit_total = 0.0
        thermflex_cutback_event_energy_limit_total = 0.0
        thermflex_recovery_rebound_energy_total = 0.0
        thermflex_recovery_time_mean = 0.0
        thermflex_recovery_time_max = 0.0
        thermflex_preheat_peak_excess_max = 0.0
        thermflex_cutback_peak_shed_max = 0.0
        thermflex_event_preheat_extra_realized = 0.0
        thermflex_event_cutback_shed_realized = 0.0
    base = {
        "point_idx": int(point_idx),
        "thermal_archetype_variant": thermal_variant,
        "run_hours": float(run_hours),
        "dispatch_mode": str(_require_key(dispatch_diag, "mode", "dispatch_diagnostics")),
        "scenario_source": dispatch_diag.get("scenario_source"),
        "reduction_method": dispatch_diag.get("reduction_method"),
        "n_day_blocks": dispatch_diag.get("n_day_blocks"),
        "dispatch_objective_eur": float(dispatch_costs.dispatch_objective_eur),
        "dispatch_operating_cost_eur": float(dispatch_costs.dispatch_operating_cost_eur),
        "dispatch_penalty_total_eur": float(dispatch_costs.dispatch_penalty_total_eur),
        "dispatch_cost_eur": float(dispatch_costs.dispatch_cost_eur),
        "grid_import_cost_eur": float(dispatch_costs.mc_auction_import_cost_proxy_eur),
        "grid_export_revenue_eur": float(dispatch_costs.grid_export_revenue_eur),
        "fuel_cost_eur": float(dispatch_costs.fuel_cost_eur),
        "co2_cost_eur": float(dispatch_costs.co2_cost_eur),
        "variable_opex_eur": float(dispatch_costs.variable_opex_eur),
        "unserved_penalty_eur": float(dispatch_costs.unserved_penalty_eur),
        "temperature_violation_penalty_eur": float(dispatch_costs.temperature_violation_penalty_eur),
        "thermflex_activation_penalty_eur": float(dispatch_costs.thermflex_activation_penalty_eur),
        "spill_penalty_eur": float(dispatch_costs.spill_penalty_eur),
        "co2_emissions_total_t": co2_total,
        "district_gas_boiler_co2_t": gas_boiler_co2_t,
        "district_gas_chp_co2_t": gas_chp_co2_t,
        "district_gas_boiler_generation_kwh": _sum_series_for_technology(
            raw_results=raw_results,
            key="district_gas_boiler_generation",
            settings=settings,
            technology_attr="district_gas_boiler",
        ),
        "district_gas_boiler_peak_kw": _diag_float_required(dispatch_diag, "district_gas_boiler_peak_kw"),
        "district_gas_chp_thermal_generation_kwh": _sum_series_for_technology(
            raw_results=raw_results,
            key="district_gas_chp_thermal_generation",
            settings=settings,
            technology_attr="district_gas_chp",
        ),
        "district_gas_chp_electric_generation_kwh": _sum_series_for_technology(
            raw_results=raw_results,
            key="district_gas_chp_electric_generation",
            settings=settings,
            technology_attr="district_gas_chp",
        ),
        "district_heat_pump_generation_kwh": _sum_series_for_technology(
            raw_results=raw_results,
            key="district_heat_pump_generation",
            settings=settings,
            technology_attr="district_heat_pump",
        ),
        "district_external_heat_generation_kwh": _sum_series_for_technology(
            raw_results=raw_results,
            key="district_external_heat_generation",
            settings=settings,
            technology_attr="district_external_heat",
        ),
        "district_waste_incineration_generation_kwh": _sum_series_for_technology(
            raw_results=raw_results,
            key="district_waste_incineration_generation",
            settings=settings,
            technology_attr="district_waste_incineration",
        ),
        "dh_unserved_heat_kwh": _sum_series_required(raw_results, "dh_unserved_heat"),
        "thermflex_use_explicit_lower_bounds": bool(getattr(thermflex_cfg, "use_explicit_lower_bounds", False)),
        "thermflex_constant_lower_bound_c": getattr(thermflex_cfg, "constant_lower_bound_c", None),
        "thermflex_day_lower_bound_c": getattr(thermflex_cfg, "day_lower_bound_c", None),
        "thermflex_night_lower_bound_c": getattr(thermflex_cfg, "night_lower_bound_c", None),
        "thermflex_constrain_upper_temperature": bool(
            getattr(thermflex_cfg, "constrain_upper_temperature", False)
        ),
        "thermflex_max_flex_duration_h": int(getattr(thermflex_cfg, "max_flex_duration_h", 0) or 0),
        "thermflex_max_events_per_day": int(getattr(thermflex_cfg, "max_flex_events_per_day", 0) or 0),
        "thermflex_event_response_bounds_active": bool(use_event_response_bounds and thermflex_enabled),
        "thermflex_event_peak_bounds_active": bool(
            thermflex_enabled and use_event_response_bounds and getattr(thermflex_cfg, "enforce_event_peak_bounds", False)
        ),
        "thermflex_event_energy_bounds_active": bool(
            thermflex_enabled and use_event_response_bounds and getattr(thermflex_cfg, "enforce_event_energy_bounds", False)
        ),
        "thermflex_event_recovery_cooldown_active": bool(
            thermflex_enabled and use_event_response_bounds and getattr(thermflex_cfg, "enforce_recovery_cooldown", False)
        ),
        "thermflex_member_count": thermflex_member_count,
        "thermflex_shifted_space_heat_kwh": thermflex_shifted,
        "thermflex_additional_space_heat_kwh": thermflex_additional,
        "thermflex_rebound_kwh": thermflex_rebound,
        "thermflex_peak_change_kw": thermflex_peak_change,
        "dh_total_peak_change_kw": dh_total_peak_change,
        "thermflex_heat_up_ramp_kw_per_h": thermflex_heat_up_ramp,
        "thermflex_heat_down_ramp_kw_per_h": thermflex_heat_down_ramp,
        "thermflex_effective_thermal_storage_kwh": thermflex_effective_storage,
        "thermflex_max_preheat_headroom_kwh": thermflex_preheat_headroom,
        "thermflex_active_member_hours_total": thermflex_active_hours,
        "thermflex_temperature_violation_degree_hours_total": thermflex_violation,
        "thermflex_t_in_min_c": thermflex_t_in_min,
        "thermflex_t_in_max_c": thermflex_t_in_max,
        "thermflex_t_in_terminal_c": thermflex_terminal_c,
        "thermflex_preheat_event_energy_limit_kwh_total": thermflex_preheat_event_energy_limit_total,
        "thermflex_cutback_event_energy_limit_kwh_total": thermflex_cutback_event_energy_limit_total,
        "thermflex_recovery_rebound_energy_kwh_total": thermflex_recovery_rebound_energy_total,
        "thermflex_recovery_time_to_reference_h_mean": thermflex_recovery_time_mean,
        "thermflex_recovery_time_to_reference_h_max": thermflex_recovery_time_max,
        "thermflex_preheat_peak_excess_kwh_per_step_max": thermflex_preheat_peak_excess_max,
        "thermflex_cutback_peak_shed_kwh_per_step_max": thermflex_cutback_peak_shed_max,
        "thermflex_event_preheat_extra_realized_kwh": thermflex_event_preheat_extra_realized,
        "thermflex_event_cutback_shed_realized_kwh": thermflex_event_cutback_shed_realized,
    }
    for window_h in normalization_windows:
        window_h = int(window_h)
        if window_h <= 0 or run_hours <= 0.0:
            continue
        factor = float(window_h) / float(run_hours)
        suffix = "per_day" if window_h == 24 else "per_week" if window_h == 168 else "annualized_from_slice" if window_h == 8760 else f"per_{window_h}h"
        for key in (
            "dispatch_objective_eur",
            "dispatch_operating_cost_eur",
            "dispatch_penalty_total_eur",
            "dispatch_cost_eur",
            "grid_import_cost_eur",
            "grid_export_revenue_eur",
            "fuel_cost_eur",
            "co2_cost_eur",
            "variable_opex_eur",
            "unserved_penalty_eur",
            "temperature_violation_penalty_eur",
            "thermflex_activation_penalty_eur",
            "spill_penalty_eur",
            "co2_emissions_total_t",
            "district_gas_boiler_co2_t",
            "district_gas_chp_co2_t",
            "district_gas_boiler_generation_kwh",
            "district_gas_boiler_peak_kw",
            "district_gas_chp_thermal_generation_kwh",
            "district_gas_chp_electric_generation_kwh",
            "district_heat_pump_generation_kwh",
            "district_external_heat_generation_kwh",
            "district_waste_incineration_generation_kwh",
            "dh_unserved_heat_kwh",
            "thermflex_shifted_space_heat_kwh",
            "thermflex_additional_space_heat_kwh",
            "thermflex_rebound_kwh",
            "thermflex_active_member_hours_total",
            "thermflex_temperature_violation_degree_hours_total",
        ):
            base[f"{key}_{suffix}"] = float(base[key]) * factor
    return base


def append_dispatch_kpi_exports(
    *,
    run_dir: str,
    settings: Any,
    payload: dict[str, Any],
) -> None:
    reporting = getattr(settings, "reporting", None)
    csv_name = str(_require_reporting_attr(reporting, "dispatch_kpis_csv_filename"))
    json_name = str(_require_reporting_attr(reporting, "dispatch_kpis_json_filename"))
    csv_path = os.path.join(run_dir, csv_name)
    json_path = os.path.join(run_dir, json_name)

    row = dict(payload)
    if isinstance(row.get("thermflex_t_in_terminal_c"), list):
        row["thermflex_t_in_terminal_c"] = json.dumps(row["thermflex_t_in_terminal_c"])
    append_csv(Path(csv_path), list(row.keys()), row)

    if os.path.exists(json_path):
        existing = json.loads(Path(json_path).read_text(encoding="utf-8"))
        if not isinstance(existing, dict):
            raise TypeError("[dispatch_export] Bestehende dispatch_kpis.json ist kein JSON-Objekt.")
    else:
        existing = {}
    points_raw = existing.get("points", [])
    if not isinstance(points_raw, list):
        raise TypeError("[dispatch_export] dispatch_kpis.json['points'] ist keine Liste.")
    points = list(points_raw)
    points.append(payload)
    export_names = list(_require_reporting_attr(reporting, "dispatch_kpi_names"))
    summary_point = dict(payload)
    if export_names:
        summary_point = {
            k: v
            for k, v in payload.items()
            if k in export_names
            or k.endswith("_per_day")
            or k.endswith("_per_week")
            or k.endswith("_annualized_from_slice")
            or k in {"point_idx", "run_hours", "dispatch_mode", "scenario_source", "reduction_method", "n_day_blocks", "thermflex_member_count"}
        }
    out = {
        "files": {
            "csv": csv_name,
            "json": json_name,
        },
        "points": points,
        "latest_point": summary_point,
    }
    Path(json_path).write_text(json.dumps(out, indent=2, ensure_ascii=False), encoding="utf-8")


def append_thermflex_hourly_export(
    *,
    run_dir: str,
    settings: Any,
    raw_results: dict[str, Any],
    point_idx: int,
) -> None:
    reporting = getattr(settings, "reporting", None)
    if not _feature_enabled(settings, "enable_thermflex"):
        raise ValueError(
            "[dispatch_export] reporting.write_thermflex_hourly=True, aber Thermflex ist deaktiviert."
        )
    out_name = str(_require_reporting_attr(reporting, "thermflex_hourly_csv_filename"))
    out_path = Path(run_dir) / out_name
    timestamps = np.asarray(_require_key(raw_results, "timestamps", "raw_results"))
    if timestamps.size == 0:
        raise ValueError("[dispatch_export] timestamps sind leer, thermflex_hourly.csv kann nicht geschrieben werden.")
    active = _series_required(raw_results, "thermflex_active_total", expected_size=int(timestamps.size))
    violation = _series_required(
        raw_results,
        "thermflex_temperature_violation_degree_h",
        expected_size=int(timestamps.size),
    )
    space_heat = _series_required(raw_results, "district_space_heat_demand", expected_size=int(timestamps.size))
    space_heat_ref = _series_required(
        raw_results,
        "district_space_heat_demand_ref",
        expected_size=int(timestamps.size),
    )
    delta = _series_required(raw_results, "thermflex_space_heat_delta_kwh", expected_size=int(timestamps.size))
    inventory = _series_required(
        raw_results,
        "thermflex_virtual_storage_inventory_kwh",
        expected_size=int(timestamps.size),
    )
    header = [
        "point_idx",
        "timestamp",
        "thermflex_active_total",
        "thermflex_temperature_violation_degree_h",
        "district_space_heat_demand",
        "district_space_heat_demand_ref",
        "thermflex_space_heat_delta_kwh",
        "thermflex_virtual_storage_inventory_kwh",
    ]
    for i in range(int(timestamps.size)):
        append_csv(
            out_path,
            header,
            {
                "point_idx": int(point_idx),
                "timestamp": str(timestamps[i]),
                "thermflex_active_total": float(active[i]),
                "thermflex_temperature_violation_degree_h": float(violation[i]),
                "district_space_heat_demand": float(space_heat[i]),
                "district_space_heat_demand_ref": float(space_heat_ref[i]),
                "thermflex_space_heat_delta_kwh": float(delta[i]),
                "thermflex_virtual_storage_inventory_kwh": float(inventory[i]),
            },
        )


def export_load_flows_timeseries(run_dir: str, settings: Any, X_opt: np.ndarray, max_points: int = 5) -> None:
    from Optimization.framework.engines.Gold.gold_engine import GoldEngine

    if X_opt is None or len(X_opt) == 0:
        return
    X = np.asarray(X_opt, float).reshape((-1, np.asarray(X_opt, float).shape[-1]))
    idx = {name: i for i, name in enumerate(settings.bounds.names)}
    rows = []
    debug_rows = []
    n_points = min(int(max_points), X.shape[0]) if max_points and max_points > 0 else X.shape[0]
    teacher = GoldEngine(settings)
    for j in range(n_points):
        x_row = X[j, :]
        _F, _G, _flows_L, res = teacher.evaluate_one_with_details(x_row)
        n_steps = len(np.asarray(res["grid_import"]))
        ts = np.asarray(res.get("timestamps", np.arange(n_steps)))
        lifetime = float(teacher.lifetime_years)
        total_load_y = float(np.sum(np.clip(np.asarray(res.get("total_load", np.zeros(n_steps))), 0.0, None)))
        bess_throughput_y = float(
            np.sum(np.clip(np.asarray(res.get("bess_charged", np.zeros(n_steps))), 0.0, None))
            + np.sum(np.clip(np.asarray(res.get("bess_discharged", np.zeros(n_steps))), 0.0, None))
        )
        h2_charge_elec_y = float(np.sum(np.clip(np.asarray(res.get("h2_charge_elec", np.zeros(n_steps))), 0.0, None)))
        h2_discharge_elec_y = float(np.sum(np.clip(np.asarray(res.get("h2_discharge_elec", np.zeros(n_steps))), 0.0, None)))
        e_total_load_l = float(total_load_y * lifetime)
        bess_throughput_l = float(bess_throughput_y * lifetime)
        h2_charge_elec_l = float(h2_charge_elec_y * lifetime)
        h2_discharge_elec_l = float(h2_discharge_elec_y * lifetime)

        bess_kwh = float(X[j, idx["bess_kwh"]]) if "bess_kwh" in idx else 0.0
        fc_kw = float(X[j, idx["fc_kw"]]) if "fc_kw" in idx else 0.0
        ely_kw = float(X[j, idx["ely_kw"]]) if "ely_kw" in idx else 0.0
        h2_tank_kwh = float(X[j, idx["h2_tank_kwh"]]) if "h2_tank_kwh" in idx else 0.0
        small_wind_kw = float(X[j, idx["small_wind_kw"]]) if "small_wind_kw" in idx else 0.0
        large_wind_kw = float(X[j, idx["large_wind_kw"]]) if "large_wind_kw" in idx else 0.0
        district_heat_pump_kw_th = float(X[j, idx["district_heat_pump_kw_th"]]) if "district_heat_pump_kw_th" in idx else 0.0
        district_thermal_storage_kwh_th = float(X[j, idx["district_thermal_storage_kwh_th"]]) if "district_thermal_storage_kwh_th" in idx else 0.0
        district_wood_chip_boiler_kw_th = (
            float(X[j, idx["district_wood_chip_boiler_kw_th"]]) if "district_wood_chip_boiler_kw_th" in idx else 0.0
        )
        district_biomass_chp_kw_th = float(X[j, idx["district_biomass_chp_kw_th"]]) if "district_biomass_chp_kw_th" in idx else 0.0
        district_geothermal_kw_el = float(X[j, idx["district_geothermal_kw_el"]]) if "district_geothermal_kw_el" in idx else 0.0
        district_gas_chp_kw_el = float(X[j, idx["district_gas_chp_kw_el"]]) if "district_gas_chp_kw_el" in idx else 0.0
        district_biogas_chp_kw_el = float(X[j, idx["district_biogas_chp_kw_el"]]) if "district_biogas_chp_kw_el" in idx else 0.0
        biogas_engine_kw = float(X[j, idx["biogas_engine_kw"]]) if "biogas_engine_kw" in idx else 0.0
        wood_gasifier_kw = float(X[j, idx["wood_gasifier_kw"]]) if "wood_gasifier_kw" in idx else 0.0
        params = dict(teacher.params_base)
        params["pv_size"] = float(X[j, idx["pv_kwp"]]) if "pv_kwp" in idx else 0.0
        params["battery_capacity_kWh"] = bess_kwh
        params["ely_kw"] = ely_kw
        params["h2_tank_kwh"] = h2_tank_kwh
        params["fc_kw"] = fc_kw
        params["small_wind_kw"] = small_wind_kw
        params["large_wind_kw"] = large_wind_kw
        params["district_heat_pump_kw_th"] = district_heat_pump_kw_th
        params["district_thermal_storage_kwh_th"] = district_thermal_storage_kwh_th
        params["district_wood_chip_boiler_kw_th"] = district_wood_chip_boiler_kw_th
        params["district_biomass_chp_kw_th"] = district_biomass_chp_kw_th
        params["district_geothermal_kw_el"] = district_geothermal_kw_el
        params["district_gas_chp_kw_el"] = district_gas_chp_kw_el
        params["district_biogas_chp_kw_el"] = district_biogas_chp_kw_el
        params["biogas_engine_kw"] = biogas_engine_kw
        params["wood_gasifier_kw"] = wood_gasifier_kw
        bess_rep = compute_bess_replacement(
            params,
            bess_kwh=bess_kwh,
            annual_bess_throughput_kwh=bess_throughput_y,
        )
        h2_trigger_rep = compute_fc_replacement(
            params,
            fc_kw=fc_kw,
            annual_fc_output_kwh=h2_discharge_elec_y,
        )

        metric = "climate_change"
        bess_lca = params.get("BESS", {}).get("LCA", {})
        fc_lca = params.get("FC", {}).get("LCA", {})
        ely_lca = params.get("ELY", {}).get("LCA", {})
        h2_tank_lca = params.get("H2_TANK", {}).get("LCA", {})
        bess_infra = float(bess_lca.get("infra", {}).get(metric, 0.0))
        bess_op = float(bess_lca.get("op", {}).get(metric, 0.0))
        fc_infra = float(fc_lca.get("infra", {}).get(metric, 0.0))
        fc_op = float(fc_lca.get("op", {}).get(metric, 0.0))
        ely_infra = float(ely_lca.get("infra", {}).get(metric, 0.0))
        ely_op = float(ely_lca.get("op", {}).get(metric, 0.0))
        h2_tank_infra = float(h2_tank_lca.get("infra", {}).get(metric, 0.0))
        h2_tank_op = float(h2_tank_lca.get("op", {}).get(metric, 0.0))

        h2_rep_units = float(h2_trigger_rep.n_total_units)
        bess_ghg_total = float(
            bess_infra * bess_kwh * float(bess_rep.n_total_units)
            + bess_op * bess_throughput_l
        )
        h2_ghg_total = float(
            fc_infra * fc_kw * h2_rep_units
            + ely_infra * ely_kw * h2_rep_units
            + h2_tank_infra * h2_tank_kwh * h2_rep_units
            + fc_op * h2_discharge_elec_l
            + ely_op * h2_charge_elec_l
            + h2_tank_op * h2_discharge_elec_l
        )
        bess_ghg_per_kwh = float(bess_ghg_total / e_total_load_l) if e_total_load_l > 0 else float("nan")
        h2_ghg_per_kwh = float(h2_ghg_total / e_total_load_l) if e_total_load_l > 0 else float("nan")
        debug_rows.append(
            {
                "point_idx": int(j),
                "metric": metric,
                "E_total_load_kWh_lifetime": e_total_load_l,
                "BESS_ghg_total": bess_ghg_total,
                "BESS_ghg_per_kWh_load": bess_ghg_per_kwh,
                "BESS_replacements_continuous": float(bess_rep.n_replacements_continuous),
                "BESS_replacements_discrete": int(bess_rep.n_replacements_discrete),
                "H2_ghg_total": h2_ghg_total,
                "H2_ghg_per_kWh_load": h2_ghg_per_kwh,
                "H2_replacements_continuous": float(max(0.0, h2_rep_units - 1.0)),
                "H2_replacements_discrete": int(h2_trigger_rep.n_replacements_discrete),
                "H2_replacement_trigger": "FC_lifetime_and_usage",
                "SEC_kWh_per_kgH2": float(params.get("SEC_KWH_PER_KG_H2", 50.0)),
                "H2_kWh_per_kg_basis": float(params.get("H2_KWH_PER_KG", 33.33)),
                "H2_energy_basis": str(params.get("H2_ENERGY_BASIS", "LHV")),
                "small_wind_kw": small_wind_kw,
                "large_wind_kw": large_wind_kw,
                "district_heat_pump_kw_th": district_heat_pump_kw_th,
                "district_thermal_storage_kwh_th": district_thermal_storage_kwh_th,
                "district_wood_chip_boiler_kw_th": district_wood_chip_boiler_kw_th,
                "district_biomass_chp_kw_th": district_biomass_chp_kw_th,
                "district_geothermal_kw_el": district_geothermal_kw_el,
                "district_gas_chp_kw_el": district_gas_chp_kw_el,
                "district_biogas_chp_kw_el": district_biogas_chp_kw_el,
                "biogas_engine_kw": biogas_engine_kw,
                "wood_gasifier_kw": wood_gasifier_kw,
                "hours_v2h_allowed": float(res.get("hours_v2h_allowed", 0.0)),
                "hours_v2h_used": float(res.get("hours_v2h_used", 0.0)),
                "v2h_avoided_import_kWh": float(res.get("v2h_avoided_import_kwh", 0.0)),
                "v2h_recharge_grid_kWh": float(res.get("v2h_recharge_grid_kwh", 0.0)),
                "v2h_net_grid_saving_kWh": float(res.get("v2h_net_grid_saving_kwh", 0.0)),
            }
        )
        for t in range(n_steps):
            ev_dis_total = float(np.asarray(res.get("ev_discharged_total", np.zeros(n_steps)))[t])
            if ev_dis_total == 0.0 and "ev_discharged" in res:
                ev_dis_raw = np.asarray(res["ev_discharged"])
                if ev_dis_raw.ndim == 2:
                    ev_dis_total = float(ev_dis_raw[t, :].sum())
                elif ev_dis_raw.ndim == 1:
                    ev_dis_total = float(ev_dis_raw[t])
            rows.append(
                {
                    "point_idx": int(j),
                    "timestamp": str(ts[t]),
                    "grid_import": float(np.asarray(res["grid_import"])[t]),
                    "grid_export": float(np.asarray(res["grid_export"])[t]),
                    "bess_charged": float(np.asarray(res["bess_charged"])[t]),
                    "bess_discharged": float(np.asarray(res["bess_discharged"])[t]),
                    "ev_charge_ac": float(np.asarray(res["ev_charge_ac"])[t]),
                    "ev_discharged": ev_dis_total,
                    "pv_generation": float(np.asarray(res["pv_generation"])[t]),
                    "small_wind_generation": float(np.asarray(res.get("small_wind_generation", np.zeros(n_steps)))[t]),
                    "large_wind_generation": float(np.asarray(res.get("large_wind_generation", np.zeros(n_steps)))[t]),
                    "biogas_generation": float(np.asarray(res.get("biogas_generation", np.zeros(n_steps)))[t]),
                    "wood_gasifier_generation": float(np.asarray(res.get("wood_gasifier_generation", np.zeros(n_steps)))[t]),
                    "base_load": float(np.asarray(res["base_load"])[t]),
                    "total_load": float(np.asarray(res["total_load"])[t]),
                    "h2_charge_elec": float(np.asarray(res.get("h2_charge_elec", np.zeros(n_steps)))[t]),
                    "h2_discharge_elec": float(np.asarray(res.get("h2_discharge_elec", np.zeros(n_steps)))[t]),
                    "hp_flex_elec": float(np.asarray(res.get("hp_flex_elec", np.zeros(n_steps)))[t]),
                    "h2_soc": float(np.asarray(res.get("h2_soc", np.zeros(n_steps)))[t]),
                    "v2h_allowed": float(np.asarray(res.get("v2h_allowed", np.zeros(n_steps)))[t]),
                    "v2h_used": float(np.asarray(res.get("v2h_used", np.zeros(n_steps)))[t]),
                    "v2h_avoided_import_kwh_step": float(np.asarray(res.get("v2h_avoided_import_kwh_step", np.zeros(n_steps)))[t]),
                }
            )

    if rows:
        pd.DataFrame(rows).to_csv(os.path.join(run_dir, "load_flows_timeseries.csv"), index=False)
    if debug_rows:
        pd.DataFrame(debug_rows).to_csv(os.path.join(run_dir, "ghg_debug_by_point.csv"), index=False)


def export_pareto_csv(run_dir: str, settings: Any, X_opt: np.ndarray, F_opt: np.ndarray, G_opt: np.ndarray | None = None, use_teacher_for_details: bool = False) -> None:
    from Optimization.framework.engines.Gold.gold_engine import GoldEngine

    if X_opt is None or len(X_opt) == 0:
        return

    X = np.asarray(X_opt, float)
    F = np.asarray(F_opt, float) if F_opt is not None else None
    G = np.asarray(G_opt, float) if G_opt is not None else None
    df = pd.DataFrame(X, columns=list(settings.bounds.names))

    if F is not None:
        for j, name in enumerate(settings.objectives.names):
            df[f"F_{name}"] = F[:, j]
    if G is not None and G.size:
        for j, name in enumerate(settings.constraints.names):
            df[f"G_{name}"] = G[:, j]

    if use_teacher_for_details:
        teacher = GoldEngine(settings)
        details = []
        for i in range(len(X)):
            _F, _G, flows = teacher.evaluate_one_with_flows(X[i])
            details.append(flows)
        df = pd.concat([df, pd.DataFrame(details)], axis=1)

    df.to_csv(os.path.join(run_dir, "pareto_points.csv"), index=False)
    with open(os.path.join(run_dir, "results_plus.csvmeta.json"), "w", encoding="utf-8") as f:
        json.dump(
            {
                "objectives": list(settings.objectives.names),
                "constraints": list(settings.constraints.names),
                "bounds": {
                    "names": list(settings.bounds.names),
                    "lower": list(settings.bounds.lower),
                    "upper": list(settings.bounds.upper),
                },
                "metadata": _metadata_from_settings(settings),
            },
            f,
            indent=2,
        )
