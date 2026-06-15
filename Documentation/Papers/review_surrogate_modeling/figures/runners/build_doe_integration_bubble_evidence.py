"""Build the evidence-based DoE by integration-pattern bubble figure.

Only high-confidence DoE assignments from ``doe_evidence_audit.csv`` enter
the plot. Bubble size is the number of studies in a cell; color is the
dominant surrogate model class. The layout follows the standalone model-class
bubble figure so both manuscript figures share one visual grammar.
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
AUDIT = ROOT / "paper_library" / "doe_evidence_audit.csv"
OUT_COUNTS = CSV / "fig_doe_integration_bubble_evidence_counts.csv"

PATTERN_ORDER = ["P1", "P2", "P4", "P5"]
PATTERN_LABELS = {
    "P1": "P1\nreplacement",
    "P2": "P2\nacceleration",
    "P4": "P4\ndecomposition",
    "P5": "P5\nuncertainty",
}

STRATEGY_ORDER = [
    "Latin hypercube sampling",
    "Quasi-Monte Carlo / sparse-grid collocation",
    "Factorial / response-surface design",
    "Adaptive sampling",
    "Active learning",
    "Multi-fidelity training",
    "Transfer learning",
]
STRATEGY_LABELS = {
    "Latin hypercube sampling": "Latin hypercube sampling",
    "Quasi-Monte Carlo / sparse-grid collocation": "Quasi-Monte Carlo /\nsparse-grid collocation",
    "Factorial / response-surface design": "Factorial /\nresponse-surface design",
    "Adaptive sampling": "Adaptive sampling",
    "Active learning": "Active learning",
    "Multi-fidelity training": "Multi-fidelity training",
    "Transfer learning": "Transfer learning",
}

FAMILY_ORDER = [
    "PCE / RSM",
    "GP / kriging",
    "Neural network",
    "RBF / kernel",
    "Tree ensembles",
    "Constraint-aware NN",
]
FAMILY_COLORS = {
    "PCE / RSM": "#9467BD",
    "GP / kriging": "#4E79A7",
    "Neural network": "#E15759",
    "RBF / kernel": "#59A14F",
    "Tree ensembles": "#F28E2B",
    "Constraint-aware NN": "#76B7B2",
}


def read_audit() -> list[dict[str, str]]:
    if not AUDIT.is_file():
        raise FileNotFoundError(
            f"Missing DoE audit: {AUDIT}. "
            "Run paper_library/build_doe_evidence_audit.py first."
        )
    with AUDIT.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def main() -> None:
    rows = read_audit()
    cell_counts: Counter[tuple[str, str]] = Counter()
    cell_families: dict[tuple[str, str], Counter[str]] = defaultdict(Counter)

    for row in rows:
        strategy = row.get("doe_strategy", "")
        pattern = row.get("pattern", "")
        family = row.get("family", "")
        if (
            row.get("strategy_confidence") == "high"
            and strategy in STRATEGY_ORDER
            and pattern in PATTERN_ORDER
            and family in FAMILY_ORDER
        ):
            cell = (strategy, pattern)
            cell_counts[cell] += 1
            cell_families[cell][family] += 1

    if not cell_counts:
        raise RuntimeError("No high-confidence DoE cells available for plotting.")

    # Empty taxonomy rows are omitted because the evidence audit does not
    # support a quantitative zero claim for the wider literature.
    active_strategies = [
        strategy
        for strategy in STRATEGY_ORDER
        if any(cell[0] == strategy for cell in cell_counts)
    ]
    x_pattern = {pattern: index for index, pattern in enumerate(PATTERN_ORDER)}
    y_strategy = {
        strategy: index for index, strategy in enumerate(active_strategies)
    }
    max_count = max(cell_counts.values())

    fig, ax = plt.subplots(figsize=(9.2, 5.7))
    for (strategy, pattern), count in cell_counts.items():
        family = cell_families[(strategy, pattern)].most_common(1)[0][0]
        ax.scatter(
            x_pattern[pattern],
            y_strategy[strategy],
            s=65 + 900 * count / max_count,
            color=FAMILY_COLORS[family],
            edgecolor="white",
            linewidth=0.9,
            alpha=0.84,
        )
        ax.text(
            x_pattern[pattern],
            y_strategy[strategy],
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
    ax.set_yticks(
        range(len(active_strategies)),
        [STRATEGY_LABELS[strategy] for strategy in active_strategies],
    )
    ax.set_xlabel("Integration pattern")
    ax.set_ylabel("DoE / training strategy")
    ax.grid(True, color="#DDDDDD")
    ax.set_axisbelow(True)

    used_families = {
        family
        for families in cell_families.values()
        for family in families
    }
    handles = [
        Line2D(
            [0],
            [0],
            marker="o",
            color="none",
            markerfacecolor=FAMILY_COLORS[family],
            markersize=7,
            label=family,
        )
        for family in FAMILY_ORDER
        if family in used_families
    ]
    ax.legend(
        handles=handles,
        title="Dominant surrogate model class",
        loc="lower center",
        bbox_to_anchor=(0.5, 1.02),
        ncol=3,
        borderaxespad=0,
        frameon=False,
        fontsize=7.2,
        title_fontsize=8,
    )
    fig.tight_layout()
    fig.savefig(
        FIG / "fig_doe_integration_bubble_evidence.png",
        dpi=300,
        bbox_inches="tight",
    )
    plt.close(fig)

    with OUT_COUNTS.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(
            [
                "doe_strategy",
                "integration_pattern",
                "dominant_model_class",
                "n",
            ]
        )
        for (strategy, pattern), count in sorted(cell_counts.items()):
            family = cell_families[(strategy, pattern)].most_common(1)[0][0]
            writer.writerow([strategy, pattern, family, count])

    print(
        f"plotted_studies={sum(cell_counts.values())} "
        f"cells={len(cell_counts)} "
        f"strategies={len(active_strategies)}"
    )


if __name__ == "__main__":
    main()
