# Learning Layer

`Learning/` is the repository layer for learned models, datasets, artifacts,
validation outputs and retrain policy.

## Responsibilities

- Build model-ready datasets from canonical teacher or gold outputs.
- Store reusable datasets under `Learning/datasets/`.
- Store reusable model artifacts under `Learning/models/`.
- Keep model families and compatibility metadata explicit.
- Train and validate surrogates without hiding missing inputs behind defaults.
- Maintain a central inventory of reusable truth and model artifacts so old repo
  outputs can be reused deliberately instead of ad hoc.

## Building Surrogate Layer 2

The planned building-response surrogate belongs in this layer. It should read
canonical `EnergyPlus` teacher exports from
`Technical_model/technologies/buildings/calibration/`, then build hourly
transition datasets for:

```text
state_t + exogenous_t + control_t + cohort_context
  -> state_t+1 + q_heat_t + heat-balance diagnostics
```

`Technical_model` remains responsible for the physical model and teacher export.
`Learning` is responsible for feature and target construction, model training,
rollout validation and artifact management.

See `Documentation/Planning/building_surrogate_layer2_design.md` for the current
Layer-2 design.

## Central Target Matrix

`Learning/model_target_matrix.py` is the explicit model-first ownership matrix
for the current surrogate stack.

It exists to answer three narrow questions without relying on paper scripts or
implicit filename conventions:

- which learning layer currently owns a KPI family,
- which model path is currently preferred for that family,
- whether an explicit postprocessor belongs to that path.

The matrix is intentionally static and fail-fast:

- it does not auto-discover models,
- it does not infer aliases,
- ambiguous or missing target ownership should be fixed in the matrix itself.

## ThermFlex Daily Results Layer

ThermFlex paper and screening work also needs a learned system-result layer for
daily ThermFlex outcomes. This belongs in `Learning/thermflex_daily_results/`
and is intentionally broader than a single table export.

The intended contract is:

```text
policy parameters + daily context + reference-day features
  -> daily ThermFlex result deltas and daily KPIs
```

This layer should be the reusable source for:

- annual paper tables such as `Table 09`
- sensitivity sweeps over `tau`, `duration` and lower relaxation variants
- scatter / trade-off plots built from many screened days
- ranking and selection of candidate weeks or months for figure reruns

As with the building-response layer, `Optimization` remains the source of truth
for physical and dispatch truth generation. `Learning` is responsible for the
dataset contract, model training, validation, registry metadata and later
runtime inference hooks.

## ThermFlex System Results Layer

Historic ThermFlex or closely related DH run truth exports also need a separate
system-level surrogate path. This belongs in
`Learning/thermflex_system_results/`.

The intended contract is:

```text
design variables + run descriptors
  -> aggregated MILP/system outputs
```

This layer is intentionally separate from `thermflex_daily_results` because the
rows, feature semantics and target semantics are different:

- `thermflex_daily_results` learns one modeled day at a time
- `thermflex_system_results` learns one historic system/run truth point at a time

The system-results path is the natural home for broader MILP-screening or
design-space surrogate work that should not be mixed into the paper-specific
day-screen surrogate.

## ThermFlex Hourly Mechanism Layer

The current daily ThermFlex surrogate still struggles with the actual flex
mechanism targets such as shifted heat and rebound. For that reason the repo
now also grows a separate hourly mechanism path under
`Learning/thermflex_hourly_mechanism/`.

The intended contract is:

```text
policy descriptors + hourly cohort context + reference-side hourly state
  -> hourly ThermFlex mechanism response
```

This layer is intentionally narrower than the daily and system layers. It is
meant to test whether the mechanism is learnable on hourly resolution before
more truth is added, not to replace the paper-facing daily or system KPI paths.

## Artifact Inventory

`Learning/datasets/` now also owns the central reusable-artifact inventory.
This keeps four things separate:

- raw truth that can feed future training,
- already curated `Learning/datasets/` families,
- model artifacts,
- diagnostic-only outputs.

That separation matters because old `Optimization/run/artifacts/surrogates/*`
bundles are often useful for audit and model history, but they are not direct
training rows. Conversely, old `truth_dataset.csv` or `teacher_hourly.csv`
exports can be valid truth, but only for compatible surrogate families.
