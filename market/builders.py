from __future__ import annotations

from typing import Any, Dict

import numpy as np

from market.settlement import build_fixed_internal_prices, build_linked_internal_prices
from market.tariffs import (
    build_dynamic_tariff,
    build_export_penalty_tariff,
    build_flat_tariff,
    build_tou_tariff,
)
from market.types import MarketBundle, TariffSeries


def _get_market_settings(settings: Any):
    market = getattr(settings, "market", None)
    if market is None:
        raise ValueError("[market] settings.market is missing.")
    return market


def _base_prices(params: Dict[str, Any]) -> tuple[float, float, float, float]:
    return (
        float(params.get("Cbuy_grid", 0.0)),
        float(params.get("Cfeed_grid", 0.0)),
        float(params.get("Cbuy_community", 0.0)),
        float(params.get("Cfeed_community", 0.0)),
    )


def build_market_bundle(settings: Any, params: Dict[str, Any], profiles: Dict[str, Any]) -> MarketBundle:
    market = _get_market_settings(settings)
    tariffs_cfg = market.tariffs
    active = str(getattr(market, "active_tariff_arm", "flat") or "flat").strip().lower()
    c_buy_grid, c_feed_grid, c_buy_comm, c_feed_comm = _base_prices(params)

    timestamps = profiles.get("timestamps")
    if timestamps is None:
        raise ValueError("[market] profiles['timestamps'] is required.")
    n_steps = len(timestamps)

    if active == "flat":
        grid_import, grid_export, meta = build_flat_tariff(
            n_steps,
            c_buy_grid=c_buy_grid,
            c_feed_grid=c_feed_grid,
        )
        comm_buy, comm_sell = build_fixed_internal_prices(
            n_steps,
            community_buy_price=c_buy_comm,
            community_sell_price=c_feed_comm,
        )
    elif active == "tou":
        cfg = tariffs_cfg.tou
        grid_import, grid_export, meta = build_tou_tariff(
            timestamps,
            c_buy_grid=c_buy_grid,
            c_feed_grid=c_feed_grid,
            peak_start_hour=cfg.peak_start_hour,
            peak_end_hour=cfg.peak_end_hour,
            price_spread=cfg.price_spread,
        )
        comm_buy, comm_sell = build_linked_internal_prices(
            grid_import,
            grid_export,
            beta=cfg.settlement.beta,
        )
    elif active == "dynamic":
        cfg = tariffs_cfg.dynamic
        grid_import, grid_export, meta = build_dynamic_tariff(
            profiles,
            c_buy_grid=c_buy_grid,
            c_feed_grid=c_feed_grid,
            dynamic_scale=cfg.dynamic_scale,
            price_floor_factor=cfg.price_floor_factor,
            price_cap_factor=cfg.price_cap_factor,
        )
        comm_buy, comm_sell = build_linked_internal_prices(
            grid_import,
            grid_export,
            beta=cfg.settlement.beta,
        )
    elif active == "export_penalty":
        cfg = tariffs_cfg.export_penalty
        grid_import, grid_export, meta = build_export_penalty_tariff(
            n_steps,
            c_buy_grid=c_buy_grid,
            c_feed_grid=c_feed_grid,
            export_remuneration_factor=cfg.export_remuneration_factor,
        )
        comm_buy, comm_sell = build_linked_internal_prices(
            grid_import,
            grid_export,
            beta=cfg.settlement.beta,
        )
    else:
        raise ValueError(f"[market] Unsupported active_tariff_arm='{active}'.")

    return MarketBundle(
        active_tariff_arm=active,
        tariffs=TariffSeries(
            grid_import_price=np.asarray(grid_import, dtype=float),
            grid_export_price=np.asarray(grid_export, dtype=float),
            community_buy_price=np.asarray(comm_buy, dtype=float),
            community_sell_price=np.asarray(comm_sell, dtype=float),
        ),
        metadata=meta,
    )
