from __future__ import annotations
from dataclasses import dataclass

@dataclass
class RunConfig:
    tag: str = "paper_run"


def make_run() -> RunConfig:
    return RunConfig(tag="paper_run")
