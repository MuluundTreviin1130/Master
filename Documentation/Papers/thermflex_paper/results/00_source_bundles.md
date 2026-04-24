# Source Bundles

The current paper-facing results layer is built from five raw result bundles.

## Core Dispatch Bundle

- Path:
  [paper_dispatch_comparison_20260403_131344](/c:/Users/Philipp%20Thunshirn/Desktop/PhD/Python%20model/Master/Optimization/run/results/Vienna/gold/paper_dispatch_comparison_20260403_131344)
- Used for:
  - constant thermflex comparison
  - constant-policy sensitivity
  - cohort utilization summary

## Representative-Day Summary Bundle

- Path:
  [constant_thermflex_representative_day_summary_20260403](/c:/Users/Philipp%20Thunshirn/Desktop/PhD/Python%20model/Master/Optimization/run/results/Vienna/gold/constant_thermflex_representative_day_summary_20260403)
- Used for:
  - day-type ranking
  - main argument that thermflex value is day-type dependent

## Representative-Day Selector Bundle

- Path:
  [dh_thermflex_run_20260403_140316](/c:/Users/Philipp%20Thunshirn/Desktop/PhD/Python%20model/Master/Optimization/run/results/Vienna/gold/dh_thermflex_run_20260403_140316)
- Used for:
  - operationalization of representative day types
  - non-residential debug
  - teacher/cohort plots

## Biobjective Gold Bundle

- Path:
  [biobj_gold_candidates_20260403_093146](/c:/Users/Philipp%20Thunshirn/Desktop/PhD/Python%20model/Master/Optimization/run/results/Vienna/gold/biobj_gold_candidates_20260403_093146)
- Used for:
  - candidate selection
  - biobjective framing
  - day-ahead feasible gold representatives

## Two-Stage Robustness Bundle

- Path:
  [20260416_211739_biobj_co2_end_two_stage_gap_debug](/c:/Users/Philipp%20Thunshirn/Desktop/PhD/Python%20model/Master/Optimization/run/results/Vienna/gold/biobj_gold_candidates_20260403_093146/20260403_093214_biobj_co2_end_gold_day_ahead/20260416_211739_biobj_co2_end_two_stage_gap_debug)
- Used for:
  - explicit historical `48 -> 6` robustness proof for one leading thermflex candidate
