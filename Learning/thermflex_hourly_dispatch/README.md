# ThermFlex Hourly Dispatch Learning

This layer prepares hourly dispatch-flow truth for the ThermFlex surrogate path.

It is separate from `thermflex_hourly_mechanism` on purpose:

- `thermflex_hourly_mechanism` learns cohort heat, indoor-temperature and
  ThermFlex activity mechanics.
- `thermflex_hourly_dispatch` learns hourly district dispatch source-stack
  effects, especially gas CHP and gas boiler flows.

The intended downstream contract is:

```text
policy + daily/hourly context + REF hourly dispatch state
  -> hourly REF-vs-FLEX source-flow deltas
  -> reconstructed daily cost and CO2 KPIs
```

Raw hourly outputs remain in their source run folders under
`Optimization/run/results/.../daily_thermflex_screen_*/heating_season_hourly_dispatch.csv`.
Reusable ML datasets are registered through `Learning/datasets/`.

Time-key contract: every loaded row must satisfy
`date == timestamp.normalize()` and `hour_index == timestamp.hour`.
Context joins use `timestamp`; uniqueness, dedupe, and daily grouping use
`(date, hour_index)`. Mismatches fail fast instead of silently corrupting
features or holdout buckets.
