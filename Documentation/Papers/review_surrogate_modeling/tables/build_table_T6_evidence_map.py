"""Render the evidence-map table (T6) from the curated paper library.

Usage (from the ``tables`` folder)::

    py build_table_T6_evidence_map.py              # compact MES-focused map
    py build_table_T6_evidence_map.py --mode full  # all 285 manifest rows

Compact mode keeps multi-energy / sector-coupled systems, microgrids,
energy hubs, district heating, and related dispatch, OPF, expansion
and stochastic planning studies. Single-component technology papers
are dropped. All cite keys in ``08_application_evidence_map.tex`` are
always retained.

Output is a single ``longtable`` (one caption/label, page breaks).
"""
from __future__ import annotations

import argparse
import csv
import re
from pathlib import Path
from typing import Dict, List, Sequence, Set, Tuple

ROOT = Path(__file__).resolve().parent.parent
MANIFEST = ROOT / "paper_library" / "review_paper_library_manifest.csv"
BUCKETS_CSV = ROOT / "paper_library" / "review_paper_library_buckets.csv"
APPLICATIONS_TEX = ROOT / "manuscript" / "08_application_evidence_map.tex"
OUT_APPENDIX = ROOT / "manuscript" / "appendix" / "table_T6_evidence_map.tex"
OUT_TABLES_LEGACY = ROOT / "tables" / "table_T6_evidence_map.tex"
OUT_COMPACT_MANIFEST = (
    ROOT / "paper_library" / "review_paper_library_manifest_T6_compact.csv"
)
PDF_MATCH_MAP = ROOT / "_tmp_pdf_author_title_match_map.csv"
LITERATUR_ROOT = ROOT / "Literatur"
PDF_EXTRACT_PAGES = 20

COMPACT_TARGET = 142

LONGTABLE_COLSPEC = (
    r"@{}p{0.16\textwidth} p{0.04\textwidth} p{0.28\textwidth} "
    r"p{0.14\textwidth} p{0.14\textwidth} p{0.14\textwidth}@{}"
)
LONGTABLE_HEADER = (
    r"Reference & Year & Topic & Surrogate class & DoE & Validation \\"
)

DOE_BUCKET_MAP: Dict[str, str] = {
    "B10_doe_active_learning": "Active learning",
    "B11_multi_fidelity": "Multi-fidelity",
}

MES_TASK_BUCKETS = {
    "B17_ed_uc",
    "B18_opf",
    "B19_capacity_expansion",
    "B20_district_heating",
    "B21_mes_sector_coupling",
    "B22_microgrid_hub",
    "B23_moo_design",
    "B24_stochastic_robust",
}
CORE_SYSTEM_BUCKETS = {
    "B21_mes_sector_coupling",
    "B22_microgrid_hub",
    "B20_district_heating",
}

EXCLUDE_TITLE_SNIPPETS = (
    "biodiesel",
    "jatropha",
    "lipase",
    "phase change material",
    "microencapsulated",
    "electric motor",
    "permanent-magnet",
    "flywheel storage machine",
    "liquid cooling cylindrical battery",
    "machining via machine learning",
    "wind power prediction using machine learning methods: a comparative",
    "performance comparison of machine learning algorithms for load forecasting",
    "modeling of solar energy systems using artificial neural network",
    "efficient wind power prediction",
    "global horizontal irradiance",
    "photovoltaic power systems using an optimal control strategy",
    "thermal properties optimization of microencapsulated",
    "ship unit commitment",
    "hybrid ship",
    "geothermal",
    "solar-assisted-geothermal",
    "the role of biomass gasification",
)

# OpenAlex primary_topic prefixes / fragments treated as out of MES scope.
EXCLUDE_TOPIC_SNIPPETS = (
    "electric and hybrid vehicle",
    "electric vehicles and infrastructure",
    "geothermal energy",
    "maritime transport",
    "thermodynamic and exergetic",
    "thermochemical biomass",
    "advanced battery technolog",
    "advanced aircraft design",
    "fuel cells and related material",
    "electric motor design",
    "phase change materials",
    "biodiesel production",
    "photovoltaic system optimization techniques",
    "reservoir engineering and simulation",
    "radiation effects in electronics",
    "energy harvesting in wireless",
)

MOO_MES_TITLE_HINTS = (
    "microgrid",
    "multi-energy",
    "integrated",
    "hybrid renewable",
    "hres",
    "energy hub",
    "cchp",
    "ies",
    "sector",
    "coupl",
    "district",
    "combined cooling",
    "combined heat",
)

FAMILY_MAP: Dict[str, str] = {
    "B01_cornerstone_reviews": "Review",
    "B02_gp_kriging": "GP / kriging",
    "B03_pce_response_surface": "PCE / RSM",
    "B04_rbf_kernel": "RBF / kernel",
    "B05_tree_ensembles": "Tree ensembles",
    "B06_neural_surrogates": "Neural network",
    "B07_constraint_aware": "Constraint-aware NN",
    "B08_hybrid_pinn": "Hybrid / PINN",
    "B09_decision_focused_l2o": "L2O / decision-focused",
}

TASK_MAP: Dict[str, str] = {
    "B17_ed_uc": "ED / UC",
    "B18_opf": "OPF",
    "B19_capacity_expansion": "CapEx",
    "B20_district_heating": "DH",
    "B21_mes_sector_coupling": "MES",
    "B22_microgrid_hub": "Microgrid / hub",
    "B23_moo_design": "MOO design",
    "B24_stochastic_robust": "Stoch / robust",
}

ROLE_MAP: Dict[str, str] = {
    "B07_constraint_aware": "P1",
    "B09_decision_focused_l2o": "P1/P3",
    "B10_doe_active_learning": "P2",
    "B11_multi_fidelity": "P2",
    "B12_bayes_accel": "P2",
    "B14_decomposition": "P4",
    "B15_uncertainty": "P5",
    "B17_ed_uc": "P1/P3",
    "B18_opf": "P1",
    "B23_moo_design": "P2",
}

COMPACT_CAPTION = r"""  \caption{Evidence map of the MES-focused curated subset
  (Section~\ref{sec:applications}). Rows cover multi-energy and sector-
  coupled systems, microgrids and energy hubs, district heating, and
  closely related economic dispatch, OPF, expansion and stochastic
  planning studies; component-level material, vehicle, geothermal,
  maritime, aircraft and battery-technology papers are omitted.
  Topic is the OpenAlex \texttt{primary\_topic}; surrogate class,
  design-of-experiments (DoE) practice (cf.\ Table~\ref{tab:T3-doe})
  and validation evidence (cf.\ Table~\ref{tab:T4-validation}) follow
  bucket tags in \texttt{review\_paper\_library\_manifest.csv}, with
  title- and PDF-text inference (first \(N\) pages under
  \texttt{Literatur/}) when a bucket axis is silent. Review-only
  entries are omitted. The full curated library (\(N=285\)) is in
  \texttt{review\_paper\_library\_manifest.csv}.}"""

FULL_CAPTION = r"""  \caption{Evidence map of the full curated paper library
  (Section~\ref{app:search}). Surrogate class, DoE practice and
  validation evidence are inferred from bucket assignments in
  \texttt{paper\_library/review\_paper\_library\_buckets.csv}.
  Cells marked ``--'' indicate that the entry does not
  carry an unambiguous bucket assignment on the corresponding axis.}"""


def lookup(buckets: List[str], mapping: Dict[str, str]) -> str:
    """Prefer ``primary_bucket`` (first entry) before secondary tags."""
    if not buckets:
        return "--"
    primary = buckets[0]
    if primary in mapping:
        return mapping[primary]
    for b in buckets[1:]:
        if b in mapping:
            return mapping[b]
    return "--"


def load_bucket_index() -> Dict[str, List[str]]:
    index: Dict[str, List[str]] = {}
    if not BUCKETS_CSV.is_file():
        return index
    with BUCKETS_CSV.open(encoding="utf-8", newline="") as f:
        for row in csv.DictReader(f):
            key = row.get("cite_key", "").strip()
            bucket = row.get("bucket_id", "").strip()
            if key and bucket and bucket not in index.setdefault(key, []):
                index[key].append(bucket)
    return index


def paper_buckets(raw: Dict[str, str], bucket_index: Dict[str, List[str]]) -> List[str]:
    ordered: List[str] = []
    for b in [
        raw.get("primary_bucket", ""),
        *raw.get("all_buckets", "").split(";"),
        *bucket_index.get(raw["cite_key"], []),
    ]:
        b = b.strip()
        if b and b not in ordered:
            ordered.append(b)
    return ordered


def is_excluded_domain(raw: Dict[str, str]) -> bool:
    title = (raw.get("title") or "").lower()
    topic = (raw.get("primary_topic") or "").lower()
    focus = (raw.get("focus") or "").lower()
    if any(s in title for s in EXCLUDE_TITLE_SNIPPETS):
        return True
    if any(s in topic for s in EXCLUDE_TOPIC_SNIPPETS):
        return True
    if any(s in focus for s in EXCLUDE_TOPIC_SNIPPETS):
        return True
    return False


REVIEW_VENUE_SNIPPETS = (
    "renewable and sustainable energy reviews",
    "energy conversion and management",
)


MANUAL_TABLE_CELLS: Dict[str, Dict[str, str]] = {
    # PDF-verified surrogate family where the title is silent.
    "Zheng20231907": {"family": "GP / kriging"},
    "Pérez-Uresti2023": {"family": "Neural network"},
}


def is_review_article(title: str, venue: str) -> bool:
    t = title.lower()
    v = (venue or "").lower()
    if any(k in t for k in ("review", "state-of-the-art review", "comprehensive review", "survey")):
        return True
    if any(s in v for s in REVIEW_VENUE_SNIPPETS):
        if any(k in t for k in ("strategies for", "state-of-the-art", "overview of", "literature")):
            return True
        if "review" in v and not any(
            k in t
            for k in (
                "this paper proposes",
                "proposed method",
                "novel approach",
                "framework for",
                "optimization approach",
                "optimization method",
            )
        ):
            return True
    return False


def infer_family(title: str, buckets: List[str], venue: str = "") -> str:
    if "B01_cornerstone_reviews" in buckets:
        return "Review"
    t = title.lower()
    if is_review_article(title, venue):
        return "Review"
    rules = (
        (("gaussian process", "kriging", "gpr", "bayesian framework", "bayesian optimization"), "GP / kriging"),
        (("polynomial chaos", "pce", "response surface", "rsm", "simulation-based optimization"), "PCE / RSM"),
        (("physics-informed", "pinn"), "Hybrid / PINN"),
        (("learning-to-optimize", "learning to optimize", "l2o"), "L2O / decision-focused"),
        (
            (
                "machine learning",
                "data-driven",
                "neural network",
                "deep learning",
                "lstm",
                "cnn",
                "graph neural",
                "metamodel",
                "surrogate model",
                "surrogate optimization",
                "surrogate-assisted",
                "surrogate assisted",
                "surrogate-based",
                "surrogate based",
            ),
            "Neural network",
        ),
        (("support vector", "radial basis", "rbf", "kernel"), "RBF / kernel"),
        (("random forest", "xgboost", "gradient boost", "tree"), "Tree ensembles"),
    )
    for keys, label in rules:
        if any(k in t for k in keys):
            return label
    from_buckets = lookup(buckets, FAMILY_MAP)
    if from_buckets != "--":
        return from_buckets
    if "B23_moo_design" in buckets:
        return "PCE / RSM"
    return "--"


def infer_task(title: str, buckets: List[str]) -> str:
    t = title.lower()
    if "B21_mes_sector_coupling" in buckets or any(
        k in t
        for k in (
            "multi-energy",
            "integrated energy",
            "sector-coupled",
            "electricity-heat",
            "electricity heat",
            "cchp",
            "power-to-x",
            "power to x",
        )
    ):
        return "MES"
    if "B22_microgrid_hub" in buckets or any(
        k in t for k in ("microgrid", "energy hub", "hybrid renewable energy system", "hres")
    ):
        return "Microgrid / hub"
    if "B20_district_heating" in buckets or any(
        k in t for k in ("district heating", "district cooling", "thermal storage", "dh system")
    ):
        return "DH"
    if "B17_ed_uc" in buckets or any(
        k in t
        for k in (
            "unit commitment",
            "economic dispatch",
            "emission dispatch",
            "economic/emission dispatch",
            "security-constrained",
        )
    ):
        return "ED / UC"
    if "B18_opf" in buckets or "optimal power flow" in t or "opf" in t.split():
        return "OPF"
    if "B19_capacity_expansion" in buckets or any(
        k in t for k in ("capacity expansion", "generation expansion", "expansion planning")
    ):
        return "CapEx"
    if "B24_stochastic_robust" in buckets or any(
        k in t
        for k in ("stochastic", "robust optimization", "chance-constrained", "distributionally robust")
    ):
        return "Stoch / robust"
    if "probabilistic load flow" in t or "load flow" in t:
        return "OPF"
    if "network planning" in t or "network of energy models" in t:
        return "CapEx"
    if "capacitor planning" in t or "distribution network" in t:
        return "OPF"
    if "digital technologies" in t or "net-zero energy transition" in t:
        return "Survey"
    if "B23_moo_design" in buckets or any(
        k in t for k in ("multi-objective", "pareto", "nsga")
    ):
        return "MOO design"
    if "wind-farm" in t or "wind farm" in t:
        return "CapEx"
    if "review" in t or "survey" in t:
        return "Survey"
    return "--"


def infer_role(title: str, buckets: List[str], task: str) -> str:
    from_buckets = lookup(buckets, ROLE_MAP)
    if from_buckets != "--":
        return from_buckets
    t = title.lower()
    if any(
        k in t
        for k in (
            "bayesian optimization",
            "surrogate-assisted evolutionary",
            "active learning",
            "nsga",
            "multi-objective",
            "pareto",
        )
    ):
        return "P2"
    if any(
        k in t
        for k in (
            "chance-constrained",
            "uncertainty quantification",
            "polynomial chaos",
            "robust optimization",
            "stochastic",
        )
    ):
        return "P5"
    if any(
        k in t
        for k in (
            "end-to-end",
            "warm start",
            "learning to optimize",
            "learning-to-optimize",
            "optimization proxy",
            "replace",
            "metamodel",
            "surrogate",
        )
    ):
        return "P1/P3"
    if task in {"ED / UC", "OPF"}:
        return "P1"
    if task == "MOO design":
        return "P2"
    if task == "Stoch / robust":
        return "P5"
    if task in {"ED / UC", "OPF", "MES", "DH", "Microgrid / hub", "CapEx", "MOO design"}:
        if any(k in t for k in ("multi-objective", "nsga", "pareto", "bayesian optimization")):
            return "P2"
        if task == "CapEx":
            return "P2"
        if task == "MOO design":
            return "P2"
        return "P1/P3"
    return "--"


def infer_doe(title: str, buckets: List[str], family: str) -> str:
    from_buckets = lookup(buckets, DOE_BUCKET_MAP)
    if from_buckets != "--":
        return from_buckets
    if "B12_bayes_accel" in buckets:
        return "Active learning"
    t = title.lower()
    rules = (
        (("active learning", "acquisition function", "infill criterion"), "Active learning"),
        (("multi-fidelity", "multi fidelity", "co-kriging", "cokriging"), "Multi-fidelity"),
        (("latin hypercube", " lhs ", "sobol", "quasi-monte", "quasi monte"), "LHS / quasi-MC"),
        (
            ("design of experiments", "taguchi", "factorial design", "fractional factorial"),
            "Factorial / DoE",
        ),
        (
            ("adaptive sampling", "sequential design", "kriging-assisted", "kriging assisted"),
            "Adaptive sampling",
        ),
        (("transfer learning",), "Transfer learning"),
        (("iterative design of experiments", "design of experiment"), "Factorial / DoE"),
        (
            ("surrogate-assisted", "surrogate assisted", "surrogate-based optimization"),
            "Adaptive sampling",
        ),
        (("metamodel", "response surface methodology", "response surface method"), "Factorial / DoE"),
    )
    for keys, label in rules:
        if any(k in t for k in keys):
            return label
    if "bayesian optimization" in t and any(
        k in t for k in ("surrogate", "kriging", "gaussian process", "metamodel")
    ):
        return "Active learning"
    if family == "PCE / RSM":
        if any(k in t for k in ("polynomial chaos", "pce", "stochastic", "chance-constrained")):
            return "LHS / quasi-MC"
        return "Factorial / DoE"
    if family == "GP / kriging":
        return "Adaptive sampling"
    if family in {"Neural network", "Tree ensembles", "RBF / kernel"} and "data-driven" in t:
        return "Historical data"
    return "--"


def infer_validation(title: str, buckets: List[str], family: str) -> str:
    if family == "Review":
        return "--"
    if "B16_validation" in buckets:
        return "Validation focus"
    t = title.lower()
    tags: List[str] = []
    if "B15_uncertainty" in buckets or "B24_stochastic_robust" in buckets:
        tags.append("Uncertainty")
    if any(k in t for k in ("regret", "optimality gap", "decision-aware", "decision aware")):
        tags.append("Decision-aware")
    if any(k in t for k in ("out-of-distribution", "out of distribution", " ood ", "policy shift")):
        tags.append("OOD")
    if any(
        k in t
        for k in (
            "feasibility rate",
            "constraint violation",
            "violation severity",
            "feasibility of",
        )
    ):
        tags.append("Feasibility")
    if any(k in t for k in ("stress test", "stress-test", "extreme scenario", "extreme event")):
        tags.append("Stress test")
    if any(
        k in t
        for k in (
            "rmse",
            "mae",
            " r2",
            "r²",
            " r^2",
            "cross-validation",
            "cross validation",
            "test set",
            "testing set",
        )
    ):
        tags.append("Fit metrics")
    if any(k in t for k in ("dynamic validation", "model calibration", "calibration")):
        tags.append("Calibration")
    elif "validation" in t:
        tags.append("Validation")
    if any(k in t for k in ("comparative study", "comparison of", "compared with", "comparative ")):
        tags.append("Fit metrics")
    if any(k in t for k in ("uncertainty quantification", "probabilistic", "prediction interval")):
        if "Uncertainty" not in tags:
            tags.append("Uncertainty")
    if not tags and any(
        k in t for k in ("surrogate", "metamodel", "kriging", "emulator", "response surface")
    ):
        if any(
            k in t
            for k in (
                "optimization",
                "dispatch",
                "opf",
                "planning",
                "scheduling",
                "expansion",
                "microgrid",
            )
        ):
            tags.append("Fit metrics")
    if not tags:
        return "--"
    display = {
        "Fit metrics": "Point metrics (RMSE/MAE/R²)",
        "Feasibility": "Feasibility rate",
        "Decision-aware": "Decision-aware (regret/gap)",
        "Validation": "Point metrics (RMSE/MAE/R²)",
        "Uncertainty": "Uncertainty (problem UQ)",
        "Calibration": "Interval calibration",
        "Stress test": "Stress test",
        "OOD": "OOD / policy shift",
    }
    seen: Set[str] = set()
    ordered: List[str] = []
    for tag in tags:
        if tag in seen:
            continue
        seen.add(tag)
        label = display.get(tag, tag)
        if label in ordered:
            continue
        ordered.append(label)
    return "; ".join(ordered[:3])


def default_role(family: str, task: str) -> str:
    if family == "Review" or task == "Survey":
        return "P1/P3"
    if task in {"ED / UC", "OPF", "MES", "DH", "Microgrid / hub"}:
        return "P1/P3"
    if task == "CapEx":
        return "P2"
    if task == "MOO design":
        return "P2"
    if task == "Stoch / robust":
        return "P5"
    return "--"


def topic_cell(raw: Dict[str, str]) -> str:
    topic = (raw.get("primary_topic") or "").strip()
    if topic:
        return re.sub(r"\s+", " ", topic)
    title = (raw.get("title") or "").strip()
    if title:
        return re.sub(r"\s+", " ", title)
    return "--"


def is_review_paper(raw: Dict[str, str], bucket_index: Dict[str, List[str]]) -> bool:
    buckets = paper_buckets(raw, bucket_index)
    if "B01_cornerstone_reviews" in buckets:
        return True
    title = raw.get("title") or ""
    venue = raw.get("venue") or ""
    return is_review_article(title, venue)


_ESCAPES: List[Tuple[str, str]] = [
    ("\\", r"\textbackslash{}"),
    ("&", r"\&"),
    ("%", r"\%"),
    ("$", r"\$"),
    ("#", r"\#"),
    ("_", r"\_"),
    ("{", r"\{"),
    ("}", r"\}"),
    ("~", r"\textasciitilde{}"),
    ("^", r"\textasciicircum{}"),
]


def latex_escape(text: str) -> str:
    out = text or ""
    for src, dst in _ESCAPES:
        out = out.replace(src, dst)
    return out


def truncate(text: str, max_len: int) -> str:
    s = re.sub(r"\s+", " ", (text or "")).strip()
    if len(s) <= max_len:
        return s
    return s[: max_len - 1].rstrip() + "\u2026"


def cite_keys_from_tex(path: Path) -> Set[str]:
    if not path.is_file():
        return set()
    text = path.read_text(encoding="utf-8")
    return {
        k.strip()
        for m in re.finditer(r"\\cite\{([^}]+)\}", text)
        for k in m.group(1).split(",")
        if k.strip()
    }


def compact_score(
    raw: Dict[str, str], mandatory: Set[str], bucket_index: Dict[str, List[str]]
) -> int:
    if is_excluded_domain(raw):
        return -1
    if is_review_paper(raw, bucket_index):
        return -1
    key = raw["cite_key"]
    buckets = set(paper_buckets(raw, bucket_index))
    title = (raw.get("title") or "").lower()
    sources = (raw.get("sources") or "").lower()
    cites = int(raw["cited_by_count"]) if str(raw.get("cited_by_count", "")).isdigit() else 0
    task_hits = buckets & MES_TASK_BUCKETS

    if any(s in title for s in EXCLUDE_TITLE_SNIPPETS):
        return -1
    if key in mandatory:
        return 10_000 + cites
    if buckets & CORE_SYSTEM_BUCKETS:
        return 8_000 + cites
    if "B21_mes_sector_coupling" in buckets or "moo_mes_focus" in sources:
        return 7_000 + cites
    if "B22_microgrid_hub" in buckets:
        return 6_000 + cites
    if "B23_moo_design" in buckets and any(h in title for h in MOO_MES_TITLE_HINTS):
        return 6_500 + cites
    if task_hits & {"B17_ed_uc", "B18_opf"}:
        return 5_000 + cites
    if task_hits & {"B19_capacity_expansion", "B24_stochastic_robust"}:
        return 4_500 + cites
    return -1


def select_compact_rows(
    raw_rows: Sequence[Dict[str, str]],
    mandatory: Set[str],
    bucket_index: Dict[str, List[str]],
) -> List[Dict[str, str]]:
    scored = [(compact_score(r, mandatory, bucket_index), r) for r in raw_rows]
    eligible = [
        (s, r) for s, r in scored if s >= 0 and not is_review_paper(r, bucket_index)
    ]
    eligible.sort(key=lambda x: (-x[0], -int(x[1]["year"]), -int(x[1]["cited_by_count"] or 0), x[1]["cite_key"]))

    pool_size = COMPACT_TARGET + 30
    selected: List[Dict[str, str]] = [r for _, r in eligible[:pool_size]]
    selected_keys = {r["cite_key"] for r in selected}

    for _, r in eligible:
        if r["cite_key"] in mandatory and r["cite_key"] not in selected_keys:
            if is_review_paper(r, bucket_index):
                continue
            selected.append(r)
            selected_keys.add(r["cite_key"])

    return selected


def load_pdf_paths_by_key() -> Dict[str, Path]:
    """First mapped Literatur PDF path per cite key (from match_literatur run)."""
    if not PDF_MATCH_MAP.is_file():
        return {}
    paths: Dict[str, Path] = {}
    with PDF_MATCH_MAP.open(encoding="utf-8", newline="") as f:
        for row in csv.DictReader(f):
            key = (row.get("mapped_key") or "").strip()
            rel = (row.get("pdf_relpath") or "").strip().replace("\\", "/")
            if not key or key in paths or not rel:
                continue
            pdf = LITERATUR_ROOT / rel
            if pdf.is_file():
                paths[key] = pdf
    return paths


def extract_pdf_text(pdf: Path, max_pages: int = PDF_EXTRACT_PAGES) -> str:
    if not pdf.is_file():
        return ""
    try:
        import fitz  # type: ignore

        with fitz.open(str(pdf)) as doc:
            n = min(len(doc), max(1, max_pages))
            return "\n".join(doc[i].get_text() for i in range(n))
    except Exception:
        pass
    try:
        from pypdf import PdfReader

        reader = PdfReader(str(pdf))
        n = min(len(reader.pages), max(1, max_pages))
        return "\n".join((reader.pages[i].extract_text() or "") for i in range(n))
    except Exception:
        return ""


def build_pdf_text_index(keys: Set[str], pdf_paths: Dict[str, Path]) -> Dict[str, str]:
    index: Dict[str, str] = {}
    for key in keys:
        pdf = pdf_paths.get(key)
        if not pdf:
            continue
        text = extract_pdf_text(pdf)
        if text.strip():
            index[key] = text
    return index


def inference_blob(
    raw: Dict[str, str], pdf_text_index: Dict[str, str]
) -> str:
    title = raw.get("title") or ""
    snippet = pdf_text_index.get(raw["cite_key"], "")
    if not snippet:
        return title
    return f"{title}\n{snippet[:40000]}"


def manifest_row_to_table_row(
    raw: Dict[str, str],
    bucket_index: Dict[str, List[str]],
    pdf_text_index: Dict[str, str] | None = None,
) -> Dict[str, str]:
    buckets = paper_buckets(raw, bucket_index)
    family = lookup(buckets, FAMILY_MAP)
    title = raw.get("title") or ""
    venue = raw.get("venue") or ""
    blob = inference_blob(raw, pdf_text_index or {})

    # Surrogate class: title/venue/buckets only (PDF back-matter mentions "review").
    if family == "--":
        family = infer_family(title, buckets, venue)

    manual = MANUAL_TABLE_CELLS.get(raw["cite_key"], {})
    family = manual.get("family", family)
    doe = manual.get("doe", infer_doe(blob, buckets, family))
    validation = manual.get("validation", infer_validation(blob, buckets, family))

    return {
        "key": raw["cite_key"],
        "year": raw.get("year", ""),
        "topic": topic_cell(raw),
        "family": family,
        "doe": doe,
        "validation": validation,
    }


def is_table_excluded_row(row: Dict[str, str], raw: Dict[str, str], bucket_index: Dict[str, List[str]]) -> bool:
    if row["family"] == "Review":
        return True
    title = raw.get("title") or ""
    buckets = paper_buckets(raw, bucket_index)
    if infer_task(title, buckets) == "Survey":
        return True
    return False


def render_row_line(r: Dict[str, str]) -> str:
    cite = "\\cite{" + r["key"] + "}"
    topic = latex_escape(r["topic"]) if r["topic"] else "--"
    return (
        f"{cite} & {latex_escape(r['year'])} & {topic} & "
        f"{latex_escape(r['family'])} & {latex_escape(r['doe'])} & "
        f"{latex_escape(r['validation'])} \\\\"
    )


def render_longtable(rows: Sequence[Dict[str, str]], mode: str, caption: str) -> str:
    body = "\n".join(f"  {render_row_line(r)}" for r in rows)
    return (
        "% T6 evidence-map longtable. Rows: tables/build_table_T6_evidence_map.py\n"
        "% (writes this file and a synced copy under tables/table_T6_evidence_map.tex).\n"
        f"% {len(rows)} entries; mode={mode}; rebuild via build_table_T6_evidence_map.py\n"
        rf"\begin{{longtable}}{{{LONGTABLE_COLSPEC}}}"
        "\n"
        f"{caption}\n"
        r"  \label{tab:T6-evidence-map} \\"
        "\n"
        r"  \toprule"
        "\n"
        f"  {LONGTABLE_HEADER}\n"
        r"  \midrule"
        "\n"
        r"  \endfirsthead"
        "\n"
        "\n"
        r"  \toprule"
        "\n"
        f"  {LONGTABLE_HEADER}\n"
        r"  \midrule"
        "\n"
        r"  \endhead"
        "\n"
        "\n"
        r"  \bottomrule"
        "\n"
        r"  \endfoot"
        "\n"
        "\n"
        f"{body}\n"
        r"\end{longtable}"
        "\n"
    )


def write_compact_manifest(raw_rows: Sequence[Dict[str, str]]) -> None:
    if not raw_rows:
        return
    fieldnames = list(raw_rows[0].keys())
    with OUT_COMPACT_MANIFEST.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        w.writerows(raw_rows)


def main() -> int:
    parser = argparse.ArgumentParser(description="Build T6 evidence-map longtable")
    parser.add_argument(
        "--mode",
        choices=("compact", "full"),
        default="compact",
        help="compact = MES-focused subset for Section 8 (default); full = all manifest rows",
    )
    args = parser.parse_args()

    if not MANIFEST.exists():
        raise SystemExit(f"manifest missing: {MANIFEST}")

    raw_rows: List[Dict[str, str]] = []
    with MANIFEST.open(newline="", encoding="utf-8") as f:
        raw_rows.extend(csv.DictReader(f))

    bucket_index = load_bucket_index()
    mandatory = cite_keys_from_tex(APPLICATIONS_TEX)
    pdf_paths = load_pdf_paths_by_key()

    if args.mode == "compact":
        raw_selected = select_compact_rows(raw_rows, mandatory, bucket_index)
        write_compact_manifest(raw_selected)
        caption = COMPACT_CAPTION
    else:
        raw_selected = raw_rows
        caption = FULL_CAPTION

    candidate_keys = {r["cite_key"] for r in raw_selected}
    if args.mode == "compact":
        candidate_keys |= mandatory
    pdf_text_index = build_pdf_text_index(candidate_keys, pdf_paths)

    table_rows: List[Dict[str, str]] = []
    used_keys: Set[str] = set()
    for r in raw_selected:
        row = manifest_row_to_table_row(r, bucket_index, pdf_text_index)
        if is_table_excluded_row(row, r, bucket_index):
            continue
        if row["key"] in used_keys:
            continue
        table_rows.append(row)
        used_keys.add(row["key"])
        if args.mode == "compact" and len(table_rows) >= COMPACT_TARGET:
            break

    if args.mode == "compact" and len(table_rows) < COMPACT_TARGET:
        scored = [
            (compact_score(r, mandatory, bucket_index), r)
            for r in raw_rows
            if r["cite_key"] not in used_keys
        ]
        extra = [
            r
            for s, r in sorted(scored, key=lambda x: -x[0])
            if s >= 0 and not is_review_paper(r, bucket_index)
        ]
        for r in extra:
            row = manifest_row_to_table_row(r, bucket_index, pdf_text_index)
            if is_table_excluded_row(row, r, bucket_index):
                continue
            table_rows.append(row)
            used_keys.add(row["key"])
            if len(table_rows) >= COMPACT_TARGET:
                break

    def sort_key(r: Dict[str, str]) -> Tuple[int, str]:
        y = int(r["year"]) if r["year"].isdigit() else 0
        return (-y, r["key"])

    table_rows.sort(key=sort_key)
    new_tex = render_longtable(table_rows, args.mode, caption)

    OUT_APPENDIX.parent.mkdir(parents=True, exist_ok=True)
    OUT_APPENDIX.write_text(new_tex, encoding="utf-8")
    OUT_TABLES_LEGACY.write_text(new_tex, encoding="utf-8")
    print(
        f"wrote {len(table_rows)} rows ({args.mode}) longtable to "
        f"{OUT_APPENDIX.relative_to(ROOT)}"
    )
    if args.mode == "compact":
        print(f"wrote compact manifest to {OUT_COMPACT_MANIFEST.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
