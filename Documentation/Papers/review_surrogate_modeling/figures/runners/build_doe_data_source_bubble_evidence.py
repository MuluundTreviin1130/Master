"""Build the evidence-based DoE by workflow-context heatmap."""

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
STUDIES = ROOT / "paper_library" / "unified_evidence_studies.csv"
OUT_FIG = FIG / "fig_doe_workflow_bubble_evidence.png"
OUT_COUNTS = CSV / "fig_doe_workflow_bubble_evidence_counts.csv"

DOE_LABELS = {
    "Latin hypercube sampling": "Latin hypercube\nsampling",
    "Quasi-Monte Carlo / sparse-grid collocation": (
        "Quasi-Monte Carlo /\nsparse-grid collocation"
    ),
    "Factorial / response-surface design": (
        "Factorial /\nresponse-surface design"
    ),
    "Adaptive sampling": "Adaptive\nsampling",
    "Active learning": "Active\nlearning",
    "Multi-fidelity training": "Multi-fidelity\ntraining",
    "Transfer learning": "Transfer\nlearning",
}
DOE_SECTION_GROUPS = [
    (
        "Static designs",
        [
            "Factorial / response-surface design",
            "Latin hypercube sampling",
            "Quasi-Monte Carlo / sparse-grid collocation",
        ],
    ),
    (
        "Adaptive sampling and active learning",
        [
            "Adaptive sampling",
            "Active learning",
        ],
    ),
    (
        "Multi-fidelity and transfer learning",
        [
            "Multi-fidelity training",
            "Transfer learning",
        ],
    ),
]
WORKFLOW_LABELS = {
    "Simulation-driven workflow": "Simulation-driven",
    "Historical-data-driven workflow": "Historical-data-driven",
    "Hybrid model-coupled workflow": "Hybrid",
    "Not explicitly identified": "Not explicitly\nidentified",
}


def read_rows() -> list[dict[str, str]]:
    with STUDIES.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def split_labels(value: str) -> list[str]:
    return [part.strip() for part in (value or "").split(";") if part.strip()]


def main() -> None:
    rows = read_rows()
    counts: Counter[tuple[str, str]] = Counter()
    included_studies = 0

    for row in rows:
        doe_labels = split_labels(row.get("doe_strategy", ""))
        if not doe_labels:
            continue
        included_studies += 1
        workflow = (row.get("workflow_context") or "").strip() or "Not explicitly identified"
        for doe in doe_labels:
            counts[(doe, workflow)] += 1

    doe_totals = Counter(doe for doe, _ in counts)
    doe_order: list[str] = []
    grouped_labels: set[str] = set()
    for _, group_members in DOE_SECTION_GROUPS:
        present = [member for member in group_members if member in doe_totals]
        present.sort(key=lambda label: (-doe_totals[label], label))
        doe_order.extend(present)
        grouped_labels.update(present)
    doe_order.extend(
        label
        for label, _ in sorted(
            ((label, total) for label, total in doe_totals.items() if label not in grouped_labels),
            key=lambda item: (-item[1], item[0]),
        )
    )
    workflow_order = [
        label
        for label, _ in sorted(
            Counter(workflow for _, workflow in counts).items(),
            key=lambda item: (-item[1], item[0]),
        )
    ]

    matrix = np.zeros((len(workflow_order), len(doe_order)), dtype=int)
    for yi, workflow in enumerate(workflow_order):
        for xi, doe in enumerate(doe_order):
            matrix[yi, xi] = counts.get((doe, workflow), 0)

    fig, ax = plt.subplots(figsize=(13.6, 5.8))
    im = ax.imshow(matrix, cmap="Blues", aspect="auto", vmin=0)

    for yi in range(matrix.shape[0]):
        for xi in range(matrix.shape[1]):
            value = int(matrix[yi, xi])
            ax.text(
                xi,
                yi,
                "" if value == 0 else str(value),
                ha="center",
                va="center",
                fontsize=8,
                fontweight="bold",
                color="white" if value >= max(4, matrix.max() * 0.45) else "#1F1F1F",
            )

    ax.set_xticks(
        range(len(doe_order)),
        [DOE_LABELS.get(label, label) for label in doe_order],
    )
    ax.set_yticks(
        range(len(workflow_order)),
        [WORKFLOW_LABELS.get(label, label) for label in workflow_order],
    )
    ax.set_xlabel("DoE / training strategy")
    ax.set_ylabel("Data-source subsection")
    ax.tick_params(axis="x", labelsize=8)
    ax.tick_params(axis="y", labelsize=9)
    ax.set_xticks(np.arange(-0.5, len(doe_order), 1), minor=True)
    ax.set_yticks(np.arange(-0.5, len(workflow_order), 1), minor=True)
    ax.grid(which="minor", color="white", linestyle="-", linewidth=1.2)
    ax.tick_params(which="minor", bottom=False, left=False)

    x_lookup = {label: idx for idx, label in enumerate(doe_order)}
    trans = ax.get_xaxis_transform()
    for group_label, group_members in DOE_SECTION_GROUPS:
        members = [member for member in group_members if member in x_lookup]
        if not members:
            continue
        xmin = min(x_lookup[member] for member in members) - 0.5
        xmax = max(x_lookup[member] for member in members) + 0.5
        ax.plot(
            [xmin, xmax],
            [-0.10, -0.10],
            color="#6B6B6B",
            linewidth=1.2,
            transform=trans,
            clip_on=False,
        )
        ax.text(
            (xmin + xmax) / 2,
            -0.17,
            group_label,
            ha="center",
            va="top",
            fontsize=8,
            fontweight="bold",
            transform=trans,
            clip_on=False,
        )
    cbar = fig.colorbar(im, ax=ax, shrink=0.92, pad=0.02)
    cbar.set_label("Paper count")

    fig.tight_layout()
    fig.subplots_adjust(bottom=0.38)
    fig.savefig(OUT_FIG, dpi=300, bbox_inches="tight")
    plt.close(fig)

    with OUT_COUNTS.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["doe_strategy", "workflow_context", "n"])
        for workflow in workflow_order:
            for doe in doe_order:
                writer.writerow([doe, workflow, counts.get((doe, workflow), 0)])

    print(f"study_cohort={included_studies}")
    print(f"plotted_cells={len(counts)}")
    print(f"wrote {OUT_FIG}")


if __name__ == "__main__":
    main()
