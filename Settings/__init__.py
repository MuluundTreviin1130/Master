from __future__ import annotations

"""Top-level Settings package (single source of truth).

All configuration composition must go through ``get_settings(overrides=...)``.
The public objects are imported lazily so lightweight subpackages such as
``Settings.validation`` do not load data/profile dependencies at import time.
"""

__all__ = ["get_settings", "Settings"]


def get_settings(*args, **kwargs):
    from .get_settings import get_settings as _get_settings

    return _get_settings(*args, **kwargs)


def __getattr__(name: str):
    if name == "Settings":
        from .settings_model import Settings

        return Settings
    raise AttributeError(f"module 'Settings' has no attribute {name!r}")
