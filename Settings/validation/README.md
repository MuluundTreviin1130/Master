# Validation Settings

This package contains typed settings for validation-time model selection.

The current contract is intentionally small: `validation.holdout.model_id` and
`validation.holdout.artifact_path` let validation overrides force an explicit
surrogate model or artifact. Unknown fields fail through the settings override
validation instead of being accepted silently.
