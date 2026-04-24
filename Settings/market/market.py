from __future__ import annotations

from dataclasses import dataclass, field

from .tariffs import TariffCatalogConfig, make_tariffs


@dataclass
class MarketConfig:
    """Top-level market configuration.

    ``active_tariff_arm`` controls the currently active tariff regime.
    Default stays ``flat`` so current runs are unchanged.
    """

    active_tariff_arm: str = "flat"
    tariffs: TariffCatalogConfig = field(default_factory=make_tariffs)


def make_market() -> MarketConfig:
    return MarketConfig()
