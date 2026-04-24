# Run Layer

This layer contains executable optimization runners, analysis helpers, results,
artifacts, and validation outputs.

Current structure:

- `runners/`
  generic executable entry points such as `run_optimization.py` and `train_surrogate.py`
- `analysis/`
  reproducible analysis and reporting helpers
- `papers/`
  paper-specific runnable wrappers and study bundles
- `results/`
  generated run results
- `artifacts/`
  reusable artifacts such as surrogate models
- `validation/`
  current validation outputs and helpers

Intent:

- keep generic runners separate from paper-specific study wrappers
- avoid a flat `run/` root that mixes production entry points, ad-hoc paper
  scripts, and result artifacts
