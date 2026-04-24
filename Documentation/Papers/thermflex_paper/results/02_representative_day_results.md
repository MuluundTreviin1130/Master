# Representative-Day Results

## Purpose

This block captures the day-type dependence of thermflex value.

Primary raw sources:

- [constant_thermflex_representative_day_summary_20260403](/c:/Users/Philipp%20Thunshirn/Desktop/PhD/Python%20model/Master/Optimization/run/results/Vienna/gold/constant_thermflex_representative_day_summary_20260403)
- [representative_days.md](/c:/Users/Philipp%20Thunshirn/Desktop/PhD/Python%20model/Master/Optimization/run/results/Vienna/gold/dh_thermflex_run_20260403_140316/representative_days/representative_days.md)

## Day-Type Operationalization

The representative days are:

- `winter_peak_heat_day = 2023-01-17`
- `winter_price_spike_day = 2023-01-24`
- `winter_sunny_heat_day = 2023-12-04`
- `winter_typical_day = 2023-01-02`
- `shoulder_typical_day = 2023-10-31`

These are not arbitrary days. They were selected as an explicit mix of:

- rule-based extremes
- medoid-like typical days

## Main Findings

There is no globally dominant thermflex policy across all day types.

Observed pattern:

- `lb21p0_dur24_evt1` performs strongly on:
  - `winter_price_spike_day`
  - `winter_typical_day`
  - `shoulder_typical_day`
- `constant_no_thermflex` remains best on:
  - `winter_peak_heat_day` for operating cost and CO2
  - `winter_sunny_heat_day` for operating cost and CO2

From the current summary:

- `shoulder_typical_day`
  - best operating cost: `lb21p0_dur24_evt1`
  - best CO2: `lb21p0_dur24_evt1`
- `winter_price_spike_day`
  - best operating cost: `lb21p0_dur24_evt1`
  - best CO2: `lb21p0_dur24_evt1`
- `winter_typical_day`
  - best operating cost: `lb21p0_dur24_evt1`
  - best CO2: `lb21p0_dur24_evt1`
- `winter_peak_heat_day`
  - best operating cost: `constant_no_thermflex`
  - best CO2: `constant_no_thermflex`
- `winter_sunny_heat_day`
  - best operating cost: `constant_no_thermflex`
  - best CO2: `constant_no_thermflex`

## Interpretation

This is one of the strongest result blocks in the paper.

It supports the main claim that:

- thermflex is a useful operational flexibility lever
- but its value is strongly day-type dependent
- therefore the paper should not claim one universal policy as best in all
  circumstances

## Immediate Paper Use

This block should feed:

- the representative-day figure
- the main discussion argument on day-type dependence
- the method justification for using representative days
