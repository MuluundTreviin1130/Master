from __future__ import annotations

"""Shared full-year input layer for Vienna DH thermflex analysis."""

import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd


def _bootstrap_project_root() -> Path:
    current = Path(__file__).resolve()
    for parent in current.parents:
        if (parent / "Optimization").is_dir() and (parent / "Data").is_dir():
            project_root = parent
            break
    else:
        raise RuntimeError(
            "[dh_thermflex_inputs] Project root with Optimization and Data directories not found."
        )
    project_root_str = str(project_root)
    if project_root_str not in sys.path:
        sys.path.insert(0, project_root_str)
    return project_root


PROJECT_ROOT = _bootstrap_project_root()

from Settings import get_settings  # noqa: E402
from Technical_model.energy_system.precompute.adapter import prepare_profiles_adapter  # noqa: E402
from Technical_model.technologies.district_heating.core.dh_demand import build_dh_demand  # noqa: E402
from dispatch.scenarios.historical_data import load_historical_price_days  # noqa: E402


DEFAULT_BASE_OVERRIDE_PATH = (
    PROJECT_ROOT
    / "Optimization"
    / "validation"
    / "model_validation"
    / "overrides"
    / "thermflex"
    / "vienna_ref2023_dh_baseline_constant_no_thermflex_paper_day_ahead.json"
)


@dataclass(frozen=True)
class DhThermflexFullYearContext:
    """Explicit yearly context for DH thermflex input-side analysis."""

    settings: Any
    timestamps: pd.DatetimeIndex
    hourly_system_df: pd.DataFrame
    member_hourly_frames: dict[str, pd.DataFrame]
    member_runtime_counts: dict[str, int]
    member_connected_shares: dict[str, float]
    source_override_path: Path


def load_vienna_dh_thermflex_full_year_context(
    *,
    base_override_path: Path | None = None,
) -> DhThermflexFullYearContext:
    """Load the explicit full-year Vienna paper context."""

    override_path = Path(base_override_path or DEFAULT_BASE_OVERRIDE_PATH).resolve()
    if not override_path.exists():
        raise FileNotFoundError(
            f"[dh_thermflex_inputs] Base override file not found: {override_path}"
        )
    overrides = json.loads(override_path.read_text(encoding="utf-8-sig"))
    overrides["run"] = {
        "tag": "vienna_ref2023_dh_full_year_analysis",
        "profile_start": "2023-01-01 00:00:00",
        "profile_hours": 8760,
    }
    settings = get_settings(overrides=overrides)
    package = prepare_profiles_adapter(settings)
    profiles = package.profiles

    timestamps = pd.DatetimeIndex(pd.to_datetime(np.asarray(profiles.get("timestamps"))))
    if len(timestamps) != 8760:
        raise ValueError(
            f"[dh_thermflex_inputs] Expected exactly 8760 hourly timestamps, got {len(timestamps)}."
        )
    if timestamps[0] != pd.Timestamp("2023-01-01 00:00:00"):
        raise ValueError(
            "[dh_thermflex_inputs] Expected full-year context to start at 2023-01-01 00:00:00."
        )

    space_heat_member_2d = _require_member_matrix(
        profiles=profiles,
        key="space_heat_member_2d",
        n_steps=len(timestamps),
    )
    hotwater_member_2d = _require_member_matrix(
        profiles=profiles,
        key="hotwater_member_2d",
        n_steps=len(timestamps),
    )
    load_member_2d = _require_member_matrix(
        profiles=profiles,
        key="load_member_2d",
        n_steps=len(timestamps),
    )
    hp_elec_heat_member_2d = _require_member_matrix(
        profiles=profiles,
        key="hp_elec_heat_member_2d",
        n_steps=len(timestamps),
    )
    hp_elec_cool_member_2d = _require_member_matrix(
        profiles=profiles,
        key="hp_elec_cool_member_2d",
        n_steps=len(timestamps),
    )

    dh_demand = build_dh_demand(settings, profiles)
    mc_auction = _historical_mc_price_series_eur_per_mwh(
        timestamps=timestamps,
        day_ahead_root=str(settings.dispatch.historical_day_ahead_root),
    )
    gas_price = _load_daily_price_csv_as_hourly(
        timestamps=timestamps,
        csv_path=Path(settings.dispatch.historical_gas_day_ahead_price_csv).resolve(),
        value_column="price_eur_per_mwh",
        label="historical_gas_day_ahead_price_csv",
    )
    co2_price = _load_daily_price_csv_as_hourly(
        timestamps=timestamps,
        csv_path=Path(settings.dispatch.historical_co2_price_csv).resolve(),
        value_column="price_eur_per_tco2",
        label="historical_co2_price_csv",
    )

    hourly_system_df = pd.DataFrame(
        {
            "timestamp": timestamps,
            "t_outdoor_c": _require_1d_profile(profiles, "T_outdoor", len(timestamps)) - 273.15,
            "irradiance_proxy": _require_1d_profile(profiles, "irradiance", len(timestamps)),
            "solargains_proxy": _require_1d_profile(profiles, "solargains", len(timestamps)),
            "electric_load_total_kwh": load_member_2d.sum(axis=1),
            "space_heat_total_kwh": space_heat_member_2d.sum(axis=1),
            "hotwater_total_kwh": hotwater_member_2d.sum(axis=1),
            "dh_space_heat_total_kwh": np.asarray(dh_demand["space_heat_total"], dtype=float),
            "dh_hotwater_total_kwh": np.asarray(dh_demand["hotwater_total"], dtype=float),
            "dh_total_kwh": np.asarray(dh_demand["total"], dtype=float),
            "mc_auction_eur_mwh": mc_auction,
            "gas_price_eur_mwh_fuel": gas_price,
            "co2_price_eur_tco2": co2_price,
        }
    )

    member_frames: dict[str, pd.DataFrame] = {}
    member_runtime_counts: dict[str, int] = {}
    member_connected_shares: dict[str, float] = {}
    member_index = 0
    active_members = [member for member in settings.engine.members.members if int(member.count) > 0]
    if len(active_members) != space_heat_member_2d.shape[1]:
        raise ValueError(
            "[dh_thermflex_inputs] Active member count does not match prepared member profile columns."
        )

    for member in active_members:
        building_key = str(member.building_key)
        member_runtime_counts[building_key] = int(member.count)
        connected_share = float(dh_demand["connected_share_by_type"].get(building_key, np.nan))
        if not np.isfinite(connected_share):
            raise ValueError(
                f"[dh_thermflex_inputs] Missing connected_share_by_type entry for building_key='{building_key}'."
            )
        member_connected_shares[building_key] = connected_share
        member_frames[building_key] = pd.DataFrame(
            {
                "timestamp": timestamps,
                "space_heat_kwh": space_heat_member_2d[:, member_index],
                "hotwater_kwh": hotwater_member_2d[:, member_index],
                "electric_load_kwh": load_member_2d[:, member_index],
                "hp_elec_heat_kwh": hp_elec_heat_member_2d[:, member_index],
                "hp_elec_cool_kwh": hp_elec_cool_member_2d[:, member_index],
                "dh_space_heat_kwh": np.asarray(dh_demand["space_heat_by_type"][building_key], dtype=float),
                "dh_hotwater_kwh": np.asarray(dh_demand["hotwater_by_type"][building_key], dtype=float),
                "dh_total_kwh": np.asarray(dh_demand["total_by_type"][building_key], dtype=float),
                "t_outdoor_c": hourly_system_df["t_outdoor_c"].to_numpy(dtype=float),
                "irradiance_proxy": hourly_system_df["irradiance_proxy"].to_numpy(dtype=float),
                "solargains_proxy": hourly_system_df["solargains_proxy"].to_numpy(dtype=float),
                "mc_auction_eur_mwh": hourly_system_df["mc_auction_eur_mwh"].to_numpy(dtype=float),
                "gas_price_eur_mwh_fuel": hourly_system_df["gas_price_eur_mwh_fuel"].to_numpy(dtype=float),
                "co2_price_eur_tco2": hourly_system_df["co2_price_eur_tco2"].to_numpy(dtype=float),
            }
        )
        member_index += 1

    return DhThermflexFullYearContext(
        settings=settings,
        timestamps=timestamps,
        hourly_system_df=hourly_system_df,
        member_hourly_frames=member_frames,
        member_runtime_counts=member_runtime_counts,
        member_connected_shares=member_connected_shares,
        source_override_path=override_path,
    )


def _require_member_matrix(
    *,
    profiles: dict[str, Any],
    key: str,
    n_steps: int,
) -> np.ndarray:
    if key not in profiles:
        raise KeyError(f"[dh_thermflex_inputs] Required profile '{key}' is missing.")
    arr = np.asarray(profiles[key], dtype=float)
    if arr.ndim != 2:
        raise ValueError(
            f"[dh_thermflex_inputs] Profile '{key}' must be 2D, got ndim={arr.ndim}."
        )
    if arr.shape[0] != n_steps:
        raise ValueError(
            f"[dh_thermflex_inputs] Profile '{key}' has {arr.shape[0]} steps, expected {n_steps}."
        )
    return arr


def _require_1d_profile(profiles: dict[str, Any], key: str, n_steps: int) -> np.ndarray:
    if key not in profiles:
        raise KeyError(f"[dh_thermflex_inputs] Required profile '{key}' is missing.")
    arr = np.asarray(profiles[key], dtype=float).reshape(-1)
    if arr.size != n_steps:
        raise ValueError(
            f"[dh_thermflex_inputs] Profile '{key}' has {arr.size} values, expected {n_steps}."
        )
    return arr


def _historical_mc_price_series_eur_per_mwh(
    *,
    timestamps: pd.DatetimeIndex,
    day_ahead_root: str,
) -> np.ndarray:
    daily_rows = load_historical_price_days(
        day_ahead_root,
        int(timestamps.min().year),
        int(timestamps.max().year),
    )
    by_date = {
        pd.Timestamp(row.date).normalize(): np.asarray(row.price, dtype=float)
        for row in daily_rows.itertuples(index=False)
    }
    out = np.zeros(len(timestamps), dtype=float)
    for idx, ts in enumerate(timestamps):
        key = pd.Timestamp(ts).normalize()
        prices = by_date.get(key)
        if prices is None:
            raise KeyError(
                f"[dh_thermflex_inputs] Missing day-ahead price profile for date {key.date()}."
            )
        out[idx] = float(prices[int(ts.hour)])
    return out


def _load_daily_price_csv_as_hourly(
    *,
    timestamps: pd.DatetimeIndex,
    csv_path: Path,
    value_column: str,
    label: str,
) -> np.ndarray:
    if not csv_path.exists():
        raise FileNotFoundError(f"[dh_thermflex_inputs] Missing {label}: {csv_path}")
    df = pd.read_csv(csv_path)
    if "date" not in df.columns:
        raise KeyError(
            f"[dh_thermflex_inputs] {label} is missing required column 'date': {csv_path}"
        )
    if value_column not in df.columns:
        raise KeyError(
            f"[dh_thermflex_inputs] {label} is missing required column '{value_column}': {csv_path}"
        )
    daily_values = (
        df.assign(date=pd.to_datetime(df["date"]).dt.normalize())
        .set_index("date")[value_column]
        .astype(float)
    )
    out = np.zeros(len(timestamps), dtype=float)
    for idx, ts in enumerate(timestamps):
        key = pd.Timestamp(ts).normalize()
        if key not in daily_values.index:
            raise KeyError(
                f"[dh_thermflex_inputs] {label} is missing price value for date {key.date()}."
            )
        out[idx] = float(daily_values.loc[key])
    return out
