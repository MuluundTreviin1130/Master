from __future__ import annotations
from dataclasses import dataclass
from typing import Optional

@dataclass
class RunConfig:
    tag: str = "paper_run"
    profile_start: Optional[str] = None
    profile_hours: Optional[int] = None


def make_run() -> RunConfig:
    return RunConfig(tag="paper_run")
