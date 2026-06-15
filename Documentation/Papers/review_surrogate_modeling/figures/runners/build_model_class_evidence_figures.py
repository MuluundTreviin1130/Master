"""Build the evidence-based bubble figure for the model-class section.

The figure uses assigned model classes and integration patterns from the
Section-8 evidence cards. Bubble colors use high-confidence surrogate-target
assignments from the separate target audit. Unassigned rows are omitted.
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
CARDS = ROOT / "paper_library" / "sec8_evidence_cards.csv"
TARGET_AUDIT = ROOT / "paper_library" / "surrogate_target_audit.csv"
OUT_COUNTS = CSV / "fig_model_class_evidence_counts.csv"

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
    "Neural network",
    "RBF / kernel",
    "Tree ensembles",
    "Constraint-aware NN",
]
TARGET_ORDER = [
    "Exogenous inputs",
    "Objective values",
    "Physical states or constraints",
    "Probability distributions / chance-constraint terms",
    "Decisions / solution-related objects",
]
TARGET_COLORS = {
    "Exogenous inputs": "#4E79A7",
    "Objective values": "#F28E2B",
    "Physical states or constraints": "#59A14F",
    "Probability distributions / chance-constraint terms": "#9467BD",
    "Decisions / solution-related objects": "#E15759",
}


def read_cards() -> list[dict[str, str]]:
    with CARDS.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def read_target_audit() -> dict[str, dict[str, str]]:
    if not TARGET_AUDIT.is_file():
        raise FileNotFoundError(
            f"Missing target audit: {TARGET_AUDIT}. "
            "Run paper_library/build_surrogate_target_audit.py first."
        )
    with TARGET_AUDIT.open(encoding="utf-8", newline="") as handle:
        return {row["cite_key"]: row for row in csv.DictReader(handle)}


def assigned(value: str | None) -> str | None:
    value = (value or "").strip()
    return value if value and value != "--" else None


def save(fig: plt.Figure, stem: str) -> None:
    fig.savefig(FIG / f"{stem}.png", dpi=300, bbox_inches="tight")
    plt.close(fig)


def build_bubble(
    bubble_counts: Counter[tuple[str, str]],
    bubble_targets: dict[tuple[str, str], Counter[str]],
    assigned_n: int,
    total_n: int,
) -> None:
    x_pattern = {pattern: i for i, pattern in enumerate(PATTERN_ORDER)}
    y_family = {family: i for i, family in enumerate(FAMILY_ORDER)}
    max_count = max(bubble_counts.values()) if bubble_counts else 1

    fig, ax = plt.subplots(figsize=(9.2, 6.0))
    for (family, pattern), count in bubble_counts.items():
        target = bubble_targets[(family, pattern)].most_common(1)[0][0]
        ax.scatter(
            x_pattern[pattern],
            y_family[family],
            s=65 + 900 * count / max_count,
            color=TARGET_COLORS[target],
            edgecolor="white",
            linewidth=0.9,
            alpha=0.84,
        )
        ax.text(
            x_pattern[pattern],
            y_family[family],
            str(count),
            ha="center",
            va="center",
            color="white",
            fontsize=8,
            fontweight="bold",
        )

    ax.set_xticks(
        range(len(PATTERN_ORDER)),
        [PATTERN_LABELS[pattern] for pattern in PATTERN_ORDER],
    )
    ax.set_yticks(range(len(FAMILY_ORDER)), FAMILY_ORDER)
    ax.set_xlabel("Integration pattern")
    ax.set_ylabel("Surrogate model class")
    ax.grid(True, color="#DDDDDD")
    ax.set_axisbelow(True)

    handles = [
        Line2D(
            [0],
            [0],
            marker="o",
            color="none",
            markerfacecolor=TARGET_COLORS[label],
            markersize=7,
            label=label,
        )
        for label in TARGET_ORDER
        if any(label in counts for counts in bubble_targets.values())
    ]
    ax.legend(
        handles=handles,
        title="Dominant surrogate target",
        loc="lower center",
        bbox_to_anchor=(0.5, 1.02),
        ncol=2,
        borderaxespad=0,
        frameon=False,
        fontsize=7.2,
        title_fontsize=8,
    )
    fig.tight_layout()
    save(fig, "fig_model_class_integration_bubble_evidence")


def main() -> None:
    rows = read_cards()
    target_audit = read_target_audit()
    bubble_counts: Counter[tuple[str, str]] = Counter()
    bubble_targets: dict[tuple[str, str], Counter[str]] = defaultdict(Counter)

    for row in rows:
        family = assigned(row.get("family"))
        pattern = assigned(row.get("pattern"))
        audit = target_audit.get(row["cite_key"], {})
        target = assigned(audit.get("target")) if audit.get("confidence") == "high" else None
        if family in FAMILY_ORDER and pattern in PATTERN_ORDER and target in TARGET_ORDER:
            bubble_counts[(family, pattern)] += 1
            bubble_targets[(family, pattern)][target] += 1

    assigned_bubble_n = sum(bubble_counts.values())

    with OUT_COUNTS.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["figure", "model_class", "integration_pattern", "dominant_target", "n"])
        for (family, pattern), count in sorted(bubble_counts.items()):
            target = bubble_targets[(family, pattern)].most_common(1)[0][0]
            writer.writerow(["bubble", family, pattern, target, count])

    build_bubble(bubble_counts, bubble_targets, assigned_bubble_n, len(rows))


if __name__ == "__main__":
    main()
