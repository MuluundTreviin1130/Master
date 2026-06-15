"""Draft quantitative taxonomy figure for the curated review library.

The figure is intentionally conservative: it visualizes only labels that are
already present in the curated library manifest/bucket layer. It does not infer
new paper properties from free text. That makes the output useful as a design
draft before a stricter PDF/abstract audit is added.
"""

from __future__ import annotations

import csv
from collections import Counter, defaultdict
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D


ROOT = Path(__file__).resolve().parents[2]
FIG = ROOT / "figures"
CSV = FIG / "csv"
MANIFEST = ROOT / "paper_library" / "review_paper_library_manifest.csv"
BUCKETS = ROOT / "paper_library" / "review_paper_library_buckets.csv"
OUT_COUNTS = CSV / "fig_taxonomy_bubble_draft_counts.csv"


FAMILY_MAP = {
    "B02_gp_kriging": "GP / kriging",
    "B03_pce_response_surface": "PCE / RSM",
    "B04_rbf_kernel": "RBF / kernel",
    "B05_tree_ensembles": "Tree ensembles",
    "B06_neural_surrogates": "Neural network",
    "B07_constraint_aware": "Constraint-aware NN",
    "B08_hybrid_pinn": "Hybrid / PINN",
    "B09_decision_focused_l2o": "Decision-focused / L2O",
}

FAMILY_ORDER = [
    "PCE / RSM",
    "GP / kriging",
    "RBF / kernel",
    "Tree ensembles",
    "Neural network",
    "Constraint-aware NN",
    "Hybrid / PINN",
    "Decision-focused / L2O",
]

ROLE_ORDER = [
    "Weak / input proxy",
    "P1/P3 direct replacement",
    "P2 search acceleration",
    "P4 decomposition",
    "P5 uncertainty handling",
]

ROLE_BUCKETS = {
    "P1/P3 direct replacement": {
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
    "P5 uncertainty handling": {"B15_uncertainty", "B24_stochastic_robust"},
}

TARGET_MAP = {
    "B17_ed_uc": "ED / UC",
    "B18_opf": "OPF",
    "B19_capacity_expansion": "Expansion",
    "B20_district_heating": "District heating",
    "B21_mes_sector_coupling": "MES / sector coupling",
    "B22_microgrid_hub": "Microgrid / hub",
    "B23_moo_design": "MOO design",
    "B24_stochastic_robust": "Stochastic / robust",
}

TRUST_COLORS = {
    "Decision-aware / validation": "#D95F02",
    "Constraint-aware": "#1B9E77",
    "Physics-informed": "#7570B3",
    "Uncertainty-aware": "#1F78B4",
    "Adaptive / BO": "#66A61E",
    "Basic / unspecified": "#8C8C8C",
}


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def merged_buckets(row: dict[str, str], bucket_index: dict[str, set[str]]) -> set[str]:
    """Return all bucket tags known for a paper without relying on one source."""
    tags: set[str] = set()
    for raw in (row.get("primary_bucket", ""), row.get("all_buckets", "")):
        for tag in raw.split(";"):
            tag = tag.strip()
            if tag:
                tags.add(tag)
    tags.update(bucket_index.get(row["cite_key"], set()))
    return tags


def families(tags: set[str]) -> list[str]:
    """Map bucket tags to plotted model classes."""
    found = [label for tag, label in FAMILY_MAP.items() if tag in tags]
    return [label for label in FAMILY_ORDER if label in found]


def roles(tags: set[str]) -> list[str]:
    """Map bucket tags to coarse optimizer integration roles."""
    found: list[str] = []
    for role in ROLE_ORDER[1:]:
        if tags & ROLE_BUCKETS[role]:
            found.append(role)
    return found or ["Weak / input proxy"]


def dominant_trust(tags: set[str]) -> str:
    """Pick the strongest conservative trust/validation signal for color."""
    if tags & {"B09_decision_focused_l2o", "B16_validation"}:
        return "Decision-aware / validation"
    if "B07_constraint_aware" in tags:
        return "Constraint-aware"
    if "B08_hybrid_pinn" in tags:
        return "Physics-informed"
    if tags & {"B15_uncertainty", "B24_stochastic_robust"}:
        return "Uncertainty-aware"
    if tags & {"B10_doe_active_learning", "B11_multi_fidelity", "B12_bayes_accel"}:
        return "Adaptive / BO"
    return "Basic / unspecified"


def load_bucket_index() -> dict[str, set[str]]:
    index: dict[str, set[str]] = defaultdict(set)
    if not BUCKETS.is_file():
        return index
    for row in read_csv(BUCKETS):
        key = row.get("cite_key", "").strip()
        tag = row.get("bucket_id", "").strip()
        if key and tag:
            index[key].add(tag)
    return index


def main() -> None:
    rows = read_csv(MANIFEST)
    bucket_index = load_bucket_index()

    # Primary review papers summarize literature rather than being individual
    # application studies, so the draft figure excludes them from quantitative
    # method/application counts.
    records = [r for r in rows if r.get("primary_bucket") != "B01_cornerstone_reviews"]

    bubble_counts: Counter[tuple[str, str, str]] = Counter()
    target_counts: Counter[tuple[str, str]] = Counter()
    paper_counted: set[str] = set()

    for row in records:
        tags = merged_buckets(row, bucket_index)
        row_families = families(tags)
        if not row_families:
            continue
        row_roles = roles(tags)
        trust = dominant_trust(tags)
        paper_counted.add(row["cite_key"])

        for family in row_families:
            for role in row_roles:
                bubble_counts[(family, role, trust)] += 1
            for tag, target in TARGET_MAP.items():
                if tag in tags:
                    target_counts[(family, target)] += 1

    with OUT_COUNTS.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["family", "integration_role", "trust_signal", "n"])
        for (family, role, trust), count in sorted(bubble_counts.items()):
            writer.writerow([family, role, trust, count])

    fig, (ax, ax2) = plt.subplots(
        1,
        2,
        figsize=(12.8, 6.8),
        gridspec_kw={"width_ratios": [1.35, 1.0]},
    )

    x_pos = {role: i for i, role in enumerate(ROLE_ORDER)}
    y_pos = {family: i for i, family in enumerate(FAMILY_ORDER)}
    max_count = max(bubble_counts.values()) if bubble_counts else 1

    for (family, role, trust), count in bubble_counts.items():
        ax.scatter(
            x_pos[role],
            y_pos[family],
            s=80 + 980 * count / max_count,
            c=TRUST_COLORS[trust],
            alpha=0.78,
            edgecolor="white",
            linewidth=1.1,
        )
        if count >= 5:
            ax.text(
                x_pos[role],
                y_pos[family],
                str(count),
                ha="center",
                va="center",
                fontsize=8,
                color="white",
                fontweight="bold",
            )

    ax.set_xticks(range(len(ROLE_ORDER)), ROLE_ORDER, rotation=25, ha="right")
    ax.set_yticks(range(len(FAMILY_ORDER)), FAMILY_ORDER)
    ax.set_xlim(-0.55, len(ROLE_ORDER) - 0.45)
    ax.set_ylim(-0.55, len(FAMILY_ORDER) - 0.45)
    ax.grid(True, color="#D9D9D9", linewidth=0.8)
    ax.set_axisbelow(True)
    ax.set_title("A. Model class × optimizer integration", loc="left", fontweight="bold")
    ax.set_xlabel("Optimizer integration role")
    ax.set_ylabel("Surrogate model class")

    handles = [
        Line2D(
            [0],
            [0],
            marker="o",
            color="none",
            markerfacecolor=color,
            markeredgecolor="white",
            markersize=8,
            label=label,
        )
        for label, color in TRUST_COLORS.items()
    ]
    ax.legend(
        handles=handles,
        title="Dominant trust signal",
        loc="upper left",
        bbox_to_anchor=(0.0, -0.29),
        ncol=2,
        frameon=False,
        fontsize=8,
        title_fontsize=9,
    )

    top_targets = [target for target, _ in Counter(t for _, t in target_counts).most_common(6)]
    target_colors = {
        "MES / sector coupling": "#4C78A8",
        "Microgrid / hub": "#F58518",
        "MOO design": "#54A24B",
        "ED / UC": "#B279A2",
        "OPF": "#E45756",
        "Stochastic / robust": "#72B7B2",
        "Expansion": "#9D755D",
        "District heating": "#BAB0AC",
    }

    left = [0] * len(FAMILY_ORDER)
    for target in top_targets:
        vals = [target_counts.get((family, target), 0) for family in FAMILY_ORDER]
        ax2.barh(
            range(len(FAMILY_ORDER)),
            vals,
            left=left,
            color=target_colors.get(target, "#999999"),
            label=target,
            height=0.68,
        )
        left = [a + b for a, b in zip(left, vals)]

    ax2.set_yticks(range(len(FAMILY_ORDER)), FAMILY_ORDER)
    ax2.set_xlabel("Tagged paper count")
    ax2.set_title("B. Main application targets", loc="left", fontweight="bold")
    ax2.grid(axis="x", color="#D9D9D9", linewidth=0.8)
    ax2.set_axisbelow(True)
    ax2.legend(loc="upper left", bbox_to_anchor=(0.0, -0.16), frameon=False, fontsize=8)

    fig.suptitle(
        "Draft quantitative taxonomy map of surrogate-model use in the curated library",
        y=0.99,
        fontsize=14,
        fontweight="bold",
    )
    fig.text(
        0.01,
        0.01,
        (
            f"Source: review_paper_library_manifest.csv + review_paper_library_buckets.csv; "
            f"non-review records with model-class tags n={len(paper_counted)}. "
            "Counts are bucket-based draft classifications, not yet PDF/abstract-audited claims."
        ),
        fontsize=8,
        color="#4D4D4D",
    )
    fig.tight_layout(rect=(0, 0.07, 1, 0.95))

    for ext in ("png",):
        fig.savefig(FIG / f"fig_taxonomy_bubble_draft.{ext}", dpi=300, bbox_inches="tight")
    plt.close(fig)


if __name__ == "__main__":
    main()
