from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, Optional, Tuple


@dataclass(frozen=True)
class DistrictGasCHPOperatingPointConfig:
    """One explicit CHP operating point in the future piecewise power-heat region."""

    name: str
    eta_el: float
    eta_th: float


DistrictGasCHPOperatingModeModel = Literal["fixed_ratio", "piecewise_power_heat_v1"]
DistrictGasCHPPowerPriorityMode = Literal["free", "price_spike_gated_v1"]


@dataclass
class DistrictGasCHPConfig:
    """Technical SSOT for a district-heating gas CHP (CCGT with heat extraction)."""

    installed_kw_el_max: Optional[float] = None
    operating_mode_model: DistrictGasCHPOperatingModeModel = "fixed_ratio"
    power_priority_mode: DistrictGasCHPPowerPriorityMode = "free"
    power_priority_price_quantile: float = 0.9
    eta_el: Optional[float] = None
    eta_th: Optional[float] = None
    operating_points_v1: Tuple[DistrictGasCHPOperatingPointConfig, ...] = ()
    min_partload: Optional[float] = None
    fuel_lhv_kwh_per_m3: Optional[float] = None
    scheduled_downtime_days_per_year: float = 7.0
    scheduled_downtime_start_day_of_year: int = 200


def make_district_gas_chp() -> DistrictGasCHPConfig:
    return DistrictGasCHPConfig(
        operating_mode_model="fixed_ratio",
        power_priority_mode="free",
        power_priority_price_quantile=0.9,
        operating_points_v1=(
            # V1 Wien-/anlagenplausibler CCGT proxy:
            # power-led operation keeps district heat positive but relatively low.
            DistrictGasCHPOperatingPointConfig(name="power_led", eta_el=0.55, eta_th=0.30),
            # Mixed point is the simplest explicit midpoint between the two edge modes.
            DistrictGasCHPOperatingPointConfig(name="mixed", eta_el=0.425, eta_th=0.425),
            # Heat-led operation preserves total efficiency while shifting output toward DH.
            DistrictGasCHPOperatingPointConfig(name="heat_led", eta_el=0.30, eta_th=0.55),
        ),
    )
