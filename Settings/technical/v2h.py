from __future__ import annotations

from dataclasses import dataclass


@dataclass
class V2HConfig:
    """V2H dispatch policy settings.

    reserve_lookahead_h: lookahead horizon in hours for dynamic reserve calculation
    reserve_factor: conservative factor for future-driving reserve
    import_sensitive_dispatch: allow EV discharge only when it reduces residual grid import
    """

    reserve_lookahead_h: int = 8
    reserve_factor: float = 0.9
    import_sensitive_dispatch: bool = True


def make_v2h() -> V2HConfig:
    return V2HConfig()
