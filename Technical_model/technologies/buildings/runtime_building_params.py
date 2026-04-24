from __future__ import annotations

from typing import Any, Dict

from Data.technology_data.building import get_building_params


def _require_positive_float(value: Any, *, label: str) -> float:
    if value is None:
        raise ValueError(f"[runtime_building_params] {label} must not be None.")
    value_f = float(value)
    if value_f <= 0.0:
        raise ValueError(f"[runtime_building_params] {label} must be > 0, got {value_f}.")
    return value_f


def _require_nonnegative_float(value: Any, *, label: str) -> float:
    if value is None:
        raise ValueError(f"[runtime_building_params] {label} must not be None.")
    value_f = float(value)
    if value_f < 0.0:
        raise ValueError(f"[runtime_building_params] {label} must be >= 0, got {value_f}.")
    return value_f


def _require_member_attr(member: Any, attr: str) -> Any:
    if member is None or not hasattr(member, attr):
        raise ValueError(f"[runtime_building_params] Member is missing required attribute '{attr}'.")
    return getattr(member, attr)


def _seed_transmission_loss_coefficient_w_per_k(
    *,
    u_wall: float,
    a_wall: float,
    u_window: float,
    a_window_total: float,
    u_roof: float,
    a_roof: float,
    u_floor: float,
    a_floor: float,
) -> tuple[float, float]:
    l_b = (
        float(u_wall) * float(a_wall)
        + float(u_window) * float(a_window_total)
        + float(u_roof) * float(a_roof)
        + float(u_floor) * float(a_floor)
    )
    a_b = float(a_wall) + float(a_window_total) + float(a_roof) + float(a_floor)
    l_px = max(0.0, 0.2 * (0.75 - (l_b / max(a_b, 1e-9))) * l_b)
    return float(l_b), float(l_b + l_px)


def _build_effective_thermal_fields(
    *,
    archetype: Any,
    conditioned_floor_m2: float,
    a_wall_m2: float,
    a_window_total_m2: float,
    a_roof_m2: float,
    a_floor_m2: float,
) -> Dict[str, Any]:
    archetype_key = str(getattr(archetype, "key", "archetype"))
    seed_heat_capacity_wh_per_k = _require_positive_float(
        getattr(archetype, "c_th_wh_per_m2k", None),
        label=f"{archetype_key}.c_th_wh_per_m2k",
    ) * conditioned_floor_m2
    seed_envelope_loss_w_per_k, seed_total_loss_w_per_k = _seed_transmission_loss_coefficient_w_per_k(
        u_wall=_require_positive_float(getattr(archetype, "u_wall", None), label=f"{archetype_key}.u_wall"),
        a_wall=a_wall_m2,
        u_window=_require_positive_float(getattr(archetype, "u_window", None), label=f"{archetype_key}.u_window"),
        a_window_total=a_window_total_m2,
        u_roof=_require_positive_float(getattr(archetype, "u_roof", None), label=f"{archetype_key}.u_roof"),
        a_roof=a_roof_m2,
        u_floor=_require_positive_float(getattr(archetype, "u_floor", None), label=f"{archetype_key}.u_floor"),
        a_floor=a_floor_m2,
    )

    calibration_v1 = getattr(archetype, "calibration_v1", None)
    if calibration_v1 is None:
        return {
            "effective_parameter_source": "archetype_default_seed",
            "effective_transmission_loss_coefficient_w_per_k": seed_total_loss_w_per_k,
            "effective_total_loss_coefficient_w_per_k": seed_total_loss_w_per_k,
            "effective_air_loss_scale": 1.0,
            "effective_heat_capacity_wh_per_k": seed_heat_capacity_wh_per_k,
            "effective_tau_h": seed_heat_capacity_wh_per_k / max(seed_total_loss_w_per_k, 1e-9),
            "seed_envelope_loss_coefficient_w_per_k": seed_envelope_loss_w_per_k,
            "seed_total_loss_coefficient_w_per_k": seed_total_loss_w_per_k,
            "calibration_reduced_order_v1": None,
            "calibration_event_response_v1": None,
        }

    if not isinstance(calibration_v1, dict):
        raise TypeError(
            f"[runtime_building_params] calibration_v1 for archetype '{archetype_key}' must be a dict."
        )
    reduced_order = calibration_v1.get("reduced_order_v1")
    event_response = calibration_v1.get("event_response_v1")
    if not isinstance(reduced_order, dict):
        raise KeyError(
            f"[runtime_building_params] calibration_v1.reduced_order_v1 missing for archetype '{archetype_key}'."
        )
    if not isinstance(event_response, dict):
        raise KeyError(
            f"[runtime_building_params] calibration_v1.event_response_v1 missing for archetype '{archetype_key}'."
        )

    effective_transmission_loss_w_per_k = _require_positive_float(
        reduced_order.get("fitted_transmission_loss_coefficient_w_per_m2k", None),
        label=f"{archetype_key}.calibration_v1.reduced_order_v1.fitted_transmission_loss_coefficient_w_per_m2k",
    ) * conditioned_floor_m2
    effective_total_loss_w_per_k = _require_positive_float(
        reduced_order.get("fitted_total_loss_coefficient_w_per_m2k", None),
        label=f"{archetype_key}.calibration_v1.reduced_order_v1.fitted_total_loss_coefficient_w_per_m2k",
    ) * conditioned_floor_m2
    effective_heat_capacity_wh_per_k = _require_positive_float(
        reduced_order.get("fitted_effective_heat_capacity_wh_per_m2k", None),
        label=f"{archetype_key}.calibration_v1.reduced_order_v1.fitted_effective_heat_capacity_wh_per_m2k",
    ) * conditioned_floor_m2
    effective_air_loss_scale = _require_nonnegative_float(
        reduced_order.get("fitted_air_loss_scale_vs_seed_approx", None),
        label=f"{archetype_key}.calibration_v1.reduced_order_v1.fitted_air_loss_scale_vs_seed_approx",
    )
    effective_tau_h = _require_positive_float(
        reduced_order.get("fitted_tau_h", None),
        label=f"{archetype_key}.calibration_v1.reduced_order_v1.fitted_tau_h",
    )
    return {
        "effective_parameter_source": "calibrated_v1_energyplus_teacher",
        "effective_transmission_loss_coefficient_w_per_k": effective_transmission_loss_w_per_k,
        "effective_total_loss_coefficient_w_per_k": effective_total_loss_w_per_k,
        "effective_air_loss_scale": effective_air_loss_scale,
        "effective_heat_capacity_wh_per_k": effective_heat_capacity_wh_per_k,
        "effective_tau_h": effective_tau_h,
        "seed_envelope_loss_coefficient_w_per_k": seed_envelope_loss_w_per_k,
        "seed_total_loss_coefficient_w_per_k": seed_total_loss_w_per_k,
        "calibration_reduced_order_v1": dict(reduced_order),
        "calibration_event_response_v1": dict(event_response),
    }


def _enrich_legacy_building_params(raw: Dict[str, Any]) -> Dict[str, Any]:
    params = dict(raw)
    total_window_m2 = float(sum(params["A_window"].values()))
    seed_envelope_loss_w_per_k, seed_total_loss_w_per_k = _seed_transmission_loss_coefficient_w_per_k(
        u_wall=_require_positive_float(params.get("U_wall"), label="legacy.U_wall"),
        a_wall=_require_positive_float(params.get("A_wall"), label="legacy.A_wall"),
        u_window=_require_positive_float(params.get("U_window"), label="legacy.U_window"),
        a_window_total=total_window_m2,
        u_roof=_require_positive_float(params.get("U_roof"), label="legacy.U_roof"),
        a_roof=_require_positive_float(params.get("A_roof"), label="legacy.A_roof"),
        u_floor=_require_positive_float(params.get("U_floor"), label="legacy.U_floor"),
        a_floor=_require_positive_float(params.get("A_floor"), label="legacy.A_floor"),
    )
    heat_capacity = _require_positive_float(params.get("heat_capacity"), label="legacy.heat_capacity")
    params.update(
        {
            "effective_parameter_source": "legacy_building_seed",
            "effective_transmission_loss_coefficient_w_per_k": seed_total_loss_w_per_k,
            "effective_total_loss_coefficient_w_per_k": seed_total_loss_w_per_k,
            "effective_air_loss_scale": 1.0,
            "effective_heat_capacity_wh_per_k": heat_capacity,
            "effective_tau_h": heat_capacity / max(seed_total_loss_w_per_k, 1e-9),
            "seed_envelope_loss_coefficient_w_per_k": seed_envelope_loss_w_per_k,
            "seed_total_loss_coefficient_w_per_k": seed_total_loss_w_per_k,
            "calibration_reduced_order_v1": None,
            "calibration_event_response_v1": None,
        }
    )
    return params


def _build_from_thermal_archetype(member: Any, settings_obj: Any) -> Dict[str, Any]:
    thermal_key = str(_require_member_attr(member, "thermal_archetype_key") or "").strip()
    if not thermal_key:
        raise ValueError("[runtime_building_params] thermal_archetype_key must be a non-empty string.")

    thermal_cfg = getattr(settings_obj, "thermal_archetypes", None) if settings_obj is not None else None
    if thermal_cfg is None or not hasattr(thermal_cfg, "archetypes"):
        raise ValueError(
            "[runtime_building_params] settings_obj.thermal_archetypes is required for cohort-based members."
        )
    archetype = thermal_cfg.archetypes.get(thermal_key)
    if archetype is None:
        raise ValueError(f"[runtime_building_params] Unknown thermal_archetype_key='{thermal_key}'.")

    gfa_m2 = _require_positive_float(
        getattr(member, "represented_gfa_m2", None),
        label=f"{thermal_key}.represented_gfa_m2",
    )
    volume_m3 = _require_positive_float(
        getattr(member, "represented_volume_m3", None),
        label=f"{thermal_key}.represented_volume_m3",
    )
    conditioned_share = _require_positive_float(
        getattr(archetype, "conditioned_floor_share_of_gfa", None),
        label=f"{thermal_key}.conditioned_floor_share_of_gfa",
    )
    conditioned_floor_m2 = gfa_m2 * conditioned_share
    room_height_m = volume_m3 / max(1e-9, gfa_m2)
    if room_height_m <= 0.0:
        raise ValueError(f"[runtime_building_params] Derived room_height for '{thermal_key}' must be > 0.")

    total_window_m2 = _require_positive_float(
        getattr(archetype, "window_area_per_gfa", None),
        label=f"{thermal_key}.window_area_per_gfa",
    ) * gfa_m2
    quarter_window = total_window_m2 / 4.0
    a_wall_m2 = _require_positive_float(
        getattr(archetype, "wall_area_per_gfa", None),
        label=f"{thermal_key}.wall_area_per_gfa",
    ) * gfa_m2
    a_roof_m2 = _require_positive_float(
        getattr(archetype, "roof_area_per_gfa", None),
        label=f"{thermal_key}.roof_area_per_gfa",
    ) * gfa_m2
    effective = _build_effective_thermal_fields(
        archetype=archetype,
        conditioned_floor_m2=conditioned_floor_m2,
        a_wall_m2=a_wall_m2,
        a_window_total_m2=total_window_m2,
        a_roof_m2=a_roof_m2,
        a_floor_m2=conditioned_floor_m2,
    )
    sector = str(getattr(archetype, "sector", ""))
    window_g_value = getattr(archetype, "window_g_value", None)
    if sector == "residential":
        if window_g_value is None:
            raise ValueError(
                "[runtime_building_params] Residential calibrated/runtime archetypes must carry "
                f"window_g_value. Missing for '{thermal_key}'."
            )
        resolved_g_glazing = _require_positive_float(window_g_value, label=f"{thermal_key}.window_g_value")
    else:
        # Non-residential glazing remains an explicit V1 placeholder until the
        # repo gains a source-backed non-residential window typology layer.
        resolved_g_glazing = 0.6

    return {
        "U_wall": _require_positive_float(getattr(archetype, "u_wall", None), label=f"{thermal_key}.u_wall"),
        "A_wall": a_wall_m2,
        "U_window": _require_positive_float(getattr(archetype, "u_window", None), label=f"{thermal_key}.u_window"),
        "A_window": {
            "south": quarter_window,
            "east": quarter_window,
            "west": quarter_window,
            "north": quarter_window,
        },
        "solar_multipliers": {"south": 1.0, "east": 0.2, "west": 0.2, "north": 0.0},
        "g_glazing": 0.6,
        "g_glazing_shaded": 0.0,
        "A_roof": a_roof_m2,
        "U_roof": _require_positive_float(getattr(archetype, "u_roof", None), label=f"{thermal_key}.u_roof"),
        "A_floor": conditioned_floor_m2,
        "U_floor": _require_positive_float(getattr(archetype, "u_floor", None), label=f"{thermal_key}.u_floor"),
        "cp_air": 0.34,
        "room_height": room_height_m,
        "window_area_total_m2": total_window_m2,
        "heat_capacity": float(effective["effective_heat_capacity_wh_per_k"]),
        "T_min": float(getattr(archetype, "t_min_k", 294.15)),
        "T_max": float(getattr(archetype, "t_max_k", 300.15)),
        "g_glazing": float(resolved_g_glazing),
        "g_glazing_shaded": 0.0,
        "window_g_value": float(resolved_g_glazing),
        **effective,
    }


def get_runtime_building_params(member: Any, settings_obj: Any | None = None) -> Dict[str, Any]:
    thermal_key = getattr(member, "thermal_archetype_key", None)
    represented_gfa = getattr(member, "represented_gfa_m2", None)
    if thermal_key is not None or represented_gfa is not None:
        return _build_from_thermal_archetype(member, settings_obj)

    building_key = getattr(member, "building_key", None) or getattr(member, "member_id", None)
    if building_key is None:
        raise ValueError("[runtime_building_params] Member requires building_key or thermal_archetype_key.")
    return _enrich_legacy_building_params(get_building_params(str(building_key)))
