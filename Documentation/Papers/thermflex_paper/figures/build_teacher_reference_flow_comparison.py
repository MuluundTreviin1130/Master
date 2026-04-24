from __future__ import annotations

"""Build a compact residential teacher archetype grid for one representative day."""

import json
from pathlib import Path

import matplotlib
import pandas as pd
import numpy as np

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
OUTPUT_PATH = Path(__file__).resolve().parent / "fig_00_teacher_reference_flow_comparison.png"
LEGEND_OUTPUT_PATH = (
    Path(__file__).resolve().parent / "fig_00_teacher_reference_flow_comparison_legend.png"
)

# Use one cold winter baseline slice from the existing teacher library. The
# former one-day repday cuts became too mild or too solar-dominated, which made
# the midday heating rate collapse unrealistically for a load-oriented paper
# reading. We therefore keep the existing 96 h cold-year baseline experiment but
# visualize only its last 24 h, where the day stays cold while solar suppression
# is much less extreme.
PRIMARY_EXPERIMENT_ID = "winter_event_reference_96h"
PRIMARY_EXPERIMENT_TITLE = "Cold winter baseline day"
PRIMARY_SLICE_START_LOCAL = "2021-01-18T00:00:00"

RESIDENTIAL_COHORT_ORDER = (
    "residential_pre1975",
    "residential_1975_1990",
    "residential_1990_2000",
    "residential_2000_2014",
)

GAINS_COLORS = {
    "heating": "#b45309",
    "internal": "#059669",
    "solar": "#f59e0b",
    "total": "#111827",
}
LOSSES_COLORS = {
    "transmission": "#7c2d12",
    "infiltration": "#1d4ed8",
    "ventilation": "#0f766e",
    "total": "#111827",
}


def build_teacher_reference_flow_comparison() -> Path:
    """Build a 2x2 residential archetype grid with gains/heating and losses."""

    experiment = _load_experiment_library()[PRIMARY_EXPERIMENT_ID]
    series_by_cohort: dict[str, pd.DataFrame] = {}
    reference_area_by_cohort: dict[str, float] = {}
    for cohort_id in RESIDENTIAL_COHORT_ORDER:
        csv_path = (
            TEACHER_RUNS_ROOT
            / cohort_id
            / PRIMARY_EXPERIMENT_ID
            / "teacher_plausibility_hourly.csv"
        )
        if not csv_path.exists():
            raise FileNotFoundError(
                f"[teacher_reference_flow_comparison] Missing teacher csv: {csv_path}"
            )
        meta_path = (
            TEACHER_RUNS_ROOT
            / cohort_id
            / PRIMARY_EXPERIMENT_ID
            / "teacher.meta.json"
        )
        if not meta_path.exists():
            raise FileNotFoundError(
                f"[teacher_reference_flow_comparison] Missing teacher meta json: {meta_path}"
            )
        hourly = pd.read_csv(csv_path)
        series_by_cohort[cohort_id] = _select_plot_day(df=hourly, experiment=experiment)
        reference_area_by_cohort[cohort_id] = _load_reference_conditioned_floor_m2(meta_path)

    # Compute one shared y-range for all gain/heating panels and one shared
    # y-range for all loss panels. The user explicitly wants to see magnitude
    # differences between periods, so per-panel autoscaling would hide the
    # main message by making visually similar shapes look equally large.
    gain_upper_kw = 0.0
    loss_upper_kw = 0.0
    for cohort_id, df in series_by_cohort.items():
        reference_area_m2 = reference_area_by_cohort[cohort_id]
        total_gains_kw = (
            df["internal_gains_total_w"].to_numpy(dtype=float)
            + df["zone_windows_transmitted_solar_rate_w"].to_numpy(dtype=float)
        ) / reference_area_m2
        total_losses_kw = (
            df["approx_transmission_loss_seed_ua_w"].to_numpy(dtype=float)
            + df["approx_ventilation_loss_w"].to_numpy(dtype=float)
            + df["approx_infiltration_loss_w"].to_numpy(dtype=float)
        ) / reference_area_m2
        gain_upper_kw = max(
            gain_upper_kw,
            float(df["zone_total_heating_rate_w"].max()) / reference_area_m2,
            float(df["internal_gains_total_w"].max()) / reference_area_m2,
            float(df["zone_windows_transmitted_solar_rate_w"].max()) / reference_area_m2,
            float(total_gains_kw.max()),
        )
        loss_upper_kw = max(
            loss_upper_kw,
            float(df["approx_transmission_loss_seed_ua_w"].max()) / reference_area_m2,
            float(df["approx_infiltration_loss_w"].max()) / reference_area_m2,
            float(df["approx_ventilation_loss_w"].max()) / reference_area_m2,
            float(total_losses_kw.max()),
        )

    gain_ylim = (0.0, gain_upper_kw * 1.08)
    loss_ylim = (0.0, loss_upper_kw * 1.08)

    fig = plt.figure(figsize=(17, 12))
    subfigs = fig.subfigures(2, 2, wspace=0.03, hspace=0.05)
    first_time = pd.DatetimeIndex(series_by_cohort[RESIDENTIAL_COHORT_ORDER[0]]["timestamp_local"])
    gain_legend_handles = None
    gain_legend_labels = None
    loss_legend_handles = None
    loss_legend_labels = None

    for subfig, cohort_id in zip(subfigs.flat, RESIDENTIAL_COHORT_ORDER, strict=True):
        df = series_by_cohort[cohort_id]
        reference_area_m2 = reference_area_by_cohort[cohort_id]
        time = pd.DatetimeIndex(df["timestamp_local"])
        if not time.equals(first_time):
            raise ValueError("[teacher_reference_flow_comparison] Residential teacher windows are misaligned.")

        axes = subfig.subplots(2, 1, sharex=True, height_ratios=[1.0, 1.0])
        gain_ax, loss_ax = axes

        total_gains_kw = (
            df["internal_gains_total_w"].to_numpy(dtype=float)
            + df["zone_windows_transmitted_solar_rate_w"].to_numpy(dtype=float)
        ) / reference_area_m2
        total_losses_kw = (
            df["approx_transmission_loss_seed_ua_w"].to_numpy(dtype=float)
            + df["approx_ventilation_loss_w"].to_numpy(dtype=float)
            + df["approx_infiltration_loss_w"].to_numpy(dtype=float)
        ) / reference_area_m2

        gain_ax.plot(time, df["zone_total_heating_rate_w"].to_numpy(dtype=float) / reference_area_m2, color=GAINS_COLORS["heating"], linewidth=2.0, label="Space-heating rate")
        gain_ax.plot(time, df["internal_gains_total_w"].to_numpy(dtype=float) / reference_area_m2, color=GAINS_COLORS["internal"], linewidth=1.7, label="Internal gains")
        gain_ax.plot(time, df["zone_windows_transmitted_solar_rate_w"].to_numpy(dtype=float) / reference_area_m2, color=GAINS_COLORS["solar"], linewidth=1.7, label="Solar gains")
        gain_ax.plot(time, total_gains_kw, color=GAINS_COLORS["total"], linewidth=1.8, linestyle="--", label="Total gains")
        gain_ax.set_ylabel("Gain / space-heating rate [W/m²]", fontsize=11)
        gain_ax.set_ylim(*gain_ylim)
        gain_ax.grid(True, alpha=0.25)
        gain_ax.tick_params(axis="both", labelsize=10)
        if gain_legend_handles is None:
            gain_legend_handles, gain_legend_labels = gain_ax.get_legend_handles_labels()

        loss_ax.plot(time, df["approx_transmission_loss_seed_ua_w"].to_numpy(dtype=float) / reference_area_m2, color=LOSSES_COLORS["transmission"], linewidth=1.7, label="Transmission loss")
        loss_ax.plot(time, df["approx_infiltration_loss_w"].to_numpy(dtype=float) / reference_area_m2, color=LOSSES_COLORS["infiltration"], linewidth=1.5, label="Infiltration loss")
        loss_ax.plot(time, df["approx_ventilation_loss_w"].to_numpy(dtype=float) / reference_area_m2, color=LOSSES_COLORS["ventilation"], linewidth=1.5, label="Ventilation loss")
        loss_ax.plot(time, total_losses_kw, color=LOSSES_COLORS["total"], linewidth=1.8, linestyle="--", label="Total losses")
        loss_ax.set_ylabel("Loss [W/m²]", fontsize=11)
        loss_ax.set_ylim(*loss_ylim)
        loss_ax.grid(True, alpha=0.25)
        loss_ax.xaxis.set_major_locator(mdates.HourLocator(interval=3))
        loss_ax.xaxis.set_major_formatter(mdates.DateFormatter("%H:%M"))
        loss_ax.tick_params(axis="both", labelsize=10)
        if loss_legend_handles is None:
            loss_legend_handles, loss_legend_labels = loss_ax.get_legend_handles_labels()

        subfig.suptitle(_format_residential_title(cohort_id), fontsize=15, y=0.98)

    if gain_legend_handles is None or loss_legend_handles is None:
        raise RuntimeError("[teacher_reference_flow_comparison] Failed to collect figure legends.")

    fig.savefig(OUTPUT_PATH, dpi=180, bbox_inches="tight")
    plt.close(fig)
    _build_separate_legend_asset(
        gain_legend_handles=gain_legend_handles,
        gain_legend_labels=gain_legend_labels,
        loss_legend_handles=loss_legend_handles,
        loss_legend_labels=loss_legend_labels,
    )
    return OUTPUT_PATH


def _load_experiment_library() -> dict[str, dict[str, object]]:
    if not EXPERIMENT_LIBRARY_PATH.exists():
        raise FileNotFoundError(
            "[teacher_reference_flow_comparison] Missing experiment library: "
            f"{EXPERIMENT_LIBRARY_PATH}"
        )
    payload = json.loads(EXPERIMENT_LIBRARY_PATH.read_text(encoding="utf-8"))
    experiments = payload.get("experiments")
    if experiments is None:
        raise KeyError(
            "[teacher_reference_flow_comparison] Experiment library does not contain 'experiments'."
        )
    return {str(item["experiment_id"]): dict(item) for item in experiments}


def _load_reference_conditioned_floor_m2(meta_path: Path) -> float:
    payload = json.loads(meta_path.read_text(encoding="utf-8"))
    geometry = payload.get("geometry")
    if not isinstance(geometry, dict):
        raise KeyError(
            f"[teacher_reference_flow_comparison] Missing geometry block in {meta_path}."
        )
    value = float(geometry.get("conditioned_floor_m2", 0.0) or 0.0)
    if value <= 0.0:
        raise ValueError(
            f"[teacher_reference_flow_comparison] geometry.conditioned_floor_m2 must be > 0 in {meta_path}, got {value}."
        )
    return value


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
        raise KeyError(
            f"[teacher_reference_flow_comparison] Missing required teacher columns: {missing}"
        )
    hourly = df.copy()
    hourly["timestamp_local"] = pd.to_datetime(hourly["timestamp_local"])
    hourly = hourly.sort_values("timestamp_local")
    day_start = pd.Timestamp(PRIMARY_SLICE_START_LOCAL)
    day_end = day_start + pd.Timedelta(hours=24)
    window = hourly[(hourly["timestamp_local"] >= day_start) & (hourly["timestamp_local"] < day_end)].copy()
    if len(window) != 24:
        raise ValueError(
            "[teacher_reference_flow_comparison] Expected 24 hourly rows for "
            f"{day_start.date()}, got {len(window)}."
        )
        return window
    return window


def _format_residential_title(cohort_id: str) -> str:
    label = cohort_id.replace("residential_", "")
    if label == "pre1975":
        return "<1975"
    start_year, end_year = label.split("_", maxsplit=1)
    return f"{start_year}-{end_year}"


def _build_separate_legend_asset(
    *,
    gain_legend_handles: list[object],
    gain_legend_labels: list[str],
    loss_legend_handles: list[object],
    loss_legend_labels: list[str],
) -> Path:
    """Export one standalone legend asset so it can be placed manually in the paper."""

    combined_handles = list(gain_legend_handles) + list(loss_legend_handles)
    combined_labels = list(gain_legend_labels) + list(loss_legend_labels)
    legend_fig = plt.figure(figsize=(13.5, 0.9))
    legend_fig.legend(
        combined_handles,
        combined_labels,
        loc="center",
        ncol=len(combined_labels),
        fontsize=10,
        frameon=False,
        handlelength=2.4,
        columnspacing=1.2,
    )
    legend_fig.savefig(LEGEND_OUTPUT_PATH, dpi=180, bbox_inches="tight", transparent=True)
    plt.close(legend_fig)
    return LEGEND_OUTPUT_PATH


if __name__ == "__main__":
    print(build_teacher_reference_flow_comparison())
