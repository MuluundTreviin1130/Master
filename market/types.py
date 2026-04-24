from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict

import numpy as np


@dataclass
class TariffSeries:
    grid_import_price: np.ndarray
    grid_export_price: np.ndarray
    community_buy_price: np.ndarray
    community_sell_price: np.ndarray


@dataclass
class MarketBundle:
    active_tariff_arm: str
    tariffs: TariffSeries
    metadata: Dict[str, float | str] = field(default_factory=dict)
