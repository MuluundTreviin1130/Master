from __future__ import annotations

from dataclasses import dataclass


@dataclass
class RunOfRiverHydroConfig:
    enabled: bool = False
    expandable: bool = False


def make_run_of_river_hydro(*, location: str) -> RunOfRiverHydroConfig:
    return RunOfRiverHydroConfig(enabled=str(location).strip().lower() == "vienna", expandable=False)

