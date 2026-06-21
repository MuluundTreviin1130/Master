# Learning Validation

This package contains validation gates for native Learning models.

The gate code is intentionally separate from training so model eligibility is
decided by explicit `Settings.learning.validation_gate` thresholds instead of
implicit registry updates or silent runtime fallbacks.
