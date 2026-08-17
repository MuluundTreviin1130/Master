from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List


def _default_surrogate_feature_names() -> List[str]:
    return [
        "pv_kwp",
        "bess_kwh",
        "ely_kw",
        "h2_tank_kwh",
        "fc_kw",
        "enable_bess",
        "enable_v2h",
        "enable_h2",
        "enable_thermflex",
        "enable_small_wind",
        "enable_large_wind",
        "enable_biogas_engine",
        "enable_wood_gasifier",
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
        "system_id",
        "profile_id",
        "N_EV_total",
        "N_EV_bidirectional",
        "tariff_arm",
        "reference_control_mode",
        "control_mode",
        "constant_setpoint_c",
        "day_setpoint_c",
        "night_setpoint_c",
        "day_lower_bound_c",
        "night_lower_bound_c",
        "thermflex_max_duration_h",
        "thermflex_max_events_per_day",
        "thermflex_use_event_response_bounds",
        "thermflex_enforce_event_peak_bounds",
        "thermflex_enforce_event_energy_bounds",
        "thermflex_enforce_recovery_cooldown",
    ]


def _default_surrogate_feature_encoding() -> Dict[str, str]:
    return {
        "system_id": "hash32",
        "profile_id": "hash32",
        "tariff_arm": "hash32",
        "reference_control_mode": "hash32",
        "control_mode": "hash32",
    }


def _full_system_default_targets() -> List[str]:
    # This broad historical profile remains available for generic experiments.
    # It is intentionally wider than the paper-facing thermflex optimization cut.
    return [
        "E_import_grid_kWh",
        "E_export_grid_kWh",
        "E_total_load_kWh",
        "E_district_heat_pump_thermal_generation_kWh",
        "E_district_heat_pump_electricity_kWh",
        "E_district_thermal_storage_charge_kWh",
        "E_district_thermal_storage_discharge_kWh",
        "E_district_thermal_storage_losses_kWh",
        "E_district_external_heat_generation_kWh",
        "E_district_waste_incineration_generation_kWh",
        "E_district_biomass_chp_electric_generation_kWh",
        "E_district_biomass_chp_thermal_generation_kWh",
        "E_district_biomass_chp_fuel_input_kWh",
        "E_district_gas_chp_electric_generation_kWh",
        "E_district_gas_chp_thermal_generation_kWh",
        "E_district_gas_chp_fuel_input_kWh",
        "E_district_gas_boiler_generation_kWh",
        "E_district_gas_boiler_fuel_input_kWh",
        "district_gas_chp_co2_t",
        "district_gas_boiler_co2_t",
        "co2_emissions_total_t",
        "dispatch_operating_cost_eur",
        "dispatch_objective_eur",
        "dispatch_penalty_total_eur",
        "fuel_cost_eur",
        "co2_cost_eur",
        "variable_opex_eur",
        "grid_import_cost_eur",
        "grid_export_revenue_eur",
        "unserved_penalty_eur",
        "temperature_violation_penalty_eur",
        "thermflex_activation_penalty_eur",
        "spill_penalty_eur",
        "dh_unserved_heat",
        "thermflex_shifted_space_heat_kwh",
        "thermflex_active_member_hours_total",
        "thermflex_temperature_violation_degree_hours_total",
        "thermflex_t_in_min_c",
        "thermflex_t_in_max_c",
        "bess_cyclic_violation_kwh",
        "h2_cyclic_violation_kwh",
    ]


def _dispatch_publish_core_targets() -> List[str]:
    # This narrower profile is the active paper/optimization target slice.
    # It keeps only the KPI and dispatch-mix fields that drive:
    # 1. ranking quality for optimization,
    # 2. publishable dispatch comparison tables,
    # 3. thermflex behavior interpretation.
    return [
        "dispatch_operating_cost_eur",
        "dispatch_objective_eur",
        "dispatch_penalty_total_eur",
        "co2_emissions_total_t",
        "dh_unserved_heat",
        "thermflex_shifted_space_heat_kwh",
        "thermflex_additional_space_heat_kwh",
        "thermflex_rebound_kwh",
        "thermflex_peak_change_kw",
        "dh_total_peak_change_kw",
        "district_gas_boiler_peak_kw",
        "thermflex_active_member_hours_total",
        "thermflex_temperature_violation_degree_hours_total",
        "thermflex_t_in_min_c",
        "thermflex_t_in_max_c",
        "E_district_heat_pump_thermal_generation_kWh",
        "E_district_thermal_storage_charge_kWh",
        "E_district_thermal_storage_discharge_kWh",
        "E_district_external_heat_generation_kWh",
        "E_district_biomass_chp_thermal_generation_kWh",
        "E_district_gas_chp_thermal_generation_kWh",
        "E_district_gas_boiler_generation_kWh",
    ]


def _dispatch_optimization_core_targets() -> List[str]:
    # This is the narrowest active surrogate slice for the DH thermflex optimizer.
    # It drops targets that are constant in the current feasible region or mainly
    # useful for ex-post paper narration, and keeps the quantities that drive:
    # 1. optimization ranking,
    # 2. CO2 trade-offs,
    # 3. the thermal dispatch mix.
    return [
        "dispatch_operating_cost_eur",
        "dispatch_objective_eur",
        "dispatch_penalty_total_eur",
        "co2_emissions_total_t",
        "thermflex_shifted_space_heat_kwh",
        "thermflex_peak_change_kw",
        "dh_total_peak_change_kw",
        "district_gas_boiler_peak_kw",
        "thermflex_temperature_violation_degree_hours_total",
        "E_district_heat_pump_thermal_generation_kWh",
        "E_district_biomass_chp_thermal_generation_kWh",
        "E_district_gas_chp_thermal_generation_kWh",
        "E_district_gas_boiler_generation_kWh",
    ]


def _default_target_profiles() -> Dict[str, List[str]]:
    return {
        "full_system_default": _full_system_default_targets(),
        "dispatch_publish_core": _dispatch_publish_core_targets(),
        "dispatch_optimization_core": _dispatch_optimization_core_targets(),
    }


@dataclass
class SurrogateTrainConfig:
    holdout_frac: float = 0.2
    targets: List[str] = field(default_factory=list)
    target_profile: str = "full_system_default"
    target_profiles: Dict[str, List[str]] = field(default_factory=_default_target_profiles)
    append_active_technology_targets: bool = True
    include_objectives: bool = True
    model_params: Dict[str, Any] = field(default_factory=dict)
    teacher_infeasible_policy: str = "drop_and_audit"  # "drop_and_audit" | "fail"
    teacher_min_feasible_samples: int = 8
    teacher_max_infeasible_share: float = 0.5
    # Optional surrogate-only feasibility screen for optimization runs.
    # This is explicit and disabled by default. When enabled, the active
    # optimization override must also declare the matching constraint name in
    # `constraints.names`; the runtime does not silently inject constraints.
    feasibility_screen_enabled: bool = False
    feasibility_screen_constraint_name: str = "surrogate_feasible_probability_guard"
    feasibility_screen_neighbors: int = 9
    feasibility_screen_min_feasible_probability: float = 0.60
    feasibility_screen_min_labeled_samples: int = 24
    feasibility_screen_min_infeasible_samples: int = 8

    # Feature configuration for signature building
    feature_names: List[str] = field(default_factory=_default_surrogate_feature_names)
    feature_encoding: Dict[str, str] = field(default_factory=_default_surrogate_feature_encoding)

    # Teacher evaluation parallelization
    teacher_backend: str = "none"  # "processes", "threads", or "none"
    teacher_n_workers: int = 1
    teacher_batch_size: int = 32


def make_surrogate_train() -> SurrogateTrainConfig:
    """Default surrogate training config.

    Empfehlungen fuer bessere Qualitaet:
    - model_params['n_estimators']: 300-800 fuer gute Qualitaet
    - holdout_frac: 0.2 ist Standard (20% fuer Validierung)
    - teacher_n_workers: 0 = auto (nutzt alle CPUs - 1)
    """

    return SurrogateTrainConfig(
        holdout_frac=0.2,
        targets=[],
        target_profile="full_system_default",
        target_profiles=_default_target_profiles(),
        append_active_technology_targets=True,
        include_objectives=True,
        model_params={},
        teacher_infeasible_policy="drop_and_audit",
        teacher_min_feasible_samples=8,
        teacher_max_infeasible_share=0.5,
        feasibility_screen_enabled=False,
        feasibility_screen_constraint_name="surrogate_feasible_probability_guard",
        feasibility_screen_neighbors=9,
        feasibility_screen_min_feasible_probability=0.60,
        feasibility_screen_min_labeled_samples=24,
        feasibility_screen_min_infeasible_samples=8,
        feature_names=_default_surrogate_feature_names(),
        feature_encoding=_default_surrogate_feature_encoding(),
        teacher_backend="none",
        teacher_n_workers=1,
        teacher_batch_size=32,
    )
