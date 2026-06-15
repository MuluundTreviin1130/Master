"""Build core review figures from the merged bibliography.

Figures produced:

- ``fig_01_prisma_workflow.png``
    schematic PRISMA-style workflow adapted to the two-pool literature
    process used in this review
- ``fig_03_mes_concept.png``
    conceptual multi-energy-system graphic
- ``fig_04_bibliometric_overview.png``
    bibliometric overview from the merged bibliography
- ``fig_06_keyword_landscape.png``
    VOSviewer-inspired keyword co-occurrence landscape from the merged
    bibliography

The script is intentionally self-contained and reads only the generated
reference-layer artefacts. It does not mutate bibliography files.
"""

from __future__ import annotations

import csv
import math
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Dict, Iterable, List, Tuple

import matplotlib.pyplot as plt
import networkx as nx
import numpy as np
import pandas as pd
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch


ROOT = Path(__file__).resolve().parents[2]
REF = ROOT / "references"
FIG = ROOT / "figures"
CSV = FIG / "csv"


# ---------------------------------------------------------------------------
# Small helpers
# ---------------------------------------------------------------------------


def read_csv(path: Path) -> List[Dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def save_figure(fig: plt.Figure, stem: str) -> None:
    for ext in ("png",):
        out = FIG / f"{stem}.{ext}"
        fig.savefig(out, dpi=300, bbox_inches="tight")
    plt.close(fig)


def box(ax, xy, width, height, text, fc="#F7FAFC", ec="#2D3748", fontsize=9):
    patch = FancyBboxPatch(
        xy,
        width,
        height,
        boxstyle="round,pad=0.018,rounding_size=0.025",
        facecolor=fc,
        edgecolor=ec,
        linewidth=1.2,
    )
    ax.add_patch(patch)
    ax.text(
        xy[0] + width / 2,
        xy[1] + height / 2,
        text,
        ha="center",
        va="center",
        fontsize=fontsize,
        wrap=True,
    )
    return patch


def arrow(ax, start, end, color="#4A5568", rad=0.0):
    ax.add_patch(
        FancyArrowPatch(
            start,
            end,
            arrowstyle="-|>",
            mutation_scale=12,
            linewidth=1.2,
            color=color,
            connectionstyle=f"arc3,rad={rad}",
        )
    )


def clean_text(text: str) -> str:
    return re.sub(r"\s+", " ", text or "").strip()


def parse_bib_fields(path: Path) -> List[Dict[str, str]]:
    """Extract a few fields from the generated BibTeX without dependencies.

    The BibTeX has already been normalized by ``build_review_bibliography``.
    For figure generation we only need title, abstract and keyword fields,
    so a simple field regex is sufficient.
    """

    text = path.read_text(encoding="utf-8", errors="replace")
    starts = [m.start() for m in re.finditer(r"@\w+\s*\{", text)]
    starts.append(len(text))
    rows: List[Dict[str, str]] = []

    for start, next_start in zip(starts[:-1], starts[1:]):
        block = text[start:next_start]
        key_match = re.match(r"@\w+\s*\{\s*([^,]+),", block)
        if not key_match:
            continue
        row = {"cite_key": key_match.group(1).strip()}
        for field in ("title", "abstract", "author_keywords", "keywords", "journal", "journaltitle", "year"):
            match = re.search(
                rf"\b{field}\s*=\s*\{{(.*?)\}}\s*,?",
                block,
                flags=re.IGNORECASE | re.DOTALL,
            )
            row[field.lower()] = clean_text(match.group(1)) if match else ""
        rows.append(row)
    return rows


# ---------------------------------------------------------------------------
# Fig. 1: PRISMA-style workflow
# ---------------------------------------------------------------------------


def build_fig_01() -> None:
    sur = read_csv(REF / "surrogates_esm_screening.csv")
    moo = read_csv(REF / "moo_multicriteria_screening.csv")
    manifest = read_csv(REF / "review_mes_moo_surrogates_manifest.csv")

    tier_a = sum(1 for r in sur if r["tier"] == "A")
    tier_b = sum(1 for r in sur if r["tier"] == "B")
    sur_out = len(sur) - tier_a - tier_b
    moo_mes = sum(1 for r in moo if r["focus"] in {"moo_mes", "moo_mes_surrogate"})
    moo_sur = sum(1 for r in moo if r["focus"] == "moo_mes_surrogate")
    moo_excluded = len(moo) - moo_mes

    input_focus = tier_a + moo_mes
    final_n = len(manifest)
    collapsed = input_focus - final_n

    fig, ax = plt.subplots(figsize=(11.6, 7.2))
    ax.set_axis_off()
    ax.set_xlim(0, 1)
    ax.set_ylim(-0.03, 1)

    ax.text(
        0.5,
        0.96,
        "Literature identification and screening workflow",
        ha="center",
        va="top",
        fontsize=15,
        fontweight="bold",
    )
    ax.text(
        0.5,
        0.92,
        "Two complementary pools: surrogate-in-ESM methods + MOO/MES application literature",
        ha="center",
        va="top",
        fontsize=10,
        color="#4A5568",
    )

    # Identification layer
    box(ax, (0.07, 0.76), 0.36, 0.11, f"Broad surrogate-in-ESM Scopus export\nn = {len(sur)}", "#EBF8FF")
    box(ax, (0.57, 0.76), 0.36, 0.11, f"MOO / multicriteria MES export\nn = {len(moo)}", "#F0FFF4")

    # Screening layer
    box(ax, (0.07, 0.58), 0.36, 0.12, f"Offline surrogate screening\nTier A = {tier_a}\nTier B candidates = {tier_b}\nRejected/noise = {sur_out}", "#BEE3F8", fontsize=8.5)
    box(ax, (0.57, 0.58), 0.36, 0.12, f"MOO+MES focus screening\nMOO+MES = {moo_mes}\nSurrogate signal within MOO+MES = {moo_sur}\nOther MOO/non-focus = {moo_excluded}", "#C6F6D5", fontsize=8.5)

    # Eligibility / merge layer
    box(ax, (0.20, 0.38), 0.60, 0.11, f"Focus pools retained for review bibliography\nTier-A surrogate pool + MOO/MES focus pool\nn = {input_focus}", "#FEFCBF")
    box(ax, (0.20, 0.20), 0.60, 0.11, f"DOI-first and key-second deduplication\ncollapsed duplicate identities = {collapsed}", "#FAF089")
    box(ax, (0.20, 0.05), 0.60, 0.09, f"Final merged bibliography used by manuscript\nn = {final_n}", "#FED7D7")

    arrow(ax, (0.25, 0.76), (0.25, 0.70))
    arrow(ax, (0.75, 0.76), (0.75, 0.70))
    arrow(ax, (0.25, 0.58), (0.43, 0.49), rad=-0.10)
    arrow(ax, (0.75, 0.58), (0.57, 0.49), rad=0.10)
    arrow(ax, (0.50, 0.38), (0.50, 0.31))
    arrow(ax, (0.50, 0.20), (0.50, 0.14))

    ax.text(0.02, -0.01, "Note: Tier-B entries remain candidates for manual upgrading.", fontsize=8, color="#4A5568")
    save_figure(fig, "fig_01_prisma_workflow")


# ---------------------------------------------------------------------------
# Fig. 3: conceptual MES graphic
# ---------------------------------------------------------------------------


def build_fig_03() -> None:
    fig, ax = plt.subplots(figsize=(11.2, 7.0))
    ax.set_axis_off()
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)

    ax.text(0.5, 0.96, "Conceptual multi-energy system model", ha="center", va="top", fontsize=15, fontweight="bold")
    ax.text(
        0.5,
        0.92,
        "Surrogate-assisted MOO approximates expensive simulation or dispatch links while preserving Pareto-trade-off evaluation.",
        ha="center",
        va="top",
        fontsize=9.5,
        color="#4A5568",
    )

    colors = {
        "source": "#BEE3F8",
        "conversion": "#C6F6D5",
        "storage": "#FAF089",
        "demand": "#FED7D7",
        "optimizer": "#E9D8FD",
    }

    nodes = {
        "PV / wind\nrenewables": (0.08, 0.70, colors["source"]),
        "Grid import /\nexport": (0.08, 0.48, colors["source"]),
        "Biomass /\nwaste heat": (0.08, 0.26, colors["source"]),
        "Electricity bus": (0.34, 0.58, colors["conversion"]),
        "Heat / cooling bus": (0.34, 0.32, colors["conversion"]),
        "Power-to-X /\nhydrogen": (0.55, 0.70, colors["conversion"]),
        "Heat pump /\nCHP / boiler": (0.55, 0.45, colors["conversion"]),
        "BESS / EV\nstorage": (0.55, 0.20, colors["storage"]),
        "Buildings /\ncommunities": (0.80, 0.62, colors["demand"]),
        "Mobility /\nEV fleets": (0.80, 0.42, colors["demand"]),
        "Industry /\nservices": (0.80, 0.22, colors["demand"]),
        "MOO + surrogate\ncontroller": (0.38, 0.04, colors["optimizer"]),
    }

    drawn = {}
    for label, (x, y, fc) in nodes.items():
        drawn[label] = box(ax, (x, y), 0.16, 0.10, label, fc=fc, fontsize=9)

    def center(label, side="center"):
        x, y, _ = nodes[label]
        if side == "right":
            return (x + 0.16, y + 0.05)
        if side == "left":
            return (x, y + 0.05)
        if side == "top":
            return (x + 0.08, y + 0.10)
        if side == "bottom":
            return (x + 0.08, y)
        return (x + 0.08, y + 0.05)

    flows = [
        ("PV / wind\nrenewables", "Electricity bus"),
        ("Grid import /\nexport", "Electricity bus"),
        ("Biomass /\nwaste heat", "Heat / cooling bus"),
        ("Electricity bus", "Power-to-X /\nhydrogen"),
        ("Electricity bus", "Heat pump /\nCHP / boiler"),
        ("Electricity bus", "BESS / EV\nstorage"),
        ("Heat / cooling bus", "Heat pump /\nCHP / boiler"),
        ("Power-to-X /\nhydrogen", "Industry /\nservices"),
        ("Heat pump /\nCHP / boiler", "Buildings /\ncommunities"),
        ("BESS / EV\nstorage", "Mobility /\nEV fleets"),
        ("Electricity bus", "Buildings /\ncommunities"),
    ]
    for a, b in flows:
        arrow(ax, center(a, "right"), center(b, "left"), "#2B6CB0")

    # Optimizer feedback links
    for target in ("Electricity bus", "Heat / cooling bus", "Power-to-X /\nhydrogen", "BESS / EV\nstorage"):
        arrow(ax, center("MOO + surrogate\ncontroller", "top"), center(target, "bottom"), "#805AD5", rad=0.15)

    ax.text(0.05, 0.10, "Objectives: cost, CO$_2$, self-sufficiency,\npeak load, reliability, comfort", fontsize=9, color="#2D3748")
    ax.text(0.73, 0.10, "Surrogate targets: expensive dispatch,\nbuilding response, storage cycling,\nPareto-front evaluation", fontsize=9, color="#2D3748")

    save_figure(fig, "fig_03_mes_concept")


# ---------------------------------------------------------------------------
# Fig. 4: bibliometric overview
# ---------------------------------------------------------------------------


def build_fig_04() -> None:
    manifest = pd.read_csv(REF / "review_mes_moo_surrogates_manifest.csv")
    manifest["year"] = pd.to_numeric(manifest["year"], errors="coerce")
    manifest = manifest.dropna(subset=["year"])
    manifest["year"] = manifest["year"].astype(int)
    manifest = manifest[(manifest["year"] >= 2015) & (manifest["year"] <= 2026)]

    fig, axes = plt.subplots(2, 2, figsize=(13, 8.5))
    fig.suptitle("Bibliometric overview of the merged MOO/MES + surrogate literature base", fontsize=15, fontweight="bold")

    # a) Publications by year
    ax = axes[0, 0]
    year_counts = manifest["year"].value_counts().sort_index()
    years = list(range(2015, 2027))
    values = [int(year_counts.get(y, 0)) for y in years]
    ax.bar(years, values, color="#2B6CB0")
    ax.set_title("a) Publications by year")
    ax.set_ylabel("Records")
    ax.set_xticks(years)
    ax.tick_params(axis="x", rotation=45)
    ax.grid(axis="y", alpha=0.25)

    # b) Top venues
    ax = axes[0, 1]
    top_venues = manifest["venue"].fillna("(unknown)").replace("", "(unknown)").value_counts().head(12)
    ax.barh(top_venues.index[::-1], top_venues.values[::-1], color="#38A169")
    ax.set_title("b) Most frequent journals / venues")
    ax.set_xlabel("Records")
    ax.tick_params(axis="y", labelsize=8)
    ax.grid(axis="x", alpha=0.25)

    # c) Source composition
    ax = axes[1, 0]
    src = manifest["sources"].value_counts()
    labels = [s.replace("surrogate_esm_tier_a", "Surrogate search").replace("moo_mes_focus", "MOO/MES export").replace("+", " + ") for s in src.index]
    ax.pie(src.values, labels=labels, autopct=lambda p: f"{p:.1f}%", startangle=90, textprops={"fontsize": 8})
    ax.set_title("c) Source-pool composition after deduplication")

    # d) Publication outlet families
    ax = axes[1, 1]
    venue_lower = manifest["venue"].fillna("").str.lower()
    families = {
        "Elsevier energy journals": venue_lower.str.contains("applied energy|energy|energy conversion|renewable|journal of cleaner|energy and buildings|international journal of hydrogen", regex=True).sum(),
        "IEEE / IET / power systems": venue_lower.str.contains("ieee|iet|electric power|power systems|sustainable energy, grids", regex=True).sum(),
        "MDPI / Frontiers / OA": venue_lower.str.contains("sustainability|energies|electronics|frontiers|automation", regex=True).sum(),
        "Buildings / district energy": venue_lower.str.contains("building|district|thermal|applied thermal", regex=True).sum(),
        "Other venues": 0,
    }
    families["Other venues"] = len(manifest) - sum(families.values())
    fam_series = pd.Series(families).sort_values()
    ax.barh(fam_series.index, fam_series.values, color="#D69E2E")
    ax.set_title("d) Broad outlet families")
    ax.set_xlabel("Records")
    ax.grid(axis="x", alpha=0.25)
    ax.tick_params(axis="y", labelsize=8)

    fig.tight_layout(rect=[0, 0, 1, 0.96])
    save_figure(fig, "fig_04_bibliometric_overview")


# ---------------------------------------------------------------------------
# Fig. 6: VOSviewer-inspired keyword landscape
# ---------------------------------------------------------------------------


CONTROLLED_TERMS: Dict[str, Dict[str, List[str]]] = {
    "Multi-energy systems": {
        "multi-energy system": ["multi-energy system", "multi energy system"],
        "integrated energy system": ["integrated energy system", "integrated electricity-heat"],
        "sector coupling": ["sector coupling", "sector-coupling"],
        "energy hub": ["energy hub"],
        "virtual power plant": ["virtual power plant"],
        "microgrid": ["microgrid", "micro-grid", "micro grid"],
        "energy community": ["energy community", "energy communities"],
        "hybrid renewable system": ["hybrid renewable energy system", "hres"],
        "district heating": ["district heating", "district heating and cooling", "5gdhc"],
        "CCHP": ["cchp", "combined cooling, heating, and power", "combined cooling heating and power"],
    },
    "Optimization algorithms": {
        "multi-objective optimization": [
            "multi-objective optimization",
            "multiobjective optimization",
            "multi objective optimization",
            "many-objective optimization",
        ],
        "Pareto front": ["pareto", "non-dominated", "nondominated"],
        "NSGA-II / III": ["nsga-ii", "nsga ii", "nsga-iii", "nsga iii"],
        "MOPSO": ["mopso", "particle swarm"],
        "genetic algorithm": ["genetic algorithm"],
        "differential evolution": ["differential evolution"],
        "MOEA/D": ["moea/d", "moea"],
        "Bayesian optimization": ["bayesian optimization"],
        "hypervolume": ["hypervolume"],
    },
    "Surrogate / ML": {
        "surrogate model": ["surrogate model", "surrogate models", "surrogate modeling", "surrogate modelling"],
        "metamodel": ["metamodel", "meta-model", "meta model"],
        "response surface": ["response surface"],
        "kriging": ["kriging", "co-kriging"],
        "Gaussian process": ["gaussian process", "gp regression"],
        "random forest": ["random forest"],
        "XGBoost": ["xgboost", "extreme gradient boosting"],
        "neural network": ["neural network", "artificial neural network"],
        "machine learning": ["machine learning"],
        "deep learning": ["deep learning"],
        "multi-fidelity": ["multi-fidelity", "multifidelity"],
    },
    "Technologies": {
        "photovoltaics": ["photovoltaic", "pv system"],
        "wind power": ["wind power", "wind turbine"],
        "battery storage": ["battery", "bess"],
        "hydrogen": ["hydrogen", "electrolyzer", "electrolyser"],
        "heat pump": ["heat pump"],
        "electric vehicle": ["electric vehicle", "ev charging"],
        "thermal storage": ["thermal storage", "heat storage"],
        "CHP": ["combined heat and power", "chp"],
        "power-to-X": ["power-to-x", "power to x"],
        "biomass": ["biomass"],
    },
    "Objectives / criteria": {
        "cost": ["cost", "economic"],
        "emissions": ["emission", "co2", "carbon"],
        "reliability": ["reliability"],
        "resilience": ["resilience", "resiliency"],
        "self-sufficiency": ["self-sufficiency", "self sufficiency", "autarky"],
        "flexibility": ["flexibility", "flexible"],
        "energy efficiency": ["energy efficiency", "efficiency"],
        "life cycle / LCA": ["lca", "life cycle", "life-cycle"],
    },
}


def canonical_term_hits(text: str) -> List[Tuple[str, str]]:
    t = text.lower()
    hits_found = []
    for cluster, term_aliases in CONTROLLED_TERMS.items():
        for canonical, aliases in term_aliases.items():
            if any(alias in t for alias in aliases):
                hits_found.append((canonical, cluster))
    return hits_found


def build_fig_06() -> None:
    rows = parse_bib_fields(REF / "review_mes_moo_surrogates.bib")
    freq: Counter[str] = Counter()
    cluster_for: Dict[str, str] = {}
    cooc: Counter[Tuple[str, str]] = Counter()

    for row in rows:
        bag = " ".join(
            [
                row.get("title", ""),
                row.get("abstract", ""),
                row.get("author_keywords", ""),
                row.get("keywords", ""),
            ]
        )
        unique_hits = {}
        for term, cluster in canonical_term_hits(bag):
            unique_hits[term] = cluster
        terms = sorted(unique_hits)
        for term, cluster in unique_hits.items():
            freq[term] += 1
            cluster_for[term] = cluster
        for i, a in enumerate(terms):
            for b in terms[i + 1 :]:
                cooc[(a, b)] += 1

    # Keep readable network size.
    top_terms = [term for term, _ in freq.most_common(42)]
    top_set = set(top_terms)
    graph = nx.Graph()
    for term in top_terms:
        graph.add_node(term, weight=freq[term], cluster=cluster_for[term])
    for (a, b), w in cooc.items():
        if a in top_set and b in top_set and w >= 35:
            graph.add_edge(a, b, weight=w)

    # VOSviewer-like, cluster-aware deterministic positions. A pure spring
    # layout collapses almost all generic energy-system terms into the
    # centre because "multi-objective optimization" co-occurs with nearly
    # everything in this literature base. Fixed cluster centres keep the
    # conceptual structure legible while edges still show co-occurrence.
    centers = {
        "Multi-energy systems": (-1.15, 0.35),
        "Optimization algorithms": (0.00, 0.95),
        "Surrogate / ML": (1.15, 0.35),
        "Technologies": (-0.65, -0.75),
        "Objectives / criteria": (0.75, -0.75),
    }
    rank_by_cluster: Dict[str, int] = defaultdict(int)
    pos = {}
    for idx, term in enumerate(top_terms):
        cluster = cluster_for[term]
        local_rank = rank_by_cluster[cluster]
        rank_by_cluster[cluster] += 1
        cx, cy = centers[cluster]
        angle = 2 * math.pi * local_rank / max(6, sum(1 for t in top_terms if cluster_for[t] == cluster))
        ring = 0.14 + 0.075 * (local_rank // 6)
        if local_rank == 0:
            pos[term] = np.array([cx, cy])
        else:
            pos[term] = np.array([cx + ring * math.cos(angle), cy + ring * math.sin(angle)])

    colors = {
        "Multi-energy systems": "#3182CE",
        "Optimization algorithms": "#38A169",
        "Surrogate / ML": "#805AD5",
        "Technologies": "#D69E2E",
        "Objectives / criteria": "#E53E3E",
    }

    fig, ax = plt.subplots(figsize=(13.5, 9.5))
    ax.set_axis_off()
    ax.set_xlim(-1.65, 1.65)
    ax.set_ylim(-1.15, 1.25)
    ax.set_title("Keyword co-occurrence landscape of the merged review bibliography", fontsize=15, fontweight="bold", pad=16)
    ax.text(
        0.5,
        0.985,
        "VOSviewer-inspired map from title, abstract and keyword fields; node size = record frequency, edge width = co-occurrence.",
        transform=ax.transAxes,
        ha="center",
        va="top",
        fontsize=9,
        color="#4A5568",
    )

    for a, b, data in graph.edges(data=True):
        x1, y1 = pos[a]
        x2, y2 = pos[b]
        w = data["weight"]
        ax.plot([x1, x2], [y1, y2], color="#A0AEC0", alpha=0.20, linewidth=0.3 + min(w, 220) / 70)

    max_freq = max(freq[t] for t in top_terms)
    for term in top_terms:
        x, y = pos[term]
        cluster = cluster_for[term]
        size = 120 + 1550 * (freq[term] / max_freq) ** 0.75
        ax.scatter([x], [y], s=size, color=colors[cluster], alpha=0.78, edgecolor="white", linewidth=0.8)
        label = term.replace("multi-objective optimization", "MOO").replace("optimization", "opt.")
        fs = 7 + 4.5 * (freq[term] / max_freq) ** 0.7
        ax.text(x, y, label, ha="center", va="center", fontsize=fs, color="#1A202C")

    legend_handles = [
        plt.Line2D([0], [0], marker="o", color="w", markerfacecolor=color, markersize=10, label=cluster)
        for cluster, color in colors.items()
    ]
    ax.legend(handles=legend_handles, loc="lower left", frameon=False, fontsize=9)

    save_figure(fig, "fig_06_keyword_landscape")

    # Also store the term table for traceability.
    term_rows = [
        {"term": term, "cluster": cluster_for[term], "frequency": freq[term]}
        for term in top_terms
    ]
    with (CSV / "fig_06_keyword_terms.csv").open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["term", "cluster", "frequency"])
        writer.writeheader()
        writer.writerows(term_rows)


def main() -> int:
    build_fig_01()
    build_fig_03()
    build_fig_04()
    build_fig_06()
    print("Wrote figures:")
    for stem in (
        "fig_01_prisma_workflow",
        "fig_03_mes_concept",
        "fig_04_bibliometric_overview",
        "fig_06_keyword_landscape",
    ):
        print(f"  {stem}.png")
    print("  fig_06_keyword_terms.csv")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
