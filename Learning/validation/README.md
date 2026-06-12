# Learning Validation

This package contains validation helpers used by the native Learning retrain
path before model registry status is updated.

The code is intentionally fail-fast: missing target coverage, invalid holdout
arrays and non-finite predictions must block candidate models instead of
silently promoting unusable artifacts.
