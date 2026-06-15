"""Extract Panel D from the four-panel taxonomy draft as a standalone figure.

The source table is the generated count table from
``build_four_panel_final_candidate_draft.py``.  This runner keeps the plotted
quantity auditable by reading only the explicit ``D_app`` rows and failing if
the expected count schema or data are missing.
"""

from __future__ import annotations

import csv
from collections import Counter
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt


ROOT = Path(__file__).resolve().parents[2]
FIG = ROOT / "figures"
CSV = FIG / "csv"

IN_COUNTS = CSV / "fig_four_panel_final_candidate_draft_counts.csv"
OUT_FIG = FIG / "fig_panel_d_application_targets_sorted.png"

REQUIRED_COLUMNS = {"panel", "x", "y", "signal", "n"}

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


def read_panel_d_counts(path: Path) -> Counter[tuple[str, str]]:
    """Read audited Panel-D count rows as ``(model_class, application)`` counts."""
    if not path.is_file():
        raise FileNotFoundError(f"Required count table not found: {path}")

    counts: Counter[tuple[str, str]] = Counter()
    with path.open(encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        columns = set(reader.fieldnames or [])
        missing = REQUIRED_COLUMNS - columns
        if missing:
            raise ValueError(f"{path} is missing required columns: {sorted(missing)}")

        for row_number, row in enumerate(reader, start=2):
            if row["panel"] != "D_app":
                continue
            application = row["x"].strip()
            model_class = row["y"].strip()
            if not application or not model_class:
                raise ValueError(f"Empty Panel-D label in {path} row {row_number}")
            if application not in APPLICATION_COLORS:
                raise ValueError(f"Missing color for application target {application!r}")
            counts[(model_class, application)] += int(row["n"])

    if not counts:
        raise ValueError(f"No D_app rows found in {path}")
    return counts


def main() -> None:
    counts = read_panel_d_counts(IN_COUNTS)

    # Sort the visible bars by total tagged paper count, largest first.
    model_totals = Counter()
    application_totals = Counter()
    for (model_class, application), count in counts.items():
        model_totals[model_class] += count
        application_totals[application] += count

    model_order = [model_class for model_class, _ in model_totals.most_common()]
    application_order = [application for application, _ in application_totals.most_common()]

    fig, ax = plt.subplots(figsize=(10.6, 5.9))
    ypos = list(range(len(model_order)))
    left = [0] * len(model_order)

    for application in application_order:
        values = [counts.get((model_class, application), 0) for model_class in model_order]
        ax.barh(
            ypos,
            values,
            left=left,
            color=APPLICATION_COLORS[application],
            label=application,
            height=0.68,
        )
        left = [previous + value for previous, value in zip(left, values)]

    ax.set_yticks(ypos, model_order)
    ax.invert_yaxis()
    ax.grid(axis="x", color="#DDDDDD")
    ax.set_axisbelow(True)
    ax.set_xlabel("Paper count")
    ax.set_ylabel("Surrogate model class")

    ax.legend(
        loc="center left",
        bbox_to_anchor=(1.02, 0.5),
        frameon=False,
        fontsize=9,
    )
    fig.tight_layout(rect=(0, 0, 0.78, 1.0))
    fig.savefig(OUT_FIG, dpi=300, bbox_inches="tight")
    plt.close(fig)


if __name__ == "__main__":
    main()
