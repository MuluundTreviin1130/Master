from __future__ import annotations

from dataclasses import dataclass


@dataclass
class StorageConstraintConfig:
    bess_cyclic_enabled: bool = False
    h2_cyclic_enabled: bool = True
