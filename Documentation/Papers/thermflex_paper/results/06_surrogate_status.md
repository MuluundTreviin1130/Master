# Surrogate Status

## Purpose

This note records the current surrogate status for the paper and prevents the
surrogate layer from being described more strongly than the holdout evidence
supports.

Primary raw source:

- [surrogate_20260402_203051](/c:/Users/Philipp%20Thunshirn/Desktop/PhD/Python%20model/Master/Optimization/run/results/Vienna/vienna_ref2023_dh_day_night_thermflex_surrogate_opt_l96/surrogate_20260402_203051)

## Current Main Surrogate Slice

The strongest current optimization-core surrogate slice is:

- `vienna_ref2023_dh_day_night_thermflex_surrogate_opt_l96`
- model: `xgb`
- requested teacher samples: `96`
- feasible teacher samples: `55`
- infeasible teacher samples: `41`
- infeasible share: `42.7 %`

The holdout summary for this run is:

- median `R2 = 0.747`
- median `RMSE = 879214.63`

## Holdout Interpretation by Target

The surrogate is currently strong on several operationally relevant targets:

- `co2_emissions_total_t`: `R2 = 0.827`
- `thermflex_peak_change_kw`: `R2 = 0.747`
- `E_district_heat_pump_thermal_generation_kWh`: `R2 = 0.923`
- `E_district_biomass_chp_thermal_generation_kWh`: `R2 = 0.928`
- `E_district_gas_chp_thermal_generation_kWh`: `R2 = 0.955`
- `E_district_gas_boiler_generation_kWh`: `R2 = 0.834`

The surrogate is currently weak on some paper-facing targets:

- `dispatch_operating_cost_eur`: `R2 ~ 0.000`
- `thermflex_shifted_space_heat_kwh`: `R2 = -0.157`
- `dispatch_penalty_total_eur`: `R2 = 0.262`
- `dispatch_objective_eur`: `R2 = 0.330`

## What This Means for the Paper

The surrogate can be presented as:

- a useful accelerator for search and candidate ranking
- a good predictor for several dispatch-mix and emissions targets
- a supporting layer for exploration, not the final truth layer

The surrogate should not currently be presented as:

- a uniformly accurate replacement for teacher evaluation on all paper KPIs
- the primary evidence source for operating cost or shifted-heat claims

## Immediate Paper Use

This block should support:

- a short methods note on surrogate-assisted exploration
- the limitation that final paper conclusions remain tied to gold runs
- a clear distinction between search acceleration and final evaluation
