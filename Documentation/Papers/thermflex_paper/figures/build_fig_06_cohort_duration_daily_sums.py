from __future__ import annotations

"""Build daily cohort shift/release sums by Thermflex duration.

This figure deliberately excludes the indoor-temperature time series. The goal
is a compact result graphic: for each representative day, show how much heat is
shifted forward and released later by each residential cohort under different
duration settings.
"""

from pathlib import Path

import matplotlib

matplotlib.use("Agg", force=True)
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


FIGURE_DIR = Path(__file__).resolve().parent
SOURCE_HOURLY_DATA = FIGURE_DIR / "fig_05_cohort_duration_mechanism_data.csv"
OUTPUT_PATH = FIGURE_DIR / "fig_06_cohort_duration_daily_sums.png"
OUTPUT_DATA = FIGURE_DIR / "fig_06_cohort_duration_daily_sums.csv"

CASE_DATES = (
    ("2023-01-17", "Cold contrast"),
    ("2023-02-21", "February savings"),
    ("2023-03-04", "March savings I"),
    ("2023-03-16", "March savings II"),
    ("2023-03-18", "March savings III"),
    ("2023-03-23", "March peak kink"),
    ("2023-04-04", "Late-season shift"),
    ("2023-11-04", "Top savings"),
)
DURATIONS = (1, 4, 8, 12, 24)
COHORTS = (
    "residential_pre1975",
    "residential_1975_1990",
    "residential_1990_2000",
    "residential_2000_2014",
)
COHORT_LABELS = {
    "residential_pre1975": "<1975",
    "residential_1975_1990": "1975-1990",
    "residential_1990_2000": "1990-2000",
    "residential_2000_2014": "2000-2014",
}
COHORT_COLORS = {
    "residential_pre1975": "#8c2d04",
    "residential_1975_1990": "#d95f0e",
    "residential_1990_2000": "#31a354",
    "residential_2000_2014": "#08519c",
}
DURATION_ALPHA = {
    1: 0.22,
    4: 0.40,
    8: 0.58,
    12: 0.74,
    24: 0.95,
}
Y_LIMIT_LOWER_WH_M2 = -100.0
Y_LIMIT_UPPER_WH_M2 = 150.0


def build_fig_06_cohort_duration_daily_sums() -> Path:
    if OUTPUT_DATA.exists():
        # Fig. 06 is now a daily-sum figure. The daily-sum CSV is therefore the
        # reproducible plot input after the hourly diagnostic Fig. 05 was
        # retired from the active paper layer.
        summary = pd.read_csv(OUTPUT_DATA)
        _validate_summary(summary)
    elif SOURCE_HOURLY_DATA.exists():
        hourly = pd.read_csv(SOURCE_HOURLY_DATA)
        summary = _build_summary(hourly)
        summary.to_csv(OUTPUT_DATA, index=False)
    else:
        raise FileNotFoundError(
            "[fig_06] Required data missing. Expected either "
            f"{OUTPUT_DATA.name} or {SOURCE_HOURLY_DATA.name}."
        )
    _save_plot(summary)
    return OUTPUT_PATH


def _validate_summary(summary: pd.DataFrame) -> None:
    required_columns = {
        "date",
        "day_label",
        "duration_h",
        "cohort",
        "cohort_label",
        "shifted_wh_m2",
        "release_wh_m2",
        "net_wh_m2",
    }
    missing = sorted(required_columns.difference(summary.columns))
    if missing:
        raise KeyError("[fig_06] Summary data missing required columns: " + ", ".join(missing))


def _build_summary(hourly: pd.DataFrame) -> pd.DataFrame:
    required_columns = {"date", "day_label", "duration_h", "cohort", "cohort_label", "q_delta_wh_m2h"}
    missing = sorted(required_columns.difference(hourly.columns))
    if missing:
        raise KeyError("[fig_06] Source data missing required columns: " + ", ".join(missing))

    date_labels = {date: label for date, label in CASE_DATES}
    rows: list[dict[str, object]] = []
    for date, day_label in CASE_DATES:
        day = hourly.loc[hourly["date"].astype(str) == date].copy()
        if day.empty:
            raise ValueError(f"[fig_06] No rows found for date {date}.")
        for duration_h in DURATIONS:
            for cohort in COHORTS:
                group = day.loc[
                    (day["duration_h"].astype(int) == duration_h)
                    & (day["cohort"].astype(str) == cohort)
                ]
                if group.empty:
                    raise ValueError(f"[fig_06] Missing rows for {date}, duration {duration_h}, cohort {cohort}.")
                q_delta = group["q_delta_wh_m2h"].to_numpy(dtype=float)
                rows.append(
                    {
                        "date": date,
                        "day_label": date_labels[date],
                        "duration_h": int(duration_h),
                        "cohort": cohort,
                        "cohort_label": COHORT_LABELS[cohort],
                        "shifted_wh_m2": float(np.sum(np.maximum(q_delta, 0.0))),
                        "release_wh_m2": float(np.sum(np.maximum(-q_delta, 0.0))),
                        "net_wh_m2": float(np.sum(q_delta)),
                    }
                )
    return pd.DataFrame(rows)


def _save_plot(summary: pd.DataFrame) -> None:
    n_cols = 2
    n_rows = int(np.ceil(len(CASE_DATES) / n_cols))
    fig, axes = plt.subplots(n_rows, n_cols, figsize=(14.8, 4.1 * n_rows), sharey=True)
    axes_flat = np.asarray(axes).reshape(-1)
    y_limit = (Y_LIMIT_LOWER_WH_M2, Y_LIMIT_UPPER_WH_M2)
    for idx, (date, day_label) in enumerate(CASE_DATES):
        ax = axes_flat[idx]
        day = summary.loc[summary["date"] == date].copy()
        _plot_day(ax, day)
        ax.set_title(f"{day_label} ({date})", fontsize=11)
        ax.set_ylim(*y_limit)
        ax.axhline(0.0, color="#111827", linewidth=0.8)
        ax.grid(True, axis="y", alpha=0.22)
        ax.set_ylabel("daily heat shift/release [Wh/m2]", fontsize=10)
    for ax in axes_flat[len(CASE_DATES) :]:
        ax.set_axis_off()
    _add_legend(axes_flat[0])
    fig.tight_layout()
    fig.savefig(OUTPUT_PATH, dpi=180, bbox_inches="tight")
    plt.close(fig)


def _plot_day(ax: plt.Axes, day: pd.DataFrame) -> None:
    cohort_base_x = {cohort: idx for idx, cohort in enumerate(COHORTS)}
    duration_offsets = {1: -0.30, 4: -0.15, 8: 0.0, 12: 0.15, 24: 0.30}
    width = 0.062
    for duration_h in DURATIONS:
        for cohort in COHORTS:
            row = day.loc[(day["duration_h"] == duration_h) & (day["cohort"] == cohort)]
            if len(row) != 1:
                raise ValueError(f"[fig_06] Expected one row for {duration_h=} {cohort=}, got {len(row)}.")
            x = cohort_base_x[cohort] + duration_offsets[duration_h]
            shifted = float(row["shifted_wh_m2"].iloc[0])
            release = -float(row["release_wh_m2"].iloc[0])
            ax.bar(x, shifted, width=width, color=COHORT_COLORS[cohort], alpha=DURATION_ALPHA[duration_h])
            ax.bar(
                x,
                release,
                width=width,
                color=COHORT_COLORS[cohort],
                alpha=max(0.18, DURATION_ALPHA[duration_h] * 0.52),
                hatch="///",
                edgecolor=COHORT_COLORS[cohort],
                linewidth=0.35,
            )
    ax.set_xlim(-0.55, len(COHORTS) - 0.45)
    ax.set_xticks(np.arange(len(COHORTS)))
    ax.set_xticklabels([COHORT_LABELS[cohort] for cohort in COHORTS], rotation=20, ha="right")


def _add_legend(ax: plt.Axes) -> None:
    cohort_handles = [
        plt.Line2D([0], [0], color=COHORT_COLORS[cohort], linewidth=4, label=COHORT_LABELS[cohort])
        for cohort in COHORTS
    ]
    duration_handles = [
        plt.Line2D([0], [0], color="#111827", linewidth=4, alpha=DURATION_ALPHA[duration], label=f"{duration} h")
        for duration in DURATIONS
    ]
    direction_handles = [
        plt.Rectangle((0, 0), 1, 1, facecolor="#4b5563", alpha=0.75, label="shifted / preheat"),
        plt.Rectangle(
            (0, 0),
            1,
            1,
            facecolor="#4b5563",
            alpha=0.32,
            hatch="///",
            edgecolor="#4b5563",
            label="release / cutback",
        ),
    ]
    ax.legend(
        handles=cohort_handles + duration_handles + direction_handles,
        loc="upper left",
        fontsize=8,
        frameon=False,
        ncol=2,
    )


def _symmetric_ylim(values: np.ndarray) -> tuple[float, float]:
    finite = values[np.isfinite(values)]
    if finite.size == 0:
        return (-1.0, 1.0)
    max_abs = float(np.max(np.abs(finite)))
    if max_abs <= 0.0:
        max_abs = 1.0
    return (-1.12 * max_abs, 1.12 * max_abs)


if __name__ == "__main__":
    print(build_fig_06_cohort_duration_daily_sums())
