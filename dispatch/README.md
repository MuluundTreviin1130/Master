# Dispatch

This package contains dispatch building blocks independent from the engine
implementation. The goal is a single dispatch entry point with multiple modes,
while reusing the existing repo naming and output keys.

Current structure:

- `core/`
  - shared `DispatchInput` / `DispatchResult` contracts and dispatch-mode registry
- `metrics/`
  - reusable Thermflex/reporting helpers shared by multiple modes
- `policies/ec_first_policy.py`
  - EC-first helper functions used by the legacy heuristic path.
- `modes/heuristic.py`
  - Wrapper that normalizes legacy heuristic outputs into the shared dispatch
    contract.
- `modes/milp_day_ahead.py`
  - Deterministic hourly day-ahead MILP.
- `modes/milp_two_stage.py`
  - Stochastic dispatch entry point. Current implementation is an
    expected-value scenario wrapper around the day-ahead MILP; explicit
    non-anticipativity is the next step.
- `scenarios/`
  - Historical scenario generation and reduction helpers for the stochastic
    dispatch path.
  - `hdd.py` is the Celsius heating-degree-hour contract. Profile `T_outdoor`
    is Kelvin; two-stage HDD scaling must receive `ambient_temperature_c` in °C.
