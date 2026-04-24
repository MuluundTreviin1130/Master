from __future__ import annotations

"""Build a solar counterfactual figure for the Thermflex mechanism story."""

from pathlib import Path
import re
import unicodedata

import matplotlib

matplotlib.use("Agg", force=True)
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


PAPER_DIR = Path(__file__).resolve().parents[1]
TABLE_PATH = PAPER_DIR / "tables" / "table_04_preheat_timing_solar_contribution.md"
FIGURE_DIR = Path(__file__).resolve().parent
OUTPUT_PATH = FIGURE_DIR / "fig_08_solar_assisted_shift_counterfactual.png"
OUTPUT_DATA = FIGURE_DIR / "fig_08_solar_assisted_shift_counterfactual.csv"


def build_fig_08_solar_assisted_shift_counterfactual() -> Path:
    raw = _read_markdown_table(TABLE_PATH)
    data = _prepare_frame(raw)
    data.to_csv(OUTPUT_DATA, index=False)
    _save_plot(data)
    return OUTPUT_PATH


def _read_markdown_table(path: Path) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(f"[fig_08] Required table missing: {path}")

    lines = [line for line in path.read_text(encoding="utf-8").splitlines() if line.startswith("|")]
    if len(lines) < 3:
        raise ValueError(f"[fig_08] No markdown table found in {path}")
    header = [_clean_cell(cell) for cell in lines[0].strip().strip("|").split("|")]
    rows: list[list[str]] = []
    for line in lines[2:]:
        cells = [_clean_cell(cell) for cell in line.strip().strip("|").split("|")]
        if len(cells) != len(header):
            raise ValueError(
                f"[fig_08] Row has {len(cells)} cells but header has {len(header)} cells: {line}"
            )
        rows.append(cells)
    frame = pd.DataFrame(rows, columns=[_normalize_header(column) for column in header])
    expected = {
        "day",
        "midday_preheat_mwh",
        "evening_release_mwh",
        "cost_change_with_solar",
        "cost_change_without_solar",
        "co2_change_with_solar",
        "co2_change_without_solar",
    }
    missing = sorted(expected.difference(frame.columns))
    if missing:
        raise KeyError("[fig_08] Table 04 missing required columns: " + ", ".join(missing))
    return frame


def _prepare_frame(raw: pd.DataFrame) -> pd.DataFrame:
    data = raw.copy()
    for column in (
        "midday_preheat_mwh",
        "evening_release_mwh",
        "cost_change_with_solar",
        "cost_change_without_solar",
        "co2_change_with_solar",
        "co2_change_without_solar",
    ):
        data[column] = data[column].map(_parse_number)
    data["cost_solar_assist_pct_point"] = data["cost_change_without_solar"] - data["cost_change_with_solar"]
    data["co2_solar_assist_pct_point"] = data["co2_change_without_solar"] - data["co2_change_with_solar"]
    data["release_over_preheat_pct"] = 100.0 * data["evening_release_mwh"] / data["midday_preheat_mwh"]
    return data


def _save_plot(data: pd.DataFrame) -> None:
    days = data["day"].astype(str).to_list()
    x = np.arange(len(days), dtype=float)
    width = 0.34

    fig = plt.figure(figsize=(11.6, 7.8))
    gs = fig.add_gridspec(
        nrows=2,
        ncols=2,
        height_ratios=[1.08, 1.0],
        left=0.08,
        right=0.98,
        bottom=0.10,
        top=0.88,
        hspace=0.34,
        wspace=0.22,
    )
    ax_shift = fig.add_subplot(gs[0, 0])
    ax_benefit = fig.add_subplot(gs[0, 1])
    ax_delta = fig.add_subplot(gs[1, :])

    ax_shift.bar(
        x - width / 2,
        data["midday_preheat_mwh"],
        width=width,
        color="#f97316",
        alpha=0.86,
        label="midday preheat",
    )
    ax_shift.bar(
        x + width / 2,
        data["evening_release_mwh"],
        width=width,
        color="#0f766e",
        alpha=0.86,
        label="evening release",
    )
    ax_shift.set_title("A) Mechanical heat shift around solar hours", loc="left", fontsize=12, fontweight="bold")
    ax_shift.set_ylabel("Heat delta [MWh]")
    ax_shift.set_xticks(x)
    ax_shift.set_xticklabels(days)
    ax_shift.grid(True, axis="y", alpha=0.22)
    ax_shift.legend(frameon=False, fontsize=9)

    for index, row in data.iterrows():
        ax_shift.text(
            x[index],
            max(row["midday_preheat_mwh"], row["evening_release_mwh"]) * 1.04,
            f"{row['release_over_preheat_pct']:.0f}%",
            ha="center",
            va="bottom",
            fontsize=9,
            color="#374151",
        )

    benefit_metrics = ("cost", "co2")
    with_solar = np.vstack(
        [
            -data["cost_change_with_solar"].to_numpy(dtype=float),
            -data["co2_change_with_solar"].to_numpy(dtype=float),
        ]
    )
    without_solar = np.vstack(
        [
            -data["cost_change_without_solar"].to_numpy(dtype=float),
            -data["co2_change_without_solar"].to_numpy(dtype=float),
        ]
    )
    benefit_x = np.arange(len(benefit_metrics), dtype=float)
    for day_index, day in enumerate(days):
        offset = (day_index - (len(days) - 1) / 2) * 0.18
        ax_benefit.plot(
            benefit_x + offset,
            without_solar[:, day_index],
            marker="o",
            color="#9ca3af",
            linewidth=1.7,
            label="without solar" if day_index == 0 else None,
        )
        ax_benefit.plot(
            benefit_x + offset,
            with_solar[:, day_index],
            marker="o",
            color="#16a34a",
            linewidth=1.7,
            label="with solar" if day_index == 0 else None,
        )
    ax_benefit.set_xticks(benefit_x)
    ax_benefit.set_xticklabels(["Cost", "CO2"])
    ax_benefit.set_ylabel("Daily improvement [%]")
    ax_benefit.set_title("B) System benefit with/without solar", loc="left", fontsize=12, fontweight="bold")
    ax_benefit.grid(True, axis="y", alpha=0.22)
    ax_benefit.legend(frameon=False, fontsize=9)

    delta_width = 0.28
    ax_delta.bar(
        x - delta_width / 2,
        data["cost_solar_assist_pct_point"],
        width=delta_width,
        color="#14532d",
        alpha=0.84,
        label="cost benefit added by solar",
    )
    ax_delta.bar(
        x + delta_width / 2,
        data["co2_solar_assist_pct_point"],
        width=delta_width,
        color="#166534",
        alpha=0.52,
        hatch="///",
        edgecolor="#166534",
        linewidth=0.45,
        label="CO2 benefit added by solar",
    )
    ax_delta.axhline(0.0, color="#111827", linewidth=0.8)
    ax_delta.set_title("C) Solar-assisted part of the Thermflex benefit", loc="left", fontsize=12, fontweight="bold")
    ax_delta.set_ylabel("Additional improvement [percentage points]")
    ax_delta.set_xticks(x)
    ax_delta.set_xticklabels(days)
    ax_delta.grid(True, axis="y", alpha=0.22)
    ax_delta.legend(frameon=False, fontsize=9)

    fig.suptitle("Solar gains as passive co-mechanism, not active shift source", fontsize=14, fontweight="bold")
    fig.text(
        0.08,
        0.035,
        "Counterfactual keeps the dispatch case unchanged and removes runtime solar gains. Positive values mean larger cost/CO2 reduction.",
        fontsize=9,
        color="#374151",
    )
    fig.savefig(OUTPUT_PATH, dpi=180, bbox_inches="tight")
    plt.close(fig)


def _clean_cell(cell: str) -> str:
    return cell.strip().replace("`", "")


def _normalize_header(header: str) -> str:
    ascii_header = unicodedata.normalize("NFKD", header).encode("ascii", "ignore").decode("ascii")
    return re.sub(r"[^a-z0-9]+", "_", ascii_header.lower()).strip("_")


def _parse_number(value: object) -> float:
    text = str(value).strip()
    if text.lower() in {"n/a", "na", ""}:
        return float("nan")
    return float(text.replace("%", "").replace("+", "").replace(",", ""))


if __name__ == "__main__":
    print(build_fig_08_solar_assisted_shift_counterfactual())
