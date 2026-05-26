# ThermFlex Hourly Mechanism Learning

This sublayer holds the first hourly ThermFlex mechanism surrogate path.

## Responsibility

- Read explicit hourly cohort-utilization truth exported from replayed gold runs.
- Merge that truth with the canonical Vienna-2023 hourly input context.
- Build reusable hourly datasets for ThermFlex mechanism learning.
- Train narrow mechanism models that target the within-day preheat / cutback /
  rebound behavior which the daily surrogate struggles to reconstruct.

`Optimization` remains responsible for producing the physical dispatch truth.
`Learning` is responsible for the ML-ready hourly contract, grouped validation
and model artifacts.

Current target ownership for this layer is registered centrally in
[Learning/model_target_matrix.py](../model_target_matrix.py). That matrix is
the explicit SSOT for:

- which hourly family currently owns which KPI targets,
- which model artifact is currently preferred,
- and whether a family-specific KPI postprocessor is part of the preferred path.

`tau` is now also an explicit hourly policy feature in this layer. The builder
reads `dh_bus_inertia_tau_h` directly from the override's dispatch settings and
fails fast if that metadata is missing. That only makes the contract explicit;
the model will benefit from it once the truth basis actually spans multiple
`tau` values.

## Why a Separate Hourly Layer

The daily ThermFlex path already works reasonably for:

- heat-cost KPIs
- some boiler KPIs
- parts of the CO2 story

But the stubborn mechanism targets:

- `thermflex_shifted_space_heat_kwh`
- `thermflex_rebound_kwh`

are likely too compressed on pure day level. This hourly layer therefore keeps
the mechanism problem separate instead of forcing the daily contract to do both
aggregation and mechanism recovery at once.

## First V1 Contract

One row per:

```text
case_label × cohort_key × timestamp
```

Feature groups:

- policy descriptors:
  - lower bound
  - max duration
  - max events
  - dispatch bus-inertia `tau`
  - case label
- cohort descriptors:
  - cohort key
  - floor area
  - member count
- hourly canonical context:
  - outdoor temperature
  - irradiance / solargains
  - hourly district demand for that cohort
  - hourly market and fuel/carbon prices
- reference-side mechanism context:
  - `cohort_q_heat_ref_kwh`
  - hour-of-day and day-of-year position

First mechanism targets:

- `cohort_q_delta_kwh`
- `cohort_preheat_extra_kwh`
- `cohort_cutback_shed_kwh`
- `cohort_temperature_violation_degree_h`
- `cohort_flex_active_member_share`
- `cohort_t_in_weighted_mean_c`

These targets are narrow on purpose: the goal is first to test whether hourly
learning tracks the mechanism better than the daily path.

## Current Status

The first hourly truth basis is now broader than the original single-bundle
seed:

- reusable hourly exports are discovered from both
  - `constant_thermflex_cohort_utilization_hourly.csv`
  - `thermflex_cohort_utilization_hourly.csv`
- missing generic hourly exports can be hydrated from existing
  `selected_runs.json` manifests via
  - [hydrate_thermflex_cohort_utilization_from_selected_runs.py](../../Optimization/run/analysis/hydrate_thermflex_cohort_utilization_from_selected_runs.py)
- older figure-oriented `paper_mechanism_bundle_*` folders can now also be
  hydrated into the same generic hourly truth contract via
  - [hydrate_thermflex_cohort_utilization_from_mechanism_bundles.py](../../Optimization/run/analysis/hydrate_thermflex_cohort_utilization_from_mechanism_bundles.py)
- the current curated hourly family
  - `Learning/datasets/8d1b317881d2deeb567f3934ecbea12f79f13dea10c47554e2c9cafde8894ea6/`
  contains
  - `3072` hourly rows
  - `16` explicit thermflex run dirs
  - `5` source bundles

The latest explicit tests show:

- broad `mechanism_core` profile:
  - model:
    - `Learning/models/thermflex_hourly_mechanism_xgb_mechanism_core_8d1b317881d2/`
  - grouped holdout:
    - `mean R2 ~ 0.00`
  - positive but still modest:
    - `cohort_q_delta_kwh ~ 0.10`
    - `cohort_preheat_extra_kwh ~ 0.05`
    - `cohort_cutback_shed_kwh ~ 0.10`
    - `cohort_temperature_violation_degree_h ~ 0.27`
  - weak:
    - `cohort_flex_active_member_share`
    - `cohort_t_in_weighted_mean_c`

- narrower absolute-energy profile:
  - model:
    - `Learning/models/thermflex_hourly_mechanism_xgb_mechanism_energy_2435c3708d46/`
  - grouped holdout:
    - `mean R2 ~ 0.13`

- narrower area-normalized energy profile:
  - model:
    - `Learning/models/thermflex_hourly_mechanism_xgb_mechanism_energy_intensive_f8f5fa261ac2/`
  - grouped holdout:
    - `mean R2 ~ 0.20`
  - strongest individual targets:
    - `cohort_preheat_extra_wh_per_m2 ~ 0.32`
    - `cohort_temperature_violation_degree_h ~ 0.27`

- segmented constant-family area-normalized profile:
  - dataset:
    - `Learning/datasets/6fc7ad11f8bae814f2e29bff77ecea84c51425aa23a23d8f786e1ee7c8c960a5/`
  - model:
    - `Learning/models/thermflex_hourly_mechanism_xgb_mechanism_energy_intensive_6fc7ad11f8ba/`
  - grouped holdout:
    - `mean R2 ~ 0.34`
  - strongest individual targets:
    - `cohort_temperature_violation_degree_h ~ 0.88`
    - `cohort_cutback_shed_wh_per_m2 ~ 0.29`
    - `cohort_q_delta_wh_per_m2 ~ 0.16`
  - interpretation:
    - explicit `constant_only` segmentation is clearly better than the mixed
      family holdout
    - therefore part of the previous hourly weakness came from regime mixing,
      not only from lack of truth

- segmented day-night family:
  - direct gold-run truth expansion now exists via
    - [hydrate_thermflex_cohort_utilization_from_gold_run_dirs.py](../../Optimization/run/analysis/hydrate_thermflex_cohort_utilization_from_gold_run_dirs.py)
  - the direct hydrator is intentionally narrow:
    - top-level `*day_night_thermflex_paper_day_ahead` run dirs only
    - one representative per persisted `truth_dataset.csv` signature
    - incomplete run dirs are reported explicitly and skipped
  - reason for the signature dedupe:
    - several standalone day-night gold dirs are exact reruns of the same
      solved point
    - hydrating all of them would create fake grouped-holdout diversity
  - expanded dataset:
    - `Learning/datasets/9a6779e1b8e6eaa4accf41b4846deaec755da9b84a6c94a73b1c36480766a004/`
  - model:
    - `Learning/models/thermflex_hourly_mechanism_xgb_mechanism_energy_intensive_9a6779e1b8e6/`
  - grouped holdout:
    - `mean R2 ~ 0.998`
    - `cohort_q_delta_wh_per_m2 ~ 0.998`
    - `cohort_preheat_extra_wh_per_m2 ~ 1.000`
    - `cohort_cutback_shed_wh_per_m2 ~ 0.999`
    - `cohort_temperature_violation_degree_h ~ 0.995`
  - daily re-aggregation from the hourly holdout prediction:
    - `shifted_r2 ~ 0.999`
    - `rebound_r2 ~ 0.994`
    - `peak_r2 ~ 0.999`
  - interpretation:
    - `day_night` was mainly a truth-basis problem, not a mechanism-model
      problem
    - once the family gets two distinct truth-signature groups, the hourly
      mechanism path becomes effectively solved for this regime

- segmented constant `evt1` family:
  - dataset:
    - `Learning/datasets/c6d583a1294d20a396143ad8b272e35cd43f074b66d3f9dafebbb333f22f1888/`
  - model:
    - `Learning/models/thermflex_hourly_mechanism_xgb_mechanism_energy_intensive_c6d583a1294d/`
  - grouped holdout:
    - `mean R2 ~ 0.341`
  - daily re-aggregation from the hourly holdout prediction:
    - `shifted_r2 ~ 0.415`
    - `rebound_r2 ~ 0.091`
    - `peak_r2 ~ 0.599`
  - interpretation:
    - explicit `evt1` segmentation helps compared to the mixed constant family,
      but rebound remains much harder than shifted or peak

- segmented constant `evt24` family:
  - direct scenario truth is now expanded via the same direct-gold hydrator:
    - `peak`
    - `price`
    - `sunny`
    - `wintertyp`
    - `shouldertyp`
    for both
    - `constant_evt24_lower_relax`
    - `constant_evt24_upper_only`
  - lower-relax slice:
    - dataset:
      - `Learning/datasets/4f124c87fe01b2b32221284cf22c24ed621e7a6908a04bd457061fae456989a9/`
    - model:
      - `Learning/models/thermflex_hourly_mechanism_xgb_mechanism_energy_intensive_4f124c87fe01/`
    - grouped holdout:
      - `mean R2 ~ 0.53`
    - daily re-aggregation:
      - `shifted_r2 ~ 0.79`
      - `rebound_r2 ~ 0.00`
      - `peak_r2 ~ 0.30`
  - upper-only slice:
    - dataset:
      - `Learning/datasets/5f5fdf867b21d4ec7bd836ba8ab5a014dbe1616dbc48f634c394ba2d8cee9dd8/`
    - model:
      - `Learning/models/thermflex_hourly_mechanism_xgb_mechanism_energy_intensive_5f5fdf867b21/`
    - grouped holdout:
      - `mean R2 ~ 0.45`
    - daily re-aggregation:
      - `shifted_r2 ~ 0.34`
      - `rebound_r2 ~ 0.31`
      - `peak_r2 ~ 0.61`
- mixed evt24 slice after truth expansion:
    - dataset:
      - `Learning/datasets/04c7e1286d3f47787eea7fa87ce0ba2b39e9072d436d164e23c490565a5ebfc6/`
    - model:
      - `Learning/models/thermflex_hourly_mechanism_xgb_mechanism_energy_intensive_04c7e1286d3f/`
    - grouped holdout:
      - `mean R2 ~ 0.49`
    - daily re-aggregation:
      - `shifted_r2 ~ 0.74`
      - `rebound_r2 ~ 0.32`
      - `peak_r2 ~ 0.67`
  - interpretation:
    - `evt24` is no longer broken once direct scenario truth is included
    - but it is still materially harder than `day_night`
    - rebound remains the stubborn part of the `evt24` mechanism even after
      separating upper-only and lower-relax

- figure-near mechanism-bundle truth:
  - the mechanism-bundle builder now also writes
    - `thermflex_cohort_utilization_hourly.csv`
    - `thermflex_cohort_utilization_summary.csv`
    directly into each `paper_mechanism_bundle_*` folder
  - existing older bundles were hydrated with the same contract instead of
    creating a new side artifact family
  - effect on `evt24 upper_only`:
    - the slice now has more independent figure-near truth groups
    - but the grouped holdout is also harder and more realistic
    - current full-mode upper-only retrain:
      - dataset:
        - `Learning/datasets/262fb2518c9421a49e9a31ae1e9b5cd9350d29a00b1b205f6fb157a95ceb49f6/`
      - model:
        - `Learning/models/thermflex_hourly_mechanism_xgb_mechanism_energy_intensive_262fb2518c94/`
      - grouped holdout:
        - `mean R2 ~ 0.12`
      - KPI re-aggregation:
        - `shifted_r2 ~ -1.43`
        - `rebound_r2 ~ -0.57`
        - `peak_r2 ~ -0.28`
        - `3` holdout days / `3` holdout runs
  - effect on mixed `constant_evt24_only`:
    - full-mode retrain:
      - dataset:
        - `Learning/datasets/ad012bde555a5b0510cca7023eba9b872961422fc07a577891563be4ed2351ab/`
      - model:
        - `Learning/models/thermflex_hourly_mechanism_xgb_mechanism_energy_intensive_ad012bde555a/`
      - grouped holdout:
        - `mean R2 ~ 0.55`
      - KPI re-aggregation:
        - `shifted_r2 ~ 0.38`
        - `rebound_r2 ~ 0.55`
        - `peak_r2 ~ -4.62`
        - `5` holdout days / `5` holdout runs
  - interpretation:
    - the new figure-near truth is useful because it replaces fragile two-day
      KPI checks with a harder and more honest holdout
    - the remaining blind spot is now much narrower:
      - `peak` in constant `evt24`
      - and `upper_only dur24 evt24` as a distinct regime
  - after adding a third independent `dur24` upper-only mechanism bundle
    (`paper_mechanism_bundle_20260514_204413`), the picture becomes more
    specific:
    - `constant_evt24_upper_only` with the preferred
      `mechanism_energy_intensive` full-mode path now improves its
      figure-level `shifted` fit materially
      - dataset:
        - `Learning/datasets/dea7aac98eb2f01c57ef05cf880d0da8108aa9c5aff03afc51223f5d13c23dae/`
      - model:
        - `Learning/models/thermflex_hourly_mechanism_xgb_mechanism_energy_intensive_dea7aac98eb2/`
      - KPI re-aggregation:
        - `shifted_r2 ~ -0.28`
        - `rebound_r2 ~ -1.11`
        - `peak_r2 ~ -0.44`
        - `4` holdout runs / `4` holdout days
    - `evt24_compact` remains worse than full for this regime
    - mixed `constant_evt24_only` after the third bundle:
      - dataset:
        - `Learning/datasets/406423ed87865e656c55333047a2c87e928ef5d3308f5eb753f55e2e17dceb82/`
      - model:
        - `Learning/models/thermflex_hourly_mechanism_xgb_mechanism_energy_intensive_406423ed8786/`
      - KPI re-aggregation:
        - `shifted_r2 ~ -1.03`
        - `rebound_r2 ~ 0.46`
        - `peak_r2 ~ -0.09`
        - `6` holdout runs / `6` holdout days
    - interpretation:
      - more `upper_only` figure-near truth helps the pure upper-only regime
        mainly on `shifted`
      - the mixed `evt24` path now almost neutralizes `peak`
      - the remaining narrow gap is:
        - `rebound` inside `upper_only dur24 evt24`
        - keeping the near-neutral `peak` fit stable while improving the other
          figure quantities

Interpretation:

- hourly truth is now broad enough to show that mechanism learning on hourly
  basis is more promising than the direct daily `shifted/rebound` path,
- `day_night` is now strong enough to reconstruct holdout-run daily
  `shifted/rebound/peak` almost exactly after re-aggregation,
- `constant evt1` is partly recoverable, but rebound is still weak,
- `constant evt24` is now moderately learnable, but still not solved,
- the next likely lever is richer mechanism truth or more explicit state
  information, not just more daily context features,
- and explicit policy-family / event-family segmentation is now clearly
  validated as a worthwhile modeling decision for the hourly path.

## Explicit Feature Modes

The hourly dataset contract now keeps feature selection explicit via
`feature_mode`, instead of relying on ad-hoc notebook slicing.

- `full`
  - the original broad feature contract
- `evt24_compact`
  - intentionally narrow for already homogeneous `evt24` families:
    - hour/day position
    - outdoor temperature
    - DH load context
    - reference heat
    - `cohort_key`

This mode exists because the `evt24` ablations showed that adding more policy,
market, solar and cohort-context blocks does not automatically improve the
figure-relevant KPI reconstruction.

Current result:

- `evt24_compact` is reproducible and trainable,
- but it is **not yet a clear KPI winner** over the broad `full` mode for the
  routed `evt24` families,
- so the preferred current `evt24` path remains the segmented family routing,
  with `feature_mode` treated as an explicit experiment axis rather than a new
  default.

## KPI-First Evaluation

The hourly path now also contains an explicit holdout evaluator:

- [evaluate_kpi_reaggregation.py](./evaluate_kpi_reaggregation.py)

Purpose:

- reconstruct holdout-run day-level
  - `thermflex_shifted_space_heat_kwh`
  - `thermflex_rebound_kwh`
  - `thermflex_peak_change_kw`
  from one stored hourly model plus its matching curated dataset,
- keep KPI comparison reproducible instead of relying on one-off scripts.

Current interpretation:

- this stricter evaluator confirms the main design rule:
  - hourly family work must be judged by the reconstructed paper KPIs, not only
    by internal hourly target `R2`,
- and it also makes visible that some current `evt24` slices still have very
  small grouped holdouts (`2` holdout runs / `2` holdout days), so KPI-`R2`
  there remains fragile even when the internal hourly fit looks reasonable.

## Tau4 Lower-Relax Candidate

The expanded tau4 lower-relax truth basis is now represented by:

- dataset:
  - `Learning/datasets/74d382eb0b7393434724b7d0fdac499faabb24b7c799cafed73552f7bc29cf08/`
- model:
  - `Learning/models/thermflex_hourly_mechanism_xgb_mechanism_energy_intensive_74d382eb0b73/`
- split contract:
  - grouped by `split_group_run`
  - `group_stratified_shuffle`
  - `stratify_column = month`
- shifted postprocessor:
  - `shifted_postprocessor.json`
  - profile `tau4_lower_relax_shifted_daily_state_xgb_v1`
- repeated holdout diagnostics:
  - `diagnostics/repeated_kpi_holdout_summary.csv`
  - `diagnostics/repeated_kpi_holdout_summary.json`
  - `diagnostics/repeated_kpi_holdout_summary_shifted_state.csv`
  - `diagnostics/repeated_kpi_holdout_summary_shifted_state.json`

Why this candidate exists:

- tau4 lower-relax truth mixes January low-variance heating days with March,
  April, October and November transition days,
- a plain grouped random holdout can therefore select an unrepresentative
  low-variance test set and make KPI R2 unstable,
- the month-stratified grouped split keeps whole runs held out while preserving
  the main seasonal mechanism buckets,
- raw hourly `q_delta` still underestimates day-level shifted heat mass, so the
  shifted correction is kept as an explicit persisted postprocessor.

Current best tau4 KPI re-aggregation check:

- train split:
  - `random_state = 1`
  - `group_stratified_shuffle / month`
- holdout:
  - `7` days / `7` run groups
- with shifted postprocessor only:
  - `shifted_r2 ~ 0.977`
  - `rebound_r2 ~ 0.984`
  - `peak_r2 ~ 0.593`

Repeated 10-seed check with the same month-stratified split contract:

- raw median:
  - `shifted_r2 ~ -6.46`
  - `rebound_r2 ~ 0.293`
  - `peak_r2 ~ 0.549`
- with shifted postprocessor median:
  - raw-feature profile `shifted_r2 ~ 0.573`
  - state-feature profile `shifted_r2 ~ 0.986`
  - `rebound_r2 ~ 0.293`
  - `peak_r2 ~ 0.549`

Interpretation:

- `shifted` and `rebound` now have a plausible tau4 candidate at the KPI level,
- the old conservative rebound postprocessor should not be applied to this
  tau4 candidate because raw rebound is better here,
- `peak` is still the open tau4 mechanism gap and mainly fails on a few negative
  peak-reduction days that the hourly heat-shape model does not yet reconstruct.

## Explicit Rebound Postprocessor

The lower-relax `evt24` family now also has one explicit KPI-level rebound
postprocessor:

- [rebound_postprocessor.py](./rebound_postprocessor.py)

Why it exists:

- the best lower-relax base model already fits:
  - `shifted_r2 ~ 0.781`
  - `peak_r2 ~ 0.855`
- but its raw `rebound_r2` was still:
  - `~ -7.06`
- diagnosis showed a narrow failure mode:
  - small early negative hourly prediction noise activated the rebound regime
    on true zero-rebound days

The fix is intentionally explicit:

- profile:
  - `lower_relax_evt24_conservative_v1`
- negative trigger deadband:
  - `25,000 kWh`
- positive accumulation deadband:
  - `0 kWh`
- final rebound mass is then scaled with one train-fitted multiplicative factor
  that is persisted next to the base model artifact

This does **not** change the global KPI definition. It is only used when a
stored `rebound_postprocessor.json` is passed into the evaluator.

Current effect on the best lower-relax base model:

- base model:
  - `Learning/models/thermflex_hourly_mechanism_xgb_mechanism_energy_intensive_4335e9b1c5cd/`
- postprocessor:
  - `Learning/models/thermflex_hourly_mechanism_xgb_mechanism_energy_intensive_4335e9b1c5cd/rebound_postprocessor.json`
- holdout after re-aggregation:
  - `shifted_r2 ~ 0.781`
  - `rebound_r2 ~ 0.324`
  - `peak_r2 ~ 0.855`

Interpretation:

- the postprocessor does not move `shifted` or `peak`
- it only suppresses the known false rebound activations in the
  `constant_evt24_lower_relax_only` family
- it is a family-specific KPI repair, not a new default for every hourly model

## Explicit Peak Postprocessor

The mixed `constant_evt24_only` family now also has one explicit peak-focused
postprocessor:

- [peak_postprocessor.py](./peak_postprocessor.py)

Why it exists:

- the mixed `evt24` slice remains too heterogeneous for a shared
  `shifted/rebound` mechanism path,
- but it is still useful as a broad `peak`-figure path,
- the base mixed `evt24` model already had:
  - `peak_r2 ~ 0.31`
- and a simple sign-aware peak scaling on the train-side daily payload lifts the
  holdout peak fit further without changing `shifted` or `rebound`.

The current explicit profile is:

- `mixed_evt24_peak_negative_scale_v1`
- negative peak changes are scaled through the origin from the train-side daily
  payload
- nonnegative peak changes keep scale `1.0`

This is again explicit and family-specific, not a hidden change to the base
hourly prediction path.

Current effect on the mixed `evt24` base model:

- base model:
  - `Learning/models/thermflex_hourly_mechanism_xgb_mechanism_energy_intensive_f8ac31dca29b/`
- postprocessor:
  - `Learning/models/thermflex_hourly_mechanism_xgb_mechanism_energy_intensive_f8ac31dca29b/peak_postprocessor.json`
- holdout after re-aggregation:
  - `shifted_r2 ~ -1.16`
  - `rebound_r2 ~ -0.01`
  - `peak_r2 ~ 0.44`

Interpretation:

- the mixed `evt24` path should currently be treated as a `peak` path
- `shifted/rebound` remain better handled through family-routed
  `day_night` / `lower_relax` / `upper_only`
