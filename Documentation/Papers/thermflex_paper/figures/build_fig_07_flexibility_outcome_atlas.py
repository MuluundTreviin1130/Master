from __future__ import annotations

"""Build a compact KPI atlas for the active upper-only dur24 day set.

The atlas is intentionally sourced from the paper table instead of embedding
numbers in the plotting code. This keeps the figure tied to the current
reported KPI layer and makes stale values fail visibly when table columns
change.
"""

from pathlib import Path
import re
import unicodedata

import matplotlib

matplotlib.use("Agg", force=True)
import matplotlib.pyplot as plt
from matplotlib.colors import TwoSlopeNorm
import numpy as np
import pandas as pd


PAPER_DIR = Path(__file__).resolve().parents[1]
TABLE_PATH = PAPER_DIR / "tables" / "table_09_tradeoff_day_summary_upper_only_dur24.md"
FIGURE_DIR = Path(__file__).resolve().parent
OUTPUT_PATH = FIGURE_DIR / "fig_07_flexibility_outcome_atlas.png"
OUTPUT_DATA = FIGURE_DIR / "fig_07_flexibility_outcome_atlas.csv"

IMPROVEMENT_COLUMNS = {
    "Cost": "cost_change",
    "CO2": "co2_change",
    "Boiler energy": "boiler_energy_change",
    "Boiler peak": "boiler_peak_change",
}


def build_fig_07_flexibility_outcome_atlas() -> Path:
    """Render the atlas and export the parsed plotting data."""

    raw = _read_markdown_table(TABLE_PATH)
    kpi = _prepare_kpi_frame(raw)
    kpi.to_csv(OUTPUT_DATA, index=False)
    _save_plot(kpi)
    return OUTPUT_PATH


def _read_markdown_table(path: Path) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(f"[fig_07] Required table missing: {path}")

    table_lines = [line for line in path.read_text(encoding="utf-8").splitlines() if line.startswith("|")]
    if len(table_lines) < 3:
        raise ValueError(f"[fig_07] No markdown table found in {path}")

    header = [_clean_cell(cell) for cell in table_lines[0].strip().strip("|").split("|")]
    rows: list[list[str]] = []
    for line in table_lines[2:]:
        cells = [_clean_cell(cell) for cell in line.strip().strip("|").split("|")]
        if len(cells) != len(header):
            raise ValueError(
                f"[fig_07] Row has {len(cells)} cells but header has {len(header)} cells: {line}"
            )
        rows.append(cells)

    frame = pd.DataFrame(rows, columns=[_normalize_header(column) for column in header])
    expected = {
        "date",
        "day_type",
        "cost_change",
        "co2_change",
        "boiler_energy_change",
        "boiler_peak_change",
        "shifted_heat_mwh",
        "rebound_shifted",
        "max_t_in_above_setpoint_k",
    }
    missing = sorted(expected.difference(frame.columns))
    if missing:
        raise KeyError("[fig_07] Table 09 missing required columns: " + ", ".join(missing))
    return frame


def _prepare_kpi_frame(raw: pd.DataFrame) -> pd.DataFrame:
    data = raw.copy()
    for column in (
        "cost_change",
        "co2_change",
        "boiler_energy_change",
        "boiler_peak_change",
        "shifted_heat_mwh",
        "rebound_shifted",
        "max_t_in_above_setpoint_k",
    ):
        data[column] = data[column].map(_parse_number)

    rows: list[dict[str, object]] = []
    for _, row in data.iterrows():
        for label, source_column in IMPROVEMENT_COLUMNS.items():
            # Negative change means lower cost, CO2, boiler energy, or peak.
            # The atlas therefore reports the sign-flipped improvement.
            rows.append(
                {
                    "date": str(row["date"]),
                    "day_type": str(row["day_type"]),
                    "metric": label,
                    "improvement_pct": -float(row[source_column]),
                    "original_change_pct": float(row[source_column]),
                    "shifted_heat_mwh": float(row["shifted_heat_mwh"]),
                    "rebound_over_shifted_pct": float(row["rebound_shifted"])
                    if np.isfinite(row["rebound_shifted"])
                    else np.nan,
                    "max_tin_above_setpoint_k": float(row["max_t_in_above_setpoint_k"]),
                }
            )
    return pd.DataFrame(rows)


def _save_plot(kpi: pd.DataFrame) -> None:
    days = list(dict.fromkeys(kpi["date"].astype(str)))
    metrics = list(IMPROVEMENT_COLUMNS)
    matrix = np.full((len(days), len(metrics)), np.nan, dtype=float)
    annotations = np.empty((len(days), len(metrics)), dtype=object)

    for day_index, day in enumerate(days):
        for metric_index, metric in enumerate(metrics):
            item = kpi.loc[(kpi["date"] == day) & (kpi["metric"] == metric)]
            if len(item) != 1:
                raise ValueError(f"[fig_07] Expected one KPI row for {day=} {metric=}, got {len(item)}")
            improvement = float(item["improvement_pct"].iloc[0])
            matrix[day_index, metric_index] = improvement
            annotations[day_index, metric_index] = f"{improvement:+.1f}"

    shifted = (
        kpi.drop_duplicates("date")
        .set_index("date")
        .loc[days, ["shifted_heat_mwh", "rebound_over_shifted_pct", "max_tin_above_setpoint_k"]]
    )

    fig = plt.figure(figsize=(12.8, 8.6))
    gs = fig.add_gridspec(
        nrows=1,
        ncols=3,
        width_ratios=[4.2, 1.25, 1.25],
        left=0.08,
        right=0.98,
        bottom=0.10,
        top=0.90,
        wspace=0.22,
    )
    ax_heat = fig.add_subplot(gs[0, 0])
    ax_shift = fig.add_subplot(gs[0, 1], sharey=ax_heat)
    ax_rebound = fig.add_subplot(gs[0, 2], sharey=ax_heat)

    finite = matrix[np.isfinite(matrix)]
    max_abs = max(1.0, float(np.max(np.abs(finite))))
    norm = TwoSlopeNorm(vmin=-max_abs, vcenter=0.0, vmax=max_abs)
    image = ax_heat.imshow(matrix, aspect="auto", cmap="RdYlGn", norm=norm)

    ax_heat.set_xticks(np.arange(len(metrics)))
    ax_heat.set_xticklabels(metrics, fontsize=10)
    ax_heat.set_yticks(np.arange(len(days)))
    ax_heat.set_yticklabels(_build_day_labels(kpi, days), fontsize=9)
    ax_heat.set_title("A) KPI improvement vs. reference [%]", loc="left", fontsize=12, fontweight="bold")
    ax_heat.tick_params(axis="both", length=0)

    for day_index in range(len(days)):
        for metric_index in range(len(metrics)):
            value = matrix[day_index, metric_index]
            text_color = "white" if abs(value) > 0.62 * max_abs else "#111827"
            ax_heat.text(
                metric_index,
                day_index,
                annotations[day_index, metric_index],
                ha="center",
                va="center",
                color=text_color,
                fontsize=9,
                fontweight="bold",
            )

    ax_heat.set_xticks(np.arange(-0.5, len(metrics), 1), minor=True)
    ax_heat.set_yticks(np.arange(-0.5, len(days), 1), minor=True)
    ax_heat.grid(which="minor", color="white", linewidth=1.4)
    ax_heat.tick_params(which="minor", bottom=False, left=False)

    y_pos = np.arange(len(days))
    ax_shift.barh(y_pos, shifted["shifted_heat_mwh"], color="#2563eb", alpha=0.84)
    ax_shift.set_title("B) Shifted heat\n[MWh/day]", loc="left", fontsize=11, fontweight="bold")
    ax_shift.grid(True, axis="x", alpha=0.22)
    ax_shift.tick_params(axis="y", left=False, labelleft=False)
    ax_shift.invert_yaxis()

    ax_rebound.scatter(
        shifted["rebound_over_shifted_pct"],
        y_pos,
        s=np.maximum(32.0, shifted["max_tin_above_setpoint_k"].to_numpy(dtype=float) * 42.0),
        color="#7c2d12",
        alpha=0.82,
        edgecolor="white",
        linewidth=0.7,
    )
    ax_rebound.axvline(100.0, color="#111827", linewidth=0.8, linestyle=":")
    ax_rebound.set_title("C) Rebound / shifted\n[%]", loc="left", fontsize=11, fontweight="bold")
    ax_rebound.grid(True, axis="x", alpha=0.22)
    ax_rebound.tick_params(axis="y", left=False, labelleft=False)

    colorbar = fig.colorbar(image, ax=ax_heat, fraction=0.045, pad=0.02)
    colorbar.set_label("Improvement [%]; green = lower system burden", fontsize=9)

    fig.suptitle("Flexibility outcome atlas for upper-only, 24 h day proxy", fontsize=14, fontweight="bold")
    fig.text(
        0.08,
        0.035,
        "Negative original changes are sign-flipped for the heatmap. Dot size in C scales with max indoor-temperature rise.",
        fontsize=9,
        color="#374151",
    )
    fig.savefig(OUTPUT_PATH, dpi=180, bbox_inches="tight")
    plt.close(fig)


def _build_day_labels(kpi: pd.DataFrame, days: list[str]) -> list[str]:
    labels: list[str] = []
    lookup = kpi.drop_duplicates("date").set_index("date")["day_type"].to_dict()
    for day in days:
        labels.append(f"{day}\n{lookup[day]}")
    return labels


def _clean_cell(cell: str) -> str:
    return cell.strip().replace("`", "")


def _normalize_header(header: str) -> str:
    ascii_header = unicodedata.normalize("NFKD", header).encode("ascii", "ignore").decode("ascii")
    return re.sub(r"[^a-z0-9]+", "_", ascii_header.lower()).strip("_")


def _parse_number(value: object) -> float:
    text = str(value).strip()
    if text.lower() in {"n/a", "na", ""}:
        return float("nan")
    cleaned = text.replace("%", "").replace("+", "").replace(",", "")
    return float(cleaned)


if __name__ == "__main__":
    print(build_fig_07_flexibility_outcome_atlas())
