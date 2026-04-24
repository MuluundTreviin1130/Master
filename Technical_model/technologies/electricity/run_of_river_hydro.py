from __future__ import annotations

import numpy as np
import pandas as pd


def _solve_capped_scale_kw_per_flow_unit(
    flow_proxy: np.ndarray,
    *,
    installed_kw: float,
    target_annual_generation_kwh: float,
    dt_h: float,
) -> float:
    q = np.clip(np.asarray(flow_proxy, dtype=float).reshape(-1), 0.0, None)
    installed_kw_f = float(installed_kw)
    target_kwh = float(target_annual_generation_kwh)
    dt_h_f = float(dt_h)

    if q.size == 0:
        raise ValueError("[run_of_river_hydro] flow_proxy must not be empty.")
    if installed_kw_f <= 0.0:
        raise ValueError("[run_of_river_hydro] installed_kw must be > 0.")
    if target_kwh < 0.0:
        raise ValueError("[run_of_river_hydro] target_annual_generation_kwh must be >= 0.")
    if dt_h_f <= 0.0:
        raise ValueError("[run_of_river_hydro] dt_h must be > 0.")
    if not np.any(q > 0.0):
        raise ValueError("[run_of_river_hydro] flow_proxy contains no positive values.")

    max_possible_kwh = installed_kw_f * q.size * dt_h_f
    if target_kwh > max_possible_kwh + 1e-6:
        raise ValueError(
            "[run_of_river_hydro] target annual generation exceeds the physical maximum implied by "
            f"installed_kw={installed_kw_f} and {q.size} hourly steps."
        )

    def annual_generation(scale: float) -> float:
        power_kw = np.minimum(installed_kw_f, scale * q)
        return float(np.sum(power_kw) * dt_h_f)

    lo = 0.0
    hi = installed_kw_f / max(1e-9, float(np.max(q)))
    while annual_generation(hi) < target_kwh:
        hi *= 2.0
        if hi > 1e9:
            raise RuntimeError("[run_of_river_hydro] Failed to bracket capped scaling factor.")

    for _ in range(80):
        mid = 0.5 * (lo + hi)
        if annual_generation(mid) >= target_kwh:
            hi = mid
        else:
            lo = mid
    return float(hi)


def simulate_run_of_river_hydro_generation(
    *,
    timestamps: pd.DatetimeIndex | np.ndarray | list[object],
    hourly_flow_proxy: pd.Series | np.ndarray | list[object],
    installed_kw: float,
    annual_generation_gwh: float,
    dt_h: float = 1.0,
) -> np.ndarray:
    ts = pd.DatetimeIndex(pd.to_datetime(np.asarray(timestamps).reshape(-1), errors="coerce"))
    if ts.size == 0:
        return np.zeros(0, dtype=float)
    if bool(pd.isna(ts).any()):
        raise ValueError("[run_of_river_hydro] timestamps contain NaT values.")
    ts = ts.tz_localize(None) if ts.tz is not None else ts

    installed_kw_f = float(installed_kw)
    if installed_kw_f <= 0.0:
        return np.zeros(ts.size, dtype=float)

    if isinstance(hourly_flow_proxy, pd.Series):
        proxy_series_full = hourly_flow_proxy.copy()
        proxy_series_full.index = pd.DatetimeIndex(pd.to_datetime(proxy_series_full.index, errors="coerce"))
        if bool(pd.isna(proxy_series_full.index).any()):
            raise ValueError("[run_of_river_hydro] hourly_flow_proxy series index contains NaT values.")
        proxy_series_full.index = (
            proxy_series_full.index.tz_localize(None) if proxy_series_full.index.tz is not None else proxy_series_full.index
        )
        flow_for_ts = proxy_series_full.reindex(ts)
        if bool(flow_for_ts.isna().any()):
            missing = flow_for_ts.index[flow_for_ts.isna()]
            raise ValueError(
                "[run_of_river_hydro] hourly_flow_proxy series does not cover all requested timestamps. "
                f"First missing timestamp: {missing[0]!s}"
            )
    else:
        flow = np.asarray(hourly_flow_proxy, dtype=float).reshape(-1)
        if flow.size != ts.size:
            raise ValueError(
                "[run_of_river_hydro] hourly_flow_proxy length must match timestamps length when passed as an array, "
                f"got {flow.size} vs {ts.size}."
            )
        flow_for_ts = pd.Series(flow, index=ts, dtype=float)
        proxy_series_full = flow_for_ts

    annual_generation_kwh = float(annual_generation_gwh) * 1_000_000.0
    out = np.zeros(ts.size, dtype=float)
    years = sorted(pd.Index(ts.year).unique())
    for year in years:
        mask = ts.year == int(year)
        year_start = pd.Timestamp(year=int(year), month=1, day=1, hour=0)
        year_end = pd.Timestamp(year=int(year), month=12, day=31, hour=23)
        full_year_index = pd.date_range(year_start, year_end, freq="h")
        full_year_flow = proxy_series_full if proxy_series_full.index.equals(full_year_index) else proxy_series_full.reindex(full_year_index)
        if bool(full_year_flow.isna().any()):
            missing = full_year_flow.index[full_year_flow.isna()]
            raise ValueError(
                "[run_of_river_hydro] hourly_flow_proxy does not provide full-year context for annual normalization. "
                f"First missing timestamp in year {year}: {missing[0]!s}"
            )
        scale = _solve_capped_scale_kw_per_flow_unit(
            full_year_flow.to_numpy(dtype=float),
            installed_kw=installed_kw_f,
            target_annual_generation_kwh=annual_generation_kwh,
            dt_h=dt_h,
        )
        selected_year_flow = flow_for_ts.iloc[np.where(np.asarray(mask, dtype=bool))[0]].to_numpy(dtype=float)
        year_power_kw = np.minimum(installed_kw_f, scale * np.clip(selected_year_flow, 0.0, None))
        out[np.asarray(mask, dtype=bool)] = year_power_kw * float(dt_h)
    return out
