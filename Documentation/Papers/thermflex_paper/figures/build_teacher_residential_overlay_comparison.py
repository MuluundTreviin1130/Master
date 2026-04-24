from __future__ import annotations

"""Build a compact overlay comparison for the four residential archetype periods."""

import json
from pathlib import Path

import matplotlib
import pandas as pd

matplotlib.use("Agg", force=True)
import matplotlib.dates as mdates
import matplotlib.pyplot as plt


PROJECT_ROOT = Path(__file__).resolve().parents[4]
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
OUTPUT_PATH = (
    Path(__file__).resolve().parent
    / "fig_00_teacher_residential_overlay_comparison.png"
)

PRIMARY_EXPERIMENT_ID = "repday_winter_typical_day"
PRIMARY_EXPERIMENT_TITLE = "Winter typical day"

RESIDENTIAL_COHORT_ORDER = (
    "residential_pre1975",
    "residential_1975_1990",
    "residential_1990_2000",
    "residential_2000_2014",
)

COHORT_COLORS = {
    "residential_pre1975": "#8c2d04",
    "residential_1975_1990": "#cc4c02",
    "residential_1990_2000": "#ec7014",
    "residential_2000_2014": "#fe9929",
}


def build_teacher_residential_overlay_comparison() -> Path:
    experiments = _load_experiment_library()
    experiment = experiments[PRIMARY_EXPERIMENT_ID]
    series_by_cohort: dict[str, pd.DataFrame] = {}

    for cohort_id in RESIDENTIAL_COHORT_ORDER:
        csv_path = (
            TEACHER_RUNS_ROOT
            / cohort_id
            / PRIMARY_EXPERIMENT_ID
            / "teacher_plausibility_hourly.csv"
        )
        if not csv_path.exists():
            raise FileNotFoundError(
                f"[teacher_residential_overlay] Missing teacher csv: {csv_path}"
            )
        hourly = pd.read_csv(csv_path)
        series_by_cohort[cohort_id] = _select_plot_day(df=hourly, experiment=experiment)

    time = pd.DatetimeIndex(series_by_cohort[RESIDENTIAL_COHORT_ORDER[0]]["timestamp_local"])
    fig, axes = plt.subplots(2, 1, figsize=(14, 9), sharex=True)
    gain_ax, loss_ax = axes

    for cohort_id in RESIDENTIAL_COHORT_ORDER:
        df = series_by_cohort[cohort_id]
        total_gains_kw = (
            df["internal_gains_total_w"].to_numpy(dtype=float)
            + df["zone_windows_transmitted_solar_rate_w"].to_numpy(dtype=float)
        ) / 1000.0
        total_losses_kw = (
            df["approx_transmission_loss_seed_ua_w"].to_numpy(dtype=float)
            + df["approx_ventilation_loss_w"].to_numpy(dtype=float)
            + df["approx_infiltration_loss_w"].to_numpy(dtype=float)
        ) / 1000.0

        gain_ax.plot(
            time,
            df["zone_total_heating_rate_w"].to_numpy(dtype=float) / 1000.0,
            color=COHORT_COLORS[cohort_id],
            linewidth=2.2,
            label=f"{_format_label(cohort_id)} heating",
        )
        gain_ax.plot(
            time,
            total_gains_kw,
            color=COHORT_COLORS[cohort_id],
            linewidth=1.8,
            linestyle="--",
            label=f"{_format_label(cohort_id)} total gains",
        )
        loss_ax.plot(
            time,
            total_losses_kw,
            color=COHORT_COLORS[cohort_id],
            linewidth=2.2,
            label=_format_label(cohort_id),
        )

    gain_ax.set_title("Heating and total gains")
    gain_ax.set_ylabel("kW")
    gain_ax.grid(True, alpha=0.25)
    gain_ax.legend(loc="upper left", ncol=2, fontsize=8, frameon=False)

    loss_ax.set_title("Total losses")
    loss_ax.set_ylabel("kW")
    loss_ax.grid(True, alpha=0.25)
    loss_ax.legend(loc="upper left", ncol=2, fontsize=8, frameon=False)
    loss_ax.xaxis.set_major_locator(mdates.HourLocator(interval=3))
    loss_ax.xaxis.set_major_formatter(mdates.DateFormatter("%H:%M"))

    plot_day = time[0].strftime("%Y-%m-%d")
    fig.suptitle(
        f"EnergyPlus teacher residential overlay comparison | {PRIMARY_EXPERIMENT_TITLE} | plot day {plot_day}",
        fontsize=16,
        y=0.98,
    )
    fig.tight_layout(rect=(0.0, 0.02, 1.0, 0.96))
    fig.savefig(OUTPUT_PATH, dpi=180, bbox_inches="tight")
    plt.close(fig)
    return OUTPUT_PATH


def _load_experiment_library() -> dict[str, dict[str, object]]:
    if not EXPERIMENT_LIBRARY_PATH.exists():
        raise FileNotFoundError(
            f"[teacher_residential_overlay] Missing experiment library: {EXPERIMENT_LIBRARY_PATH}"
        )
    payload = json.loads(EXPERIMENT_LIBRARY_PATH.read_text(encoding="utf-8"))
    experiments = payload.get("experiments")
    if experiments is None:
        raise KeyError("[teacher_residential_overlay] Experiment library does not contain 'experiments'.")
    return {str(item["experiment_id"]): dict(item) for item in experiments}


def _select_plot_day(*, df: pd.DataFrame, experiment: dict[str, object]) -> pd.DataFrame:
    required = {
        "timestamp_local",
        "zone_total_heating_rate_w",
        "internal_gains_total_w",
        "zone_windows_transmitted_solar_rate_w",
        "approx_transmission_loss_seed_ua_w",
        "approx_ventilation_loss_w",
        "approx_infiltration_loss_w",
    }
    missing = sorted(required - set(df.columns))
    if missing:
        raise KeyError(f"[teacher_residential_overlay] Missing required teacher columns: {missing}")
    hourly = df.copy()
    hourly["timestamp_local"] = pd.to_datetime(hourly["timestamp_local"])
    hourly = hourly.sort_values("timestamp_local")
    day_start = pd.Timestamp(str(experiment["start_local"]))
    day_end = day_start + pd.Timedelta(hours=24)
    window = hourly[(hourly["timestamp_local"] >= day_start) & (hourly["timestamp_local"] < day_end)].copy()
    if len(window) != 24:
        raise ValueError(
            f"[teacher_residential_overlay] Expected 24 hourly rows for {day_start.date()}, got {len(window)}."
        )
    return window


def _format_label(cohort_id: str) -> str:
    return cohort_id.replace("residential_", "").replace("_", " | ")


if __name__ == "__main__":
    print(build_teacher_residential_overlay_comparison())
