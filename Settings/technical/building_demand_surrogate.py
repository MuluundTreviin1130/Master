"""SSOT for the Vienna EnergyPlus demand-surrogate training contract."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class BuildingDemandSurrogateConfig:
    """Training and artifact contract for useful heating/cooling emulation.

    v2 exists because v1 tracked winter/summer well but leaked off-season demand
    and mixed heating/cooling near the outdoor-temperature switch. The MES needs
    both the seasonal shape and near-zero hours, not only annual R².
    """

    experiment_id: str = "annual_reference_2023"
    model_bundle_name: str = "vienna_building_demand_annual_reference_2023_v2"
    schema_version: str = "vienna_building_demand_annual_reference_v2"
    n_splits: int = 4
    random_state: int = 2040
    max_iter: int = 700
    learning_rate: float = 0.05
    max_leaf_nodes: int = 159
    l2_regularization: float = 0.01
    # Hurdle gate: regress magnitude, then zero hours the classifier treats as off.
    # Threshold is chosen on the train fold only; it is not tuned on holdout.
    use_on_off_gate: bool = True
    on_threshold_kwh_per_m2: float = 1e-9
    gate_threshold_grid: tuple[float, ...] = (
        0.10, 0.15, 0.20, 0.25, 0.30, 0.35, 0.40, 0.45, 0.50,
        0.55, 0.60, 0.65, 0.70, 0.75, 0.80, 0.85, 0.90,
    )
    # Penalise predicted energy only on physically off hours (see training leak mask).
    # Score the gate on true-on energy recall, not year-round R²: winter R² otherwise
    # pushes the threshold to 0.8 and zeros April/May heating.
    gate_offseason_leak_penalty: float = 2.0
    classifier_max_iter: int = 300
    classifier_learning_rate: float = 0.05
    classifier_max_leaf_nodes: int = 63
    classifier_l2_regularization: float = 0.05
    use_setpoint_drive_features: bool = True
    use_ua_drive_features: bool = True
    use_monotonic_constraints: bool = True
    # Extra weight on small-but-positive hours so the switch is not dominated by
    # winter zeros. Peaks get a separate boost; they must not stay at weight 1.
    # 4.0 / 0.90 still left the city heating peak about 8 % low in the paper week.
    shoulder_weight_boost: float = 1.0
    peak_weight_boost: float = 8.0
    peak_quantile: float = 0.85


def make_building_demand_surrogate_config() -> BuildingDemandSurrogateConfig:
    return BuildingDemandSurrogateConfig()
