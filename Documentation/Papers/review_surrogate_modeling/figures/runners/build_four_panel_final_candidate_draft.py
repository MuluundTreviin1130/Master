"""Build a four-panel draft candidate for the review taxonomy figure.

Panels:

A. Bubble map: model class x optimizer integration role.
B. Alluvial flow: model class -> validation signal -> optimizer role.
C. Heatmap: DoE/training design x integration pattern.
D. Stacked bars: main application targets by model class.

Panels B and C use PDF-backed Section-8 evidence cards, where validation,
DoE, model class and pattern are explicit. Panels A and D use the broader
curated library bucket layer to show the wider quantitative taxonomy and
application landscape. All labels are draft encodings from the manuscript's
existing categories.
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
MANIFEST = ROOT / "paper_library" / "review_paper_library_manifest.csv"
BUCKETS = ROOT / "paper_library" / "review_paper_library_buckets.csv"
CARDS = ROOT / "paper_library" / "sec8_evidence_cards.csv"
OUT_COUNTS = CSV / "fig_four_panel_final_candidate_draft_counts.csv"


ROLE_ORDER_FULL = [
    "Input / weak",
    "P1/P3 replace",
    "P2 accelerate",
    "P4 decompose",
    "P5 uncertainty",
]
ROLE_BUCKETS = {
    "P1/P3 replace": {"B07_constraint_aware", "B09_decision_focused_l2o", "B17_ed_uc", "B18_opf"},
    "P2 accelerate": {
        "B10_doe_active_learning",
        "B11_multi_fidelity",
        "B12_bayes_accel",
        "B23_moo_design",
        "B25_moo_algorithms_nsga",
        "B26_moo_metaheuristics",
    },
    "P4 decompose": {"B14_decomposition"},
    "P5 uncertainty": {"B15_uncertainty", "B24_stochastic_robust"},
}

PATTERN_ORDER = ["P1", "P2", "P4", "P5"]
PATTERN_LABELS = ["P1\nreplacement", "P2\nacceleration", "P4\ndecomposition", "P5\nuncertainty"]
PATTERN_TO_ROLE = {
    "P1": "P1/P3 replace",
    "P2": "P2 accelerate",
    "P4": "P4 decompose",
    "P5": "P5 uncertainty",
}

FAMILY_ORDER = ["PCE/RSM", "GP/Kriging", "RBF/Kernel", "Tree", "NN", "Constraint NN", "Hybrid/PINN", "L2O"]
FAMILY_CARD_ORDER = [
    "PCE / RSM",
    "GP / kriging",
    "RBF / kernel",
    "Tree ensembles",
    "Neural network",
    "Constraint-aware NN",
    "Hybrid / PINN",
    "L2O / decision-focused",
    "--",
]
CARD_TO_SHORT_FAMILY = {
    "PCE / RSM": "PCE/RSM",
    "GP / kriging": "GP/Kriging",
    "RBF / kernel": "RBF/Kernel",
    "Tree ensembles": "Tree",
    "Neural network": "NN",
    "Constraint-aware NN": "Constraint NN",
    "Hybrid / PINN": "Hybrid/PINN",
    "L2O / decision-focused": "L2O",
    "--": "--",
}
FAMILY_BUCKETS = {
    "PCE/RSM": {"B03_pce_response_surface"},
    "GP/Kriging": {"B02_gp_kriging"},
    "RBF/Kernel": {"B04_rbf_kernel"},
    "Tree": {"B05_tree_ensembles"},
    "NN": {"B06_neural_surrogates"},
    "Constraint NN": {"B07_constraint_aware"},
    "Hybrid/PINN": {"B08_hybrid_pinn"},
    "L2O": {"B09_decision_focused_l2o"},
}
FAMILY_COLORS = {
    "PCE/RSM": "#4E79A7",
    "GP/Kriging": "#F28E2B",
    "RBF/Kernel": "#59A14F",
    "Tree": "#EDC948",
    "NN": "#E15759",
    "Constraint NN": "#76B7B2",
    "Hybrid/PINN": "#B07AA1",
    "L2O": "#9C755F",
    "--": "#BDBDBD",
}

TRUST_COLORS = {
    "basic": "#999999",
    "adaptive": "#66A61E",
    "uncertainty": "#1F78B4",
    "physics": "#7570B3",
    "constraint": "#1B9E77",
    "decision": "#D95F02",
}
TRUST_LABELS = {
    "basic": "basic / point",
    "adaptive": "adaptive / BO",
    "uncertainty": "uncertainty",
    "physics": "physics-informed",
    "constraint": "constraint-aware",
    "decision": "decision-aware",
}

VALIDATION_ORDER = [
    "Point metrics",
    "Feasibility",
    "Uncertainty",
    "Interval calibration",
    "Decision-aware",
    "Stress test",
    "--",
]
VALIDATION_COLORS = {
    "Point metrics": "#7F7F7F",
    "Feasibility": "#1B9E77",
    "Uncertainty": "#1F78B4",
    "Interval calibration": "#9467BD",
    "Decision-aware": "#D95F02",
    "Stress test": "#E15759",
    "--": "#D9D9D9",
}

DOE_ORDER = [
    "--",
    "Historical data",
    "LHS / quasi-MC",
    "Factorial / DoE",
    "Adaptive sampling",
    "Active learning",
    "Multi-fidelity",
    "Transfer learning",
]

APPLICATION_BUCKETS = {
    "ED / UC": {"B17_ed_uc"},
    "OPF": {"B18_opf"},
    "Expansion": {"B19_capacity_expansion"},
    "District heating": {"B20_district_heating"},
    "MES / sector": {"B21_mes_sector_coupling"},
    "Microgrid / hub": {"B22_microgrid_hub"},
    "MOO design": {"B23_moo_design"},
    "Stoch / robust": {"B24_stochastic_robust"},
}
APPLICATION_COLORS = {
    "ED / UC": "#B279A2",
    "OPF": "#E45756",
    "Expansion": "#9D755D",
    "District heating": "#BAB0AC",
    "MES / sector": "#4C78A8",
    "Microgrid / hub": "#F58518",
    "MOO design": "#54A24B",
    "Stoch / robust": "#72B7B2",
}


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def bucket_index() -> dict[str, set[str]]:
    index: dict[str, set[str]] = defaultdict(set)
    if not BUCKETS.is_file():
        return index
    for row in read_csv(BUCKETS):
        key = row.get("cite_key", "").strip()
        tag = row.get("bucket_id", "").strip()
        if key and tag:
            index[key].add(tag)
    return index


def merged_buckets(row: dict[str, str], extra: dict[str, set[str]]) -> set[str]:
    tags: set[str] = set()
    for raw in (row.get("primary_bucket", ""), row.get("all_buckets", "")):
        for tag in raw.split(";"):
            tag = tag.strip()
            if tag:
                tags.add(tag)
    tags.update(extra.get(row.get("cite_key", ""), set()))
    return tags


def family_from_tags(tags: set[str]) -> str | None:
    found = [label for label in FAMILY_ORDER if tags & FAMILY_BUCKETS[label]]
    if not found:
        return None
    for specific in ("L2O", "Hybrid/PINN", "Constraint NN"):
        if specific in found:
            return specific
    return found[0]


def roles_from_tags(tags: set[str]) -> list[str]:
    found = [role for role in ROLE_ORDER_FULL[1:] if tags & ROLE_BUCKETS[role]]
    return found or ["Input / weak"]


def trust_from_tags(tags: set[str]) -> str:
    if tags & {"B09_decision_focused_l2o", "B16_validation"}:
        return "decision"
    if "B07_constraint_aware" in tags:
        return "constraint"
    if "B08_hybrid_pinn" in tags:
        return "physics"
    if tags & {"B15_uncertainty", "B24_stochastic_robust"}:
        return "uncertainty"
    if tags & {"B10_doe_active_learning", "B11_multi_fidelity", "B12_bayes_accel"}:
        return "adaptive"
    return "basic"


def validation_tags(raw: str) -> set[str]:
    text = (raw or "").lower()
    tags: set[str] = set()
    if not text or text.strip() == "--":
        return {"--"}
    if "point metrics" in text or "rmse" in text or "mae" in text or "r²" in text or "r2" in text:
        tags.add("Point metrics")
    if "feasibility" in text or "constraint" in text:
        tags.add("Feasibility")
    if "uncertainty" in text:
        tags.add("Uncertainty")
    if "interval calibration" in text:
        tags.add("Interval calibration")
    if "decision-aware" in text or "regret" in text or "gap" in text:
        tags.add("Decision-aware")
    if "stress test" in text:
        tags.add("Stress test")
    return tags or {"--"}


def dominant_validation(raw: str) -> str:
    tags = validation_tags(raw)
    for label in ["Decision-aware", "Stress test", "Interval calibration", "Feasibility", "Uncertainty", "Point metrics", "--"]:
        if label in tags:
            return label
    return "--"


def node_positions(labels: list[str], counts: Counter[str]) -> dict[str, tuple[float, float]]:
    present = [label for label in labels if counts[label] > 0]
    total = sum(counts[label] for label in present)
    gap = 0.02
    usable = 0.80 - gap * max(len(present) - 1, 0)
    y_top = 0.90
    positions: dict[str, tuple[float, float]] = {}
    cursor = y_top
    for label in present:
        height = usable * counts[label] / total if total else 0
        y0 = cursor - height
        positions[label] = (y0, cursor)
        cursor = y0 - gap
    return positions


def draw_flow(ax: plt.Axes, x0: float, y0: float, x1: float, y1: float, width: float, color: str, alpha: float) -> None:
    verts = [(x0, y0), (x0 + 0.12, y0), (x1 - 0.12, y1), (x1, y1)]
    path = MplPath(verts, [MplPath.MOVETO, MplPath.CURVE4, MplPath.CURVE4, MplPath.CURVE4])
    ax.add_patch(PathPatch(path, facecolor="none", edgecolor=color, linewidth=width, alpha=alpha, capstyle="round"))


def draw_alluvial(ax: plt.Axes, card_records: list[tuple[str, str, str]]) -> None:
    family_counts = Counter(f for f, _, _ in card_records)
    validation_counts = Counter(v for _, v, _ in card_records)
    role_counts = Counter(r for _, _, r in card_records)
    fv_counts = Counter((f, v) for f, v, _ in card_records)
    vr_counts = Counter((v, r) for _, v, r in card_records)
    family_order = [f for f in FAMILY_ORDER + ["--"] if family_counts[f] > 0]
    family_pos = node_positions(family_order, family_counts)
    validation_pos = node_positions(VALIDATION_ORDER, validation_counts)
    role_pos = node_positions(ROLE_ORDER_FULL[1:], role_counts)
    x_family, x_validation, x_role = 0.10, 0.50, 0.90
    node_w = 0.035
    max_flow = max(max(fv_counts.values(), default=1), max(vr_counts.values(), default=1))
    scale = 18.0 / max_flow

    for (family, validation), count in fv_counts.items():
        fy0, fy1 = family_pos[family]
        vy0, vy1 = validation_pos[validation]
        source_index = sum(v for (f, val), v in fv_counts.items() if f == family and VALIDATION_ORDER.index(val) < VALIDATION_ORDER.index(validation))
        target_index = sum(v for (f, val), v in fv_counts.items() if val == validation and family_order.index(f) < family_order.index(family))
        fy = fy1 - (source_index + count / 2) / family_counts[family] * (fy1 - fy0)
        vy = vy1 - (target_index + count / 2) / validation_counts[validation] * (vy1 - vy0)
        draw_flow(ax, x_family + node_w, fy, x_validation - node_w, vy, max(0.8, count * scale), FAMILY_COLORS[family], 0.25)

    for (validation, role), count in vr_counts.items():
        vy0, vy1 = validation_pos[validation]
        ry0, ry1 = role_pos[role]
        source_index = sum(v for (val, r), v in vr_counts.items() if val == validation and ROLE_ORDER_FULL.index(r) < ROLE_ORDER_FULL.index(role))
        target_index = sum(v for (val, r), v in vr_counts.items() if r == role and VALIDATION_ORDER.index(val) < VALIDATION_ORDER.index(validation))
        vy = vy1 - (source_index + count / 2) / validation_counts[validation] * (vy1 - vy0)
        ry = ry1 - (target_index + count / 2) / role_counts[role] * (ry1 - ry0)
        draw_flow(ax, x_validation + node_w, vy, x_role - node_w, ry, max(0.8, count * scale), VALIDATION_COLORS[validation], 0.23)

    def draw_nodes(x: float, positions: dict[str, tuple[float, float]], counts: Counter[str], title: str, colors: dict[str, str] | None) -> None:
        ax.text(x, 0.98, title, ha="center", va="top", fontsize=10, fontweight="bold")
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
                ax.text(x - 0.025, (y0 + y1) / 2, f"{label} ({counts[label]})", ha="right", va="center", fontsize=7.2)
            else:
                ax.text(x + 0.025, (y0 + y1) / 2, f"{label} ({counts[label]})", ha="left", va="center", fontsize=7.2)

    draw_nodes(x_family, family_pos, family_counts, "Model class", FAMILY_COLORS)
    draw_nodes(x_validation, validation_pos, validation_counts, "Validation", VALIDATION_COLORS)
    draw_nodes(x_role, role_pos, role_counts, "Optimizer role", None)
    ax.set_axis_off()
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.set_title("B. Model class -> validation -> optimizer role", loc="left", fontweight="bold")


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
    extra = bucket_index()
    library_records: list[tuple[str, set[str]]] = []
    for row in read_csv(MANIFEST):
        if row.get("primary_bucket") == "B01_cornerstone_reviews":
            continue
        tags = merged_buckets(row, extra)
        family = family_from_tags(tags)
        if family:
            library_records.append((family, tags))

    bubble_counts: Counter[tuple[str, str, str]] = Counter()
    app_counts: Counter[tuple[str, str]] = Counter()
    for family, tags in library_records:
        trust = trust_from_tags(tags)
        for role in roles_from_tags(tags):
            bubble_counts[(family, role, trust)] += 1
        for app, app_tags in APPLICATION_BUCKETS.items():
            if tags & app_tags:
                app_counts[(family, app)] += 1

    cards = read_csv(CARDS)
    card_records: list[tuple[str, str, str]] = []
    doe_counts: Counter[tuple[str, str]] = Counter()
    for row in cards:
        pattern = (row.get("pattern") or "").strip()
        if pattern not in PATTERN_ORDER:
            continue
        family = CARD_TO_SHORT_FAMILY.get((row.get("family") or "--").strip() or "--", "--")
        role = PATTERN_TO_ROLE[pattern]
        validation = dominant_validation(row.get("validation", ""))
        card_records.append((family, validation, role))
        doe = (row.get("doe") or "--").strip() or "--"
        doe_counts[(doe, pattern)] += 1

    with OUT_COUNTS.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["panel", "x", "y", "signal", "n"])
        for (family, role, trust), count in sorted(bubble_counts.items()):
            writer.writerow(["A_bubble", role, family, trust, count])
        for family, validation, role in card_records:
            writer.writerow(["B_alluvial_record", role, family, validation, 1])
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

    # A. Bubble map, model class x optimizer integration.
    x_role = {role: i for i, role in enumerate(ROLE_ORDER_FULL)}
    y_family = {family: i for i, family in enumerate(FAMILY_ORDER)}
    max_count = max(bubble_counts.values()) if bubble_counts else 1
    for (family, role, trust), count in bubble_counts.items():
        ax_a.scatter(
            x_role[role],
            y_family[family],
            s=45 + 760 * count / max_count,
            c=TRUST_COLORS[trust],
            alpha=0.80,
            edgecolor="white",
            linewidth=0.8,
        )
        if count >= 7:
            ax_a.text(x_role[role], y_family[family], str(count), ha="center", va="center", fontsize=7.5, color="white", fontweight="bold")
    ax_a.set_xticks(range(len(ROLE_ORDER_FULL)), ROLE_ORDER_FULL, rotation=26, ha="right")
    ax_a.set_yticks(range(len(FAMILY_ORDER)), FAMILY_ORDER)
    ax_a.grid(True, color="#DDDDDD")
    ax_a.set_axisbelow(True)
    ax_a.set_title("A. Model class x optimizer role", loc="left", fontweight="bold")
    ax_a.set_xlabel("Optimizer integration role")
    ax_a.set_ylabel("Surrogate model class")

    # B. Alluvial flow with validation in the middle.
    draw_alluvial(ax_b, card_records)

    # C. DoE heatmap by integration pattern.
    doe_rows = [row for row in DOE_ORDER if any(doe_counts.get((row, pattern), 0) for pattern in PATTERN_ORDER)]
    doe_matrix = np.array([[doe_counts.get((row, pattern), 0) for pattern in PATTERN_ORDER] for row in doe_rows], dtype=float)
    im_c = ax_c.imshow(doe_matrix, cmap="YlOrBr", aspect="auto")
    annotate_heatmap(ax_c, doe_matrix)
    ax_c.set_xticks(range(len(PATTERN_ORDER)), PATTERN_LABELS)
    ax_c.set_yticks(range(len(doe_rows)), doe_rows)
    ax_c.set_title("C. Training / DoE by integration pattern", loc="left", fontweight="bold")
    ax_c.set_xlabel("Integration pattern")
    fig.colorbar(im_c, ax=ax_c, fraction=0.046, pad=0.02, label="paper count")

    # D. Stacked bar chart for application targets.
    top_apps = [app for app, _ in Counter(app for _, app in app_counts).most_common(7)]
    left = [0] * len(FAMILY_ORDER)
    ypos = range(len(FAMILY_ORDER))
    for app in top_apps:
        vals = [app_counts.get((family, app), 0) for family in FAMILY_ORDER]
        ax_d.barh(ypos, vals, left=left, color=APPLICATION_COLORS[app], label=app, height=0.68)
        left = [a + b for a, b in zip(left, vals)]
    ax_d.set_yticks(list(ypos), FAMILY_ORDER)
    ax_d.grid(axis="x", color="#DDDDDD")
    ax_d.set_axisbelow(True)
    ax_d.set_title("D. Main application targets", loc="left", fontweight="bold")
    ax_d.set_xlabel("Tagged paper count")
    ax_d.legend(title="Application target", loc="lower right", frameon=False, fontsize=8, title_fontsize=9)

    trust_handles = [
        Line2D([0], [0], marker="o", color="none", markerfacecolor=TRUST_COLORS[t], markersize=7, label=TRUST_LABELS[t])
        for t in ("basic", "adaptive", "uncertainty", "physics", "constraint", "decision")
    ]
    fig.legend(handles=trust_handles, title="Panel A: trust signal", loc="lower left", bbox_to_anchor=(0.02, 0.012), ncol=3, frameon=False, fontsize=8, title_fontsize=9)
    validation_handles = [
        Line2D([0], [0], color=VALIDATION_COLORS[v], lw=5, label=v)
        for v in VALIDATION_ORDER
        if v != "--"
    ]
    fig.legend(handles=validation_handles, title="Panel B: validation node color", loc="lower center", bbox_to_anchor=(0.57, 0.012), ncol=3, frameon=False, fontsize=8, title_fontsize=9)

    fig.suptitle("Draft quantitative taxonomy synthesis: integration, validation, training and applications", fontsize=15, fontweight="bold", y=0.985)
    fig.text(
        0.01,
        0.004,
        (
            f"Sources: Panels A/D use curated library bucket tags, non-review model-class records n={len(library_records)}; "
            f"Panels B/C use PDF-backed evidence cards n={len(cards)}. Draft classification for visual review."
        ),
        fontsize=8,
        color="#555555",
    )
    fig.tight_layout(rect=(0, 0.08, 1, 0.955))
    for ext in ("png",):
        fig.savefig(FIG / f"fig_four_panel_final_candidate_draft.{ext}", dpi=300, bbox_inches="tight")
    plt.close(fig)


if __name__ == "__main__":
    main()
