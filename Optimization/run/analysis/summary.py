from __future__ import annotations

import json
import os

import numpy as np


def _range_str(a: np.ndarray) -> str:
    return f"[{np.min(a):.3g} ... {np.max(a):.3g}]"


def _require_reporting_attr(reporting, attr: str):
    if reporting is None:
        raise ValueError("[summary] settings.reporting fehlt.")
    value = getattr(reporting, attr, None)
    if value in (None, ""):
        raise ValueError(f"[summary] settings.reporting.{attr} fehlt oder ist leer.")
    return value


def write_summary(run_dir: str, settings, X_opt: np.ndarray, F_opt: np.ndarray) -> None:
    X = np.asarray(X_opt, float) if X_opt is not None else None
    F = np.asarray(F_opt, float) if F_opt is not None else None

    lines: list[str] = []
    lines.append("=== Optimization Summary ===")
    lines.append(f"Engine: {settings.engine.name}")
    lines.append(f"System: {settings.engine.system_id} @ {settings.engine.location}")
    lines.append(
        f"EC shares (import/export): {settings.engine.ec_share_import}/{settings.engine.ec_share_export}"
    )
    lines.append(
        f"N_HH={settings.engine.N_HH}, "
        f"N_EV_total={settings.engine.N_EV_total}, "
        f"N_EV_bidirectional={settings.engine.N_EV_bidirectional}"
    )
    feat = getattr(settings.engine, "features", None)
    if feat is not None:
        lines.append(
            "Features: "
            f"bess={bool(getattr(feat, 'enable_bess', False))}, "
            f"v2h={bool(getattr(feat, 'enable_v2h', False))}, "
            f"h2={bool(getattr(feat, 'enable_h2', False))}, "
            f"thermflex={bool(getattr(feat, 'enable_thermflex', False))}, "
            f"small_wind={bool(getattr(feat, 'enable_small_wind', False))}, "
            f"large_wind={bool(getattr(feat, 'enable_large_wind', False))}, "
            f"biogas_engine={bool(getattr(feat, 'enable_biogas_engine', False))}, "
            f"wood_gasifier={bool(getattr(feat, 'enable_wood_gasifier', False))}"
        )
    lines.append("")
    lines.append(f"Design vars: {settings.bounds.names}")
    lines.append(f"Bounds: lower={settings.bounds.lower}, upper={settings.bounds.upper}")
    lines.append(f"Objectives: {settings.objectives.names} (minimize={settings.objectives.minimize})")
    if settings.constraints.names:
        lines.append(
            f"Constraints (<=0): {list(zip(settings.constraints.names, settings.constraints.senses, settings.constraints.rhs))}"
        )
    lines.append("")
    lines.append(
        f"Sampler: {settings.sampler.name} (n={settings.sampler.n_samples}, seed={settings.sampler.seed})"
    )
    lines.append(
        f"Optimizer: {settings.optimizer.name} {settings.optimizer.kwargs} (seed={settings.optimizer.seed})"
    )
    lines.append("")

    if X is not None and X.size:
        lines.append(
            "X ranges: " + ", ".join(f"{n}={_range_str(X[:, i])}" for i, n in enumerate(settings.bounds.names))
        )
    if F is not None and F.size:
        lines.append(
            "F ranges: "
            + ", ".join(f"{n}={_range_str(F[:, i])}" for i, n in enumerate(settings.objectives.names))
        )

    reporting = getattr(settings, "reporting", None)
    dispatch_json_name = str(_require_reporting_attr(reporting, "dispatch_kpis_json_filename"))
    dispatch_json_path = os.path.join(run_dir, dispatch_json_name)
    if os.path.exists(dispatch_json_path):
        with open(dispatch_json_path, "r", encoding="utf-8") as f:
            payload = json.load(f)
        latest = payload.get("latest_point", {}) if isinstance(payload, dict) else {}
        if isinstance(latest, dict) and latest:
            lines.append("")
            lines.append("=== Dispatch / Thermflex KPIs ===")
            preferred_keys = [
                "dispatch_mode",
                "scenario_source",
                "reduction_method",
                "run_hours",
                "thermal_archetype_variant",
                "dispatch_objective_eur",
                "dispatch_objective_eur_per_day",
                "dispatch_operating_cost_eur",
                "dispatch_operating_cost_eur_per_day",
                "dispatch_penalty_total_eur",
                "dispatch_penalty_total_eur_per_day",
                "dispatch_cost_eur",
                "dispatch_cost_eur_per_day",
                "dispatch_cost_eur_per_week",
                "grid_import_cost_eur",
                "grid_export_revenue_eur",
                "co2_emissions_total_t",
                "co2_emissions_total_t_per_day",
                "fuel_cost_eur",
                "co2_cost_eur",
                "variable_opex_eur",
                "unserved_penalty_eur",
                "temperature_violation_penalty_eur",
                "thermflex_activation_penalty_eur",
                "spill_penalty_eur",
                "district_gas_boiler_generation_kwh",
                "district_gas_boiler_peak_kw",
                "district_gas_chp_thermal_generation_kwh",
                "district_gas_chp_electric_generation_kwh",
                "district_heat_pump_generation_kwh",
                "district_external_heat_generation_kwh",
                "district_waste_incineration_generation_kwh",
                "thermflex_shifted_space_heat_kwh",
                "thermflex_additional_space_heat_kwh",
                "thermflex_rebound_kwh",
                "thermflex_peak_change_kw",
                "dh_total_peak_change_kw",
                "thermflex_heat_up_ramp_kw_per_h",
                "thermflex_heat_down_ramp_kw_per_h",
                "thermflex_effective_thermal_storage_kwh",
                "thermflex_max_preheat_headroom_kwh",
                "thermflex_active_member_hours_total",
                "thermflex_temperature_violation_degree_hours_total",
                "thermflex_t_in_min_c",
                "thermflex_t_in_max_c",
                "thermflex_t_in_terminal_c",
                "thermflex_use_explicit_lower_bounds",
                "thermflex_constant_lower_bound_c",
                "thermflex_day_lower_bound_c",
                "thermflex_night_lower_bound_c",
                "thermflex_constrain_upper_temperature",
                "thermflex_max_flex_duration_h",
                "thermflex_max_events_per_day",
                "thermflex_event_response_bounds_active",
                "thermflex_event_peak_bounds_active",
                "thermflex_event_energy_bounds_active",
                "thermflex_event_recovery_cooldown_active",
                "thermflex_preheat_event_energy_limit_kwh_total",
                "thermflex_cutback_event_energy_limit_kwh_total",
                "thermflex_recovery_rebound_energy_kwh_total",
                "thermflex_recovery_time_to_reference_h_mean",
                "thermflex_recovery_time_to_reference_h_max",
                "thermflex_preheat_peak_excess_kwh_per_step_max",
                "thermflex_cutback_peak_shed_kwh_per_step_max",
                "thermflex_event_preheat_extra_realized_kwh",
                "thermflex_event_cutback_shed_realized_kwh",
            ]
            for key in preferred_keys:
                if key in latest:
                    lines.append(f"{key}: {latest[key]}")

    out_txt = os.path.join(run_dir, "summary.txt")
    with open(out_txt, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
