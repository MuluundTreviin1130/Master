"""Build a standalone keyword-frequency word cloud for bibliometric analysis.

The figure deliberately uses only the BibTeX ``author_keywords`` and
``keywords`` fields from the curated paper library.  Spatial placement is
deterministic and carries no co-occurrence meaning; frequency is encoded by font
size, and color follows explicit keyword families.
"""

from __future__ import annotations

import csv
import math
import random
import re
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from PIL import Image


ROOT = Path(__file__).resolve().parents[2]
PAPER_LIBRARY = ROOT / "paper_library"
FIG = ROOT / "figures"
CSV = FIG / "csv"

IN_BIB = PAPER_LIBRARY / "review_paper_library.bib"
OUT_FIG = FIG / "fig_bibliometric_keyword_wordcloud.png"
OUT_TERMS = CSV / "fig_bibliometric_keyword_wordcloud_terms.csv"
OUT_UNCLASSIFIED = CSV / "fig_bibliometric_keyword_wordcloud_unclassified_terms.csv"

CLUSTER_COLORS = {
    "Energy-system context": "#2C7FB8",
    "Optimization and decision methods": "#41AB5D",
    "Surrogate and AI methods": "#756BB1",
    "Energy technologies": "#E6AB02",
    "Performance objectives": "#E34A33",
}

CLUSTER_RULES = {
    "Energy-system context": [
        "multi-energy",
        "multi energy",
        "energy system",
        "integrated energy",
        "sector coupling",
        "energy hub",
        "virtual power plant",
        "microgrid",
        "micro-grid",
        "energy community",
        "hybrid renewable",
        "district heating",
        "smart grid",
        "distributed generation",
        "energy management",
        "power system",
        "electric power",
        "building",
        "buildings",
        "cchp",
        "polygeneration",
        "trigeneration",
    ],
    "Optimization and decision methods": [
        "optimization",
        "optimisation",
        "multi-objective",
        "multiobjective",
        "pareto",
        "non-dominated",
        "nondominated",
        "nsga",
        "mopso",
        "particle swarm",
        "genetic algorithm",
        "differential evolution",
        "evolutionary",
        "moea",
        "bayesian optimization",
        "integer programming",
        "linear programming",
        "learning to optimize",
        "load dispatching",
        "dispatch",
        "model predictive control",
        "decision",
        "decision making",
        "decision-making",
        "mcdm",
        "topsis",
        "ahp",
        "vikor",
        "scheduling",
        "planning",
        "optimal",
    ],
    "Surrogate and AI methods": [
        "surrogate",
        "metamodel",
        "meta-model",
        "response surface",
        "kriging",
        "gaussian process",
        "random forest",
        "xgboost",
        "forecasting",
        "forecasting method",
        "load forecasting",
        "probabilistic forecasting",
        "weather forecasting",
        "neural network",
        "neural networks",
        "artificial neural",
        "machine learning",
        "deep learning",
        "artificial intelligence",
        "data-driven",
        "data driven",
        "multi-fidelity",
        "multifidelity",
        "digital twin",
        "regression",
        "reinforcement learning",
        "polynomial chaos",
        "support vector",
    ],
    "Energy technologies": [
        "renewable",
        "solar",
        "photovoltaic",
        "pv",
        "wind",
        "battery",
        "storage",
        "hydrogen",
        "electroly",
        "heat pump",
        "electric vehicle",
        "ev ",
        "thermal",
        "chp",
        "combined heat",
        "power-to-x",
        "power to x",
        "biomass",
        "fuel cell",
        "alternative energy",
        "energy conversion",
    ],
    "Performance objectives": [
        "cost",
        "economic",
        "emission",
        "co2",
        "carbon",
        "reliability",
        "resilience",
        "self-sufficiency",
        "autarky",
        "flexibility",
        "efficiency",
        "life cycle",
        "lca",
        "sustainability",
        "sustainable",
        "environmental",
        "uncertainty",
        "sensitivity analysis",
        "robust",
        "risk",
    ],
}

PHRASE_ALIASES = {
    "ann": "neural network",
    "artificial neural network": "neural network",
    "artificial neural networks": "neural network",
    "bayesian optimizations": "bayesian optimization",
    "bess": "battery storage",
    "battery energy storage": "battery storage",
    "battery energy storage systems": "battery storage",
    "co2 emissions": "emissions",
    "co2 emission": "emissions",
    "carbon emissions": "emissions",
    "data driven": "data-driven",
    "data driven approaches": "data-driven",
    "data driven methods": "data-driven",
    "energy storage": "battery storage",
    "gaussian process regression": "Gaussian process",
    "gaussian processes": "Gaussian process",
    "global optimizations": "global optimization",
    "genetic algorithms": "genetic algorithm",
    "hres": "hybrid renewable system",
    "hybrid renewable energy system": "hybrid renewable system",
    "hybrid renewable energy systems": "hybrid renewable system",
    "multi objective optimization": "multi-objective optimization",
    "multi objective optimisation": "multi-objective optimization",
    "multi-objective optimisation": "multi-objective optimization",
    "multiobjective optimization": "multi-objective optimization",
    "multiobjective optimisation": "multi-objective optimization",
    "multi objectives optimization": "multi-objective optimization",
    "neural networks": "neural network",
    "optimisation": "optimization",
    "optimisations": "optimization",
    "multi-criteria decision making": "decision making",
    "multi-criteria decision-making": "decision making",
    "multi-criteria decision analysis": "decision making",
    "multi criteria decision making": "decision making",
    "mcdm": "decision making",
    "particle swarm optimisation": "particle swarm optimization",
    "particle swarm optimization": "particle swarm optimization",
    "photovoltaic": "photovoltaics",
    "photovoltaic systems": "photovoltaics",
    "pv system": "photovoltaics",
    "renewable energies": "renewable energy",
    "renewable energy source": "renewable energy",
    "renewable energy resources": "renewable energy",
    "renewable energy sources": "renewable energy",
    "surrogate modeling": "surrogate model",
    "surrogate modelling": "surrogate model",
    "surrogate models": "surrogate model",
}

STOP_PHRASES = {
    "",
    "article",
    "case study",
    "energy",
    "model",
    "models",
    "review",
    "simulation",
    "system",
    "systems",
}


@dataclass(frozen=True)
class Term:
    label: str
    cluster: str
    frequency: int


def clean_text(text: str) -> str:
    return re.sub(r"\s+", " ", text or "").strip()


def parse_bib_keyword_fields(path: Path) -> list[list[str]]:
    """Extract only keyword-bearing fields from the curated library BibTeX."""
    if not path.is_file():
        raise FileNotFoundError(f"Required bibliography not found: {path}")

    text = path.read_text(encoding="utf-8", errors="replace")
    starts = [match.start() for match in re.finditer(r"@\w+\s*\{", text)]
    starts.append(len(text))
    keyword_records: list[list[str]] = []

    for start, next_start in zip(starts[:-1], starts[1:]):
        block = text[start:next_start]
        fields: list[str] = []
        for field in ("author_keywords", "keywords"):
            match = re.search(
                rf"\b{field}\s*=\s*\{{(.*?)\}}\s*,?",
                block,
                flags=re.IGNORECASE | re.DOTALL,
            )
            if match:
                fields.extend(split_keywords(clean_text(match.group(1))))
        if fields:
            keyword_records.append(fields)

    if not keyword_records:
        raise ValueError(f"No keyword fields found in {path}")
    return keyword_records


def split_keywords(raw: str) -> list[str]:
    """Split Scopus/BibTeX keyword fields without using abstract text."""
    normalized = raw.replace("\\&", "&").replace("{", "").replace("}", "")
    parts = re.split(r"\s*;\s*|\s*\|\s*", normalized)
    return [part.strip() for part in parts if part.strip()]


def canonicalize_phrase(raw: str) -> str:
    """Normalize keyword variants while preserving publication-readable labels."""
    text = raw.lower()
    text = text.replace("-", " ")
    text = re.sub(r"[^a-z0-9+/& ]+", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    text = PHRASE_ALIASES.get(text, text)
    if text.endswith(" systems") and text[:-1] in PHRASE_ALIASES:
        text = PHRASE_ALIASES[text[:-1]]
    if text in STOP_PHRASES:
        return ""
    return text


def display_label(term: str) -> str:
    """Restore common abbreviations and title conventions for plotted labels."""
    replacements = {
        "ahp": "AHP",
        "cchp": "CCHP",
        "chp": "CHP",
        "co2": "CO2",
        "gaussian process": "Gaussian process",
        "mcdm": "MCDM",
        "moea/d": "MOEA/D",
        "mopso": "MOPSO",
        "nsga ii": "NSGA-II",
        "nsga ii / iii": "NSGA-II / III",
        "topsis": "TOPSIS",
        "xgboost": "XGBoost",
    }
    if term in replacements:
        return replacements[term]
    return term


def classify_term(term: str) -> str | None:
    """Assign a keyword to exactly one explicit visual color family."""
    matches = []
    for cluster, needles in CLUSTER_RULES.items():
        if any(needle in term for needle in needles):
            matches.append(cluster)
    if not matches:
        return None
    # If terms touch several families, prioritize method/context labels over
    # generic objective words so color remains stable and interpretable.
    priority = [
        "Surrogate and AI methods",
        "Optimization and decision methods",
        "Energy technologies",
        "Energy-system context",
        "Performance objectives",
    ]
    for cluster in priority:
        if cluster in matches:
            return cluster
    return matches[0]


def build_terms(path: Path) -> list[Term]:
    """Count controlled keyword hits per record using only keyword fields."""
    frequency: Counter[str] = Counter()
    cluster_for: dict[str, str] = {}
    unclassified: Counter[str] = Counter()

    for record_keywords in parse_bib_keyword_fields(path):
        unique_terms = {canonicalize_phrase(keyword) for keyword in record_keywords}
        unique_terms.discard("")
        for term in unique_terms:
            cluster = classify_term(term)
            if cluster is None:
                unclassified[term] += 1
                continue
            frequency[term] += 1
            cluster_for[term] = cluster

    terms = [
        Term(label=display_label(term), cluster=cluster_for[term], frequency=count)
        for term, count in frequency.items()
        if count >= 1
    ]
    write_unclassified_table(OUT_UNCLASSIFIED, unclassified)

    if not terms:
        raise ValueError(f"No controlled keyword terms found in {path}")
    return sorted(terms, key=lambda item: item.frequency, reverse=True)


def write_term_table(path: Path, terms: list[Term]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["term", "cluster", "frequency"])
        writer.writeheader()
        for term in terms:
            writer.writerow({"term": term.label, "cluster": term.cluster, "frequency": term.frequency})


def write_unclassified_table(path: Path, terms: Counter[str]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["term", "frequency"])
        writer.writeheader()
        for term, count in terms.most_common():
            writer.writerow({"term": display_label(term), "frequency": count})


FIGSIZE = (7.6, 7.6)


def font_size(term: Term, max_frequency: int) -> float:
    """Compress the large frequency range into readable word-cloud sizes."""
    scaled = math.sqrt(term.frequency / max_frequency)
    return 3.9 + 30.0 * scaled


def candidate_positions(rng: random.Random, preferred_y: float) -> list[tuple[float, float]]:
    """Generate positions along square shells instead of circular rings."""
    positions = [(0.5, preferred_y), (0.30, preferred_y), (0.70, preferred_y), (0.5, 0.24), (0.5, 0.80)]
    center_x = 0.5
    center_y = 0.52
    shell_radii = [0.06, 0.12, 0.18, 0.24, 0.30, 0.36, 0.42, 0.46]
    edge_steps = [3, 5, 7, 9, 11, 13, 15, 17]
    for radius, steps in zip(shell_radii, edge_steps):
        coords = []
        for idx in range(steps):
            t = idx / (steps - 1)
            offset = -radius + 2.0 * radius * t
            coords.extend(
                [
                    (center_x + offset, center_y - radius),
                    (center_x + radius, center_y + offset),
                    (center_x - offset, center_y + radius),
                    (center_x - radius, center_y - offset),
                ]
            )
        rng.shuffle(coords)
        coords.sort(key=lambda item: abs(item[1] - preferred_y))
        for x, y in coords:
            jitter_x = rng.uniform(-0.010, 0.010)
            jitter_y = rng.uniform(-0.010, 0.010)
            px = min(0.94, max(0.06, x + jitter_x))
            py = min(0.93, max(0.10, y + jitter_y))
            positions.append((px, py))
    return positions


def estimated_box(label: str, size: float, x: float, y: float) -> tuple[float, float, float, float]:
    """Estimate a text box in axes coordinates before drawing the label."""
    width = len(label) * size * 0.58 / 72.0 / FIGSIZE[0]
    height = size * 1.16 / 72.0 / FIGSIZE[1]
    return (x - width / 2, y - height / 2, x + width / 2, y + height / 2)


def overlaps(candidate: tuple[float, float, float, float], placed: list[tuple[float, float, float, float]]) -> bool:
    """Check conservative axes-coordinate rectangle overlap."""
    x0, y0, x1, y1 = candidate
    if x0 < 0.035 or y0 < 0.085 or x1 > 0.965 or y1 > 0.955:
        return True
    pad_x = 0.004
    pad_y = 0.006
    for ox0, oy0, ox1, oy1 in placed:
        if not (x1 + pad_x < ox0 or ox1 + pad_x < x0 or y1 + pad_y < oy0 or oy1 + pad_y < y0):
            return True
    return False


def main() -> None:
    terms = build_terms(IN_BIB)
    write_term_table(OUT_TERMS, terms)
    max_frequency = max(term.frequency for term in terms)
    rng = random.Random(20260608)

    fig, ax = plt.subplots(figsize=FIGSIZE)
    fig.subplots_adjust(left=0.035, right=0.965, top=0.965, bottom=0.185)
    ax.set_axis_off()
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)

    placed_boxes: list[tuple[float, float, float, float]] = []
    preferred_rows = [0.52, 0.38, 0.66, 0.24, 0.80, 0.14, 0.90]
    for index, term in enumerate(terms[:320]):
        size = font_size(term, max_frequency)
        color = CLUSTER_COLORS[term.cluster]
        box = None
        x = y = 0.5
        # If a lower-ranked long phrase cannot fit at its initial size, shrink
        # it slightly instead of hiding the term or changing the frequency data.
        for scale in [1.0, 0.94, 0.88, 0.82, 0.76, 0.70, 0.64, 0.58, 0.52, 0.46]:
            candidate_size = size * scale
            for x, y in candidate_positions(rng, preferred_rows[index % len(preferred_rows)]):
                candidate = estimated_box(term.label, candidate_size, x, y)
                if not overlaps(candidate, placed_boxes):
                    box = candidate
                    size = candidate_size
                    break
            if box is not None:
                break
        if box is None:
            continue
        placed_boxes.append(box)
        ax.text(
            x,
            y,
            term.label,
            transform=ax.transAxes,
            ha="center",
            va="center",
            fontsize=size,
            color=color,
            alpha=0.90,
            fontweight="bold" if term.frequency >= 300 else "normal",
        )

    legend_handles = [
        plt.Line2D([0], [0], marker="o", color="w", markerfacecolor=color, markersize=10, label=cluster)
        for cluster, color in CLUSTER_COLORS.items()
    ]
    fig.legend(
        handles=legend_handles,
        loc="lower center",
        bbox_to_anchor=(0.5, 0.03),
        ncol=2,
        frameon=False,
        fontsize=11.0,
        handletextpad=0.6,
        columnspacing=1.8,
        borderaxespad=0.0,
    )

    fig.savefig(OUT_FIG, dpi=300)
    plt.close(fig)
    enforce_square_canvas(OUT_FIG)


def enforce_square_canvas(path: Path) -> None:
    """Pad the saved PNG to an exact square canvas without distorting labels."""
    with Image.open(path) as image:
        width, height = image.size
        if width == height:
            return
        side = max(width, height)
        square = Image.new("RGBA", (side, side), (255, 255, 255, 255))
        offset = ((side - width) // 2, (side - height) // 2)
        square.paste(image, offset)
        square.save(path)


if __name__ == "__main__":
    main()
