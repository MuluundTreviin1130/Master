from __future__ import annotations

from typing import Tuple

import numpy as np


def clear_ec(net_member_2d: np.ndarray) -> Tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """
    EC clearing for net supply/deficit per member.
    net_member_2d shape: [T, N_EC] with net = supply - demand.
    Returns:
        grid_import_1d, grid_export_1d, ec_sell_member_2d, ec_buy_member_2d, T_1d
    """
    net = np.asarray(net_member_2d, float)
    if net.ndim != 2:
        raise ValueError("net_member_2d must be 2D [T, N_EC]")
    
    # Assertion [REMOVE AFTER CHECK]
    assert net.shape[1] > 0, "[REMOVE AFTER CHECK] N_EC must be > 0"

    surplus = np.clip(net, 0.0, None)
    deficit = np.clip(-net, 0.0, None)

    S = np.sum(surplus, axis=1)
    D = np.sum(deficit, axis=1)
    T = np.minimum(S, D)

    S_safe = np.where(S > 0.0, S, 1.0)
    D_safe = np.where(D > 0.0, D, 1.0)

    ec_sell_member = surplus * (T / S_safe)[:, None]
    ec_buy_member = deficit * (T / D_safe)[:, None]

    grid_export = S - T
    grid_import = D - T

    return grid_import, grid_export, ec_sell_member, ec_buy_member, T


def split_trade_by_source(
    T_1d: np.ndarray,
    pv_surplus_2d: np.ndarray,
    ev_surplus_2d: np.ndarray,
    eps: float = 1e-9,
) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    """
    Split EC imports/exports by source using proportional allocation.
    Returns:
        ec_import_from_pv_1d, ec_import_from_ev_1d, ec_export_from_pv_1d
    """
    T = np.asarray(T_1d, float)
    pv = np.asarray(pv_surplus_2d, float)
    ev = np.asarray(ev_surplus_2d, float)

    pv_total = np.sum(pv, axis=1)
    ev_total = np.sum(ev, axis=1)
    denom = pv_total + ev_total + eps

    ec_import_from_pv = T * pv_total / denom
    ec_import_from_ev = T - ec_import_from_pv

    source_surplus = pv_total + ev_total
    ec_export_from_pv = np.maximum(source_surplus - T, 0.0) * (pv_total / denom)

    return ec_import_from_pv, ec_import_from_ev, ec_export_from_pv
