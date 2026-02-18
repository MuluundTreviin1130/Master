from __future__ import annotations
from dataclasses import dataclass
from typing import List, Optional

@dataclass
class Bounds:
    """Design variables."""
    names: List[str]
    lower: List[float]
    upper: List[float]
    steps: Optional[List[float]] = None


def make_bounds(engine) -> Bounds:
    """Default bounds. Depends on engine.N_EC."""
    per_hh_cap = 54.0  # kWp/kWh per EC member (upper bound)
    return Bounds(
        names=["pv_kwp", "bess_kwh"],
        lower=[0.0, 0.0],
        upper=[per_hh_cap * float(engine.N_EC), per_hh_cap * float(engine.N_EC)],
        steps=[0.1,0.1],
    )

    # Alternatives (copy/paste)
    # return Bounds(names=["pv_kwp","bess_kwh"], lower=[0,0], upper=[50,50], steps=[0.5,0.5])
