"""Build the three conference-paper figures for the Vienna EnergyPlus demand surrogate.

Figure 1 is the EnergyPlus teacher flow grid. Figure 2 is city holdout in four
weeks (peak heating, April heating, peak cooling, September cooling). Figure 3
is the outdoor-temperature response that EnergyPlus generates and the
surrogate reproduces. Runtime stays a table, not a figure.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg", force=True)
import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import numpy as np
import pandas as pd

from _paths import CSV_DIR, PAPER_DIR, PNG_DIR, PROJECT_ROOT, ensure_output_dirs


TEACHER_RUNS_ROOT = (
    PROJECT_ROOT
    / "Technical_model"
    / "technologies"
    / "buildings"
    / "calibration"
    / "_teacher_runs"
)
HOLDOUT_PATH = (
    PROJECT_ROOT
    / "Learning"
    / "models"
    / "vienna_building_demand_annual_reference_2023_v2"
    / "holdout_predictions.csv.gz"
)
TEACHER_HOURLY_PATH = (
    PROJECT_ROOT
    / "Learning"
    / "datasets"
    / "vienna_building_energyplus_teacher"
    / "building_teacher_annual_reference_2023_cohort_hourly.csv.gz"
)
RUNTIME_JSON = PAPER_DIR / "results" / "runtime_benchmark.json"
FLOW_EXPERIMENT_ID = "winter_event_reference_96h"
FLOW_SLICE_START_LOCAL = "2021-01-18T00:00:00"
RESIDENTIAL_COHORT_ORDER = (
    "residential_pre1975",
    "residential_1975_1990",
    "residential_1990_2000",
    "residential_2000_2014",
)
COHORT_LABELS = {
    "residential_pre1975": "<1975",
    "residential_1975_1990": "1975–1990",
    "residential_1990_2000": "1990–2000",
    "residential_2000_2014": "2000–2014",
}
GAINS_COLORS = {
    "heating": "#b45309",
    "internal": "#059669",
    "solar": "#f59e0b",
    "total": "#111827",
}
LOSSES_COLORS = {
    "transmission": "#7c2d12",
    "ventilation": "#0f766e",
    "total": "#111827",
}
# Shared EnergyPlus vs surrogate styling for the city holdout weeks.
HOLD_TRUTH_COLOR = "#111827"
HOLD_PRED_COLOR = "#d94801"
SPRING_WEEK_MONTH = 4
AUTUMN_WEEK_MONTH = 9


def _style() -> None:
    plt.rcParams.update(
        {
            "font.size": 9,
            "axes.titlesize": 10,
            "axes.labelsize": 9,
            "legend.fontsize": 8,
            "figure.facecolor": "white",
            "axes.facecolor": "white",
            "savefig.facecolor": "white",
        }
    )


def _load_flow_day(cohort_id: str) -> tuple[pd.DataFrame, float]:
    """Load the same 24 h teacher slice used in the ThermFlex flow figure."""
    csv_path = TEACHER_RUNS_ROOT / cohort_id / FLOW_EXPERIMENT_ID / "teacher_plausibility_hourly.csv"
    meta_path = TEACHER_RUNS_ROOT / cohort_id / FLOW_EXPERIMENT_ID / "teacher.meta.json"
    if not csv_path.is_file():
        raise FileNotFoundError(f"[paper_figures] Missing teacher CSV: {csv_path}")
    if not meta_path.is_file():
        raise FileNotFoundError(f"[paper_figures] Missing teacher meta: {meta_path}")
    required = {
        "timestamp_local",
        "zone_total_heating_rate_w",
        "internal_gains_total_w",
        "zone_windows_transmitted_solar_rate_w",
        "approx_transmission_loss_seed_ua_w",
        "approx_ventilation_loss_w",
    }
    frame = pd.read_csv(csv_path, parse_dates=["timestamp_local"]).sort_values("timestamp_local")
    missing = sorted(required - set(frame.columns))
    if missing:
        raise KeyError(f"[paper_figures] Teacher CSV {csv_path} missing columns: {missing}")
    day_start = pd.Timestamp(FLOW_SLICE_START_LOCAL)
    window = frame.loc[
        (frame["timestamp_local"] >= day_start) & (frame["timestamp_local"] < day_start + pd.Timedelta(hours=24))
    ].copy()
    if len(window) != 24:
        raise ValueError(f"[paper_figures] Expected 24 flow hours for {cohort_id} on {day_start.date()}, got {len(window)}.")
    geometry = json.loads(meta_path.read_text(encoding="utf-8")).get("geometry")
    if not isinstance(geometry, dict):
        raise KeyError(f"[paper_figures] Missing geometry in {meta_path}.")
    area_m2 = float(geometry.get("conditioned_floor_m2", 0.0) or 0.0)
    if area_m2 <= 0.0:
        raise ValueError(f"[paper_figures] conditioned_floor_m2 must be > 0 in {meta_path}.")
    return window.reset_index(drop=True), area_m2


def build_fig_01_teacher_cohorts() -> Path:
    """EnergyPlus teacher heat-balance flows for the four residential periods."""
    series: dict[str, tuple[pd.DataFrame, float]] = {}
    gain_upper = 0.0
    loss_upper = 0.0
    csv_rows: list[pd.DataFrame] = []
    for cohort_id in RESIDENTIAL_COHORT_ORDER:
        df, area_m2 = _load_flow_day(cohort_id)
        series[cohort_id] = (df, area_m2)
        heating = df["zone_total_heating_rate_w"].to_numpy(dtype=float) / area_m2
        internal = df["internal_gains_total_w"].to_numpy(dtype=float) / area_m2
        solar = df["zone_windows_transmitted_solar_rate_w"].to_numpy(dtype=float) / area_m2
        transmission = df["approx_transmission_loss_seed_ua_w"].to_numpy(dtype=float) / area_m2
        ventilation = df["approx_ventilation_loss_w"].to_numpy(dtype=float) / area_m2
        gain_upper = max(gain_upper, float(heating.max()), float(internal.max()), float(solar.max()), float((internal + solar).max()))
        loss_upper = max(loss_upper, float(transmission.max()), float(ventilation.max()), float((transmission + ventilation).max()))
        csv_rows.append(
            df.assign(
                cohort_id=cohort_id,
                heating_w_per_m2=heating,
                internal_gains_w_per_m2=internal,
                solar_gains_w_per_m2=solar,
                transmission_loss_w_per_m2=transmission,
                ventilation_loss_w_per_m2=ventilation,
            )
        )

    fig = plt.figure(figsize=(8.7, 6.9))
    outer = fig.add_gridspec(1, 2, width_ratios=[3.25, 1.15], wspace=0.16)
    plot_fig = fig.add_subfigure(outer[0, 0])
    legend_ax = fig.add_subplot(outer[0, 1])
    legend_ax.set_axis_off()
    subfigs = plot_fig.subfigures(2, 2, wspace=0.08, hspace=0.16)
    first_time = None
    legend_handles = None
    legend_labels = None
    for subfig, cohort_id in zip(subfigs.flat, RESIDENTIAL_COHORT_ORDER, strict=True):
        df, area_m2 = series[cohort_id]
        time = pd.DatetimeIndex(df["timestamp_local"])
        if first_time is None:
            first_time = time
        elif not time.equals(first_time):
            raise ValueError("[paper_figures] Residential teacher flow windows are misaligned.")
        gain_ax, loss_ax = subfig.subplots(2, 1, sharex=True)
        heating = df["zone_total_heating_rate_w"].to_numpy(dtype=float) / area_m2
        internal = df["internal_gains_total_w"].to_numpy(dtype=float) / area_m2
        solar = df["zone_windows_transmitted_solar_rate_w"].to_numpy(dtype=float) / area_m2
        transmission = df["approx_transmission_loss_seed_ua_w"].to_numpy(dtype=float) / area_m2
        ventilation = df["approx_ventilation_loss_w"].to_numpy(dtype=float) / area_m2
        gain_ax.plot(time, heating, color=GAINS_COLORS["heating"], lw=1.7, label="Space heating")
        gain_ax.plot(time, internal, color=GAINS_COLORS["internal"], lw=1.4, label="Internal gains")
        gain_ax.plot(time, solar, color=GAINS_COLORS["solar"], lw=1.4, label="Solar gains")
        gain_ax.plot(time, internal + solar, color=GAINS_COLORS["total"], lw=1.4, ls="--", label="Total gains")
        loss_ax.plot(time, transmission, color=LOSSES_COLORS["transmission"], lw=1.4, label="Transmission")
        loss_ax.plot(time, ventilation, color=LOSSES_COLORS["ventilation"], lw=1.3, label="Ventilation")
        loss_ax.plot(time, transmission + ventilation, color=LOSSES_COLORS["total"], lw=1.4, ls="--", label="Total losses")
        gain_ax.set_ylim(0.0, gain_upper * 1.08)
        loss_ax.set_ylim(0.0, loss_upper * 1.08)
        gain_ax.grid(True, alpha=0.28)
        loss_ax.grid(True, alpha=0.28)
        gain_ax.set_ylabel("Heat flow (W m$^{-2}$)")
        loss_ax.set_ylabel("Heat flow (W m$^{-2}$)")
        loss_ax.xaxis.set_major_locator(mdates.HourLocator(interval=6))
        loss_ax.xaxis.set_major_formatter(mdates.DateFormatter("%H:%M"))
        subfig.suptitle(COHORT_LABELS[cohort_id], fontsize=10, y=0.98)
        if legend_handles is None:
            gain_h, gain_l = gain_ax.get_legend_handles_labels()
            loss_h, loss_l = loss_ax.get_legend_handles_labels()
            legend_handles = gain_h + loss_h
            legend_labels = gain_l + loss_l

    if legend_handles is None or legend_labels is None:
        raise RuntimeError("[paper_figures] Flow figure legend was not collected.")
    legend_ax.legend(
        legend_handles,
        legend_labels,
        loc="center",
        ncol=1,
        frameon=False,
        borderaxespad=0.4,
        handlelength=2.2,
        labelspacing=1.15,
    )
    out = PNG_DIR / "fig_01_teacher_flow_day.png"
    fig.savefig(out, dpi=300, bbox_inches="tight", pad_inches=0.12)
    plt.close(fig)
    pd.concat(csv_rows, ignore_index=True).to_csv(CSV_DIR / "fig_01_teacher_flow_day.csv", index=False)
    for leftover in (
        PNG_DIR / "fig_01_teacher_residential_heating_cooling.png",
        CSV_DIR / "fig_01_winter_heating.csv",
        CSV_DIR / "fig_01_summer_cooling.csv",
    ):
        if leftover.exists():
            leftover.unlink()
    return out


def _city_holdout() -> pd.DataFrame:
    if not HOLDOUT_PATH.is_file():
        raise FileNotFoundError(f"[paper_figures] Missing holdout file: {HOLDOUT_PATH}")
    if not TEACHER_HOURLY_PATH.is_file():
        raise FileNotFoundError(f"[paper_figures] Missing teacher hourly file: {TEACHER_HOURLY_PATH}")
    frame = pd.read_csv(HOLDOUT_PATH, parse_dates=["timestamp_local"])
    required = {
        "timestamp_local",
        "cohort_id",
        "cohort_represented_gfa_m2",
        "truth__useful_space_heating_kwh_per_m2",
        "prediction__useful_space_heating_kwh_per_m2",
        "truth__useful_cooling_kwh_per_m2",
        "prediction__useful_cooling_kwh_per_m2",
    }
    missing = sorted(required - set(frame.columns))
    if missing:
        raise KeyError(f"[paper_figures] Holdout missing columns: {missing}")
    weather = pd.read_csv(
        TEACHER_HOURLY_PATH,
        usecols=["timestamp_local", "cohort_id", "outdoor_temperature_c"],
        parse_dates=["timestamp_local"],
    )
    frame = frame.merge(weather, on=["timestamp_local", "cohort_id"], how="left", validate="one_to_one")
    if frame["outdoor_temperature_c"].isna().any():
        raise ValueError("[paper_figures] Outdoor temperature missing after teacher merge.")
    frame["heat_truth_mw"] = (
        frame["truth__useful_space_heating_kwh_per_m2"] * frame["cohort_represented_gfa_m2"] / 1000.0
    )
    frame["heat_pred_mw"] = (
        frame["prediction__useful_space_heating_kwh_per_m2"] * frame["cohort_represented_gfa_m2"] / 1000.0
    )
    frame["cool_truth_mw"] = (
        frame["truth__useful_cooling_kwh_per_m2"] * frame["cohort_represented_gfa_m2"] / 1000.0
    )
    frame["cool_pred_mw"] = (
        frame["prediction__useful_cooling_kwh_per_m2"] * frame["cohort_represented_gfa_m2"] / 1000.0
    )
    city = (
        frame.groupby("timestamp_local", as_index=False)
        .agg(
            heat_truth_mw=("heat_truth_mw", "sum"),
            heat_pred_mw=("heat_pred_mw", "sum"),
            cool_truth_mw=("cool_truth_mw", "sum"),
            cool_pred_mw=("cool_pred_mw", "sum"),
            outdoor_temperature_c=("outdoor_temperature_c", "first"),
            outdoor_temperature_nunique=("outdoor_temperature_c", "nunique"),
        )
        .sort_values("timestamp_local")
        .reset_index(drop=True)
    )
    if len(city) != 8760:
        raise ValueError(f"[paper_figures] Expected 8760 city hours, got {len(city)}.")
    if int(city["outdoor_temperature_nunique"].max()) != 1:
        raise ValueError("[paper_figures] Outdoor temperature is not unique across cohorts at a given hour.")
    return city.drop(columns=["outdoor_temperature_nunique"])


def _peak_week(city: pd.DataFrame, column: str) -> pd.DataFrame:
    """Take the 168 h window whose truth peak sits at hour 84, clipped to the year."""
    peak_at = int(city[column].to_numpy(dtype=float).argmax())
    start = max(int(peak_at) - 84, 0)
    end = min(start + 168, len(city))
    start = end - 168
    window = city.iloc[start:end].copy()
    if len(window) != 168:
        raise ValueError(f"[paper_figures] Peak-week window for {column} is not 168 hours.")
    return window.reset_index(drop=True)


def _month_peak_week(city: pd.DataFrame, month: int, column: str) -> pd.DataFrame:
    """168 h window entirely in `month` with the highest mean of `column`.

    Spring/autumn panels should show a real heating or cooling week in that
    month, not the mild week whose outdoor temperature happens to match the
    monthly mean. That mild week sits on the heat/cool switch and is not what
    the MES sees as spring heating or autumn cooling.
    """
    month_index = pd.DatetimeIndex(city["timestamp_local"]).month.to_numpy(dtype=int)
    in_month = month_index == int(month)
    if int(in_month.sum()) < 168:
        raise ValueError(f"[paper_figures] Month {month} does not contain 168 hours.")
    values = city[column].to_numpy(dtype=float)
    best_start: int | None = None
    best_mean: float | None = None
    for start in range(0, len(city) - 167):
        if not bool(in_month[start : start + 168].all()):
            continue
        mean_value = float(values[start : start + 168].mean())
        if best_mean is None or mean_value > best_mean:
            best_mean = mean_value
            best_start = start
    if best_start is None:
        raise ValueError(f"[paper_figures] No full 168 h window inside month {month}.")
    return city.iloc[best_start : best_start + 168].copy().reset_index(drop=True)


_WEEK_MONTH_ABBR = (
    "Jan",
    "Feb",
    "Mar",
    "Apr",
    "May",
    "Jun",
    "Jul",
    "Aug",
    "Sep",
    "Oct",
    "Nov",
    "Dec",
)


def _week_title(label: str, week: pd.DataFrame) -> str:
    start = pd.Timestamp(week["timestamp_local"].iloc[0])
    end = pd.Timestamp(week["timestamp_local"].iloc[-1])
    start_label = f"{start.day:02d} {_WEEK_MONTH_ABBR[start.month - 1]}"
    end_label = f"{end.day:02d} {_WEEK_MONTH_ABBR[end.month - 1]}"
    return f"{label}, {start_label}–{end_label}"


def _week_day_label(value: float, _pos: object) -> str:
    """Locale-independent day labels so a German Windows locale cannot widen ticks."""
    stamp = mdates.num2date(value)
    return f"{stamp.day} {_WEEK_MONTH_ABBR[stamp.month - 1]}"


def _plot_holdout_week(
    ax,
    week: pd.DataFrame,
    *,
    truth_col: str,
    pred_col: str,
    ylabel: str,
    title: str,
    show_legend: bool,
) -> None:
    """Same EnergyPlus/surrogate styling as the original two-panel figure."""
    ax.plot(week["timestamp_local"], week[truth_col], color=HOLD_TRUTH_COLOR, lw=1.6, label="EnergyPlus")
    ax.plot(week["timestamp_local"], week[pred_col], color=HOLD_PRED_COLOR, lw=1.6, ls="--", label="Surrogate")
    ax.set_title(title)
    ax.set_ylabel(ylabel)
    ax.grid(True, alpha=0.28)
    start = pd.Timestamp(week["timestamp_local"].iloc[0])
    end = pd.Timestamp(week["timestamp_local"].iloc[-1])
    ax.set_xlim(start, end)
    # One-line daily labels. Two-line "%d\\n%b" ticks were clipped between the
    # 2x2 rows, so the horizontal dates were not readable.
    ax.xaxis.set_major_locator(mdates.DayLocator())
    ax.xaxis.set_major_formatter(mticker.FuncFormatter(_week_day_label))
    ax.tick_params(axis="x", labelsize=9, pad=4, length=3.5)
    ax.set_ylim(bottom=0.0)
    if show_legend:
        ax.legend(loc="upper right", frameon=False)


def build_fig_02_city_holdout(city: pd.DataFrame) -> Path:
    """City holdout: peak heating, April heating week, peak cooling, September cooling week."""
    weeks = {
        "peak_heating": _peak_week(city, "heat_truth_mw"),
        "spring": _month_peak_week(city, SPRING_WEEK_MONTH, "heat_truth_mw"),
        "peak_cooling": _peak_week(city, "cool_truth_mw"),
        "autumn": _month_peak_week(city, AUTUMN_WEEK_MONTH, "cool_truth_mw"),
    }
    fig, axes = plt.subplots(2, 2, figsize=(8.2, 6.4), sharex=False, constrained_layout=True)
    panels = (
        (axes[0, 0], weeks["peak_heating"], "heat_truth_mw", "heat_pred_mw", "Heating (MW)", "Peak heating", True),
        (axes[0, 1], weeks["spring"], "heat_truth_mw", "heat_pred_mw", "Heating (MW)", "Spring", False),
        (axes[1, 0], weeks["peak_cooling"], "cool_truth_mw", "cool_pred_mw", "Cooling (MW)", "Peak cooling", False),
        (axes[1, 1], weeks["autumn"], "cool_truth_mw", "cool_pred_mw", "Cooling (MW)", "Autumn", False),
    )
    for ax, week, truth_col, pred_col, ylabel, label, show_legend in panels:
        _plot_holdout_week(
            ax,
            week,
            truth_col=truth_col,
            pred_col=pred_col,
            ylabel=ylabel,
            title=_week_title(label, week),
            show_legend=show_legend,
        )
    fig.set_constrained_layout_pads(w_pad=0.04, h_pad=0.06, wspace=0.08, hspace=0.14)
    out = PNG_DIR / "fig_02_city_holdout_seasonal_weeks.png"
    fig.savefig(out, dpi=300, bbox_inches="tight", pad_inches=0.15)
    plt.close(fig)
    for name, week in weeks.items():
        week.assign(week=name).to_csv(CSV_DIR / f"fig_02_{name}_week.csv", index=False)
    leftover = PNG_DIR / "fig_02_city_holdout_peak_weeks.png"
    if leftover.exists():
        leftover.unlink()
    return out


def _temperature_bins(city: pd.DataFrame) -> pd.DataFrame:
    """1 K outdoor-temperature bins with enough hours to show a stable mean."""
    binned = city.copy()
    binned["t_bin_c"] = np.floor(binned["outdoor_temperature_c"].to_numpy(dtype=float))
    grouped = binned.groupby("t_bin_c", as_index=False).agg(
        n_hours=("outdoor_temperature_c", "size"),
        heat_truth_mw=("heat_truth_mw", "mean"),
        heat_pred_mw=("heat_pred_mw", "mean"),
        cool_truth_mw=("cool_truth_mw", "mean"),
        cool_pred_mw=("cool_pred_mw", "mean"),
    )
    grouped = grouped.loc[grouped["n_hours"] >= 8].sort_values("t_bin_c")
    if grouped.empty:
        raise ValueError("[paper_figures] No outdoor-temperature bins with at least 8 hours.")
    return grouped


def build_fig_03_temperature_response(city: pd.DataFrame) -> Path:
    """EnergyPlus heating/cooling vs outdoor temperature, with the surrogate overlay."""
    bins = _temperature_bins(city)
    fig, axes = plt.subplots(1, 2, figsize=(7.4, 3.25), sharex=True)
    for ax, truth, pred, ylabel, title in (
        (axes[0], "heat_truth_mw", "heat_pred_mw", "Heating (MW)", "Heating"),
        (axes[1], "cool_truth_mw", "cool_pred_mw", "Cooling (MW)", "Cooling"),
    ):
        ax.scatter(
            city["outdoor_temperature_c"],
            city[truth],
            s=6,
            c="#111827",
            alpha=0.08,
            linewidths=0,
            label="EnergyPlus hours",
        )
        ax.plot(bins["t_bin_c"] + 0.5, bins[truth], color="#111827", lw=2.0, label="EnergyPlus mean")
        ax.plot(bins["t_bin_c"] + 0.5, bins[pred], color="#d94801", lw=2.0, ls="--", label="Surrogate mean")
        ax.set_title(title)
        ax.set_xlabel("Outdoor temperature (°C)")
        ax.set_ylabel(ylabel)
        ax.grid(True, alpha=0.28)
    handles, labels = axes[0].get_legend_handles_labels()
    axes[1].legend(handles, labels, loc="upper left", frameon=False)
    fig.tight_layout()
    out = PNG_DIR / "fig_03_temperature_response.png"
    fig.savefig(out, dpi=300, bbox_inches="tight")
    plt.close(fig)
    bins.to_csv(CSV_DIR / "fig_03_temperature_bins.csv", index=False)
    city.loc[:, ["timestamp_local", "outdoor_temperature_c", "heat_truth_mw", "heat_pred_mw", "cool_truth_mw", "cool_pred_mw"]].to_csv(
        CSV_DIR / "fig_03_temperature_hourly_city.csv", index=False
    )
    for leftover in (
        PNG_DIR / "fig_03_runtime_city_year.png",
        CSV_DIR / "fig_03_runtime.csv",
    ):
        if leftover.exists():
            leftover.unlink()
    return out


def write_runtime_table() -> Path:
    """Keep wall-clock evidence as a table rather than a third figure."""
    if not RUNTIME_JSON.is_file():
        raise FileNotFoundError(f"[paper_figures] Missing runtime benchmark: {RUNTIME_JSON}")
    payload = json.loads(RUNTIME_JSON.read_text(encoding="utf-8"))
    city = payload.get("city_year")
    surrogate = payload.get("surrogate")
    if not isinstance(city, dict) or not isinstance(surrogate, dict):
        raise KeyError("[paper_figures] runtime_benchmark.json is missing city_year or surrogate.")
    lines = [
        "# Table: runtime for one Vienna city year",
        "",
        "Eight `annual_reference_2023` cohorts, 8 x 8760 h. Diagnostic plots excluded.",
        "",
        "| Path | Prepare [s] | EnergyPlus engine [s] | SQL extract [s] | Total [s] |",
        "|---|---:|---:|---:|---:|",
        f"| EnergyPlus demand path | {float(city['prepare_s']):.1f} | {float(city['energyplus_wall_median_sum_s']):.1f} | {float(city['sql_extract_s']):.1f} | {float(city['demand_path_s']):.1f} |",
        f"| Surrogate inference | — | — | — | {float(surrogate['predict_both_targets_median_s']):.2f} |",
        "",
        f"Speedup (demand path / predict): **{float(city['speedup_demand_path_vs_predict']):.0f}×**.",
        f"One-time surrogate fit: {float(surrogate['fit_both_targets_s']):.1f} s.",
        "",
    ]
    out = PAPER_DIR / "results" / "table_01_runtime.md"
    out.write_text("\n".join(lines), encoding="utf-8")
    return out


def main() -> None:
    if str(PROJECT_ROOT) not in sys.path:
        sys.path.insert(0, str(PROJECT_ROOT))
    ensure_output_dirs()
    _style()
    city = _city_holdout()
    paths = (
        build_fig_01_teacher_cohorts(),
        build_fig_02_city_holdout(city),
        build_fig_03_temperature_response(city),
        write_runtime_table(),
    )
    for path in paths:
        print(path)


if __name__ == "__main__":
    main()
