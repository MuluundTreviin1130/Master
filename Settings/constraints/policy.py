from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List


@dataclass
class PolicyConstraintConfig:
    enabled_categories: List[str]
    cfg: Dict[str, Any]
