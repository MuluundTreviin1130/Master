from __future__ import annotations

from dataclasses import dataclass


@dataclass
class FeatureFlags:
    """Feature toggles for the unified EC_FLEX architecture."""

    enable_bess: bool = True
    enable_v2h: bool = True
    enable_h2: bool = True
    enable_thermflex: bool = True
    enable_small_wind: bool = False
    enable_large_wind: bool = False
    enable_biogas_engine: bool = False
    enable_wood_gasifier: bool = False
