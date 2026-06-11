# Learning validation

`Learning.validation` contains small, Settings-backed validation contracts used
before trained surrogate models can be marked optimization-eligible.

The promotion gate is intentionally fail-fast on malformed arrays and returns a
JSON-safe result payload for model-registry metadata.
