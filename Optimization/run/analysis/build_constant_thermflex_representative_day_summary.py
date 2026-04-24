from __future__ import annotations

"""Build a compact cross-day summary for representative-day sensitivity runs."""

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

CORE_COLUMNS = (
    "day_label",
    "date",
    "case_label",
    "dispatch_operating_cost_eur",
    "co2_emissions_total_t",
    "dh_unserved_heat_kwh",
    "thermflex_shifted_space_heat_kwh",
    "thermflex_rebound_kwh",
    "thermflex_peak_change_kw",
    "run_dir",
)


def build_constant_thermflex_representative_day_summary(
    *,
    output_dir: Path,
    run_rows: list[dict[str, Any]],
) -> Path:
    output_dir = Path(output_dir).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    table = pd.DataFrame(run_rows)
    missing = [col for col in CORE_COLUMNS if col not in table.columns]
    if missing:
        raise KeyError(
            "[representative_day_summary] Missing required run summary columns: "
            + ", ".join(missing)
        )

    table["case_label"] = pd.Categorical(table["case_label"], categories=list(CASE_ORDER), ordered=True)
    table = table.sort_values(["day_label", "case_label"]).reset_index(drop=True)
    table.to_csv(output_dir / "representative_day_case_summary.csv", index=False)
    (output_dir / "representative_day_case_summary.json").write_text(
        json.dumps(table.to_dict(orient="records"), indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    _write_markdown(output_dir=output_dir, table=table)
    _save_plot(output_dir=output_dir, table=table)
    return output_dir


def _write_markdown(*, output_dir: Path, table: pd.DataFrame) -> None:
    lines = [
        "# Constant Thermflex Representative-Day Summary",
        "",
    ]
    for day_label in table["day_label"].astype(str).unique():
        subset = table[table["day_label"].astype(str) == day_label].copy()
        subset = subset.sort_values("dispatch_operating_cost_eur")
        best_cost = subset.iloc[0]
        best_co2 = subset.sort_values("co2_emissions_total_t").iloc[0]
        best_shift = subset.sort_values("thermflex_shifted_space_heat_kwh", ascending=False).iloc[0]
        lines.extend(
            [
                f"## {day_label}",
                "",
                f"- Date: `{best_cost['date']}`",
                f"- Best operating cost: `{best_cost['case_label']}` -> `{float(best_cost['dispatch_operating_cost_eur']):.0f} EUR`",
                f"- Best CO2: `{best_co2['case_label']}` -> `{float(best_co2['co2_emissions_total_t']):.2f} t`",
                f"- Most shifted heat: `{best_shift['case_label']}` -> `{float(best_shift['thermflex_shifted_space_heat_kwh']) / 1e3:.2f} MWh`",
                "",
            ]
        )
    (output_dir / "representative_day_case_summary.md").write_text(
        "\n".join(lines),
        encoding="utf-8",
    )


def _save_plot(*, output_dir: Path, table: pd.DataFrame) -> None:
    fig, axes = plt.subplots(3, 1, figsize=(15, 12), sharex=True)
    case_labels = list(CASE_ORDER)

    for day_label in table["day_label"].astype(str).unique():
        subset = table[table["day_label"].astype(str) == day_label].copy()
        subset = subset.set_index("case_label").reindex(case_labels)
        axes[0].plot(case_labels, subset["dispatch_operating_cost_eur"] / 1e6, marker="o", label=day_label)
        axes[1].plot(case_labels, subset["co2_emissions_total_t"], marker="o", label=day_label)
        axes[2].plot(case_labels, subset["thermflex_shifted_space_heat_kwh"] / 1e3, marker="o", label=day_label)

    axes[0].set_ylabel("Operating cost [MEUR]")
    axes[0].set_title("Operating cost by day and policy")
    axes[1].set_ylabel("CO2 [t]")
    axes[1].set_title("CO2 by day and policy")
    axes[2].set_ylabel("Shifted heat [MWh]")
    axes[2].set_title("Shifted heat by day and policy")

    for ax in axes:
        ax.grid(True, alpha=0.25)
        ax.legend(loc="best", fontsize=8)

    axes[2].tick_params(axis="x", rotation=25)
    fig.tight_layout()
    fig.savefig(output_dir / "representative_day_case_summary.png", dpi=180, bbox_inches="tight")
    plt.close(fig)
