from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional


@dataclass
class HypervolumeConfig:
    enabled: bool = True
    mode: str = "auto_from_warmup"  # "fixed" | "auto_from_warmup" | "auto_from_seen" | "off"
    reference_point: Optional[List[float]] = None
    margin_mode: str = "relative"  # "relative" | "absolute"
    margin_value: float = 0.1
    warmup_stage_index: int = 0
    require_positive_contributions: bool = True
    zero_hv_fraction_warn_threshold: float = 0.25


def make_hypervolume() -> HypervolumeConfig:
    return HypervolumeConfig(
        enabled=True,
        mode="auto_from_warmup",
        reference_point=None,
        margin_mode="relative",
        margin_value=0.1,
        warmup_stage_index=0,
        require_positive_contributions=True,
        zero_hv_fraction_warn_threshold=0.25,
    )
