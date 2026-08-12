from __future__ import annotations

from typing import Any, Dict, List

import numpy as np

from Optimization.framework.engines.kpi import get_selected_objective_names
from Settings.surrogate.train import make_surrogate_train


def hash_to_int(value: str) -> int:
    return int.from_bytes(str(value).encode("utf-8"), "little") % 1_000_000_000


def get_active_tariff_arm(settings: Any) -> str:
    return str(getattr(getattr(settings, "market", None), "active_tariff_arm", "flat") or "flat").strip().lower()


def get_reference_control_mode(settings: Any) -> str:
    return str(getattr(getattr(settings, "heating_control", None), "reference_control_mode", "constant") or "constant").strip().lower()


def get_control_mode(settings: Any) -> str:
    return str(getattr(getattr(settings, "heating_control", None), "control_mode", "constant") or "constant").strip().lower()


def heating_control_policy_identity(settings: Any) -> Dict[str, Any]:
    """Return heating-control fields that change teacher labels and must
    participate in native surrogate family identity.

    ThermFlex paper cases treat ``constant_setpoint_c`` and ``control_mode`` as
    first-class global policy levers. Those values already appear in static
    features and signature context, but ``build_family`` previously hashed only
    feature *names*, so e.g. setpoint 22.0 vs 22.5 (Settings default vs paper)
    or ``constant`` vs ``day_night`` collided on one ``family_hash``. Dataset
    cache reuse and ``resolve_model`` then silently attached the wrong teacher
    labels / artifact across incompatible heating policies.
    """
    heating_control = getattr(settings, "heating_control", None)
    return {
        "reference_control_mode": get_reference_control_mode(settings),
        "control_mode": get_control_mode(settings),
        "constant_setpoint_c": float(getattr(heating_control, "constant_setpoint_c", 0.0) or 0.0),
        "day_setpoint_c": float(getattr(heating_control, "day_setpoint_c", 0.0) or 0.0),
        "night_setpoint_c": float(getattr(heating_control, "night_setpoint_c", 0.0) or 0.0),
    }


def thermflex_event_response_policy_identity(settings: Any) -> Dict[str, Any]:
    """Return ThermFlex event-response fields that change MILP teacher labels.

    Vienna ThermFlex paper cases activate
    ``constraints.thermflex.use_event_response_bounds=True`` (with peak/energy/
    recovery enforces). Settings defaults keep the flag ``False``. Those levers
    change the feasible ThermFlex region and therefore teacher KPIs, but they
    previously lived in neither ``signature_hash`` static context nor the hashed
    native ``family_hash`` (open PR #39 covers envelope lowers/duration/events
    only). Train under defaults then switch to the paper event-response cut
    reused one family/artifact silently.
    """
    thermflex_cfg = getattr(getattr(settings, "constraints", None), "thermflex", None)
    return {
        "use_event_response_bounds": bool(
            getattr(thermflex_cfg, "use_event_response_bounds", False)
        ),
        "enforce_event_peak_bounds": bool(
            getattr(thermflex_cfg, "enforce_event_peak_bounds", True)
        ),
        "enforce_event_energy_bounds": bool(
            getattr(thermflex_cfg, "enforce_event_energy_bounds", True)
        ),
        "enforce_recovery_cooldown": bool(
            getattr(thermflex_cfg, "enforce_recovery_cooldown", True)
        ),
    }


def engine_feature_policy_identity(settings: Any) -> Dict[str, Any]:
    """Return engine/technology enable flags that change teacher labels.

    SH/GIW arms toggle ``features.enable_thermflex`` / ``enable_h2`` / … while
    keeping the same design-bound *names* and static feature *names*. Family
    hashing previously used only those names, so e.g. ``bess0_v2h0_h2{0}_tf0``
    vs ``…_tf1`` shared one ``family_hash`` and ``auto_train_surrogate`` could
    reuse incompatible teacher Y across arms. ``signature_hash`` already embeds
    these flags; family identity must match that contract.
    """
    features = getattr(getattr(settings, "engine", None), "features", None)
    activation = getattr(settings, "technology_activation", None)
    return {
        "enable_bess": bool(getattr(features, "enable_bess", False)),
        "enable_v2h": bool(getattr(features, "enable_v2h", False)),
        "enable_h2": bool(getattr(features, "enable_h2", False)),
        "enable_thermflex": bool(getattr(features, "enable_thermflex", False)),
        "enable_small_wind": bool(getattr(features, "enable_small_wind", False)),
        "enable_large_wind": bool(getattr(features, "enable_large_wind", False)),
        "enable_biogas_engine": bool(getattr(features, "enable_biogas_engine", False)),
        "enable_wood_gasifier": bool(getattr(features, "enable_wood_gasifier", False)),
        "district_external_heat": bool(getattr(activation, "district_external_heat", False)),
        "district_gas_boiler": bool(getattr(activation, "district_gas_boiler", False)),
        "district_heat_pump": bool(getattr(activation, "district_heat_pump", False)),
        "district_thermal_storage": bool(
            getattr(activation, "district_thermal_storage", False)
        ),
        "district_wood_chip_boiler": bool(
            getattr(activation, "district_wood_chip_boiler", False)
        ),
        "district_biomass_chp": bool(getattr(activation, "district_biomass_chp", False)),
        "district_biogas_chp": bool(getattr(activation, "district_biogas_chp", False)),
        "district_gas_chp": bool(getattr(activation, "district_gas_chp", False)),
        "district_geothermal": bool(getattr(activation, "district_geothermal", False)),
        "district_solar_thermal": bool(getattr(activation, "district_solar_thermal", False)),
        "district_waste_incineration": bool(
            getattr(activation, "district_waste_incineration", False)
        ),
    }


def _is_feature_enabled(settings: Any, attr: str) -> bool:
    eng_cfg = getattr(settings, "engine", None)
    features = getattr(eng_cfg, "features", None)
    return bool(getattr(features, attr, False))


def _is_technology_enabled(settings: Any, attr: str) -> bool:
    activation = getattr(settings, "technology_activation", None)
    return bool(getattr(activation, attr, False))


def build_signature_system_flags(settings: Any, params_base: Dict[str, Any]) -> Dict[str, Any]:
    """Build the explicit system-flag block used in surrogate signatures.

    This helper exists because training-time promotion and runtime loading must
    hash the *same* structural context. If these flags drift apart, the repo can
    silently create incompatible artifact directories for the same logical
    surrogate family. We keep the block centralized here to make that contract
    inspectable and stable.
    """
    features = getattr(getattr(settings, "engine", None), "features", None)
    technology_activation = getattr(settings, "technology_activation", None)
    district_heating = getattr(settings, "district_heating", None)
    return {
        "enable_bess": int(bool(getattr(features, "enable_bess", False))),
        "enable_v2h": int(bool(getattr(features, "enable_v2h", False))),
        "enable_h2": int(bool(getattr(features, "enable_h2", False))),
        "enable_thermflex": int(bool(getattr(features, "enable_thermflex", False))),
        "enable_small_wind": int(bool(getattr(features, "enable_small_wind", False))),
        "enable_large_wind": int(bool(getattr(features, "enable_large_wind", False))),
        "enable_biogas_engine": int(bool(getattr(features, "enable_biogas_engine", False))),
        "enable_wood_gasifier": int(bool(getattr(features, "enable_wood_gasifier", False))),
        "enable_district_external_heat": int(bool(getattr(technology_activation, "district_external_heat", False))),
        "enable_district_gas_boiler": int(bool(getattr(technology_activation, "district_gas_boiler", False))),
        "enable_district_heat_pump": int(bool(getattr(technology_activation, "district_heat_pump", False))),
        "enable_district_thermal_storage": int(bool(getattr(technology_activation, "district_thermal_storage", False))),
        "enable_district_solar_thermal": int(bool(getattr(technology_activation, "district_solar_thermal", False))),
        "enable_district_waste_incineration": int(bool(getattr(technology_activation, "district_waste_incineration", False))),
        "enable_district_wood_chip_boiler": int(bool(getattr(technology_activation, "district_wood_chip_boiler", False))),
        "enable_district_biomass_chp": int(bool(getattr(technology_activation, "district_biomass_chp", False))),
        "enable_district_biogas_chp": int(bool(getattr(technology_activation, "district_biogas_chp", False))),
        "enable_district_gas_chp": int(bool(getattr(technology_activation, "district_gas_chp", False))),
        "enable_district_geothermal": int(bool(getattr(technology_activation, "district_geothermal", False))),
        "district_heating_share": float(getattr(district_heating, "share", 0.0) or 0.0),
        "district_external_heat_kw_th": float(params_base.get("district_external_heat_kw_th", 0.0)),
        "district_gas_boiler_kw_th": float(params_base.get("district_gas_boiler_kw_th", 0.0)),
        "district_solar_thermal_kw_th": float(params_base.get("district_solar_thermal_kw_th", 0.0)),
        "district_waste_incineration_kw_th": float(params_base.get("district_waste_incineration_kw_th", 0.0)),
    }


def resolve_surrogate_family(settings: Any) -> str:
    system_id = str(getattr(getattr(settings, "engine", None), "system_id", "unknown") or "unknown")
    active_tariff_arm = get_active_tariff_arm(settings)
    has_extended_features = any(
        [
            _is_feature_enabled(settings, "enable_small_wind"),
            _is_feature_enabled(settings, "enable_large_wind"),
            _is_feature_enabled(settings, "enable_biogas_engine"),
            _is_feature_enabled(settings, "enable_wood_gasifier"),
            _is_technology_enabled(settings, "district_external_heat"),
            _is_technology_enabled(settings, "district_gas_boiler"),
            _is_technology_enabled(settings, "district_heat_pump"),
            _is_technology_enabled(settings, "district_thermal_storage"),
            _is_technology_enabled(settings, "district_wood_chip_boiler"),
            _is_technology_enabled(settings, "district_biomass_chp"),
            _is_technology_enabled(settings, "district_biogas_chp"),
            _is_technology_enabled(settings, "district_gas_chp"),
            _is_technology_enabled(settings, "district_geothermal"),
            _is_technology_enabled(settings, "district_solar_thermal"),
            _is_technology_enabled(settings, "district_waste_incineration"),
        ]
    )
    if system_id == "EC_FLEX" and active_tariff_arm == "flat" and not has_extended_features:
        return "classic_shared"
    return "extended_shared"


def _default_base_targets_for_system(settings: Any) -> List[str]:
    system_id = str(getattr(getattr(settings, "engine", None), "system_id", "unknown") or "unknown")
    common = [
        "E_import_grid_kWh",
        "E_export_grid_kWh",
        "E_total_load_kWh",
        "PV_generation_kWh",
        "E_ev_charged_kWh",
        "E_ev_discharged_kWh",
        "E_h2_charge_elec_kWh",
        "E_h2_discharge_elec_kWh",
        "E_hp_flex_elec_kWh",
        "bess_cyclic_violation_kwh",
        "h2_cyclic_violation_kwh",
    ]
    if system_id == "EC_FLEX":
        return [
            "E_import_ec_pv_kWh",
            "E_import_ec_ev_kWh",
            "E_export_ec_pv_kWh",
            *common,
        ]
    return common


def _active_technology_targets(settings: Any) -> List[str]:
    targets: List[str] = []
    if _is_feature_enabled(settings, "enable_small_wind"):
        targets.append("E_small_wind_generation_kWh")
    if _is_feature_enabled(settings, "enable_large_wind"):
        targets.append("E_large_wind_generation_kWh")
    if _is_feature_enabled(settings, "enable_biogas_engine"):
        targets.append("E_biogas_generation_kWh")
    if _is_feature_enabled(settings, "enable_wood_gasifier"):
        targets.extend(
            [
                "E_wood_gasifier_generation_kWh",
                "E_wood_gasifier_fuel_input_kWh",
            ]
        )
    if _is_technology_enabled(settings, "district_heat_pump"):
        targets.extend(
            [
                "E_district_heat_pump_thermal_generation_kWh",
                "E_district_heat_pump_electricity_kWh",
            ]
        )
    if _is_technology_enabled(settings, "district_thermal_storage"):
        targets.extend(
            [
                "E_district_thermal_storage_charge_kWh",
                "E_district_thermal_storage_discharge_kWh",
                "E_district_thermal_storage_losses_kWh",
            ]
        )
    if _is_technology_enabled(settings, "district_wood_chip_boiler"):
        targets.extend(
            [
                "E_district_wood_chip_boiler_generation_kWh",
                "E_district_wood_chip_boiler_fuel_input_kWh",
                "M_district_wood_chip_boiler_fuel_input_kg",
            ]
        )
    if _is_technology_enabled(settings, "district_biomass_chp"):
        targets.extend(
            [
                "E_district_biomass_chp_electric_generation_kWh",
                "E_district_biomass_chp_thermal_generation_kWh",
                "E_district_biomass_chp_fuel_input_kWh",
                "M_district_biomass_chp_fuel_input_kg",
            ]
        )
    if _is_technology_enabled(settings, "district_biogas_chp"):
        targets.extend(
            [
                "E_district_biogas_chp_electric_generation_kWh",
                "E_district_biogas_chp_thermal_generation_kWh",
                "E_district_biogas_chp_fuel_input_kWh",
                "V_district_biogas_chp_fuel_input_nm3",
            ]
        )
    if _is_technology_enabled(settings, "district_gas_chp"):
        targets.extend(
            [
                "E_district_gas_chp_electric_generation_kWh",
                "E_district_gas_chp_thermal_generation_kWh",
                "E_district_gas_chp_fuel_input_kWh",
                "V_district_gas_chp_fuel_input_m3",
            ]
        )
    if _is_technology_enabled(settings, "district_gas_boiler"):
        targets.extend(
            [
                "E_district_gas_boiler_generation_kWh",
                "E_district_gas_boiler_fuel_input_kWh",
                "V_district_gas_boiler_fuel_input_m3",
            ]
        )
    if _is_technology_enabled(settings, "district_external_heat"):
        targets.append("E_district_external_heat_generation_kWh")
    if _is_technology_enabled(settings, "district_geothermal"):
        targets.extend(
            [
                "E_district_geothermal_electric_generation_kWh",
                "E_district_geothermal_thermal_generation_kWh",
            ]
        )
    if _is_technology_enabled(settings, "district_solar_thermal"):
        targets.append("E_district_solar_thermal_generation_kWh")
    if _is_technology_enabled(settings, "district_waste_incineration"):
        targets.append("E_district_waste_incineration_generation_kWh")
    return targets


def _resolve_configured_target_base(settings: Any) -> List[str]:
    # The target slice must come from explicit settings.
    # We first honor a manual `targets` override because it is the most direct SSOT.
    # If no manual list is provided, we resolve the named profile from
    # `surrogate_train.target_profiles`. We do not silently fall back to a runtime
    # heuristic because that would hide which KPI slice is actually being learned.
    train_cfg = getattr(settings, "surrogate_train", None)
    explicit_targets = list(getattr(train_cfg, "targets", []) or [])
    if explicit_targets:
        return explicit_targets

    target_profile = str(getattr(train_cfg, "target_profile", "") or "").strip()
    if not target_profile:
        raise ValueError(
            "[surrogate_targets] Neither surrogate_train.targets nor surrogate_train.target_profile is configured."
        )

    target_profiles = getattr(train_cfg, "target_profiles", None)
    if not isinstance(target_profiles, dict):
        raise TypeError("[surrogate_targets] surrogate_train.target_profiles must be a dict.")
    if target_profile not in target_profiles:
        raise KeyError(
            f"[surrogate_targets] Unknown surrogate_train.target_profile '{target_profile}'."
        )

    profile_targets_raw = target_profiles[target_profile]
    if not isinstance(profile_targets_raw, list):
        raise TypeError(
            f"[surrogate_targets] target_profiles['{target_profile}'] must be a list of target names."
        )
    profile_targets = [str(target).strip() for target in profile_targets_raw if str(target).strip()]
    if not profile_targets:
        raise ValueError(
            f"[surrogate_targets] target_profiles['{target_profile}'] is empty after normalization."
        )
    return profile_targets


def resolve_surrogate_targets(settings: Any) -> List[str]:
    train_cfg = getattr(settings, "surrogate_train", None)
    base_targets = _resolve_configured_target_base(settings)
    append_active_technology_targets = bool(
        getattr(train_cfg, "append_active_technology_targets", False)
    )
    if append_active_technology_targets:
        # Active-technology auto-extension stays explicit behind a settings flag.
        # Focused paper profiles disable this to keep the learned KPI slice small
        # and fully inspectable.
        base_targets = list(base_targets) + _active_technology_targets(settings)
    include_objectives = bool(getattr(train_cfg, "include_objectives", False))
    obj_targets = get_selected_objective_names(settings) if include_objectives else []
    active_tariff_arm = get_active_tariff_arm(settings)
    if active_tariff_arm != "flat":
        selected_objectives = get_selected_objective_names(settings)
        if "npc_eur" in selected_objectives and "npc_eur" not in obj_targets:
            # Tariff-aware NPC cannot be reconstructed from surrogate lifetime flows
            # without hourly truth results. Force it into the surrogate target set.
            obj_targets = list(obj_targets) + ["npc_eur"]
    targets_ordered: List[str] = []
    seen = set()
    for t in list(base_targets) + list(obj_targets):
        if t not in seen:
            targets_ordered.append(t)
            seen.add(t)
    return targets_ordered


def resolve_feature_names(settings: Any) -> List[str]:
    train_cfg = getattr(settings, "surrogate_train", None)
    feature_names = list(getattr(train_cfg, "feature_names", []) or [])
    if not feature_names:
        feature_names = list(getattr(make_surrogate_train(), "feature_names", []) or [])
    required = [
        "enable_district_external_heat",
        "enable_district_gas_boiler",
        "enable_district_heat_pump",
        "enable_district_thermal_storage",
        "enable_district_wood_chip_boiler",
        "enable_district_biomass_chp",
        "enable_district_biogas_chp",
        "enable_district_gas_chp",
        "enable_district_geothermal",
        "enable_district_solar_thermal",
        "enable_district_waste_incineration",
        "reference_control_mode",
        "control_mode",
        "constant_setpoint_c",
        "day_setpoint_c",
        "night_setpoint_c",
        "day_lower_bound_c",
        "night_lower_bound_c",
        "thermflex_max_duration_h",
        "thermflex_max_events_per_day",
        # Event-response policy must participate in feature schema identity so
        # default-off vs Vienna-paper-on cannot share one static column layout.
        "thermflex_use_event_response_bounds",
        "thermflex_enforce_event_peak_bounds",
        "thermflex_enforce_event_energy_bounds",
        "thermflex_enforce_recovery_cooldown",
    ]
    for name in required:
        if name not in feature_names:
            feature_names.append(name)
    return feature_names


def resolve_feature_encoding(settings: Any) -> Dict[str, str]:
    train_cfg = getattr(settings, "surrogate_train", None)
    feature_encoding = dict(getattr(train_cfg, "feature_encoding", {}) or {})
    if feature_encoding:
        return feature_encoding
    return dict(getattr(make_surrogate_train(), "feature_encoding", {}) or {})


def build_static_feature_vector(settings: Any, profile_id: str) -> np.ndarray:
    eng_cfg = getattr(settings, "engine", None)
    features = getattr(eng_cfg, "features", None)
    activation = getattr(settings, "technology_activation", None)
    heating_control = getattr(settings, "heating_control", None)
    thermflex_cfg = getattr(getattr(settings, "constraints", None), "thermflex", None)
    active_tariff_arm = get_active_tariff_arm(settings)
    # Live event-response flags must occupy static columns (not only names) so
    # default-off vs paper-on policies produce distinct augmented X rows even
    # before family-hash / signature-hash separation.
    event_response = thermflex_event_response_policy_identity(settings)
    return np.array(
        [
            float(int(bool(getattr(features, "enable_bess", False)))),
            float(int(bool(getattr(features, "enable_v2h", False)))),
            float(int(bool(getattr(features, "enable_h2", False)))),
            float(int(bool(getattr(features, "enable_thermflex", False)))),
            float(int(bool(getattr(features, "enable_small_wind", False)))),
            float(int(bool(getattr(features, "enable_large_wind", False)))),
            float(int(bool(getattr(features, "enable_biogas_engine", False)))),
            float(int(bool(getattr(features, "enable_wood_gasifier", False)))),
            float(int(bool(getattr(activation, "district_external_heat", False)))),
            float(int(bool(getattr(activation, "district_gas_boiler", False)))),
            float(int(bool(getattr(activation, "district_heat_pump", False)))),
            float(int(bool(getattr(activation, "district_thermal_storage", False)))),
            float(int(bool(getattr(activation, "district_wood_chip_boiler", False)))),
            float(int(bool(getattr(activation, "district_biomass_chp", False)))),
            float(int(bool(getattr(activation, "district_biogas_chp", False)))),
            float(int(bool(getattr(activation, "district_gas_chp", False)))),
            float(int(bool(getattr(activation, "district_geothermal", False)))),
            float(int(bool(getattr(activation, "district_solar_thermal", False)))),
            float(int(bool(getattr(activation, "district_waste_incineration", False)))),
            float(hash_to_int(str(getattr(eng_cfg, "system_id", "unknown")))),
            float(hash_to_int(str(profile_id))),
            float(int(getattr(eng_cfg, "N_EV_total", 0))),
            float(int(getattr(eng_cfg, "N_EV_bidirectional", 0))),
            float(hash_to_int(active_tariff_arm)),
            float(hash_to_int(get_reference_control_mode(settings))),
            float(hash_to_int(get_control_mode(settings))),
            float(getattr(heating_control, "constant_setpoint_c", 0.0) or 0.0),
            float(getattr(heating_control, "day_setpoint_c", 0.0) or 0.0),
            float(getattr(heating_control, "night_setpoint_c", 0.0) or 0.0),
            float(getattr(thermflex_cfg, "day_lower_bound_c", 0.0) or 0.0),
            float(getattr(thermflex_cfg, "night_lower_bound_c", 0.0) or 0.0),
            float(getattr(thermflex_cfg, "max_flex_duration_h", 0.0) or 0.0),
            float(getattr(thermflex_cfg, "max_flex_events_per_day", 0.0) or 0.0),
            float(int(bool(event_response["use_event_response_bounds"]))),
            float(int(bool(event_response["enforce_event_peak_bounds"]))),
            float(int(bool(event_response["enforce_event_energy_bounds"]))),
            float(int(bool(event_response["enforce_recovery_cooldown"]))),
        ],
        dtype=float,
    )


def build_signature_context_payload(settings: Any, profile_id: str) -> Dict[str, Any]:
    eng_cfg = getattr(settings, "engine", None)
    features = getattr(eng_cfg, "features", None)
    activation = getattr(settings, "technology_activation", None)
    heating_control = getattr(settings, "heating_control", None)
    thermflex_cfg = getattr(getattr(settings, "constraints", None), "thermflex", None)
    dispatch_cfg = getattr(settings, "dispatch", None)
    district_heating = getattr(settings, "district_heating", None)
    # Keep event-response policy inside signature context so artifact directories
    # under Optimization/Learning scoped by signature_hash cannot collide across
    # the Settings-default-off vs Vienna-paper-on cut.
    event_response = thermflex_event_response_policy_identity(settings)
    return {
        "profile_id": str(profile_id),
        "system_id": str(getattr(eng_cfg, "system_id", "unknown") or "unknown"),
        "active_tariff_arm": get_active_tariff_arm(settings),
        "reference_control_mode": get_reference_control_mode(settings),
        "control_mode": get_control_mode(settings),
        "constant_setpoint_c": float(getattr(heating_control, "constant_setpoint_c", 0.0) or 0.0),
        "day_setpoint_c": float(getattr(heating_control, "day_setpoint_c", 0.0) or 0.0),
        "night_setpoint_c": float(getattr(heating_control, "night_setpoint_c", 0.0) or 0.0),
        "day_lower_bound_c": float(getattr(thermflex_cfg, "day_lower_bound_c", 0.0) or 0.0),
        "night_lower_bound_c": float(getattr(thermflex_cfg, "night_lower_bound_c", 0.0) or 0.0),
        "max_flex_duration_h": float(getattr(thermflex_cfg, "max_flex_duration_h", 0.0) or 0.0),
        "max_flex_events_per_day": float(getattr(thermflex_cfg, "max_flex_events_per_day", 0.0) or 0.0),
        "use_event_response_bounds": bool(event_response["use_event_response_bounds"]),
        "enforce_event_peak_bounds": bool(event_response["enforce_event_peak_bounds"]),
        "enforce_event_energy_bounds": bool(event_response["enforce_event_energy_bounds"]),
        "enforce_recovery_cooldown": bool(event_response["enforce_recovery_cooldown"]),
        "district_heating_share": float(getattr(district_heating, "share", 0.0) or 0.0),
        "dispatch_mode": str(getattr(dispatch_cfg, "mode", "unknown") or "unknown"),
        "dispatch_stochastic_enabled": bool(getattr(dispatch_cfg, "stochastic_enabled", False)),
        # ``run.tag`` is a reporting/provenance label only. It must not affect
        # surrogate compatibility because the same learned family must be reusable
        # across training, optimization, and validation runs with different tags.
        "feature_flags": {
            "enable_bess": bool(getattr(features, "enable_bess", False)),
            "enable_v2h": bool(getattr(features, "enable_v2h", False)),
            "enable_h2": bool(getattr(features, "enable_h2", False)),
            "enable_thermflex": bool(getattr(features, "enable_thermflex", False)),
            "enable_small_wind": bool(getattr(features, "enable_small_wind", False)),
            "enable_large_wind": bool(getattr(features, "enable_large_wind", False)),
            "enable_biogas_engine": bool(getattr(features, "enable_biogas_engine", False)),
            "enable_wood_gasifier": bool(getattr(features, "enable_wood_gasifier", False)),
        },
        "technology_flags": {
            "district_external_heat": bool(getattr(activation, "district_external_heat", False)),
            "district_gas_boiler": bool(getattr(activation, "district_gas_boiler", False)),
            "district_heat_pump": bool(getattr(activation, "district_heat_pump", False)),
            "district_thermal_storage": bool(getattr(activation, "district_thermal_storage", False)),
            "district_wood_chip_boiler": bool(getattr(activation, "district_wood_chip_boiler", False)),
            "district_biomass_chp": bool(getattr(activation, "district_biomass_chp", False)),
            "district_biogas_chp": bool(getattr(activation, "district_biogas_chp", False)),
            "district_gas_chp": bool(getattr(activation, "district_gas_chp", False)),
            "district_geothermal": bool(getattr(activation, "district_geothermal", False)),
            "district_solar_thermal": bool(getattr(activation, "district_solar_thermal", False)),
            "district_waste_incineration": bool(getattr(activation, "district_waste_incineration", False)),
        },
    }


def augment_features(settings: Any, X_design: np.ndarray, profile_id: str) -> np.ndarray:
    X_design = np.asarray(X_design, float)
    if X_design.ndim == 1:
        X_design = X_design.reshape(1, -1)
    static = np.tile(build_static_feature_vector(settings, profile_id).reshape(1, -1), (X_design.shape[0], 1))
    return np.hstack([X_design, static])
