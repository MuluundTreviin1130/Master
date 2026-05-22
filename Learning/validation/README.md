# Learning validation

This package contains validation gates for learned artifacts before they become
eligible for optimization.

The gate is intentionally fail-fast on malformed holdout arrays and reports
target-level pass/fail information so blocked models can be remediated without
guessing which KPI failed.
