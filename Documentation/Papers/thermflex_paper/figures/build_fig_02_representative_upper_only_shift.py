from __future__ import annotations

"""Build a lean multi-panel paper figure for upper-only thermflex day-type contrast.

The figure now tells the intended paper story directly:
- on very cold days, upper-only thermflex hardly shifts the district space-heat
  path in a meaningful intra-day way,
- on milder transition and shoulder days, the same policy produces a visible
  within-day preheat / release pattern.

The current day-ahead setup otherwise shows a horizon-end artifact in the last
hour for some cold-day 24 h slices. To avoid visualizing that artifact as if it
were the mechanism, the figure solves a 25 h horizon and plots only the first
24 h. This keeps the within-day comparison on the active part of the horizon
without changing the underlying policy settings.
"""

import json
import os
from pathlib import Path
import sys
from typing import Any

import matplotlib

matplotlib.use("Agg", force=True)
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[4]
project_root_str = str(PROJECT_ROOT.resolve())
if project_root_str not in sys.path:
    sys.path.insert(0, project_root_str)

from Optimization.run.analysis.build_constant_thermflex_isolation import (  # noqa: E402
    _evaluate_case_timeseries,
)


OVERRIDE_DIR = (
    PROJECT_ROOT
    / "Optimization"
    / "validation"
    / "model_validation"
    / "overrides"
    / "thermflex"
)
REFERENCE_OVERRIDE = (
    OVERRIDE_DIR / "vienna_ref2023_dh_baseline_constant_no_thermflex_paper_day_ahead.json"
)
UPPER_ONLY_OVERRIDE = (
    OVERRIDE_DIR
    / "vienna_ref2023_dh_baseline_constant_thermflex_lb22p5_dur1_evt1_upper_only_paper_day_ahead.json"
)
OUTPUT_PATH = Path(__file__).resolve().parent / "fig_02_representative_upper_only_shift.png"
TEMP_OVERRIDE_DIR = PROJECT_ROOT / "_tmp_codex_thermflex_figures"

PLOT_HOURS = 24
SOLVE_HOURS = 25
SMOOTHING_WINDOW_H = 2

CASE_SPECS = (
    {
        "title": "Cold peak-load day",
        "date": "2023-01-17",
        "note": "Upper-only stays effectively inactive",
        "color": "#1d4ed8",
    },
    {
        "title": "Moderate winter shift day",
        "date": "2023-02-06",
        "note": "Visible winter preheat, but still limited",
        "color": "#d97706",
    },
    {
        "title": "Late-winter preheat day",
        "date": "2023-03-15",
        "note": "Clear preheat followed by later release",
        "color": "#f59e0b",
    },
    {
        "title": "Spring shift day",
        "date": "2023-04-24",
        "note": "Broad preheat with visible later release",
        "color": "#b45309",
    },
    {
        "title": "Autumn shoulder day",
        "date": "2023-10-15",
        "note": "Strong visible within-day load shift",
        "color": "#059669",
    },
    {
        "title": "Late-autumn shift day",
        "date": "2023-11-20",
        "note": "Strong shift before full winter lock-in",
        "color": "#16a34a",
    },
)


def build_fig_02_representative_upper_only_shift() -> Path:
    panel_payloads = []
    for case in CASE_SPECS:
        ref_series = _evaluate_day_slice(REFERENCE_OVERRIDE, case["date"])
        upper_series = _evaluate_day_slice(UPPER_ONLY_OVERRIDE, case["date"])
        panel_payloads.append(
            {
                "case": case,
                "ref_series": ref_series,
                "upper_series": upper_series,
            }
        )

    demand_ylim = _compute_shared_ylim(panel_payloads)

    fig, axes = plt.subplots(3, 2, figsize=(13.5, 11.6), sharex=True, sharey=True)
    axes_flat = axes.flatten()
    for idx, payload in enumerate(panel_payloads):
        ax = axes_flat[idx]
        case = payload["case"]
        ref_series = payload["ref_series"]
        upper_series = payload["upper_series"]

        hours = np.arange(PLOT_HOURS, dtype=int)
        timestamps = pd.DatetimeIndex(ref_series["timestamps"][:PLOT_HOURS])
        ref_mw_raw = np.asarray(ref_series["dh_total_demand"][:PLOT_HOURS], dtype=float) / 1000.0
        upper_mw_raw = np.asarray(upper_series["dh_total_demand"][:PLOT_HOURS], dtype=float) / 1000.0
        ref_mw = _smooth_series(ref_mw_raw)
        upper_mw = _smooth_series(upper_mw_raw)

        ax.plot(hours, ref_mw, color="#9ca3af", linewidth=2.1, label="Reference")
        ax.plot(hours, upper_mw, color=case["color"], linewidth=2.1, label="Upper-only")
        ax.fill_between(
            hours,
            ref_mw,
            upper_mw,
            color=case["color"],
            alpha=0.18,
        )
        ax.set_ylim(*demand_ylim)
        ax.grid(True, axis="y", alpha=0.25)
        ax.tick_params(axis="both", labelsize=10)
        ax.set_title(
            f"{case['title']} ({case['date']})",
            fontsize=12,
        )
        ax.text(
            0.02,
            0.96,
            str(case["note"]),
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
    axes[2, 0].set_xlabel("Hour of slice", fontsize=11)
    axes[2, 1].set_xlabel("Hour of slice", fontsize=11)

    fig.tight_layout()
    fig.savefig(OUTPUT_PATH, dpi=180, bbox_inches="tight")
    plt.close(fig)
    return OUTPUT_PATH


def _evaluate_day_slice(override_path: Path, date_str: str) -> dict[str, Any]:
    override_path = Path(override_path).resolve()
    payload = json.loads(override_path.read_text(encoding="utf-8-sig"))
    payload["run"]["profile_start"] = f"{date_str} 00:00:00"
    payload["run"]["profile_hours"] = SOLVE_HOURS
    payload["dispatch"]["horizon_h"] = SOLVE_HOURS
    payload["run"]["tag"] = f"{payload['run']['tag']}_{date_str.replace('-', '')}_{SOLVE_HOURS}h"

    # Materialize a short-lived workspace-local override so the existing helper
    # can re-use the official Gold evaluation path without introducing a second
    # evaluation implementation in the paper layer.
    TEMP_OVERRIDE_DIR.mkdir(parents=True, exist_ok=True)
    temp_path = (
        TEMP_OVERRIDE_DIR
        / f"{override_path.stem}_{date_str.replace('-', '')}_{SOLVE_HOURS}h_{os.getpid()}.json"
    )
    try:
        temp_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
        raw_series = _evaluate_case_timeseries(temp_path)
    finally:
        if temp_path.exists():
            temp_path.unlink()
        if TEMP_OVERRIDE_DIR.exists() and not any(TEMP_OVERRIDE_DIR.iterdir()):
            TEMP_OVERRIDE_DIR.rmdir()
    if len(raw_series["timestamps"]) < PLOT_HOURS:
        raise ValueError(
            "[build_fig_02_representative_upper_only_shift] "
            f"Expected at least {PLOT_HOURS} hourly points for {date_str}, got {len(raw_series['timestamps'])}."
        )
    return raw_series


def _compute_shared_ylim(panel_payloads: list[dict[str, Any]]) -> tuple[float, float]:
    lower = float("inf")
    upper = float("-inf")
    for payload in panel_payloads:
        ref_values = _smooth_series(
            np.asarray(payload["ref_series"]["dh_total_demand"][:PLOT_HOURS], dtype=float) / 1000.0
        )
        upper_values = _smooth_series(
            np.asarray(payload["upper_series"]["dh_total_demand"][:PLOT_HOURS], dtype=float) / 1000.0
        )
        lower = min(lower, float(np.min(ref_values)), float(np.min(upper_values)))
        upper = max(upper, float(np.max(ref_values)), float(np.max(upper_values)))
    span = upper - lower
    pad = 0.08 * span if span > 0.0 else 1.0
    return (lower - pad, upper + pad)


def _smooth_series(values: np.ndarray) -> np.ndarray:
    arr = np.asarray(values, dtype=float).reshape(-1)
    if arr.size == 0:
        return arr
    if SMOOTHING_WINDOW_H <= 1:
        return arr.copy()
    series = pd.Series(arr)
    return series.rolling(window=SMOOTHING_WINDOW_H, center=True, min_periods=1).mean().to_numpy(dtype=float)


if __name__ == "__main__":
    print(build_fig_02_representative_upper_only_shift())
