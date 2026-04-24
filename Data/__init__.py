from __future__ import annotations

#
# Compatibility shim:
# Older runtime modules still import `from Data import data as data` and expect
# the historical facade module with `get_parameters`, `load_profiles`, and the
# backward-compatible path/technology exports. After moving that facade to
# Data/assembly/api.py, we re-expose it here explicitly so the repo structure
# can evolve without silently breaking downstream imports.
from .assembly import api as data
from .assembly import get_parameters, load_profiles

__all__ = ["data", "get_parameters", "load_profiles"]
