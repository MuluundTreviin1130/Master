"""Build evidence-based four-panel taxonomy figure from PDF-backed cards.

This script upgrades the earlier generic draft to a conservative
evidence-card figure. It uses only study-level assignments that already exist
in ``paper_library/sec8_evidence_cards.csv``:

* surrogate model class
* integration pattern
* design-of-experiments / training design
* validation signal
* application section

Rows with an unassigned value (``--``) are omitted from the affected panel
rather than plotted as a category. This keeps the figure claim conservative.
"""

from __future__ import annotations

import csv
from collections import Counter, defaultdict
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.lines import Line2D
from matplotlib.path import Path as MplPath
from matplotlib.patches import PathPatch, Rectangle


ROOT = Path(__file__).resolve().parents[2]
FIG = ROOT / "figures"
CSV = FIG / "csv"
CARDS = ROOT / "paper_library" / "sec8_evidence_cards.csv"
OUT_COUNTS = CSV / "fig_four_panel_taxonomy_evidence_counts.csv"


PATTERN_ORDER = ["P1", "P2", "P4", "P5"]
PATTERN_LABELS = {
    "P1": "P1\nreplacement",
    "P2": "P2\nacceleration",
    "P4": "P4\ndecomposition",
    "P5": "P5\nuncertainty",
}

FAMILY_ORDER = [
    "PCE / RSM",
    "GP / kriging",
    "RBF / kernel",
    "Tree ensembles",
    "Neural network",
    "Constraint-aware NN",
]
FAMILY_COLORS = {
    "PCE / RSM": "#4E79A7",
    "GP / kriging": "#F28E2B",
    "RBF / kernel": "#59A14F",
    "Tree ensembles": "#EDC948",
    "Neural network": "#E15759",
    "Constraint-aware NN": "#76B7B2",
}

DOE_ORDER = [
    "Historical data",
    "LHS / quasi-MC",
    "Factorial / DoE",
    "Adaptive sampling",
    "Active learning",
    "Multi-fidelity",
    "Transfer learning",
]

VALIDATION_ORDER = [
    "Point metrics (RMSE/MAE/R²)",
    "Feasibility rate",
    "Uncertainty (problem UQ)",
    "Interval calibration",
    "Decision-aware (regret/gap)",
    "Stress test",
]
VALIDATION_COLORS = {
    "Point metrics (RMSE/MAE/R²)": "#7F7F7F",
    "Feasibility rate": "#1B9E77",
    "Uncertainty (problem UQ)": "#1F78B4",
    "Interval calibration": "#9467BD",
    "Decision-aware (regret/gap)": "#D95F02",
    "Stress test": "#E15759",
}

SECTION_LABELS = {
    "mes": "Multi-energy and sector-coupled systems",
    "moo": "Multi-objective energy system design",
    "microgrid": "Microgrids and energy hubs",
    "dh": "District heating systems and thermal storage",
    "dispatch": "Economic dispatch and unit commitment",
    "opf": "Optimal power flow and AC relaxations",
    "expansion": "Capacity and generation expansion planning",
    "stochastic": "Stochastic and robust energy planning",
}
SECTION_SHORT = {
    "mes": "MES / sector",
    "moo": "MOO design",
    "microgrid": "Microgrid / hub",
    "dh": "District heating",
    "dispatch": "ED / UC",
    "opf": "OPF",
    "expansion": "Expansion",
    "stochastic": "Stoch / robust",
}
APPLICATION_COLORS = {
    "MES / sector": "#4C78A8",
    "MOO design": "#54A24B",
    "Microgrid / hub": "#F58518",
    "District heating": "#BAB0AC",
    "ED / UC": "#B279A2",
    "OPF": "#E45756",
    "Expansion": "#9D755D",
    "Stoch / robust": "#72B7B2",
}


def read_cards() -> list[dict[str, str]]:
    with CARDS.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def split_validation(raw: str) -> list[str]:
    if not raw or raw.strip() == "--":
        return []
    values: list[str] = []
    for part in raw.split(";"):
        value = part.strip()
        if value in VALIDATION_ORDER and value not in values:
            values.append(value)
    return values


def dominant_validation(raw: str) -> str | None:
    values = set(split_validation(raw))
    for label in [
        "Decision-aware (regret/gap)",
        "Stress test",
        "Interval calibration",
        "Feasibility rate",
        "Uncertainty (problem UQ)",
        "Point metrics (RMSE/MAE/R²)",
    ]:
        if label in values:
            return label
    return None


def assigned(value: str | None) -> str | None:
    value = (value or "").strip()
    if not value or value == "--":
        return None
    return value


def node_positions(labels: list[str], counts: Counter[str]) -> dict[str, tuple[float, float]]:
    present = [label for label in labels if counts[label] > 0]
    total = sum(counts[label] for label in present)
    gap = 0.022
    usable = 0.80 - gap * max(len(present) - 1, 0)
    cursor = 0.90
    positions: dict[str, tuple[float, float]] = {}
    for label in present:
        height = usable * counts[label] / total if total else 0
        y0 = cursor - height
        positions[label] = (y0, cursor)
        cursor = y0 - gap
    return positions


def draw_flow(ax: plt.Axes, x0: float, y0: float, x1: float, y1: float, width: float, color: str) -> None:
    verts = [(x0, y0), (x0 + 0.12, y0), (x1 - 0.12, y1), (x1, y1)]
    path = MplPath(verts, [MplPath.MOVETO, MplPath.CURVE4, MplPath.CURVE4, MplPath.CURVE4])
    ax.add_patch(
        PathPatch(
            path,
            facecolor="none",
            edgecolor=color,
            linewidth=width,
            alpha=0.25,
            capstyle="round",
        )
    )


def draw_nodes(
    ax: plt.Axes,
    x: float,
    positions: dict[str, tuple[float, float]],
    counts: Counter[str],
    title: str,
    colors: dict[str, str] | None,
) -> None:
    node_w = 0.034
    ax.text(x, 0.985, title, ha="center", va="top", fontsize=10, fontweight="bold")
    for label, (y0, y1) in positions.items():
        ax.add_patch(
            Rectangle(
                (x - node_w / 2, y0),
                node_w,
                y1 - y0,
                facecolor=colors.get(label, "#D9D9D9") if colors else "#D9D9D9",
                edgecolor="#333333",
                linewidth=0.6,
            )
        )
        if x < 0.5:
            ax.text(x - 0.025, (y0 + y1) / 2, f"{label} ({counts[label]})", ha="right", va="center", fontsize=7.0)
        else:
            ax.text(x + 0.025, (y0 + y1) / 2, f"{label} ({counts[label]})", ha="left", va="center", fontsize=7.0)


def draw_alluvial(ax: plt.Axes, records: list[tuple[str, str, str]]) -> None:
    family_counts = Counter(f for f, _, _ in records)
    validation_counts = Counter(v for _, v, _ in records)
    pattern_counts = Counter(p for _, _, p in records)
    fv_counts = Counter((f, v) for f, v, _ in records)
    vp_counts = Counter((v, p) for _, v, p in records)

    family_order = [f for f in FAMILY_ORDER if family_counts[f] > 0]
    validation_order = [v for v in VALIDATION_ORDER if validation_counts[v] > 0]
    pattern_order = [p for p in PATTERN_ORDER if pattern_counts[p] > 0]
    family_pos = node_positions(family_order, family_counts)
    validation_pos = node_positions(validation_order, validation_counts)
    pattern_pos = node_positions(pattern_order, pattern_counts)

    x_family, x_validation, x_pattern = 0.10, 0.50, 0.90
    node_w = 0.034
    max_flow = max(max(fv_counts.values(), default=1), max(vp_counts.values(), default=1))
    scale = 18.0 / max_flow

    for (family, validation), count in fv_counts.items():
        fy0, fy1 = family_pos[family]
        vy0, vy1 = validation_pos[validation]
        source_index = sum(
            v for (f, val), v in fv_counts.items()
            if f == family and validation_order.index(val) < validation_order.index(validation)
        )
        target_index = sum(
            v for (f, val), v in fv_counts.items()
            if val == validation and family_order.index(f) < family_order.index(family)
        )
        fy = fy1 - (source_index + count / 2) / family_counts[family] * (fy1 - fy0)
        vy = vy1 - (target_index + count / 2) / validation_counts[validation] * (vy1 - vy0)
        draw_flow(ax, x_family + node_w, fy, x_validation - node_w, vy, max(0.8, count * scale), FAMILY_COLORS[family])

    for (validation, pattern), count in vp_counts.items():
        vy0, vy1 = validation_pos[validation]
        py0, py1 = pattern_pos[pattern]
        source_index = sum(
            v for (val, p), v in vp_counts.items()
            if val == validation and pattern_order.index(p) < pattern_order.index(pattern)
        )
        target_index = sum(
            v for (val, p), v in vp_counts.items()
            if p == pattern and validation_order.index(val) < validation_order.index(validation)
        )
        vy = vy1 - (source_index + count / 2) / validation_counts[validation] * (vy1 - vy0)
        py = py1 - (target_index + count / 2) / pattern_counts[pattern] * (py1 - py0)
        draw_flow(ax, x_validation + node_w, vy, x_pattern - node_w, py, max(0.8, count * scale), VALIDATION_COLORS[validation])

    draw_nodes(ax, x_family, family_pos, family_counts, "Model class", FAMILY_COLORS)
    draw_nodes(ax, x_validation, validation_pos, validation_counts, "Validation", VALIDATION_COLORS)
    draw_nodes(ax, x_pattern, pattern_pos, pattern_counts, "Integration pattern", None)
    ax.set_axis_off()
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.set_title("B. Model class -> validation -> integration pattern", loc="left", fontweight="bold")


def annotate_heatmap(ax: plt.Axes, data: np.ndarray) -> None:
    threshold = max(data.max() * 0.55, 1) if data.size else 1
    for y in range(data.shape[0]):
        for x in range(data.shape[1]):
            value = int(data[y, x])
            if value:
                ax.text(
                    x,
                    y,
                    str(value),
                    ha="center",
                    va="center",
                    fontsize=8,
                    fontweight="bold",
                    color="white" if value >= threshold else "#222222",
                )


def main() -> None:
    rows = read_cards()

    bubble_counts: Counter[tuple[str, str]] = Counter()
    bubble_validation: dict[tuple[str, str], Counter[str]] = defaultdict(Counter)
    alluvial_records: list[tuple[str, str, str]] = []
    doe_counts: Counter[tuple[str, str]] = Counter()
    app_counts: Counter[tuple[str, str]] = Counter()

    for row in rows:
        family = assigned(row.get("family"))
        pattern = assigned(row.get("pattern"))
        validation = dominant_validation(row.get("validation", ""))
        doe = assigned(row.get("doe"))
        section = assigned(row.get("section"))

        if family in FAMILY_ORDER and pattern in PATTERN_ORDER and validation:
            bubble_counts[(family, pattern)] += 1
            bubble_validation[(family, pattern)][validation] += 1
            alluvial_records.append((family, validation, pattern))
        if doe in DOE_ORDER and pattern in PATTERN_ORDER:
            doe_counts[(doe, pattern)] += 1
        if family in FAMILY_ORDER and section in SECTION_SHORT:
            app_counts[(family, SECTION_SHORT[section])] += 1

    with OUT_COUNTS.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["panel", "x", "y", "signal", "n"])
        for (family, pattern), count in sorted(bubble_counts.items()):
            validation = bubble_validation[(family, pattern)].most_common(1)[0][0]
            writer.writerow(["A_bubble", pattern, family, validation, count])
        for family, validation, pattern in alluvial_records:
            writer.writerow(["B_alluvial_record", pattern, family, validation, 1])
        for (doe, pattern), count in sorted(doe_counts.items()):
            writer.writerow(["C_doe", pattern, doe, "", count])
        for (family, app), count in sorted(app_counts.items()):
            writer.writerow(["D_app", app, family, "", count])

    fig = plt.figure(figsize=(15.8, 11.0))
    gs = fig.add_gridspec(2, 2, width_ratios=[1.05, 1.25], height_ratios=[1.05, 1.0], hspace=0.34, wspace=0.30)
    ax_a = fig.add_subplot(gs[0, 0])
    ax_b = fig.add_subplot(gs[0, 1])
    ax_c = fig.add_subplot(gs[1, 0])
    ax_d = fig.add_subplot(gs[1, 1])

    # A. Bubble map.
    x_pattern = {pattern: i for i, pattern in enumerate(PATTERN_ORDER)}
    y_family = {family: i for i, family in enumerate(FAMILY_ORDER)}
    max_count = max(bubble_counts.values()) if bubble_counts else 1
    for (family, pattern), count in bubble_counts.items():
        validation = bubble_validation[(family, pattern)].most_common(1)[0][0]
        ax_a.scatter(
            x_pattern[pattern],
            y_family[family],
            s=55 + 820 * count / max_count,
            c=VALIDATION_COLORS[validation],
            alpha=0.82,
            edgecolor="white",
            linewidth=0.8,
        )
        if count >= 4:
            ax_a.text(x_pattern[pattern], y_family[family], str(count), ha="center", va="center", fontsize=7.5, color="white", fontweight="bold")
    ax_a.set_xticks(range(len(PATTERN_ORDER)), [PATTERN_LABELS[p] for p in PATTERN_ORDER])
    ax_a.set_yticks(range(len(FAMILY_ORDER)), FAMILY_ORDER)
    ax_a.grid(True, color="#DDDDDD")
    ax_a.set_axisbelow(True)
    ax_a.set_title("A. Model class x integration pattern", loc="left", fontweight="bold")
    ax_a.set_xlabel("Integration pattern")
    ax_a.set_ylabel("Surrogate model class")
    validation_handles = [
        Line2D([0], [0], marker="o", color="none", markerfacecolor=VALIDATION_COLORS[v], markersize=6, label=v)
        for v in VALIDATION_ORDER
    ]
    ax_a.legend(
        handles=validation_handles,
        title="Dominant validation",
        loc="upper right",
        frameon=False,
        fontsize=6.8,
        title_fontsize=7.5,
    )

    # B. Alluvial flow.
    draw_alluvial(ax_b, alluvial_records)

    # C. DoE heatmap.
    doe_rows = [row for row in DOE_ORDER if any(doe_counts.get((row, pattern), 0) for pattern in PATTERN_ORDER)]
    doe_matrix = np.array([[doe_counts.get((row, pattern), 0) for pattern in PATTERN_ORDER] for row in doe_rows], dtype=float)
    im_c = ax_c.imshow(doe_matrix, cmap="YlOrBr", aspect="auto")
    annotate_heatmap(ax_c, doe_matrix)
    ax_c.set_xticks(range(len(PATTERN_ORDER)), [PATTERN_LABELS[p] for p in PATTERN_ORDER])
    ax_c.set_yticks(range(len(doe_rows)), doe_rows)
    ax_c.set_title("C. Training / DoE by integration pattern", loc="left", fontweight="bold")
    ax_c.set_xlabel("Integration pattern")
    fig.colorbar(im_c, ax=ax_c, fraction=0.046, pad=0.02, label="paper count")

    # D. Application bars, sorted by assigned total count.
    family_totals = Counter()
    for (family, _app), count in app_counts.items():
        family_totals[family] += count
    family_rows = [family for family, _count in family_totals.most_common()]
    app_totals = Counter()
    for (_family, app), count in app_counts.items():
        app_totals[app] += count
    app_order = [app for app, _count in app_totals.most_common()]

    left = [0] * len(family_rows)
    ypos = range(len(family_rows))
    for app in app_order:
        vals = [app_counts.get((family, app), 0) for family in family_rows]
        ax_d.barh(ypos, vals, left=left, color=APPLICATION_COLORS[app], label=app, height=0.68)
        left = [a + b for a, b in zip(left, vals)]
    ax_d.set_yticks(list(ypos), family_rows)
    ax_d.invert_yaxis()
    ax_d.grid(axis="x", color="#DDDDDD")
    ax_d.set_axisbelow(True)
    ax_d.set_title("D. Main application targets", loc="left", fontweight="bold")
    ax_d.set_xlabel("PDF-backed paper count")
    ax_d.legend(title="Application target", loc="lower right", frameon=False, fontsize=8, title_fontsize=9)

    fig.suptitle("Evidence-based taxonomy synthesis: integration, validation, training and applications", fontsize=15, fontweight="bold", y=0.985)
    fig.text(
        0.01,
        0.004,
        (
            f"Source: PDF-backed Section-8 evidence cards, n={len(rows)}. "
            "Unassigned cells are omitted from the affected panel; Panel B uses the strongest reported validation signal per study."
        ),
        fontsize=8,
        color="#555555",
    )
    fig.tight_layout(rect=(0, 0.035, 1, 0.955))
    for ext in ("png",):
        fig.savefig(FIG / f"fig_four_panel_taxonomy_evidence.{ext}", dpi=300, bbox_inches="tight")
    plt.close(fig)


if __name__ == "__main__":
    main()
