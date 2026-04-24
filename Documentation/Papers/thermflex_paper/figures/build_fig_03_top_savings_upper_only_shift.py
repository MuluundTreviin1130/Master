from __future__ import annotations

"""Build a second representative-day figure focused on top savings days.

This figure intentionally does not overwrite the existing day-type contrast
graphic. It is a candidate paper figure for the stronger KPI story:
- one cold contrast day with little flexibility benefit,
- three high-savings days selected from the full heating-season daily screen.
"""

from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[4]
project_root_str = str(PROJECT_ROOT.resolve())
if project_root_str not in sys.path:
    sys.path.insert(0, project_root_str)

from Documentation.Papers.thermflex_paper.figures.build_fig_02_representative_upper_only_shift import (  # noqa: E402
    REFERENCE_OVERRIDE,
    UPPER_ONLY_OVERRIDE,
    PLOT_HOURS,
    _compute_shared_ylim,
    _evaluate_day_slice,
    _smooth_series,
)

import matplotlib  # noqa: E402

matplotlib.use("Agg", force=True)
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402


OUTPUT_PATH = Path(__file__).resolve().parent / "fig_03_top_savings_upper_only_shift.png"

CASE_SPECS = (
    {
        "title": "Cold contrast day",
        "date": "2023-01-17",
        "note": "Very limited benefit on a cold, high-load day",
        "color": "#1d4ed8",
    },
    {
        "title": "Strong February savings day",
        "date": "2023-02-21",
        "note": "Clear savings with visible release after preheat",
        "color": "#b45309",
    },
    {
        "title": "Strong March savings day",
        "date": "2023-03-04",
        "note": "Large daily shift with robust cost and CO2 reduction",
        "color": "#d97706",
    },
    {
        "title": "Strong November savings day",
        "date": "2023-11-04",
        "note": "Mild-day flexibility with the strongest joint savings",
        "color": "#059669",
    },
    {
        "title": "March savings day II",
        "date": "2023-03-16",
        "note": "Large shift, but rebound already starts to matter",
        "color": "#f59e0b",
    },
    {
        "title": "March savings day III",
        "date": "2023-03-23",
        "note": "Very strong shift with strong KPI gains",
        "color": "#ea580c",
    },
    {
        "title": "April transition savings day",
        "date": "2023-04-01",
        "note": "High mild-day savings with strong boiler relief",
        "color": "#65a30d",
    },
    {
        "title": "February savings day II",
        "date": "2023-02-23",
        "note": "Clear winter savings with visible peak relief",
        "color": "#0f766e",
    },
)


def build_fig_03_top_savings_upper_only_shift() -> Path:
    """Render the second paper figure with top-savings day candidates."""

    panel_payloads = []
    for case in CASE_SPECS:
        panel_payloads.append(
            {
                "case": case,
                "ref_series": _evaluate_day_slice(REFERENCE_OVERRIDE, case["date"]),
                "upper_series": _evaluate_day_slice(UPPER_ONLY_OVERRIDE, case["date"]),
            }
        )

    demand_ylim = _compute_shared_ylim(panel_payloads)
    fig, axes = plt.subplots(4, 2, figsize=(13.4, 16.0), sharex=True, sharey=True)
    axes_flat = axes.flatten()

    for idx, payload in enumerate(panel_payloads):
        ax = axes_flat[idx]
        case = payload["case"]
        ref_series = payload["ref_series"]
        upper_series = payload["upper_series"]
        hours = np.arange(PLOT_HOURS, dtype=int)
        timestamps = pd.DatetimeIndex(ref_series["timestamps"][:PLOT_HOURS])
        ref_mw = _smooth_series(np.asarray(ref_series["dh_total_demand"][:PLOT_HOURS], dtype=float) / 1000.0)
        upper_mw = _smooth_series(
            np.asarray(upper_series["dh_total_demand"][:PLOT_HOURS], dtype=float) / 1000.0
        )

        ax.plot(hours, ref_mw, color="#9ca3af", linewidth=2.1, label="Reference")
        ax.plot(hours, upper_mw, color=case["color"], linewidth=2.1, label="Upper-only")
        ax.fill_between(hours, ref_mw, upper_mw, color=case["color"], alpha=0.18)
        ax.set_ylim(*demand_ylim)
        ax.grid(True, axis="y", alpha=0.25)
        ax.tick_params(axis="both", labelsize=10)
        ax.set_title(f"{case['title']} ({case['date']})", fontsize=12)
        ax.text(
            0.02,
            0.96,
            case["note"],
            transform=ax.transAxes,
            ha="left",
            va="top",
            fontsize=9,
            color="#374151",
        )
        if idx == 0:
            ax.legend(loc="upper right", fontsize=9, frameon=False)
        tick_labels = [ts.strftime("%H:%M") for ts in timestamps]
        ax.set_xticks(hours[::3])
        ax.set_xticklabels(tick_labels[::3], fontsize=10)

    axes[0, 0].set_ylabel("District total heat demand [MW thermal]", fontsize=11)
    axes[1, 0].set_ylabel("District total heat demand [MW thermal]", fontsize=11)
    axes[2, 0].set_ylabel("District total heat demand [MW thermal]", fontsize=11)
    axes[3, 0].set_ylabel("District total heat demand [MW thermal]", fontsize=11)
    axes[3, 0].set_xlabel("Hour of slice", fontsize=11)
    axes[3, 1].set_xlabel("Hour of slice", fontsize=11)

    fig.tight_layout()
    fig.savefig(OUTPUT_PATH, dpi=180, bbox_inches="tight")
    plt.close(fig)
    return OUTPUT_PATH


if __name__ == "__main__":
    print(build_fig_03_top_savings_upper_only_shift())
