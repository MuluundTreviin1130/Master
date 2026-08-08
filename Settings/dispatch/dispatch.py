from __future__ import annotations

from dataclasses import dataclass, field
from typing import List


@dataclass
class DispatchConfig:
    """Top-level dispatch configuration.

    The hourly resolution is fixed for now. ``mode`` selects the active
    operational policy. The stochastic fields are intentionally already part of
    the SSOT so deterministic day-ahead and later two-stage dispatch use the
    same settings block.
    """

    mode: str = "heuristic"
    horizon_h: int = 24

    stochastic_enabled: bool = False
    scenario_source: str = "historical"
    n_raw_scenarios: int = 200
    n_reduced_scenarios: int = 10
    reduction_method: str = "fast_forward"
    distance_metric: str = "standardized_euclidean"
    scenario_feature_keys: List[str] = field(
        default_factory=lambda: [
            "ambient_temperature_c",
            "grid_import_price",
            "district_space_heat_demand",
            "co2_price_eur_per_tco2",
        ]
    )
    risk_measure: str = "expected_value"
    historical_weather_path: str = (
        r"C:\Users\Philipp Thunshirn\Desktop\PhD\Daten\Messstationen Stundendaten v2 Datensatz_20160101T0000_20260324T1300.csv"
    )
    historical_pvgis_path: str = r"C:\Users\Philipp Thunshirn\Desktop\PhD\Daten\PV_GIS_2016-23.csv"
    historical_day_ahead_root: str = r"C:\Users\Philipp Thunshirn\Desktop\PhD\Daten\Day-Ahead Preise"
    historical_gas_price_csv: str = ""
    historical_gas_day_ahead_price_csv: str = (
        r"C:\Users\Philipp Thunshirn\Desktop\PhD\Python model\Master\Data\profiles\common\gas\oegpi_monthly_daily_proxy_2020_2025.csv"
    )
    historical_gas_balance_price_csv: str = ""
    historical_co2_price_csv: str = (
        r"C:\Users\Philipp Thunshirn\Desktop\PhD\Python model\Master\Data\profiles\common\co2\ets_monthly_daily_proxy_2020_2025.csv"
    )
    historical_min_year: int = 2020
    historical_max_year: int = 2025
    historical_heating_season_only: bool = True
    # When False (default), peak-boiler fuel cost uses the economics SSOT mix
    # price derived from district_gas_boiler.fuel_eur_per_m3. When True, the
    # boiler reuses the historical gas day-ahead series (sensitivity contract).
    historical_gas_boiler_uses_day_ahead_price: bool = False

    objective_components: List[str] = field(
        default_factory=lambda: [
            "grid_import_cost",
            "grid_export_revenue",
            "fuel_cost",
            "co2_cost",
            "variable_opex",
        ]
    )


def make_dispatch() -> DispatchConfig:
    return DispatchConfig()
