# Two-Stage Robustness Results

## Purpose

This block captures the historical stochastic robustness check.

Primary raw source:

- [20260416_211739_biobj_co2_end_two_stage_gap_debug](/c:/Users/Philipp%20Thunshirn/Desktop/PhD/Python%20model/Master/Optimization/run/results/Vienna/gold/biobj_gold_candidates_20260403_093146/20260403_093214_biobj_co2_end_gold_day_ahead/20260416_211739_biobj_co2_end_two_stage_gap_debug)

## What Is Proven Here

The current result does not mean that `milp_two_stage` becomes the new main
search path. It proves something narrower and more useful for this paper:

- the `day_ahead -> two_stage` bridge is now operationally closed for a leading
  thermflex candidate
- the historical `48 -> 6` stochastic slice solves to `optimal`
- `milp_two_stage` can therefore be used as a historical robustness check

## Closed Gap

The two-stage closure required two concrete fixes:

1. `milp_two_stage` had to export the same member-level thermflex hourly contract
   as `milp_day_ahead`.
2. the historical CO2 proxy had to be separated cleanly from the gas-price loader
   in the scenario builder.

## Current Explicit Result

For `biobj_co2_end`:

- `raw48_red6`
  - `status = ok`
  - `eval_s = 2392.99`
  - `dispatch_objective_eur = 51.656 Mio`
  - `dispatch_operating_cost_eur = 6.318 Mio`
  - `dispatch_penalty_total_eur = 45.338 Mio`

This run is not yet the full reduced-scenario sensitivity block. It is the
proof-of-closure run for the full target scenario width.

## Interpretation

The paper can now state:

- deterministic representative-day and policy results remain the main analytical
  path
- a historical stochastic robustness layer exists and is operational
- the method no longer rests on a broken `two_stage` bridge

## Immediate Paper Use

This block should feed:

- the methods section on historical robustness
- an optional compact robustness table
- the limitations section, where `two_stage` remains secondary but no longer
  "unresolved"
