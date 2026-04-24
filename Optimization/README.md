# Optimization Package

Core optimization orchestration and engines.

## Entry points

- `Optimization/run/runners/run_optimization.py`: main optimization entry.
- `Optimization/validation/run_validation.py`: validation entry (delegates internally).

## Main folders

- `framework/`: settings compatibility shims, orchestrator, engines, optimizers.
- `run/analysis/`: CSV exports, plots, run summaries.
- `validation/`: model/surrogate validation flows.
