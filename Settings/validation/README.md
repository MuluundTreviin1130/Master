# Validation Settings

This package contains validation-specific runtime configuration.

- `holdout.py` defines explicit Learning model overrides for validation and
  debugging runs.
- Empty `model_id` and `artifact_path` values mean that normal registry-based
  Learning model resolution remains active.
