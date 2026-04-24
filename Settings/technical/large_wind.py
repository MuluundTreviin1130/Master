from __future__ import annotations

from dataclasses import dataclass


@dataclass
class LargeWindConfig:
    reference_measurement_height_m: float = 10.0
    hub_height_m: float = 80.0
    shear_exponent: float = 0.18
    reference_air_density_kg_per_m3: float = 1.225
    cut_in_ms: float = 3.0
    rated_ms: float = 12.0
    cut_out_ms: float = 25.0


def make_large_wind() -> LargeWindConfig:
    return LargeWindConfig()
