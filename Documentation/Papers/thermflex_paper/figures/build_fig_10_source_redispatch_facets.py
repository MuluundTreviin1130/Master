from __future__ import annotations

"""Build a facet figure for Thermflex source redispatch on representative days.

The intent is to show a new paper-level mechanism that is not yet explicit in
the current active figures:
- whether the gas peak boiler is displaced within the day,
- whether gas-CHP heat becomes smoother / more levelled on strong savings days,
- and where this mechanism is absent on cold contrast days.

The figure reuses the same Gold re-evaluation helper path as the other paper
figures, so the plotted hourly series come from the same official day-ahead
dispatch evaluation rather than from ad-hoc postprocessing.
"""

from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[4]
project_root_str = str(PROJECT_ROOT.resolve())
if project_root_str not in sys.path:
    sys.path.insert(0, project_root_str)

from Documentation.Papers.thermflex_paper.figures.build_fig_02_representative_upper_only_shift import (  # noqa: E402
    PLOT_HOURS,
    REFERENCE_OVERRIDE,
    _evaluate_day_slice,
    _smooth_series,
)

import matplotlib  # noqa: E402

matplotlib.use("Agg", force=True)
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402


OVERRIDE_DIR = (
    PROJECT_ROOT
    / "Optimization"
    / "validation"
    / "model_validation"
    / "overrides"
    / "thermflex"
)
UPPER_ONLY_DUR24_OVERRIDE = (
    OVERRIDE_DIR
    / "vienna_ref2023_dh_baseline_constant_thermflex_lb22p5_dur24_evt24_upper_only_paper_day_ahead.json"
)
OUTPUT_PATH = Path(__file__).resolve().parent / "fig_10_source_redispatch_facets.png"
OUTPUT_DATA = Path(__file__).resolve().parent / "fig_10_source_redispatch_facets.csv"

CASE_SPECS = (
    {
        "title": "Cold contrast",
        "date": "2023-01-17",
        "note": "Almost no useful source-side reshaping",
        "color": "#1d4ed8",
    },
    {
        "title": "Winter savings day",
        "date": "2023-02-21",
        "note": "Boiler relief with visible source shifting",
        "color": "#b45309",
    },
    {
        "title": "Peak-kink day",
        "date": "2023-03-23",
        "note": "Boiler energy drops, but the absolute peak hour can still move",
        "color": "#d97706",
    },
    {
        "title": "Top savings day",
        "date": "2023-11-04",
        "note": "Strong boiler relief with smooth CHP support",
        "color": "#059669",
    },
)

BOILER_KEY = "district_gas_boiler_generation"
CHP_KEY = "district_gas_chp_thermal_generation"


def build_fig_10_source_redispatch_facets() -> Path:
    panel_payloads: list[dict[str, object]] = []
    summary_rows: list[dict[str, object]] = []

    for case in CASE_SPECS:
        ref_series = _evaluate_day_slice(REFERENCE_OVERRIDE, case["date"])
        flex_series = _evaluate_day_slice(UPPER_ONLY_DUR24_OVERRIDE, case["date"])
        panel_payloads.append({"case": case, "ref_series": ref_series, "flex_series": flex_series})
        summary_rows.append(_build_summary_row(case=case, ref_series=ref_series, flex_series=flex_series))

    pd.DataFrame(summary_rows).to_csv(OUTPUT_DATA, index=False)

    boiler_ylim = _compute_shared_ylim(panel_payloads, key=BOILER_KEY, anchor_zero=True)
    chp_ylim = _compute_shared_ylim(panel_payloads, key=CHP_KEY, anchor_zero=False)

    fig, axes = plt.subplots(len(CASE_SPECS), 2, figsize=(14.4, 12.8), sharex=True, sharey="col")
    if len(CASE_SPECS) == 1:
        axes = np.asarray([axes], dtype=object)

    for row_idx, payload in enumerate(panel_payloads):
        case = payload["case"]
        ref_series = payload["ref_series"]
        flex_series = payload["flex_series"]
        hours = np.arange(PLOT_HOURS, dtype=int)
        timestamps = pd.DatetimeIndex(ref_series["timestamps"][:PLOT_HOURS])

        ref_boiler = _series_mw(ref_series, BOILER_KEY)
        flex_boiler = _series_mw(flex_series, BOILER_KEY)
        ref_chp = _series_mw(ref_series, CHP_KEY)
        flex_chp = _series_mw(flex_series, CHP_KEY)

        ax_boiler = axes[row_idx, 0]
        ax_chp = axes[row_idx, 1]

        _plot_series_panel(
            ax=ax_boiler,
            hours=hours,
            ref_values=ref_boiler,
            flex_values=flex_boiler,
            color=str(case["color"]),
            title=f"{case['title']} ({case['date']})",
            subtitle=str(case["note"]),
            ylabel="Gas peak boiler [MW thermal]",
            ylim=boiler_ylim,
            delta_text=_build_delta_text(ref_boiler, flex_boiler, "boiler", use_shape_text=True),
        )
        _plot_series_panel(
            ax=ax_chp,
            hours=hours,
            ref_values=ref_chp,
            flex_values=flex_chp,
            color=str(case["color"]),
            title="",
            subtitle="",
            ylabel="Gas CHP heat [MW thermal]",
            ylim=chp_ylim,
            delta_text=_build_delta_text(ref_chp, flex_chp, "CHP", use_shape_text=False),
        )

        tick_labels = [ts.strftime("%H:%M") for ts in timestamps]
        ax_boiler.set_xticks(hours[::3])
        ax_boiler.set_xticklabels(tick_labels[::3], fontsize=9)
        ax_chp.set_xticks(hours[::3])
        ax_chp.set_xticklabels(tick_labels[::3], fontsize=9)

        if row_idx == 0:
            ax_boiler.set_title("A) Peak-boiler redispatch", loc="left", fontsize=12, fontweight="bold")
            ax_chp.set_title("B) Gas-CHP thermal redispatch", loc="left", fontsize=12, fontweight="bold")

    axes[-1, 0].set_xlabel("Hour of day", fontsize=11)
    axes[-1, 1].set_xlabel("Hour of day", fontsize=11)

    fig.suptitle("Source-side Thermflex redispatch on representative upper-only days", fontsize=15, fontweight="bold")
    fig.text(
        0.08,
        0.035,
        "Reference vs. upper-only, 24 h day proxy. Filled area marks intra-day redispatch relative to the reference path.",
        fontsize=9,
        color="#374151",
    )
    fig.tight_layout(rect=(0.0, 0.05, 1.0, 0.95))
    fig.savefig(OUTPUT_PATH, dpi=180, bbox_inches="tight")
    plt.close(fig)
    return OUTPUT_PATH


def _series_mw(series: dict[str, object], key: str) -> np.ndarray:
    values = np.asarray(series[key][:PLOT_HOURS], dtype=float) / 1000.0
    return _smooth_series(values)


def _compute_shared_ylim(
    panel_payloads: list[dict[str, object]], *, key: str, anchor_zero: bool
) -> tuple[float, float]:
    lower = float("inf")
    upper = float("-inf")
    for payload in panel_payloads:
        ref_values = _series_mw(payload["ref_series"], key)
        flex_values = _series_mw(payload["flex_series"], key)
        lower = min(lower, float(np.min(ref_values)), float(np.min(flex_values)))
        upper = max(upper, float(np.max(ref_values)), float(np.max(flex_values)))
    span = max(0.1, upper - lower)
    pad = 0.10 * span
    if anchor_zero and lower >= 0.0:
        return (0.0, upper + pad)
    return (lower - pad, upper + pad)


def _plot_series_panel(
    *,
    ax: plt.Axes,
    hours: np.ndarray,
    ref_values: np.ndarray,
    flex_values: np.ndarray,
    color: str,
    title: str,
    subtitle: str,
    ylabel: str,
    ylim: tuple[float, float],
    delta_text: str,
) -> None:
    ax.plot(hours, ref_values, color="#9ca3af", linewidth=2.0, label="Reference")
    ax.plot(hours, flex_values, color=color, linewidth=2.1, label="Upper-only dur24")
    ax.fill_between(hours, ref_values, flex_values, where=flex_values <= ref_values, color="#10b981", alpha=0.20)
    ax.fill_between(hours, ref_values, flex_values, where=flex_values > ref_values, color="#f59e0b", alpha=0.16)
    ax.set_ylim(*ylim)
    ax.set_ylabel(ylabel, fontsize=10)
    ax.grid(True, axis="y", alpha=0.24)
    ax.tick_params(axis="both", labelsize=9)
    if title:
        ax.text(
            0.00,
            0.98,
            title,
            transform=ax.transAxes,
            ha="left",
            va="top",
            fontsize=10.8,
            fontweight="bold",
            color="#111827",
        )
    if subtitle:
        ax.text(
            0.00,
            0.90,
            subtitle,
            transform=ax.transAxes,
            ha="left",
            va="top",
            fontsize=9,
            color="#374151",
        )
    ax.text(
        0.98,
        0.92,
        delta_text,
        transform=ax.transAxes,
        ha="right",
        va="top",
        fontsize=8.8,
        color="#374151",
        bbox={"boxstyle": "round,pad=0.22", "facecolor": "white", "edgecolor": "#d1d5db", "alpha": 0.90},
    )


def _build_delta_text(
    ref_values: np.ndarray,
    flex_values: np.ndarray,
    label: str,
    *,
    use_shape_text: bool,
) -> str:
    ref_energy = float(np.sum(ref_values))
    flex_energy = float(np.sum(flex_values))
    if abs(ref_energy) < 1e-9:
        pct = np.nan
    else:
        pct = 100.0 * (flex_energy - ref_energy) / ref_energy
    ramp_ref = float(np.std(ref_values))
    ramp_flex = float(np.std(flex_values))
    ramp_delta = ramp_flex - ramp_ref
    if np.isfinite(pct):
        if use_shape_text:
            ramp_text = "flatter" if ramp_flex < ramp_ref else "not flatter"
            return f"daily {label} Δ {pct:+.1f}%\nshape: {ramp_text}"
        return f"daily {label} Δ {pct:+.1f}%\nσ Δ {ramp_delta:+.2f} MW"
    if use_shape_text:
        return f"daily {label} Δ n/a\nshape: n/a"
    return f"daily {label} Δ n/a\nσ Δ n/a"


def _build_summary_row(
    *,
    case: dict[str, object],
    ref_series: dict[str, object],
    flex_series: dict[str, object],
) -> dict[str, object]:
    ref_boiler = np.asarray(ref_series[BOILER_KEY][:PLOT_HOURS], dtype=float)
    flex_boiler = np.asarray(flex_series[BOILER_KEY][:PLOT_HOURS], dtype=float)
    ref_chp = np.asarray(ref_series[CHP_KEY][:PLOT_HOURS], dtype=float)
    flex_chp = np.asarray(flex_series[CHP_KEY][:PLOT_HOURS], dtype=float)
    return {
        "date": str(case["date"]),
        "title": str(case["title"]),
        "boiler_ref_mwh": float(np.sum(ref_boiler) / 1000.0),
        "boiler_upper_mwh": float(np.sum(flex_boiler) / 1000.0),
        "boiler_change_pct": _pct_change(np.sum(flex_boiler), np.sum(ref_boiler)),
        "boiler_peak_ref_mw": float(np.max(ref_boiler) / 1000.0),
        "boiler_peak_upper_mw": float(np.max(flex_boiler) / 1000.0),
        "boiler_peak_change_pct": _pct_change(np.max(flex_boiler), np.max(ref_boiler)),
        "gas_chp_heat_ref_mwh": float(np.sum(ref_chp) / 1000.0),
        "gas_chp_heat_upper_mwh": float(np.sum(flex_chp) / 1000.0),
        "gas_chp_heat_change_pct": _pct_change(np.sum(flex_chp), np.sum(ref_chp)),
        "gas_chp_heat_std_ref_mw": float(np.std(ref_chp) / 1000.0),
        "gas_chp_heat_std_upper_mw": float(np.std(flex_chp) / 1000.0),
    }


def _pct_change(new_value: float, ref_value: float) -> float:
    ref = float(ref_value)
    if abs(ref) < 1e-9:
        return float("nan")
    return 100.0 * (float(new_value) - ref) / ref


if __name__ == "__main__":
    print(build_fig_10_source_redispatch_facets())
