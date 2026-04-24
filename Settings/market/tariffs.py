from __future__ import annotations

from dataclasses import dataclass, field
from typing import List

from .settlement import SettlementConfig, make_settlement


@dataclass
class FlatTariffConfig:
    enabled: bool = True


@dataclass
class TOUTariffConfig:
    peak_start_hour: int = 7
    peak_end_hour: int = 21
    price_spread: float = 0.50
    settlement: SettlementConfig = field(default_factory=lambda: SettlementConfig(mode="linked", beta=0.5))


@dataclass
class DynamicTariffConfig:
    signal_mode: str = "residual_load_proxy"
    dynamic_scale: float = 0.35
    price_floor_factor: float = 0.60
    price_cap_factor: float = 1.60
    settlement: SettlementConfig = field(default_factory=lambda: SettlementConfig(mode="linked", beta=0.5))


@dataclass
class ExportPenaltyTariffConfig:
    export_remuneration_factor: float = 0.50
    settlement: SettlementConfig = field(default_factory=lambda: SettlementConfig(mode="linked", beta=0.5))


@dataclass
class TariffCatalogConfig:
    available_arms: List[str] = field(default_factory=lambda: ["flat", "tou", "dynamic", "export_penalty"])
    flat: FlatTariffConfig = field(default_factory=FlatTariffConfig)
    tou: TOUTariffConfig = field(default_factory=TOUTariffConfig)
    dynamic: DynamicTariffConfig = field(default_factory=DynamicTariffConfig)
    export_penalty: ExportPenaltyTariffConfig = field(default_factory=ExportPenaltyTariffConfig)
    default_settlement: SettlementConfig = field(default_factory=make_settlement)


def make_tariffs() -> TariffCatalogConfig:
    return TariffCatalogConfig()
