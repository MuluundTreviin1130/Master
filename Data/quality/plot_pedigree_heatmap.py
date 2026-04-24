from __future__ import annotations

import argparse
import csv
from pathlib import Path
import sys
from typing import Dict, List

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.colors import ListedColormap

PEDIGREE_COLUMNS = [
    ("reliability", "Rel"),
    ("completeness", "Comp"),
    ("technological_representativeness", "TechR"),
    ("geographical_representativeness", "GeoR"),
    ("temporal_representativeness", "TempR"),
]

DISPLAY_LABELS = {
    "fuel_cell_PEM": "Fuel cell",
}


def _project_root() -> Path:
    here = Path(__file__).resolve()
    for p in [here.parent, *here.parents]:
        if (p / "Data").exists():
            return p
    return here.parents[2]


ROOT = _project_root()
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from Data.LCA_data.pedigree.dqr import compute_dqr_from_scores, extract_scores
from Data.LCA_data.pedigree.load_pedigree import load_all_records


def _class_label(dqr: float | None) -> str:
    if dqr is None:
        return "pending"
    if dqr < 1.6:
        return "high_quality"
    if dqr > 3.0:
        return "data_estimate"
    return "medium_quality"


def _sort_key(item: tuple[str, Dict]) -> tuple[int, float, str]:
    tech, record = item
    status = str(record.get("assessment_status", ""))
    if status == "scored":
        scores = extract_scores(record)
        dqr = compute_dqr_from_scores(scores)
        return (0, dqr, tech.lower())
    return (1, 999.0, tech.lower())


def build_rows(country: str) -> List[Dict]:
    records = load_all_records(country)
    rows: List[Dict] = []
    for tech, record in sorted(records.items(), key=_sort_key):
        status = str(record.get("assessment_status", ""))
        row: Dict[str, object] = {
            "technology": tech,
            "assessment_status": status,
        }
        if status == "scored":
            scores = extract_scores(record)
            dqr = compute_dqr_from_scores(scores)
            for key, _ in PEDIGREE_COLUMNS:
                row[key] = scores[key]
            row["dqr"] = dqr
            row["dqr_class"] = _class_label(dqr)
        else:
            for key, _ in PEDIGREE_COLUMNS:
                row[key] = None
            row["dqr"] = None
            row["dqr_class"] = "pending"
        rows.append(row)
    return rows


def filter_rows(rows: List[Dict], technologies: List[str] | None) -> List[Dict]:
    if not technologies:
        return rows
    wanted = {str(tech).strip() for tech in technologies if str(tech).strip()}
    return [row for row in rows if str(row["technology"]) in wanted]


def write_summary_csv(rows: List[Dict], out_csv: Path) -> None:
    out_csv.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "technology",
        "assessment_status",
        "reliability",
        "completeness",
        "technological_representativeness",
        "geographical_representativeness",
        "temporal_representativeness",
        "dqr",
        "dqr_class",
    ]
    with out_csv.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def render_heatmap(rows: List[Dict], country: str, out_png: Path) -> None:
    out_png.parent.mkdir(parents=True, exist_ok=True)
    labels = [DISPLAY_LABELS.get(str(row["technology"]), str(row["technology"])) for row in rows]
    matrix = np.full((len(rows), len(PEDIGREE_COLUMNS)), np.nan, dtype=float)
    dqr_values: List[str] = []

    for i, row in enumerate(rows):
        for j, (key, _) in enumerate(PEDIGREE_COLUMNS):
            value = row[key]
            matrix[i, j] = np.nan if value is None else float(value)
        dqr = row["dqr"]
        dqr_values.append("-" if dqr is None else f"{float(dqr):.2f}")

    cmap = ListedColormap(
        [
            "#7FBC73",
            "#F4E67A",
            "#F0BE76",
            "#EA9C6B",
            "#E16D67",
        ]
    )
    cmap.set_bad(color="#E6E6E6")

    fig_h = max(3.2, 0.68 * len(rows) + 0.9)
    fig, ax = plt.subplots(figsize=(9.0, fig_h))
    im = ax.imshow(matrix, cmap=cmap, vmin=1, vmax=5, aspect="auto")

    ax.set_xticks(np.arange(len(PEDIGREE_COLUMNS) + 1))
    ax.set_xticklabels([label for _, label in PEDIGREE_COLUMNS] + ["DQR"], fontsize=11, fontweight="bold")
    ax.xaxis.tick_top()
    ax.set_yticks(np.arange(len(labels)))
    ax.set_yticklabels(labels, fontsize=11, fontweight="bold")

    for i, row in enumerate(rows):
        for j, (key, _) in enumerate(PEDIGREE_COLUMNS):
            value = row[key]
            ax.text(
                j,
                i,
                "-" if value is None else f"{int(value)}",
                ha="center",
                va="center",
                fontsize=11,
                fontweight="bold",
                color="black",
            )
        ax.text(
            len(PEDIGREE_COLUMNS),
            i,
            dqr_values[i],
            ha="center",
            va="center",
            fontsize=11,
            fontweight="bold",
            color="black",
        )

    ax.set_xlim(-0.5, len(PEDIGREE_COLUMNS) + 0.5)
    ax.set_ylim(len(labels) - 0.5, -0.5)

    for x in np.arange(-0.5, len(PEDIGREE_COLUMNS) + 1.5, 1.0):
        ax.axvline(x, color="#B8B8B8", linewidth=1.0)
    for y in np.arange(-0.5, len(labels) + 0.5, 1.0):
        ax.axhline(y, color="#B8B8B8", linewidth=1.0)

    cbar = fig.colorbar(im, ax=ax, fraction=0.03, pad=0.03, ticks=[1, 2, 3, 4, 5])
    cbar.ax.set_yticklabels(["1 best", "2", "3", "4", "5 worst"])
    cbar.ax.tick_params(labelsize=10)

    fig.tight_layout(pad=0.6)
    fig.savefig(out_png, dpi=220, bbox_inches="tight")
    plt.close(fig)


def main() -> None:
    parser = argparse.ArgumentParser(description="Render pedigree heatmap and CSV summary.")
    parser.add_argument("--country", default="AT")
    parser.add_argument("--outdir", default=None)
    parser.add_argument("--technologies", nargs="*", default=None)
    args = parser.parse_args()

    outdir = Path(args.outdir) if args.outdir else ROOT / "Analysis" / "data_quality" / "outputs" / args.country
    rows = filter_rows(build_rows(args.country), args.technologies)
    write_summary_csv(rows, outdir / f"pedigree_summary_{args.country}.csv")
    render_heatmap(rows, args.country, outdir / f"pedigree_heatmap_{args.country}.png")
    print(outdir)


if __name__ == "__main__":
    main()
