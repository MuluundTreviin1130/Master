from __future__ import annotations

"""Build a grouped-bar trade-off figure for selected heating-season days.

The user explicitly wants a simpler mechanism figure than the previous
scatter-plus-bars draft:
- no upper scatter panel,
- clearer separation between day groups,
- more days,
- focus on the metrics that tell the mechanism directly.

This figure therefore shows one grouped-bar panel over a mixed set of:
- a cold weak-benefit day,
- robust savings days,
- trade-off / mechanism-kink days.

The active paper path remains the current `upper_only dur1 evt1` setup.
"""

from pathlib import Path
import sys

import matplotlib

matplotlib.use("Agg", force=True)
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[4]
project_root_str = str(PROJECT_ROOT.resolve())
if project_root_str not in sys.path:
    sys.path.insert(0, project_root_str)

FIGURE_DIR = Path(__file__).resolve().parent
SCREEN_PATH = (
    PROJECT_ROOT
    / "Optimization"
    / "run"
    / "results"
    / "Vienna"
    / "gold"
    / "daily_thermflex_screen_20260421_160246"
    / "heating_season_day_screen.csv"
)
OUTPUT_PATH = FIGURE_DIR / "fig_04_tradeoff_day_map.png"


DAY_GROUPS = (
    {
        "group": "Cold contrast",
        "days": (
            {"date": "2023-01-17", "label": "Jan-17"},
        ),
    },
    {
        "group": "Robust savings",
        "days": (
            {"date": "2023-02-21", "label": "Feb-21"},
            {"date": "2023-03-04", "label": "Mar-04"},
            {"date": "2023-03-18", "label": "Mar-18"},
            {"date": "2023-11-04", "label": "Nov-04"},
        ),
    },
    {
        "group": "Trade-offs / kinks",
        "days": (
            {"date": "2023-03-17", "label": "Mar-17"},
            {"date": "2023-04-22", "label": "Apr-22"},
            {"date": "2023-04-23", "label": "Apr-23"},
        ),
    },
)

BAR_METRICS = (
    {
        "column": "dispatch_operating_cost_pct_change",
        "label": "Cost",
        "color": "#1d4ed8",
    },
    {
        "column": "co2_emissions_total_pct_change",
        "label": "CO2",
        "color": "#059669",
    },
    {
        "column": "district_gas_boiler_generation_pct_change",
        "label": "Boiler energy",
        "color": "#b45309",
    },
    {
        "column": "thermflex_rebound_over_shifted_pct",
        "label": "Rebound / shifted",
        "color": "#7c3aed",
    },
)


def _load_screen() -> pd.DataFrame:
    """Load the daily screen and coerce required columns."""

    df = pd.read_csv(SCREEN_PATH)
    required_columns = (
        "date",
        "dispatch_operating_cost_pct_change",
        "co2_emissions_total_pct_change",
        "district_gas_boiler_generation_pct_change",
        "thermflex_rebound_over_shifted_pct",
    )
    for column in required_columns:
        if column not in df.columns:
            raise KeyError(f"[build_fig_04_tradeoff_day_map] Missing screen column: {column}")
    for column in required_columns[1:]:
        df[column] = pd.to_numeric(df[column], errors="raise")
    return df


def _build_tradeoff_frame() -> pd.DataFrame:
    """Assemble the selected days with KPI deltas and rebound context."""

    screen_df = _load_screen()
    rows: list[dict[str, object]] = []

    for group_idx, group in enumerate(DAY_GROUPS):
        for day_idx, day_spec in enumerate(group["days"]):
            date_str = str(day_spec["date"])
            label = str(day_spec["label"])

            screen_row = screen_df.loc[screen_df["date"] == date_str]
            if screen_row.empty:
                raise ValueError(f"[build_fig_04_tradeoff_day_map] Day missing from screen: {date_str}")
            screen_row = screen_row.iloc[0]

            rows.append(
                {
                    "group": str(group["group"]),
                    "group_idx": int(group_idx),
                    "day_idx": int(day_idx),
                    "date": date_str,
                    "label": label,
                    "dispatch_operating_cost_pct_change": float(screen_row["dispatch_operating_cost_pct_change"]),
                    "co2_emissions_total_pct_change": float(screen_row["co2_emissions_total_pct_change"]),
                    "district_gas_boiler_generation_pct_change": float(
                        screen_row["district_gas_boiler_generation_pct_change"]
                    ),
                    "thermflex_rebound_over_shifted_pct": float(screen_row["thermflex_rebound_over_shifted_pct"]),
                }
            )

    return pd.DataFrame(rows)


def _compute_grouped_positions(df: pd.DataFrame) -> tuple[np.ndarray, dict[str, tuple[float, float]]]:
    """Compute x positions with visible gaps between day groups."""

    positions: list[float] = []
    group_spans: dict[str, tuple[float, float]] = {}
    cursor = 0.0
    within_gap = 1.0
    between_gap = 0.9

    for group in df["group"].drop_duplicates():
        group_mask = df["group"] == group
        group_size = int(group_mask.sum())
        group_positions = [cursor + idx * within_gap for idx in range(group_size)]
        positions.extend(group_positions)
        group_spans[group] = (group_positions[0], group_positions[-1])
        cursor = group_positions[-1] + within_gap + between_gap

    return np.asarray(positions, dtype=float), group_spans


def build_fig_04_tradeoff_day_map() -> Path:
    """Build the grouped-bar trade-off figure."""

    df = _build_tradeoff_frame()
    x, group_spans = _compute_grouped_positions(df)

    fig, ax = plt.subplots(figsize=(14.6, 7.8))
    width = 0.18
    offsets = np.linspace(-(1.5 * width), 1.5 * width, num=len(BAR_METRICS))

    for offset, metric in zip(offsets, BAR_METRICS):
        values = df[metric["column"]].to_numpy(dtype=float)
        bars = ax.bar(
            x + offset,
            values,
            width=width,
            color=metric["color"],
            alpha=0.92,
            label=metric["label"],
        )
        for bar, value in zip(bars, values):
            if abs(value) < 0.05:
                continue
            pad = 0.7 if value >= 0 else -0.7
            va = "bottom" if value >= 0 else "top"
            ax.text(
                bar.get_x() + bar.get_width() / 2.0,
                value + pad,
                f"{value:.1f}",
                ha="center",
                va=va,
                fontsize=8,
                color="#111827",
            )

    ax.axhline(0.0, color="#4b5563", linewidth=1.1)
    ax.grid(True, axis="y", alpha=0.22)
    ax.set_ylabel("Change [%]")
    ax.set_xticks(x)
    ax.set_xticklabels(df["label"].tolist(), fontsize=10)
    ax.set_title(
        "Daily trade-offs and mechanism shifts for upper-only thermflex\n"
        "(active paper path: upper_only, dur=1 h, evt=1)",
        fontsize=13,
    )

    ymax = float(max(8.0, np.nanmax(df[[m["column"] for m in BAR_METRICS]].to_numpy(dtype=float))))
    ymin = float(min(-70.0, np.nanmin(df[[m["column"] for m in BAR_METRICS]].to_numpy(dtype=float)) - 4.0))
    ax.set_ylim(ymin, ymax + 8.5)

    separator_positions = []
    ordered_groups = list(df["group"].drop_duplicates())
    for idx, group in enumerate(ordered_groups):
        left, right = group_spans[group]
        center = 0.5 * (left + right)
        ax.text(
            center,
            ymax + 5.7,
            group,
            ha="center",
            va="bottom",
            fontsize=10,
            color="#374151",
            fontweight="bold",
        )
        if idx < len(ordered_groups) - 1:
            separator_positions.append(right + 0.95)

    for xpos in separator_positions:
        ax.axvline(xpos, color="#d1d5db", linewidth=1.0, linestyle="--", alpha=0.9)

    ax.legend(loc="lower left", fontsize=9, ncol=2, frameon=False)
    fig.tight_layout()
    fig.savefig(OUTPUT_PATH, dpi=180, bbox_inches="tight")
    plt.close(fig)
    return OUTPUT_PATH


if __name__ == "__main__":
    print(build_fig_04_tradeoff_day_map())
