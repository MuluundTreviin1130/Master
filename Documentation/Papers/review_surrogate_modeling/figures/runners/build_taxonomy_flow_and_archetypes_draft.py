"""Build draft alluvial-flow and lollipop archetype figures.

Both figures use the same conservative bucket-derived taxonomy that is already
used in the manuscript pipeline:

* model class
* surrogate target
* optimizer integration role
* trust mechanism

The alluvial figure shows how records flow from model class through surrogate
target to integration role. The lollipop figure lists the most common complete
archetypes. These are draft visual encodings; the mappings should be audited
before manuscript-final claims are made.
"""

from __future__ import annotations

import csv
import re
from collections import Counter, defaultdict
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
from matplotlib.path import Path as MplPath
from matplotlib.patches import PathPatch, Rectangle


ROOT = Path(__file__).resolve().parents[2]
FIG = ROOT / "figures"
CSV = FIG / "csv"
MANIFEST = ROOT / "paper_library" / "review_paper_library_manifest.csv"
BUCKETS = ROOT / "paper_library" / "review_paper_library_buckets.csv"
OUT_COUNTS = CSV / "fig_taxonomy_flow_and_archetypes_draft_counts.csv"
UNIFIED_STUDIES = ROOT / "paper_library" / "unified_evidence_studies.csv"
MANUSCRIPT = ROOT / "manuscript" / "main.md"


ROLE_ORDER = ["Input / weak", "P1/P3 replace", "P2 accelerate", "P4 decompose", "P5 uncertainty"]
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

FAMILY_ORDER = ["PCE/RSM", "GP/Kriging", "RBF/Kernel", "Tree", "NN", "Constraint NN", "Hybrid/PINN", "L2O"]
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
}

EVIDENCE_FAMILY_ORDER = [
    "PCE / RSM",
    "GP / kriging",
    "RBF / kernel",
    "Tree ensembles",
    "Neural network",
]
EVIDENCE_FAMILY_COLORS = {
    "PCE / RSM": "#9467BD",
    "GP / kriging": "#4E79A7",
    "RBF / kernel": "#59A14F",
    "Tree ensembles": "#F28E2B",
    "Neural network": "#E15759",
}
EVIDENCE_DOE_ORDER = [
    "Latin hypercube sampling",
    "Quasi-Monte Carlo / sparse-grid collocation",
    "Factorial / response-surface design",
    "Adaptive sampling",
    "Active learning",
    "Multi-fidelity training",
    "Transfer learning",
    "Synthetic data",
    "Historical data",
    "Hybrid data",
    "Not explicitly identified",
]
EVIDENCE_PATTERN_ORDER = [
    "P1 replacement",
    "P2 acceleration",
    "P3 solution proxy",
    "P4 decomposition",
    "P5 uncertainty",
    "Not explicitly identified",
]
EVIDENCE_VALIDATION_ORDER = [
    "Decision-aware",
    "Stress test",
    "Interval calibration",
    "Feasibility",
    "Problem UQ",
    "Point metrics",
    "Not explicitly identified",
]

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

TARGET_ORDER = ["exogenous input", "objective / response", "constraints / states", "uncertainty / risk", "solution / policy"]

TRUST_ORDER = ["basic", "adaptive", "uncertainty", "physics", "constraint", "decision"]
TRUST_LABELS = {
    "basic": "basic / point",
    "adaptive": "adaptive / BO",
    "uncertainty": "uncertainty",
    "physics": "physics-informed",
    "constraint": "constraint-aware",
    "decision": "decision-aware",
}
TRUST_COLORS = {
    "basic": "#999999",
    "adaptive": "#66A61E",
    "uncertainty": "#1F78B4",
    "physics": "#7570B3",
    "constraint": "#1B9E77",
    "decision": "#D95F02",
}


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def norm(text: str) -> str:
    return re.sub(r"\s+", " ", text or "").strip().lower()


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


def strongest_role(tags: set[str]) -> str:
    for role in reversed(ROLE_ORDER[1:]):
        if tags & ROLE_BUCKETS[role]:
            return role
    return "Input / weak"


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


def surrogate_target(row: dict[str, str], tags: set[str]) -> str:
    title = norm(row.get("title", ""))
    if "B09_decision_focused_l2o" in tags:
        return "solution / policy"
    if tags & {"B15_uncertainty", "B24_stochastic_robust"}:
        return "uncertainty / risk"
    if tags & {"B07_constraint_aware", "B18_opf"}:
        return "constraints / states"
    if re.search(r"\b(load|forecast|wind|solar|pv|price|demand)\b", title) and not tags & {
        "B17_ed_uc",
        "B18_opf",
        "B21_mes_sector_coupling",
        "B22_microgrid_hub",
        "B23_moo_design",
    }:
        return "exogenous input"
    return "objective / response"


def load_records() -> list[tuple[str, str, str, str]]:
    extra = bucket_index()
    records: list[tuple[str, str, str, str]] = []
    for row in read_csv(MANIFEST):
        if row.get("primary_bucket") == "B01_cornerstone_reviews":
            continue
        tags = merged_buckets(row, extra)
        family = family_from_tags(tags)
        if not family:
            continue
        records.append((family, surrogate_target(row, tags), strongest_role(tags), trust_from_tags(tags)))
    return records


def save(fig: plt.Figure, stem: str) -> None:
    for ext in ("png",):
        fig.savefig(FIG / f"{stem}.{ext}", dpi=300, bbox_inches="tight")
    plt.close(fig)


def node_positions(labels: list[str], counts: Counter[str]) -> dict[str, tuple[float, float]]:
    present = [label for label in labels if counts[label] > 0]
    total = sum(counts[label] for label in present)
    gap = 0.018
    usable = 0.86 - gap * max(len(present) - 1, 0)
    y_top = 0.92
    positions: dict[str, tuple[float, float]] = {}
    cursor = y_top
    for label in present:
        height = usable * counts[label] / total if total else 0
        y0 = cursor - height
        positions[label] = (y0, cursor)
        cursor = y0 - gap
    return positions


def draw_flow(
    ax: plt.Axes,
    x0: float,
    y0: float,
    x1: float,
    y1: float,
    width: float,
    color: str,
    alpha: float = 0.24,
) -> None:
    verts = [
        (x0, y0),
        (x0 + 0.16, y0),
        (x1 - 0.16, y1),
        (x1, y1),
    ]
    path = MplPath(verts, [MplPath.MOVETO, MplPath.CURVE4, MplPath.CURVE4, MplPath.CURVE4])
    patch = PathPatch(path, facecolor="none", edgecolor=color, linewidth=width, alpha=alpha, capstyle="round")
    ax.add_patch(patch)


def sorted_stage_order(values: list[str]) -> list[str]:
    return [
        label
        for label, _ in sorted(
            Counter(values).items(),
            key=lambda item: (-item[1], item[0]),
        )
    ]


def extract_cite_keys(text: str) -> list[str]:
    keys: list[str] = []
    for block in re.findall(r"\[@([^\]]+)\]", text):
        for part in block.split(";"):
            cite = part.strip()
            if cite.startswith("@"):
                cite = cite[1:]
            if cite:
                keys.append(cite)
    return keys


def load_application_map() -> dict[str, str]:
    if not MANUSCRIPT.is_file():
        return {}
    text = MANUSCRIPT.read_text(encoding="utf-8")
    lines = text.splitlines()
    current: str | None = None
    section_text: dict[str, list[str]] = defaultdict(list)
    for line in lines:
        if line.startswith("## "):
            current = None
            continue
        if line.startswith("### "):
            title = re.sub(r"\s+\{#.*\}$", "", line[4:]).strip()
            current = title if title in APPLICATION_SECTION_TITLES else None
            continue
        if current is not None:
            section_text[current].append(line)
    mapping: dict[str, str] = {}
    for title, block_lines in section_text.items():
        for key in extract_cite_keys("\n".join(block_lines)):
            mapping[key] = APPLICATION_SECTION_TO_DOMAIN[title]
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


def load_evidence_records() -> list[tuple[str, str, str, str, str]]:
    """Load study-level Sankey paths with explicit evidence for the five shown stages."""
    if not UNIFIED_STUDIES.is_file():
        raise FileNotFoundError(
            f"Missing unified evidence table: {UNIFIED_STUDIES}. "
            "Run paper_library/build_unified_evidence_audit.py first."
        )
    app_map = load_application_map()
    records: list[tuple[str, str, str, str, str]] = []
    for row in read_csv(UNIFIED_STUDIES):
        family = row["family"]
        if family not in EVIDENCE_FAMILY_ORDER:
            continue
        application = app_map.get(row["cite_key"]) or infer_application_domain(
            row.get("title", "")
        )
        doe_labels = [label.strip() for label in row.get("doe_strategy", "").split(";") if label.strip()]
        pattern_labels = [label.strip() for label in row.get("pattern", "").split(";") if label.strip()]
        validation_labels = [label.strip() for label in row.get("validation", "").split(";") if label.strip()]
        if not doe_labels or not pattern_labels or not validation_labels:
            continue
        for doe in doe_labels:
            for pattern in pattern_labels:
                for validation in validation_labels:
                    if (
                        doe in EVIDENCE_DOE_ORDER
                        and pattern in EVIDENCE_PATTERN_ORDER
                        and validation in EVIDENCE_VALIDATION_ORDER
                    ):
                        records.append((family, application, doe, pattern, validation))
    if not records:
        raise RuntimeError("No complete alluvial study paths were found.")
    return records


def build_evidence_alluvial(records: list[tuple[str, str, str, str, str]]) -> None:
    """Draw model class -> application target -> DoE -> integration -> validation."""
    stage_values = [
        [record[index] for record in records]
        for index in range(5)
    ]
    stage_orders = [sorted_stage_order(values) for values in stage_values]
    stage_titles = [
        "Model class",
        "Application target",
        "DoE / training strategy",
        "Integration pattern",
        "Validation",
    ]
    stage_counts = [Counter(values) for values in stage_values]
    stage_positions = [
        node_positions(order, counts)
        for order, counts in zip(stage_orders, stage_counts)
    ]
    transition_counts = [
        Counter((record[index], record[index + 1]) for record in records)
        for index in range(4)
    ]

    fig, ax = plt.subplots(figsize=(17.2, 8.2))
    ax.set_axis_off()
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    xs = [0.05, 0.27, 0.49, 0.71, 0.93]
    node_w = 0.022
    max_transition = max(
        count
        for transitions in transition_counts
        for count in transitions.values()
    )
    scale = 30.0 / max(max_transition, 1)

    for stage_index, transitions in enumerate(transition_counts):
        source_order = stage_orders[stage_index]
        target_order = stage_orders[stage_index + 1]
        source_counts = stage_counts[stage_index]
        target_counts = stage_counts[stage_index + 1]
        source_pos = stage_positions[stage_index]
        target_pos = stage_positions[stage_index + 1]

        for (source, target), count in transitions.items():
            sy0, sy1 = source_pos[source]
            ty0, ty1 = target_pos[target]
            source_index = sum(
                value
                for (left, right), value in transitions.items()
                if left == source
                and target_order.index(right) < target_order.index(target)
            )
            target_index = sum(
                value
                for (left, right), value in transitions.items()
                if right == target
                and source_order.index(left) < source_order.index(source)
            )
            source_y = sy1 - (
                source_index + count / 2
            ) / source_counts[source] * (sy1 - sy0)
            target_y = ty1 - (
                target_index + count / 2
            ) / target_counts[target] * (ty1 - ty0)

            if source == "Not explicitly identified" or target == "Not explicitly identified":
                color = "#A9A9A9"
                alpha = 0.18
            else:
                families = Counter(
                    record[0]
                    for record in records
                    if record[stage_index] == source
                    and record[stage_index + 1] == target
                )
                family = families.most_common(1)[0][0]
                color = EVIDENCE_FAMILY_COLORS[family]
                alpha = 0.23
            draw_flow(
                ax,
                xs[stage_index] + node_w,
                source_y,
                xs[stage_index + 1] - node_w,
                target_y,
                max(0.7, count * scale),
                color,
                alpha=alpha,
            )

    for stage_index, (x, title, positions, counts) in enumerate(
        zip(xs, stage_titles, stage_positions, stage_counts)
    ):
        ax.text(
            x,
            0.985,
            title,
            ha="center",
            va="top",
            fontsize=11,
            fontweight="bold",
        )
        for label, (y0, y1) in positions.items():
            if stage_index == 0:
                color = EVIDENCE_FAMILY_COLORS[label]
            elif label == "Not explicitly identified":
                color = "#BDBDBD"
            else:
                color = "#E4E4E4"
            ax.add_patch(
                Rectangle(
                    (x - node_w / 2, y0),
                    node_w,
                    y1 - y0,
                    facecolor=color,
                    edgecolor="#333333",
                    linewidth=0.7,
                )
            )
            if stage_index == 0:
                text_x = x - 0.019
                ha = "right"
            else:
                text_x = x + 0.019
                ha = "left"
            ax.text(
                text_x,
                (y0 + y1) / 2,
                f"{label} ({counts[label]})",
                ha=ha,
                va="center",
                fontsize=7.2,
            )

    fig.savefig(
        FIG / "fig_taxonomy_alluvial_flow_evidence.png",
        dpi=300,
        bbox_inches="tight",
    )
    plt.close(fig)


def build_alluvial(records: list[tuple[str, str, str, str]]) -> None:
    family_counts = Counter(f for f, _, _, _ in records)
    target_counts = Counter(t for _, t, _, _ in records)
    role_counts = Counter(r for _, _, r, _ in records)
    ft_counts = Counter((f, t) for f, t, _, _ in records)
    tr_counts = Counter((t, r) for _, t, r, _ in records)

    family_pos = node_positions(FAMILY_ORDER, family_counts)
    target_pos = node_positions(TARGET_ORDER, target_counts)
    role_pos = node_positions(ROLE_ORDER, role_counts)

    fig, ax = plt.subplots(figsize=(11.8, 7.2))
    ax.set_axis_off()
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)

    xs = {"family": 0.12, "target": 0.50, "role": 0.88}
    node_w = 0.035
    scale = 22.0 / max(max(ft_counts.values()), max(tr_counts.values()), 1)

    for (family, target), count in ft_counts.items():
        fy0, fy1 = family_pos[family]
        ty0, ty1 = target_pos[target]
        source_index = sum(v for (f, t), v in ft_counts.items() if f == family and TARGET_ORDER.index(t) < TARGET_ORDER.index(target))
        target_index = sum(v for (f, t), v in ft_counts.items() if t == target and FAMILY_ORDER.index(f) < FAMILY_ORDER.index(family))
        fy = fy1 - (source_index + count / 2) / family_counts[family] * (fy1 - fy0)
        ty = ty1 - (target_index + count / 2) / target_counts[target] * (ty1 - ty0)
        draw_flow(ax, xs["family"] + node_w, fy, xs["target"] - node_w, ty, max(0.7, count * scale), FAMILY_COLORS[family])

    for (target, role), count in tr_counts.items():
        ty0, ty1 = target_pos[target]
        ry0, ry1 = role_pos[role]
        source_index = sum(v for (t, r), v in tr_counts.items() if t == target and ROLE_ORDER.index(r) < ROLE_ORDER.index(role))
        target_index = sum(v for (t, r), v in tr_counts.items() if r == role and TARGET_ORDER.index(t) < TARGET_ORDER.index(target))
        ty = ty1 - (source_index + count / 2) / target_counts[target] * (ty1 - ty0)
        ry = ry1 - (target_index + count / 2) / role_counts[role] * (ry1 - ry0)
        dominant_family = Counter(f for f, t, r, _ in records if t == target and r == role).most_common(1)[0][0]
        draw_flow(ax, xs["target"] + node_w, ty, xs["role"] - node_w, ry, max(0.7, count * scale), FAMILY_COLORS[dominant_family], alpha=0.20)

    def draw_nodes(x: float, positions: dict[str, tuple[float, float]], counts: Counter[str], title: str, color_lookup: dict[str, str] | None = None) -> None:
        ax.text(x, 0.985, title, ha="center", va="top", fontsize=11, fontweight="bold")
        for label, (y0, y1) in positions.items():
            color = color_lookup.get(label, "#D9D9D9") if color_lookup else "#D9D9D9"
            ax.add_patch(Rectangle((x - node_w / 2, y0), node_w, y1 - y0, facecolor=color, edgecolor="#333333", linewidth=0.7))
            ha = "right" if x < 0.5 else "left"
            tx = x - 0.026 if x < 0.5 else x + 0.026
            ax.text(tx, (y0 + y1) / 2, f"{label} ({counts[label]})", ha=ha, va="center", fontsize=8.5)

    draw_nodes(xs["family"], family_pos, family_counts, "Model class", FAMILY_COLORS)
    draw_nodes(xs["target"], target_pos, target_counts, "Surrogate target")
    draw_nodes(xs["role"], role_pos, role_counts, "Optimizer role")

    ax.set_title("Draft alluvial taxonomy flow: model class -> surrogate target -> optimizer role", fontsize=14, fontweight="bold", pad=16)
    ax.text(0.01, 0.015, f"Source: curated library bucket tags, non-review model-class records n={len(records)}.", fontsize=8, color="#555555")
    save(fig, "fig_taxonomy_alluvial_flow_draft")


def build_lollipop(records: list[tuple[str, str, str, str]]) -> None:
    archetype_counts = Counter(records)
    top = archetype_counts.most_common(16)
    labels = [f"{f} -> {t} -> {r}" for (f, t, r, _), _ in top]
    counts = [n for _, n in top]
    trusts = [trust for (_, _, _, trust), _ in top]

    fig, ax = plt.subplots(figsize=(11.2, 7.4))
    y = list(range(len(top)))[::-1]
    for yy, count, trust in zip(y, counts, trusts):
        ax.hlines(yy, 0, count, color="#BDBDBD", linewidth=2)
        ax.scatter(count, yy, s=115, color=TRUST_COLORS[trust], edgecolor="#333333", linewidth=0.8, zorder=3)
        ax.text(count + 0.7, yy, str(count), va="center", fontsize=8.5, fontweight="bold")
    ax.set_yticks(y, labels)
    ax.set_xlabel("Paper count")
    ax.set_title("Draft top taxonomy archetypes: model class -> target -> optimizer role", loc="left", fontweight="bold")
    ax.grid(axis="x", color="#DDDDDD")
    ax.set_axisbelow(True)
    ax.set_xlim(0, max(counts) + 5 if counts else 1)
    handles = [
        Line2D([0], [0], marker="o", color="none", markerfacecolor=TRUST_COLORS[t], markeredgecolor="#333333", markersize=8, label=TRUST_LABELS[t])
        for t in TRUST_ORDER
    ]
    ax.legend(handles=handles, title="Dominant trust mechanism", loc="lower right", frameon=False, fontsize=8, title_fontsize=9)
    fig.text(
        0.01,
        0.01,
        f"Source: curated library bucket tags, non-review model-class records n={len(records)}. Draft archetypes use conservative bucket-derived labels.",
        fontsize=8,
        color="#555555",
    )
    fig.tight_layout(rect=(0, 0.04, 1, 1))
    save(fig, "fig_taxonomy_archetypes_lollipop_draft")


def main() -> None:
    records = load_evidence_records()
    with OUT_COUNTS.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["family", "target", "doe", "pattern", "validation", "n"])
        for (family, target, doe, pattern, validation), count in sorted(
            Counter(records).items()
        ):
            writer.writerow([family, target, doe, pattern, validation, count])
    build_evidence_alluvial(records)
    print(f"plotted_records={len(records)}")


if __name__ == "__main__":
    main()
