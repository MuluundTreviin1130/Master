from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict


@dataclass
class DispatchInput:
    """Canonical input contract for dispatch modes.

    Keys inside the dictionaries should reuse existing repo naming where
    possible. The schema stays intentionally lightweight so the current
    heuristic path and later MILP modes can share the same outer contract.
    """

    series: Dict[str, Any] = field(default_factory=dict)
    assets: Dict[str, float] = field(default_factory=dict)
    params: Dict[str, Any] = field(default_factory=dict)
    initial_state: Dict[str, float] = field(default_factory=dict)


@dataclass
class DispatchResult:
    """Canonical dispatch output.

    ``hourly`` should reuse existing IES output keys such as
    ``district_heat_pump_generation`` or ``district_biomass_chp_fuel_input_kg``
    so downstream registry, KPI and learning paths do not need a second
    vocabulary.
    """

    hourly: Dict[str, Any] = field(default_factory=dict)
    objective_terms: Dict[str, float] = field(default_factory=dict)
    diagnostics: Dict[str, Any] = field(default_factory=dict)
