from __future__ import annotations

from dataclasses import dataclass


@dataclass
class ImpactsConfig:
    """LCA/impact settings.

    export_credit is kept configurable for future scenarios, but paper runs
    enforce export_credit == 0 for reproducibility.
    """

    export_credit: float = 0.0
    lca_static_root: str = "Data/LCA_data/static"


def make_impacts() -> ImpactsConfig:
    return ImpactsConfig()
