"""Build draft evidence-rigor and optimizer-embedding taxonomy figures.

These figures are prototypes, not final audited manuscript figures.

``fig_evidence_rigor_quadrant_draft`` uses the PDF-backed evidence-card layer
because DoE and validation are explicit there.

``fig_optimizer_embedding_taxonomy_draft`` uses the larger curated library and
maps existing bucket tags to coarse optimizer role, surrogate target criticality,
dominant model class and dominant trust signal. The mappings are intentionally
conservative and written in this script so they can be reviewed before the
figure is promoted to the manuscript.
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


ROOT = Path(__file__).resolve().parents[2]
FIG = ROOT / "figures"
CSV = FIG / "csv"
CARDS = ROOT / "paper_library" / "sec8_evidence_cards.csv"
MANIFEST = ROOT / "paper_library" / "review_paper_library_manifest.csv"
BUCKETS = ROOT / "paper_library" / "review_paper_library_buckets.csv"

OUT_RIGOR_COUNTS = CSV / "fig_evidence_rigor_quadrant_draft_counts.csv"
OUT_OPT_COUNTS = CSV / "fig_optimizer_embedding_taxonomy_draft_counts.csv"


ROLE_ORDER = [
    "Input / weak coupling",
    "P1/P3 replacement",
    "P2 search acceleration",
    "P4 decomposition",
    "P5 uncertainty",
]

ROLE_BUCKETS = {
    "P1/P3 replacement": {
        "B07_constraint_aware",
        "B09_decision_focused_l2o",
        "B17_ed_uc",
        "B18_opf",
    },
    "P2 search acceleration": {
        "B10_doe_active_learning",
        "B11_multi_fidelity",
        "B12_bayes_accel",
        "B23_moo_design",
        "B25_moo_algorithms_nsga",
        "B26_moo_metaheuristics",
    },
    "P4 decomposition": {"B14_decomposition"},
    "P5 uncertainty": {"B15_uncertainty", "B24_stochastic_robust"},
}

ROLE_COLORS = {
    "Input / weak coupling": "#8C8C8C",
    "P1/P3 replacement": "#1B9E77",
    "P2 search acceleration": "#66A61E",
    "P4 decomposition": "#7570B3",
    "P5 uncertainty": "#1F78B4",
}

FAMILY_ORDER = [
    "PCE/RSM",
    "GP/Kriging",
    "RBF/Kernel",
    "Tree",
    "NN",
    "Constraint NN",
    "Hybrid/PINN",
    "L2O",
]

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
    "Mixed": "#7F7F7F",
}

TRUST_ORDER = [
    "basic",
    "adaptive",
    "uncertainty",
    "physics",
    "constraint",
    "decision",
]

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


def save(fig: plt.Figure, stem: str) -> None:
    for ext in ("png",):
        fig.savefig(FIG / f"{stem}.{ext}", dpi=300, bbox_inches="tight")
    plt.close(fig)


def normalized(text: str) -> str:
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


def strongest_role(tags: set[str]) -> str:
    """Return the most optimizer-embedded role signalled by the bucket tags."""
    for role in reversed(ROLE_ORDER[1:]):
        if tags & ROLE_BUCKETS[role]:
            return role
    return "Input / weak coupling"


def family_from_tags(tags: set[str]) -> str | None:
    found = [label for label in FAMILY_ORDER if tags & FAMILY_BUCKETS[label]]
    if not found:
        return None
    # Prefer specialised labels over generic NN when both are present.
    for label in ("L2O", "Hybrid/PINN", "Constraint NN"):
        if label in found:
            return label
    return found[0]


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


def target_criticality(row: dict[str, str], tags: set[str]) -> str:
    """Map tags/title to a coarse target axis ordered by optimizer criticality."""
    title = normalized(row.get("title", ""))
    if tags & {"B09_decision_focused_l2o"}:
        return "solution / policy"
    if tags & {"B15_uncertainty", "B24_stochastic_robust"}:
        return "uncertainty / risk"
    if tags & {"B07_constraint_aware", "B18_opf"}:
        return "constraints / states"
    if tags & {"B17_ed_uc", "B19_capacity_expansion", "B20_district_heating", "B21_mes_sector_coupling", "B22_microgrid_hub", "B23_moo_design"}:
        return "objective / system response"
    if re.search(r"\b(load|forecast|wind|solar|pv|price|demand)\b", title):
        return "exogenous input"
    return "objective / system response"


TARGET_ORDER = [
    "exogenous input",
    "objective / system response",
    "constraints / states",
    "uncertainty / risk",
    "solution / policy",
]


def doe_depth(doe: str) -> tuple[int, str]:
    text = normalized(doe)
    if not text or text == "--":
        return 0, "unclear"
    if any(term in text for term in ("historical", "synthetic")):
        return 1, "batch / historical"
    if any(term in text for term in ("lhs", "quasi", "factorial", "doe")):
        return 2, "static structured DoE"
    if any(term in text for term in ("adaptive", "active", "multi-fidelity", "transfer")):
        return 3, "sequential / multi-source"
    return 1, "batch / historical"


def validation_depth(validation: str) -> tuple[int, str]:
    text = normalized(validation)
    if not text or text == "--":
        return 0, "unclear"
    if any(term in text for term in ("decision-aware", "regret", "gap", "stress test")):
        return 3, "decision / robustness"
    if any(term in text for term in ("feasibility", "constraint", "uncertainty", "interval calibration")):
        return 2, "operational / uncertainty"
    if any(term in text for term in ("rmse", "mae", "r²", "r2", "point metrics")):
        return 1, "point metrics"
    return 1, "point metrics"


def role_from_card(row: dict[str, str]) -> str:
    pattern = (row.get("pattern") or "").strip()
    return {
        "P1": "P1/P3 replacement",
        "P2": "P2 search acceleration",
        "P4": "P4 decomposition",
        "P5": "P5 uncertainty",
    }.get(pattern, "Input / weak coupling")


def build_evidence_rigor() -> None:
    rows = read_csv(CARDS)
    cell_counts: Counter[tuple[int, int]] = Counter()
    cell_roles: dict[tuple[int, int], Counter[str]] = defaultdict(Counter)
    cell_families: dict[tuple[int, int], Counter[str]] = defaultdict(Counter)

    for row in rows:
        x, _ = doe_depth(row.get("doe", ""))
        y, _ = validation_depth(row.get("validation", ""))
        cell = (x, y)
        cell_counts[cell] += 1
        cell_roles[cell][role_from_card(row)] += 1
        cell_families[cell][row.get("family", "--") or "--"] += 1

    with OUT_RIGOR_COUNTS.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["doe_depth", "validation_depth", "dominant_role", "dominant_family", "n"])
        for cell, count in sorted(cell_counts.items()):
            writer.writerow(
                [
                    cell[0],
                    cell[1],
                    cell_roles[cell].most_common(1)[0][0],
                    cell_families[cell].most_common(1)[0][0],
                    count,
                ]
            )

    fig, ax = plt.subplots(figsize=(8.7, 7.5))
    max_count = max(cell_counts.values()) if cell_counts else 1
    for (x, y), count in cell_counts.items():
        role = cell_roles[(x, y)].most_common(1)[0][0]
        family = cell_families[(x, y)].most_common(1)[0][0]
        ax.scatter(
            x,
            y,
            s=180 + 1450 * count / max_count,
            facecolor=ROLE_COLORS[role],
            edgecolor="#2F2F2F",
            linewidth=1.1,
            alpha=0.82,
        )
        ax.text(x, y + 0.03, str(count), ha="center", va="center", fontsize=10, color="white", fontweight="bold")
        ax.text(x, y - 0.25, family.replace(" / ", "/"), ha="center", va="center", fontsize=7.2, color="#252525")

    ax.set_xticks(
        range(4),
        ["unclear", "batch /\nhistorical", "static\nstructured DoE", "sequential /\nmulti-source"],
    )
    ax.set_yticks(
        range(4),
        ["unclear", "point\nmetrics", "operational /\nuncertainty", "decision /\nrobustness"],
    )
    ax.set_xlim(-0.55, 3.55)
    ax.set_ylim(-0.55, 3.55)
    ax.grid(True, color="#D9D9D9")
    ax.set_axisbelow(True)
    ax.set_xlabel("Reported training-design depth")
    ax.set_ylabel("Reported validation depth")
    ax.set_title("Evidence-rigor map: DoE depth × validation depth", loc="left", fontweight="bold")

    handles = [
        Line2D([0], [0], marker="o", color="none", markerfacecolor=color, markersize=9, label=label)
        for label, color in ROLE_COLORS.items()
    ]
    ax.legend(handles=handles, title="Dominant integration role", loc="upper left", bbox_to_anchor=(0, -0.20), ncol=2, frameon=False, fontsize=8)
    fig.text(
        0.01,
        0.01,
        "Source: sec8_evidence_cards.csv; PDF-backed evidence-card subset. Bubble size = paper count; label below count = dominant model class.",
        fontsize=8,
        color="#4D4D4D",
    )
    fig.tight_layout(rect=(0, 0.11, 1, 1))
    save(fig, "fig_evidence_rigor_quadrant_draft")


def build_optimizer_embedding() -> None:
    rows = [r for r in read_csv(MANIFEST) if r.get("primary_bucket") != "B01_cornerstone_reviews"]
    extra = bucket_index()
    cell_counts: Counter[tuple[str, str]] = Counter()
    cell_families: dict[tuple[str, str], Counter[str]] = defaultdict(Counter)
    cell_trust: dict[tuple[str, str], Counter[str]] = defaultdict(Counter)
    counted: set[str] = set()

    for row in rows:
        tags = merged_buckets(row, extra)
        family = family_from_tags(tags)
        if not family:
            continue
        role = strongest_role(tags)
        target = target_criticality(row, tags)
        trust = trust_from_tags(tags)
        cell = (role, target)
        cell_counts[cell] += 1
        cell_families[cell][family] += 1
        cell_trust[cell][trust] += 1
        counted.add(row["cite_key"])

    with OUT_OPT_COUNTS.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["integration_role", "surrogate_target", "dominant_family", "dominant_trust", "n"])
        for cell, count in sorted(cell_counts.items()):
            writer.writerow(
                [
                    cell[0],
                    cell[1],
                    cell_families[cell].most_common(1)[0][0],
                    TRUST_LABELS[cell_trust[cell].most_common(1)[0][0]],
                    count,
                ]
            )

    fig, ax = plt.subplots(figsize=(10.2, 8.1))
    x_pos = {role: i for i, role in enumerate(ROLE_ORDER)}
    y_pos = {target: i for i, target in enumerate(TARGET_ORDER)}
    max_count = max(cell_counts.values()) if cell_counts else 1

    for (role, target), count in cell_counts.items():
        family = cell_families[(role, target)].most_common(1)[0][0]
        trust = cell_trust[(role, target)].most_common(1)[0][0]
        ax.scatter(
            x_pos[role],
            y_pos[target],
            s=170 + 1600 * count / max_count,
            facecolor=FAMILY_COLORS[family],
            edgecolor=TRUST_COLORS[trust],
            linewidth=3.0,
            alpha=0.82,
        )
        ax.text(x_pos[role], y_pos[target] + 0.04, str(count), ha="center", va="center", color="white", fontsize=10, fontweight="bold")
        ax.text(x_pos[role], y_pos[target] - 0.25, family, ha="center", va="center", color="#252525", fontsize=7.2)

    ax.set_xticks(range(len(ROLE_ORDER)), ROLE_ORDER, rotation=24, ha="right")
    ax.set_yticks(range(len(TARGET_ORDER)), TARGET_ORDER)
    ax.set_xlim(-0.55, len(ROLE_ORDER) - 0.45)
    ax.set_ylim(-0.55, len(TARGET_ORDER) - 0.45)
    ax.grid(True, color="#D9D9D9")
    ax.set_axisbelow(True)
    ax.set_xlabel("Optimizer integration role", labelpad=10)
    ax.set_ylabel("Surrogate target criticality")
    ax.set_title("Optimizer-embedding taxonomy map", loc="left", fontweight="bold")

    family_handles = [
        Line2D([0], [0], marker="o", color="none", markerfacecolor=FAMILY_COLORS[f], markersize=8, label=f)
        for f in FAMILY_ORDER
    ]
    trust_handles = [
        Line2D([0], [0], marker="o", color=TRUST_COLORS[t], markerfacecolor="white", markeredgewidth=2.5, markersize=8, label=TRUST_LABELS[t])
        for t in TRUST_ORDER
    ]
    leg1 = ax.legend(handles=family_handles, title="Dominant model class", loc="upper left", bbox_to_anchor=(0.0, -0.30), ncol=4, frameon=False, fontsize=8)
    ax.add_artist(leg1)
    ax.legend(handles=trust_handles, title="Dominant trust signal (ring)", loc="upper left", bbox_to_anchor=(0.55, -0.30), ncol=2, frameon=False, fontsize=8)

    fig.text(
        0.01,
        0.01,
        (
            f"Source: curated library manifest + bucket tags; non-review records with model-class tags n={len(counted)}. "
            "Bubble size = paper count; fill = dominant model class; ring = dominant trust signal. Draft bucket-based classification."
        ),
        fontsize=8,
        color="#4D4D4D",
    )
    fig.tight_layout(rect=(0, 0.19, 1, 1))
    save(fig, "fig_optimizer_embedding_taxonomy_draft")


def main() -> None:
    build_evidence_rigor()
    build_optimizer_embedding()


if __name__ == "__main__":
    main()
