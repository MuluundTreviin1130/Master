from __future__ import annotations

import numpy as np


def build_export_penalty_tariff(
    n_steps: int,
    *,
    c_buy_grid: float,
    c_feed_grid: float,
    export_remuneration_factor: float,
) -> tuple[np.ndarray, np.ndarray, dict]:
    factor = max(0.0, float(export_remuneration_factor))
    import_price = np.full(n_steps, float(c_buy_grid), dtype=float)
    export_price = np.full(n_steps, float(c_feed_grid) * factor, dtype=float)
    return import_price, export_price, {
        "mode": "export_penalty",
        "export_remuneration_factor": float(export_remuneration_factor),
    }
