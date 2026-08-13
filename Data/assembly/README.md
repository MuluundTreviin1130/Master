# Data Assembly

This sublayer contains runtime assembly and compatibility facades that turn
technology data, location economics, and profile loaders into assembled inputs.

Current contents:

- `api.py`
  backward-compatible facade for `get_parameters(...)` and `load_profiles(...)`
- `params.py`
  canonical merged parameter assembly
- `location_params.py`
  location-specific economics and local settings bridge
- `tech_params.py`
  global technology dictionary assembly
- `replacements.py`
  replacement-interval helpers used by cost and KPI reporting.
  BESS throughput is charge+discharge energy; `annual_bess_throughput_kwh`
  is the shared helper for Gold, teacher, and CSV exports.
