from __future__ import annotations

"""Build a paper figure that compares thermflex use cases against the same reference.

The user wants one compact figure that shows the core operational mechanism:
- left: district space-heat demand over 24 h with the shifted area relative to the reference,
- right: gas-boiler dispatch over 24 h,
- one row per use case,
- the constant no-thermflex reference is not a standalone row but the gray line
  inside each panel.

The figure is intentionally paper-local and therefore lives directly in the
manuscript figure layer. It reuses the existing Gold re-evaluation helper from
the constant thermflex analysis path so that there is no second hidden source
for the hourly series.
"""

import matplotlib
from pathlib import Path
import sys

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
OUTPUT_PATH = Path(__file__).resolve().parent / "fig_01_use_case_shift_boiler.png"

REFERENCE_OVERRIDE = (
    OVERRIDE_DIR / "vienna_ref2023_dh_baseline_constant_no_thermflex_paper_day_ahead.json"
)
CASE_SPECS = (
    (
        "Upper-only preheat",
        OVERRIDE_DIR
        / "vienna_ref2023_dh_baseline_constant_thermflex_lb22p5_dur4_evt1_upper_only_paper_day_ahead.json",
        "#c0392b",
    ),
    (
        "Full thermflex, dur=1 h",
        OVERRIDE_DIR
        / "vienna_ref2023_dh_baseline_constant_thermflex_lb21p0_dur1_evt1_paper_day_ahead.json",
        "#b45309",
    ),
)


def build_fig_01_use_case_shift_boiler() -> Path:
    """Build the paper-local use-case comparison figure."""

    ref_series = _evaluate_case_timeseries(REFERENCE_OVERRIDE)
    case_series = []
    for label, override_path, color in CASE_SPECS:
        series = _evaluate_case_timeseries(override_path)
        case_series.append(
            {
                "label": label,
                "color": color,
                "series": series,
            }
        )

    ref_hours = np.arange(len(ref_series["timestamps"]), dtype=int)
    ref_time = pd.DatetimeIndex(ref_series["timestamps"])
    if len(ref_hours) != 24:
        raise ValueError(
            f"[build_fig_01_use_case_shift_boiler] Expected 24 hourly points, got {len(ref_hours)}."
        )

    demand_ylim = _compute_demand_ylim(ref_series=ref_series, case_series=case_series)
    boiler_ylim = _compute_boiler_ylim(ref_series=ref_series, case_series=case_series)

    fig, axes = plt.subplots(2, 2, figsize=(14, 8), sharex=True)
    for row_idx, case in enumerate(case_series):
        left_ax = axes[row_idx, 0]
        right_ax = axes[row_idx, 1]
        label = case["label"]
        color = case["color"]
        series = case["series"]

        ref_space_heat_mw = np.asarray(ref_series["district_space_heat_demand"], dtype=float) / 1e3
        case_space_heat_mw = np.asarray(series["district_space_heat_demand"], dtype=float) / 1e3
        left_ax.plot(ref_hours, ref_space_heat_mw, color="#7f8c8d", linewidth=2.0, label="Reference")
        left_ax.plot(ref_hours, case_space_heat_mw, color=color, linewidth=2.0, label=label)
        left_ax.fill_between(
            ref_hours,
            ref_space_heat_mw,
            case_space_heat_mw,
            color=color,
            alpha=0.18,
            label="Shifted area",
        )
        left_ax.set_ylim(*demand_ylim)
        left_ax.set_ylabel("MW thermal", fontsize=11)
        left_ax.grid(True, axis="y", alpha=0.3)
        left_ax.set_title(f"{label}: district space-heat demand", fontsize=12)
        left_ax.tick_params(axis="both", labelsize=10)
        if row_idx == 0:
            left_ax.legend(loc="upper right", fontsize=9, frameon=False)

        ref_boiler_mw = ref_series["district_gas_boiler_generation"] / 1e3
        case_boiler_mw = series["district_gas_boiler_generation"] / 1e3
        boiler_cap_mw = float(ref_series["district_gas_boiler_cap_kw_th"]) / 1e3
        right_ax.plot(ref_hours, ref_boiler_mw, color="#7f8c8d", linewidth=2.0, label="Reference")
        right_ax.plot(ref_hours, case_boiler_mw, color=color, linewidth=2.0, label=label)
        right_ax.axhline(boiler_cap_mw, color="#1f2937", linestyle="--", linewidth=1.2, label="Capacity")
        right_ax.set_ylim(*boiler_ylim)
        right_ax.set_ylabel("MW thermal", fontsize=11)
        right_ax.grid(True, axis="y", alpha=0.3)
        right_ax.set_title(f"{label}: gas boiler dispatch", fontsize=12)
        right_ax.tick_params(axis="both", labelsize=10)
        if row_idx == 0:
            right_ax.legend(loc="upper right", fontsize=9, frameon=False)

    tick_labels = [ts.strftime("%H:%M") for ts in ref_time]
    for ax in axes[-1, :]:
        ax.set_xticks(ref_hours[::3])
        ax.set_xticklabels(tick_labels[::3], fontsize=10)
        ax.set_xlabel("Hour of day", fontsize=11)

    fig.tight_layout()
    fig.savefig(OUTPUT_PATH, dpi=180, bbox_inches="tight")
    plt.close(fig)
    return OUTPUT_PATH


def _compute_demand_ylim(*, ref_series: dict[str, object], case_series: list[dict[str, object]]) -> tuple[float, float]:
    lower = float(np.min(np.asarray(ref_series["district_space_heat_demand"], dtype=float) / 1e3))
    upper = float(np.max(np.asarray(ref_series["district_space_heat_demand"], dtype=float) / 1e3))
    for case in case_series:
        series = case["series"]
        demand = np.asarray(series["district_space_heat_demand"], dtype=float) / 1e3
        lower = min(lower, float(np.min(demand)))
        upper = max(upper, float(np.max(demand)))
    span = upper - lower
    pad = 0.08 * span if span > 0.0 else 0.1
    return (lower - pad, upper + pad)


def _compute_boiler_ylim(*, ref_series: dict[str, object], case_series: list[dict[str, object]]) -> tuple[float, float]:
    upper = float(np.max(np.asarray(ref_series["district_gas_boiler_generation"], dtype=float)) / 1e3)
    upper = max(upper, float(ref_series["district_gas_boiler_cap_kw_th"]) / 1e3)
    for case in case_series:
        series = case["series"]
        upper = max(upper, float(np.max(np.asarray(series["district_gas_boiler_generation"], dtype=float)) / 1e3))
    return (0.0, upper * 1.05)


if __name__ == "__main__":
    print(build_fig_01_use_case_shift_boiler())
