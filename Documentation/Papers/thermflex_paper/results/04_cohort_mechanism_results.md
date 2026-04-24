# Cohort Mechanism Results

## Purpose

This block explains who actually uses thermflex.

Primary raw sources:

- [constant_thermflex_cohort_utilization_summary.md](/c:/Users/Philipp%20Thunshirn/Desktop/PhD/Python%20model/Master/Optimization/run/results/Vienna/gold/paper_dispatch_comparison_20260403_131344/constant_thermflex_cohort_utilization_summary.md)
- [nonres_2000_2014_debug_summary.md](/c:/Users/Philipp%20Thunshirn/Desktop/PhD/Python%20model/Master/Optimization/run/results/Vienna/gold/dh_thermflex_run_20260403_140316/nonres_2000_2014_debug/nonres_2000_2014_debug_summary.md)

## Main Findings

The cohort layer confirms that global policy settings are filtered by cohort
physics and day-specific demand.

Important examples:

- `residential_2000_2014` gains strongly from longer durations
  - `dur4`: `734.0 MWh shifted`
  - `dur6`: `1504.7 MWh shifted`
  - `dur8`: `1522.0 MWh shifted`
- `residential_1990_2000` saturates much earlier
  - `dur4`: `113.1 MWh shifted`
  - `dur6`: `112.0 MWh shifted`
  - `dur8`: `115.2 MWh shifted`
- `non_residential_2000_2014` is inactive in the analyzed slice
  - `shifted = 0`
  - `active_cap = 0`
  - this is a day-type effect, not a general cohort bug

## What This Means

This block supports two paper messages:

1. a single global thermflex policy is a simplification
2. but it is not a physically blind simplification, because cohort-level bounds
   and demand conditions already create differentiated use

## Non-Residential Clarification

The zero-use case for `non_residential_2000_2014` on the old paper slice should
not be presented as a structural failure of the cohort.

The debug result shows:

- the cohort has annual space heat
- it is not active on that specific day
- the paper should frame this as a day-type and demand-state effect

## Immediate Paper Use

This block should feed:

- one cohort mechanism figure or appendix figure
- the discussion on heterogeneity
- the limitation statement on non-residential maturity
