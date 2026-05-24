# Learning validation

This package contains the validation gate used after native surrogate retraining.
The gate is intentionally fail-fast: missing columns, non-finite labels, and
failed critical targets block model eligibility instead of silently promoting an
unsafe surrogate artifact.
