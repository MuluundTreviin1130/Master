# Profiles

This layer bundles profile assets together with their runtime loading logic.

Current structure:

- `registry.py`
  canonical repo-local path registry for profile sources
- `loaders.py`
  profile loading and assembly helpers
- `Vienna/`, `common/`
  raw input assets grouped by location or shared usage
