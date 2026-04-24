from __future__ import annotations

import csv
import json
import math
import sys
from dataclasses import asdict, dataclass
from pathlib import Path

import pandas as pd
import pvlib

PROJECT_ROOT = Path(__file__).resolve().parents[5]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from Settings.technical.building_calibration import make_building_calibration_config


SIGMA = 5.6697e-8
SUPPORTED_HORIZONTAL_IR_MODELS = {"clark_allen"}
SUPPORTED_OPAQUE_SKY_MODES = {"same_as_total"}
SUPPORTED_UNSUPPORTED_FIELD_POLICIES = {"epw_missing_codes"}
EPW_HEADER_ROWS = 8


@dataclass(frozen=True)
class TemplateInfo:
    header_rows: list[list[str]]
    data_source_uncertainty_flags: str


@dataclass(frozen=True)
class BuiltEpwArtifact:
    role: str
    year: int
    epw_path: Path
    meta_path: Path


def _load_template(template_path: Path) -> TemplateInfo:
    if not template_path.exists():
        raise FileNotFoundError(f"[pseudo_epw] Template EPW not found: {template_path}")
    with template_path.open("r", encoding="utf-8-sig", newline="") as fh:
        rows = list(csv.reader(fh))
    if len(rows) <= EPW_HEADER_ROWS:
        raise RuntimeError(f"[pseudo_epw] Template EPW is too short: {template_path}")
    header_rows = rows[:EPW_HEADER_ROWS]
    first_data = rows[EPW_HEADER_ROWS]
    if len(first_data) < 6:
        raise RuntimeError(f"[pseudo_epw] Template EPW first data row is malformed: {template_path}")
    flags = str(first_data[5]).strip()
    if not flags:
        raise RuntimeError(f"[pseudo_epw] Template EPW does not expose data-source flags: {template_path}")
    return TemplateInfo(header_rows=header_rows, data_source_uncertainty_flags=flags)


def _load_weather(weather_csv: Path) -> pd.DataFrame:
    if not weather_csv.exists():
        raise FileNotFoundError(f"[pseudo_epw] Weather archive not found: {weather_csv}")
    df = pd.read_csv(weather_csv, parse_dates=["timestamp_utc"])
    required = {
        "timestamp_utc",
        "temperature_2m",
        "relative_humidity_2m",
        "dew_point_2m",
        "surface_pressure",
        "cloud_cover",
        "wind_speed_10m",
        "wind_direction_10m",
        "precipitation",
        "snowfall",
        "snow_depth",
        "shortwave_radiation",
        "diffuse_radiation",
        "direct_normal_irradiance",
    }
    missing = sorted(required - set(df.columns))
    if missing:
        raise KeyError(f"[pseudo_epw] Weather archive missing required columns: {missing}")
    df["timestamp_utc"] = pd.to_datetime(df["timestamp_utc"], utc=True)
    if df["timestamp_utc"].duplicated().any():
        raise RuntimeError("[pseudo_epw] Weather archive contains duplicate timestamps.")
    return df.set_index("timestamp_utc").sort_index()


def _load_selection(selection_json: Path, roles: tuple[str, ...]) -> dict[str, int]:
    if not selection_json.exists():
        raise FileNotFoundError(f"[pseudo_epw] Representative-years JSON not found: {selection_json}")
    payload = json.loads(selection_json.read_text(encoding="utf-8"))
    selected = payload.get("selected_years")
    if not isinstance(selected, dict):
        raise RuntimeError(f"[pseudo_epw] Invalid representative-years JSON: {selection_json}")
    out: dict[str, int] = {}
    for role in roles:
        if role not in selected:
            raise KeyError(f"[pseudo_epw] Representative-years JSON missing role '{role}'.")
        out[role] = int(selected[role])
    return out


def _missing_codes() -> dict[str, object]:
    return {
        "horizontal_ir": 9999,
        "global_illuminance": 999999,
        "direct_normal_illuminance": 999999,
        "diffuse_horizontal_illuminance": 999999,
        "zenith_luminance": 9999,
        "visibility_km": 9999,
        "ceiling_height_m": 99999,
        "present_weather_observation": 9,
        "present_weather_codes": 999999999,
        "precipitable_water_mm": 999,
        "aerosol_optical_depth": 0.999,
        "snow_depth_cm": 999,
        "days_since_last_snow": 99,
        "albedo": 999,
    }


def _clark_allen_horizontal_ir_w_m2(dry_bulb_c: pd.Series, dew_point_c: pd.Series, sky_cover_tenths: pd.Series) -> pd.Series:
    t_dry_k = dry_bulb_c.astype(float) + 273.15
    t_dew_k = dew_point_c.astype(float) + 273.15
    n = sky_cover_tenths.astype(float).clip(lower=0.0, upper=10.0)
    emissivity_clear = 0.787 + 0.764 * pd.Series([math.log(max(v / 273.15, 1e-6)) for v in t_dew_k], index=t_dew_k.index)
    emissivity = emissivity_clear * (1.0 + 0.0224 * n - 0.0035 * (n**2) + 0.00028 * (n**3))
    emissivity = emissivity.clip(lower=0.0, upper=1.2)
    return emissivity * SIGMA * (t_dry_k**4)


def _days_since_last_snow(snowfall_cm: pd.Series) -> pd.Series:
    event = snowfall_cm.fillna(0.0).astype(float) > 0.0
    dates = snowfall_cm.index.normalize()
    last_event_date = None
    out: list[int] = []
    for current_date, is_event in zip(dates, event):
        if is_event:
            last_event_date = current_date
            out.append(0)
        elif last_event_date is None:
            out.append(_missing_codes()["days_since_last_snow"])
        else:
            out.append(int((current_date - last_event_date).days))
    return pd.Series(out, index=snowfall_cm.index, dtype=int)


def _build_local_year_frame(
    weather_utc: pd.DataFrame,
    *,
    year: int,
    utc_offset_hours: int,
) -> pd.DataFrame:
    local_index = pd.date_range(f"{year}-01-01 00:00", f"{year}-12-31 23:00", freq="h")
    utc_index = local_index.tz_localize("UTC") - pd.Timedelta(hours=utc_offset_hours)
    frame = weather_utc.reindex(utc_index)
    if frame.isna().any().any():
        missing = {col: int(frame[col].isna().sum()) for col in frame.columns if frame[col].isna().any()}
        raise RuntimeError(f"[pseudo_epw] Missing weather values for local year {year}: {missing}")
    frame = frame.copy()
    frame["timestamp_local_standard"] = local_index
    return frame


def _build_header_rows(template: TemplateInfo, *, role: str, year: int, weather_csv: Path, cfg: object) -> list[list[str]]:
    rows = [list(r) for r in template.header_rows]
    rows[5] = [
        "COMMENTS 1",
        (
            f"Pseudo EPW built from Open-Meteo archive for Vienna local-standard year {year}; "
            f"role={role}."
        ),
    ]
    rows[6] = [
        "COMMENTS 2",
        (
            f"Source weather={weather_csv.name}; "
            f"horizontal_ir_model={getattr(cfg, 'horizontal_ir_model')}; "
            f"opaque_sky_mode={getattr(cfg, 'total_to_opaque_sky_cover_mode')}; "
            f"unsupported_fields_policy={getattr(cfg, 'unsupported_fields_policy')}."
        ),
    ]
    weekday = pd.Timestamp(year=year, month=1, day=1).strftime("%A")
    rows[7] = ["DATA PERIODS", "1", "1", "Data", weekday, "1/ 1", "12/31"]
    return rows


def _build_hourly_rows(
    frame: pd.DataFrame,
    *,
    template: TemplateInfo,
    latitude_deg: float,
    longitude_deg: float,
    horizontal_ir_model: str,
    total_to_opaque_sky_cover_mode: str,
    unsupported_fields_policy: str,
) -> list[list[object]]:
    if horizontal_ir_model not in SUPPORTED_HORIZONTAL_IR_MODELS:
        raise ValueError(f"[pseudo_epw] Unsupported horizontal_ir_model='{horizontal_ir_model}'.")
    if total_to_opaque_sky_cover_mode not in SUPPORTED_OPAQUE_SKY_MODES:
        raise ValueError(f"[pseudo_epw] Unsupported opaque sky cover mode='{total_to_opaque_sky_cover_mode}'.")
    if unsupported_fields_policy not in SUPPORTED_UNSUPPORTED_FIELD_POLICIES:
        raise ValueError(f"[pseudo_epw] Unsupported unsupported_fields_policy='{unsupported_fields_policy}'.")

    idx_utc = pd.DatetimeIndex(frame.index)
    solar_pos = pvlib.solarposition.get_solarposition(idx_utc, latitude=float(latitude_deg), longitude=float(longitude_deg))
    dni_extra = pd.Series(pvlib.irradiance.get_extra_radiation(idx_utc), index=frame.index)
    cos_zenith = pd.Series(
        (pvlib.tools.cosd(solar_pos["zenith"]).clip(lower=0.0)).to_numpy(),
        index=frame.index,
    )
    ext_horizontal = (dni_extra * cos_zenith).clip(lower=0.0)

    total_sky_tenths = (frame["cloud_cover"].astype(float) / 10.0).round().clip(lower=0, upper=10).astype(int)
    if total_to_opaque_sky_cover_mode == "same_as_total":
        opaque_sky_tenths = total_sky_tenths
    else:
        raise ValueError(
            f"[pseudo_epw] Unsupported opaque sky cover mode '{total_to_opaque_sky_cover_mode}'."
        )

    horizontal_ir = _clark_allen_horizontal_ir_w_m2(
        frame["temperature_2m"], frame["dew_point_2m"], total_sky_tenths
    ).round().clip(lower=0.0)

    missing = _missing_codes()
    days_since_last_snow = _days_since_last_snow(frame["snowfall"])
    rows: list[list[object]] = []
    for ts, row in frame.iterrows():
        local_ts = pd.Timestamp(row["timestamp_local_standard"])
        precip_depth = max(float(row["precipitation"]), 0.0)
        snow_depth_cm = max(float(row["snow_depth"]) * 100.0, 0.0)
        out = [
            int(local_ts.year),
            int(local_ts.month),
            int(local_ts.day),
            int(local_ts.hour) + 1,
            0,
            template.data_source_uncertainty_flags,
            round(float(row["temperature_2m"]), 1),
            round(float(row["dew_point_2m"]), 1),
            int(round(float(row["relative_humidity_2m"]))),
            int(round(float(row["surface_pressure"]) * 100.0)),
            int(round(float(ext_horizontal.loc[ts]))),
            int(round(float(dni_extra.loc[ts]))),
            int(round(float(horizontal_ir.loc[ts]))),
            int(round(max(float(row["shortwave_radiation"]), 0.0))),
            int(round(max(float(row["direct_normal_irradiance"]), 0.0))),
            int(round(max(float(row["diffuse_radiation"]), 0.0))),
            missing["global_illuminance"],
            missing["direct_normal_illuminance"],
            missing["diffuse_horizontal_illuminance"],
            missing["zenith_luminance"],
            int(round(float(row["wind_direction_10m"]))),
            round(max(float(row["wind_speed_10m"]) / 3.6, 0.0), 1),
            int(total_sky_tenths.loc[ts]),
            int(opaque_sky_tenths.loc[ts]),
            missing["visibility_km"],
            missing["ceiling_height_m"],
            missing["present_weather_observation"],
            missing["present_weather_codes"],
            missing["precipitable_water_mm"],
            missing["aerosol_optical_depth"],
            int(round(snow_depth_cm)) if snow_depth_cm >= 0 else missing["snow_depth_cm"],
            int(days_since_last_snow.loc[ts]),
            missing["albedo"],
            round(precip_depth, 1),
            1 if precip_depth > 0.0 else 0,
        ]
        rows.append(out)
    return rows


def build_selected_vienna_pseudo_epws() -> list[BuiltEpwArtifact]:
    cfg = make_building_calibration_config()
    template_path = Path(cfg.pseudo_epw_template_path).resolve()
    weather_csv = Path(cfg.pseudo_epw_weather_csv).resolve()
    selection_json = Path(cfg.pseudo_epw_representative_years_json).resolve()
    output_dir = Path(cfg.pseudo_epw_output_dir).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    template = _load_template(template_path)
    weather_utc = _load_weather(weather_csv)
    selected = _load_selection(selection_json, cfg.pseudo_epw_year_roles)
    selected = {
        **selected,
        **{str(role): int(year) for role, year in dict(cfg.pseudo_epw_extra_year_roles).items()},
    }

    location_row = template.header_rows[0]
    latitude_deg = float(location_row[6])
    longitude_deg = float(location_row[7])
    built: list[BuiltEpwArtifact] = []
    ordered_roles = [str(role) for role in cfg.pseudo_epw_year_roles] + [
        str(role) for role in dict(cfg.pseudo_epw_extra_year_roles).keys()
    ]
    for role in ordered_roles:
        year = selected[role]
        frame = _build_local_year_frame(
            weather_utc,
            year=year,
            utc_offset_hours=int(cfg.local_standard_utc_offset_hours),
        )
        header_rows = _build_header_rows(
            template,
            role=role,
            year=year,
            weather_csv=weather_csv,
            cfg=cfg,
        )
        hourly_rows = _build_hourly_rows(
            frame,
            template=template,
            latitude_deg=latitude_deg,
            longitude_deg=longitude_deg,
            horizontal_ir_model=cfg.horizontal_ir_model,
            total_to_opaque_sky_cover_mode=cfg.total_to_opaque_sky_cover_mode,
            unsupported_fields_policy=cfg.unsupported_fields_policy,
        )

        epw_path = output_dir / f"vienna_openmeteo_{role}_{year}.epw"
        meta_path = epw_path.with_suffix(epw_path.suffix + ".meta.json")
        with epw_path.open("w", encoding="utf-8", newline="") as fh:
            writer = csv.writer(fh)
            writer.writerows(header_rows)
            writer.writerows(hourly_rows)

        meta = {
            "role": role,
            "year": int(year),
            "epw_path": str(epw_path),
            "template_epw_path": str(template_path),
            "source_weather_csv": str(weather_csv),
            "source_selection_json": str(selection_json),
            "config": asdict(cfg),
            "assumptions": {
                "local_standard_time": f"UTC+{cfg.local_standard_utc_offset_hours} without DST",
                "horizontal_ir_model": cfg.horizontal_ir_model,
                "opaque_sky_cover_mode": cfg.total_to_opaque_sky_cover_mode,
                "unsupported_fields_policy": cfg.unsupported_fields_policy,
                "present_weather_codes": "left as EPW missing code",
                "illuminance_fields": "left as EPW missing codes",
                "precipitable_water": "left as EPW missing code",
                "aerosol_optical_depth": "left as EPW missing code",
            },
        }
        meta_path.write_text(json.dumps(meta, indent=2), encoding="utf-8")
        built.append(BuiltEpwArtifact(role=role, year=year, epw_path=epw_path, meta_path=meta_path))
    return built


def main() -> None:
    built = build_selected_vienna_pseudo_epws()
    for artifact in built:
        print(
            "[pseudo_epw] wrote "
            f"{artifact.role} year {artifact.year}: {artifact.epw_path}"
        )


if __name__ == "__main__":
    main()
