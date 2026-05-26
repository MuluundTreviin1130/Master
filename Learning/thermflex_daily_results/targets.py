from __future__ import annotations

from Learning.thermflex_daily_results.schema import TARGET_COLUMNS

# These are intentionally result-oriented targets rather than table-oriented
# outputs so that one learned layer can later feed multiple paper artifacts.
TARGET_GROUPS: dict[str, tuple[str, ...]] = {
    "cost_and_co2": (
        "dispatch_operating_cost_eur_delta",
        "dispatch_operating_cost_pct_change",
        "co2_emissions_total_t_delta",
        "co2_emissions_total_pct_change",
    ),
    "peak_boiler": (
        "district_gas_boiler_peak_kw_delta",
        "district_gas_boiler_peak_pct_change",
        "district_gas_boiler_generation_kwh_delta",
        "district_gas_boiler_generation_pct_change",
    ),
    "thermflex": (
        "thermflex_shifted_space_heat_kwh",
        "thermflex_rebound_kwh",
        "thermflex_rebound_over_shifted_pct",
        "dh_total_peak_change_kw",
        "thermflex_peak_change_kw",
        "joint_savings_score",
    ),
}


ALL_TARGET_COLUMNS: tuple[str, ...] = TARGET_COLUMNS
