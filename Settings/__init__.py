from __future__ import annotations

"""Top-level Settings package (single source of truth).

All configuration composition must go through ``get_settings(overrides=...)``.
"""

from .get_settings import get_settings
from .settings_model import Settings

__all__ = ["get_settings", "Settings"]
