from __future__ import annotations

import json
import math
import os
import shutil
import sqlite3
import subprocess
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg", force=True)
import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[5]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from Settings.technical.building_calibration import make_building_calibration_config
from Settings.technical.district_heating import make_district_heating
from Technical_model.technologies.buildings.calibration.teachers.base import (
    TeacherExperimentResult,
    TeacherSmokeResult,
)


_OPTIONAL_AIR_PATH_OUTPUT_VARIABLES = (
    "Zone Infiltration Sensible Heat Loss Energy",
    "Zone Infiltration Sensible Heat Gain Energy",
    "Zone Ventilation Sensible Heat Loss Energy",
    "Zone Ventilation Sensible Heat Gain Energy",
)

_OPTIONAL_IDEAL_LOADS_OUTDOOR_AIR_OUTPUT_VARIABLES = (
    "Zone Ideal Loads Outdoor Air Sensible Heating Rate",
    "Zone Ideal Loads Outdoor Air Sensible Cooling Rate",
)

_DEBUG_AIR_PATH_OUTPUT_VARIABLES = (
    "Zone Infiltration Standard Density Volume Flow Rate",
    "Zone Infiltration Standard Density Air Change Rate",
    "Zone Ventilation Standard Density Volume Flow Rate",
    "Zone Ventilation Standard Density Air Change Rate",
    "Zone Ventilation Air Inlet Temperature",
    "Zone Air Heat Balance Outdoor Air Transfer Rate",
    "Zone Outdoor Air Drybulb Temperature",
    "Zone Predicted Sensible Load to Heating Setpoint Heat Transfer Rate",
    "Zone System Predicted Sensible Load to Heating Setpoint Heat Transfer Rate",
    "Zone Ideal Loads Outdoor Air Standard Density Volume Flow Rate",
    "Zone Ideal Loads Outdoor Air Mass Flow Rate",
)


def _discover_energyplus(explicit_path: str) -> Path:
    if explicit_path:
        candidate = Path(explicit_path).resolve()
        if not candidate.exists():
            raise FileNotFoundError(f"[energyplus_teacher] Configured energyplus executable not found: {candidate}")
        return candidate

    which = shutil.which("energyplus")
    if which:
        return Path(which).resolve()

    roots = [Path(r"C:\Program Files"), Path(r"C:\Program Files (x86)")]
    matches: list[Path] = []
    for root in roots:
        if not root.exists():
            continue
        for sub in root.glob("EnergyPlus*"):
            exe = sub / "energyplus.exe"
            if exe.exists():
                matches.append(exe.resolve())
    if matches:
        matches.sort(reverse=True)
        return matches[0]

    raise FileNotFoundError(
        "[energyplus_teacher] EnergyPlus executable not found. "
        "Set Settings.technical.building_calibration.energyplus_executable_path explicitly."
    )


def _load_pseudo_epw(role: str) -> Path:
    cfg = make_building_calibration_config()
    epw_dir = Path(cfg.pseudo_epw_output_dir).resolve()
    candidates = sorted(epw_dir.glob(f"vienna_openmeteo_{role}_*.epw"))
    if not candidates:
        raise FileNotFoundError(
            f"[energyplus_teacher] No pseudo EPW found for role '{role}' in {epw_dir}. Build pseudo EPWs first."
        )
    if len(candidates) > 1:
        raise RuntimeError(
            f"[energyplus_teacher] Expected exactly one pseudo EPW for role '{role}', found {len(candidates)}."
        )
    return candidates[0]


def _load_json(path_str: str, *, label: str) -> dict:
    path = Path(path_str).resolve()
    if not path.exists():
        raise FileNotFoundError(f"[energyplus_teacher] Missing {label}: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def _resolve_teacher_context(*, cohort_id: str, experiment_id: str) -> tuple[dict, dict]:
    cfg = make_building_calibration_config()
    teacher_bundle = _load_json(cfg.teacher_input_output_json, label="teacher_input_output_json")
    experiment_library = _load_json(cfg.experiment_library_output_json, label="experiment_library_output_json")
    cohorts = {str(item["cohort_id"]): dict(item) for item in teacher_bundle.get("cohorts", [])}
    experiments = {str(item["experiment_id"]): dict(item) for item in experiment_library.get("experiments", [])}
    if cohort_id not in cohorts:
        raise KeyError(f"[energyplus_teacher] Unknown cohort_id='{cohort_id}' in teacher bundle.")
    if experiment_id not in experiments:
        raise KeyError(f"[energyplus_teacher] Unknown experiment_id='{experiment_id}' in experiment library.")
    return cohorts[cohort_id], experiments[experiment_id]


def _load_usage_profile() -> pd.DataFrame:
    cfg = make_building_calibration_config()
    path = Path(cfg.usage_profile_excel_path).resolve()
    if not path.exists():
        raise FileNotFoundError(f"[energyplus_teacher] Missing usage-profile workbook: {path}")
    df = pd.read_excel(path, sheet_name=cfg.usage_profile_sheet_name)
    required = list(cfg.required_usage_profile_columns)
    missing = [col for col in required if col not in df.columns]
    if missing:
        raise KeyError(f"[energyplus_teacher] Usage-profile workbook is missing required columns: {missing}")
    df = df.copy()
    df["H"] = pd.to_numeric(df["H"], errors="coerce")
    if df["H"].isna().any():
        raise ValueError("[energyplus_teacher] Usage-profile column 'H' contains non-numeric values.")
    df["H"] = df["H"].astype(int)
    df = df.sort_values("H")
    if str(cfg.usage_profile_timebase) == "annual_8760":
        if tuple(df["H"].tolist()) != tuple(range(1, 8761)):
            raise ValueError(
                "[energyplus_teacher] For usage_profile_timebase='annual_8760' the sheet must contain exactly "
                "hours 1..8760."
            )
        return df.reset_index(drop=True)
    if tuple(df["H"].tolist()) != tuple(range(1, 25)):
        raise ValueError(
            "[energyplus_teacher] For non-annual usage profiles the sheet must contain exactly hours 1..24."
        )
    return df.reset_index(drop=True)


def _build_full_year_schedule_frame(*, calendar_year: int, cohort: dict, experiment: dict) -> pd.DataFrame:
    cfg = make_building_calibration_config()
    idx = pd.date_range(
        start=pd.Timestamp(year=calendar_year, month=1, day=1, hour=0),
        end=pd.Timestamp(year=calendar_year, month=12, day=31, hour=23),
        freq="h",
    )
    usage_df = _load_usage_profile()
    if str(cfg.usage_profile_timebase) == "annual_8760":
        base_idx = pd.date_range(
            start=pd.Timestamp(year=2019, month=1, day=1, hour=0),
            end=pd.Timestamp(year=2019, month=12, day=31, hour=23),
            freq="h",
        )
        if len(usage_df) != len(base_idx):
            raise ValueError(
                "[energyplus_teacher] annual_8760 usage profile length does not match the expected normal-year index."
            )
        usage_annual = usage_df.copy()
        usage_annual.index = base_idx
        mapped_index = []
        for ts in idx:
            if ts.month == 2 and ts.day == 29:
                mapped_index.append(pd.Timestamp(year=2019, month=2, day=28, hour=ts.hour))
            else:
                mapped_index.append(ts.replace(year=2019))
        mapped = usage_annual.reindex(pd.DatetimeIndex(mapped_index))
        if calendar_year % 4 == 0 and str(cfg.usage_profile_leap_day_policy) == "repeat_feb28":
            leap_mask = (idx.month == 2) & (idx.day == 29)
            if leap_mask.any():
                feb28_source = usage_annual.loc["2019-02-28 00:00:00":"2019-02-28 23:00:00"]
                if len(feb28_source) != 24:
                    raise ValueError("[energyplus_teacher] Could not resolve Feb-28 source profile for leap-day expansion.")
                mapped.loc[leap_mask, :] = feb28_source.to_numpy()
        elif calendar_year % 4 == 0:
            raise ValueError(
                f"[energyplus_teacher] Unsupported usage_profile_leap_day_policy='{cfg.usage_profile_leap_day_policy}'."
            )
        winter_mask = idx.month.isin([10, 11, 12, 1, 2, 3, 4])
        internal_gains_w_m2 = pd.Series(
            mapped["Qi Sommer W/m2"].to_numpy(dtype=float),
            index=idx,
            dtype=float,
        )
        internal_gains_w_m2.loc[winter_mask] = mapped.loc[winter_mask, "Qi Winter W/m2"].to_numpy(dtype=float)
        internal_gains_w_m2 = internal_gains_w_m2.to_numpy(dtype=float)
        infiltration_ach = mapped["Luftwechsel_Infiltration_1_h"].to_numpy(dtype=float)
        ventilation_ach = mapped["Luftwechsel_Anlage_1_h"].to_numpy(dtype=float)
    else:
        usage_by_hour = usage_df.set_index("H")
        hours = idx.hour + 1
        months = idx.month
        winter_mask = months.isin([10, 11, 12, 1, 2, 3, 4])
        internal_gains_w_m2 = []
        infiltration_ach = []
        ventilation_ach = []
        for hour_value, is_winter in zip(hours, winter_mask):
            row = usage_by_hour.loc[int(hour_value)]
            internal_gains_w_m2.append(float(row["Qi Winter W/m2"] if is_winter else row["Qi Sommer W/m2"]))
            infiltration_ach.append(float(row["Luftwechsel_Infiltration_1_h"]))
            ventilation_ach.append(float(row["Luftwechsel_Anlage_1_h"]))

    heating_setpoint_c = pd.Series(float(cohort["t_min_k"]) - 273.15, index=idx, dtype=float)
    cooling_setpoint_c = pd.Series(float(cohort["t_max_k"]) - 273.15, index=idx, dtype=float)
    if (cooling_setpoint_c <= heating_setpoint_c).any():
        raise ValueError(
            f"[energyplus_teacher] Invalid setpoint band for cohort='{cohort['cohort_id']}'. "
            "Cooling setpoint must stay above heating setpoint."
        )

    start_local = pd.Timestamp(str(experiment["start_local"]))
    if int(start_local.hour) != 0:
        raise ValueError(
            f"[energyplus_teacher] Experiment '{experiment['experiment_id']}' must currently start at 00:00 local time."
        )
    event_type = str(experiment["event_type"])
    if event_type != "none":
        event_start = start_local + pd.Timedelta(hours=int(experiment["event_start_offset_h"]))
        event_end = event_start + pd.Timedelta(hours=int(experiment["event_duration_h"]))
        event_mask = (idx >= event_start) & (idx < event_end)
        heating_setpoint_c.loc[event_mask] = heating_setpoint_c.loc[event_mask] + float(
            experiment["event_setpoint_delta_k"]
        )
        if (cooling_setpoint_c.loc[event_mask] <= heating_setpoint_c.loc[event_mask]).any():
            raise ValueError(
                f"[energyplus_teacher] Event '{experiment['experiment_id']}' collapses the setpoint band."
            )

    return pd.DataFrame(
        {
            "timestamp_local": idx,
            "heating_setpoint_c": heating_setpoint_c.to_numpy(dtype=float),
            "cooling_setpoint_c": cooling_setpoint_c.to_numpy(dtype=float),
            "internal_gains_w_m2": pd.Series(internal_gains_w_m2, index=idx, dtype=float).to_numpy(dtype=float),
            "infiltration_ach": pd.Series(infiltration_ach, index=idx, dtype=float).to_numpy(dtype=float),
            "ventilation_ach": pd.Series(ventilation_ach, index=idx, dtype=float).to_numpy(dtype=float),
        }
    )


def _resolve_reference_scale(cohort: dict) -> dict[str, float]:
    cfg = make_building_calibration_config()
    represented_gfa = float(cohort["represented_gfa_m2"])
    if represented_gfa <= 0.0:
        raise ValueError(f"[energyplus_teacher] represented_gfa_m2 must be > 0 for cohort='{cohort['cohort_id']}'.")
    reference_gfa = float(cfg.teacher_reference_gfa_m2)
    if reference_gfa <= 0.0:
        raise ValueError("[energyplus_teacher] teacher_reference_gfa_m2 must be > 0.")
    scale = reference_gfa / represented_gfa
    if scale <= 0.0:
        raise ValueError("[energyplus_teacher] Derived teacher reference scale must be > 0.")
    return {
        "reference_gfa_m2": reference_gfa,
        "scale": scale,
        "conditioned_floor_m2": float(cohort["conditioned_floor_m2"]) * scale,
        "roof_area_m2": float(cohort["roof_area_m2"]) * scale,
        "wall_area_m2": float(cohort["wall_area_m2"]) * scale,
        "window_area_total_m2": float(cohort["window_area_total_m2"]) * scale,
        "floor_exposed_area_m2": float(cohort["floor_exposed_area_m2"]) * scale,
        "volume_m3": float(cohort["represented_volume_m3"]) * scale,
        "heat_capacity_wh_per_k": float(cohort["heat_capacity_wh_per_k"]) * scale,
    }


def _build_equivalent_geometry(cohort: dict) -> dict[str, float]:
    scaled = _resolve_reference_scale(cohort)
    footprint_area = float(scaled["roof_area_m2"])
    if footprint_area <= 0.0:
        raise ValueError(f"[energyplus_teacher] roof_area_m2 must be > 0 for cohort='{cohort['cohort_id']}'.")
    side = math.sqrt(footprint_area)
    if side <= 0.0:
        raise ValueError("[energyplus_teacher] Derived footprint side must be > 0.")
    total_height = float(scaled["volume_m3"]) / footprint_area
    if total_height <= 0.0:
        raise ValueError("[energyplus_teacher] Derived building height must be > 0.")
    simple_wall_area = 4.0 * side * total_height
    if simple_wall_area <= 0.0:
        raise ValueError("[energyplus_teacher] Derived exposed wall area must be > 0.")

    window_per_facade = float(scaled["window_area_total_m2"]) / 4.0
    max_window_area_per_facade = 0.8 * side * 0.8 * total_height
    if window_per_facade > max_window_area_per_facade + 1e-9:
        raise ValueError(
            f"[energyplus_teacher] Window area for cohort='{cohort['cohort_id']}' does not fit the simplified facade."
        )
    target_height = min(0.6 * total_height, max(0.5, window_per_facade / max(0.8 * side, 1e-9)))
    target_height = min(target_height, 0.8 * total_height)
    window_length = window_per_facade / max(target_height, 1e-9)
    if window_length > 0.8 * side + 1e-9:
        raise ValueError(
            f"[energyplus_teacher] Window width for cohort='{cohort['cohort_id']}' does not fit the simplified facade."
        )

    roof_u_eff = (float(cohort["u_roof"]) * float(scaled["roof_area_m2"])) / footprint_area
    wall_u_eff = (float(cohort["u_wall"]) * float(scaled["wall_area_m2"])) / simple_wall_area
    floor_u_eff = (float(cohort["u_floor"]) * float(scaled["floor_exposed_area_m2"])) / footprint_area
    if min(roof_u_eff, wall_u_eff, floor_u_eff) <= 0.0:
        raise ValueError(f"[energyplus_teacher] Effective U-values must be > 0 for cohort='{cohort['cohort_id']}'.")

    air_capacity_wh_per_k = 0.34 * float(scaled["volume_m3"])
    extra_capacity_wh_per_k = max(0.0, float(scaled["heat_capacity_wh_per_k"]) - air_capacity_wh_per_k)

    return {
        **scaled,
        "footprint_side_m": side,
        "footprint_area_m2": footprint_area,
        "total_height_m": total_height,
        "simple_wall_area_m2": simple_wall_area,
        "window_height_m": target_height,
        "window_length_m": window_length,
        "roof_u_eff": roof_u_eff,
        "wall_u_eff": wall_u_eff,
        "floor_u_eff": floor_u_eff,
        "air_capacity_wh_per_k": air_capacity_wh_per_k,
        "extra_capacity_wh_per_k": extra_capacity_wh_per_k,
    }


def _write_schedule_csv(workdir: Path, *, schedule_df: pd.DataFrame) -> Path:
    out = workdir / "teacher_schedules.csv"
    export = schedule_df.copy()
    required_columns = (
        "internal_gains_w_m2",
        "infiltration_ach",
        "ventilation_ach",
    )
    missing = [col for col in required_columns if col not in export.columns]
    if missing:
        raise KeyError(f"[energyplus_teacher] Schedule dataframe is missing required columns: {missing}")

    for absolute_col, fraction_col in (
        ("internal_gains_w_m2", "internal_gains_fraction"),
        ("infiltration_ach", "infiltration_fraction"),
        ("ventilation_ach", "ventilation_fraction"),
    ):
        peak = float(pd.to_numeric(export[absolute_col], errors="coerce").max())
        if peak < 0.0:
            raise ValueError(
                f"[energyplus_teacher] Peak for '{absolute_col}' must be >= 0, got {peak}."
            )
        if peak == 0.0:
            export[fraction_col] = 0.0
            continue
        export[fraction_col] = pd.to_numeric(export[absolute_col], errors="coerce") / peak
        if export[fraction_col].isna().any():
            raise ValueError(
                f"[energyplus_teacher] Could not derive normalized schedule '{fraction_col}' from '{absolute_col}'."
            )
        if (export[fraction_col] < -1e-9).any() or (export[fraction_col] > 1.0 + 1e-9).any():
            raise ValueError(
                f"[energyplus_teacher] Normalized schedule '{fraction_col}' must stay within [0, 1]."
            )

    export["timestamp_local"] = export["timestamp_local"].dt.strftime("%Y-%m-%d %H:%M:%S")
    export.to_csv(out, index=False, encoding="utf-8")
    return out


def _schedule_file_block(name: str, schedule_type: str, csv_path: Path, column_number: int, rows: int) -> str:
    return f"""Schedule:File,
  {name},
  {schedule_type},
  {csv_path.name},
  {column_number},
  1,
  {rows},
  Comma,
  No,
  60,
  No;
"""


def _build_teacher_idf(
    *,
    idf_path: Path,
    cohort: dict,
    experiment: dict,
    geometry: dict[str, float],
    schedule_csv_path: Path,
    year_rows: int,
    version: str,
) -> None:
    cfg = make_building_calibration_config()
    calendar_year = int(experiment["calendar_year"])
    start_local = pd.Timestamp(str(experiment["start_local"]))
    end_exclusive = pd.Timestamp(str(experiment["end_local"]))
    if int(start_local.hour) != 0 or int(end_exclusive.hour) != 0:
        raise ValueError(
            f"[energyplus_teacher] Experiment '{experiment['experiment_id']}' currently requires day-aligned start/end."
        )
    last_simulated = end_exclusive - pd.Timedelta(hours=1)
    start_weekday = start_local.strftime("%A")
    control_mode = str(experiment["control_mode"])

    side = float(geometry["footprint_side_m"])
    height = float(geometry["total_height_m"])
    z_win_1 = (height - float(geometry["window_height_m"])) / 2.0
    z_win_2 = z_win_1 + float(geometry["window_height_m"])
    x_win_1 = (side - float(geometry["window_length_m"])) / 2.0
    x_win_2 = x_win_1 + float(geometry["window_length_m"])

    internal_mass_area = max(1.0, float(geometry["conditioned_floor_m2"]))
    internal_mass_thickness_m = 0.10
    internal_mass_cp_j_per_kgk = 1000.0
    internal_mass_k_w_per_mk = 0.15
    extra_capacity_j_per_k = float(geometry["extra_capacity_wh_per_k"]) * 3600.0
    internal_mass_density = (
        max(1.0, extra_capacity_j_per_k / (internal_mass_area * internal_mass_thickness_m * internal_mass_cp_j_per_kgk))
        if extra_capacity_j_per_k > 0.0
        else 1.0
    )
    simple_glazing_shgc = float(cohort["teacher_simple_glazing_shgc"])
    simple_glazing_visible_transmittance = float(cohort["teacher_simple_glazing_visible_transmittance"])
    if min(simple_glazing_shgc, simple_glazing_visible_transmittance) <= 0.0:
        raise ValueError(
            f"[energyplus_teacher] Teacher simple-glazing optics must be > 0 for cohort='{cohort['cohort_id']}'."
        )

    schedule_blocks = [
        "ScheduleTypeLimits,\n  Fraction;\n",
        "ScheduleTypeLimits,\n  Temperature;\n",
        "ScheduleTypeLimits,\n  Any Number;\n",
        _schedule_file_block("HeatingSetpointFile", "Temperature", schedule_csv_path, 2, year_rows),
        _schedule_file_block("CoolingSetpointFile", "Temperature", schedule_csv_path, 3, year_rows),
        _schedule_file_block("InternalGainsFraction", "Fraction", schedule_csv_path, 7, year_rows),
        _schedule_file_block("InfiltrationFraction", "Fraction", schedule_csv_path, 8, year_rows),
        _schedule_file_block("VentilationFraction", "Fraction", schedule_csv_path, 9, year_rows),
        "Schedule:Compact,\n  ZoneControlTypeAlwaysFour,\n  Any Number,\n  Through: 12/31,\n  For: AllDays,\n  Until: 24:00,4;\n",
    ]

    ideal_loads_block = ""
    thermostat_block = ""
    output_blocks = [
        "Output:VariableDictionary,\n  IDF;\n",
        "Output:Variable,\n  *,\n  Zone Mean Air Temperature,\n  Hourly;\n",
        "Output:Variable,\n  *,\n  Site Outdoor Air Drybulb Temperature,\n  Hourly;\n",
        "Output:Variable,\n  *,\n  Enclosure Windows Total Transmitted Solar Radiation Rate,\n  Hourly;\n",
        "Output:Variable,\n  *,\n  Zone Windows Total Heat Gain Rate,\n  Hourly;\n",
        "Output:Variable,\n  *,\n  Zone Windows Total Heat Loss Rate,\n  Hourly;\n",
    ]
    output_blocks.extend(
        [f"Output:Variable,\n  *,\n  {name},\n  Hourly;\n" for name in _OPTIONAL_AIR_PATH_OUTPUT_VARIABLES]
    )
    output_blocks.extend(
        [f"Output:Variable,\n  *,\n  {name},\n  Hourly;\n" for name in _DEBUG_AIR_PATH_OUTPUT_VARIABLES]
    )
    if control_mode != "free_float":
        thermostat_block = """ThermostatSetpoint:DualSetpoint,
  DualThermostat,
  HeatingSetpointFile,
  CoolingSetpointFile;

ZoneControl:Thermostat,
  ZoneThermostat,
  Zone1,
  ZoneControlTypeAlwaysFour,
  ThermostatSetpoint:DualSetpoint,
  DualThermostat;
"""
        ideal_loads_block = """ZoneHVAC:EquipmentConnections,
  Zone1,
  Zone1 Equipment,
  Zone1 Supply Inlet,
  ,
  Zone1 Air Node,
  Zone1 Return Outlet;

ZoneHVAC:EquipmentList,
  Zone1 Equipment,
  SequentialLoad,
  ZoneHVAC:IdealLoadsAirSystem,
  Zone1 Ideal Loads,
  1,
  1,
  ,
  ;

ZoneHVAC:IdealLoadsAirSystem,
  Zone1 Ideal Loads,
  ,
  Zone1 Supply Inlet,
  ,
  ,
  50,
  13,
  0.015,
  0.01,
  NoLimit,
  ,
  ,
  NoLimit,
  ,
  ,
  ,
  ,
  ,
  ,
  ,
  ,
  ,
  ,
  ;
"""
        output_blocks.extend(
            [
                "Output:Variable,\n  *,\n  Zone Ideal Loads Zone Total Heating Rate,\n  Hourly;\n",
                "Output:Variable,\n  *,\n  Zone Ideal Loads Zone Total Cooling Rate,\n  Hourly;\n",
                *[
                    f"Output:Variable,\n  *,\n  {name},\n  Hourly;\n"
                    for name in _OPTIONAL_IDEAL_LOADS_OUTDOOR_AIR_OUTPUT_VARIABLES
                ],
            ]
        )

    schedule_export = pd.read_csv(schedule_csv_path)
    required_schedule_columns = [
        "internal_gains_w_m2",
        "infiltration_ach",
        "ventilation_ach",
        "internal_gains_fraction",
        "infiltration_fraction",
        "ventilation_fraction",
    ]
    missing_schedule_columns = [col for col in required_schedule_columns if col not in schedule_export.columns]
    if missing_schedule_columns:
        raise KeyError(
            "[energyplus_teacher] Exported schedule CSV is missing required normalized columns: "
            f"{missing_schedule_columns}"
        )
    internal_gains_peak_w_m2 = float(schedule_export["internal_gains_w_m2"].max())
    infiltration_peak_ach = float(schedule_export["infiltration_ach"].max())
    ventilation_peak_ach = float(schedule_export["ventilation_ach"].max())

    electric_equipment_block = ""
    if internal_gains_peak_w_m2 > 0.0:
        design_level_w = internal_gains_peak_w_m2 * float(geometry["conditioned_floor_m2"])
        electric_equipment_block = f"""ElectricEquipment,
  Zone1 Internal Gains,
  Zone1,
  InternalGainsFraction,
  EquipmentLevel,
  {design_level_w:.6f},
  ,
  ,
  0.0,
  0.58,
  0.0;
"""

    infiltration_block = ""
    if infiltration_peak_ach > 0.0:
        infiltration_design_flow = infiltration_peak_ach * float(geometry["volume_m3"]) / 3600.0
        infiltration_block = f"""ZoneInfiltration:DesignFlowRate,
  Zone1 Infiltration,
  Zone1,
  InfiltrationFraction,
  Flow/Zone,
  {infiltration_design_flow:.8f},
  ,
  ,
  ,
  1.0,
  0.0,
  0.0,
  0.0;
"""

    ventilation_block = ""
    if ventilation_peak_ach > 0.0:
        ventilation_design_flow = ventilation_peak_ach * float(geometry["volume_m3"]) / 3600.0
        ventilation_block = f"""ZoneVentilation:DesignFlowRate,
  Zone1 Ventilation,
  Zone1,
  VentilationFraction,
  Flow/Zone,
  {ventilation_design_flow:.8f},
  ,
  ,
  ,
  Intake,
  0.0,
  1.0,
  1.0,
  0.0,
  0.0,
  0.0,
  -100.0,
  ,
  100.0,
  ,
  -100.0,
  ,
  100.0,
  ,
  40.0;
"""

    internal_mass_block = ""
    if extra_capacity_j_per_k > 0.0:
        internal_mass_block = f"""Material,
  InternalMassMaterial,
  MediumSmooth,
  {internal_mass_thickness_m:.6f},
  {internal_mass_k_w_per_mk:.6f},
  {internal_mass_density:.6f},
  {internal_mass_cp_j_per_kgk:.6f};

Construction,
  InternalMassConstruction,
  InternalMassMaterial;

InternalMass,
  Zone1 Internal Mass,
  InternalMassConstruction,
  Zone1,
  ,
  {internal_mass_area:.6f};
"""

    content = f"""Version,{version};

Building,
  CalibrationTeacher,
  0.0,
  Suburbs,
  0.04,
  0.4,
  FullInteriorAndExterior,
  25,
  6;

Timestep,1;

SimulationControl,
  No,
  No,
  No,
  Yes,
  Yes;

RunPeriod,
  {experiment["experiment_id"]},
  {int(start_local.month)},
  {int(start_local.day)},
  {calendar_year},
  {int(last_simulated.month)},
  {int(last_simulated.day)},
  {calendar_year},
  {start_weekday},
  Yes,
  No,
  No,
  Yes,
  Yes;

GlobalGeometryRules,
  UpperLeftCorner,
  CounterClockWise,
  World;

Material:NoMass,
  WallResistance,
  Rough,
  {1.0 / float(geometry["wall_u_eff"]):.8f};

Material:NoMass,
  RoofResistance,
  Rough,
  {1.0 / float(geometry["roof_u_eff"]):.8f};

Material:NoMass,
  FloorResistance,
  Rough,
  {1.0 / float(geometry["floor_u_eff"]):.8f};

WindowMaterial:SimpleGlazingSystem,
  WindowSimple,
  {float(cohort["u_window"]):.6f},
  {simple_glazing_shgc:.6f},
  {simple_glazing_visible_transmittance:.6f};

Construction,
  WallConstruction,
  WallResistance;

Construction,
  RoofConstruction,
  RoofResistance;

Construction,
  FloorConstruction,
  FloorResistance;

Construction,
  WindowConstruction,
  WindowSimple;

Zone,
  Zone1;

BuildingSurface:Detailed,
  Floor,
  Floor,
  FloorConstruction,
  Zone1,
  ,
  Ground,
  ,
  NoSun,
  NoWind,
  0.0,
  4,
  0,0,0,
  0,{side:.6f},0,
  {side:.6f},{side:.6f},0,
  {side:.6f},0,0;

BuildingSurface:Detailed,
  Roof,
  Roof,
  RoofConstruction,
  Zone1,
  ,
  Outdoors,
  ,
  SunExposed,
  WindExposed,
  0.0,
  4,
  0,{side:.6f},{height:.6f},
  0,0,{height:.6f},
  {side:.6f},0,{height:.6f},
  {side:.6f},{side:.6f},{height:.6f};

BuildingSurface:Detailed,
  WallSouth,
  Wall,
  WallConstruction,
  Zone1,
  ,
  Outdoors,
  ,
  SunExposed,
  WindExposed,
  0.5,
  4,
  0,0,{height:.6f},
  0,0,0,
  {side:.6f},0,0,
  {side:.6f},0,{height:.6f};

BuildingSurface:Detailed,
  WallEast,
  Wall,
  WallConstruction,
  Zone1,
  ,
  Outdoors,
  ,
  SunExposed,
  WindExposed,
  0.5,
  4,
  {side:.6f},0,{height:.6f},
  {side:.6f},0,0,
  {side:.6f},{side:.6f},0,
  {side:.6f},{side:.6f},{height:.6f};

BuildingSurface:Detailed,
  WallNorth,
  Wall,
  WallConstruction,
  Zone1,
  ,
  Outdoors,
  ,
  SunExposed,
  WindExposed,
  0.5,
  4,
  {side:.6f},{side:.6f},{height:.6f},
  {side:.6f},{side:.6f},0,
  0,{side:.6f},0,
  0,{side:.6f},{height:.6f};

BuildingSurface:Detailed,
  WallWest,
  Wall,
  WallConstruction,
  Zone1,
  ,
  Outdoors,
  ,
  SunExposed,
  WindExposed,
  0.5,
  4,
  0,{side:.6f},{height:.6f},
  0,{side:.6f},0,
  0,0,0,
  0,0,{height:.6f};

FenestrationSurface:Detailed,
  SouthWindow,
  Window,
  WindowConstruction,
  WallSouth,
  ,
  0.5,
  ,
  1,
  4,
  {x_win_1:.6f},0,{z_win_2:.6f},
  {x_win_1:.6f},0,{z_win_1:.6f},
  {x_win_2:.6f},0,{z_win_1:.6f},
  {x_win_2:.6f},0,{z_win_2:.6f};

FenestrationSurface:Detailed,
  EastWindow,
  Window,
  WindowConstruction,
  WallEast,
  ,
  0.5,
  ,
  1,
  4,
  {side:.6f},{x_win_1:.6f},{z_win_2:.6f},
  {side:.6f},{x_win_1:.6f},{z_win_1:.6f},
  {side:.6f},{x_win_2:.6f},{z_win_1:.6f},
  {side:.6f},{x_win_2:.6f},{z_win_2:.6f};

FenestrationSurface:Detailed,
  NorthWindow,
  Window,
  WindowConstruction,
  WallNorth,
  ,
  0.5,
  ,
  1,
  4,
  {x_win_2:.6f},{side:.6f},{z_win_2:.6f},
  {x_win_2:.6f},{side:.6f},{z_win_1:.6f},
  {x_win_1:.6f},{side:.6f},{z_win_1:.6f},
  {x_win_1:.6f},{side:.6f},{z_win_2:.6f};

FenestrationSurface:Detailed,
  WestWindow,
  Window,
  WindowConstruction,
  WallWest,
  ,
  0.5,
  ,
  1,
  4,
  0,{x_win_2:.6f},{z_win_2:.6f},
  0,{x_win_2:.6f},{z_win_1:.6f},
  0,{x_win_1:.6f},{z_win_1:.6f},
  0,{x_win_1:.6f},{z_win_2:.6f};

{''.join(schedule_blocks)}
{thermostat_block}
{ideal_loads_block}
{electric_equipment_block}
{infiltration_block}
{ventilation_block}
{internal_mass_block}
Output:SQLite,
  SimpleAndTabular;

{''.join(output_blocks)}
"""
    idf_path.write_text(content, encoding="utf-8")


def _extract_hourly_outputs(sql_path: Path, *, control_mode: str) -> pd.DataFrame:
    con = sqlite3.connect(sql_path)
    query = """
        SELECT
            t.Year,
            t.Month,
            t.Day,
            t.Hour,
            t.Minute,
            d.Name,
            d.Units,
            r.Value
        FROM ReportData r
        JOIN ReportDataDictionary d
          ON r.ReportDataDictionaryIndex = d.ReportDataDictionaryIndex
        JOIN Time t
          ON r.TimeIndex = t.TimeIndex
        WHERE (t.WarmupFlag IS NULL OR t.WarmupFlag = 0)
          AND d.ReportingFrequency = 'Hourly'
          AND d.Name IN (
              'Zone Mean Air Temperature',
              'Zone Ideal Loads Zone Total Heating Rate',
              'Zone Ideal Loads Zone Total Cooling Rate',
              'Site Outdoor Air Drybulb Temperature',
              'Enclosure Windows Total Transmitted Solar Radiation Rate',
              'Zone Windows Total Heat Gain Rate',
              'Zone Windows Total Heat Loss Rate',
              'Zone Infiltration Sensible Heat Loss Energy',
              'Zone Infiltration Sensible Heat Gain Energy',
              'Zone Ventilation Sensible Heat Loss Energy',
              'Zone Ventilation Sensible Heat Gain Energy',
              'Zone Air Heat Balance Outdoor Air Transfer Rate',
              'Zone Ideal Loads Outdoor Air Sensible Heating Rate',
              'Zone Ideal Loads Outdoor Air Sensible Cooling Rate'
          )
        ORDER BY t.Year, t.Month, t.Day, t.Hour, d.Name
    """
    df = pd.read_sql_query(query, con)
    con.close()
    if df.empty:
        raise RuntimeError(f"[energyplus_teacher] No hourly report data found in {sql_path}.")
    pivot = (
        df.pivot_table(
            index=["Year", "Month", "Day", "Hour", "Minute"],
            columns="Name",
            values="Value",
            aggfunc="first",
        )
        .reset_index()
        .rename_axis(columns=None)
    )
    required = [
        "Zone Mean Air Temperature",
        "Site Outdoor Air Drybulb Temperature",
        "Enclosure Windows Total Transmitted Solar Radiation Rate",
        "Zone Windows Total Heat Gain Rate",
        "Zone Windows Total Heat Loss Rate",
    ]
    missing = [name for name in required if name not in pivot.columns]
    if missing:
        raise RuntimeError(f"[energyplus_teacher] Missing required hourly output columns in {sql_path}: {missing}")
    if control_mode == "free_float":
        pivot["Zone Ideal Loads Zone Total Heating Rate"] = 0.0
        pivot["Zone Ideal Loads Zone Total Cooling Rate"] = 0.0
    else:
        for name in ("Zone Ideal Loads Zone Total Heating Rate", "Zone Ideal Loads Zone Total Cooling Rate"):
            if name not in pivot.columns:
                raise RuntimeError(
                    f"[energyplus_teacher] Missing required ideal-loads output '{name}' in {sql_path}."
                )
    for name in _OPTIONAL_AIR_PATH_OUTPUT_VARIABLES:
        if name not in pivot.columns:
            pivot[name] = 0.0
    for name in _OPTIONAL_IDEAL_LOADS_OUTDOOR_AIR_OUTPUT_VARIABLES:
        if name not in pivot.columns:
            pivot[name] = 0.0
    return pivot


def _build_timestamp_local(hourly: pd.DataFrame) -> pd.DatetimeIndex:
    if "Minute" not in hourly.columns:
        raise KeyError("[energyplus_teacher] Hourly dataframe is missing required column 'Minute'.")
    if "Hour" not in hourly.columns:
        raise KeyError("[energyplus_teacher] Hourly dataframe is missing required column 'Hour'.")
    if (hourly["Hour"] < 1).any() or (hourly["Hour"] > 24).any():
        raise ValueError("[energyplus_teacher] EnergyPlus hourly output must use hours in 1..24.")
    return pd.to_datetime(
        {
            "year": hourly["Year"].astype(int),
            "month": hourly["Month"].astype(int),
            "day": hourly["Day"].astype(int),
            "hour": hourly["Hour"].astype(int) - 1,
            "minute": hourly["Minute"].astype(int),
        }
    )


def _load_epw_weather_window(*, epw_path: Path, start_local: pd.Timestamp, end_local: pd.Timestamp) -> pd.DataFrame:
    epw = pd.read_csv(epw_path, skiprows=8, header=None)
    if epw.empty:
        raise RuntimeError(f"[energyplus_teacher] EPW file appears empty: {epw_path}")
    required_cols = [0, 1, 2, 3, 6, 13, 14, 15]
    missing_cols = [col for col in required_cols if col not in epw.columns]
    if missing_cols:
        raise RuntimeError(f"[energyplus_teacher] EPW file is missing required columns: {missing_cols}")
    weather = pd.DataFrame(
        {
            "timestamp_local": pd.to_datetime(
                {
                    "year": epw[0].astype(int),
                    "month": epw[1].astype(int),
                    "day": epw[2].astype(int),
                    "hour": epw[3].astype(int) - 1,
                    "minute": 0,
                }
            ),
            "epw_outdoor_air_drybulb_c": pd.to_numeric(epw[6], errors="coerce"),
            "epw_ghi_wh_m2": pd.to_numeric(epw[13], errors="coerce"),
            "epw_dni_wh_m2": pd.to_numeric(epw[14], errors="coerce"),
            "epw_dhi_wh_m2": pd.to_numeric(epw[15], errors="coerce"),
        }
    )
    weather_window = weather.loc[
        (weather["timestamp_local"] >= start_local) & (weather["timestamp_local"] < end_local)
    ].copy()
    if weather_window.empty:
        raise RuntimeError(
            f"[energyplus_teacher] No EPW weather rows found in requested window {start_local} .. {end_local}."
        )
    return weather_window.reset_index(drop=True)


def _resolve_dh_connected_share(
    *,
    cohort: dict,
    location: str,
    explicit_share: float | None,
) -> tuple[float | None, str]:
    override = cohort.get("dh_connected_share_override")
    if override is not None:
        share = float(override)
        source = "cohort_override"
    elif explicit_share is not None:
        share = float(explicit_share)
        source = "run_argument"
    else:
        dh_cfg = make_district_heating(location=location)
        if float(dh_cfg.share) > 0.0:
            share = float(dh_cfg.share)
            source = "district_heating.share"
        else:
            return None, "unset"
    if not 0.0 <= share <= 1.0:
        raise ValueError(f"[energyplus_teacher] DH connected share must stay within [0, 1], got {share}.")
    return share, source


def _build_plausibility_export(
    *,
    hourly: pd.DataFrame,
    schedule_df: pd.DataFrame,
    experiment: dict,
    geometry: dict[str, float],
    cohort: dict,
    explicit_dh_connected_share: float | None,
) -> tuple[pd.DataFrame, dict]:
    cfg = make_building_calibration_config()
    hourly_local = hourly.copy()
    hourly_local["timestamp_local"] = _build_timestamp_local(hourly_local)

    start_local = pd.Timestamp(str(experiment["start_local"]))
    end_local = pd.Timestamp(str(experiment["end_local"]))
    weather_window = _load_epw_weather_window(
        epw_path=Path(str(experiment["epw_path"])).resolve(),
        start_local=start_local,
        end_local=end_local,
    )
    schedule_window = schedule_df.loc[
        (schedule_df["timestamp_local"] >= start_local) & (schedule_df["timestamp_local"] < end_local)
    ].copy()
    if len(schedule_window) != len(hourly_local):
        raise RuntimeError(
            "[energyplus_teacher] Schedule window length does not match extracted EnergyPlus hourly outputs."
        )
    if len(weather_window) != len(hourly_local):
        raise RuntimeError(
            "[energyplus_teacher] EPW weather window length does not match extracted EnergyPlus hourly outputs."
        )

    merged = hourly_local.merge(schedule_window, on="timestamp_local", how="left", validate="one_to_one")
    merged = merged.merge(weather_window, on="timestamp_local", how="left", validate="one_to_one")
    required_schedule_cols = [
        "heating_setpoint_c",
        "cooling_setpoint_c",
        "internal_gains_w_m2",
        "internal_gains_fraction",
        "infiltration_ach",
        "infiltration_fraction",
        "ventilation_ach",
        "ventilation_fraction",
    ]
    missing_schedule_cols = [col for col in required_schedule_cols if col not in merged.columns]
    if missing_schedule_cols:
        raise KeyError(
            "[energyplus_teacher] Plausibility export is missing required schedule columns after merge: "
            f"{missing_schedule_cols}"
        )

    reference_area_m2 = float(geometry["conditioned_floor_m2"])
    if reference_area_m2 <= 0.0:
        raise ValueError("[energyplus_teacher] conditioned_floor_m2 must be > 0 for plausibility export.")
    seed_ua_reference_w_per_k = float(cohort["runtime_ua_w_per_k"]) * float(geometry["scale"])
    if seed_ua_reference_w_per_k <= 0.0:
        raise ValueError("[energyplus_teacher] Derived reference-scale seed UA must be > 0.")
    scale_to_cohort = float(cohort["represented_gfa_m2"]) / reference_area_m2
    if scale_to_cohort <= 0.0:
        raise ValueError("[energyplus_teacher] scale_to_cohort must be > 0 for plausibility export.")
    dh_connected_share, dh_connected_share_source = _resolve_dh_connected_share(
        cohort=cohort,
        location=str(cfg.location),
        explicit_share=explicit_dh_connected_share,
    )
    scale_to_dh_bus = None if dh_connected_share is None else scale_to_cohort * dh_connected_share
    volume_m3 = float(geometry["volume_m3"])
    if volume_m3 <= 0.0:
        raise ValueError("[energyplus_teacher] volume_m3 must be > 0 for plausibility export.")
    cp_air_wh_per_m3k = 0.34
    delta_t_positive_k = (merged["zone_mean_air_temperature_c"] - merged["site_outdoor_air_drybulb_c"]).clip(lower=0.0)
    delta_t_negative_k = (merged["site_outdoor_air_drybulb_c"] - merged["zone_mean_air_temperature_c"]).clip(lower=0.0)

    merged["internal_gains_total_w"] = merged["internal_gains_w_m2"] * reference_area_m2
    merged["approx_transmission_loss_seed_ua_w"] = (
        seed_ua_reference_w_per_k * delta_t_positive_k
    )
    merged["approx_transmission_gain_seed_ua_w"] = (
        seed_ua_reference_w_per_k * delta_t_negative_k
    )
    merged["approx_infiltration_loss_w"] = (
        cp_air_wh_per_m3k * volume_m3 * merged["infiltration_ach"] * delta_t_positive_k
    )
    merged["approx_infiltration_gain_w"] = (
        cp_air_wh_per_m3k * volume_m3 * merged["infiltration_ach"] * delta_t_negative_k
    )
    merged["approx_ventilation_loss_w"] = (
        cp_air_wh_per_m3k * volume_m3 * merged["ventilation_ach"] * delta_t_positive_k
    )
    merged["approx_ventilation_gain_w"] = (
        cp_air_wh_per_m3k * volume_m3 * merged["ventilation_ach"] * delta_t_negative_k
    )
    merged["window_to_floor_ratio_reference"] = float(geometry["window_area_total_m2"]) / reference_area_m2
    merged["wall_to_floor_ratio_reference"] = float(geometry["wall_area_m2"]) / reference_area_m2
    merged["roof_to_floor_ratio_reference"] = float(geometry["roof_area_m2"]) / reference_area_m2
    merged["floor_exposed_to_floor_ratio_reference"] = float(geometry["floor_exposed_area_m2"]) / reference_area_m2
    merged["window_solar_transmitted_kwh"] = merged["zone_windows_transmitted_solar_rate_w"] / 1000.0
    merged["window_heat_gain_kwh"] = merged["zone_windows_total_heat_gain_rate_w"] / 1000.0
    merged["window_heat_loss_kwh"] = merged["zone_windows_total_heat_loss_rate_w"] / 1000.0
    merged["teacher_infiltration_sensible_heat_loss_kwh"] = merged["zone_infiltration_sensible_heat_loss_kwh"]
    merged["teacher_infiltration_sensible_heat_gain_kwh"] = merged["zone_infiltration_sensible_heat_gain_kwh"]
    merged["teacher_ventilation_sensible_heat_loss_kwh"] = merged["zone_ventilation_sensible_heat_loss_kwh"]
    merged["teacher_ventilation_sensible_heat_gain_kwh"] = merged["zone_ventilation_sensible_heat_gain_kwh"]
    merged["teacher_infiltration_sensible_heat_loss_w"] = merged["teacher_infiltration_sensible_heat_loss_kwh"] * 1000.0
    merged["teacher_ventilation_sensible_heat_loss_w"] = merged["teacher_ventilation_sensible_heat_loss_kwh"] * 1000.0
    merged["teacher_outdoor_air_loss_w"] = (
        -merged["zone_air_heat_balance_outdoor_air_transfer_rate_w"]
    ).clip(lower=0.0)
    merged["teacher_outdoor_air_gain_w"] = merged["zone_air_heat_balance_outdoor_air_transfer_rate_w"].clip(lower=0.0)
    merged["teacher_outdoor_air_loss_kwh"] = merged["teacher_outdoor_air_loss_w"] / 1000.0
    merged["teacher_outdoor_air_gain_kwh"] = merged["teacher_outdoor_air_gain_w"] / 1000.0
    merged["teacher_ideal_loads_outdoor_air_sensible_heating_kwh"] = (
        merged["zone_ideal_loads_outdoor_air_sensible_heating_kwh"]
    )
    merged["teacher_ideal_loads_outdoor_air_sensible_cooling_kwh"] = (
        merged["zone_ideal_loads_outdoor_air_sensible_cooling_kwh"]
    )

    window_hours = float(len(merged))
    annual_space_heat_target_kwh = float(cohort["annual_space_heat_target_kwh"])
    expected_average_window_space_heat_kwh_cohort = annual_space_heat_target_kwh * (window_hours / 8760.0)
    observed_window_space_heat_kwh_reference = float((merged["zone_total_heating_rate_w"] / 1000.0).sum())
    observed_window_space_heat_kwh_cohort = observed_window_space_heat_kwh_reference * scale_to_cohort
    observed_window_space_heat_kwh_dh_bus = (
        None if scale_to_dh_bus is None else observed_window_space_heat_kwh_reference * scale_to_dh_bus
    )
    expected_average_window_space_heat_kwh_dh_bus = (
        None if dh_connected_share is None else expected_average_window_space_heat_kwh_cohort * dh_connected_share
    )
    window_area_total_m2 = float(geometry["window_area_total_m2"])
    if window_area_total_m2 <= 0.0:
        raise ValueError("[energyplus_teacher] window_area_total_m2 must be > 0 for plausibility export.")
    window_solar_transmitted_kwh_total = float(merged["window_solar_transmitted_kwh"].sum())
    window_heat_gain_kwh_total = float(merged["window_heat_gain_kwh"].sum())
    window_heat_loss_kwh_total = float(merged["window_heat_loss_kwh"].sum())

    summary = {
        "window_hours": int(window_hours),
        "reference_conditioned_floor_m2": reference_area_m2,
        "cohort_represented_gfa_m2": float(cohort["represented_gfa_m2"]),
        "dh_connected_share_used": dh_connected_share,
        "dh_connected_share_source": dh_connected_share_source,
        "scale_to_cohort": scale_to_cohort,
        "scale_to_dh_bus": scale_to_dh_bus,
        "annual_space_heat_target_kwh_cohort": annual_space_heat_target_kwh,
        "annual_space_heat_target_kwh_dh_bus": (
            None if dh_connected_share is None else annual_space_heat_target_kwh * dh_connected_share
        ),
        "heating_kwh_total": float((merged["zone_total_heating_rate_w"] / 1000.0).sum()),
        "cooling_kwh_total": float((merged["zone_total_cooling_rate_w"] / 1000.0).sum()),
        "heating_kwh_reference_total": observed_window_space_heat_kwh_reference,
        "heating_kwh_cohort_scaled_total": observed_window_space_heat_kwh_cohort,
        "heating_kwh_dh_bus_scaled_total": observed_window_space_heat_kwh_dh_bus,
        "expected_average_window_space_heat_kwh_cohort": expected_average_window_space_heat_kwh_cohort,
        "expected_average_window_space_heat_kwh_dh_bus": expected_average_window_space_heat_kwh_dh_bus,
        "window_factor_vs_average_cohort": (
            observed_window_space_heat_kwh_cohort / expected_average_window_space_heat_kwh_cohort
            if expected_average_window_space_heat_kwh_cohort > 0.0
            else None
        ),
        "window_factor_vs_average_dh_bus": (
            observed_window_space_heat_kwh_dh_bus / expected_average_window_space_heat_kwh_dh_bus
            if observed_window_space_heat_kwh_dh_bus is not None
            and expected_average_window_space_heat_kwh_dh_bus is not None
            and expected_average_window_space_heat_kwh_dh_bus > 0.0
            else None
        ),
        "internal_gains_kwh_total": float((merged["internal_gains_total_w"] / 1000.0).sum()),
        "window_solar_transmitted_kwh_total": window_solar_transmitted_kwh_total,
        "window_heat_gain_kwh_total": window_heat_gain_kwh_total,
        "window_heat_loss_kwh_total": window_heat_loss_kwh_total,
        "window_solar_transmitted_kwh_per_window_m2": window_solar_transmitted_kwh_total / window_area_total_m2,
        "window_heat_gain_kwh_per_window_m2": window_heat_gain_kwh_total / window_area_total_m2,
        "window_heat_loss_kwh_per_window_m2": window_heat_loss_kwh_total / window_area_total_m2,
        "window_to_floor_ratio_reference": float(geometry["window_area_total_m2"]) / reference_area_m2,
        "wall_to_floor_ratio_reference": float(geometry["wall_area_m2"]) / reference_area_m2,
        "roof_to_floor_ratio_reference": float(geometry["roof_area_m2"]) / reference_area_m2,
        "floor_exposed_to_floor_ratio_reference": float(geometry["floor_exposed_area_m2"]) / reference_area_m2,
        "seed_ua_reference_w_per_m2k": seed_ua_reference_w_per_k / reference_area_m2,
        "heat_capacity_reference_wh_per_m2k": float(geometry["heat_capacity_wh_per_k"]) / reference_area_m2,
        "window_solar_to_internal_gains_ratio": (
            window_solar_transmitted_kwh_total / float((merged["internal_gains_total_w"] / 1000.0).sum())
            if float((merged["internal_gains_total_w"] / 1000.0).sum()) > 0.0
            else None
        ),
        "window_solar_to_heating_ratio": (
            window_solar_transmitted_kwh_total / observed_window_space_heat_kwh_reference
            if observed_window_space_heat_kwh_reference > 0.0
            else None
        ),
        "epw_ghi_wh_m2_total": float(merged["epw_ghi_wh_m2"].sum()),
        "epw_dni_wh_m2_total": float(merged["epw_dni_wh_m2"].sum()),
        "epw_dhi_wh_m2_total": float(merged["epw_dhi_wh_m2"].sum()),
        "teacher_infiltration_sensible_heat_loss_kwh_total": float(
            merged["teacher_infiltration_sensible_heat_loss_kwh"].sum()
        ),
        "teacher_infiltration_sensible_heat_gain_kwh_total": float(
            merged["teacher_infiltration_sensible_heat_gain_kwh"].sum()
        ),
        "teacher_ventilation_sensible_heat_loss_kwh_total": float(
            merged["teacher_ventilation_sensible_heat_loss_kwh"].sum()
        ),
        "teacher_ventilation_sensible_heat_gain_kwh_total": float(
            merged["teacher_ventilation_sensible_heat_gain_kwh"].sum()
        ),
        "teacher_outdoor_air_loss_kwh_total": float(merged["teacher_outdoor_air_loss_kwh"].sum()),
        "teacher_outdoor_air_gain_kwh_total": float(merged["teacher_outdoor_air_gain_kwh"].sum()),
        "teacher_ideal_loads_outdoor_air_sensible_heating_kwh_total": float(
            merged["teacher_ideal_loads_outdoor_air_sensible_heating_kwh"].sum()
        ),
        "teacher_ideal_loads_outdoor_air_sensible_cooling_kwh_total": float(
            merged["teacher_ideal_loads_outdoor_air_sensible_cooling_kwh"].sum()
        ),
        "approx_infiltration_loss_kwh_total": float((merged["approx_infiltration_loss_w"] / 1000.0).sum()),
        "approx_ventilation_loss_kwh_total": float((merged["approx_ventilation_loss_w"] / 1000.0).sum()),
        "approx_transmission_loss_seed_ua_kwh_total": float((merged["approx_transmission_loss_seed_ua_w"] / 1000.0).sum()),
        "mean_zone_air_temperature_c": float(merged["zone_mean_air_temperature_c"].mean()),
        "min_zone_air_temperature_c": float(merged["zone_mean_air_temperature_c"].min()),
        "max_zone_air_temperature_c": float(merged["zone_mean_air_temperature_c"].max()),
        "mean_outdoor_air_temperature_c": float(merged["site_outdoor_air_drybulb_c"].mean()),
        "seed_ua_reference_w_per_k": seed_ua_reference_w_per_k,
    }
    return merged, summary


def _save_plausibility_plot(df: pd.DataFrame, *, out_path: Path) -> None:
    fig, axes = plt.subplots(3, 1, figsize=(14, 10), sharex=True)
    ts = pd.to_datetime(df["timestamp_local"])

    ax = axes[0]
    ax.plot(ts, df["zone_mean_air_temperature_c"], label="Indoor air", linewidth=1.8, color="#111827")
    ax.plot(ts, df["site_outdoor_air_drybulb_c"], label="Outdoor air", linewidth=1.3, color="#6b7280")
    ax.plot(ts, df["heating_setpoint_c"], label="Heating setpoint", linewidth=1.3, linestyle="--", color="#dc2626")
    ax.plot(ts, df["cooling_setpoint_c"], label="Cooling setpoint", linewidth=1.3, linestyle="--", color="#2563eb")
    ax.set_ylabel("Temperature [C]")
    ax.legend(loc="upper right", ncol=2)
    ax.grid(alpha=0.25)

    ax = axes[1]
    ax.plot(ts, df["zone_total_heating_rate_w"] / 1000.0, label="Heating", linewidth=1.8, color="#b91c1c")
    ax.plot(ts, df["zone_total_cooling_rate_w"] / 1000.0, label="Cooling", linewidth=1.5, color="#1d4ed8")
    ax.plot(ts, df["internal_gains_total_w"] / 1000.0, label="Internal gains", linewidth=1.4, color="#7c3aed")
    ax.plot(
        ts,
        df["zone_windows_transmitted_solar_rate_w"] / 1000.0,
        label="Window solar gain",
        linewidth=1.4,
        color="#f59e0b",
    )
    ax.set_ylabel("Power [kW]")
    ax.legend(loc="upper right", ncol=2)
    ax.grid(alpha=0.25)

    ax = axes[2]
    ax.plot(
        ts,
        df["approx_transmission_loss_seed_ua_w"] / 1000.0,
        label="Transmission loss (seed UA)",
        linewidth=1.4,
        color="#374151",
    )
    ax.plot(
        ts,
        df["approx_infiltration_loss_w"] / 1000.0,
        label="Infiltration loss (approx)",
        linewidth=1.4,
        color="#0f766e",
    )
    ax.plot(
        ts,
        df["approx_ventilation_loss_w"] / 1000.0,
        label="Ventilation loss (approx)",
        linewidth=1.4,
        color="#0891b2",
    )
    ax.plot(
        ts,
        df["zone_windows_total_heat_loss_rate_w"] / 1000.0,
        label="Window heat loss",
        linewidth=1.4,
        color="#f59e0b",
    )
    ax.set_ylabel("Power [kW]")
    ax.set_xlabel("Local time")
    ax.legend(loc="upper right", ncol=2)
    ax.grid(alpha=0.25)
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%m-%d\n%H:%M"))

    fig.tight_layout()
    fig.savefig(out_path, dpi=170, bbox_inches="tight")
    plt.close(fig)


def run_energyplus_teacher_experiment(
    *,
    cohort_id: str | None = None,
    experiment_id: str | None = None,
    dh_connected_share: float | None = None,
) -> TeacherExperimentResult:
    cfg = make_building_calibration_config()
    resolved_cohort_id = str(cohort_id or cfg.teacher_pilot_default_cohort_id).strip()
    resolved_experiment_id = str(experiment_id or cfg.teacher_pilot_default_experiment_id).strip()
    if not resolved_cohort_id:
        raise ValueError("[energyplus_teacher] cohort_id must be a non-empty string.")
    if not resolved_experiment_id:
        raise ValueError("[energyplus_teacher] experiment_id must be a non-empty string.")

    cohort, experiment = _resolve_teacher_context(
        cohort_id=resolved_cohort_id,
        experiment_id=resolved_experiment_id,
    )
    exe = _discover_energyplus(cfg.energyplus_executable_path)
    workdir = Path(cfg.teacher_runs_output_dir).resolve() / resolved_cohort_id / resolved_experiment_id
    if workdir.exists():
        shutil.rmtree(workdir)
    workdir.mkdir(parents=True, exist_ok=False)

    schedule_df = _build_full_year_schedule_frame(
        calendar_year=int(experiment["calendar_year"]),
        cohort=cohort,
        experiment=experiment,
    )
    schedule_csv_path = _write_schedule_csv(workdir, schedule_df=schedule_df)
    schedule_export = pd.read_csv(schedule_csv_path, parse_dates=["timestamp_local"])
    geometry = _build_equivalent_geometry(cohort)

    idf_path = workdir / "teacher_experiment.idf"
    _build_teacher_idf(
        idf_path=idf_path,
        cohort=cohort,
        experiment=experiment,
        geometry=geometry,
        schedule_csv_path=schedule_csv_path,
        year_rows=len(schedule_df),
        version=str(cfg.energyplus_idf_version),
    )

    stdout_path = workdir / "stdout.txt"
    stderr_path = workdir / "stderr.txt"
    err_path = workdir / "eplusout.err"
    command = (
        str(exe),
        "-w",
        str(Path(experiment["epw_path"]).resolve()),
        "-d",
        str(workdir),
        str(idf_path),
    )
    proc = subprocess.run(
        command,
        cwd=str(workdir),
        capture_output=True,
        text=True,
        check=False,
    )
    stdout_path.write_text(proc.stdout, encoding="utf-8")
    stderr_path.write_text(proc.stderr, encoding="utf-8")
    if proc.returncode != 0:
        raise RuntimeError(
            f"[energyplus_teacher] Teacher experiment failed with return code {proc.returncode}. "
            f"See {stdout_path} and {stderr_path}."
        )
    if not err_path.exists():
        raise RuntimeError(f"[energyplus_teacher] Expected EnergyPlus error file missing: {err_path}")
    err_text = err_path.read_text(encoding="utf-8", errors="ignore")
    if "**  Fatal  **" in err_text or "** Severe  **" in err_text:
        raise RuntimeError(
            f"[energyplus_teacher] EnergyPlus teacher experiment reported severe/fatal errors in {err_path}."
        )

    sql_path = workdir / "eplusout.sql"
    if not sql_path.exists():
        raise RuntimeError(f"[energyplus_teacher] Expected EnergyPlus SQLite output missing: {sql_path}")

    hourly = _extract_hourly_outputs(sql_path, control_mode=str(experiment["control_mode"]))
    reference_gfa = float(geometry["reference_gfa_m2"])
    represented_gfa = float(cohort["represented_gfa_m2"])
    scale_to_cohort = represented_gfa / reference_gfa
    hourly = hourly.rename(
        columns={
            "Zone Mean Air Temperature": "zone_mean_air_temperature_c",
            "Zone Ideal Loads Zone Total Heating Rate": "zone_total_heating_rate_w",
            "Zone Ideal Loads Zone Total Cooling Rate": "zone_total_cooling_rate_w",
            "Site Outdoor Air Drybulb Temperature": "site_outdoor_air_drybulb_c",
            "Enclosure Windows Total Transmitted Solar Radiation Rate": "zone_windows_transmitted_solar_rate_w",
            "Zone Windows Total Heat Gain Rate": "zone_windows_total_heat_gain_rate_w",
            "Zone Windows Total Heat Loss Rate": "zone_windows_total_heat_loss_rate_w",
            "Zone Infiltration Sensible Heat Loss Energy": "zone_infiltration_sensible_heat_loss_energy_j",
            "Zone Infiltration Sensible Heat Gain Energy": "zone_infiltration_sensible_heat_gain_energy_j",
            "Zone Ventilation Sensible Heat Loss Energy": "zone_ventilation_sensible_heat_loss_energy_j",
            "Zone Ventilation Sensible Heat Gain Energy": "zone_ventilation_sensible_heat_gain_energy_j",
            "Zone Air Heat Balance Outdoor Air Transfer Rate": "zone_air_heat_balance_outdoor_air_transfer_rate_w",
            "Zone Ideal Loads Outdoor Air Sensible Heating Rate": "zone_ideal_loads_outdoor_air_sensible_heating_rate_w",
            "Zone Ideal Loads Outdoor Air Sensible Cooling Rate": "zone_ideal_loads_outdoor_air_sensible_cooling_rate_w",
        }
    )
    hourly["zone_total_heating_kwh"] = hourly["zone_total_heating_rate_w"] / 1000.0
    hourly["zone_total_cooling_kwh"] = hourly["zone_total_cooling_rate_w"] / 1000.0
    hourly["zone_windows_transmitted_solar_kwh"] = hourly["zone_windows_transmitted_solar_rate_w"] / 1000.0
    hourly["zone_windows_total_heat_gain_kwh"] = hourly["zone_windows_total_heat_gain_rate_w"] / 1000.0
    hourly["zone_windows_total_heat_loss_kwh"] = hourly["zone_windows_total_heat_loss_rate_w"] / 1000.0
    hourly["zone_infiltration_sensible_heat_loss_kwh"] = hourly["zone_infiltration_sensible_heat_loss_energy_j"] / 3_600_000.0
    hourly["zone_infiltration_sensible_heat_gain_kwh"] = hourly["zone_infiltration_sensible_heat_gain_energy_j"] / 3_600_000.0
    hourly["zone_ventilation_sensible_heat_loss_kwh"] = hourly["zone_ventilation_sensible_heat_loss_energy_j"] / 3_600_000.0
    hourly["zone_ventilation_sensible_heat_gain_kwh"] = hourly["zone_ventilation_sensible_heat_gain_energy_j"] / 3_600_000.0
    hourly["zone_air_heat_balance_outdoor_air_loss_kwh"] = (
        (-hourly["zone_air_heat_balance_outdoor_air_transfer_rate_w"]).clip(lower=0.0) / 1000.0
    )
    hourly["zone_air_heat_balance_outdoor_air_gain_kwh"] = (
        hourly["zone_air_heat_balance_outdoor_air_transfer_rate_w"].clip(lower=0.0) / 1000.0
    )
    hourly["zone_ideal_loads_outdoor_air_sensible_heating_kwh"] = (
        hourly["zone_ideal_loads_outdoor_air_sensible_heating_rate_w"] / 1000.0
    )
    hourly["zone_ideal_loads_outdoor_air_sensible_cooling_kwh"] = (
        hourly["zone_ideal_loads_outdoor_air_sensible_cooling_rate_w"] / 1000.0
    )
    hourly["heating_kwh_per_reference_gfa_m2"] = hourly["zone_total_heating_kwh"] / reference_gfa
    hourly["cooling_kwh_per_reference_gfa_m2"] = hourly["zone_total_cooling_kwh"] / reference_gfa
    hourly["zone_total_heating_rate_w_scaled_to_cohort"] = hourly["zone_total_heating_rate_w"] * scale_to_cohort
    hourly["zone_total_cooling_rate_w_scaled_to_cohort"] = hourly["zone_total_cooling_rate_w"] * scale_to_cohort

    hourly_csv_path = workdir / str(cfg.teacher_hourly_filename)
    hourly.to_csv(hourly_csv_path, index=False, encoding="utf-8")

    plausibility_hourly, plausibility_summary = _build_plausibility_export(
        hourly=hourly,
        schedule_df=schedule_export,
        experiment=experiment,
        geometry=geometry,
        cohort=cohort,
        explicit_dh_connected_share=dh_connected_share,
    )
    plausibility_hourly_csv_path = workdir / str(cfg.teacher_plausibility_hourly_filename)
    plausibility_hourly.to_csv(plausibility_hourly_csv_path, index=False, encoding="utf-8")
    plausibility_summary_path = workdir / str(cfg.teacher_plausibility_summary_filename)
    plausibility_summary_path.write_text(json.dumps(plausibility_summary, indent=2), encoding="utf-8")
    plausibility_plot_path = workdir / str(cfg.teacher_plausibility_plot_filename)
    _save_plausibility_plot(plausibility_hourly, out_path=plausibility_plot_path)

    meta = {
        "teacher": "energyplus",
        "cohort_id": resolved_cohort_id,
        "experiment_id": resolved_experiment_id,
        "epw_path": str(Path(experiment["epw_path"]).resolve()),
        "dh_connected_share_argument": dh_connected_share,
        "idf_path": str(idf_path),
        "schedule_csv_path": str(schedule_csv_path),
        "hourly_csv_path": str(hourly_csv_path),
        "plausibility_hourly_csv_path": str(plausibility_hourly_csv_path),
        "plausibility_summary_path": str(plausibility_summary_path),
        "plausibility_plot_path": str(plausibility_plot_path),
        "command": list(command),
        "stdout_path": str(stdout_path),
        "stderr_path": str(stderr_path),
        "err_path": str(err_path),
        "energyplus_executable": str(exe),
        "control_mode": str(experiment["control_mode"]),
        "teacher_reference_gfa_m2": reference_gfa,
        "cohort_represented_gfa_m2": represented_gfa,
        "scale_to_cohort": scale_to_cohort,
        "geometry": geometry,
        "plausibility_summary": plausibility_summary,
    }
    meta_path = workdir / str(cfg.teacher_meta_filename)
    meta_path.write_text(json.dumps(meta, indent=2), encoding="utf-8")

    return TeacherExperimentResult(
        teacher="energyplus",
        cohort_id=resolved_cohort_id,
        experiment_id=resolved_experiment_id,
        epw_path=Path(experiment["epw_path"]).resolve(),
        workdir=workdir,
        command=command,
        stdout_path=stdout_path,
        stderr_path=stderr_path,
        err_path=err_path,
        hourly_csv_path=hourly_csv_path,
        meta_path=meta_path,
        plausibility_hourly_csv_path=plausibility_hourly_csv_path,
        plausibility_summary_path=plausibility_summary_path,
        plausibility_plot_path=plausibility_plot_path,
    )


def _build_minimal_smoke_idf(idf_path: Path, *, version: str, calendar_year: int) -> None:
    start_weekday = pd.Timestamp(year=calendar_year, month=1, day=1).strftime("%A")
    content = f"""Version,{version};

Building,
  ViennaMiniSmoke,           !- Name
  0.0,                       !- North Axis {{deg}}
  Suburbs,                   !- Terrain
  0.04,                      !- Loads Convergence Tolerance Value
  0.4,                       !- Temperature Convergence Tolerance Value {{deltaC}}
  FullInteriorAndExterior,   !- Solar Distribution
  25,                        !- Maximum Number of Warmup Days
  6;                         !- Minimum Number of Warmup Days

Timestep,1;

SimulationControl,
  No,                        !- Do Zone Sizing Calculation
  No,                        !- Do System Sizing Calculation
  No,                        !- Do Plant Sizing Calculation
  Yes,                       !- Run Simulation for Sizing Periods
  Yes;                       !- Run Simulation for Weather File Run Periods

RunPeriod,
  CalendarYear,              !- Name
  1,                         !- Begin Month
  1,                         !- Begin Day of Month
  {calendar_year},           !- Begin Year
  12,                        !- End Month
  31,                        !- End Day of Month
  {calendar_year},           !- End Year
  {start_weekday},           !- Day of Week for Start Day
  Yes,                       !- Use Weather File Holidays and Special Days
  Yes,                       !- Use Weather File Daylight Saving Period
  No,                        !- Apply Weekend Holiday Rule
  Yes,                       !- Use Weather File Rain Indicators
  Yes;                       !- Use Weather File Snow Indicators

GlobalGeometryRules,
  UpperLeftCorner,
  CounterClockWise,
  World;

Material,
  WallMaterial,
  Rough,
  0.20,
  0.80,
  2200,
  1000;

Material,
  RoofMaterial,
  Rough,
  0.25,
  0.80,
  2200,
  1000;

Material,
  FloorMaterial,
  Rough,
  0.25,
  1.40,
  2200,
  1000;

Construction,
  WallConstruction,
  WallMaterial;

Construction,
  RoofConstruction,
  RoofMaterial;

Construction,
  FloorConstruction,
  FloorMaterial;

Zone,
  Zone1;

BuildingSurface:Detailed,
  Floor,                     !- Name
  Floor,                     !- Surface Type
  FloorConstruction,         !- Construction Name
  Zone1,                     !- Zone Name
  ,                          !- Space Name
  Ground,                    !- Outside Boundary Condition
  ,                          !- Outside Boundary Condition Object
  NoSun,                     !- Sun Exposure
  NoWind,                    !- Wind Exposure
  0.0,                       !- View Factor to Ground
  4,                         !- Number of Vertices
  0,0,0,
  10,0,0,
  10,10,0,
  0,10,0;

BuildingSurface:Detailed,
  Roof,
  Roof,
  RoofConstruction,
  Zone1,
  ,
  Outdoors,
  ,
  SunExposed,
  WindExposed,
  0.0,
  4,
  0,0,3,
  0,10,3,
  10,10,3,
  10,0,3;

BuildingSurface:Detailed,
  WallSouth,
  Wall,
  WallConstruction,
  Zone1,
  ,
  Outdoors,
  ,
  SunExposed,
  WindExposed,
  0.5,
  4,
  0,0,3,
  10,0,3,
  10,0,0,
  0,0,0;

BuildingSurface:Detailed,
  WallEast,
  Wall,
  WallConstruction,
  Zone1,
  ,
  Outdoors,
  ,
  SunExposed,
  WindExposed,
  0.5,
  4,
  10,0,3,
  10,10,3,
  10,10,0,
  10,0,0;

BuildingSurface:Detailed,
  WallNorth,
  Wall,
  WallConstruction,
  Zone1,
  ,
  Outdoors,
  ,
  SunExposed,
  WindExposed,
  0.5,
  4,
  10,10,3,
  0,10,3,
  0,10,0,
  10,10,0;

BuildingSurface:Detailed,
  WallWest,
  Wall,
  WallConstruction,
  Zone1,
  ,
  Outdoors,
  ,
  SunExposed,
  WindExposed,
  0.5,
  4,
  0,10,3,
  0,0,3,
  0,0,0,
  0,10,0;

Output:Variable,
  Zone1,
  Zone Mean Air Temperature,
  Hourly;

Output:SQLite,
  SimpleAndTabular;
"""
    idf_path.write_text(content, encoding="utf-8")


def run_energyplus_mini_smoke(role: str | None = None) -> TeacherSmokeResult:
    cfg = make_building_calibration_config()
    smoke_role = role or cfg.energyplus_smoke_role
    epw_path = _load_pseudo_epw(smoke_role)
    exe = _discover_energyplus(cfg.energyplus_executable_path)

    workdir = Path(cfg.energyplus_smoke_output_dir).resolve() / smoke_role
    if workdir.exists():
        shutil.rmtree(workdir)
    workdir.mkdir(parents=True, exist_ok=False)

    idf_path = workdir / "mini_smoke.idf"
    weather_year = int(epw_path.stem.rsplit("_", 1)[-1])
    _build_minimal_smoke_idf(idf_path, version=str(cfg.energyplus_idf_version), calendar_year=weather_year)

    stdout_path = workdir / "stdout.txt"
    stderr_path = workdir / "stderr.txt"
    err_path = workdir / "eplusout.err"
    command = (
        str(exe),
        "-w",
        str(epw_path),
        "-d",
        str(workdir),
        str(idf_path),
    )
    proc = subprocess.run(
        command,
        cwd=str(workdir),
        capture_output=True,
        text=True,
        check=False,
    )
    stdout_path.write_text(proc.stdout, encoding="utf-8")
    stderr_path.write_text(proc.stderr, encoding="utf-8")

    if proc.returncode != 0:
        raise RuntimeError(
            f"[energyplus_teacher] EnergyPlus mini smoke failed with return code {proc.returncode}. "
            f"See {stdout_path} and {stderr_path}."
        )
    if not err_path.exists():
        raise RuntimeError(f"[energyplus_teacher] Expected EnergyPlus error file missing: {err_path}")

    err_text = err_path.read_text(encoding="utf-8", errors="ignore")
    if "**  Fatal  **" in err_text or "** Severe  **" in err_text:
        raise RuntimeError(f"[energyplus_teacher] EnergyPlus mini smoke reported severe/fatal errors in {err_path}.")

    meta = {
        "teacher": "energyplus",
        "role": smoke_role,
        "epw_path": str(epw_path),
        "idf_path": str(idf_path),
        "command": list(command),
        "stdout_path": str(stdout_path),
        "stderr_path": str(stderr_path),
        "err_path": str(err_path),
        "energyplus_executable": str(exe),
    }
    (workdir / "smoke.meta.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")

    return TeacherSmokeResult(
        teacher="energyplus",
        epw_path=epw_path,
        workdir=workdir,
        command=command,
        stdout_path=stdout_path,
        stderr_path=stderr_path,
        err_path=err_path,
    )
