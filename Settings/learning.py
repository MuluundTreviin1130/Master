from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List


@dataclass
class ValidationGateConfig:
    enabled: bool = True
    auto_validate_after_retrain: bool = True
    auto_promote_to_eligible: bool = True
    auto_remediate_on_blocked: bool = True
    max_remediation_rounds: int = 2
    require_full_target_coverage: bool = True
    fail_on_nan_predictions: bool = True
    holdout_frac: float = 0.2
    min_pass_share: float = 0.9
    critical_target_min_r2: float = 0.95
    critical_target_max_rel_mae_percent: float = 8.0
    secondary_target_min_r2: float = 0.85
    secondary_target_max_rel_mae_percent: float = 15.0
    critical_blocks: List[str] = field(
        default_factory=lambda: ["dispatch_core", "co2_operational", "thermflex_operational"]
    )
    critical_targets: List[str] = field(default_factory=list)
    remediation_append_growth_factor: float = 2.0
    remediation_max_append_samples: int = 200
    remediation_min_failed_targets_for_retry: int = 1
    remediation_critical_growth_multiplier: float = 1.5
    remediation_stop_on_zero_pass_share: bool = True
    remediation_stop_after_critical_fail_rounds: int = 2


@dataclass
class LearningConfig:
    auto_retrain_mode: str = "assist"  # strict | assist | auto
    allow_auto_append: bool = True
    allow_auto_refit: bool = True
    allow_auto_new_family: bool = False
    allow_auto_full_rebuild: bool = False
    force_native_retrain: bool = False
    force_append_then_train: bool = False
    max_auto_append_samples: int = 50
    max_auto_refit_walltime_min: int = 30
    resolution: str = "1h"
    horizon_type: str = "full_year"  # full_year | representative_periods
    time_series_schema: List[str] = field(default_factory=lambda: ["load", "pv_generation", "T_outdoor"])
    location_mode: str = "dataset_context"
    dispatch_model_id: str = "default"
    target_blocks: List[str] = field(
        default_factory=lambda: [
            "core_energy",
            "dispatch_core",
            "dispatch_penalties",
            "co2_operational",
            "thermflex_operational",
            "bess",
            "h2",
            "thermflex",
            "district_heating",
            "wind",
            "biomass",
        ]
    )
    target_block_targets: Dict[str, List[str]] = field(
        default_factory=lambda: {
            "core_energy": [
                "E_import_grid_kWh",
                "E_export_grid_kWh",
                "E_import_ec_pv_kWh",
                "E_import_ec_ev_kWh",
                "E_export_ec_pv_kWh",
                "E_total_load_kWh",
                "PV_generation_kWh",
                "E_ev_charged_kWh",
                "E_ev_discharged_kWh",
                "npc_eur",
                "climate_change",
            ],
            "dispatch_core": [
                "dispatch_operating_cost_eur",
                "E_district_gas_boiler_generation_kWh",
                "E_district_gas_chp_thermal_generation_kWh",
                "E_district_gas_chp_electric_generation_kWh",
                "E_district_heat_pump_thermal_generation_kWh",
                "E_district_external_heat_generation_kWh",
                "E_district_waste_incineration_generation_kWh",
                "dh_unserved_heat",
            ],
            "dispatch_penalties": [
                "dispatch_objective_eur",
                "dispatch_penalty_total_eur",
                "unserved_penalty_eur",
                "temperature_violation_penalty_eur",
                "thermflex_activation_penalty_eur",
                "spill_penalty_eur",
                "fuel_cost_eur",
                "co2_cost_eur",
                "variable_opex_eur",
                "grid_import_cost_eur",
                "grid_export_revenue_eur",
            ],
            "co2_operational": [
                "district_gas_boiler_co2_t",
                "district_gas_chp_co2_t",
                "co2_emissions_total_t",
            ],
            "thermflex_operational": [
                "thermflex_shifted_space_heat_kwh",
                "dh_total_peak_change_kw",
                "district_gas_boiler_peak_kw",
                "thermflex_active_member_hours_total",
                "thermflex_temperature_violation_degree_hours_total",
                "thermflex_t_in_min_c",
                "thermflex_t_in_max_c",
                "thermflex_t_in_terminal_c",
            ],
            "bess": [
                "bess_cyclic_violation_kwh",
            ],
            "h2": [
                "E_h2_charge_elec_kWh",
                "E_h2_discharge_elec_kWh",
                "h2_cyclic_violation_kwh",
            ],
            "thermflex": [
                "E_hp_flex_elec_kWh",
            ],
            "district_heating": [
                "E_district_heat_pump_thermal_generation_kWh",
                "E_district_heat_pump_electricity_kWh",
                "E_district_thermal_storage_charge_kWh",
                "E_district_thermal_storage_discharge_kWh",
                "E_district_thermal_storage_losses_kWh",
                "E_district_wood_chip_boiler_generation_kWh",
                "E_district_wood_chip_boiler_fuel_input_kWh",
                "M_district_wood_chip_boiler_fuel_input_kg",
                "E_district_biomass_chp_electric_generation_kWh",
                "E_district_biomass_chp_thermal_generation_kWh",
                "E_district_biomass_chp_fuel_input_kWh",
                "M_district_biomass_chp_fuel_input_kg",
                "E_district_biogas_chp_electric_generation_kWh",
                "E_district_biogas_chp_thermal_generation_kWh",
                "E_district_biogas_chp_fuel_input_kWh",
                "V_district_biogas_chp_fuel_input_nm3",
                "E_district_gas_chp_electric_generation_kWh",
                "E_district_gas_chp_thermal_generation_kWh",
                "E_district_gas_chp_fuel_input_kWh",
                "V_district_gas_chp_fuel_input_m3",
                "E_district_gas_boiler_generation_kWh",
                "E_district_gas_boiler_fuel_input_kWh",
                "V_district_gas_boiler_fuel_input_m3",
                "E_district_external_heat_generation_kWh",
                "E_district_geothermal_electric_generation_kWh",
                "E_district_geothermal_thermal_generation_kWh",
                "E_district_solar_thermal_generation_kWh",
                "E_district_waste_incineration_generation_kWh"
            ],
            "wind": [
                "E_small_wind_generation_kWh",
                "E_large_wind_generation_kWh",
            ],
            "biomass": [
                "E_biogas_generation_kWh",
                "E_wood_gasifier_generation_kWh",
                "E_wood_gasifier_fuel_input_kWh",
            ],
        }
    )
    registry_path: str = "Learning/registry/registry.json"
    legacy_inventory_path: str = "Learning/bootstrap/legacy_inventory.json"
    legacy_classification_path: str = "Learning/bootstrap/legacy_classification.json"
    legacy_import_manifest_path: str = "Learning/bootstrap/legacy_import_manifest.json"
    active_model_root: str = "Learning/models"
    active_dataset_root: str = "Learning/datasets"
    archive_root: str = "Learning/archive"
    primary_artifact_filename: str = "surrogate_bundle.joblib"
    primary_meta_filename: str = "surrogate_bundle.meta.json"
    legacy_artifact_filename: str = "surrogate_rf.joblib"
    legacy_meta_filename: str = "surrogate_rf.meta.json"
    validation_root: str = "Optimization/run/validation"
    legacy_validation_root: str = "Optimization/run/validation_old"
    validation_gate: ValidationGateConfig = field(default_factory=ValidationGateConfig)


def make_learning() -> LearningConfig:
    cfg = LearningConfig()
    if not cfg.validation_gate.critical_targets:
        derived_targets: List[str] = []
        seen: set[str] = set()
        for block_name in cfg.validation_gate.critical_blocks:
            for target in cfg.target_block_targets.get(block_name, []):
                if target not in seen:
                    derived_targets.append(target)
                    seen.add(target)
        cfg.validation_gate.critical_targets = derived_targets
    return cfg
