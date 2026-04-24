# Settings Package

`Settings/` is the single source of truth for runtime configuration.

## Usage

- Build config through `Settings.get_settings(overrides=...)`.
- CLI layers must only build an `overrides` dictionary and pass it to `get_settings`.
- Do not mutate config in parallel code paths.

## Structure

- `run/`: run-level orchestration config (`run.py`, `scheduler.py`).
- `optimization/`: optimization algorithm and sampling (`optimizer.py`, `sampler.py`).
- `engines/`: engine selection + gated controller config (`engine.py`, `gating.py`).
- `surrogate/`: surrogate model and training config (`surrogate.py`, `train.py`).
- `reporting/`: export/report toggles and output paths (`reporting.py`).
- `problem/`: bounds, objectives, constraints, PB config.
- `technical/`: members, feature toggles, thermal, hydrogen settings.
- `data/`: impact/LCA settings.
- `validation/`: surrogate holdout validation config.

## Extending

1. Add a dataclass + `make_*` factory in the matching subpackage.
2. Wire it into `Settings/settings_model.py`.
3. Compose it in `Settings/get_settings.py`.
4. If required, expose it via package `__init__.py`.
