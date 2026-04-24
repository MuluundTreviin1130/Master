from __future__ import annotations

from dataclasses import dataclass

from Settings.data.building_stock import BuildingStockConfig
from Settings.data.energy_potentials import EnergyPotentialsConfig
from Settings.data.impacts import ImpactsConfig
from Settings.data.thermal_archetypes import ThermalArchetypesConfig
from Settings.constraints import Constraints
from Settings.dispatch.dispatch import DispatchConfig
from Settings.engines.engine import EngineConfig
from Settings.engines.gating import GatingConfig
from Settings.market.market import MarketConfig
from Settings.learning import LearningConfig
from Settings.optimization.optimizer import OptimizerConfig
from Settings.reporting.reporting import ReportingConfig
from Settings.run.run import RunConfig
from Settings.optimization.sampler import SamplerConfig
from Settings.run.scheduler import SchedulerConfig
from Settings.surrogate.surrogate import SurrogateConfig
from Settings.surrogate.train import SurrogateTrainConfig
from Settings.problem.bounds import Bounds
from Settings.problem.feasibility.verification import FeasibilityGateConfig
from Settings.problem.hypervolume import HypervolumeConfig
from Settings.problem.objectives import Objectives
from Settings.technical.bess import BESSConfig
from Settings.technical.biogas_engine import BiogasEngineConfig
from Settings.technical.building_calibration import BuildingCalibrationConfig
from Settings.technical.district_biogas_chp import DistrictBiogasCHPConfig
from Settings.technical.district_biomass_chp import DistrictBiomassCHPConfig
from Settings.technical.district_external_heat import DistrictExternalHeatConfig
from Settings.technical.district_gas_boiler import DistrictGasBoilerConfig
from Settings.technical.district_gas_chp import DistrictGasCHPConfig
from Settings.technical.district_heating import DistrictHeatingConfig
from Settings.technical.district_heat_pump import DistrictHeatPumpConfig
from Settings.technical.district_thermal_storage import DistrictThermalStorageConfig
from Settings.technical.district_geothermal import DistrictGeothermalConfig
from Settings.technical.district_solar_thermal import DistrictSolarThermalConfig
from Settings.technical.district_waste_incineration import DistrictWasteIncinerationConfig
from Settings.technical.district_wood_chip_boiler import DistrictWoodChipBoilerConfig
from Settings.technical.full_load_hours import FullLoadHoursConfig
from Settings.technical.heating_control import HeatingControlConfig
from Settings.technical.hydrogen import HydrogenConfig
from Settings.technical.large_wind import LargeWindConfig
from Settings.technical.run_of_river_hydro import RunOfRiverHydroConfig
from Settings.technical.small_wind import SmallWindConfig
from Settings.technical.technology_activation import TechnologyActivationConfig
from Settings.technical.thermal import ThermalConfig
from Settings.technical.v2h import V2HConfig
from Settings.technical.wood_gasifier import WoodGasifierConfig
from Settings.validation.holdout import ValidationConfig


@dataclass
class Settings:
    """Top-level settings model (SSOT)."""

    run: RunConfig
    engine: EngineConfig
    bounds: Bounds
    objectives: Objectives
    constraints: Constraints
    feasibility: FeasibilityGateConfig
    hypervolume: HypervolumeConfig
    sampler: SamplerConfig
    optimizer: OptimizerConfig
    reporting: ReportingConfig
    surrogate_train: SurrogateTrainConfig
    surrogate: SurrogateConfig
    gating: GatingConfig
    scheduler: SchedulerConfig
    learning: LearningConfig
    validation: ValidationConfig
    market: MarketConfig
    dispatch: DispatchConfig
    building_stock: BuildingStockConfig
    thermal_archetypes: ThermalArchetypesConfig
    building_calibration: BuildingCalibrationConfig
    thermal: ThermalConfig
    heating_control: HeatingControlConfig
    bess: BESSConfig
    hydrogen: HydrogenConfig
    v2h: V2HConfig
    small_wind: SmallWindConfig
    large_wind: LargeWindConfig
    run_of_river_hydro: RunOfRiverHydroConfig
    biogas_engine: BiogasEngineConfig
    district_heating: DistrictHeatingConfig
    technology_activation: TechnologyActivationConfig
    district_heat_pump: DistrictHeatPumpConfig
    district_thermal_storage: DistrictThermalStorageConfig
    district_biogas_chp: DistrictBiogasCHPConfig
    district_biomass_chp: DistrictBiomassCHPConfig
    district_external_heat: DistrictExternalHeatConfig
    district_gas_boiler: DistrictGasBoilerConfig
    district_gas_chp: DistrictGasCHPConfig
    district_solar_thermal: DistrictSolarThermalConfig
    district_geothermal: DistrictGeothermalConfig
    district_waste_incineration: DistrictWasteIncinerationConfig
    district_wood_chip_boiler: DistrictWoodChipBoilerConfig
    full_load_hours: FullLoadHoursConfig
    wood_gasifier: WoodGasifierConfig
    energy_potentials: EnergyPotentialsConfig
    impacts: ImpactsConfig
