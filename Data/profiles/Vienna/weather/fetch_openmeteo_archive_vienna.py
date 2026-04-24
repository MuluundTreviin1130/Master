from __future__ import annotations

import argparse
import json
import sys
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterable

import openmeteo_requests
import pandas as pd
import requests_cache
from retry_requests import retry

PROJECT_ROOT = Path(__file__).resolve().parents[4]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from Data.district_heating.Vienna.solar_thermal_reference_site import (
    VIENNA_HOHE_WARTE_REFERENCE_SITE,
)
from Data.profiles import location_openmeteo_weather_archives


ARCHIVE_URL = "https://archive-api.open-meteo.com/v1/archive"
DEFAULT_START_DATE = "2016-01-01"
DEFAULT_END_DATE = "2025-12-31"
DEFAULT_TIMEZONE = "GMT"
DEFAULT_CACHE_DIR = (
    Path(location_openmeteo_weather_archives["Vienna"]).resolve().parent / ".cache" / "openmeteo"
)
DEFAULT_META_SUFFIX = ".meta.json"
RATE_LIMIT_SLEEP_S = 65.0
MAX_API_ATTEMPTS = 6

# Keep the request list explicit and stable. This is the weather SSOT for the
# offline-building-calibration path, not a hidden best-effort fetch.
HOURLY_VARIABLES: tuple[str, ...] = (
    "temperature_2m",
    "relative_humidity_2m",
    "dew_point_2m",
    "precipitation",
    "rain",
    "apparent_temperature",
    "snowfall",
    "snow_depth",
    "weather_code",
    "pressure_msl",
    "surface_pressure",
    "cloud_cover",
    "cloud_cover_low",
    "cloud_cover_mid",
    "cloud_cover_high",
    "et0_fao_evapotranspiration",
    "vapour_pressure_deficit",
    "wind_speed_100m",
    "wind_speed_10m",
    "wind_direction_10m",
    "wind_direction_100m",
    "wind_gusts_10m",
    "soil_temperature_0_to_7cm",
    "soil_temperature_7_to_28cm",
    "soil_temperature_28_to_100cm",
    "soil_temperature_100_to_255cm",
    "soil_moisture_0_to_7cm",
    "soil_moisture_7_to_28cm",
    "soil_moisture_28_to_100cm",
    "soil_moisture_100_to_255cm",
    "shortwave_radiation",
    "direct_radiation",
    "diffuse_radiation",
    "direct_normal_irradiance",
    "terrestrial_radiation",
    "shortwave_radiation_instant",
    "direct_radiation_instant",
    "diffuse_radiation_instant",
    "direct_normal_irradiance_instant",
    "terrestrial_radiation_instant",
)


@dataclass(frozen=True)
class FetchConfig:
    latitude: float
    longitude: float
    timezone: str
    start_date: str
    end_date: str
    output_csv: Path
    output_meta: Path
    cache_dir: Path
    chunk_dir: Path


def _parse_args() -> FetchConfig:
    parser = argparse.ArgumentParser(
        description=(
            "Fetch Vienna hourly Open-Meteo archive weather and store it in the repo data layer. "
            "Default period is the last 10 full calendar years: 2016-01-01 to 2025-12-31."
        )
    )
    parser.add_argument("--latitude", type=float, default=float(VIENNA_HOHE_WARTE_REFERENCE_SITE.latitude_deg))
    parser.add_argument("--longitude", type=float, default=float(VIENNA_HOHE_WARTE_REFERENCE_SITE.longitude_deg))
    parser.add_argument("--timezone", type=str, default=DEFAULT_TIMEZONE)
    parser.add_argument("--start-date", type=str, default=DEFAULT_START_DATE)
    parser.add_argument("--end-date", type=str, default=DEFAULT_END_DATE)
    parser.add_argument(
        "--output-csv",
        type=Path,
        default=Path(location_openmeteo_weather_archives["Vienna"]).resolve(),
    )
    parser.add_argument("--output-meta", type=Path, default=None)
    parser.add_argument("--cache-dir", type=Path, default=DEFAULT_CACHE_DIR)
    parser.add_argument("--chunk-dir", type=Path, default=None)
    args = parser.parse_args()

    output_csv = Path(args.output_csv).resolve()
    output_meta = Path(args.output_meta).resolve() if args.output_meta else output_csv.with_suffix(output_csv.suffix + DEFAULT_META_SUFFIX)
    chunk_dir = Path(args.chunk_dir).resolve() if args.chunk_dir else output_csv.parent / "_openmeteo_chunks"
    return FetchConfig(
        latitude=float(args.latitude),
        longitude=float(args.longitude),
        timezone=str(args.timezone),
        start_date=str(args.start_date),
        end_date=str(args.end_date),
        output_csv=output_csv,
        output_meta=output_meta,
        cache_dir=Path(args.cache_dir).resolve(),
        chunk_dir=chunk_dir,
    )


def _iter_calendar_year_chunks(start_date: str, end_date: str) -> Iterable[tuple[str, str]]:
    start = pd.Timestamp(start_date)
    end = pd.Timestamp(end_date)
    if start.tzinfo is not None or end.tzinfo is not None:
        raise ValueError("[openmeteo_vienna] start_date/end_date must be date strings without timezone.")
    if end < start:
        raise ValueError("[openmeteo_vienna] end_date must be on or after start_date.")

    cursor = start.normalize()
    while cursor <= end:
        year_end = min(pd.Timestamp(year=cursor.year, month=12, day=31), end)
        yield cursor.strftime("%Y-%m-%d"), year_end.strftime("%Y-%m-%d")
        cursor = year_end + pd.Timedelta(days=1)


def _build_client(cache_dir: Path) -> openmeteo_requests.Client:
    cache_dir.mkdir(parents=True, exist_ok=True)
    cache_path = cache_dir / "archive.sqlite"
    session = requests_cache.CachedSession(str(cache_path), expire_after=-1)
    retry_session = retry(session, retries=5, backoff_factor=0.2)
    return openmeteo_requests.Client(session=retry_session)


def _fetch_chunk(
    client: openmeteo_requests.Client,
    *,
    latitude: float,
    longitude: float,
    timezone: str,
    start_date: str,
    end_date: str,
) -> tuple[pd.DataFrame, dict[str, object]]:
    params = {
        "latitude": latitude,
        "longitude": longitude,
        "timezone": timezone,
        "start_date": start_date,
        "end_date": end_date,
        "hourly": list(HOURLY_VARIABLES),
    }
    responses = None
    for attempt in range(1, MAX_API_ATTEMPTS + 1):
        try:
            responses = client.weather_api(ARCHIVE_URL, params=params)
            break
        except Exception as exc:
            msg = str(exc).lower()
            if "request limit exceeded" not in msg or attempt == MAX_API_ATTEMPTS:
                raise
            print(
                "[openmeteo_vienna] rate limit hit for "
                f"{start_date}..{end_date}; sleeping {RATE_LIMIT_SLEEP_S:.0f}s before retry {attempt + 1}/{MAX_API_ATTEMPTS}."
            )
            time.sleep(RATE_LIMIT_SLEEP_S)
    if responses is None:
        raise RuntimeError(f"[openmeteo_vienna] No response returned for {start_date}..{end_date}.")
    if len(responses) != 1:
        raise RuntimeError(
            f"[openmeteo_vienna] Expected exactly one location response, got {len(responses)} for {start_date}..{end_date}."
        )
    response = responses[0]
    hourly = response.Hourly()
    n_vars = hourly.VariablesLength()
    if n_vars != len(HOURLY_VARIABLES):
        raise RuntimeError(
            "[openmeteo_vienna] Open-Meteo returned an unexpected number of hourly variables: "
            f"{n_vars} instead of {len(HOURLY_VARIABLES)}."
        )

    date_index = pd.date_range(
        start=pd.to_datetime(hourly.Time(), unit="s", utc=True),
        end=pd.to_datetime(hourly.TimeEnd(), unit="s", utc=True),
        freq=pd.Timedelta(seconds=hourly.Interval()),
        inclusive="left",
    )
    expected_rows = len(date_index)
    hourly_data: dict[str, object] = {"timestamp_utc": date_index}
    for idx, name in enumerate(HOURLY_VARIABLES):
        values = hourly.Variables(idx).ValuesAsNumpy()
        if len(values) != expected_rows:
            raise RuntimeError(
                f"[openmeteo_vienna] Variable '{name}' returned {len(values)} rows; expected {expected_rows}."
            )
        hourly_data[name] = values

    df = pd.DataFrame(hourly_data)
    if df["timestamp_utc"].duplicated().any():
        raise RuntimeError(f"[openmeteo_vienna] Duplicate timestamps detected in chunk {start_date}..{end_date}.")
    if df["timestamp_utc"].isna().any():
        raise RuntimeError(f"[openmeteo_vienna] NaT timestamps detected in chunk {start_date}..{end_date}.")
    if any(df[col].isna().any() for col in df.columns if col != "timestamp_utc"):
        missing = {col: int(df[col].isna().sum()) for col in df.columns if col != "timestamp_utc" and df[col].isna().any()}
        raise RuntimeError(
            f"[openmeteo_vienna] Missing hourly values returned by API for {start_date}..{end_date}: {missing}"
        )

    meta = {
        "requested_start_date": start_date,
        "requested_end_date": end_date,
        "latitude": float(response.Latitude()),
        "longitude": float(response.Longitude()),
        "elevation_m": float(response.Elevation()),
        "utc_offset_seconds": int(response.UtcOffsetSeconds()),
        "timezone": str(response.Timezone()),
        "timezone_abbreviation": str(response.TimezoneAbbreviation()),
    }
    return df, meta


def _expected_hours(start_date: str, end_date: str) -> int:
    start = pd.Timestamp(start_date)
    end = pd.Timestamp(end_date) + pd.Timedelta(days=1)
    return int((end - start) / pd.Timedelta(hours=1))


def _chunk_stem(start_date: str, end_date: str) -> str:
    return f"{start_date}_{end_date}"


def _chunk_paths(chunk_dir: Path, start_date: str, end_date: str) -> tuple[Path, Path]:
    stem = _chunk_stem(start_date, end_date)
    return chunk_dir / f"{stem}.csv", chunk_dir / f"{stem}.meta.json"


def _load_existing_chunk(csv_path: Path, *, start_date: str, end_date: str) -> pd.DataFrame:
    df = pd.read_csv(csv_path, parse_dates=["timestamp_utc"])
    if "timestamp_utc" not in df.columns:
        raise RuntimeError(f"[openmeteo_vienna] Existing chunk is missing 'timestamp_utc': {csv_path}")
    if df["timestamp_utc"].duplicated().any():
        raise RuntimeError(f"[openmeteo_vienna] Existing chunk contains duplicate timestamps: {csv_path}")
    expected_rows = _expected_hours(start_date, end_date)
    if len(df) != expected_rows:
        raise RuntimeError(
            f"[openmeteo_vienna] Existing chunk has wrong row count {len(df)} instead of {expected_rows}: {csv_path}"
        )
    first_ts = pd.Timestamp(start_date, tz="UTC")
    last_ts = pd.Timestamp(end_date, tz="UTC") + pd.Timedelta(hours=23)
    ts = pd.to_datetime(df["timestamp_utc"], utc=True)
    if ts.iloc[0] != first_ts or ts.iloc[-1] != last_ts:
        raise RuntimeError(
            "[openmeteo_vienna] Existing chunk has wrong timestamp coverage "
            f"{ts.iloc[0]} .. {ts.iloc[-1]} expected {first_ts} .. {last_ts}: {csv_path}"
        )
    return df


def main() -> None:
    cfg = _parse_args()
    cfg.output_csv.parent.mkdir(parents=True, exist_ok=True)
    cfg.output_meta.parent.mkdir(parents=True, exist_ok=True)
    cfg.chunk_dir.mkdir(parents=True, exist_ok=True)

    client = _build_client(cfg.cache_dir)
    chunks: list[pd.DataFrame] = []
    chunk_meta: list[dict[str, object]] = []
    for chunk_start, chunk_end in _iter_calendar_year_chunks(cfg.start_date, cfg.end_date):
        chunk_csv, chunk_meta_path = _chunk_paths(cfg.chunk_dir, chunk_start, chunk_end)
        if chunk_csv.exists():
            df_chunk = _load_existing_chunk(chunk_csv, start_date=chunk_start, end_date=chunk_end)
            if not chunk_meta_path.exists():
                raise RuntimeError(f"[openmeteo_vienna] Missing meta for existing chunk: {chunk_meta_path}")
            meta_chunk = json.loads(chunk_meta_path.read_text(encoding="utf-8"))
            print(f"[openmeteo_vienna] reusing chunk: {chunk_csv.name}")
        else:
            df_chunk, meta_chunk = _fetch_chunk(
                client,
                latitude=cfg.latitude,
                longitude=cfg.longitude,
                timezone=cfg.timezone,
                start_date=chunk_start,
                end_date=chunk_end,
            )
            df_chunk.to_csv(chunk_csv, index=False)
            chunk_meta_path.write_text(json.dumps(meta_chunk, indent=2), encoding="utf-8")
            print(f"[openmeteo_vienna] wrote chunk : {chunk_csv.name}")
        chunks.append(df_chunk)
        chunk_meta.append(meta_chunk)

    df = pd.concat(chunks, axis=0, ignore_index=True)
    if df["timestamp_utc"].duplicated().any():
        raise RuntimeError("[openmeteo_vienna] Duplicate timestamps detected after concatenation.")
    if len(df) != _expected_hours(cfg.start_date, cfg.end_date):
        raise RuntimeError(
            "[openmeteo_vienna] Unexpected row count after concatenation: "
            f"{len(df)} instead of {_expected_hours(cfg.start_date, cfg.end_date)}."
        )

    first_ts = pd.Timestamp(cfg.start_date, tz="UTC")
    last_ts = pd.Timestamp(cfg.end_date, tz="UTC") + pd.Timedelta(hours=23)
    if df["timestamp_utc"].iloc[0] != first_ts or df["timestamp_utc"].iloc[-1] != last_ts:
        raise RuntimeError(
            "[openmeteo_vienna] Timestamp coverage mismatch after concatenation: "
            f"{df['timestamp_utc'].iloc[0]} .. {df['timestamp_utc'].iloc[-1]} expected {first_ts} .. {last_ts}."
        )

    df.to_csv(cfg.output_csv, index=False)

    meta = {
        "source": "Open-Meteo archive API",
        "source_url": ARCHIVE_URL,
        "config": {
            **asdict(cfg),
            "output_csv": str(cfg.output_csv),
            "output_meta": str(cfg.output_meta),
            "cache_dir": str(cfg.cache_dir),
            "chunk_dir": str(cfg.chunk_dir),
        },
        "site_name": VIENNA_HOHE_WARTE_REFERENCE_SITE.name,
        "site_note": VIENNA_HOHE_WARTE_REFERENCE_SITE.note,
        "requested_hourly_variables": list(HOURLY_VARIABLES),
        "n_rows": int(len(df)),
        "timestamp_utc_min": str(df["timestamp_utc"].iloc[0]),
        "timestamp_utc_max": str(df["timestamp_utc"].iloc[-1]),
        "chunks": chunk_meta,
    }
    cfg.output_meta.write_text(json.dumps(meta, indent=2), encoding="utf-8")

    print(f"[openmeteo_vienna] wrote CSV : {cfg.output_csv}")
    print(f"[openmeteo_vienna] wrote meta: {cfg.output_meta}")
    print(f"[openmeteo_vienna] rows      : {len(df)}")
    print(f"[openmeteo_vienna] period    : {cfg.start_date} .. {cfg.end_date}")


if __name__ == "__main__":
    main()
