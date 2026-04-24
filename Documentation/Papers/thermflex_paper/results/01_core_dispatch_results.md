# Core Dispatch Results

## Purpose

This block is the main deterministic result layer for the paper.

Primary raw source:

- [paper_dispatch_comparison_20260403_131344](/c:/Users/Philipp%20Thunshirn/Desktop/PhD/Python%20model/Master/Optimization/run/results/Vienna/gold/paper_dispatch_comparison_20260403_131344)

## Main Comparison

The deterministic constant-policy block shows the core mechanism clearly:

- `constant_no_thermflex` has:
  - very high unserved heat
  - no shifted heat
  - no peak relief
- activated thermflex cases remove unserved heat and shift several gigawatt-hours
  of space-heating demand

For the current constant-policy sensitivity bundle:

- `constant_no_thermflex`
  - `dispatch_operating_cost_eur = 18.223 Mio`
  - `co2_emissions_total_t = 11871.27`
  - `dh_unserved_heat_kwh = 1.412 GWh`
- `lb21p0_dur24_evt1`
  - `dispatch_operating_cost_eur = 17.362 Mio`
  - `co2_emissions_total_t = 12288.66`
  - `dh_unserved_heat_kwh = 0`
  - `thermflex_shifted_space_heat_kwh = 6.714 GWh`
  - `thermflex_rebound_kwh = 5.117 GWh`
  - `thermflex_peak_change_kw = -686.56 MW`

Interpretation:

- thermflex has a strong operational effect in the DH system
- the main gain is not only cost, but also:
  - elimination of unserved heat
  - temporal shifting of space heat
  - peak reduction

## Constant-Policy Sensitivity

The constant-policy sensitivity shows three robust messages:

1. `lower_bound` matters.
- `lb22p5` upper-only cases are consistently weaker than `lb21p0`.

2. `duration` matters more than high event counts.
- moving from `dur1` to longer durations changes results materially
- `evt24` does not add value relative to `evt1` in the tested `dur24` case

3. there is no single scalar "best" objective without context.
- some settings improve operating cost
- some improve CO2
- some maximize shifted energy

For `lower = 21.0 C`, `events = 1`, the duration trend is:

- `dur1`: `17.653 Mio EUR`, `12380.20 t CO2`, `6.607 GWh shifted`
- `dur2`: `17.636 Mio EUR`, `12356.68 t CO2`, `6.331 GWh shifted`
- `dur4`: `17.511 Mio EUR`, `12460.45 t CO2`, `6.360 GWh shifted`
- `dur6`: `17.493 Mio EUR`, `12471.55 t CO2`, `6.315 GWh shifted`
- `dur8`: `17.487 Mio EUR`, `12463.99 t CO2`, `6.370 GWh shifted`
- `dur24`: `17.362 Mio EUR`, `12288.66 t CO2`, `6.714 GWh shifted`

Interpretation:

- the global duration cap is not irrelevant
- but its system effect is non-monotonic and should not be read as "more hours is
  always better on every KPI"

## Immediate Paper Use

This block should feed:

- the main constant thermflex figure
- the main KPI table
- the policy-sensitivity appendix figure
