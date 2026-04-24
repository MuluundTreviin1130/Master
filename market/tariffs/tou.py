from __future__ import annotations

import numpy as np
import pandas as pd


def build_tou_tariff(
    timestamps,
    *,
    c_buy_grid: float,
    c_feed_grid: float,
    peak_start_hour: int,
    peak_end_hour: int,
    price_spread: float,
) -> tuple[np.ndarray, np.ndarray, dict]:
    ts = pd.to_datetime(timestamps)
    hours = np.asarray(ts.hour, dtype=int)
    peak = (hours >= int(peak_start_hour)) & (hours < int(peak_end_hour))
    spread = max(0.0, float(price_spread))
    high = float(c_buy_grid) * (1.0 + 0.5 * spread)
    low = float(c_buy_grid) * max(0.0, 1.0 - 0.5 * spread)
    import_price = np.where(peak, high, low).astype(float)
    export_price = np.full(import_price.shape[0], float(c_feed_grid), dtype=float)
    return import_price, export_price, {
        "mode": "tou",
        "peak_start_hour": int(peak_start_hour),
        "peak_end_hour": int(peak_end_hour),
        "price_spread": float(price_spread),
    }
