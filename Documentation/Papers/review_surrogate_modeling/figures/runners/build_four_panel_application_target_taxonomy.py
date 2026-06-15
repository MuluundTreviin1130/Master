"""Build a four-panel application-target taxonomy figure from unified evidence.

Panels:
A. Surrogate model class by application target
B. DoE / training blocks by application target
C. Integration pattern by application target
D. Validation by application target

All panels use the same five application-target domains as the evidence-based
Sankey, but they do not require a complete multi-stage Sankey path. Counts are
derived from the unified study-level evidence table with explicit assignments
only; unresolved labels are omitted rather than forced into filler categories.
"""

from __future__ import annotations

import csv
import re
from collections import Counter, defaultdict
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Patch
from matplotlib.transforms import blended_transform_factory


ROOT = Path(__file__).resolve().parents[2]
FIG = ROOT / "figures"
CSV_DIR = FIG / "csv"
UNIFIED_STUDIES = ROOT / "paper_library" / "unified_evidence_studies.csv"
MANUSCRIPT = ROOT / "manuscript" / "main.md"
OUT_FIG = FIG / "fig_four_panel_application_target_taxonomy.png"
OUT_COUNTS = CSV_DIR / "fig_four_panel_application_target_taxonomy_counts.csv"

APPLICATION_SECTION_TITLES = [
    "Integrated and distributed multi-energy systems: multi-energy and sector-coupled systems",
    "System design and expansion: multi-objective energy system design",
    "Integrated and distributed multi-energy systems: microgrids and energy hubs",
    "Thermal and building energy systems: district heating and thermal storage",
    "Power-system operation and markets: economic dispatch and unit commitment",
    "Power flow, network security and grid planning: optimal power flow and AC relaxations",
    "System design and expansion: capacity and generation expansion planning",
]
APPLICATION_SECTION_TO_DOMAIN = {
    title: title.split(":", 1)[0].replace(
        "Power-system operation", "Power system operation"
    )
    for title in APPLICATION_SECTION_TITLES
}
APPLICATION_SHORT = {
    "Integrated and distributed multi-energy systems": "Integrated / distributed MES",
    "Power flow, network security and grid planning": "Power flow / grid planning",
    "System design and expansion": "System design / expansion",
    "Power system operation and markets": "Operation / markets",
    "Thermal and building energy systems": "Thermal / buildings",
}

FAMILY_ORDER = [
    "PCE / RSM",
    "GP / kriging",
    "RBF / kernel",
    "Tree ensembles",
    "Neural network",
]
FAMILY_COLORS = {
    "PCE / RSM": "#9467BD",
    "GP / kriging": "#4E79A7",
    "RBF / kernel": "#59A14F",
    "Tree ensembles": "#F28E2B",
    "Neural network": "#E15759",
}

PATTERN_ORDER = [
    "P1 replacement",
    "P2 acceleration",
    "P3 solution proxy",
    "P4 decomposition",
    "P5 uncertainty",
]
PATTERN_COLORS = {
    "P1 replacement": "#4E79A7",
    "P2 acceleration": "#F28E2B",
    "P3 solution proxy": "#59A14F",
    "P4 decomposition": "#B279A2",
    "P5 uncertainty": "#E15759",
}

VALIDATION_ORDER = [
    "Point metrics",
    "Problem UQ",
    "Decision-aware",
    "Feasibility",
    "Stress test",
    "Interval calibration",
]
VALIDATION_COLORS = {
    "Point metrics": "#7F7F7F",
    "Problem UQ": "#1F78B4",
    "Decision-aware": "#D95F02",
    "Feasibility": "#1B9E77",
    "Stress test": "#E15759",
    "Interval calibration": "#9467BD",
}

DOE_BLOCKS = [
    (
        "Data",
        ["Synthetic data", "Historical data", "Hybrid data"],
        {
            "Synthetic data": "#4C78A8",
            "Historical data": "#F58518",
            "Hybrid data": "#54A24B",
        },
    ),
    (
        "Static",
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
        "Adaptive",
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
            key = part.strip()
            if key.startswith("@"):
                key = key[1:]
            if key:
                keys.append(key)
    return keys


def load_application_map() -> dict[str, str]:
    text = MANUSCRIPT.read_text(encoding="utf-8")
    current_section: str | None = None
    section_text: dict[str, list[str]] = defaultdict(list)
    for line in text.splitlines():
        if line.startswith("## "):
            current_section = None
            continue
        if line.startswith("### "):
            title = re.sub(r"\s+\{#.*\}$", "", line[4:]).strip()
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


def draw_stacked_barh(ax, order, counts, category_order, colors, title, xlabel, show_legend=False, legend_title=None):
    ypos = list(range(len(order)))
    left = [0] * len(order)
    max_total = 0
    for row in order:
        max_total = max(max_total, sum(counts.get((row, category), 0) for category in category_order))
    for category in category_order:
        values = [counts.get((row, category), 0) for row in order]
        ax.barh(ypos, values, left=left, color=colors[category], label=category, height=0.68)
        for idx, value in enumerate(values):
            if value >= 3:
                ax.text(left[idx] + value / 2, ypos[idx], str(value), ha="center", va="center", fontsize=8.8, color="white", fontweight="bold")
        left = [a + b for a, b in zip(left, values)]
    ax.set_yticks(ypos, [APPLICATION_SHORT[row] for row in order], fontsize=10.5)
    ax.invert_yaxis()
    ax.grid(axis="x", color="#DDDDDD")
    ax.set_axisbelow(True)
    ax.set_title(title, loc="left", fontweight="bold", fontsize=15)
    ax.set_xlabel(xlabel, fontsize=11.5)
    ax.tick_params(axis="x", labelsize=10.5)
    if show_legend:
        legend = ax.legend(
            title=legend_title,
            loc="lower right",
            bbox_to_anchor=(0.98, 0.03),
            frameon=True,
            fontsize=10.2,
            title_fontsize=11.2,
        )
        legend.get_frame().set_facecolor("white")
        legend.get_frame().set_alpha(0.92)
        legend.get_frame().set_linewidth(0.0)


def draw_doe_panel(ax, application_order, counts):
    row_gap = 0.92
    group_gap = 0.78
    y_positions = []
    row_meta = []
    y = 0.0
    for application in application_order:
        for block_label, _subcategories, _colors in DOE_BLOCKS:
            y_positions.append(y)
            row_meta.append((application, block_label))
            y += row_gap
        y += group_gap

    max_total = 0
    for application, block_label in row_meta:
        subcategories = next(subs for label, subs, _ in DOE_BLOCKS if label == block_label)
        max_total = max(max_total, sum(counts.get((application, block_label, subcategory), 0) for subcategory in subcategories))

    for ypos, (application, block_label) in zip(y_positions, row_meta):
        left = 0
        subcategories = next(subs for label, subs, _ in DOE_BLOCKS if label == block_label)
        colors = next(color_map for label, _subs, color_map in DOE_BLOCKS if label == block_label)
        for subcategory in subcategories:
            value = counts.get((application, block_label, subcategory), 0)
            if value == 0:
                continue
            ax.barh(ypos, value, left=left, height=0.68, color=colors[subcategory], edgecolor="white", linewidth=0.8)
            if value >= 3:
                ax.text(left + value / 2, ypos, str(value), ha="center", va="center", fontsize=8.4, color="white", fontweight="bold")
            left += value

    ax.set_yticks(y_positions, [""] * len(y_positions))
    ax.invert_yaxis()
    ax.grid(axis="x", color="#DDDDDD")
    ax.set_axisbelow(True)
    ax.set_title("B. DoE / training by application target", loc="left", fontweight="bold", fontsize=15)
    ax.set_xlabel("Paper count", fontsize=11.5)
    ax.tick_params(axis="x", labelsize=10.5)

    ax.set_xlim(0, max_total + 1.0)
    trans = blended_transform_factory(ax.transAxes, ax.transData)
    app_x = -0.085
    block_x = -0.008

    for group_index, application in enumerate(application_order):
        group_rows = [y_positions[index] for index, (app, _block) in enumerate(row_meta) if app == application]
        ax.text(
            app_x,
            sum(group_rows) / len(group_rows),
            APPLICATION_SHORT[application],
            ha="right",
            va="center",
            fontsize=10.0,
            transform=trans,
            clip_on=False,
        )
        if group_index < len(application_order) - 1:
            ax.axhline(group_rows[-1] + (row_gap + group_gap) / 2, color="#CCCCCC", linewidth=0.9)

    for ypos, (_application, block_label) in zip(y_positions, row_meta):
        ax.text(
            block_x,
            ypos,
            block_label,
            ha="right",
            va="center",
            fontsize=10.0,
            transform=trans,
            clip_on=False,
        )

    data_handles = [Patch(facecolor=color, label=label) for label, color in DOE_BLOCKS[0][2].items()]
    static_handles = [Patch(facecolor=color, label=label) for label, color in DOE_BLOCKS[1][2].items()]
    adaptive_handles = [Patch(facecolor=color, label=label) for label, color in DOE_BLOCKS[2][2].items()]
    legend_x = 0.60
    legend1 = ax.legend(
        handles=data_handles,
        title="Data",
        loc="upper left",
        bbox_to_anchor=(legend_x, 0.60),
        frameon=True,
        fontsize=10.0,
        title_fontsize=11.0,
    )
    legend1.get_frame().set_facecolor("white")
    legend1.get_frame().set_alpha(0.92)
    legend1.get_frame().set_linewidth(0.0)
    ax.add_artist(legend1)
    legend2 = ax.legend(
        handles=static_handles,
        title="Static",
        loc="upper left",
        bbox_to_anchor=(legend_x, 0.40),
        frameon=True,
        fontsize=10.0,
        title_fontsize=11.0,
    )
    legend2.get_frame().set_facecolor("white")
    legend2.get_frame().set_alpha(0.92)
    legend2.get_frame().set_linewidth(0.0)
    ax.add_artist(legend2)
    legend3 = ax.legend(
        handles=adaptive_handles,
        title="Adaptive",
        loc="upper left",
        bbox_to_anchor=(legend_x, 0.20),
        frameon=True,
        fontsize=10.0,
        title_fontsize=11.0,
    )
    legend3.get_frame().set_facecolor("white")
    legend3.get_frame().set_alpha(0.92)
    legend3.get_frame().set_linewidth(0.0)


def main() -> None:
    CSV_DIR.mkdir(parents=True, exist_ok=True)
    rows = read_csv(UNIFIED_STUDIES)
    application_map = load_application_map()

    family_counts: Counter[tuple[str, str]] = Counter()
    doe_counts: Counter[tuple[str, str, str]] = Counter()
    pattern_counts: Counter[tuple[str, str]] = Counter()
    validation_counts: Counter[tuple[str, str]] = Counter()

    for row in rows:
        application = application_map.get(row["cite_key"]) or infer_application_domain(row.get("title", ""))
        if application not in APPLICATION_SHORT:
            continue

        family = row.get("family", "").strip()
        if family in FAMILY_ORDER:
            family_counts[(application, family)] += 1

        explicit_data = set(split_labels(row.get("data_source", "")))
        explicit_doe = set(split_labels(row.get("doe_strategy", "")))
        for block_label, subcategories, _colors in DOE_BLOCKS:
            source = explicit_data if block_label == "Data" else explicit_doe
            for subcategory in subcategories:
                if subcategory in source:
                    doe_counts[(application, block_label, subcategory)] += 1

        for pattern in split_labels(row.get("pattern", "")):
            if pattern in PATTERN_ORDER:
                pattern_counts[(application, pattern)] += 1

        for validation in split_labels(row.get("validation", "")):
            if validation in VALIDATION_ORDER:
                validation_counts[(application, validation)] += 1

    app_totals = Counter()
    for (application, _family), count in family_counts.items():
        app_totals[application] += count
    application_order = [application for application, _count in app_totals.most_common()]

    with OUT_COUNTS.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["panel", "application_target", "category", "subcategory", "n"])
        for (application, family), count in sorted(family_counts.items()):
            writer.writerow(["A_model_class", application, family, "", count])
        for (application, block_label, subcategory), count in sorted(doe_counts.items()):
            writer.writerow(["B_doe", application, block_label, subcategory, count])
        for (application, pattern), count in sorted(pattern_counts.items()):
            writer.writerow(["C_integration", application, pattern, "", count])
        for (application, validation), count in sorted(validation_counts.items()):
            writer.writerow(["D_validation", application, validation, "", count])

    fig = plt.figure(figsize=(16.5, 12.2))
    gs = fig.add_gridspec(2, 2, width_ratios=[1.0, 1.35], height_ratios=[1.0, 1.25], hspace=0.24, wspace=0.46)
    ax_a = fig.add_subplot(gs[0, 0])
    ax_b = fig.add_subplot(gs[0, 1])
    ax_c = fig.add_subplot(gs[1, 0])
    ax_d = fig.add_subplot(gs[1, 1])

    draw_stacked_barh(
        ax_a,
        application_order,
        family_counts,
        FAMILY_ORDER,
        FAMILY_COLORS,
        "A. Surrogate model class by application target",
        "Paper count",
        show_legend=True,
        legend_title="Model class",
    )

    draw_doe_panel(ax_b, application_order, doe_counts)

    draw_stacked_barh(
        ax_c,
        application_order,
        pattern_counts,
        PATTERN_ORDER,
        PATTERN_COLORS,
        "C. Integration pattern by application target",
        "Paper count",
        show_legend=True,
        legend_title="Integration pattern",
    )

    draw_stacked_barh(
        ax_d,
        application_order,
        validation_counts,
        VALIDATION_ORDER,
        VALIDATION_COLORS,
        "D. Validation by application target",
        "Paper count",
        show_legend=True,
        legend_title="Validation",
    )

    fig.subplots_adjust(left=0.08, right=1.18, top=0.97, bottom=0.06)
    fig.savefig(OUT_FIG, dpi=300, bbox_inches="tight")
    plt.close(fig)

    print(f"applications={len(application_order)}")
    print(f"wrote {OUT_FIG}")


if __name__ == "__main__":
    main()
