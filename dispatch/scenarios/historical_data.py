from __future__ import annotations

from functools import lru_cache
from io import StringIO
from pathlib import Path
from typing import Any, Dict, List
import warnings
from zipfile import ZipFile

import numpy as np
import pandas as pd

from dispatch.core import DispatchInput
from .hdd import heating_degree_hours, require_ambient_temperature_c
from Technical_model.technologies.electricity.large_wind import simulate_large_wind_generation
from Technical_model.technologies.electricity.small_wind import simulate_small_wind_generation


HEATING_SEASON_DAILY_AVG_TEMP_THRESHOLD_C = 12.0


def _daily_hourly_arrays(df: pd.DataFrame, *, ts_col: str, value_cols: List[str]) -> pd.DataFrame:
    if df.empty:
        return pd.DataFrame(columns=["date", *value_cols])

    work = df.copy()
    work[ts_col] = pd.to_datetime(work[ts_col], errors="coerce")
    work = work.dropna(subset=[ts_col]).copy()
    work["date"] = work[ts_col].dt.normalize()
    work["hour"] = work[ts_col].dt.hour
    grouped = work.groupby(["date", "hour"], sort=True)[value_cols].mean()

    wide_by_col: dict[str, pd.DataFrame] = {}
    valid_mask: pd.Series | None = None
    for col in value_cols:
        wide = grouped[col].unstack("hour").reindex(columns=range(24))
        wide = wide.astype(float).interpolate(axis=1, limit_direction="both")
        wide_by_col[col] = wide
        col_valid = ~wide.isna().any(axis=1)
        valid_mask = col_valid if valid_mask is None else (valid_mask & col_valid)

    if valid_mask is None:
        return pd.DataFrame(columns=["date", *value_cols])

    valid_dates = valid_mask.index[valid_mask]
    out: dict[str, Any] = {"date": valid_dates.to_numpy()}
    for col, wide in wide_by_col.items():
        out[col] = list(wide.loc[valid_dates, range(24)].to_numpy(dtype=float))
    return pd.DataFrame(out)


def _align_daily(values: Any, n: int, *, fill_value: float) -> np.ndarray:
    arr = np.asarray(values, dtype=float).reshape(-1)
    if arr.size == n:
        return arr
    if arr.size == 0:
        return np.full(n, float(fill_value), dtype=float)
    if arr.size > n:
        return arr[:n]
    return np.pad(arr, (0, n - arr.size), constant_values=float(arr[-1]))


@lru_cache(maxsize=4)
def load_historical_weather_days(weather_csv_path: str) -> pd.DataFrame:
    path = Path(weather_csv_path)
    if not path.exists():
        raise FileNotFoundError(f"[dispatch.scenarios] Historical weather file not found: {path}")

    df = pd.read_csv(
        path,
        sep=";",
        usecols=["time", "cglo", "tl", "ff", "p"],
        dtype={"cglo": float, "tl": float, "ff": float, "p": float},
    )
    required = {"time", "cglo", "tl", "ff", "p"}
    missing = required.difference(df.columns)
    if missing:
        raise KeyError(f"[dispatch.scenarios] Historical weather file is missing columns: {sorted(missing)}")

    ts_utc = pd.to_datetime(df["time"], utc=True, errors="coerce")
    work = pd.DataFrame(
        {
            "ts_local": ts_utc.dt.tz_convert("Europe/Vienna").dt.tz_localize(None),
            "temperature": pd.to_numeric(df["tl"], errors="coerce"),
            "solar": pd.to_numeric(df["cglo"], errors="coerce"),
            "wind_speed": pd.to_numeric(df["ff"], errors="coerce"),
            "pressure": pd.to_numeric(df["p"], errors="coerce"),
        }
    ).dropna(subset=["ts_local", "temperature", "solar", "wind_speed", "pressure"])

    return _daily_hourly_arrays(
        work,
        ts_col="ts_local",
        value_cols=["temperature", "solar", "wind_speed", "pressure"],
    )


@lru_cache(maxsize=4)
def load_historical_pvgis_days(pvgis_csv_path: str) -> pd.DataFrame:
    path = Path(pvgis_csv_path)
    if not path.exists():
        raise FileNotFoundError(f"[dispatch.scenarios] Historical PVGIS file not found: {path}")

    lines = path.read_text(encoding="utf-8-sig", errors="replace").splitlines()
    try:
        header_idx = next(i for i, line in enumerate(lines) if line.startswith("time,"))
        footer_idx = next(i for i, line in enumerate(lines[header_idx + 1 :], start=header_idx + 1) if line.startswith("P: "))
    except StopIteration as exc:
        raise ValueError(f"[dispatch.scenarios] Could not parse PVGIS hourly block from {path}") from exc

    csv_text = "\n".join(lines[header_idx:footer_idx])
    df = pd.read_csv(StringIO(csv_text))
    required = {"time", "P", "G(i)", "T2m", "WS10m"}
    missing = required.difference(df.columns)
    if missing:
        raise KeyError(f"[dispatch.scenarios] PVGIS file is missing columns: {sorted(missing)}")

    ts_local = pd.to_datetime(df["time"].astype(str), format="%Y%m%d:%H%M", errors="coerce")
    work = pd.DataFrame(
        {
            "ts_local": ts_local,
            "pv_power_ref": pd.to_numeric(df["P"], errors="coerce"),
            "solar_poa": pd.to_numeric(df["G(i)"], errors="coerce"),
            "pv_temperature": pd.to_numeric(df["T2m"], errors="coerce"),
            "ws10m": pd.to_numeric(df["WS10m"], errors="coerce"),
        }
    ).dropna(subset=["ts_local", "pv_power_ref", "solar_poa", "pv_temperature", "ws10m"])

    return _daily_hourly_arrays(
        work,
        ts_col="ts_local",
        value_cols=["pv_power_ref", "solar_poa", "pv_temperature", "ws10m"],
    )


def _read_price_text_from_year_dir(year_dir: Path) -> tuple[str, str]:
    files = sorted([p for p in year_dir.iterdir() if p.is_file()])
    if not files:
        raise FileNotFoundError(f"[dispatch.scenarios] No day-ahead files found in {year_dir}")

    for file in files:
        if file.suffix.lower() == ".csv":
            raw = file.read_bytes()
            encoding = "utf-16" if raw.startswith((b"\xff\xfe", b"\xfe\xff")) else "utf-8-sig"
            return file.name, raw.decode(encoding, errors="replace")

    for file in files:
        if file.suffix.lower() == ".zip" and "English" in file.name:
            with ZipFile(file) as zf:
                names = [name for name in zf.namelist() if name.lower().endswith(".csv")]
                if not names:
                    continue
                return f"{file.name}:{names[0]}", zf.read(names[0]).decode("utf-8-sig", errors="replace")

    raise ValueError(
        f"[dispatch.scenarios] Expected a direct CSV or an English ZIP day-ahead export in {year_dir}, found: {[p.name for p in files]}"
    )


def _load_price_year(year_dir: Path) -> pd.DataFrame:
    source_name, text = _read_price_text_from_year_dir(year_dir)
    header = text.splitlines()[0].replace("\ufeff", "")
    separator = ";" if ";" in header else ","
    dayfirst = separator == ";"

    from_col = "Time from [CET/CEST]" if "Time from [CET/CEST]" in header else "Zeit von [CET/CEST]"
    to_col = "Time to [CET/CEST]" if "Time to [CET/CEST]" in header else "Zeit bis [CET/CEST]"
    mc_col = "Price MC Auction [EUR/MWh]" if "Price MC Auction [EUR/MWh]" in header else "Preis MC Auktion [EUR/MWh]"
    usecols = [from_col, to_col]
    if mc_col not in header:
        warnings.warn(
            f"[dispatch.scenarios] Skipping day-ahead year '{year_dir.name}' because 'MC Auction' is unavailable in {source_name}.",
            RuntimeWarning,
            stacklevel=2,
        )
        return pd.DataFrame(columns=["date", "price", "source_name", "price_source"])
    usecols.append(mc_col)
    df = pd.read_csv(
        StringIO(text),
        sep=separator,
        decimal="," if separator == ";" else ".",
        usecols=usecols,
        dtype=str,
        low_memory=False,
    )
    df.columns = [str(col).replace("\ufeff", "").strip() for col in df.columns]

    from_raw = df[from_col].astype(str).str.strip().str.replace("2A", "2", regex=False).str.replace("2B", "2", regex=False)
    to_raw = df[to_col].astype(str).str.strip().str.replace("2A", "2", regex=False).str.replace("2B", "2", regex=False)
    work = pd.DataFrame(
        {
            "from_ts": pd.to_datetime(from_raw, dayfirst=dayfirst, errors="coerce"),
            "to_ts": pd.to_datetime(to_raw, dayfirst=dayfirst, errors="coerce"),
            "mc_price": pd.to_numeric(df[mc_col].replace({"-": None, "": None}), errors="coerce"),
        }
    ).dropna(subset=["from_ts", "to_ts"])
    if int(work["mc_price"].notna().sum()) <= 0:
        warnings.warn(
            f"[dispatch.scenarios] Skipping day-ahead year '{year_dir.name}' because 'MC Auction' is empty in {source_name}.",
            RuntimeWarning,
            stacklevel=2,
        )
        return pd.DataFrame(columns=["date", "price", "source_name", "price_source"])

    work["price"] = work["mc_price"]
    work = work.dropna(subset=["price"]).copy()
    work["hour_ts"] = work["from_ts"].dt.floor("h")

    hourly = work.groupby("hour_ts", as_index=False)["price"].mean()
    out = _daily_hourly_arrays(hourly, ts_col="hour_ts", value_cols=["price"])
    out["source_name"] = source_name
    out["price_source"] = "mc_price"
    expected_days = 366 if int(year_dir.name) % 4 == 0 and (int(year_dir.name) % 100 != 0 or int(year_dir.name) % 400 == 0) else 365
    if len(out) < expected_days:
        warnings.warn(
            f"[dispatch.scenarios] Day-ahead year '{year_dir.name}' is incomplete for 'MC Auction' in {source_name}: {len(out)} daily profiles instead of {expected_days}.",
            RuntimeWarning,
            stacklevel=2,
        )
    return out


@lru_cache(maxsize=4)
def load_historical_price_days(day_ahead_root: str, min_year: int, max_year: int) -> pd.DataFrame:
    root = Path(day_ahead_root)
    if not root.exists():
        raise FileNotFoundError(f"[dispatch.scenarios] Historical day-ahead directory not found: {root}")
    if int(min_year) < 2020:
        warnings.warn(
            f"[dispatch.scenarios] Historical day-ahead MC series is only robust from 2020 onward. Requested min_year={min_year}; older years will likely be skipped.",
            RuntimeWarning,
            stacklevel=2,
        )

    frames: list[pd.DataFrame] = []
    for year in range(int(min_year), int(max_year) + 1):
        year_dir = root / str(year)
        if not year_dir.exists():
            continue
        year_df = _load_price_year(year_dir)
        if not year_df.empty:
            frames.append(year_df)

    if not frames:
        raise FileNotFoundError(f"[dispatch.scenarios] No historical MC Auction day-ahead files found in {root}")

    out = pd.concat(frames, ignore_index=True)
    out = out.sort_values("date").drop_duplicates(subset=["date"], keep="last").reset_index(drop=True)
    return out


@lru_cache(maxsize=8)
def _load_historical_daily_price_days(
    csv_path: str,
    *,
    min_year: int,
    max_year: int,
    value_column_candidates: tuple[str, ...],
    output_value_name: str,
    dataset_label: str,
) -> pd.DataFrame:
    path = Path(csv_path)
    if not path.exists():
        raise FileNotFoundError(f"[dispatch.scenarios] Historical {dataset_label} file not found: {path}")
    df = pd.read_csv(path)
    normalized = {str(col).strip().lower(): str(col) for col in df.columns}
    date_col = next(
        (
            normalized[key]
            for key in (
                "date",
                "day",
                "trading_date",
                "gas_day",
            )
            if key in normalized
        ),
        None,
    )
    price_col = next(
        (normalized[key] for key in value_column_candidates if key in normalized),
        None,
    )
    if date_col is None or price_col is None:
        raise KeyError(
            f"[dispatch.scenarios] Historical {dataset_label} CSV requires a date column and one of the value "
            f"columns {list(value_column_candidates)}."
        )
    work = pd.DataFrame(
        {
            "date": pd.to_datetime(df[date_col], errors="coerce").dt.normalize(),
            output_value_name: pd.to_numeric(df[price_col], errors="coerce"),
        }
    ).dropna(subset=["date", output_value_name])
    work = work[
        (work["date"].dt.year >= int(min_year)) & (work["date"].dt.year <= int(max_year))
    ].copy()
    if work.empty:
        raise ValueError(
            f"[dispatch.scenarios] Historical {dataset_label} CSV has no valid rows in [{min_year}, {max_year}]."
        )
    return work.sort_values("date").drop_duplicates(subset=["date"], keep="last").reset_index(drop=True)


@lru_cache(maxsize=4)
def load_historical_gas_price_days(gas_price_csv_path: str, min_year: int, max_year: int) -> pd.DataFrame:
    return _load_historical_daily_price_days(
        gas_price_csv_path,
        min_year=min_year,
        max_year=max_year,
        value_column_candidates=(
            "price_eur_per_mwh",
            "ceghix_eur_per_mwh",
            "gas_price_eur_per_mwh",
            "cegh_day_ahead_eur_per_mwh",
            "price",
        ),
        output_value_name="gas_price",
        dataset_label="gas-price",
    )


@lru_cache(maxsize=4)
def load_historical_co2_price_days(co2_price_csv_path: str, min_year: int, max_year: int) -> pd.DataFrame:
    return _load_historical_daily_price_days(
        co2_price_csv_path,
        min_year=min_year,
        max_year=max_year,
        value_column_candidates=(
            "price_eur_per_tco2",
            "co2_price_eur_per_tco2",
            "ets_price_eur_per_tco2",
            "price",
        ),
        output_value_name="co2_price",
        dataset_label="CO2-price",
    )


@lru_cache(maxsize=4)
def load_joint_historical_daily_dataset(
    weather_csv_path: str,
    pvgis_csv_path: str,
    day_ahead_root: str,
    min_year: int,
    max_year: int,
) -> pd.DataFrame:
    weather = load_historical_weather_days(weather_csv_path)
    pvgis = load_historical_pvgis_days(pvgis_csv_path)
    prices = load_historical_price_days(day_ahead_root, min_year, max_year)
    merged = weather.merge(pvgis, on="date", how="inner")
    merged = merged.merge(prices[["date", "price", "source_name", "price_source"]], on="date", how="inner")
    merged = merged[
        (merged["date"].dt.year >= int(min_year)) & (merged["date"].dt.year <= int(max_year))
    ].copy()
    merged["dayofyear"] = merged["date"].dt.dayofyear
    return merged.sort_values("date").reset_index(drop=True)


def _apply_heating_season_filter(df: pd.DataFrame, *, temp_col: str = "temperature") -> pd.DataFrame:
    if df.empty or temp_col not in df.columns:
        return df.copy()
    daily_avg_temp_c = np.stack(df[temp_col].to_list(), axis=0).mean(axis=1)
    mask = daily_avg_temp_c < HEATING_SEASON_DAILY_AVG_TEMP_THRESHOLD_C
    out = df.loc[mask].copy()
    out["daily_avg_temperature_c"] = daily_avg_temp_c[mask]
    return out.reset_index(drop=True)


@lru_cache(maxsize=4)
def load_joint_historical_dispatch_daily_dataset(
    weather_csv_path: str,
    day_ahead_root: str,
    gas_day_ahead_price_csv_path: str,
    gas_balance_price_csv_path: str,
    co2_price_csv_path: str,
    min_year: int,
    max_year: int,
    heating_season_only: bool = True,
) -> pd.DataFrame:
    weather = load_historical_weather_days(weather_csv_path)
    prices = load_historical_price_days(day_ahead_root, min_year, max_year)
    merged = weather.merge(prices[["date", "price", "source_name", "price_source"]], on="date", how="inner")
    gas_da_path = str(gas_day_ahead_price_csv_path or "").strip()
    gas_balance_path = str(gas_balance_price_csv_path or "").strip()
    if gas_da_path:
        gas_prices = load_historical_gas_price_days(gas_da_path, min_year, max_year).rename(
            columns={"gas_price": "gas_day_ahead_price"}
        )
        merged = merged.merge(gas_prices[["date", "gas_day_ahead_price"]], on="date", how="inner")
    if gas_balance_path:
        gas_balance_prices = load_historical_gas_price_days(gas_balance_path, min_year, max_year).rename(
            columns={"gas_price": "gas_balance_price"}
        )
        merged = merged.merge(gas_balance_prices[["date", "gas_balance_price"]], on="date", how="inner")
    co2_path = str(co2_price_csv_path or "").strip()
    if co2_path:
        co2_prices = load_historical_co2_price_days(co2_path, min_year, max_year)
        merged = merged.merge(co2_prices[["date", "co2_price"]], on="date", how="inner")
    merged = merged[
        (merged["date"].dt.year >= int(min_year)) & (merged["date"].dt.year <= int(max_year))
    ].copy()
    if heating_season_only:
        merged = _apply_heating_season_filter(merged, temp_col="temperature")
    merged["dayofyear"] = merged["date"].dt.dayofyear
    return merged.sort_values("date").reset_index(drop=True)


def _safe_ratio(numerator: np.ndarray, denominator: np.ndarray, *, default: float = 1.0) -> np.ndarray:
    out = np.full_like(numerator, float(default), dtype=float)
    mask = np.abs(denominator) > 1e-9
    out[mask] = numerator[mask] / denominator[mask]
    out[~np.isfinite(out)] = float(default)
    return out


def _pv_from_irradiance(
    base_pv: np.ndarray,
    base_irradiance: np.ndarray,
    scenario_irradiance: np.ndarray,
) -> np.ndarray:
    ratio = _safe_ratio(
        np.clip(np.asarray(scenario_irradiance, dtype=float), 0.0, None),
        np.clip(np.asarray(base_irradiance, dtype=float), 0.0, None),
        default=1.0,
    )
    return np.clip(np.asarray(base_pv, dtype=float) * ratio, 0.0, None)


def _simulate_wind_generation(
    *,
    kind: str,
    installed_kw: float,
    wind_speed_ms: np.ndarray,
    temperature_c: np.ndarray,
    pressure_hpa: np.ndarray,
    settings_obj: Any,
) -> np.ndarray:
    if float(installed_kw) <= 0.0:
        return np.zeros_like(np.asarray(wind_speed_ms, dtype=float))

    if kind == "small":
        cfg = getattr(settings_obj, "small_wind", None)
        return simulate_small_wind_generation(
            installed_kw=float(installed_kw),
            wind_speed_ms=np.asarray(wind_speed_ms, dtype=float),
            reference_height_m=float(getattr(cfg, "reference_measurement_height_m")),
            hub_height_m=float(getattr(cfg, "hub_height_m")),
            shear_exponent=float(getattr(cfg, "shear_exponent")),
            cut_in_ms=float(getattr(cfg, "cut_in_ms")),
            rated_ms=float(getattr(cfg, "rated_ms")),
            cut_out_ms=float(getattr(cfg, "cut_out_ms")),
            temperature_c=np.asarray(temperature_c, dtype=float),
            pressure_hpa=np.asarray(pressure_hpa, dtype=float),
            reference_air_density_kg_per_m3=float(getattr(cfg, "reference_air_density_kg_per_m3")),
            dt_h=1.0,
        )
    if kind == "large":
        cfg = getattr(settings_obj, "large_wind", None)
        return simulate_large_wind_generation(
            installed_kw=float(installed_kw),
            wind_speed_ms=np.asarray(wind_speed_ms, dtype=float),
            reference_height_m=float(getattr(cfg, "reference_measurement_height_m")),
            hub_height_m=float(getattr(cfg, "hub_height_m")),
            shear_exponent=float(getattr(cfg, "shear_exponent")),
            cut_in_ms=float(getattr(cfg, "cut_in_ms")),
            rated_ms=float(getattr(cfg, "rated_ms")),
            cut_out_ms=float(getattr(cfg, "cut_out_ms")),
            temperature_c=np.asarray(temperature_c, dtype=float),
            pressure_hpa=np.asarray(pressure_hpa, dtype=float),
            reference_air_density_kg_per_m3=float(getattr(cfg, "reference_air_density_kg_per_m3")),
            dt_h=1.0,
        )
    raise ValueError(f"[dispatch.scenarios] Unsupported wind kind '{kind}'.")


@lru_cache(maxsize=4)
def build_historical_residual_library(
    weather_csv_path: str,
    pvgis_csv_path: str,
    day_ahead_root: str,
    min_year: int,
    max_year: int,
) -> pd.DataFrame:
    history = load_joint_historical_daily_dataset(weather_csv_path, pvgis_csv_path, day_ahead_root, min_year, max_year)
    climate_rows: list[dict[str, Any]] = []
    for doy, group in history.groupby("dayofyear", sort=True):
        climate_rows.append(
            {
                "dayofyear": int(doy),
                "temperature": np.mean(np.stack(group["temperature"].to_list(), axis=0), axis=0),
                "pressure": np.mean(np.stack(group["pressure"].to_list(), axis=0), axis=0),
                "pv_power_ref": np.mean(np.stack(group["pv_power_ref"].to_list(), axis=0), axis=0),
                "solar_poa": np.mean(np.stack(group["solar_poa"].to_list(), axis=0), axis=0),
                "ws10m": np.mean(np.stack(group["ws10m"].to_list(), axis=0), axis=0),
                "price": np.mean(np.stack(group["price"].to_list(), axis=0), axis=0),
            }
        )
    climate = pd.DataFrame(climate_rows).sort_values("dayofyear").set_index("dayofyear")

    rows: list[dict[str, Any]] = []
    for row in history.itertuples(index=False):
        base = climate.loc[int(row.dayofyear)]
        temp_actual = np.asarray(row.temperature, dtype=float)
        temp_base = np.asarray(base["temperature"], dtype=float)
        pv_actual = np.asarray(row.pv_power_ref, dtype=float)
        pv_base = np.asarray(base["pv_power_ref"], dtype=float)
        solar_actual = np.asarray(row.solar_poa, dtype=float)
        solar_base = np.asarray(base["solar_poa"], dtype=float)
        ws10m_actual = np.asarray(row.ws10m, dtype=float)
        ws10m_base = np.asarray(base["ws10m"], dtype=float)
        pressure_actual = np.asarray(row.pressure, dtype=float)
        pressure_base = np.asarray(base["pressure"], dtype=float)
        price_actual = np.asarray(row.price, dtype=float)
        price_base = np.asarray(base["price"], dtype=float)

        hdd_actual = heating_degree_hours(temp_actual, ctx="historical residual actual")
        hdd_base = heating_degree_hours(temp_base, ctx="historical residual climate")

        rows.append(
            {
                "date": pd.Timestamp(row.date),
                "dayofyear": int(row.dayofyear),
                "temperature_residual": temp_actual - temp_base,
                "pv_factor": np.clip(_safe_ratio(np.clip(pv_actual, 0.0, None), np.clip(pv_base, 0.0, None), default=1.0), 0.0, 4.0),
                "solar_poa_residual": solar_actual - solar_base,
                "ws10m_residual": ws10m_actual - ws10m_base,
                "pressure_residual": pressure_actual - pressure_base,
                "hdd_factor": np.clip(_safe_ratio(hdd_actual, hdd_base, default=1.0), 0.1, 4.0),
                "price_residual": price_actual - price_base,
                "price_source": str(row.price_source),
            }
        )
    return pd.DataFrame(rows).sort_values("date").reset_index(drop=True)


@lru_cache(maxsize=4)
def build_historical_dispatch_day_library(
    weather_csv_path: str,
    day_ahead_root: str,
    gas_day_ahead_price_csv_path: str,
    gas_balance_price_csv_path: str,
    co2_price_csv_path: str,
    min_year: int,
    max_year: int,
    heating_season_only: bool = True,
) -> pd.DataFrame:
    history = load_joint_historical_dispatch_daily_dataset(
        weather_csv_path,
        day_ahead_root,
        gas_day_ahead_price_csv_path,
        gas_balance_price_csv_path,
        co2_price_csv_path,
        min_year,
        max_year,
        heating_season_only=heating_season_only,
    )
    return history.sort_values("date").reset_index(drop=True)


def _uniform_subsample(df: pd.DataFrame, n_keep: int) -> pd.DataFrame:
    if n_keep <= 0 or len(df) <= n_keep:
        return df.reset_index(drop=True)
    idx = np.linspace(0, len(df) - 1, num=n_keep, dtype=int)
    idx = np.unique(idx)
    return df.iloc[idx].reset_index(drop=True)


def build_ies_historical_scenarios(
    dispatch_input: DispatchInput,
    *,
    settings_obj: Any,
    timestamps: Any,
) -> List[Dict[str, Any]]:
    # Current stochastic DH path:
    # - build historical day scenarios directly from MC auction price + ambient temperature
    # - filter to heating-season days using the same daily-mean threshold logic as the heating model
    # - derive hourly district space heat from the scenario temperature afterwards
    # This keeps the reduction space compact and avoids counting temperature and derived space heat twice.
    time_index = pd.to_datetime(np.asarray(timestamps).reshape(-1), errors="coerce")
    if time_index.size == 0 or pd.isna(time_index[0]):
        return []

    dispatch_cfg = getattr(settings_obj, "dispatch", None)
    weather_path = str(getattr(dispatch_cfg, "historical_weather_path", "") or "").strip()
    price_root = str(getattr(dispatch_cfg, "historical_day_ahead_root", "") or "").strip()
    gas_day_ahead_price_csv_path = str(
        getattr(dispatch_cfg, "historical_gas_day_ahead_price_csv", "")
        or getattr(dispatch_cfg, "historical_gas_price_csv", "")
        or ""
    ).strip()
    gas_balance_price_csv_path = str(
        getattr(dispatch_cfg, "historical_gas_balance_price_csv", "") or ""
    ).strip()
    co2_price_csv_path = str(
        getattr(dispatch_cfg, "historical_co2_price_csv", "") or ""
    ).strip()
    min_year = int(getattr(dispatch_cfg, "historical_min_year", 2020) or 2020)
    max_year = int(getattr(dispatch_cfg, "historical_max_year", 2025) or 2025)
    heating_season_only = bool(getattr(dispatch_cfg, "historical_heating_season_only", True))
    if not weather_path or not price_root:
        raise ValueError("[dispatch.scenarios] Historical scenario source requires weather and day-ahead paths in settings.dispatch.")

    day_library = build_historical_dispatch_day_library(
        weather_path,
        price_root,
        gas_day_ahead_price_csv_path,
        gas_balance_price_csv_path,
        co2_price_csv_path,
        min_year,
        max_year,
        heating_season_only=heating_season_only,
    )
    target_date = pd.Timestamp(time_index[0]).normalize()
    n_raw = int(dispatch_input.params.get("dispatch_n_raw_scenarios", 0) or 0)
    candidates = day_library[day_library["date"] != target_date].copy()
    if n_raw > 0:
        candidates = _uniform_subsample(candidates, n_raw)
    if candidates.empty:
        return []

    n = len(time_index)
    base_dh = np.asarray(dispatch_input.series.get("district_heat_demand", np.zeros(n)), dtype=float).reshape(-1)
    base_space_heat = np.asarray(dispatch_input.series.get("district_space_heat_demand", base_dh), dtype=float).reshape(-1)
    base_hotwater = np.asarray(
        dispatch_input.series.get("district_hotwater_demand", np.clip(base_dh - base_space_heat, 0.0, None)),
        dtype=float,
    ).reshape(-1)
    if "ambient_temperature_c" not in dispatch_input.series:
        raise KeyError(
            "[dispatch.scenarios] Missing dispatch_input.series['ambient_temperature_c']; "
            "historical HDD scaling has no silent zero-temperature fallback."
        )
    base_temperature = require_ambient_temperature_c(
        dispatch_input.series["ambient_temperature_c"],
        ctx="base dispatch day",
    )
    base_price = np.asarray(dispatch_input.series.get("grid_import_price", np.zeros(n)), dtype=float).reshape(-1)
    base_export = np.asarray(dispatch_input.series.get("grid_export_price", np.zeros(n)), dtype=float).reshape(-1)
    base_gas_day_ahead_key = (
        "district_gas_day_ahead_price_eur_per_mwh_fuel"
        if "district_gas_day_ahead_price_eur_per_mwh_fuel" in dispatch_input.series
        else "district_gas_price_eur_per_mwh_fuel"
    )
    if base_gas_day_ahead_key not in dispatch_input.series:
        raise ValueError(
            "[dispatch.scenarios] Missing dispatch_input.series['district_gas_day_ahead_price_eur_per_mwh_fuel'] "
            "(or legacy alias 'district_gas_price_eur_per_mwh_fuel'); no silent gas-price fallback is allowed."
        )
    base_gas_day_ahead_price = np.asarray(
        dispatch_input.series[base_gas_day_ahead_key],
        dtype=float,
    ).reshape(-1)
    base_gas_balance_price = np.asarray(
        dispatch_input.series.get("district_gas_balance_price_eur_per_mwh_fuel", base_gas_day_ahead_price),
        dtype=float,
    ).reshape(-1)
    if "co2_price_eur_per_tco2" not in dispatch_input.series:
        raise ValueError(
            "[dispatch.scenarios] Missing dispatch_input.series['co2_price_eur_per_tco2']; "
            "the two-stage historical scenario builder requires an explicit CO2 price path."
        )
    base_co2_price = np.asarray(
        dispatch_input.series["co2_price_eur_per_tco2"],
        dtype=float,
    ).reshape(-1)

    scenarios: list[dict[str, Any]] = []
    for row in candidates.itertuples(index=False):
        scenario_temperature = _align_daily(
            row.temperature,
            n,
            fill_value=float(base_temperature[-1]) if base_temperature.size else 0.0,
        )
        scenario_price = _align_daily(
            np.asarray(row.price, dtype=float) / 1000.0,
            n,
            fill_value=float(base_price[-1]) if base_price.size else 0.0,
        )
        if hasattr(row, "gas_day_ahead_price") and pd.notna(getattr(row, "gas_day_ahead_price")):
            scenario_gas_day_ahead_price = _align_daily(
                np.asarray([float(getattr(row, "gas_day_ahead_price"))], dtype=float),
                n,
                fill_value=(
                    float(base_gas_day_ahead_price[-1])
                    if base_gas_day_ahead_price.size
                    else float(getattr(row, "gas_day_ahead_price"))
                ),
            )
        else:
            scenario_gas_day_ahead_price = _align_daily(
                base_gas_day_ahead_price,
                n,
                fill_value=float(base_gas_day_ahead_price[-1]) if base_gas_day_ahead_price.size else 0.0,
            )
        if hasattr(row, "gas_balance_price") and pd.notna(getattr(row, "gas_balance_price")):
            scenario_gas_balance_price = _align_daily(
                np.asarray([float(getattr(row, "gas_balance_price"))], dtype=float),
                n,
                fill_value=(
                    float(base_gas_balance_price[-1])
                    if base_gas_balance_price.size
                    else float(getattr(row, "gas_balance_price"))
                ),
            )
        else:
            scenario_gas_balance_price = _align_daily(
                base_gas_balance_price,
                n,
                fill_value=float(base_gas_balance_price[-1]) if base_gas_balance_price.size else 0.0,
            )
        if hasattr(row, "co2_price") and pd.notna(getattr(row, "co2_price")):
            scenario_co2_price = _align_daily(
                np.asarray([float(getattr(row, "co2_price"))], dtype=float),
                n,
                fill_value=(
                    float(base_co2_price[-1])
                    if base_co2_price.size
                    else float(getattr(row, "co2_price"))
                ),
            )
        else:
            scenario_co2_price = _align_daily(
                base_co2_price,
                n,
                fill_value=float(base_co2_price[-1]) if base_co2_price.size else 0.0,
            )
        base_hdd = heating_degree_hours(base_temperature, ctx="base dispatch day")
        scenario_hdd = heating_degree_hours(scenario_temperature, ctx="historical scenario day")
        dh_factor = np.clip(_safe_ratio(scenario_hdd, base_hdd, default=1.0), 0.1, 4.0)
        dh_factor[~np.isfinite(dh_factor)] = 1.0
        daily_avg_temp_c = float(np.mean(scenario_temperature))

        scenario_series: Dict[str, Any] = {
            "district_space_heat_demand": np.clip(base_space_heat * dh_factor, 0.0, None),
            "district_hotwater_demand": np.clip(base_hotwater, 0.0, None),
            "grid_import_price": scenario_price,
            "grid_export_price": base_export.copy(),
            "district_gas_price_eur_per_mwh_fuel": scenario_gas_day_ahead_price,
            "district_gas_day_ahead_price_eur_per_mwh_fuel": scenario_gas_day_ahead_price,
            "district_gas_balance_price_eur_per_mwh_fuel": scenario_gas_balance_price,
            "co2_price_eur_per_tco2": scenario_co2_price,
            "ambient_temperature_c": scenario_temperature,
        }
        scenario_series["district_heat_demand"] = scenario_series["district_space_heat_demand"] + scenario_series["district_hotwater_demand"]
        if "district_waste_incineration_available_th" in dispatch_input.series:
            scenario_series["district_waste_incineration_available_th"] = np.asarray(
                dispatch_input.series.get("district_waste_incineration_available_th", np.zeros(n)),
                dtype=float,
            ).reshape(-1)

        scenarios.append(
            {
                "label": str(pd.Timestamp(row.date).date()),
                "probability": 1.0,
                "series": scenario_series,
                "params": {
                    "historical_date": str(pd.Timestamp(row.date).date()),
                    "historical_price_source": str(getattr(row, "price_source", "mc_price")),
                    "historical_temperature_source": "weather_hourly",
                    "historical_daily_avg_temperature_c": daily_avg_temp_c,
                    "historical_heating_season_only": bool(heating_season_only),
                    "scenario_generation_mode": "historical_price_temperature_days",
                },
            }
        )
    return scenarios
