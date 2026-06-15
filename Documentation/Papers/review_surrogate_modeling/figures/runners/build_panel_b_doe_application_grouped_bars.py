"""Build DoE-by-application grouped stacked bars from the unified evidence table.

This panel keeps the Sankey's five application-target domains, but does not
require a complete multi-stage path. It counts application-linked studies for
three DoE-related blocks:

* Data sources
* Static designs
* Adaptive sampling and active learning

Within each block, the visible stacks are the explicit subcategories already
used in the manuscript taxonomy. Missing assignments are omitted rather than
forced into a filler bucket.
"""

from __future__ import annotations

import csv
import re
from collections import Counter, defaultdict
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt


ROOT = Path(__file__).resolve().parents[2]
FIG = ROOT / "figures"
CSV_DIR = FIG / "csv"
UNIFIED_STUDIES = ROOT / "paper_library" / "unified_evidence_studies.csv"
MANUSCRIPT = ROOT / "manuscript" / "main.md"

OUT_FIG = FIG / "fig_panel_b_doe_application_grouped_bars.png"
OUT_COUNTS = CSV_DIR / "fig_panel_b_doe_application_grouped_bars_counts.csv"

APPLICATION_SECTION_TITLES = [
    "Multi-energy and sector-coupled systems",
    "Multi-objective energy system design",
    "Microgrids and energy hubs",
    "District heating systems and thermal storage",
    "Economic dispatch and unit commitment",
    "Optimal power flow and AC relaxations",
    "Capacity and generation expansion planning",
]
APPLICATION_SECTION_TO_DOMAIN = {
    "Multi-energy and sector-coupled systems": "Integrated and distributed multi-energy systems",
    "Multi-objective energy system design": "System design and expansion",
    "Microgrids and energy hubs": "Integrated and distributed multi-energy systems",
    "District heating systems and thermal storage": "Thermal and building energy systems",
    "Economic dispatch and unit commitment": "Power system operation and markets",
    "Optimal power flow and AC relaxations": "Power flow, network security and grid planning",
    "Capacity and generation expansion planning": "System design and expansion",
}
APPLICATION_ORDER = [
    "Integrated and distributed multi-energy systems",
    "Power flow, network security and grid planning",
    "System design and expansion",
    "Power system operation and markets",
    "Thermal and building energy systems",
]
APPLICATION_SHORT = {
    "Integrated and distributed multi-energy systems": "Integrated / distributed MES",
    "Power flow, network security and grid planning": "Power flow / grid planning",
    "System design and expansion": "System design / expansion",
    "Power system operation and markets": "Operation / markets",
    "Thermal and building energy systems": "Thermal / buildings",
}

BLOCKS = [
    (
        "Data sources",
        ["Synthetic data", "Historical data", "Hybrid data"],
        {
            "Synthetic data": "#4C78A8",
            "Historical data": "#F58518",
            "Hybrid data": "#54A24B",
        },
    ),
    (
        "Static designs",
        [
            "Factorial / response-surface design",
            "Latin hypercube sampling",
            "Quasi-Monte Carlo / sparse-grid collocation",
        ],
        {
            "Factorial / response-surface design": "#B279A2",
            "Latin hypercube sampling": "#E45756",
            "Quasi-Monte Carlo / sparse-grid collocation": "#72B7B2",
        },
    ),
    (
        "Adaptive sampling and active learning",
        ["Adaptive sampling", "Active learning"],
        {
            "Adaptive sampling": "#9D755D",
            "Active learning": "#BAB0AC",
        },
    ),
]


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def split_labels(value: str | None) -> list[str]:
    return [part.strip() for part in (value or "").split(";") if part.strip()]


def norm(text: str) -> str:
    return re.sub(r"\s+", " ", text or "").strip().lower()


def extract_cite_keys(text: str) -> list[str]:
    keys: list[str] = []
    for block in re.findall(r"\[@([^\]]+)\]", text):
        for part in block.split(";"):
            cite_key = part.strip()
            if cite_key.startswith("@"):
                cite_key = cite_key[1:]
            if cite_key:
                keys.append(cite_key)
    return keys


def load_application_map() -> dict[str, str]:
    if not MANUSCRIPT.is_file():
        return {}
    text = MANUSCRIPT.read_text(encoding="utf-8")
    current_section: str | None = None
    section_text: dict[str, list[str]] = defaultdict(list)
    for line in text.splitlines():
        if line.startswith("## "):
            title = re.sub(r"\s+\{#.*\}$", "", line[3:]).strip()
            current_section = title if title in APPLICATION_SECTION_TITLES else None
            continue
        if current_section is not None:
            section_text[current_section].append(line)

    mapping: dict[str, str] = {}
    for title, lines in section_text.items():
        for cite_key in extract_cite_keys("\n".join(lines)):
            mapping[cite_key] = APPLICATION_SECTION_TO_DOMAIN[title]
    return mapping


def infer_application_domain(title: str) -> str:
    low = norm(title)
    if re.search(r"\b(microgrid|energy hub|vpp|virtual power plant|hres|distributed energy)\b", low):
        return "Integrated and distributed multi-energy systems"
    if re.search(r"\b(multi-energy|integrated energy|sector-coupl|district energy|multi-carrier|electrofuels|campus)\b", low):
        return "Integrated and distributed multi-energy systems"
    if re.search(r"\b(dispatch|unit commitment|market|bidding|scheduling|scuc|sced|forecasting|forecast|wind power prediction|wind speed prediction|load forecasting|net load forecasting)\b", low):
        return "Power system operation and markets"
    if re.search(r"\b(opf|optimal power flow|load flow|power flow|hosting capacity|voltage|reliability|grid planning|distribution network|ac-opf|dc-opf)\b", low):
        return "Power flow, network security and grid planning"
    if re.search(r"\b(building|hvac|district heating|thermal storage|cooling|heating|energy consumption|aquifer thermal|geothermal)\b", low):
        return "Thermal and building energy systems"
    if re.search(r"\b(expansion planning|capacity planning|generation expansion|design optimization|power system design|wind farm|well placement|layout optimization|trajectory planning)\b", low):
        return "System design and expansion"
    if re.search(r"\b(state of charge|remaining capacity|battery state|prognostics|photovoltaic power systems|electrolysis|lithium-ion batteries|airborne wind energy|electronic design|thermal conductivity measurement|motor|synchronous machine)\b", low):
        return "System design and expansion"
    return "Integrated and distributed multi-energy systems"


def main() -> None:
    if not UNIFIED_STUDIES.is_file():
        raise FileNotFoundError(
            f"Missing unified evidence table: {UNIFIED_STUDIES}. "
            "Run paper_library/build_unified_evidence_audit.py first."
        )

    CSV_DIR.mkdir(parents=True, exist_ok=True)

    rows = read_csv(UNIFIED_STUDIES)
    application_map = load_application_map()
    counts: Counter[tuple[str, str, str]] = Counter()
    block_totals: Counter[tuple[str, str]] = Counter()
    included_studies: set[str] = set()

    for row in rows:
        application = application_map.get(row["cite_key"]) or infer_application_domain(row.get("title", ""))
        if application not in APPLICATION_ORDER:
            continue

        present_by_block: dict[str, set[str]] = {}
        for block_label, subcategories, _colors in BLOCKS:
            explicit = set(split_labels(row.get("data_source" if block_label == "Data sources" else "doe_strategy", "")))
            matched = {label for label in subcategories if label in explicit}
            if matched:
                present_by_block[block_label] = matched

        if not present_by_block:
            continue
        included_studies.add(row["cite_key"])

        for block_label, matched in present_by_block.items():
            for subcategory in matched:
                counts[(application, block_label, subcategory)] += 1
            block_totals[(application, block_label)] += 1

    with OUT_COUNTS.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["application_target", "block", "subcategory", "n"])
        for application in APPLICATION_ORDER:
            for block_label, subcategories, _colors in BLOCKS:
                for subcategory in subcategories:
                    writer.writerow(
                        [
                            application,
                            block_label,
                            subcategory,
                            counts.get((application, block_label, subcategory), 0),
                        ]
                    )

    y_positions: list[float] = []
    y_labels: list[str] = []
    row_meta: list[tuple[str, str]] = []
    row_gap = 0.92
    group_gap = 0.80
    y = 0.0
    for application in APPLICATION_ORDER:
        for block_label, _subcategories, _colors in BLOCKS:
            y_positions.append(y)
            y_labels.append("")
            row_meta.append((application, block_label))
            y += row_gap
        y += group_gap

    fig, ax = plt.subplots(figsize=(14.8, 7.8))
    max_total = 0
    for application, block_label in row_meta:
        max_total = max(max_total, sum(counts.get((application, block_label, sub), 0) for _block, subs, _ in BLOCKS if _block == block_label for sub in subs))

    for ypos, (application, block_label) in zip(y_positions, row_meta):
        for divider_after in (2,):
            pass
        left = 0
        subcategories = next(subs for label, subs, _ in BLOCKS if label == block_label)
        colors = next(color_map for label, _subs, color_map in BLOCKS if label == block_label)
        for subcategory in subcategories:
            value = counts.get((application, block_label, subcategory), 0)
            if value == 0:
                continue
            ax.barh(
                ypos,
                value,
                left=left,
                height=0.68,
                color=colors[subcategory],
                edgecolor="white",
                linewidth=0.8,
            )
            if value >= 2:
                ax.text(
                    left + value / 2,
                    ypos,
                    str(value),
                    ha="center",
                    va="center",
                    fontsize=8,
                    fontweight="bold",
                    color="white",
                )
            left += value

    block_abbrev = {
        "Data sources": "Data",
        "Static designs": "Static",
        "Adaptive sampling and active learning": "Adaptive",
    }
    ax.set_yticks(y_positions, [""] * len(y_positions))
    ax.invert_yaxis()
    ax.grid(axis="x", color="#DDDDDD")
    ax.set_axisbelow(True)
    ax.set_xlabel("Paper count")
    ax.set_ylabel("")

    # Application group labels and separators.
    x_left = -max(max_total * 0.62, 11.5)
    x_block = -max(max_total * 0.18, 3.2)
    for group_index, application in enumerate(APPLICATION_ORDER):
        group_rows = [
            y_positions[index]
            for index, (app, _block) in enumerate(row_meta)
            if app == application
        ]
        group_center = sum(group_rows) / len(group_rows)
        ax.text(
            x_left,
            group_center,
            APPLICATION_SHORT[application],
            ha="right",
            va="center",
            fontsize=9.0,
            fontweight="bold",
        )
        if group_index < len(APPLICATION_ORDER) - 1:
            ax.axhline(group_rows[-1] + (row_gap + group_gap) / 2, color="#CCCCCC", linewidth=0.9)

    for ypos, (_application, block_label) in zip(y_positions, row_meta):
        ax.text(
            x_block,
            ypos,
            block_abbrev[block_label],
            ha="right",
            va="center",
            fontsize=9.0,
        )

    ax.set_xlim(x_left - 1.2, max_total + 1.2)

    legend_handles = []
    legend_labels = []
    for block_label, subcategories, colors in BLOCKS:
        for subcategory in subcategories:
            legend_handles.append(
                plt.Rectangle((0, 0), 1, 1, facecolor=colors[subcategory], edgecolor="none")
            )
            legend_labels.append(subcategory)

    ax.legend(
        legend_handles,
        legend_labels,
        loc="center left",
        bbox_to_anchor=(1.01, 0.5),
        frameon=False,
        fontsize=8.5,
    )

    # Group headers above the bars, aligned to the three recurring row types.
    ax.text(x_left, y_positions[0] - 0.95, "Application target", ha="right", va="bottom", fontsize=9.5, fontweight="bold")
    ax.text(x_block, y_positions[0] - 0.95, "Block", ha="right", va="bottom", fontsize=9.5, fontweight="bold")

    fig.tight_layout(rect=(0.06, 0.02, 0.82, 0.98))
    fig.savefig(OUT_FIG, dpi=300, bbox_inches="tight")
    plt.close(fig)

    print(f"included_studies={len(included_studies)}")
    print(f"nonzero_cells={sum(1 for value in counts.values() if value > 0)}")
    print(f"wrote {OUT_FIG}")


if __name__ == "__main__":
    main()
