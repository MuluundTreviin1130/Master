"""Build draft heatmaps that profile integration patterns across three axes.

The x-axis is fixed to the integration patterns used in the manuscript. The
three panels then show how each pattern is associated with (i) surrogate model
classes, (ii) reported DoE/training designs, and (iii) reported validation
signals. This keeps the visual grammar consistent and uses only categories
already produced by the evidence-card pipeline.
"""

from __future__ import annotations

import csv
from collections import Counter
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np


ROOT = Path(__file__).resolve().parents[2]
FIG = ROOT / "figures"
CSV = FIG / "csv"
CARDS = ROOT / "paper_library" / "sec8_evidence_cards.csv"
OUT_COUNTS = CSV / "fig_integration_pattern_profile_heatmaps_draft_counts.csv"


PATTERN_ORDER = ["P1", "P2", "P4", "P5"]
PATTERN_LABELS = [
    "P1\nreplacement",
    "P2\nacceleration",
    "P4\ndecomposition",
    "P5\nuncertainty",
]

FAMILY_ORDER = [
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

VALIDATION_BUCKETS = [
    "Point metrics",
    "Feasibility",
    "Uncertainty",
    "Interval calibration",
    "Decision-aware",
    "Stress test",
    "--",
]


def read_cards() -> list[dict[str, str]]:
    with CARDS.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


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


def matrix_from_counts(
    counts: Counter[tuple[str, str]], row_order: list[str]
) -> np.ndarray:
    return np.array(
        [[counts.get((row, pattern), 0) for pattern in PATTERN_ORDER] for row in row_order],
        dtype=float,
    )


def annotate(ax: plt.Axes, data: np.ndarray) -> None:
    threshold = max(data.max() * 0.55, 1) if data.size else 1
    for y in range(data.shape[0]):
        for x in range(data.shape[1]):
            value = int(data[y, x])
            if value:
                color = "white" if value >= threshold else "#222222"
                ax.text(
                    x,
                    y,
                    str(value),
                    ha="center",
                    va="center",
                    color=color,
                    fontsize=8,
                    fontweight="bold",
                )


def plot_heatmap(
    ax: plt.Axes,
    data: np.ndarray,
    rows: list[str],
    title: str,
    cmap: str,
) -> None:
    image = ax.imshow(data, cmap=cmap, aspect="auto")
    annotate(ax, data)
    ax.set_xticks(range(len(PATTERN_ORDER)), PATTERN_LABELS)
    ax.set_yticks(range(len(rows)), rows)
    ax.set_title(title, loc="left", fontweight="bold")
    ax.set_xlabel("Integration pattern")
    ax.tick_params(axis="both", labelsize=8)
    ax.grid(False)
    return image


def main() -> None:
    cards = read_cards()
    family_counts: Counter[tuple[str, str]] = Counter()
    doe_counts: Counter[tuple[str, str]] = Counter()
    validation_counts: Counter[tuple[str, str]] = Counter()

    for row in cards:
        pattern = (row.get("pattern") or "").strip()
        if pattern not in PATTERN_ORDER:
            continue
        family = (row.get("family") or "--").strip() or "--"
        doe = (row.get("doe") or "--").strip() or "--"
        family_counts[(family, pattern)] += 1
        doe_counts[(doe, pattern)] += 1
        for tag in validation_tags(row.get("validation", "")):
            validation_counts[(tag, pattern)] += 1

    with OUT_COUNTS.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["panel", "category", "pattern", "n"])
        for (category, pattern), count in sorted(family_counts.items()):
            writer.writerow(["model_class", category, pattern, count])
        for (category, pattern), count in sorted(doe_counts.items()):
            writer.writerow(["doe", category, pattern, count])
        for (category, pattern), count in sorted(validation_counts.items()):
            writer.writerow(["validation", category, pattern, count])

    family_rows = [r for r in FAMILY_ORDER if any(family_counts.get((r, p), 0) for p in PATTERN_ORDER)]
    doe_rows = [r for r in DOE_ORDER if any(doe_counts.get((r, p), 0) for p in PATTERN_ORDER)]
    validation_rows = [
        r for r in VALIDATION_BUCKETS if any(validation_counts.get((r, p), 0) for p in PATTERN_ORDER)
    ]

    family_matrix = matrix_from_counts(family_counts, family_rows)
    doe_matrix = matrix_from_counts(doe_counts, doe_rows)
    validation_matrix = matrix_from_counts(validation_counts, validation_rows)

    fig, axes = plt.subplots(
        1,
        3,
        figsize=(15.5, 6.2),
        gridspec_kw={"width_ratios": [1.15, 1.05, 1.05]},
    )
    images = [
        plot_heatmap(axes[0], family_matrix, family_rows, "A. Model class by pattern", "YlGnBu"),
        plot_heatmap(axes[1], doe_matrix, doe_rows, "B. Training / DoE by pattern", "YlOrBr"),
        plot_heatmap(axes[2], validation_matrix, validation_rows, "C. Validation signal by pattern", "PuBuGn"),
    ]
    for ax, image in zip(axes, images):
        fig.colorbar(image, ax=ax, fraction=0.046, pad=0.02, label="paper count")

    fig.suptitle(
        "Draft integration-pattern profiles across model class, training design and validation",
        fontsize=14,
        fontweight="bold",
        y=0.985,
    )
    fig.text(
        0.01,
        0.01,
        (
            f"Source: PDF-backed Section-8 evidence cards, n={len(cards)}. "
            "Validation counts are multi-label when a study reports more than one validation signal."
        ),
        fontsize=8,
        color="#555555",
    )
    fig.tight_layout(rect=(0, 0.04, 1, 0.93), w_pad=2.0)
    for ext in ("png",):
        fig.savefig(FIG / f"fig_integration_pattern_profile_heatmaps_draft.{ext}", dpi=300, bbox_inches="tight")
    plt.close(fig)


if __name__ == "__main__":
    main()
