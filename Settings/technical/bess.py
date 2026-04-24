from __future__ import annotations

from dataclasses import dataclass


@dataclass
class BESSConfig:
    """Battery module settings."""

    initial_soc: float = 0.5
    cyclic_soc: bool = False
    cyclic_soc_rtol: float = 1e-6


def make_bess() -> BESSConfig:
    return BESSConfig()
