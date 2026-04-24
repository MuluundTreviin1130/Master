from __future__ import annotations

import numpy as np


def build_flat_tariff(
    n_steps: int,
    *,
    c_buy_grid: float,
    c_feed_grid: float,
) -> tuple[np.ndarray, np.ndarray, dict]:
    import_price = np.full(n_steps, float(c_buy_grid), dtype=float)
    export_price = np.full(n_steps, float(c_feed_grid), dtype=float)
    return import_price, export_price, {"mode": "flat"}
