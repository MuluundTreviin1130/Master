# Settings Validation Layer

This sublayer stores explicit validation-time selectors that must remain part of
the Settings SSOT. Defaults are intentionally empty so runtime resolution only
forces a model when an override sets a concrete `validation.holdout` value.
