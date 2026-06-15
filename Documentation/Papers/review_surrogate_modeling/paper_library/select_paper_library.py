"""Build the curated Overleaf paper library for the review.

The paper library is a *story-aligned* subset of
``review_mes_moo_surrogates.bib`` that:

1.  contains every citation that already appears in the manuscript
    sections (mandatory keys), so the existing draft compiles cleanly,
2.  rounds out the set to ~240 entries with the highest-impact papers
    per story bucket (Sections 1-9 of the manuscript), and
3.  carries a manifest and a per-section citation plan so future text
    edits can pick the right keys without re-reading thousands of
    BibTeX entries.

Inputs (read-only):

    - manuscript/*.tex
    - references/review_mes_moo_surrogates.bib
    - references/review_mes_moo_surrogates_manifest.csv
    - references/surrogates_esm_screening_enriched.csv
    - references/moo_multicriteria_screening.csv

Outputs (written into ``paper_library/``):

    - review_paper_library.bib
    - review_paper_library_manifest.csv
    - review_paper_library_citation_plan.md
    - review_paper_library_buckets.csv

Run from the ``paper_library`` folder:

    py select_paper_library.py

The selection logic is intentionally deterministic: same inputs produce
the same library. Buckets, quotas and matching terms are documented in
``paper_library/README.md``.
"""

from __future__ import annotations

import csv
import re
import sys
import unicodedata
from collections import Counter, defaultdict
from pathlib import Path
from typing import Callable, Dict, Iterable, List, Tuple

# The shared BibTeX parser lives in references/. We import it via the
# script directory, not by polluting sys.path globally.
HERE = Path(__file__).resolve().parent
PAPER_ROOT = HERE.parent
REFS = PAPER_ROOT / "references"
MAN = PAPER_ROOT / "manuscript"

sys.path.insert(0, str(REFS))
from filter_bib import BibEntry, parse_bib  # noqa: E402  (after sys.path tweak)


# =====================================================================
# BibTeX cleanup
#
# The combined source pool (review_mes_moo_surrogates.bib) is built from
# Scopus exports and therefore carries Scopus-specific telemetry that
# does not belong in a publication-grade bibliography:
#
#   - ``url`` fields point to ``scopus.com`` (Scopus result-list links),
#   - ``note`` fields are ``Cited by: NN; All/Gold/Green Open Access``,
#   - ``type``, ``source``, ``publication_stage`` are Scopus workflow
#     metadata,
#   - ``author_keywords`` is redundant with ``keywords``.
#
# We strip those fields when writing the curated paper-library bib.
# Source files are never modified; this cleanup only affects the
# generated ``review_paper_library.bib`` so the screening pipeline
# stays reproducible against the raw Scopus export.
# =====================================================================


# Whitelist of BibTeX fields that may appear in the curated bib. Any
# field outside this set is dropped silently. The order is the canonical
# emission order; fields are written in this sequence when present so
# the output is diff-friendly across rebuilds.
KEEP_FIELDS: Tuple[str, ...] = (
    "author",
    "title",
    "journal",
    "journaltitle",
    "booktitle",
    "year",
    "date",
    "month",
    "volume",
    "number",
    "pages",
    "doi",
    "issn",
    "isbn",
    "publisher",
    "editor",
    "institution",
    "organization",
    "address",
    "school",
    "series",
    "chapter",
    "edition",
    "howpublished",
    "url",
    "note",
    "keywords",
    "abstract",
)
KEEP_FIELDS_SET: frozenset[str] = frozenset(KEEP_FIELDS)

# Content rules. ``url`` and ``note`` are technically allowed BibTeX
# fields, but in the Scopus export they almost always carry Scopus
# telemetry. The substrings below are checked case-insensitively
# against the field value; a hit drops the field for this entry.
DROP_URL_SUBSTRINGS: Tuple[str, ...] = (
    "scopus.com",
)
DROP_NOTE_SUBSTRINGS: Tuple[str, ...] = (
    "cited by",
    "open access",
)


def clean_bib_entry(entry: BibEntry, new_key: str | None = None) -> Tuple[str, Counter]:
    """Re-serialize a BibEntry with Scopus telemetry stripped.

    Returns the cleaned BibTeX block and a counter of dropped fields,
    so the caller can summarise what was removed across the library.
    """

    key = (new_key or entry.key).strip()
    type_str = entry.type.lower()
    drops: Counter[str] = Counter()

    cleaned: List[Tuple[str, str]] = []
    for name in KEEP_FIELDS:
        raw = entry.fields.get(name)
        if raw is None:
            continue
        value = raw.strip()
        if not value:
            continue
        if name == "url" and any(p in value.lower() for p in DROP_URL_SUBSTRINGS):
            drops["url:scopus"] += 1
            continue
        if name == "note" and any(p in value.lower() for p in DROP_NOTE_SUBSTRINGS):
            drops["note:scopus"] += 1
            continue
        cleaned.append((name, value))

    # Account for fields that were present in the source entry but never
    # made it into ``cleaned``, so the run-end summary shows the full
    # cleanup volume (type, source, publication_stage, author_keywords).
    for name in entry.fields:
        if name not in KEEP_FIELDS_SET:
            drops[f"field:{name}"] += 1

    lines: List[str] = [f"@{type_str}{{{key},"]
    for i, (name, value) in enumerate(cleaned):
        sep = "," if i < len(cleaned) - 1 else ""
        # Multi-line values (abstracts) are preserved verbatim; BibTeX
        # parsers tolerate embedded newlines inside braces.
        lines.append(f"  {name} = {{{value}}}{sep}")
    lines.append("}")
    return "\n".join(lines) + "\n", drops


# =====================================================================
# I/O helpers
# =====================================================================


def ascii_fold(text: str) -> str:
    """Lower-case + strip diacritics so matching is stable across exports."""

    return (
        unicodedata.normalize("NFKD", text or "")
        .encode("ascii", "ignore")
        .decode("ascii")
        .lower()
    )


def _strip_latex_comments(text: str) -> str:
    """Remove LaTeX comments so cite-keys inside ``%``-comments do not
    leak into the mandatory set.

    A ``%`` starts a comment unless it is escaped as ``\\%``. We walk the
    text character by character so backslash-escaping is handled
    correctly. This is intentionally simple -- proper LaTeX parsing
    would be overkill for a one-shot scrape of ``\\cite{...}`` calls.
    """

    out: List[str] = []
    in_comment = False
    i = 0
    while i < len(text):
        ch = text[i]
        if in_comment:
            if ch == "\n":
                in_comment = False
                out.append(ch)
            i += 1
            continue
        if ch == "\\" and i + 1 < len(text):
            out.append(ch)
            out.append(text[i + 1])
            i += 2
            continue
        if ch == "%":
            in_comment = True
            i += 1
            continue
        out.append(ch)
        i += 1
    return "".join(out)


def collect_mandatory_cites() -> List[str]:
    """Return citation keys already used in the manuscript .tex files
    and in the table .tex files that the manuscript ``\\input``s.

    LaTeX comments are stripped before scanning so example ``\\cite{...}``
    calls inside ``%``-comments (e.g. in template headers) do not become
    spurious mandatory keys.

    Both the ``manuscript/`` folder (section bodies) and the ``tables/``
    folder (table_T*.tex files included from the sections) are scanned
    so cite keys that live exclusively inside a table file (e.g. T7
    meta-review citations) are also picked up as mandatory.
    """

    keys: List[str] = []
    seen: set[str] = set()
    tables_dir = PAPER_ROOT / "tables"
    sources: List[Path] = sorted(MAN.glob("*.tex"))
    if tables_dir.exists():
        sources.extend(sorted(tables_dir.glob("*.tex")))
    for tex in sources:
        raw = tex.read_text(encoding="utf-8", errors="ignore")
        text = _strip_latex_comments(raw)
        for match in re.finditer(r"\\cite\{([^}]+)\}", text):
            for raw_key in match.group(1).split(","):
                key = raw_key.strip()
                if key and key not in seen:
                    seen.add(key)
                    keys.append(key)
    return keys


def load_csv(path: Path, key_field: str = "cite_key") -> Dict[str, Dict[str, str]]:
    """Load a CSV indexed by ``key_field`` (skip duplicates silently)."""

    rows: Dict[str, Dict[str, str]] = {}
    with path.open(encoding="utf-8") as f:
        for row in csv.DictReader(f):
            key = row.get(key_field, "")
            if key and key not in rows:
                rows[key] = row
    return rows


# =====================================================================
# Pool construction
# =====================================================================


def to_int(value: object) -> int:
    """Lenient int parser (citation counts and years are sometimes empty)."""

    try:
        return int(str(value).strip())
    except (TypeError, ValueError):
        return 0


def build_pool() -> Dict[str, Dict[str, object]]:
    """Merge manifest + screening CSVs into the working pool."""

    manifest = load_csv(REFS / "review_mes_moo_surrogates_manifest.csv")
    surr_csv = load_csv(REFS / "surrogates_esm_screening_enriched.csv")
    moo_csv = load_csv(REFS / "moo_multicriteria_screening.csv")

    pool: Dict[str, Dict[str, object]] = {}
    for ck, row in manifest.items():
        # Manifest stores both the (renamed) library key and the original
        # Scopus key. Screening CSVs are indexed by the Scopus key.
        original = (row.get("original_cite_key") or ck).strip()
        srec = surr_csv.get(original, {})
        mrec = moo_csv.get(original, {})

        title = row.get("title", "") or ""
        venue = row.get("venue", "") or ""

        merged_terms = {
            "matched_surrogate_terms": "; ".join(
                t for t in [srec.get("matched_surrogate_terms"), mrec.get("matched_surrogate_terms")] if t
            ),
            "matched_ml_terms": "; ".join(
                t for t in [srec.get("matched_ml_terms"), mrec.get("matched_ml_terms")] if t
            ),
            "matched_opt_terms": srec.get("matched_opt_terms", "") or "",
            "matched_esm_terms": srec.get("matched_esm_terms", "") or "",
            "matched_moo_terms": mrec.get("matched_moo_terms", "") or "",
            "matched_mes_terms": mrec.get("matched_mes_terms", "") or "",
            "matched_mcdm_terms": mrec.get("matched_mcdm_terms", "") or "",
            "matched_algorithm_terms": mrec.get("matched_algorithm_terms", "") or "",
            "matched_proxy_hints": "; ".join(
                t for t in [srec.get("matched_proxy_hints"), mrec.get("matched_proxy_hints")] if t
            ),
        }

        pool[ck] = {
            "cite_key": ck,
            "original_cite_key": original,
            "title": title,
            "title_ascii": ascii_fold(title),
            "venue": venue,
            "venue_ascii": ascii_fold(venue),
            "year": to_int(row.get("year")),
            "doi": (row.get("doi") or "").strip(),
            "sources": (row.get("sources") or "").strip(),
            "cited_by_count": to_int(srec.get("cited_by_count")),
            "tier": (srec.get("tier") or "").strip(),
            "decision": (srec.get("decision") or "").strip(),
            "primary_topic": (srec.get("primary_topic") or "").strip(),
            "read_priority": (srec.get("read_priority") or "").strip(),
            "focus": (mrec.get("focus") or "").strip(),
            "surrogate_signal": (mrec.get("surrogate_signal") or "0").strip(),
            "is_mes": (mrec.get("is_mes") or "0").strip(),
            "is_moo": (mrec.get("is_moo") or "0").strip(),
            **{k: ascii_fold(v) for k, v in merged_terms.items()},
        }
    return pool


# =====================================================================
# Bucket definitions
#
# Each bucket mirrors a part of the manuscript story. The predicate is a
# pure function on a pool row; quotas are *target* sizes, not strict
# upper bounds (mandatory cites can push a bucket above its quota).
# =====================================================================


def has_term(haystack: str, needles: Iterable[str]) -> bool:
    """True if any needle appears as substring in the haystack."""

    return any(n in haystack for n in needles)


def title_or_terms(row: Dict[str, object], terms: Iterable[str]) -> bool:
    """Match across title + all merged matched_* fields."""

    bag_parts: List[str] = [str(row["title_ascii"])]
    for field in (
        "matched_surrogate_terms",
        "matched_ml_terms",
        "matched_opt_terms",
        "matched_esm_terms",
        "matched_moo_terms",
        "matched_mes_terms",
        "matched_mcdm_terms",
        "matched_algorithm_terms",
        "matched_proxy_hints",
    ):
        bag_parts.append(str(row[field]))
    bag = " | ".join(bag_parts)
    return has_term(bag, terms)


def is_review(row: Dict[str, object]) -> bool:
    """Reviews / surveys / scoping / comparative meta-studies."""

    title = str(row["title_ascii"])
    return has_term(
        title,
        [
            "review",
            "survey",
            "scoping",
            "systematic literature",
            "state of the art",
            "state-of-the-art",
            "overview of",
            "perspective",
            "tutorial",
            "bibliometric",
            "research agenda",
            "roadmap",
            "comparison of",
            "comparison and",
            "comparative study",
            "comparative analysis",
            "preliminary study",
        ],
    )


# Term banks per story section; aliases included so spelling variants
# are caught (multi-objective / multiobjective / multi objective ...).
T_GP = ["gaussian process", "kriging", "co-kriging", "cokriging", "gp surrogate"]
T_PCE = [
    "polynomial chaos",
    "chaos expansion",
    "stochastic collocation",
    "response surface",
    "polynomial regression",
    "polynomial surrogate",
]
T_RBF = [
    "radial basis",
    "rbf network",
    "rbf surrogate",
    "kernel regression",
    "support vector",
]
T_TREE = [
    "random forest",
    "gradient boosting",
    "xgboost",
    "lightgbm",
    "catboost",
    "decision tree",
    "boosted trees",
    "regression tree",
]
T_NEURAL = [
    "neural network",
    "deep learning",
    "convolutional",
    "recurrent",
    "lstm",
    "gru",
    "transformer",
    "attention",
    "graph neural",
    "feedforward",
    "multilayer perceptron",
    "deep neural",
]
T_CONSTRAINT = [
    "constraint",
    "feasib",
    "violation",
    "differentiable",
    "lagrang",
    "kkt",
    "primal-dual",
]
T_HYBRID = [
    "physics-informed",
    "physics informed",
    "hybrid model",
    "data-driven physics",
    "domain knowledge",
    "grey-box",
    "grey box",
    "knowledge-based",
]
T_DECISION = [
    "learning to optimize",
    "learn to solve",
    "learn-to-solve",
    "predict-then-optimize",
    "predict and optimize",
    "decision-focused",
    "decision focused",
    "end-to-end",
    "optimization proxy",
    "optimization proxies",
    "differentiable optim",
]
T_DOE = [
    "latin hypercube",
    "sobol",
    "halton",
    "design of experiments",
    "active learning",
    "adaptive sampling",
    "experiment design",
    "doe",
]
T_MULTIFI = [
    "multi-fidelity",
    "multifidelity",
    "multi fidelity",
    "co-kriging",
    "transfer learning",
    "fidelity",
]
T_BAYES = [
    "bayesian optim",
    "expected improvement",
    "acquisition function",
    "surrogate-assisted",
    "surrogate assisted",
]
T_WARM = [
    "warm-start",
    "warm start",
    "primal-dual",
    "feasible solution",
    "initialization",
    "hot start",
]
T_DECOMP = [
    "benders",
    "decomposition",
    "lagrangian relaxation",
    "dantzig-wolfe",
    "admm",
    "column generation",
]
T_UNCERTAIN = [
    "uncertainty",
    "stochastic",
    "robust",
    "scenario",
    "chance-constrained",
    "chance constrained",
    "risk",
    "probabilistic",
]
T_VALID = [
    "validation",
    "calibration",
    "out-of-distribution",
    "out of distribution",
    "regret",
    "mip-gap",
    "mip gap",
    "feasibility check",
    "stress test",
]
T_ED_UC = [
    "unit commitment",
    "economic dispatch",
    "uc problem",
    "dispatch optim",
    "security-constrained",
    "security constrained",
]
T_OPF = [
    "optimal power flow",
    "opf ",
    " opf",
    "ac opf",
    "ac-opf",
    "dc opf",
    "dc-opf",
    "ac/dc",
]
T_CAP_EXP = [
    "capacity expansion",
    "generation expansion",
    "transmission expansion",
    "investment plan",
    "long-term planning",
    "long term planning",
    "capacity planning",
    "expansion planning",
]
T_DH = [
    "district heating",
    "district cooling",
    "thermal network",
    "heating network",
    "fifth generation",
    "5gdhc",
    "low-temperature heating",
]
T_MES = [
    "multi-energy",
    "multi energy",
    "multienergy",
    "sector coupling",
    "sector-coupling",
    "integrated energy",
    "energy hub",
    "power-to-heat",
    "power-to-x",
    "power to x",
    "hydrogen",
    "co-production",
    "coproduction",
    "electrolyzer",
    "electrolyser",
    "fuel cell",
]
T_MICROGRID = [
    "microgrid",
    "micro-grid",
    "micro grid",
    "energy community",
    "energy communities",
    "virtual power plant",
    "off-grid",
    "stand-alone",
    "standalone",
    "hybrid renewable",
]
T_MOO = [
    "multi-objective",
    "multi objective",
    "multiobjective",
    "many-objective",
    "pareto",
    "non-dominated",
    "nondominated",
    "trade-off",
    "trade off",
]
T_STOCH = [
    "stochastic optim",
    "robust optim",
    "two-stage",
    "two stage",
    "scenario-based",
    "scenario based",
    "chance-constrained",
    "chance constrained",
]
T_NSGA = [
    "nsga",
    "nsga-ii",
    "nsga ii",
    "nsga-iii",
    "nsga iii",
    "moea/d",
    "moead",
    "spea",
    "rvea",
    "sms-emoa",
    "indicator-based",
]
T_META = [
    "particle swarm",
    "pso",
    "differential evolution",
    "grey wolf",
    "cma-es",
    "evolution strategy",
    "genetic algorithm",
    "ant colony",
    "bat algorithm",
    "harris hawks",
    "whale optim",
    "cuckoo",
]
T_MCDM = [
    "topsis",
    "vikor",
    "promethee",
    " ahp",
    " anp",
    "electre",
    "waspas",
    "codas",
    "mcdm",
    "multicriteria decision",
    "multi-criteria decision",
]


def is_surrogate_signal(row: Dict[str, object]) -> bool:
    """Helper: paper has any surrogate / ML / proxy signal."""

    return (
        bool(row["matched_surrogate_terms"])
        or bool(row["matched_ml_terms"])
        or bool(row["matched_proxy_hints"])
        or row["surrogate_signal"] == "1"
        or row["tier"] in {"A", "B"}
    )


# Bucket = (id, label, manuscript section, predicate, quota)
BUCKETS: List[Tuple[str, str, str, Callable[[Dict[str, object]], bool], int]] = [
    (
        "B01_cornerstone_reviews",
        "Cornerstone reviews and surveys",
        "Sec. 1, 2, 8",
        is_review,
        14,
    ),
    (
        "B02_gp_kriging",
        "Gaussian process / kriging emulators",
        "Sec. 3.2",
        lambda r: title_or_terms(r, T_GP),
        12,
    ),
    (
        "B03_pce_response_surface",
        "Polynomial chaos and response surfaces",
        "Sec. 3.1",
        lambda r: title_or_terms(r, T_PCE),
        10,
    ),
    (
        "B04_rbf_kernel",
        "Radial basis functions / kernel regressors",
        "Sec. 3.3",
        lambda r: title_or_terms(r, T_RBF),
        8,
    ),
    (
        "B05_tree_ensembles",
        "Tree ensembles (RF, gradient boosting)",
        "Sec. 3.4",
        lambda r: title_or_terms(r, T_TREE),
        8,
    ),
    (
        "B06_neural_surrogates",
        "Neural surrogates (MLP/CNN/RNN/GNN)",
        "Sec. 3.5",
        lambda r: title_or_terms(r, T_NEURAL),
        16,
    ),
    (
        "B07_constraint_aware",
        "Constraint-aware / structure-preserving surrogates",
        "Sec. 3.6",
        lambda r: title_or_terms(r, T_CONSTRAINT) and is_surrogate_signal(r),
        7,
    ),
    (
        "B08_hybrid_pinn",
        "Hybrid and physics-informed surrogates",
        "Sec. 3.7",
        lambda r: title_or_terms(r, T_HYBRID),
        7,
    ),
    (
        "B09_decision_focused_l2o",
        "Decision-focused and learning-to-optimize",
        "Sec. 3.8",
        lambda r: title_or_terms(r, T_DECISION),
        7,
    ),
    (
        "B10_doe_active_learning",
        "Design of experiments and active learning",
        "Sec. 4.2-4.3",
        lambda r: title_or_terms(r, T_DOE),
        7,
    ),
    (
        "B11_multi_fidelity",
        "Multi-fidelity / transfer learning",
        "Sec. 4.4",
        lambda r: title_or_terms(r, T_MULTIFI),
        7,
    ),
    (
        "B12_bayes_accel",
        "Bayesian / surrogate-assisted optimization",
        "Sec. 5.2",
        lambda r: title_or_terms(r, T_BAYES),
        9,
    ),
    (
        "B13_warm_start",
        "Warm-start and primal-dual proxies",
        "Sec. 5.3",
        lambda r: title_or_terms(r, T_WARM) and is_surrogate_signal(r),
        5,
    ),
    (
        "B14_decomposition",
        "Surrogate-enabled decomposition",
        "Sec. 5.4",
        lambda r: title_or_terms(r, T_DECOMP),
        6,
    ),
    (
        "B15_uncertainty",
        "Uncertainty handling with surrogates",
        "Sec. 5.5",
        lambda r: title_or_terms(r, T_UNCERTAIN) and is_surrogate_signal(r),
        9,
    ),
    (
        "B16_validation",
        "Validation and decision-aware metrics",
        "Sec. 6",
        lambda r: title_or_terms(r, T_VALID),
        5,
    ),
    (
        "B17_ed_uc",
        "Economic dispatch and unit commitment",
        "Sec. 7.1",
        lambda r: title_or_terms(r, T_ED_UC),
        9,
    ),
    (
        "B18_opf",
        "Optimal power flow surrogates",
        "Sec. 7.2",
        lambda r: title_or_terms(r, T_OPF),
        9,
    ),
    (
        "B19_capacity_expansion",
        "Capacity and generation expansion planning",
        "Sec. 7.3",
        lambda r: title_or_terms(r, T_CAP_EXP),
        8,
    ),
    (
        "B20_district_heating",
        "District heating and thermal storage",
        "Sec. 7.4",
        lambda r: title_or_terms(r, T_DH),
        8,
    ),
    (
        "B21_mes_sector_coupling",
        "Multi-energy and sector-coupled systems",
        "Sec. 7.5",
        lambda r: title_or_terms(r, T_MES),
        12,
    ),
    (
        "B22_microgrid_hub",
        "Microgrids, energy hubs and communities",
        "Sec. 7.6",
        lambda r: title_or_terms(r, T_MICROGRID),
        12,
    ),
    (
        "B23_moo_design",
        "Multi-objective MES design",
        "Sec. 7.7",
        lambda r: title_or_terms(r, T_MOO) and (r["is_mes"] == "1" or title_or_terms(r, T_MES + T_MICROGRID)),
        14,
    ),
    (
        "B24_stochastic_robust",
        "Stochastic and robust energy planning",
        "Sec. 7.8",
        lambda r: title_or_terms(r, T_STOCH),
        8,
    ),
    (
        "B25_moo_algorithms_nsga",
        "MOO algorithms (NSGA-II/III, MOEA/D, RVEA)",
        "Sec. 5, 7.7",
        lambda r: title_or_terms(r, T_NSGA),
        10,
    ),
    (
        "B26_moo_metaheuristics",
        "Other multi-objective metaheuristics",
        "Sec. 5, 7.7",
        # NSGA already has its own bucket; here we want the breadth of
        # MOO metaheuristics (PSO, DE, GWO, CMA-ES, ...). We accept any
        # algorithm tag together with a multi-objective signal.
        lambda r: (
            bool(r["matched_algorithm_terms"])
            and (bool(r["matched_moo_terms"]) or r["is_moo"] == "1" or title_or_terms(r, T_MOO))
            and not has_term(str(r["matched_algorithm_terms"]), ["nsga"])
        ),
        6,
    ),
    (
        "B27_mcdm",
        "MCDM and posterior decision making",
        "Sec. 7.7, 8",
        # MCDM is rare in the MOO+MES intersection; accept tag-based
        # matches as well as title text so we still cover the post-Pareto
        # decision-making literature.
        lambda r: title_or_terms(r, T_MCDM) or bool(r["matched_mcdm_terms"]),
        4,
    ),
]


# =====================================================================
# Selection algorithm
# =====================================================================


def score(row: Dict[str, object]) -> Tuple[int, int]:
    """Higher is better: (citations, year)."""

    return (int(row["cited_by_count"]), int(row["year"]))


def select_for_bucket(
    pool: Dict[str, Dict[str, object]],
    predicate: Callable[[Dict[str, object]], bool],
    quota: int,
    already_selected: set[str],
) -> List[str]:
    """Return up to ``quota`` keys from the pool that match ``predicate``.

    Top-up by citation count is intentional: review readers expect to
    see the most-cited works in each thematic block. Mandatory keys are
    inserted upstream, so this function only fills the gap.
    """

    candidates = [r for r in pool.values() if r["cite_key"] not in already_selected and predicate(r)]
    candidates.sort(key=score, reverse=True)
    return [r["cite_key"] for r in candidates[:quota]]


def assign_buckets(
    selected: Iterable[str],
    pool: Dict[str, Dict[str, object]],
) -> Dict[str, List[str]]:
    """For each selected key, list every bucket it logically falls into.

    A paper can legitimately serve multiple sections (e.g. an OPF
    surrogate that is also Bayesian-optimization based). The citation
    plan reports all such bucket memberships.
    """

    by_key: Dict[str, List[str]] = defaultdict(list)
    for key in selected:
        row = pool.get(key)
        if not row:
            continue
        for bucket_id, _label, _section, predicate, _quota in BUCKETS:
            try:
                if predicate(row):
                    by_key[key].append(bucket_id)
            except Exception:  # noqa: BLE001 - predicates are pure
                continue
        if not by_key[key]:
            by_key[key].append("B99_misc")
    return by_key


# =====================================================================
# Output writers
# =====================================================================


def write_subset_bib(
    selected: List[str],
    bib_path: Path,
    out_path: Path,
) -> Tuple[int, Counter]:
    """Write a BibTeX subset with Scopus telemetry stripped.

    Returns ``(entries_written, drop_summary)`` where ``drop_summary``
    is a counter of dropped Scopus fields across the whole library.
    """

    entries = parse_bib(bib_path)
    by_key: Dict[str, BibEntry] = {e.key: e for e in entries}
    written = 0
    drop_summary: Counter[str] = Counter()
    with out_path.open("w", encoding="utf-8") as f:
        f.write("% Generated by select_paper_library.py.\n")
        f.write(f"% Subset of {bib_path.name} aligned with the manuscript story.\n")
        f.write(
            "% Scopus-specific metadata (url -> scopus.com, note 'Cited by'/\n"
            "%  Open Access, type, source, publication_stage, author_keywords)\n"
            "%  is stripped. Source files are never modified; rebuild via\n"
            "%  paper_library/select_paper_library.py.\n\n"
        )
        for key in selected:
            entry = by_key.get(key)
            if not entry:
                continue
            block, drops = clean_bib_entry(entry, new_key=key)
            f.write(block)
            f.write("\n")
            written += 1
            drop_summary.update(drops)
    return written, drop_summary


def write_manifest(
    selected: List[str],
    pool: Dict[str, Dict[str, object]],
    bucket_map: Dict[str, List[str]],
    mandatory: set[str],
    primary_bucket: Dict[str, str],
    out_path: Path,
) -> None:
    """Per-paper provenance + bucket assignment for the curated library."""

    fieldnames = [
        "cite_key",
        "primary_bucket",
        "all_buckets",
        "mandatory",
        "year",
        "title",
        "venue",
        "doi",
        "cited_by_count",
        "tier",
        "focus",
        "primary_topic",
        "sources",
    ]
    with out_path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for key in selected:
            row = pool.get(key, {})
            writer.writerow(
                {
                    "cite_key": key,
                    "primary_bucket": primary_bucket.get(key, "B99_misc"),
                    "all_buckets": ";".join(bucket_map.get(key, [])),
                    "mandatory": "1" if key in mandatory else "0",
                    "year": row.get("year", ""),
                    "title": row.get("title", ""),
                    "venue": row.get("venue", ""),
                    "doi": row.get("doi", ""),
                    "cited_by_count": row.get("cited_by_count", ""),
                    "tier": row.get("tier", ""),
                    "focus": row.get("focus", ""),
                    "primary_topic": row.get("primary_topic", ""),
                    "sources": row.get("sources", ""),
                }
            )


def write_buckets_csv(
    bucket_members: Dict[str, List[str]],
    pool: Dict[str, Dict[str, object]],
    out_path: Path,
) -> None:
    """Long-format bucket -> cite_key listing for spreadsheet review."""

    fieldnames = [
        "bucket_id",
        "bucket_label",
        "section",
        "cite_key",
        "year",
        "cited_by_count",
        "title",
    ]
    bucket_meta = {b[0]: (b[1], b[2]) for b in BUCKETS}
    with out_path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for bucket_id, _label, _section, _pred, _quota in BUCKETS:
            for key in bucket_members.get(bucket_id, []):
                row = pool.get(key, {})
                writer.writerow(
                    {
                        "bucket_id": bucket_id,
                        "bucket_label": bucket_meta[bucket_id][0],
                        "section": bucket_meta[bucket_id][1],
                        "cite_key": key,
                        "year": row.get("year", ""),
                        "cited_by_count": row.get("cited_by_count", ""),
                        "title": row.get("title", ""),
                    }
                )


def write_citation_plan(
    bucket_members: Dict[str, List[str]],
    pool: Dict[str, Dict[str, object]],
    mandatory: set[str],
    out_path: Path,
) -> None:
    """Markdown plan that maps story sections to ready-to-cite keys."""

    lines: List[str] = []
    lines.append("# Citation plan for the surrogate-MOO-MES review\n")
    lines.append(
        "Auto-generated by `select_paper_library.py`. Each block lists the "
        "cite keys that match the manuscript section, sorted by citation "
        "count (desc) within the bucket. Keys flagged with `*` are already "
        "cited in the current draft; keys without flag are top-up.\n"
    )

    for bucket_id, label, section, _pred, _quota in BUCKETS:
        keys = bucket_members.get(bucket_id, [])
        if not keys:
            continue
        # Sort within bucket by score, mandatory first.
        keys_sorted = sorted(
            keys,
            key=lambda k: (
                0 if k in mandatory else 1,
                -int(pool[k]["cited_by_count"]),
                -int(pool[k]["year"]),
            ),
        )
        lines.append(f"\n## {bucket_id}: {label}\n")
        lines.append(f"Manuscript sections: {section}.\n")
        lines.append("")
        for key in keys_sorted:
            row = pool[key]
            star = "*" if key in mandatory else " "
            lines.append(
                f"- [{star}] `{key}` ({row['year']}, cited {row['cited_by_count']}): "
                f"{row['title']} -- {row['venue']}"
            )

    out_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


# =====================================================================
# Driver
# =====================================================================


def main() -> int:
    pool = build_pool()
    mandatory_keys = collect_mandatory_cites()
    mandatory = set(mandatory_keys)

    # Sanity: every mandatory key must exist in the pool. The manuscript
    # has been written against the combined bibliography, so a miss here
    # is a hard error -- we surface it instead of silently dropping it.
    missing = [k for k in mandatory_keys if k not in pool]
    if missing:
        sys.stderr.write(
            "error: the following mandatory cite keys from the manuscript are "
            "not present in review_mes_moo_surrogates_manifest.csv:\n  - "
            + "\n  - ".join(missing)
            + "\n"
        )
        return 2

    selected: List[str] = []
    selected_set: set[str] = set()
    bucket_members: Dict[str, List[str]] = {b[0]: [] for b in BUCKETS}

    # Step 1: every mandatory key enters the library and gets one bucket
    # tag (the first matching bucket); the manifest will list all
    # matching buckets so cross-references stay visible.
    for key in mandatory_keys:
        if key in selected_set:
            continue
        selected.append(key)
        selected_set.add(key)
        row = pool[key]
        for bucket_id, _label, _section, predicate, _quota in BUCKETS:
            if predicate(row):
                bucket_members[bucket_id].append(key)
                break
        else:
            bucket_members.setdefault("B99_misc", []).append(key)

    # Step 2: top-up each bucket up to its quota with the highest-cited
    # non-mandatory papers that satisfy the bucket predicate.
    for bucket_id, _label, _section, predicate, quota in BUCKETS:
        existing = len(bucket_members[bucket_id])
        if existing >= quota:
            continue
        gap = quota - existing
        new_keys = select_for_bucket(pool, predicate, gap * 3, selected_set)
        added = 0
        for k in new_keys:
            if added >= gap:
                break
            if k in selected_set:
                continue
            selected.append(k)
            selected_set.add(k)
            bucket_members[bucket_id].append(k)
            added += 1

    # Step 3: if the library is below the global target, top-up with the
    # highest-cited remaining papers that are MOO+MES focused but did
    # not match any bucket -- still story-relevant.
    GLOBAL_TARGET = 240
    if len(selected) < GLOBAL_TARGET:
        remaining = [
            r
            for r in pool.values()
            if r["cite_key"] not in selected_set
            and (r["focus"] in {"moo_mes", "moo_mes_surrogate"} or r["tier"] == "A")
        ]
        remaining.sort(key=score, reverse=True)
        for r in remaining:
            if len(selected) >= GLOBAL_TARGET:
                break
            selected.append(r["cite_key"])
            selected_set.add(r["cite_key"])
            bucket_members.setdefault("B99_misc", []).append(r["cite_key"])

    # Cap if we somehow overshoot (mandatory + bucket fill could exceed
    # the quota total). Mandatory keys are never dropped.
    HARD_CAP = 260
    if len(selected) > HARD_CAP:
        # Drop trailing non-mandatory entries.
        keep: List[str] = []
        for key in selected:
            if len(keep) >= HARD_CAP and key not in mandatory:
                continue
            keep.append(key)
        selected = keep
        selected_set = set(selected)
        for bucket_id in list(bucket_members):
            bucket_members[bucket_id] = [k for k in bucket_members[bucket_id] if k in selected_set]

    # Build the all-buckets map and a primary-bucket map for the
    # manifest. Primary bucket is the first BUCKETS entry the row
    # matches, mirroring step-1 logic.
    bucket_map = assign_buckets(selected, pool)
    primary_bucket: Dict[str, str] = {}
    for bucket_id, _label, _section, _pred, _quota in BUCKETS:
        for key in bucket_members.get(bucket_id, []):
            primary_bucket.setdefault(key, bucket_id)
    for key in selected:
        primary_bucket.setdefault(key, "B99_misc")

    # ---- write outputs --------------------------------------------------
    out_bib = HERE / "review_paper_library.bib"
    out_manifest = HERE / "review_paper_library_manifest.csv"
    out_buckets = HERE / "review_paper_library_buckets.csv"
    out_plan = HERE / "review_paper_library_citation_plan.md"

    written, drop_summary = write_subset_bib(
        selected,
        REFS / "review_mes_moo_surrogates.bib",
        out_bib,
    )
    write_manifest(selected, pool, bucket_map, mandatory, primary_bucket, out_manifest)
    write_buckets_csv(bucket_members, pool, out_buckets)
    write_citation_plan(bucket_members, pool, mandatory, out_plan)

    bucket_counts = Counter({b: len(v) for b, v in bucket_members.items()})
    print(f"Pool size                     : {len(pool)}")
    print(f"Mandatory cite keys           : {len(mandatory_keys)}")
    print(f"Library size (selected keys)  : {len(selected)}")
    print(f"BibTeX entries written        : {written}")
    print()
    print("Bucket distribution:")
    for bucket_id, _label, _section, _pred, _quota in BUCKETS + [("B99_misc", "misc", "-", lambda r: False, 0)]:
        if bucket_counts.get(bucket_id):
            print(f"  {bucket_id:<32} {bucket_counts[bucket_id]:>3}")
    print()
    if drop_summary:
        print("Scopus telemetry stripped from bib entries:")
        for key, count in sorted(drop_summary.items()):
            print(f"  {key:<32} {count}")
        print()
    print(f"Wrote {out_bib.name}")
    print(f"Wrote {out_manifest.name}")
    print(f"Wrote {out_buckets.name}")
    print(f"Wrote {out_plan.name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
