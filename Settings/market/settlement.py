from __future__ import annotations

from dataclasses import dataclass


@dataclass
class SettlementConfig:
    """Internal EC settlement policy.

    Modes:
    - ``fixed``: use a fixed internal community price.
    - ``linked``: internal price follows the interval between grid export/import.
    """

    mode: str = "fixed"
    beta: float = 0.5


def make_settlement() -> SettlementConfig:
    return SettlementConfig()
