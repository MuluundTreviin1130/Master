from __future__ import annotations

import numpy as np


def build_dynamic_tariff(
    profiles,
    *,
    c_buy_grid: float,
    c_feed_grid: float,
    dynamic_scale: float,
    price_floor_factor: float,
    price_cap_factor: float,
) -> tuple[np.ndarray, np.ndarray, dict]:
    load_member = np.asarray(profiles["load_member_2d"], dtype=float)
    pv_generation_w = np.asarray(profiles["pv_generation"], dtype=float)
    pv_reference_kwh = pv_generation_w / 1000.0
    residual = load_member.sum(axis=1) - pv_reference_kwh
    residual_centered = residual - float(np.mean(residual))
    scale = float(np.std(residual_centered))
    if scale <= 1e-12:
        signal = np.zeros_like(residual_centered)
    else:
        signal = residual_centered / scale

    alpha = max(0.0, float(dynamic_scale))
    raw_import = float(c_buy_grid) * (1.0 + alpha * signal)
    floor_val = float(c_buy_grid) * max(0.0, float(price_floor_factor))
    cap_val = float(c_buy_grid) * max(float(price_floor_factor), float(price_cap_factor))
    import_price = np.clip(raw_import, floor_val, cap_val)
    export_price = np.full(import_price.shape[0], float(c_feed_grid), dtype=float)
    return import_price.astype(float), export_price, {
        "mode": "dynamic",
        "signal_mode": "residual_load_proxy",
        "dynamic_scale": float(dynamic_scale),
        "price_floor_factor": float(price_floor_factor),
        "price_cap_factor": float(price_cap_factor),
    }
