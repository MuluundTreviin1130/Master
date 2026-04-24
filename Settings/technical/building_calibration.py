from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from Data.profiles import location_openmeteo_weather_archives, location_usage_profiles
from Data.thermal_archetypes.Vienna.windows import build_vienna_window_typology_values


PROJECT_ROOT = Path(__file__).resolve().parents[2]
_WINDOW_TYPLOGY_VALUES = build_vienna_window_typology_values()
_RESIDENTIAL_WINDOW_TYPLOGY_VALUES = dict(_WINDOW_TYPLOGY_VALUES["residential_by_period"])


@dataclass(frozen=True)
class BuildingCalibrationExperimentTemplate:
    """Declarative SSOT for one offline calibration experiment."""

    key: str
    role: str
    start_month: int
    start_day: int
    start_hour: int
    duration_h: int
    control_mode: str
    event_type: str = "none"
    event_start_offset_h: int = 0
    event_duration_h: int = 0
    event_setpoint_delta_k: float = 0.0
    post_event_observation_h: int = 0
    notes: tuple[str, ...] = ()


@dataclass
class BuildingCalibrationConfig:
    """SSOT for offline building-calibration sidecar tooling."""

    enabled: bool = False
    location: str = "Vienna"
    pseudo_epw_weather_csv: str = location_openmeteo_weather_archives["Vienna"]
    pseudo_epw_representative_years_json: str = str(
        Path(location_openmeteo_weather_archives["Vienna"]).with_name(
            "openmeteo_representative_years_2016_2025.json"
        )
    )
    pseudo_epw_output_dir: str = str(
        (PROJECT_ROOT / "Data" / "profiles" / "Vienna" / "weather" / "epw").resolve()
    )
    pseudo_epw_template_path: str = str(
        (
            Path.home()
            / "Downloads"
            / "AUT_WI_Wien-Innere.Stadt.110340_TMYx.2011-2025"
            / "AUT_WI_Wien-Innere.Stadt.110340_TMYx.2011-2025.epw"
        ).resolve()
    )
    pseudo_epw_year_roles: tuple[str, ...] = ("average_year", "cold_year", "mild_year")
    pseudo_epw_extra_year_roles: dict[str, int] = field(
        default_factory=lambda: {"historical_2023": 2023}
    )
    usage_profile_excel_path: str = location_usage_profiles
    usage_profile_sheet_name: str = "usage_profiles"
    usage_profile_timebase: str = "annual_8760"
    usage_profile_leap_day_policy: str = "repeat_feb28"
    required_usage_profile_columns: tuple[str, ...] = (
        "H",
        "Betriebszeit_-",
        "Pers/m2",
        "Qi Sommer W/m2",
        "Qi Winter W/m2",
        "Luftwechsel_Anlage_1_h",
        "Luftwechsel_Infiltration_1_h",
        "Warmwasserbedarf_W_m2",
    )
    local_standard_utc_offset_hours: int = 1
    horizontal_ir_model: str = "clark_allen"
    total_to_opaque_sky_cover_mode: str = "same_as_total"
    unsupported_fields_policy: str = "epw_missing_codes"
    energyplus_executable_path: str = str(
        (
            PROJECT_ROOT
            / "Technical_model"
            / "technologies"
            / "buildings"
            / "calibration"
            / "_vendor"
            / "EnergyPlus-26.1.0"
            / "EnergyPlus-26.1.0-6f2e40d102-Windows-x86_64"
            / "energyplus.exe"
        ).resolve()
    )
    energyplus_idf_version: str = "26.1"
    energyplus_smoke_role: str = "average_year"
    energyplus_smoke_output_dir: str = str(
        (PROJECT_ROOT / "Technical_model" / "technologies" / "buildings" / "calibration" / "_smoke").resolve()
    )
    teacher_runs_output_dir: str = str(
        (PROJECT_ROOT / "Technical_model" / "technologies" / "buildings" / "calibration" / "_teacher_runs").resolve()
    )
    teacher_plausibility_batch_output_dir: str = str(
        (
            PROJECT_ROOT
            / "Technical_model"
            / "technologies"
            / "buildings"
            / "calibration"
            / "_teacher_runs"
            / "_plausibility_batches"
        ).resolve()
    )
    teacher_plausibility_batch_default_experiments: tuple[str, ...] = (
        "winter_reference_week",
        "winter_free_float_72h",
    )
    teacher_plausibility_batch_summary_csv: str = "teacher_plausibility_batch_summary.csv"
    teacher_plausibility_batch_summary_json: str = "teacher_plausibility_batch_summary.json"
    teacher_geometry_solar_review_csv: str = "teacher_geometry_solar_review.csv"
    teacher_geometry_solar_review_json: str = "teacher_geometry_solar_review.json"
    teacher_event_batch_output_dir: str = str(
        (
            PROJECT_ROOT
            / "Technical_model"
            / "technologies"
            / "buildings"
            / "calibration"
            / "_teacher_runs"
            / "_event_batches"
        ).resolve()
    )
    teacher_event_batch_default_experiments: tuple[str, ...] = (
        "winter_event_reference_96h",
        "winter_recovery_reference_120h",
        "winter_preheat_event",
        "winter_cutback_event",
        "winter_recovery_event",
    )
    teacher_event_batch_summary_csv: str = "teacher_event_batch_summary.csv"
    teacher_event_batch_summary_json: str = "teacher_event_batch_summary.json"
    reduced_order_fit_output_dir: str = str(
        (
            PROJECT_ROOT
            / "Technical_model"
            / "technologies"
            / "buildings"
            / "calibration"
            / "_reduced_order_fits"
        ).resolve()
    )
    reduced_order_fit_summary_csv: str = "reduced_order_fit_summary.csv"
    reduced_order_fit_summary_json: str = "reduced_order_fit_summary.json"
    reduced_order_fit_default_reference_experiment_id: str = "winter_reference_week"
    reduced_order_fit_default_free_float_experiment_id: str = "winter_free_float_72h"
    event_response_fit_output_dir: str = str(
        (
            PROJECT_ROOT
            / "Technical_model"
            / "technologies"
            / "buildings"
            / "calibration"
            / "_event_response_fits"
        ).resolve()
    )
    event_response_fit_summary_csv: str = "event_response_fit_summary.csv"
    event_response_fit_summary_json: str = "event_response_fit_summary.json"
    event_response_preheat_reference_experiment_id: str = "winter_event_reference_96h"
    event_response_cutback_reference_experiment_id: str = "winter_event_reference_96h"
    event_response_recovery_reference_experiment_id: str = "winter_recovery_reference_120h"
    event_response_preheat_experiment_id: str = "winter_preheat_event"
    event_response_cutback_experiment_id: str = "winter_cutback_event"
    event_response_recovery_experiment_id: str = "winter_recovery_event"
    event_response_temperature_recovery_tolerance_c: float = 0.1
    event_response_unrecovered_sentinel_h: float = -1.0
    calibrated_v1_json_path: str = str(
        (PROJECT_ROOT / "Data" / "thermal_archetypes" / "Vienna" / "calibrated_v1.json").resolve()
    )
    calibrated_v1_python_path: str = str(
        (PROJECT_ROOT / "Data" / "thermal_archetypes" / "Vienna" / "calibrated_v1.py").resolve()
    )
    teacher_hourly_filename: str = "teacher_hourly.csv"
    teacher_meta_filename: str = "teacher.meta.json"
    teacher_plausibility_hourly_filename: str = "teacher_plausibility_hourly.csv"
    teacher_plausibility_summary_filename: str = "teacher_plausibility_summary.json"
    teacher_plausibility_plot_filename: str = "teacher_plausibility_overview.png"
    teacher_reference_gfa_m2: float = 1000.0
    # These V1 optical properties are the explicit bridge between the source-backed
    # residential TABULA window typology classes and the simple-glazing teacher model.
    # The typology classes themselves come from Austrian TABULA/EPISCOPE.
    #
    # Numeric SHGC values are now anchored to similar TABULA window-type evidence from
    # other European country reports where Austria does not provide direct g-values:
    # - single glazing ~ 0.85
    # - double glazing ~ 0.75-0.76
    # - double low-e / heat-protection glazing ~ 0.60-0.63
    # - triple low-e / high-performance glazing ~ 0.50
    #
    # Visible transmittance remains a documented V1 companion proxy because the same
    # cross-country TABULA material does not provide a comparably clean VT ladder.
    teacher_window_typology_optics: dict[str, dict[str, object]] = field(
        default_factory=lambda: {
            str(record["window_typology_class"]): {
                "shgc": float(record["g_value"]),
                "visible_transmittance": float(record["visible_transmittance"]),
                "source": f"{str(record['g_value_source'])};{str(record['visible_transmittance_source'])}",
            }
            for record in _RESIDENTIAL_WINDOW_TYPLOGY_VALUES.values()
        }
    )
    # Non-residential window typology is still not source-backed in the repo SSOT.
    # Keeping this as an explicit config branch avoids silent fallback behaviour.
    teacher_non_residential_simple_glazing_mode: str = "global_v1"
    teacher_non_residential_simple_glazing_shgc: float = 0.60
    teacher_non_residential_simple_glazing_visible_transmittance: float = 0.60
    teacher_non_residential_simple_glazing_source: str = (
        "non_residential_v1_global_simple_glazing_no_source_backed_window_typology"
    )
    teacher_simple_glazing_shgc: float = 0.6
    teacher_simple_glazing_visible_transmittance: float = 0.6
    teacher_pilot_default_cohort_id: str = "residential_1975_1990"
    teacher_pilot_default_experiment_id: str = "winter_reference_week"
    teacher_setup_output_dir: str = str(
        (PROJECT_ROOT / "Data" / "profiles" / "Vienna" / "weather" / "calibration_setup").resolve()
    )
    teacher_input_output_json: str = str(
        (
            PROJECT_ROOT
            / "Data"
            / "profiles"
            / "Vienna"
            / "weather"
            / "calibration_setup"
            / "teacher_inputs_v1.json"
        ).resolve()
    )
    experiment_library_output_json: str = str(
        (
            PROJECT_ROOT
            / "Data"
            / "profiles"
            / "Vienna"
            / "weather"
            / "calibration_setup"
            / "experiment_library_v1.json"
        ).resolve()
    )
    experiment_templates: tuple[BuildingCalibrationExperimentTemplate, ...] = (
        BuildingCalibrationExperimentTemplate(
            key="winter_reference_week",
            role="average_year",
            start_month=1,
            start_day=15,
            start_hour=0,
            duration_h=168,
            control_mode="reference",
            notes=(
                "Baseline winter reference week on the average representative year.",
                "Used as main comparison anchor before event-style flexibility experiments.",
            ),
        ),
        BuildingCalibrationExperimentTemplate(
            key="winter_free_float_72h",
            role="cold_year",
            start_month=1,
            start_day=15,
            start_hour=0,
            duration_h=72,
            control_mode="free_float",
            notes=(
                "Free-float cooling-down experiment on the cold representative year.",
            ),
        ),
        BuildingCalibrationExperimentTemplate(
            key="winter_event_reference_96h",
            role="cold_year",
            start_month=1,
            start_day=15,
            start_hour=0,
            duration_h=96,
            control_mode="reference",
            notes=(
                "Cold-year event baseline without setpoint perturbation.",
                "Used as direct comparison anchor for preheat and cutback event runs.",
            ),
        ),
        BuildingCalibrationExperimentTemplate(
            key="winter_preheat_event",
            role="cold_year",
            start_month=1,
            start_day=15,
            start_hour=0,
            duration_h=96,
            control_mode="reference",
            event_type="preheat",
            event_start_offset_h=24,
            event_duration_h=12,
            event_setpoint_delta_k=2.0,
            post_event_observation_h=24,
            notes=(
                "Temporary preheating event around the winter reference trajectory.",
            ),
        ),
        BuildingCalibrationExperimentTemplate(
            key="winter_cutback_event",
            role="cold_year",
            start_month=1,
            start_day=15,
            start_hour=0,
            duration_h=96,
            control_mode="reference",
            event_type="cutback",
            event_start_offset_h=24,
            event_duration_h=12,
            event_setpoint_delta_k=-2.0,
            post_event_observation_h=24,
            notes=(
                "Temporary cutback event around the winter reference trajectory.",
            ),
        ),
        BuildingCalibrationExperimentTemplate(
            key="winter_recovery_reference_120h",
            role="cold_year",
            start_month=1,
            start_day=15,
            start_hour=0,
            duration_h=120,
            control_mode="reference",
            notes=(
                "Cold-year recovery baseline without setpoint perturbation.",
                "Used as direct comparison anchor for the recovery event run.",
            ),
        ),
        BuildingCalibrationExperimentTemplate(
            key="winter_recovery_event",
            role="cold_year",
            start_month=1,
            start_day=15,
            start_hour=0,
            duration_h=120,
            control_mode="reference",
            event_type="recovery_probe",
            event_start_offset_h=24,
            event_duration_h=24,
            event_setpoint_delta_k=-2.0,
            post_event_observation_h=48,
            notes=(
                "Cutback and recovery probe used to quantify rebound and recovery speed.",
            ),
        ),
        BuildingCalibrationExperimentTemplate(
            key="shoulder_reference_week",
            role="mild_year",
            start_month=10,
            start_day=1,
            start_hour=0,
            duration_h=168,
            control_mode="reference",
            notes=(
                "Shoulder-season reference week on the mild representative year.",
            ),
        ),
        BuildingCalibrationExperimentTemplate(
            key="repday_winter_peak_heat_day",
            role="historical_2023",
            start_month=1,
            start_day=17,
            start_hour=0,
            duration_h=24,
            control_mode="reference",
            notes=(
                "Teacher reference day aligned with the selected 2023 winter_peak_heat_day.",
            ),
        ),
        BuildingCalibrationExperimentTemplate(
            key="repday_winter_price_spike_day",
            role="historical_2023",
            start_month=1,
            start_day=24,
            start_hour=0,
            duration_h=24,
            control_mode="reference",
            notes=(
                "Teacher reference day aligned with the selected 2023 winter_price_spike_day.",
            ),
        ),
        BuildingCalibrationExperimentTemplate(
            key="repday_winter_sunny_heat_day",
            role="historical_2023",
            start_month=12,
            start_day=4,
            start_hour=0,
            duration_h=24,
            control_mode="reference",
            notes=(
                "Teacher reference day aligned with the selected 2023 winter_sunny_heat_day.",
            ),
        ),
        BuildingCalibrationExperimentTemplate(
            key="repday_winter_typical_day",
            role="historical_2023",
            start_month=1,
            start_day=2,
            start_hour=0,
            duration_h=24,
            control_mode="reference",
            notes=(
                "Teacher reference day aligned with the selected 2023 winter_typical_day.",
            ),
        ),
        BuildingCalibrationExperimentTemplate(
            key="repday_shoulder_typical_day",
            role="historical_2023",
            start_month=10,
            start_day=31,
            start_hour=0,
            duration_h=24,
            control_mode="reference",
            notes=(
                "Teacher reference day aligned with the selected 2023 shoulder_typical_day.",
            ),
        ),
    )
    notes: list[str] = field(
        default_factory=lambda: [
            "Pseudo-EPW builder stays offline and sidecar-only; not part of the runtime dispatch loop.",
            "Open-Meteo weather is the current data SSOT for pseudo-EPW V1.",
            "Template EPW is used only as file-format/header anchor, not as hourly weather truth.",
            "First true teacher runs stay on a normalized reference GFA to avoid city-scale geometry in EnergyPlus.",
            "The shared usage-profile workbook is currently interpreted as a normal-year 8760 annual profile.",
        ]
    )


def make_building_calibration_config() -> BuildingCalibrationConfig:
    return BuildingCalibrationConfig()
