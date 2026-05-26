# ThermFlex Daily Results Learning

This sublayer prepares learned daily ThermFlex result models from canonical
daily ThermFlex truth exports and cached paper-screen bundles.

## Responsibility

- Read canonical daily ThermFlex truth data produced by the optimization and
  analysis stack.
- Build explicit day-level ML datasets for ThermFlex result prediction.
- Keep feature and target contracts explicit and fail fast on missing required
  truth columns.
- Provide a reusable learned daily-results path for paper tables, sensitivity
  sweeps, trade-off plots and candidate-period screening.

`Optimization` remains responsible for truth generation. This layer is
responsible for ML-ready daily features, daily result targets, grouped
validation, model artifacts and later inference hooks.

## Scope

This layer is intentionally broader than `Table 09`.

The learned contract should represent general ThermFlex day-screen outcomes:

```text
policy parameters + daily context + reference-day features
  -> daily result deltas + daily KPIs + source-shift summaries
```

Examples of downstream consumers:

- heating-season or annual table aggregation
- sensitivity scans over `tau`, `duration`, `0K/1K/2K`
- scatter plots of cost vs. CO2 vs. peak-boiler reduction
- selection of interesting days or weeks for full MILP reruns

## First Dataset Contract

The initial V1 dataset should create one row per modeled day and include:

- explicit policy descriptors:
  - case labels
  - override identity
  - later explicit `tau`, `duration`, `lower relaxation` extracted from bundle or override metadata
- explicit day context:
  - weather summaries
  - load summaries
  - market-price summaries
  - seasonal position / calendar context
- explicit reference-day descriptors:
  - baseline cost, CO2 and peak-boiler information
  - baseline source shares where available
- explicit day targets:
  - cost delta
  - CO2 delta
  - peak-boiler energy delta
  - peak-boiler peak delta
  - source-shift metrics needed for paper evaluation

The current truth contract is grounded in the existing
`heating_season_day_screen.csv` export written by
`screen_vienna_constant_thermflex_heating_season_days.py`. The first builder
step should therefore reuse the real exported columns for:

- daily context (`t_outdoor_*`, `dh_*`, irradiance, prices)
- REF values
- flex values
- explicit delta fields
- paper-facing identifiers such as `flex_case_label` and `flex_override_name`

The first V1 builder should remain dataset-first. Training, uncertainty and
runtime gating can then evolve on top of a stable daily-truth contract.

## Target Profiles

Training is no longer forced to use the full target block at once.

The current path supports:

- `all`
  - the full day-level result block
- `robust_kpi`
  - the first focused KPI profile:
    - `dispatch_operating_cost_pct_change`
    - `co2_emissions_total_pct_change`
    - `district_gas_boiler_peak_kw_delta`
    - `district_gas_boiler_generation_kwh_delta`
    - `dh_total_peak_change_kw`
    - `thermflex_peak_change_kw`
- `robust_kpi_absolute`
  - same KPI block, but with absolute cost and CO2 deltas:
    - `dispatch_operating_cost_eur_delta`
    - `co2_emissions_total_t_delta`
    - `district_gas_boiler_peak_kw_delta`
    - `district_gas_boiler_generation_kwh_delta`
    - `dh_total_peak_change_kw`
    - `thermflex_peak_change_kw`

This keeps paper-facing KPI learning separate from the harder shift/rebound
targets, which should be reintroduced deliberately later.

- `table_09_paper`
  - the minimal daily target block needed to reconstruct a surrogate
    `heating_season_day_screen.csv` for the existing Table-09 builder:
    - `dispatch_operating_cost_pct_change`
    - `co2_emissions_total_pct_change`
    - `district_gas_boiler_peak_kw_delta`
    - `district_gas_boiler_generation_kwh_delta`
    - `thermflex_shifted_space_heat_kwh`
    - `thermflex_rebound_kwh`

The current cost target inside `robust_kpi` is fitted with an explicit
`signed_log1p` transform during training and mapped back to the original scale
for metrics. This is documented because the raw cost-percentage target contains
heavy outliers and should not be treated as a plain unscaled regression target.

The absolute-delta profile exists because percentage-based daily KPIs can become
numerically unstable near very small reference-day denominators. At the moment
that alternative profile is useful as an explicit diagnostic path, but it is
not the preferred baseline because its grouped-holdout performance stayed below
the percentage-based `robust_kpi` baseline.

## Validation Direction

Validation should not use naive random row splits.

The intended validation path is grouped holdout over whole screen bundles,
case families and coherent time blocks so that similar weather and load shapes
do not leak between train and holdout.

## Naming Rule

This sublayer is called `thermflex_daily_results` on purpose.

It should stay useful even if later paper tables, figures or screening exports
change. Table-specific exports should be built as aggregations on top of this
general daily-results layer, not as separate surrogate silos.

## Current Builder Status

The current module status is intentionally split in two steps:

- implemented:
  - discover completed `heating_season_day_screen.csv` bundles
  - validate them against the explicit current truth contract
  - merge them into one auditable daily truth table with source metadata
  - normalize one explicit legacy upper-only screen schema into the current column contract
  - derive canonical policy metadata from the referenced ThermFlex override SSOT
  - persist curated datasets into `Learning/datasets/`
  - grouped holdout execution
  - target-wise XGB baselines for `all` and `robust_kpi`
- still open:
  - broader bundle coverage
  - stronger cost target performance
  - separate shift/rebound-focused target path
  - stronger Table-09 surrogate quality, especially for shifted/rebound

The merged truth table now intentionally keeps both:

- exported paper-facing labels such as `flex_case_label`
- canonical override-derived labels and descriptors such as
  `policy_case_label_canonical`, `policy_duration_h`,
  `policy_lower_relaxation_k` and `policy_tau_h`

This makes legacy or transitional bundle inconsistencies visible instead of
hiding them in a silent overwrite.

## First Inference Hook

The daily layer now also contains a first explicit surrogate-to-paper adapter:

- `predict.py`
  - builds an inference frame from:
    - one heating-season template screen
    - one explicit ThermFlex override
  - runs one trained daily model
  - reconstructs a surrogate `heating_season_day_screen.csv`-style frame
- `aggregate.py`
  - passes that surrogate screen into the unchanged existing
    `build_table_09_heating_season_kpis.py`

This means the Table-09 path is now executable through the learning layer.
However, the current daily grouped-holdout quality is still the main blocker:

- `table_09_paper` on the current mixed curated family:
  - model:
    - `Learning/models/thermflex_daily_results_xgb_table_09_paper_5896cea66bba/`
  - mean `R2`: about `-0.048`
  - cost / CO2 / boiler are at least directionally usable
  - shifted / rebound remain too weak for paper-ready surrogate reporting

The current best daily Table-09 path is now:

- dataset family:
  - earlier mixed-family baseline:
    - `d13030264a0b5582928f45de9470284270820ffd734aa4d00782ccdac91bbb88`
  - current curated gold-first family:
    - `f77eafde5cdc366ee47282e6755eaac41fec0f8da18321c709a6f4a094828e98`
  - includes:
    - full bundles
    - larger checkpoint/partial bundles
    - legacy bundles explicitly tagged
    - live `Optimization/run/results/.../gold` is intentionally preferred over
      older snapshot copies when bundle names collide, so the curated dataset
      keeps the newest failure manifests and partial-truth state
    - newly useful partial families:
      - `LOWER2K_DUR1_EVT24`
      - `LOWER2K_DUR4_EVT24`
- model:
  - current best:
    - `Learning/models/thermflex_daily_results_xgb_table_09_paper_f77eafde5cdc/`
- grouped-holdout:
  - mean `R2`: about `0.334`
  - current target-level picture:
    - `dispatch_operating_cost_pct_change`: `0.595`
    - `co2_emissions_total_pct_change`: `0.228`
    - `district_gas_boiler_peak_kw_delta`: `-0.063`
    - `district_gas_boiler_generation_kwh_delta`: `0.241`
    - `thermflex_shifted_space_heat_kwh`: `0.525`
    - `thermflex_rebound_kwh`: `0.475`

The most important recent shift is not the mean value alone, but that
`shifted` and `rebound` are now positive on grouped holdout after:

- adding tractable `LOWER2K_DUR1_EVT24` and especially `LOWER2K_DUR4_EVT24`
  partial-truth bundles
- tuning the target-specific XGB parameter blocks for:
  - `thermflex_shifted_space_heat_kwh`
  - `thermflex_rebound_kwh`

The current preferred daily baseline is still the tuned `f77...` family/model
pair, even though newer families with additional very small partial bundles now
exist. Some of those later families produced worse grouped splits because the
holdout composition changed unfavorably. They remain useful as truth inventory,
but not yet as the preferred `Table 09` surrogate baseline.

After the later `dur8` truth expansion this preference moved forward:

- current stronger daily baseline:
  - `Learning/models/thermflex_daily_results_xgb_table_09_paper_29cc229d5820/`
  - grouped holdout mean `R2 = 0.134`
  - target picture:
    - `dispatch_operating_cost_pct_change = 0.903`
    - `co2_emissions_total_pct_change = -0.012`
    - `district_gas_boiler_peak_kw_delta = 0.382`
    - `district_gas_boiler_generation_kwh_delta = 0.335`
    - `thermflex_shifted_space_heat_kwh = -0.579`
    - `thermflex_rebound_kwh = -0.224`

An additional daily-weather enrichment test was then run by extending the
contract with:

- `t_outdoor_max_c`
- `t_outdoor_range_c`
- `hdd18_kh`
- `t_outdoor_mean_prevday_c`
- `t_outdoor_mean_nextday_c`
- plus engineered deltas/intensity terms

That enriched profile produced:

- `Learning/models/thermflex_daily_results_xgb_table_09_paper_d30bb08d4b86/`
- grouped holdout mean `R2 = 0.065`

Interpretation:

- the extra outdoor-temperature metrics help cost further
- but they do not improve the current daily blocker targets:
  - `shifted`
  - `rebound`
  - daily `CO2`

So the preferred daily baseline stays the simpler `29cc...` weather-light
contract for now, while the weather-enriched variant remains a documented
experiment rather than the promoted paper path.

The next explicit context test then added daily cohort-mix features from the
same canonical Vienna-2023 yearly SSOT:

- daily `dh_space_heat_share_*` for all eight building-key cohorts
- aggregated:
  - `dh_space_heat_share_residential_total`
  - `dh_space_heat_share_non_residential_total`
- engineered:
  - `residential_to_non_residential_space_heat_ratio`
  - `old_stock_space_heat_share`
  - `modern_stock_space_heat_share`

That cohort-aware contract produced:

- `Learning/models/thermflex_daily_results_xgb_table_09_paper_3aa909c1c12e/`
- grouped holdout mean `R2 = 0.082`

Interpretation:

- daily CO2 becomes positive on holdout
- but `shifted` and `rebound` get worse again
- the dedicated `shifted_rebound_only` profile on the same cohort-aware family
  also stays clearly negative

So the current evidence is:

- more static or day-aggregate context is not the main blocker anymore
- the next plausible lever is future daily-truth enrichment with explicit
  comfort / temperature diagnostics as auxiliary targets, not another generic
  context expansion

The daily screen exporter has therefore been extended for future truth runs:

- `screen_vienna_constant_thermflex_heating_season_days.py` now writes:
  - `thermflex_t_in_min_c`
  - `thermflex_t_in_max_c`
  - `thermflex_temperature_violation_degree_hours_total`

These columns are not yet part of the active V1 training contract, because the
existing curated bundles do not contain them. The intended next step is to let
new partial/full daily-screen bundles accumulate with that richer export and
then test temperature / comfort auxiliary targets explicitly on the daily path.

Partial ThermFlex truth is now a first-class dataset concept:

- `screen_vienna_constant_thermflex_heating_season_days.py` can continue after
  day-level solver failures when `--allow-incomplete-days` is set
- failed dates are written to:
  - `heating_season_day_screen_failures.csv`
  - `heating_season_day_screen_failures.json`
  - `heating_season_day_screen_meta.json`
- later resumes explicitly skip already known failure dates instead of burning
  the same 10-minute timeout again
- curated dataset manifests now surface per-bundle:
  - `failure_csv`
  - `known_failure_rows`
  - `known_failure_dates`

So the path is ready for engineering iteration and fast what-if generation, but
not yet the final paper-truth replacement for Table 09.

## Current Dur8 Follow-Up

The latest partial-truth expansion changed the `dur8` picture materially:

- `LOWER2K_DUR8_EVT24`
  - `71` solved days up to `2023-03-28`
  - `16` explicit heavy-day failures
- `LOWER1K_DUR8_EVT24`
  - `48` solved days up to `2023-02-19`
  - `2` explicit heavy-day failures

On that truth state:

- the narrow profile `shifted_rebound_only`
  - model:
    - `Learning/models/thermflex_daily_results_xgb_shifted_rebound_only_2b65d41fa479/`
  - grouped holdout:
    - `thermflex_shifted_space_heat_kwh = -0.623`
    - `thermflex_rebound_kwh = -0.256`
- the full daily Table-09 profile
  - model:
    - `Learning/models/thermflex_daily_results_xgb_table_09_paper_2b65d41fa479/`
  - grouped holdout mean `R2 = 0.048`
  - target-level picture:
    - `dispatch_operating_cost_pct_change = 0.826`
    - `co2_emissions_total_pct_change = -0.387`
    - `district_gas_boiler_peak_kw_delta = 0.349`
    - `district_gas_boiler_generation_kwh_delta = 0.379`
    - `thermflex_shifted_space_heat_kwh = -0.623`
    - `thermflex_rebound_kwh = -0.256`

This means:

- the dedicated `shifted/rebound` profile is useful for diagnosis, but it does
  not by itself solve the daily mechanism fit
- updated target-specific params for `shifted` and `rebound` do improve both
  targets relative to the previous strict-holdout baseline
- the current daily blocker is now very specific:
  - `shifted`
  - `rebound`
  - secondarily daily CO2
