from __future__ import annotations

from functools import lru_cache
from pathlib import Path

import numpy as np
import pandas as pd


FREUDENAU_INSTALLED_KW = 172_000.0
FREUDENAU_ANNUAL_GENERATION_GWH = 1_052.0

_HERE = Path(__file__).resolve().parent
#
# This module now lives under:
#   Data/technology_data/run_of_river_hydro/Vienna/
# Therefore:
#   parents[0] = run_of_river_hydro
#   parents[1] = technology_data
#   parents[2] = Data
#   parents[3] = project root
# Using parents[2] would incorrectly point to .../Data and produce a duplicated
# path segment (.../Data/Data/profiles/...) after the hygiene move.
_PROJECT_ROOT = _HERE.parents[3]
_DAILY_PROXY_PATH = _PROJECT_ROOT / "Data" / "profiles" / "Vienna" / "hydro" / "freudenau_korneuburg_daily_flow.csv"


@lru_cache(maxsize=1)
def load_freudenau_daily_flow_proxy() -> pd.DataFrame:
    if not _DAILY_PROXY_PATH.exists():
        raise FileNotFoundError(f"[freudenau] Daily flow proxy not found: {_DAILY_PROXY_PATH}")

    df = pd.read_csv(_DAILY_PROXY_PATH, parse_dates=["date"])
    required = {"date", "q_min", "q_mean", "q_max"}
    missing = required.difference(df.columns)
    if missing:
        raise KeyError(f"[freudenau] Daily flow proxy is missing columns: {sorted(missing)}")

    df = df.copy()
    df["date"] = pd.to_datetime(df["date"], errors="coerce")
    df["q_mean"] = pd.to_numeric(df["q_mean"], errors="coerce")
    df = df.dropna(subset=["date", "q_mean"]).sort_values("date").reset_index(drop=True)
    if df.empty:
        raise ValueError("[freudenau] Daily flow proxy is empty after cleaning.")
    if bool((df["q_mean"] < 0.0).any()):
        raise ValueError("[freudenau] Daily flow proxy contains negative q_mean values.")
    return df


@lru_cache(maxsize=1)
def load_freudenau_daily_flow_climatology() -> pd.DataFrame:
    df = load_freudenau_daily_flow_proxy().copy()
    df["month"] = df["date"].dt.month.astype(int)
    df["day"] = df["date"].dt.day.astype(int)
    climatology = (
        df.groupby(["month", "day"], as_index=False)["q_mean"]
        .mean()
        .sort_values(["month", "day"])
        .reset_index(drop=True)
    )
    if climatology.empty:
        raise ValueError("[freudenau] Daily flow climatology is empty.")
    return climatology


def _daily_climatology_for_year(year: int) -> pd.DataFrame:
    year_i = int(year)
    daily_index = pd.date_range(f"{year_i}-01-01", f"{year_i}-12-31", freq="D")
    climatology = load_freudenau_daily_flow_climatology().copy()
    climatology["month"] = climatology["month"].astype(int)
    climatology["day"] = climatology["day"].astype(int)

    target = pd.DataFrame({"date": daily_index})
    target["month"] = target["date"].dt.month.astype(int)
    target["day"] = target["date"].dt.day.astype(int)
    target = target.merge(climatology, on=["month", "day"], how="left").sort_values("date").reset_index(drop=True)
    if bool(target["q_mean"].isna().any()):
        target["q_mean"] = target["q_mean"].interpolate(limit_direction="both")
    if bool(target["q_mean"].isna().any()):
        missing_days = target.loc[target["q_mean"].isna(), "date"]
        raise ValueError(
            f"[freudenau] Daily flow climatology for year {year_i} is incomplete. Missing days: "
            f"{missing_days.head().dt.strftime('%Y-%m-%d').tolist()}"
        )
    return target[["date", "q_mean"]]


@lru_cache(maxsize=8)
def load_freudenau_hourly_flow_proxy_for_year(year: int) -> pd.Series:
    year_i = int(year)
    daily = _daily_climatology_for_year(year_i).set_index("date")

    hourly_index = pd.date_range(f"{year_i}-01-01 00:00:00", f"{year_i}-12-31 23:00:00", freq="h")
    hourly_q_mean = daily["q_mean"].reindex(hourly_index.normalize()).to_numpy(dtype=float)
    if hourly_q_mean.size != hourly_index.size:
        raise ValueError(
            f"[freudenau] Hourly proxy construction failed for year {year_i}: "
            f"{hourly_q_mean.size} values for {hourly_index.size} timestamps."
        )
    return pd.Series(hourly_q_mean, index=hourly_index, dtype=float, name="q_mean_m3_per_s")


def load_freudenau_hourly_flow_proxy_context(
    timestamps: pd.DatetimeIndex | np.ndarray | list[object],
) -> pd.Series:
    ts = pd.DatetimeIndex(pd.to_datetime(np.asarray(timestamps).reshape(-1), errors="coerce"))
    if ts.size == 0:
        return pd.Series(dtype=float)
    if bool(pd.isna(ts).any()):
        raise ValueError("[freudenau] Timestamps contain NaT values.")

    ts = ts.tz_localize(None) if ts.tz is not None else ts
    full_year_parts = [load_freudenau_hourly_flow_proxy_for_year(int(year)) for year in sorted(ts.year.unique())]
    return pd.concat(full_year_parts).sort_index()


def load_freudenau_hourly_flow_proxy(timestamps: pd.DatetimeIndex | np.ndarray | list[object]) -> np.ndarray:
    ts = pd.DatetimeIndex(pd.to_datetime(np.asarray(timestamps).reshape(-1), errors="coerce"))
    if ts.size == 0:
        return np.zeros(0, dtype=float)
    if bool(pd.isna(ts).any()):
        raise ValueError("[freudenau] Timestamps contain NaT values.")

    ts = ts.tz_localize(None) if ts.tz is not None else ts
    full_year_series = load_freudenau_hourly_flow_proxy_context(ts)
    missing = ts[~ts.isin(full_year_series.index)]
    if len(missing) > 0:
        raise ValueError(
            "[freudenau] Hourly flow proxy does not cover all requested timestamps. "
            f"First missing timestamp: {missing[0]!s}"
        )
    return full_year_series.reindex(ts).to_numpy(dtype=float)
