from __future__ import annotations

import json
import sys
from dataclasses import dataclass
from pathlib import Path

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[4]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from Data.profiles import location_openmeteo_weather_archives


WEATHER_CSV = Path(location_openmeteo_weather_archives["Vienna"]).resolve()
SUMMARY_CSV = WEATHER_CSV.with_name("openmeteo_year_summary_2016_2025.csv")
SELECTION_JSON = WEATHER_CSV.with_name("openmeteo_representative_years_2016_2025.json")

REPRESENTATIVE_METRIC_COLUMNS: tuple[str, ...] = (
    "annual_mean_temp_c",
    "annual_shortwave_kwh_m2",
    "hdd18",
    "winter_mean_temp_c",
    "winter_shortwave_kwh_m2",
    "winter_hdd18",
)


@dataclass(frozen=True)
class RepresentativeYearSelection:
    average_year: int
    cold_year: int
    mild_year: int


def _load_weather() -> pd.DataFrame:
    if not WEATHER_CSV.exists():
        raise FileNotFoundError(f"[openmeteo_year_select] Weather archive not found: {WEATHER_CSV}")
    df = pd.read_csv(WEATHER_CSV, parse_dates=["timestamp_utc"])
    required = {"timestamp_utc", "temperature_2m", "shortwave_radiation", "direct_normal_irradiance"}
    missing = sorted(required - set(df.columns))
    if missing:
        raise KeyError(f"[openmeteo_year_select] Weather archive missing required columns: {missing}")
    df["timestamp_utc"] = pd.to_datetime(df["timestamp_utc"], utc=True)
    if df["timestamp_utc"].duplicated().any():
        raise RuntimeError("[openmeteo_year_select] Duplicate timestamps in weather archive.")
    return df


def _build_year_summary(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    out["year"] = out["timestamp_utc"].dt.year
    out["month"] = out["timestamp_utc"].dt.month
    out["winter_year"] = out["year"]
    out.loc[out["month"] == 12, "winter_year"] = out.loc[out["month"] == 12, "year"] + 1
    out["hdh18"] = (18.0 - out["temperature_2m"]).clip(lower=0.0)

    annual = out.groupby("year", sort=True).agg(
        annual_mean_temp_c=("temperature_2m", "mean"),
        annual_shortwave_kwh_m2=("shortwave_radiation", lambda s: float(s.sum()) / 1000.0),
        annual_dni_kwh_m2=("direct_normal_irradiance", lambda s: float(s.sum()) / 1000.0),
        hdd18=("hdh18", lambda s: float(s.sum()) / 24.0),
    )
    winter = out[out["month"].isin([12, 1, 2])].groupby("winter_year", sort=True).agg(
        winter_mean_temp_c=("temperature_2m", "mean"),
        winter_shortwave_kwh_m2=("shortwave_radiation", lambda s: float(s.sum()) / 1000.0),
        winter_dni_kwh_m2=("direct_normal_irradiance", lambda s: float(s.sum()) / 1000.0),
        winter_hdd18=("hdh18", lambda s: float(s.sum()) / 24.0),
    )
    summary = annual.join(winter, how="left")
    if summary.index.has_duplicates:
        raise RuntimeError("[openmeteo_year_select] Duplicate years in summary table.")
    return summary


def _select_years(summary: pd.DataFrame) -> RepresentativeYearSelection:
    metric_table = summary.loc[:, list(REPRESENTATIVE_METRIC_COLUMNS)].dropna()
    if metric_table.empty:
        raise RuntimeError("[openmeteo_year_select] Representative metric table is empty.")
    std = metric_table.std(ddof=0)
    zero_std = std[std <= 0]
    if not zero_std.empty:
        raise RuntimeError(
            f"[openmeteo_year_select] Zero-variance representative metrics are not allowed: {list(zero_std.index)}"
        )
    z = (metric_table - metric_table.mean()) / std
    distances = (z.pow(2).sum(axis=1) ** 0.5).rename("representative_distance")
    summary.loc[distances.index, "representative_distance"] = distances

    if summary["hdd18"].isna().any():
        missing_years = summary.index[summary["hdd18"].isna()].tolist()
        raise RuntimeError(f"[openmeteo_year_select] Missing HDD18 values for years: {missing_years}")

    return RepresentativeYearSelection(
        average_year=int(distances.idxmin()),
        cold_year=int(summary["hdd18"].idxmax()),
        mild_year=int(summary["hdd18"].idxmin()),
    )


def main() -> None:
    df = _load_weather()
    summary = _build_year_summary(df)
    selection = _select_years(summary)

    summary_reset = summary.reset_index().rename(columns={"year": "calendar_year"})
    summary_reset.to_csv(SUMMARY_CSV, index=False)

    payload = {
        "source_weather_csv": str(WEATHER_CSV),
        "summary_csv": str(SUMMARY_CSV),
        "selection_method": {
            "average_year": {
                "type": "minimum_z_distance",
                "metric_columns": list(REPRESENTATIVE_METRIC_COLUMNS),
            },
            "cold_year": {"type": "max_hdd18"},
            "mild_year": {"type": "min_hdd18"},
        },
        "selected_years": {
            "average_year": int(selection.average_year),
            "cold_year": int(selection.cold_year),
            "mild_year": int(selection.mild_year),
        },
    }
    SELECTION_JSON.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    print(f"[openmeteo_year_select] wrote summary : {SUMMARY_CSV}")
    print(f"[openmeteo_year_select] wrote select  : {SELECTION_JSON}")
    print(
        "[openmeteo_year_select] years        : "
        f"average={selection.average_year}, cold={selection.cold_year}, mild={selection.mild_year}"
    )


if __name__ == "__main__":
    main()
