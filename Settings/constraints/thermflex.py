from __future__ import annotations

from dataclasses import dataclass


@dataclass
class ThermflexConstraintConfig:
    use_explicit_lower_bounds: bool = False
    constant_lower_bound_c: float | None = None
    day_lower_bound_c: float | None = None
    night_lower_bound_c: float | None = None
    comfort_band_k: float = 0.0
    reference_deadband_k: float = 0.5
    constrain_upper_temperature: bool = False
    use_event_response_bounds: bool = False
    enforce_event_peak_bounds: bool = True
    enforce_event_energy_bounds: bool = True
    enforce_recovery_cooldown: bool = True
    max_flex_duration_h: int = 0
    max_flex_events_per_day: int = 0
    activation_penalty_eur_per_member_h: float = 1e-4
    temperature_violation_penalty_eur_per_degree_h: float = 1e6
    allow_terminal_deviation: bool = True
    terminal_band_k: float = 0.0
