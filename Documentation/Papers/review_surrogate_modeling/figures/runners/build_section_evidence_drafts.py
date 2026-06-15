"""Build section-specific model-taxonomy and validation evidence drafts.

Both figures use the shared long-format evidence table produced by
``paper_library/build_unified_evidence_audit.py``. The model-class figure keeps
trust mechanisms separate within each model-class/target cell. The validation
figure is a compact UpSet-style plot of exact multi-label combinations.
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
STUDIES = ROOT / "paper_library" / "unified_evidence_studies.csv"
OUT_COUNTS = CSV / "fig_section_evidence_drafts_counts.csv"
OUT_BUBBLE = FIG / "fig_model_class_target_trust_draft.png"
OUT_UPSET = FIG / "fig_validation_combinations_upset_draft.png"

FAMILY_ORDER = [
    "PCE / RSM",
    "GP / kriging",
    "RBF / kernel",
    "Tree ensembles",
    "Neural network",
]
TARGET_ORDER = [
    "Exogenous inputs",
    "Objective values",
    "Physical states or constraints",
    "Probability distributions / chance-constraint terms",
    "Decisions / solution-related objects",
]
TARGET_LABELS = {
    "Exogenous inputs": "Exogenous\ninputs",
    "Objective values": "Objective\nvalues",
    "Physical states or constraints": "Physical states\nor constraints",
    "Probability distributions / chance-constraint terms": (
        "Probability distributions /\nchance-constraint terms"
    ),
    "Decisions / solution-related objects": (
        "Decisions /\nsolution-related objects"
    ),
}
TRUST_ORDER = [
    "Predictive-error based",
    "Posterior uncertainty",
    "Physics-guided",
    "Structure-preserving / solver-compatible",
    "Decision-oriented",
    "Trust mechanism not explicitly identified",
]
TRUST_COLORS = {
    "Predictive-error based": "#4E79A7",
    "Posterior uncertainty": "#F28E2B",
    "Physics-guided": "#59A14F",
    "Structure-preserving / solver-compatible": "#B07AA1",
    "Decision-oriented": "#E15759",
    "Trust mechanism not explicitly identified": "#BDBDBD",
}
TRUST_OFFSETS = {
    "Predictive-error based": (-0.16, 0.14),
    "Posterior uncertainty": (0.16, 0.14),
    "Physics-guided": (-0.16, -0.01),
    "Structure-preserving / solver-compatible": (0.16, -0.01),
    "Decision-oriented": (-0.16, -0.16),
    "Trust mechanism not explicitly identified": (0.16, -0.16),
}

VALIDATION_ORDER = [
    "Point metrics",
    "Problem UQ",
    "Feasibility",
    "Interval calibration",
    "Decision-aware",
    "Stress test",
]


def read_csv(path: Path) -> list[dict[str, str]]:
    if not path.is_file():
        raise FileNotFoundError(
            f"Missing unified evidence table: {path}. Run the unified audit."
        )
    with path.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def split_labels(value: str) -> set[str]:
    return {part.strip() for part in (value or "").split(";") if part.strip()}


def build_model_counts(
    rows: list[dict[str, str]],
) -> tuple[Counter[tuple[str, str, str]], int]:
    counts: Counter[tuple[str, str, str]] = Counter()
    included = 0
    for row in rows:
        families = split_labels(row["family"])
        targets = split_labels(row["target"])
        trusts = split_labels(row["trust"])
        if not targets:
            continue
        if len(families) != 1:
            continue
        family = next(iter(families))
        if family not in FAMILY_ORDER:
            continue
        included += 1
        usable_trusts = [trust for trust in trusts if trust in TRUST_ORDER]
        if not usable_trusts:
            usable_trusts = ["Trust mechanism not explicitly identified"]
        for target in targets:
            for trust in usable_trusts:
                if target in TARGET_ORDER:
                    counts[(family, target, trust)] += 1
    if not counts:
        raise RuntimeError("No model-class/target records found.")
    return counts, included


def build_validation_counts(
    rows: list[dict[str, str]],
) -> tuple[Counter[tuple[str, ...]], int]:
    counts: Counter[tuple[str, ...]] = Counter()
    included = 0
    for row in rows:
        labels = split_labels(row["validation"])
        labels = {label for label in labels if label in VALIDATION_ORDER}
        if not labels:
            continue
        combination = tuple(
            label for label in VALIDATION_ORDER if label in labels
        )
        counts[combination] += 1
        included += 1
    if not counts:
        raise RuntimeError("No validation combinations found.")
    return counts, included


def render_bubble(
    counts: Counter[tuple[str, str, str]],
    included: int,
) -> None:
    x_pos = {label: index for index, label in enumerate(TARGET_ORDER)}
    y_pos = {label: index for index, label in enumerate(FAMILY_ORDER)}
    total_counts: Counter[tuple[str, str]] = Counter()
    trust_by_cell: dict[tuple[str, str], Counter[str]] = defaultdict(Counter)
    for (family, target, trust), count in counts.items():
        total_counts[(family, target)] += count
        trust_by_cell[(family, target)][trust] += count

    max_count = max(total_counts.values())
    base_fill = "#DCE6F2"
    base_edge = "#6B7C93"

    fig, ax = plt.subplots(figsize=(11.2, 6.2))
    for (family, target), total_count in total_counts.items():
        x = x_pos[target]
        y = y_pos[family]
        ax.scatter(
            x,
            y,
            s=380 + 2450 * total_count / max_count,
            color=base_fill,
            edgecolor=base_edge,
            linewidth=1.1,
            alpha=0.95,
            zorder=2,
        )
        ax.text(
            x,
            y,
            str(total_count),
            ha="center",
            va="center",
            fontsize=8,
            fontweight="bold",
            color="#1F1F1F",
            zorder=5,
        )

        trust_counts = trust_by_cell[(family, target)]
        missing_count = trust_counts.get("Trust mechanism not explicitly identified", 0)
        known_counts = {
            trust: count
            for trust, count in trust_counts.items()
            if trust != "Trust mechanism not explicitly identified"
        }

        if known_counts:
            dominant_trust, dominant_count = max(
                known_counts.items(), key=lambda item: (item[1], item[0])
            )
            ax.scatter(
                x + 0.18,
                y - 0.18,
                s=120 + 820 * dominant_count / max_count,
                color=TRUST_COLORS[dominant_trust],
                edgecolor="white",
                linewidth=0.9,
                alpha=0.95,
                zorder=4,
            )
            ax.text(
                x + 0.18,
                y - 0.18,
                str(dominant_count),
                ha="center",
                va="center",
                fontsize=6.2,
                fontweight="bold",
                color="white",
                zorder=5,
            )

        if missing_count:
            ax.scatter(
                x + 0.18,
                y + 0.18,
                s=120 + 820 * missing_count / max_count,
                color=TRUST_COLORS["Trust mechanism not explicitly identified"],
                edgecolor="white",
                linewidth=0.9,
                alpha=0.98,
                zorder=4,
            )
            ax.text(
                x + 0.18,
                y + 0.18,
                str(missing_count),
                ha="center",
                va="center",
                fontsize=6.2,
                fontweight="bold",
                color="#1F1F1F",
                zorder=5,
            )

    ax.set_xticks(
        range(len(TARGET_ORDER)),
        [TARGET_LABELS[label] for label in TARGET_ORDER],
    )
    ax.set_yticks(range(len(FAMILY_ORDER)), FAMILY_ORDER)
    ax.set_xlim(-0.55, len(TARGET_ORDER) - 0.45)
    ax.set_ylim(-0.55, len(FAMILY_ORDER) - 0.45)
    ax.invert_yaxis()
    ax.set_xlabel("Surrogate target")
    ax.set_ylabel("Surrogate model class")
    ax.grid(color="#DDDDDD", linewidth=0.8)
    ax.set_axisbelow(True)

    present = {trust for _, _, trust in counts}
    handles = [
        Line2D(
            [0],
            [0],
            marker="o",
            color="none",
            markerfacecolor=base_fill,
            markeredgecolor=base_edge,
            markersize=10,
            label="All studies",
        )
    ]
    handles.extend(
        [
            Line2D(
                [0],
                [0],
                marker="o",
                color="none",
                markerfacecolor=TRUST_COLORS[trust],
                markeredgecolor="white",
                markersize=8,
                label=trust,
            )
            for trust in TRUST_ORDER
            if trust in present
        ]
    )
    ax.legend(
        handles=handles,
        loc="lower center",
        bbox_to_anchor=(0.5, 1.02),
        ncol=3,
        frameon=False,
        fontsize=8,
        borderaxespad=0,
    )
    fig.tight_layout()
    fig.savefig(OUT_BUBBLE, dpi=300, bbox_inches="tight")
    plt.close(fig)


def render_upset(
    counts: Counter[tuple[str, ...]],
    included: int,
) -> None:
    combinations = sorted(
        counts,
        key=lambda combination: (
            -counts[combination],
            -len(combination),
            combination,
        ),
    )
    x = list(range(len(combinations)))
    values = [counts[combination] for combination in combinations]

    fig = plt.figure(figsize=(11.8, 6.8))
    grid = fig.add_gridspec(
        2,
        1,
        height_ratios=(2.2, 1.55),
        hspace=0.03,
    )
    ax_bar = fig.add_subplot(grid[0])
    ax_matrix = fig.add_subplot(grid[1], sharex=ax_bar)

    ax_bar.bar(x, values, color="#4E79A7", width=0.68)
    ax_bar.set_ylabel("Paper count")
    ax_bar.set_ylim(0, max(values) * 1.17)
    ax_bar.grid(axis="y", color="#DDDDDD")
    ax_bar.set_axisbelow(True)
    ax_bar.tick_params(axis="x", labelbottom=False, bottom=False)
    ax_bar.spines["right"].set_visible(False)
    ax_bar.spines["top"].set_visible(False)

    y_pos = {
        label: len(VALIDATION_ORDER) - index - 1
        for index, label in enumerate(VALIDATION_ORDER)
    }
    for row_index, label in enumerate(VALIDATION_ORDER):
        ypos = y_pos[label]
        if row_index % 2:
            ax_matrix.axhspan(
                ypos - 0.5,
                ypos + 0.5,
                color="#F3F3F3",
                zorder=0,
            )

    for xpos, combination in zip(x, combinations):
        ys = [y_pos[label] for label in combination]
        if len(ys) > 1:
            ax_matrix.plot(
                [xpos, xpos],
                [min(ys), max(ys)],
                color="#333333",
                linewidth=1.5,
                zorder=2,
            )
        for label in VALIDATION_ORDER:
            active = label in combination
            ax_matrix.scatter(
                xpos,
                y_pos[label],
                s=45 if active else 20,
                color="#333333" if active else "#D7D7D7",
                edgecolor="none",
                zorder=3,
            )

    ax_matrix.set_yticks(
        [y_pos[label] for label in VALIDATION_ORDER],
        VALIDATION_ORDER,
    )
    ax_matrix.set_xticks([])
    ax_matrix.set_xlim(-0.6, len(combinations) - 0.4)
    ax_matrix.set_ylim(-0.55, len(VALIDATION_ORDER) - 0.45)
    for spine in ("right", "top", "bottom"):
        ax_matrix.spines[spine].set_visible(False)
    ax_matrix.tick_params(axis="y", length=0)

    fig.tight_layout()
    fig.savefig(OUT_UPSET, dpi=300, bbox_inches="tight")
    plt.close(fig)


def write_counts(
    model_counts: Counter[tuple[str, str, str]],
    validation_counts: Counter[tuple[str, ...]],
) -> None:
    rows = []
    for (family, target, trust), count in sorted(model_counts.items()):
        rows.append(
            {
                "figure": "model_target_trust",
                "model_class": family,
                "target": target,
                "trust_or_combination": trust,
                "n": count,
            }
        )
    for combination, count in sorted(
        validation_counts.items(),
        key=lambda value: (-value[1], value[0]),
    ):
        rows.append(
            {
                "figure": "validation_upset",
                "model_class": "",
                "target": "",
                "trust_or_combination": " + ".join(combination),
                "n": count,
            }
        )
    with OUT_COUNTS.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    rows = read_csv(STUDIES)
    model_counts, model_n = build_model_counts(rows)
    validation_counts, validation_n = build_validation_counts(rows)
    write_counts(model_counts, validation_counts)
    render_bubble(model_counts, model_n)
    render_upset(validation_counts, validation_n)
    print(f"model_target_trust_studies={model_n}")
    print(f"validation_studies={validation_n}")
    print(f"validation_combinations={len(validation_counts)}")
    print(f"wrote {OUT_BUBBLE}")
    print(f"wrote {OUT_UPSET}")


if __name__ == "__main__":
    main()
