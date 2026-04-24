from __future__ import annotations

"""Build a compact sensitivity comparison for constant-reference thermflex cases.

This analysis stays intentionally simple:
- it consumes the official `paper_dispatch_comparison.csv`,
- it requires explicit case labels and KPI columns,
- it produces one compact summary plus one compact plot sheet.

The goal is not a generic plotting framework. The goal is one explicit paper
artifact for the "constant thermflex settings sensitivity" question.
"""

import json
from pathlib import Path
from typing import Any

import matplotlib
import pandas as pd

matplotlib.use("Agg", force=True)
import matplotlib.pyplot as plt


CASE_ORDER = (
    "constant_no_thermflex",
    "lb21p0_dur1_evt1",
    "lb21p0_dur2_evt1",
    "lb21p0_dur4_evt1",
    "lb21p0_dur6_evt1",
    "lb21p0_dur8_evt1",
    "lb21p0_dur24_evt1",
    "lb21p0_dur24_evt24",
    "lb22p5_dur4_evt1_upper_only",
    "lb22p5_dur24_evt24_upper_only_proxy",
    "lb21p5_dur4_evt1",
    "lb20p0_dur4_evt1",
    "lb21p0_dur4_evt2",
)

REQUIRED_COLUMNS = (
    "dispatch_operating_cost_eur",
    "co2_emissions_total_t",
    "dh_unserved_heat_kwh",
    "thermflex_shifted_space_heat_kwh",
    "thermflex_rebound_kwh",
    "thermflex_peak_change_kw",
    "thermflex_constant_lower_bound_c",
    "thermflex_max_flex_duration_h",
    "thermflex_max_events_per_day",
)


def build_constant_thermflex_sensitivity_bundle(output_dir: Path) -> Path:
    output_dir = Path(output_dir).resolve()
    comparison_csv = output_dir / "paper_dispatch_comparison.csv"
    if not comparison_csv.exists():
        raise FileNotFoundError(
            f"[constant_thermflex_sensitivity] paper_dispatch_comparison.csv not found: {comparison_csv}"
        )

    df = pd.read_csv(comparison_csv)
    if "case_label" not in df.columns:
        raise KeyError("[constant_thermflex_sensitivity] case_label missing in paper comparison csv.")
    df = df.set_index("case_label")

    missing_cases = [label for label in CASE_ORDER if label not in df.index]
    if missing_cases:
        raise KeyError(
            "[constant_thermflex_sensitivity] Required cases missing in paper comparison csv: "
            + ", ".join(missing_cases)
        )

    missing_cols = [col for col in REQUIRED_COLUMNS if col not in df.columns]
    if missing_cols:
        raise KeyError(
            "[constant_thermflex_sensitivity] Required KPI columns missing in paper comparison csv: "
            + ", ".join(missing_cols)
        )

    ordered = df.loc[list(CASE_ORDER)].copy()
    summary = _build_summary(ordered)
    _write_summary(output_dir=output_dir, ordered=ordered, summary=summary)
    _save_plot(output_dir=output_dir, ordered=ordered)
    return output_dir


def _pct_delta(value: float, baseline: float) -> float | None:
    if abs(baseline) < 1e-12:
        return None
    return float(100.0 * (value - baseline) / baseline)


def _build_summary(df: pd.DataFrame) -> dict[str, Any]:
    baseline = df.loc["constant_no_thermflex"]
    cases: dict[str, Any] = {}

    # Each case summary keeps both the explicit setting triplet and the key KPI
    # deltas versus the no-thermflex baseline. This keeps the export readable and
    # avoids a second hidden source for the settings metadata.
    for label, row in df.iterrows():
        cases[str(label)] = {
            "settings": {
                "constant_lower_bound_c": float(row["thermflex_constant_lower_bound_c"]),
                "max_flex_duration_h": int(row["thermflex_max_flex_duration_h"]),
                "max_flex_events_per_day": int(row["thermflex_max_events_per_day"]),
            },
            "kpis": {
                "dispatch_operating_cost_eur": float(row["dispatch_operating_cost_eur"]),
                "co2_emissions_total_t": float(row["co2_emissions_total_t"]),
                "dh_unserved_heat_kwh": float(row["dh_unserved_heat_kwh"]),
                "thermflex_shifted_space_heat_kwh": float(row["thermflex_shifted_space_heat_kwh"]),
                "thermflex_rebound_kwh": float(row["thermflex_rebound_kwh"]),
                "thermflex_peak_change_kw": float(row["thermflex_peak_change_kw"]),
            },
        }
        if label == "constant_no_thermflex":
            continue
        cases[str(label)]["delta_vs_constant_no_thermflex"] = {
            "dispatch_operating_cost_eur": float(row["dispatch_operating_cost_eur"] - baseline["dispatch_operating_cost_eur"]),
            "dispatch_operating_cost_pct": _pct_delta(
                float(row["dispatch_operating_cost_eur"]),
                float(baseline["dispatch_operating_cost_eur"]),
            ),
            "co2_emissions_total_t": float(row["co2_emissions_total_t"] - baseline["co2_emissions_total_t"]),
            "co2_emissions_total_pct": _pct_delta(
                float(row["co2_emissions_total_t"]),
                float(baseline["co2_emissions_total_t"]),
            ),
            "dh_unserved_heat_kwh": float(row["dh_unserved_heat_kwh"] - baseline["dh_unserved_heat_kwh"]),
        }

    # The dispatch export uses one explicit settings column for the allowed
    # event count. The analysis reads that column directly instead of guessing a
    # second alias, so schema mismatches fail immediately.
    duration_slice = df[
        (df["thermflex_constant_lower_bound_c"] == 21.0)
        & (df["thermflex_max_events_per_day"] == 1)
        & (df.index != "constant_no_thermflex")
    ].sort_values("thermflex_max_flex_duration_h")
    duration_trend = [
        {
            "duration_h": int(row["thermflex_max_flex_duration_h"]),
            "dispatch_operating_cost_eur": float(row["dispatch_operating_cost_eur"]),
            "co2_emissions_total_t": float(row["co2_emissions_total_t"]),
            "thermflex_shifted_space_heat_kwh": float(row["thermflex_shifted_space_heat_kwh"]),
            "thermflex_rebound_kwh": float(row["thermflex_rebound_kwh"]),
            "thermflex_peak_change_kw": float(row["thermflex_peak_change_kw"]),
        }
        for _, row in duration_slice.iterrows()
    ]

    return {
        "baseline_case": "constant_no_thermflex",
        "cases": cases,
        "duration_trend_lb21_evt1": duration_trend,
    }


def _write_summary(*, output_dir: Path, ordered: pd.DataFrame, summary: dict[str, Any]) -> None:
    json_path = output_dir / "constant_thermflex_sensitivity_summary.json"
    md_path = output_dir / "constant_thermflex_sensitivity_summary.md"
    json_path.write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")

    lines = [
        "# Constant Thermflex Sensitivity Summary",
        "",
        "Compared cases:",
    ]
    for label, row in ordered.iterrows():
        lines.append(
            "- "
            f"`{label}`: "
            f"`lower={float(row['thermflex_constant_lower_bound_c']):.1f} C`, "
            f"`duration={int(row['thermflex_max_flex_duration_h'])} h`, "
            f"`events={int(row['thermflex_max_events_per_day'])}`"
        )

    lines.extend(
        [
            "",
            "Duration trend for `lower=21.0 C`, `events=1`:",
        ]
    )
    for item in summary["duration_trend_lb21_evt1"]:
        lines.append(
            "- "
            f"`duration={item['duration_h']} h`: "
            f"`op_cost={item['dispatch_operating_cost_eur']:.0f} EUR`, "
            f"`co2={item['co2_emissions_total_t']:.2f} t`, "
            f"`shifted={item['thermflex_shifted_space_heat_kwh'] / 1e3:.2f} MWh`, "
            f"`rebound={item['thermflex_rebound_kwh'] / 1e3:.2f} MWh`, "
            f"`peak_change={item['thermflex_peak_change_kw'] / 1e3:.2f} MW`"
        )

    md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _save_plot(*, output_dir: Path, ordered: pd.DataFrame) -> None:
    labels = ordered.index.astype(str).tolist()
    x = range(len(labels))

    fig, axes = plt.subplots(2, 2, figsize=(15, 10))

    axes[0, 0].bar(labels, ordered["dispatch_operating_cost_eur"] / 1e6, color="#c0392b")
    axes[0, 0].set_ylabel("EUR million / slice")
    axes[0, 0].set_title("Operating Cost")
    axes[0, 0].grid(True, axis="y", alpha=0.3)
    axes[0, 0].tick_params(axis="x", rotation=20)

    axes[0, 1].bar(labels, ordered["co2_emissions_total_t"], color="#16a085")
    axes[0, 1].set_ylabel("t CO2 / slice")
    axes[0, 1].set_title("Operational CO2")
    axes[0, 1].grid(True, axis="y", alpha=0.3)
    axes[0, 1].tick_params(axis="x", rotation=20)

    width = 0.35
    axes[1, 0].bar([i - width / 2 for i in x], ordered["thermflex_shifted_space_heat_kwh"] / 1e3, width=width, label="Shifted")
    axes[1, 0].bar([i + width / 2 for i in x], ordered["thermflex_rebound_kwh"] / 1e3, width=width, label="Rebound")
    axes[1, 0].set_xticks(list(x))
    axes[1, 0].set_xticklabels(labels, rotation=20, ha="right")
    axes[1, 0].set_ylabel("MWh / slice")
    axes[1, 0].set_title("Shifted vs Rebound")
    axes[1, 0].grid(True, axis="y", alpha=0.3)
    axes[1, 0].legend()

    axes[1, 1].bar(labels, ordered["thermflex_peak_change_kw"] / 1e3, color="#2c3e50")
    axes[1, 1].set_ylabel("MW / slice")
    axes[1, 1].set_title("Peak Change")
    axes[1, 1].grid(True, axis="y", alpha=0.3)
    axes[1, 1].tick_params(axis="x", rotation=20)

    fig.tight_layout()
    fig.savefig(output_dir / "constant_thermflex_sensitivity.png", dpi=180, bbox_inches="tight")
    plt.close(fig)
