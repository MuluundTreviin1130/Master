from __future__ import annotations

"""Build compact cohort/day plots from existing EnergyPlus teacher outputs."""

import json
from pathlib import Path

import matplotlib
import pandas as pd

matplotlib.use("Agg", force=True)
import matplotlib.dates as mdates
import matplotlib.pyplot as plt


PROJECT_ROOT = Path(__file__).resolve().parents[3]
TEACHER_RUNS_ROOT = (
    PROJECT_ROOT
    / "Technical_model"
    / "technologies"
    / "buildings"
    / "calibration"
    / "_teacher_runs"
)
EXPERIMENT_LIBRARY_PATH = (
    PROJECT_ROOT
    / "Data"
    / "profiles"
    / "Vienna"
    / "weather"
    / "calibration_setup"
    / "experiment_library_v1.json"
)
COHORT_IDS = (
    "residential_pre1975",
    "residential_1975_1990",
    "residential_1990_2000",
    "residential_2000_2014",
    "non_residential_pre1975",
    "non_residential_1975_1990",
    "non_residential_1990_2000",
    "non_residential_2000_2014",
)
EXPERIMENT_IDS = (
    "winter_reference_week",
    "winter_cutback_event",
)


def build_energyplus_cohort_day_plots_bundle(output_dir: Path) -> Path:
    output_dir = Path(output_dir).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    if not EXPERIMENT_LIBRARY_PATH.exists():
        raise FileNotFoundError(
            f"[energyplus_day_plots] Experiment library not found: {EXPERIMENT_LIBRARY_PATH}"
        )
    experiment_library = json.loads(EXPERIMENT_LIBRARY_PATH.read_text(encoding="utf-8"))
    experiments = {str(item["experiment_id"]): dict(item) for item in experiment_library.get("experiments", [])}

    summary_rows: list[dict[str, object]] = []
    for cohort_id in COHORT_IDS:
        for experiment_id in EXPERIMENT_IDS:
            if experiment_id not in experiments:
                raise KeyError(
                    f"[energyplus_day_plots] Experiment '{experiment_id}' missing in experiment library."
                )
            csv_path = (
                TEACHER_RUNS_ROOT
                / cohort_id
                / experiment_id
                / "teacher_plausibility_hourly.csv"
            )
            if not csv_path.exists():
                raise FileNotFoundError(
                    f"[energyplus_day_plots] Missing teacher_plausibility_hourly.csv: {csv_path}"
                )
            df = pd.read_csv(csv_path)
            day_df, day_label, event_window = _select_plot_day(
                df=df,
                experiment=experiments[experiment_id],
            )
            plot_path = output_dir / f"{cohort_id}_{experiment_id}_{day_label}.png"
            _save_plot(
                cohort_id=cohort_id,
                experiment_id=experiment_id,
                df=day_df,
                event_window=event_window,
                out_path=plot_path,
            )
            summary_rows.append(
                {
                    "cohort_id": cohort_id,
                    "experiment_id": experiment_id,
                    "plot_day": day_label,
                    "event_window_start": str(event_window[0]) if event_window is not None else None,
                    "event_window_end": str(event_window[1]) if event_window is not None else None,
                    "mean_zone_air_temperature_c": float(day_df["zone_mean_air_temperature_c"].mean()),
                    "min_zone_air_temperature_c": float(day_df["zone_mean_air_temperature_c"].min()),
                    "max_zone_air_temperature_c": float(day_df["zone_mean_air_temperature_c"].max()),
                    "heating_kwh_total": float(day_df["zone_total_heating_kwh"].sum()),
                    "internal_gains_kwh_total": float((day_df["internal_gains_total_w"] / 1000.0).sum()),
                    "window_solar_transmitted_kwh_total": float(day_df["window_solar_transmitted_kwh"].sum()),
                    "transmission_loss_kwh_total": float((day_df["approx_transmission_loss_seed_ua_w"] / 1000.0).sum()),
                    "ventilation_loss_kwh_total": float((day_df["approx_ventilation_loss_w"] / 1000.0).sum()),
                    "infiltration_loss_kwh_total": float((day_df["approx_infiltration_loss_w"] / 1000.0).sum()),
                    "plot_path": str(plot_path),
                }
            )

    summary_df = pd.DataFrame(summary_rows)
    summary_df.to_csv(output_dir / "teacher_day_plot_summary.csv", index=False)
    (output_dir / "teacher_day_plot_summary.json").write_text(
        json.dumps(summary_rows, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    return output_dir


def _select_plot_day(
    *,
    df: pd.DataFrame,
    experiment: dict[str, object],
) -> tuple[pd.DataFrame, str, tuple[pd.Timestamp, pd.Timestamp] | None]:
    required = {
        "timestamp_local",
        "zone_mean_air_temperature_c",
        "site_outdoor_air_drybulb_c",
        "zone_total_heating_rate_w",
        "zone_total_heating_kwh",
        "internal_gains_total_w",
        "zone_windows_transmitted_solar_rate_w",
        "window_solar_transmitted_kwh",
        "approx_transmission_loss_seed_ua_w",
        "approx_infiltration_loss_w",
        "approx_ventilation_loss_w",
        "heating_setpoint_c",
        "cooling_setpoint_c",
    }
    missing = sorted(required - set(df.columns))
    if missing:
        raise KeyError(
            f"[energyplus_day_plots] Missing required columns in teacher_plausibility_hourly.csv: {missing}"
        )
    hourly = df.copy()
    hourly["timestamp_local"] = pd.to_datetime(hourly["timestamp_local"])
    hourly = hourly.sort_values("timestamp_local")

    start_local = pd.Timestamp(str(experiment["start_local"]))
    event_type = str(experiment["event_type"])
    if event_type == "none":
        day_start = start_local
        day_end = day_start + pd.Timedelta(hours=24)
        event_window = None
    else:
        day_start = start_local + pd.Timedelta(hours=int(experiment["event_start_offset_h"]))
        day_end = day_start + pd.Timedelta(hours=24)
        event_window = (
            day_start,
            day_start + pd.Timedelta(hours=int(experiment["event_duration_h"])),
        )

    window = hourly[(hourly["timestamp_local"] >= day_start) & (hourly["timestamp_local"] < day_end)].copy()
    if len(window) != 24:
        raise ValueError(
            f"[energyplus_day_plots] Expected exactly 24 hourly rows for plot day {day_start.date()}, got {len(window)}."
        )
    return window, day_start.strftime("%Y%m%d"), event_window


def _save_plot(
    *,
    cohort_id: str,
    experiment_id: str,
    df: pd.DataFrame,
    event_window: tuple[pd.Timestamp, pd.Timestamp] | None,
    out_path: Path,
) -> None:
    time = pd.DatetimeIndex(df["timestamp_local"])
    window_loss_kw = df.get("window_heat_loss_kwh", pd.Series([0.0] * len(df))).to_numpy(dtype=float)

    fig, axes = plt.subplots(3, 1, figsize=(14, 10), sharex=True)

    axes[0].plot(time, df["zone_mean_air_temperature_c"], label="Indoor T", color="#dc2626", linewidth=2.0)
    axes[0].plot(time, df["site_outdoor_air_drybulb_c"], label="Outdoor T", color="#2563eb", linewidth=1.6)
    axes[0].plot(time, df["heating_setpoint_c"], label="Heating setpoint", color="#111827", linestyle="--", linewidth=1.2)
    axes[0].plot(time, df["cooling_setpoint_c"], label="Cooling setpoint", color="#6b7280", linestyle=":", linewidth=1.1)
    axes[0].set_ylabel("Temperature [C]")
    axes[0].set_title(f"{cohort_id} | {experiment_id}")
    axes[0].grid(True, alpha=0.25)
    axes[0].legend(loc="upper left", ncol=4)

    axes[1].plot(time, df["zone_total_heating_rate_w"] / 1000.0, label="Heating", color="#b45309", linewidth=2.0)
    axes[1].plot(time, df["internal_gains_total_w"] / 1000.0, label="Internal gains", color="#059669", linewidth=1.6)
    axes[1].plot(time, df["zone_windows_transmitted_solar_rate_w"] / 1000.0, label="Solar gains", color="#f59e0b", linewidth=1.6)
    axes[1].set_ylabel("Gain / heating rate [kW]")
    axes[1].grid(True, alpha=0.25)
    axes[1].legend(loc="upper left", ncol=3)

    axes[2].plot(time, df["approx_transmission_loss_seed_ua_w"] / 1000.0, label="Transmission loss", color="#7c2d12", linewidth=1.6)
    axes[2].plot(time, df["approx_infiltration_loss_w"] / 1000.0, label="Infiltration loss", color="#1d4ed8", linewidth=1.4)
    axes[2].plot(time, df["approx_ventilation_loss_w"] / 1000.0, label="Ventilation loss", color="#0f766e", linewidth=1.4)
    axes[2].plot(time, window_loss_kw, label="Window loss", color="#6b7280", linewidth=1.2)
    axes[2].set_ylabel("Loss proxy [kW]")
    axes[2].grid(True, alpha=0.25)
    axes[2].legend(loc="upper left", ncol=4)

    if event_window is not None:
        for ax in axes:
            ax.axvspan(event_window[0], event_window[1], color="#fca5a5", alpha=0.22)

    axes[2].xaxis.set_major_locator(mdates.HourLocator(interval=3))
    axes[2].xaxis.set_major_formatter(mdates.DateFormatter("%H:%M"))
    fig.tight_layout()
    fig.savefig(out_path, dpi=180, bbox_inches="tight")
    plt.close(fig)
