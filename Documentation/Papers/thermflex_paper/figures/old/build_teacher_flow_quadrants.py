from __future__ import annotations

"""Build paper-facing teacher flow comparison figures for all eight archetypes."""

import json
from pathlib import Path

import matplotlib
import pandas as pd

matplotlib.use("Agg", force=True)
import matplotlib.dates as mdates
import matplotlib.pyplot as plt


# This builder lives directly in the paper figure layer because it does not
# create a general model-analysis artifact. It creates a manuscript-facing
# comparison from already existing EnergyPlus teacher outputs.
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

COHORT_ORDER = (
    "residential_pre1975",
    "residential_1975_1990",
    "residential_1990_2000",
    "residential_2000_2014",
    "non_residential_pre1975",
    "non_residential_1975_1990",
    "non_residential_1990_2000",
    "non_residential_2000_2014",
)

COHORT_COLORS = {
    "residential_pre1975": "#8c2d04",
    "residential_1975_1990": "#cc4c02",
    "residential_1990_2000": "#ec7014",
    "residential_2000_2014": "#fe9929",
    "non_residential_pre1975": "#08519c",
    "non_residential_1975_1990": "#3182bd",
    "non_residential_1990_2000": "#6baed6",
    "non_residential_2000_2014": "#9ecae1",
}

EXPERIMENT_TO_FILENAME = {
    "winter_reference_week": "fig_00_teacher_flow_quadrant_winter_reference_week.png",
    "winter_cutback_event": "fig_00_teacher_flow_quadrant_winter_cutback_event.png",
}


def build_teacher_flow_quadrants() -> list[Path]:
    """Build one 2x2 flow comparison figure per active teacher experiment."""

    experiment_library = _load_experiment_library()
    built_paths: list[Path] = []
    for experiment_id, filename in EXPERIMENT_TO_FILENAME.items():
        built_paths.append(
            _build_single_experiment_figure(
                experiment_id=experiment_id,
                experiment=experiment_library[experiment_id],
                out_path=Path(__file__).resolve().parent / filename,
            )
        )
    return built_paths


def _load_experiment_library() -> dict[str, dict[str, object]]:
    """Load the experiment contract and fail hard if it is missing."""

    if not EXPERIMENT_LIBRARY_PATH.exists():
        raise FileNotFoundError(
            f"[teacher_flow_quadrants] Missing experiment library: {EXPERIMENT_LIBRARY_PATH}"
        )
    experiment_library = json.loads(EXPERIMENT_LIBRARY_PATH.read_text(encoding="utf-8"))
    experiments = experiment_library.get("experiments")
    if experiments is None:
        raise KeyError(
            "[teacher_flow_quadrants] Experiment library does not contain 'experiments'."
        )
    return {str(item["experiment_id"]): dict(item) for item in experiments}


def _build_single_experiment_figure(
    *,
    experiment_id: str,
    experiment: dict[str, object],
    out_path: Path,
) -> Path:
    """Create a 2x2 flow figure for one experiment across all eight archetypes."""

    series_by_cohort: dict[str, pd.DataFrame] = {}
    event_window: tuple[pd.Timestamp, pd.Timestamp] | None = None

    for cohort_id in COHORT_ORDER:
        csv_path = (
            TEACHER_RUNS_ROOT
            / cohort_id
            / experiment_id
            / "teacher_plausibility_hourly.csv"
        )
        if not csv_path.exists():
            raise FileNotFoundError(
                f"[teacher_flow_quadrants] Missing teacher csv: {csv_path}"
            )
        hourly = pd.read_csv(csv_path)
        day_df, current_event_window = _select_plot_day(df=hourly, experiment=experiment)
        series_by_cohort[cohort_id] = day_df
        if event_window is None:
            event_window = current_event_window

    first_df = series_by_cohort[COHORT_ORDER[0]]
    time = pd.DatetimeIndex(first_df["timestamp_local"])

    fig, axes = plt.subplots(2, 2, figsize=(18, 11), sharex=True)
    axes = axes.flatten()

    # Panel 1: indoor temperature. Outdoor temperature is added as a single
    # black dashed reference because the weather path is shared across cohorts.
    axes[0].plot(
        time,
        first_df["site_outdoor_air_drybulb_c"].to_numpy(dtype=float),
        color="#111827",
        linewidth=1.7,
        linestyle="--",
        label="Outdoor temperature",
    )
    for cohort_id in COHORT_ORDER:
        df = series_by_cohort[cohort_id]
        axes[0].plot(
            time,
            df["zone_mean_air_temperature_c"].to_numpy(dtype=float),
            color=COHORT_COLORS[cohort_id],
            linewidth=2.0,
            label=_format_cohort_label(cohort_id),
        )
    axes[0].set_title("Indoor temperature")
    axes[0].set_ylabel("Temperature [C]")

    # Panel 2: heating demand / supplied heating rate from the teacher.
    for cohort_id in COHORT_ORDER:
        df = series_by_cohort[cohort_id]
        axes[1].plot(
            time,
            df["zone_total_heating_rate_w"].to_numpy(dtype=float) / 1000.0,
            color=COHORT_COLORS[cohort_id],
            linewidth=2.0,
        )
    axes[1].set_title("Heating")
    axes[1].set_ylabel("Heating rate [kW]")

    # Panel 3: transmitted solar gains through the windows.
    for cohort_id in COHORT_ORDER:
        df = series_by_cohort[cohort_id]
        axes[2].plot(
            time,
            df["zone_windows_transmitted_solar_rate_w"].to_numpy(dtype=float) / 1000.0,
            color=COHORT_COLORS[cohort_id],
            linewidth=2.0,
        )
    axes[2].set_title("Window solar gains")
    axes[2].set_ylabel("Solar gain [kW]")

    # Panel 4: total losses. This is intentionally aggregated to keep the plot
    # readable. Transmission, ventilation, and infiltration remain separately
    # available in the teacher CSVs and can be broken out later if needed.
    for cohort_id in COHORT_ORDER:
        df = series_by_cohort[cohort_id]
        total_loss_kw = (
            df["approx_transmission_loss_seed_ua_w"].to_numpy(dtype=float)
            + df["approx_ventilation_loss_w"].to_numpy(dtype=float)
            + df["approx_infiltration_loss_w"].to_numpy(dtype=float)
        ) / 1000.0
        axes[3].plot(
            time,
            total_loss_kw,
            color=COHORT_COLORS[cohort_id],
            linewidth=2.0,
        )
    axes[3].set_title("Total losses")
    axes[3].set_ylabel("Loss proxy [kW]")

    for axis in axes:
        axis.grid(True, alpha=0.25)
        if event_window is not None:
            axis.axvspan(event_window[0], event_window[1], color="#fca5a5", alpha=0.20)
        axis.xaxis.set_major_locator(mdates.HourLocator(interval=3))
        axis.xaxis.set_major_formatter(mdates.DateFormatter("%H:%M"))

    legend_handles = [
        plt.Line2D([0], [0], color="#111827", linewidth=1.7, linestyle="--", label="Outdoor temperature")
    ]
    legend_handles.extend(
        [
            plt.Line2D(
                [0],
                [0],
                color=COHORT_COLORS[cohort_id],
                linewidth=2.0,
                label=_format_cohort_label(cohort_id),
            )
            for cohort_id in COHORT_ORDER
        ]
    )
    fig.legend(
        handles=legend_handles,
        loc="lower center",
        ncol=3,
        frameon=False,
        bbox_to_anchor=(0.5, -0.02),
    )

    plot_day = time[0].strftime("%Y-%m-%d")
    fig.suptitle(
        f"EnergyPlus teacher flow comparison | {experiment_id} | plot day {plot_day}",
        fontsize=16,
        y=0.98,
    )
    fig.tight_layout(rect=(0.0, 0.05, 1.0, 0.95))
    fig.savefig(out_path, dpi=180, bbox_inches="tight")
    plt.close(fig)
    return out_path


def _select_plot_day(
    *,
    df: pd.DataFrame,
    experiment: dict[str, object],
) -> tuple[pd.DataFrame, tuple[pd.Timestamp, pd.Timestamp] | None]:
    """Select the exact 24h plot window used elsewhere in the teacher bundle."""

    required = {
        "timestamp_local",
        "site_outdoor_air_drybulb_c",
        "zone_mean_air_temperature_c",
        "zone_total_heating_rate_w",
        "zone_windows_transmitted_solar_rate_w",
        "approx_transmission_loss_seed_ua_w",
        "approx_ventilation_loss_w",
        "approx_infiltration_loss_w",
    }
    missing = sorted(required - set(df.columns))
    if missing:
        raise KeyError(
            f"[teacher_flow_quadrants] Missing required teacher columns: {missing}"
        )

    hourly = df.copy()
    hourly["timestamp_local"] = pd.to_datetime(hourly["timestamp_local"])
    hourly = hourly.sort_values("timestamp_local")

    start_local = pd.Timestamp(str(experiment["start_local"]))
    event_type = str(experiment["event_type"])
    if event_type == "none":
        day_start = start_local
        event_window = None
    else:
        day_start = start_local + pd.Timedelta(hours=int(experiment["event_start_offset_h"]))
        event_window = (
            day_start,
            day_start + pd.Timedelta(hours=int(experiment["event_duration_h"])),
        )

    day_end = day_start + pd.Timedelta(hours=24)
    window = hourly[(hourly["timestamp_local"] >= day_start) & (hourly["timestamp_local"] < day_end)].copy()
    if len(window) != 24:
        raise ValueError(
            "[teacher_flow_quadrants] Expected 24 hourly rows for plot day "
            f"{day_start.date()}, got {len(window)}."
        )
    return window, event_window


def _format_cohort_label(cohort_id: str) -> str:
    """Convert internal cohort ids into compact, readable labels."""

    if cohort_id.startswith("residential_"):
        return "Res " + cohort_id.replace("residential_", "")
    if cohort_id.startswith("non_residential_"):
        return "Non-res " + cohort_id.replace("non_residential_", "")
    return cohort_id


if __name__ == "__main__":
    built = build_teacher_flow_quadrants()
    for path in built:
        print(path)
