# ThermFlex System Results Learning

This sublayer learns system-level ThermFlex or closely related DH run results
from historic `truth_dataset.csv` exports.

## Responsibility

- Read canonical run-level truth exports from historic ThermFlex or DH runs.
- Keep this run-level/system-level contract separate from the day-screen
  contract in `Learning/thermflex_daily_results/`.
- Build curated datasets and first baselines for broad MILP/system screening.

## Why This Exists

The repo now has two clearly different ThermFlex learning families:

1. `thermflex_daily_results`
   - one row per modeled day
   - inputs include policy plus day context
   - targets are daily KPI deltas and day-screen outputs

2. `thermflex_system_results`
   - one row per historic design/system run truth point
   - inputs are design and run descriptors
   - targets are aggregated MILP/system outputs

They solve different problems and must not be mixed silently.

## Current Scope

The initial V1 path is intentionally conservative:

- source: historic ThermFlex or related DH `truth_dataset.csv` files
- default exclusion: old `gold_smoke` runs with `npc_eur` instead of the
  dispatch-cost-focused output contract
- stable contract: only the explicitly validated common column core across the
  non-smoke schemas

The first baseline is therefore not the final target design. It is the first
coherent system-level surrogate path for:

- broad sensitivity screening
- candidate mining before expensive MILP reruns
- later connection to wider MES or design-space work

## Target Profiles

Training supports explicit target profiles instead of forcing the full mixed
output block from the start.

The current path supports:

- `all`
  - the full V1 target block
- `robust_heat_system`
  - the first focused heat-system profile:
    - gas CHP electric / thermal / fuel
    - gas boiler generation / fuel
    - thermal-storage charge / discharge
    - `dispatch_cost_eur`
- `dispatch_kpi_core`
  - the richer dispatch-KPI block from `truth_dataset.csv + dispatch_kpis.json`
  - includes the older `dispatch_operating_cost_eur` together with the richer
    heat-cost, carbon and ThermFlex behavior KPIs
- `dispatch_kpi_paper`
  - the paper-facing KPI subset:
    - `dispatch_heat_operating_cost_eur`
    - `fuel_cost_eur`
    - `co2_cost_eur`
    - `variable_opex_eur`
    - `co2_emissions_total_t`
    - `district_gas_boiler_co2_t`
    - shifted/additional/rebound heat
    - peak change
    - active-member hours
    - temperature-violation degree-hours
  - explicitly excludes:
    - `dispatch_operating_cost_eur`
    - `district_gas_chp_co2_t`

This profile keeps the first MILP/system baseline concentrated on the main heat
system outputs before weaker or more heterogeneous targets are expanded again.

Within this profile, `dispatch_cost_eur` is currently trained with an explicit
`log1p` transform and evaluated again on the original Euro scale. This keeps
the cost target numerically tractable without redefining the reported metric.

Because `dispatch_cost_eur` remained the weakest KPI after the first context
feature upgrade, the training module now also keeps an explicit
cost-specific XGBoost parameter set for that one target. The parameter block
was selected from a grouped-holdout sweep on the current curated family and is
documented in code instead of being hidden in a silent default change.

The same explicit target-wise parameter rule now also applies to the three gas
CHP outputs and the two thermal-storage outputs. The system path is trained
target-wise on purpose, so these parameter differences are treated as part of
the documented model contract rather than as incidental tuning noise.

## Current Context Features

The current V1 dataset now derives additional run-context features directly
from the historic result-folder slug:

- slice tags such as `peak`, `price`, `sunny`, `wintertyp`, `shouldertyp`
- binary flags for these slice classes
- anchor month and anchor day-of-year when the slug ends with `YYYYMMDD`

These context descriptors turned out to matter strongly for boiler and cost
prediction and are therefore part of the explicit contract.

An additional experimental family now also enriches anchored scenario runs with
explicit day-level market/weather/load features from the canonical Vienna
paper-year context. That enriched family is useful for controlled comparison,
but it is not automatically the preferred KPI baseline: on the current grouped
holdout it did not beat the simpler slug-context family for the focused
`robust_heat_system` profile.

## KPI-Enriched Family

The enriched family built from `truth_dataset.csv + dispatch_kpis.json` is now
the preferred path for paper-facing KPI work:

- dataset family:
  - `612be5461a303ff3cbfd0fd044e124fe36662098497280403e3246ca7ddc5aab`
- compatible source contract:
  - only run folders with a `dispatch_kpis.json` `latest_point`
  - fail-fast key check against the explicit KPI contract
  - `dispatch_heat_operating_cost_eur` is derived explicitly when absent as:
    - `fuel_cost_eur + co2_cost_eur + variable_opex_eur`

Current grouped-holdout baselines on this family:

- `dispatch_kpi_core`
  - model:
    - `Learning/models/thermflex_system_results_xgb_dispatch_kpi_core_612be5461a30/`
  - mean `R2`: `0.855`
  - key result:
    - strong on heat-only cost, carbon and ThermFlex behavior
    - weak on `dispatch_operating_cost_eur`, which confirms that the old
      grid-tainted operating-cost KPI is the wrong anchor for the paper story
- `dispatch_kpi_paper`
  - model:
    - `Learning/models/thermflex_system_results_xgb_dispatch_kpi_paper_612be5461a30/`
  - mean `R2`: `0.980`
  - standout targets:
    - `dispatch_heat_operating_cost_eur`: `0.983`
    - `fuel_cost_eur`: `0.985`
    - `co2_cost_eur`: `0.971`
    - `co2_emissions_total_t`: `0.967`
    - `thermflex_rebound_kwh`: `0.957`
    - `thermflex_peak_change_kw`: `0.988`
    - `thermflex_temperature_violation_degree_hours_total`: `0.992`

This is the first system-level ThermFlex KPI profile that clears the desired
`R2 ~ 0.97` quality threshold for the actual paper-facing KPI block on grouped
holdout.
