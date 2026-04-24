# Building Surrogate Layer 2 Design

## Purpose

Layer 2 replaces the current reduced-order building runtime with a learned
building-response surrogate trained directly from `EnergyPlus` teacher data.

The target architecture is:

- `EnergyPlus` remains the high-fidelity teacher and truth source for building
  thermal behavior.
- `Learning/` remains the model, artifact, validation, retrain and later active
  learning layer.
- A new stateful building-response surrogate becomes the runtime building model.
- The existing dispatch/KPI surrogate remains a separate system layer above the
  building response.

The goal is not to preserve the reduced-order model as the long-term physics
layer. The goal is to retain as much `EnergyPlus` physics as practical in the
teacher data and use a learned runtime model for speed.

## Current Repo Inventory

### Existing EnergyPlus teacher path

The active teacher adapter is:

- `Technical_model/technologies/buildings/calibration/teachers/energyplus.py`

It already exports hourly teacher data and a richer plausibility hourly file.
Relevant exported or derived columns already include:

- `zone_mean_air_temperature_c`
- `site_outdoor_air_drybulb_c`
- `zone_total_heating_rate_w`
- `zone_total_heating_kwh`
- `zone_total_cooling_rate_w`
- `zone_windows_transmitted_solar_rate_w`
- `zone_windows_transmitted_solar_kwh`
- `zone_windows_total_heat_gain_rate_w`
- `zone_windows_total_heat_loss_rate_w`
- `zone_infiltration_sensible_heat_loss_kwh`
- `zone_infiltration_sensible_heat_gain_kwh`
- `zone_ventilation_sensible_heat_loss_kwh`
- `zone_ventilation_sensible_heat_gain_kwh`
- `zone_air_heat_balance_outdoor_air_loss_kwh`
- `zone_air_heat_balance_outdoor_air_gain_kwh`
- `zone_ideal_loads_outdoor_air_sensible_heating_kwh`
- `zone_ideal_loads_outdoor_air_sensible_cooling_kwh`
- `heating_setpoint_c`
- `cooling_setpoint_c`
- `internal_gains_w_m2`
- `internal_gains_total_w`
- `infiltration_ach`
- `ventilation_ach`
- `epw_ghi_wh_m2`
- `epw_dni_wh_m2`
- `epw_dhi_wh_m2`
- approximate transmission, infiltration and ventilation diagnostics

This is already close to the needed Layer-2 teacher source. The main missing
piece is a standardized transition dataset, not another high-level annual
summary.

### Existing runtime building path

The current runtime building model is centered on:

- `Technical_model/technologies/buildings/runtime_space_heat.py`
- `Technical_model/technologies/buildings/thermal_building_state.py`
- `Technical_model/technologies/buildings/thermal_flex_controller.py`

This path is stateful and explicit, but it is still reduced-order. It uses
calibrated capacity/loss parameters and simple hourly state propagation.

Layer 2 should eventually replace this runtime behavior with a learned
state-transition model. During development, a backend switch is still useful for
side-by-side validation.

### Existing Learning layer

The existing `Learning/` layer already provides reusable patterns for:

- model artifact storage
- bundle loading
- retrain decision policy
- dataset storage
- validation/holdout exports

Layer 2 should reuse those mechanisms instead of creating a separate ad hoc
model registry. The building surrogate needs a separate target family and
dataset contract from the current dispatch/KPI surrogate.

## Layer-2 Runtime Contract

The runtime call should be a one-hour state transition:

```text
state_t, exogenous_t, control_t, cohort_context -> state_t+1, q_heat_t, diagnostics_t
```

### Required inputs

- `cohort_id`
- current indoor state, at least `t_in_c`
- outdoor dry-bulb temperature
- solar radiation / transmitted solar proxy
- internal gains proxy
- infiltration and ventilation proxies where available
- heating setpoint
- lower comfort bound
- upper comfort bound if preheating is allowed
- control/event mode
- hour, month or season encodings if validation shows they add value

### Required runtime outputs

- `t_in_next_c`
- `q_heat_kwh`
- `comfort_margin_lower_k`
- `comfort_margin_upper_k`

### Diagnostic outputs

These should be available for validation and paper explanation, but do not need
to be consumed by dispatch at every call:

- `solar_gain_kwh`
- `internal_gain_kwh`
- `infiltration_loss_kwh`
- `ventilation_loss_kwh`
- `outdoor_air_loss_kwh`
- `window_heat_gain_kwh`
- `window_heat_loss_kwh`
- optional latent storage proxy if the selected model exposes it

## Teacher Dataset Contract

Create a standardized hourly transition table, for example:

- `building_response_teacher_hourly.csv`

Minimum columns:

- `teacher_id`
- `cohort_id`
- `experiment_id`
- `timestamp_local`
- `step_index`
- `t_in_c`
- `t_in_next_c`
- `t_out_c`
- `heating_setpoint_c`
- `lower_bound_c`
- `upper_bound_c`
- `control_mode`
- `event_mode`
- `event_elapsed_h`
- `event_remaining_h`
- `zone_total_heating_kwh`
- `zone_windows_transmitted_solar_kwh`
- `internal_gains_kwh`
- `zone_infiltration_sensible_heat_loss_kwh`
- `zone_ventilation_sensible_heat_loss_kwh`
- `zone_air_heat_balance_outdoor_air_loss_kwh`
- `zone_windows_total_heat_gain_kwh`
- `zone_windows_total_heat_loss_kwh`
- `epw_ghi_wh_m2`
- `epw_dni_wh_m2`
- `epw_dhi_wh_m2`
- `reference_floor_area_m2`
- `cohort_represented_gfa_m2`

The transition table must be built from `EnergyPlus` outputs with fail-fast
validation. Missing required teacher columns should stop the builder unless the
corresponding physical feature is explicitly disabled in settings.

## Learning Targets

The model should learn several central `EnergyPlus` flows, not only final heat
demand. This makes the learned model more physically constrained and easier to
debug.

### Must-have targets

- `t_in_next_c`
- `zone_total_heating_kwh`

### Strong auxiliary targets

- `zone_windows_transmitted_solar_kwh`
- `internal_gains_kwh`
- `zone_infiltration_sensible_heat_loss_kwh`
- `zone_ventilation_sensible_heat_loss_kwh`
- `zone_air_heat_balance_outdoor_air_loss_kwh`
- `zone_windows_total_heat_gain_kwh`
- `zone_windows_total_heat_loss_kwh`

### Later targets

- cooling demand if needed for summer use cases
- surface or thermal mass heat-balance proxies if exported cleanly from
  `EnergyPlus`
- learned latent state diagnostics if the model class supports them

## Model Strategy

The first useful model should be conservative:

- one shared model family across cohorts
- `cohort_id` and building descriptors as explicit inputs
- one-step training plus recursive rollout validation
- multi-output learning for indoor temperature, heating and key heat-balance
  flows

Good first candidates:

- `xgb` or sklearn-compatible multi-output regressors for one-step transitions
- a small state-space model if recursive error becomes the bottleneck
- a sequence model only after the tabular/state-transition baseline is measured

The long-term runtime should not depend on the current reduced-order equations.
However, during validation the reduced-order path should remain available as a
baseline backend until the learned model has passed rollout gates.

## Validation Gates

Layer 2 is acceptable only if it performs under recursive use, not just random
holdout rows.

Required validation:

- one-step `MAE/RMSE` for `t_in_next_c`
- one-step `MAE/RMSE` for `zone_total_heating_kwh`
- 24 h rollout error for `T_in`
- 48 h rollout error for `T_in`
- total heating error over 24 h and 48 h
- shifted/release/rebound error on event experiments
- comfort violation false negatives
- cohort-specific error tables
- separate error slices for cold, mild, sunny and low-solar days

Recommended physical sanity checks:

- stronger solar input should not increase heating demand all else equal
- higher outdoor temperature should not increase heating demand all else equal
- predicted `T_in` should remain stable under recursive no-event operation
- missing teacher heat-balance targets should fail before training

## Integration Plan

1. Add a teacher-transition dataset builder under the existing building
   calibration layer.
2. Add a building-surrogate dataset/model family to `Learning/` using the
   existing artifact and validation patterns.
3. Add explicit settings for the building runtime backend, for example:
   `rom`, `building_surrogate`, `energyplus_teacher_test`.
4. Keep dispatch/KPI surrogate separate from the building surrogate.
5. Run side-by-side validation on existing EnergyPlus experiments before any
   dispatch path is allowed to consume the building surrogate.
6. Remove the reduced-order runtime dependency only after Layer 2 passes the
   rollout and comfort gates.

## Open Decisions

- Whether the first model should be one shared multi-cohort model or one model
  per cohort. Current recommendation: shared model with explicit cohort and
  geometry descriptors.
- Whether to include `1 K` cooldown in V1. Current recommendation: start with
  reference and `upper_only`, then add cooldown after the transition builder is
  stable.
- Whether to export additional `EnergyPlus` surface heat-balance variables.
  Current recommendation: only add them if the existing flow targets do not
  explain rollout or rebound error sufficiently.
- How uncertainty is represented for Layer 2. Current recommendation: add
  uncertainty after the deterministic transition contract and rollout
  validation are stable, then connect uncertain points to teacher re-runs.

