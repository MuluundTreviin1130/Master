from __future__ import annotations

import numpy as np


def build_fixed_internal_prices(
    n_steps: int,
    *,
    community_buy_price: float,
    community_sell_price: float,
) -> tuple[np.ndarray, np.ndarray]:
    buy = np.full(n_steps, float(community_buy_price), dtype=float)
    sell = np.full(n_steps, float(community_sell_price), dtype=float)
    return buy, sell


def build_linked_internal_prices(
    grid_import_price: np.ndarray,
    grid_export_price: np.ndarray,
    *,
    beta: float,
) -> tuple[np.ndarray, np.ndarray]:
    imp = np.asarray(grid_import_price, dtype=float)
    exp = np.asarray(grid_export_price, dtype=float)
    b = min(1.0, max(0.0, float(beta)))
    internal = exp + b * (imp - exp)
    return internal.copy(), internal.copy()
