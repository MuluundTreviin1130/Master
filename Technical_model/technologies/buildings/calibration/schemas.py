from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass(frozen=True)
class CalibrationWeatherRoleInput:
    role: str
    year: int
    epw_path: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class CalibrationTeacherCohortInput:
    cohort_id: str
    sector: str
    construction_period: str
    thermal_archetype_key: str
    window_typology_class: str | None
    window_pane_count: int | None
    window_glazing_family: str | None
    window_frame_type: str | None
    window_has_low_e: bool | None
    window_has_inert_gas_fill: bool | None
    window_has_thermal_break: bool | None
    window_g_value: float | None
    window_visible_transmittance: float | None
    window_data_source_note: str | None
    glazing_source: str | None
    solar_shading_assumption: str | None
    teacher_simple_glazing_shgc: float
    teacher_simple_glazing_visible_transmittance: float
    teacher_simple_glazing_source: str
    include_hotwater: bool
    load_profile_mix: dict[str, float]
    dh_connected_share_override: float | None
    represented_gfa_m2: float
    represented_volume_m3: float
    conditioned_floor_m2: float
    floor_exposed_area_m2: float
    room_height_m: float
    annual_heat_target_kwh: float
    annual_space_heat_target_kwh: float
    annual_hotwater_target_kwh: float
    annual_electricity_official_kwh: float
    annual_electricity_target_kwh: float
    u_wall: float
    u_window: float
    u_roof: float
    u_floor: float
    wall_area_m2: float
    window_area_total_m2: float
    roof_area_m2: float
    floor_area_m2: float
    runtime_ua_w_per_k: float
    heat_capacity_wh_per_k: float
    t_min_k: float
    t_max_k: float

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class CalibrationTeacherInputBundle:
    schema_version: str
    location: str
    building_stock_source: str
    thermal_archetypes_source: str
    source_file_paths: list[str]
    usage_profile_path: str
    usage_profile_sheet_name: str
    usage_profile_required_columns: list[str]
    representative_years_json: str
    weather_roles: list[CalibrationWeatherRoleInput]
    cohorts: list[CalibrationTeacherCohortInput]
    notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["weather_roles"] = [item.to_dict() for item in self.weather_roles]
        payload["cohorts"] = [item.to_dict() for item in self.cohorts]
        return payload


@dataclass(frozen=True)
class CalibrationExperimentSpec:
    experiment_id: str
    role: str
    calendar_year: int
    epw_path: str
    start_local: str
    end_local: str
    duration_h: int
    control_mode: str
    event_type: str
    event_start_offset_h: int
    event_duration_h: int
    event_setpoint_delta_k: float
    post_event_observation_h: int
    notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class CalibrationExperimentLibrary:
    schema_version: str
    location: str
    representative_years_json: str
    experiments: list[CalibrationExperimentSpec]
    notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["experiments"] = [item.to_dict() for item in self.experiments]
        return payload


@dataclass(frozen=True)
class CalibrationReducedOrderFitResult:
    cohort_id: str
    reference_experiment_id: str
    free_float_experiment_id: str
    reference_hours_used: int
    free_float_steps_used: int
    fitted_total_loss_coefficient_w_per_k: float
    fitted_transmission_loss_coefficient_w_per_k: float
    fitted_ventilation_loss_coefficient_w_per_k_approx: float
    fitted_infiltration_loss_coefficient_w_per_k_approx: float
    fitted_effective_heat_capacity_wh_per_k: float
    fitted_tau_h: float
    fitted_total_loss_coefficient_w_per_m2k: float
    fitted_transmission_loss_coefficient_w_per_m2k: float
    fitted_effective_heat_capacity_wh_per_m2k: float
    fitted_transmission_scale_vs_seed: float
    fitted_air_loss_scale_vs_seed_approx: float
    seed_ua_reference_w_per_k: float
    seed_heat_capacity_wh_per_k: float
    total_loss_vs_seed_ua_ratio: float
    transmission_vs_seed_ua_ratio: float
    heat_capacity_vs_seed_ratio: float
    reference_heating_rmse_w: float
    reference_heating_mae_w: float
    free_float_temperature_rmse_c: float
    free_float_temperature_mae_c: float
    notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class CalibrationEventResponseResult:
    cohort_id: str
    preheat_reference_experiment_id: str
    cutback_reference_experiment_id: str
    recovery_reference_experiment_id: str
    preheat_experiment_id: str
    cutback_experiment_id: str
    recovery_experiment_id: str
    preheat_added_energy_kwh: float
    preheat_peak_excess_kw: float
    preheat_temperature_uplift_max_c: float
    preheat_temperature_uplift_end_c: float
    preheat_post_event_payback_kwh: float
    cutback_shed_energy_kwh: float
    cutback_peak_shed_kw: float
    cutback_temperature_drop_max_c: float
    cutback_temperature_drop_end_c: float
    recovery_rebound_energy_kwh: float
    recovery_peak_rebound_kw: float
    recovery_overshoot_max_c: float
    recovery_temperature_gap_at_event_end_c: float
    recovery_temperature_gap_after_observation_c: float
    recovery_time_to_reference_h: float
    notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
