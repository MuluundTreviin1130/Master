"""Build one evidence table for all quantitative review-paper figures.

The runner extracts each available article PDF once, caches page text, and
audits all dimensions required by the taxonomy, DoE, alluvial, and validation
figures. Multi-label dimensions remain multi-label. Every accepted assignment
retains its evidence source, PDF page where available, and a compact snippet.

Use ``--smoke N`` for a deterministic representative subset. The smoke path
uses the same extraction, classifiers, cache, and output schema as the full
overnight run.
"""

from __future__ import annotations

import argparse
import csv
import json
import re
import time
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Dict, Iterable, Sequence, Tuple

from build_alluvial_evidence_audit import (
    FAMILY_ORDER,
    FAMILY_PATTERNS,
    PATTERN_ORDER,
    PATTERN_PATTERNS,
    REVIEW_RE,
    VALIDATION_PATTERNS,
    VALIDATION_PRIORITY,
)
from build_doe_evidence_audit import (
    SOURCE_ORDER,
    SOURCE_PATTERNS,
    STRATEGY_ORDER,
    STRATEGY_PATTERNS,
)
from build_surrogate_target_audit import (
    TARGET_ORDER,
    TARGET_PATTERNS,
    load_bib_text,
    load_pdf_paths,
)


ROOT = Path(__file__).resolve().parent.parent
MANIFEST = ROOT / "paper_library" / "review_paper_library_manifest.csv"
MANUAL = ROOT / "paper_library" / "alluvial_manual_adjudication.csv"
FOLLOWUP_WIDE = ROOT / "paper_library" / "alluvial_evidence_audit_followup.csv"
TARGETED_MANUAL = ROOT / "paper_library" / "unified_targeted_manual_adjudication.csv"
CACHE = ROOT / "paper_library" / "cache" / "unified_pdf_text"
HYBRID_WORKFLOW_KEYS = {
    "Sánchez-Zabala2024",
    "Reich2020",
    "Jalving2023",
    "Dong2023",
    "Yin2024",
}

TRUST_ORDER = (
    "Predictive-error based",
    "Posterior uncertainty",
    "Physics-guided",
    "Structure-preserving / solver-compatible",
    "Decision-oriented",
)
TRUST_PATTERNS: Dict[str, Tuple[Tuple[str, int], ...]] = {
    "Predictive-error based": (
        (r"\broot mean squared error\b", 8),
        (r"\bmean absolute error\b", 8),
        (r"\b(?:rmse|nrmse|mae|mape|r[- ]?squared)\b", 7),
        (r"\bprediction accuracy\b", 7),
    ),
    "Posterior uncertainty": (
        (r"\bposterior (?:variance|uncertainty|distribution)\b", 9),
        (r"\bpredictive (?:variance|uncertainty|distribution)\b", 9),
        (r"\bacquisition function\b", 8),
        (r"\bexpected improvement\b", 8),
        (r"\bcredible interval\b", 8),
    ),
    "Physics-guided": (
        (r"\bphysics[- ](?:informed|guided|induced)\b", 10),
        (r"\bphysical residual(?:s)?\b", 9),
        (r"\b(?:power|heat|mass|energy) balance residual(?:s)?\b", 9),
        (r"\bphysics[- ]based loss\b", 9),
    ),
    "Structure-preserving / solver-compatible": (
        (r"\bstructure[- ]preserving\b", 10),
        (r"\bconstraint[- ]aware\b", 10),
        (r"\bfeasibility[- ]preserving\b", 10),
        (r"\binput[- ]convex neural network\b", 10),
        (r"\bmonotone neural network\b", 10),
        (r"\bmixed[- ]integer compatible\b", 9),
        (r"\b(?:milp|mip)[- ]compatible\b", 9),
        (r"\bembedded (?:as|in).{0,80}\b(?:milp|mixed[- ]integer)\b", 9),
    ),
    "Decision-oriented": (
        (r"\bdecision[- ]focused\b", 10),
        (r"\blearning[- ]to[- ]optimi[sz]e\b", 10),
        (r"\boptimality gap\b", 9),
        (r"\bdecision quality\b", 9),
        (r"\bregret\b", 9),
        (r"\bcost gap\b", 9),
    ),
}

UNIFIED_SOURCE_PATTERNS: Dict[str, Tuple[Tuple[str, int], ...]] = {
    "Synthetic data": (
        *SOURCE_PATTERNS["Synthetic data"],
        (r"\bdataset(?:s)?\s+(?:containing|with)\s+\d[\d,\.]*\s+samples\b", 7),
        (r"\b(?:dataset|training set)\s+(?:is|was)\s+(?:constructed|built|created)\s+from\s+(?:repeated\s+)?(?:simulation|simulations|simulator runs|optimization runs|solver runs)\b", 8),
        (r"\b(?:training|input|output)\s+data\s+(?:are|were|is|was)\s+obtained\s+by\s+(?:solving|running|evaluating)\b", 8),
        (r"\b(?:evaluate|evaluated|evaluating)\s+each\s+(?:candidate|sample|scenario)\s+with\s+(?:the\s+)?(?:full|high[- ]fidelity)\s+(?:model|simulation|solver)\b", 8),
        (r"\b(?:simulation|simulator)\s+results?\s+(?:are|were|is|was)\s+used\s+as\s+training data\b", 8),
        (r"\b(?:monte carlo|latin hypercube|sobol|halton).{0,140}\b(?:generate|generated|obtain|obtained).{0,140}\btraining (?:set|data)\b", 7),
    ),
    "Historical data": (
        *SOURCE_PATTERNS["Historical data"],
        (r"\blocal historical data\b", 8),
        (r"\bactual (?:load|wind|solar|pv|operation|operational|measurement)s?\b", 7),
        (r"\bonsite (?:test|tests|measurement|measurements|data)\b", 7),
        (r"\brecorded (?:operation|operational|measurement|measurements|data)\b", 8),
        (r"\btime[- ]series data\b", 6),
        (r"\bmeasured (?:load|wind|speed|power|temperature|irradiation|generation)\b", 7),
        (r"\btraining (?:set|data)\s+(?:comes|come|came|is|was)\s+from\s+(?:historical|measured|recorded|operational)\b", 8),
        (r"\bused\s+(?:historical|measured|recorded|operational)\s+data\s+for\s+(?:training|testing|validation)\b", 8),
    ),
    "Hybrid data": SOURCE_PATTERNS["Hybrid data"],
}

DIMENSION_PATTERNS = {
    "family": (FAMILY_ORDER, FAMILY_PATTERNS, False),
    "target": (TARGET_ORDER, TARGET_PATTERNS, True),
    "trust": (TRUST_ORDER, TRUST_PATTERNS, True),
    "data_source": (SOURCE_ORDER, UNIFIED_SOURCE_PATTERNS, True),
    "doe_strategy": (STRATEGY_ORDER, STRATEGY_PATTERNS, True),
    "pattern": (PATTERN_ORDER, PATTERN_PATTERNS, False),
    "validation": (VALIDATION_PRIORITY, VALIDATION_PATTERNS, True),
}

FOCAL_SIGNAL = re.compile(
    r"\b(we (?:use|used|employ|employed|develop|developed|propose|proposed|"
    r"train|trained|construct|constructed|generate|generated|evaluate|evaluated|"
    r"validate|validated)|our (?:model|method|approach|framework|surrogate|"
    r"study|results|experiments)|this (?:paper|study|work|article)|"
    r"the proposed (?:model|method|approach|framework|algorithm|surrogate))\b",
    re.IGNORECASE,
)
VALIDATION_SIGNAL = re.compile(
    r"\b(results?|validation|evaluation|performance|accuracy|test set|"
    r"out[- ]of[- ]sample|comparison|error|feasibility|calibration|table|fig(?:ure)?\.?)\b",
    re.IGNORECASE,
)
TRAINING_SIGNAL = re.compile(
    r"\b(training (?:data|set|samples)|dataset generation|data generation|"
    r"design points|sample points|initial design|sampling strategy|"
    r"simulations?|measurements?|historical data)\b",
    re.IGNORECASE,
)
RELATED_WORK_SIGNAL = re.compile(
    r"(?:\b(previous studies|prior studies|earlier studies|other studies|"
    r"existing studies|literature review|related work|researchers have|"
    r"authors have)\b|\bet al\.)",
    re.IGNORECASE,
)
SURROGATE_SIGNAL = re.compile(
    r"\b(surrogate|metamodel|emulator|proxy|response surface|kriging|"
    r"gaussian process|neural network|random forest|gradient boosting|"
    r"support vector|radial basis|polynomial chaos|approximat(?:e|ion|ing)|"
    r"predict(?:s|ed|ing|ion)|learn(?:s|ed|ing))\b",
    re.IGNORECASE,
)
RESULT_SIGNAL = re.compile(
    r"\b(results?|table|fig(?:ure)?\.?)\b.{0,140}\b"
    r"(show|shows|shown|demonstrate|demonstrates|report|reports|achiev|obtain)",
    re.IGNORECASE,
)
NUMERIC_EVIDENCE = re.compile(
    r"\b(?:rmse|nrmse|mae|mape|r[- ]?squared|error|accuracy|gap|regret|"
    r"violation|coverage)\b.{0,80}(?:\d+(?:\.\d+)?\s*%|\d+\.\d+)",
    re.IGNORECASE,
)
REFERENCE_HEADING = re.compile(
    r"(?im)^\s*(references|bibliography|literature cited)\s*$"
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--smoke",
        type=int,
        default=0,
        metavar="N",
        help="Audit a deterministic representative subset of N studies.",
    )
    parser.add_argument("--max-pages", type=int, default=35)
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument(
        "--refresh-cache",
        action="store_true",
        help="Ignore matching cached PDF page text.",
    )
    return parser.parse_args()


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def compact(text: str) -> str:
    return re.sub(r"\s+", " ", text or "").strip()


def cache_path(key: str) -> Path:
    safe = re.sub(r"[^A-Za-z0-9_.-]+", "_", key)
    return CACHE / f"{safe}.json"


def extract_pdf_pages(pdf: Path, max_pages: int) -> list[dict[str, object]]:
    """Extract page text, stopping when a conventional reference section starts."""
    pages: list[dict[str, object]] = []
    try:
        import fitz  # type: ignore

        with fitz.open(str(pdf)) as document:
            for index in range(min(len(document), max_pages)):
                text = document[index].get_text() or ""
                if index >= 2 and REFERENCE_HEADING.search(text[:2500]):
                    break
                if text.strip():
                    pages.append({"page": index + 1, "text": text})
        return pages
    except Exception:
        pass

    from pypdf import PdfReader

    reader = PdfReader(str(pdf))
    for index, page in enumerate(reader.pages[:max_pages]):
        text = page.extract_text() or ""
        if index >= 2 and REFERENCE_HEADING.search(text[:2500]):
            break
        if text.strip():
            pages.append({"page": index + 1, "text": text})
    return pages


def load_or_extract(
    key: str,
    pdf: Path,
    max_pages: int,
    refresh: bool,
) -> tuple[list[dict[str, object]], bool, float]:
    """Return pages, whether cache was used, and extraction duration."""
    target = cache_path(key)
    stat = pdf.stat()
    if target.is_file() and not refresh:
        payload = json.loads(target.read_text(encoding="utf-8"))
        if (
            payload.get("pdf_path") == str(pdf)
            and payload.get("pdf_size") == stat.st_size
            and payload.get("pdf_mtime_ns") == stat.st_mtime_ns
            and payload.get("max_pages") == max_pages
        ):
            return payload.get("pages", []), True, 0.0

    started = time.perf_counter()
    pages = extract_pdf_pages(pdf, max_pages)
    duration = time.perf_counter() - started
    CACHE.mkdir(parents=True, exist_ok=True)
    payload = {
        "cite_key": key,
        "pdf_path": str(pdf),
        "pdf_size": stat.st_size,
        "pdf_mtime_ns": stat.st_mtime_ns,
        "max_pages": max_pages,
        "pages": pages,
    }
    target.write_text(
        json.dumps(payload, ensure_ascii=True),
        encoding="utf-8",
    )
    return pages, False, duration


def representative_subset(
    rows: list[dict[str, str]],
    pdf_paths: dict[str, Path],
    limit: int,
) -> list[dict[str, str]]:
    """Cover distinct primary buckets first, then fill deterministically."""
    if limit <= 0 or limit >= len(rows):
        return rows
    selected: list[dict[str, str]] = []
    used: set[str] = set()

    # PDF-backed studies dominate the smoke run because extraction determines
    # runtime. Distinct buckets keep the classification paths heterogeneous.
    for require_pdf in (True, False):
        seen_buckets: set[str] = set()
        for row in rows:
            key = row["cite_key"]
            has_pdf = key in pdf_paths
            if has_pdf != require_pdf:
                continue
            bucket = row.get("primary_bucket", "")
            if bucket in seen_buckets or key in used:
                continue
            selected.append(row)
            used.add(key)
            seen_buckets.add(bucket)
            if len(selected) == limit:
                return selected

    for row in rows:
        if row["cite_key"] not in used:
            selected.append(row)
            used.add(row["cite_key"])
            if len(selected) == limit:
                break
    return selected


def best_pattern_hit(
    text: str,
    patterns: Iterable[Tuple[str, int]],
) -> tuple[int, str]:
    best_weight = 0
    best_snippet = ""
    for pattern, weight in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if not match or weight < best_weight:
            continue
        start = max(0, match.start() - 180)
        end = min(len(text), match.end() + 260)
        best_weight = weight
        best_snippet = compact(text[start:end])
    return best_weight, best_snippet


def pdf_context_is_focal(dimension: str, snippet: str) -> bool:
    # A citation-bearing passage is rejected unless the focal-study signal
    # occurs before the evidence phrase. This avoids accepting "X et al.
    # proposed ..." descriptions merely because the cited method itself is
    # called "the proposed model" later in the same window.
    related = RELATED_WORK_SIGNAL.search(snippet)
    focal = FOCAL_SIGNAL.search(snippet)
    if related and (not focal or related.start() <= focal.start()):
        return False
    if focal:
        return True
    if dimension == "validation":
        return bool(
            VALIDATION_SIGNAL.search(snippet)
            and (RESULT_SIGNAL.search(snippet) or NUMERIC_EVIDENCE.search(snippet))
        )
    if dimension in {"data_source", "doe_strategy"}:
        return bool(TRAINING_SIGNAL.search(snippet))
    return False


def source_context_is_valid(
    dimension: str,
    source: str,
    snippet: str,
) -> bool:
    """Apply dimension-specific context requirements before accepting a hit."""
    if dimension == "target":
        return bool(SURROGATE_SIGNAL.search(snippet))
    if dimension == "validation":
        # A method named in a title is not evidence that the focal study
        # validated it. Abstract evidence must describe evaluation/results.
        if source in {"title", "keywords"}:
            return False
        return bool(
            VALIDATION_SIGNAL.search(snippet)
            and (
                FOCAL_SIGNAL.search(snippet)
                or RESULT_SIGNAL.search(snippet)
                or NUMERIC_EVIDENCE.search(snippet)
            )
        )
    return True


def evidence_for_label(
    dimension: str,
    patterns: Sequence[Tuple[str, int]],
    title: str,
    abstract: str,
    keywords: str,
    pages: list[dict[str, object]],
) -> dict[str, str] | None:
    """Return the strongest explicit focal-study evidence for one label."""
    candidates: list[tuple[int, int, dict[str, str]]] = []
    for source, text, source_rank in (
        ("title", title, 4),
        ("abstract", abstract, 3),
        ("keywords", keywords, 2),
    ):
        weight, snippet = best_pattern_hit(text, patterns)
        if weight and source_context_is_valid(dimension, source, snippet):
            candidates.append(
                (
                    source_rank,
                    weight,
                    {
                        "source": source,
                        "page": "",
                        "snippet": snippet,
                        "weight": str(weight),
                    },
                )
            )

    for page in pages:
        text = str(page["text"])
        weight, snippet = best_pattern_hit(text, patterns)
        if (
            not weight
            or not source_context_is_valid(dimension, "pdf", snippet)
            or not pdf_context_is_focal(dimension, snippet)
        ):
            continue
        candidates.append(
            (
                1,
                weight,
                {
                    "source": "pdf",
                    "page": str(page["page"]),
                    "snippet": snippet,
                    "weight": str(weight),
                },
            )
        )

    if not candidates:
        return None
    _, _, result = max(candidates, key=lambda value: (value[0], value[1]))
    return result


def classify_study(
    row: dict[str, str],
    bib_row: dict[str, str],
    pages: list[dict[str, object]],
) -> list[dict[str, str]]:
    title = bib_row.get("title") or row.get("title", "")
    abstract = bib_row.get("abstract", "")
    keywords = bib_row.get("keywords", "")
    accepted: list[dict[str, str]] = []

    for dimension, (order, patterns_by_label, multi_label) in (
        DIMENSION_PATTERNS.items()
    ):
        candidates = []
        for label in order:
            evidence = evidence_for_label(
                dimension,
                patterns_by_label[label],
                title,
                abstract,
                keywords,
                pages,
            )
            if evidence:
                candidates.append((label, evidence))
        if not multi_label and candidates:
            source_rank = {"title": 4, "abstract": 3, "keywords": 2, "pdf": 1}
            candidates = [
                max(
                    candidates,
                    key=lambda value: (
                        source_rank[value[1]["source"]],
                        int(value[1]["weight"]),
                    ),
                )
            ]
        for label, evidence in candidates:
            accepted.append(
                {
                    "cite_key": row["cite_key"],
                    "dimension": dimension,
                    "label": label,
                    "confidence": "high",
                    "evidence_source": evidence["source"],
                    "page": evidence["page"],
                    "evidence_snippet": evidence["snippet"],
                    "evidence_weight": evidence["weight"],
                    "adjudication": "automatic",
                }
            )
    return accepted


def merge_manual(
    labels: list[dict[str, str]],
    selected_keys: set[str],
) -> list[dict[str, str]]:
    if not MANUAL.is_file():
        return labels
    dimension_map = {
        "family": "family",
        "pattern": "pattern",
        "validation": "validation",
    }
    label_map = {
        "Simulation-generated data": "Synthetic data",
        "Historical operational data": "Historical data",
        "Hybrid approaches": "Hybrid data",
    }
    allowed = {
        dimension: set(order)
        for dimension, (order, _, _) in DIMENSION_PATTERNS.items()
    }
    indexed = {
        (row["cite_key"], row["dimension"], row["label"]): row
        for row in labels
    }
    for row in read_csv(MANUAL):
        key = row["cite_key"]
        if key not in selected_keys:
            continue
        old_dimension = row["dimension"]
        label = label_map.get(row["label"], row["label"])
        if old_dimension == "doe":
            dimension = (
                "doe_strategy"
                if label in allowed["doe_strategy"]
                else "data_source"
            )
        else:
            dimension = dimension_map.get(old_dimension, old_dimension)
        if dimension not in allowed or label not in allowed[dimension]:
            raise ValueError(
                f"Unsupported manual assignment: {key} {dimension} {label}"
            )
        indexed[(key, dimension, label)] = {
            "cite_key": key,
            "dimension": dimension,
            "label": label,
            "confidence": "high",
            "evidence_source": row["evidence_source"],
            "page": row["page"],
            "evidence_snippet": row["evidence_snippet"],
            "evidence_weight": "manual",
            "adjudication": "manual",
        }
    return sorted(
        indexed.values(),
        key=lambda value: (
            value["cite_key"],
            value["dimension"],
            value["label"],
        ),
    )


def merge_followup_wide(
    labels: list[dict[str, str]],
    selected_keys: set[str],
) -> list[dict[str, str]]:
    """Merge existing wide follow-up adjudications into the unified label table.

    The follow-up file already contains high-confidence assignments from a
    broader manual/semi-manual review pass. Reusing those adjudications keeps
    the unified audit as the SSOT while avoiding a second divergent truth
    table for Sankey and DoE figures.
    """
    if not FOLLOWUP_WIDE.is_file():
        return labels

    allowed = {
        dimension: set(order)
        for dimension, (order, _, _) in DIMENSION_PATTERNS.items()
    }
    label_map = {
        "Simulation-generated data": "Synthetic data",
        "Historical operational data": "Historical data",
        "Hybrid approaches": "Hybrid data",
    }
    indexed = {
        (row["cite_key"], row["dimension"], row["label"]): row
        for row in labels
    }
    dimension_columns = {
        "family": "family",
        "doe": "doe",
        "pattern": "pattern",
        "validation": "validation",
    }
    for row in read_csv(FOLLOWUP_WIDE):
        key = row["cite_key"]
        if key not in selected_keys:
            continue
        for old_dimension, column in dimension_columns.items():
            confidence = row.get(f"{column}_confidence", "")
            label = label_map.get(row.get(column, ""), row.get(column, ""))
            if confidence != "high" or not label:
                continue
            if old_dimension == "doe":
                dimension = (
                    "doe_strategy"
                    if label in allowed["doe_strategy"]
                    else "data_source"
                )
            else:
                dimension = old_dimension
            if dimension not in allowed or label not in allowed[dimension]:
                continue
            indexed[(key, dimension, label)] = {
                "cite_key": key,
                "dimension": dimension,
                "label": label,
                "confidence": "high",
                "evidence_source": row.get(f"{column}_evidence_source", "")
                or "followup",
                "page": "",
                "evidence_snippet": row.get(f"{column}_evidence_snippet", ""),
                "evidence_weight": row.get(f"{column}_score", "") or "followup",
                "adjudication": "followup wide audit",
            }
    return sorted(
        indexed.values(),
        key=lambda value: (
            value["cite_key"],
            value["dimension"],
            value["label"],
        ),
    )


def merge_targeted_manual(
    labels: list[dict[str, str]],
    selected_keys: set[str],
) -> list[dict[str, str]]:
    """Merge exact-dimension targeted manual adjudications."""
    if not TARGETED_MANUAL.is_file():
        return labels

    allowed = {
        dimension: set(order)
        for dimension, (order, _, _) in DIMENSION_PATTERNS.items()
    }
    indexed = {
        (row["cite_key"], row["dimension"], row["label"]): row
        for row in labels
    }
    for row in read_csv(TARGETED_MANUAL):
        key = row["cite_key"]
        dimension = row["dimension"]
        label = row["label"]
        if key not in selected_keys:
            continue
        if dimension not in allowed or label not in allowed[dimension]:
            raise ValueError(
                f"Unsupported targeted manual assignment: {key} {dimension} {label}"
            )
        indexed[(key, dimension, label)] = {
            "cite_key": key,
            "dimension": dimension,
            "label": label,
            "confidence": "high",
            "evidence_source": row.get("evidence_source", ""),
            "page": row.get("page", ""),
            "evidence_snippet": row.get("evidence_snippet", ""),
            "evidence_weight": "manual",
            "adjudication": "targeted manual followup",
        }
    return sorted(
        indexed.values(),
        key=lambda value: (
            value["cite_key"],
            value["dimension"],
            value["label"],
        ),
    )


def derive_evidence_equivalents(
    labels: list[dict[str, str]],
) -> list[dict[str, str]]:
    """Reuse one accepted passage where two manuscript labels are equivalent.

    Reporting RMSE/MAE/R2 is both a point-metric validation practice and the
    manuscript's predictive-error-based trust mechanism. Reusing that exact
    passage increases coverage without introducing a new inference source.
    """
    indexed = {
        (row["cite_key"], row["dimension"], row["label"]): row
        for row in labels
    }
    for row in list(labels):
        if row["dimension"] != "validation" or row["label"] != "Point metrics":
            continue
        key = (row["cite_key"], "trust", "Predictive-error based")
        if key in indexed:
            continue
        indexed[key] = {
            **row,
            "dimension": "trust",
            "label": "Predictive-error based",
            "adjudication": "derived from identical point-metric evidence",
        }
    return sorted(
        indexed.values(),
        key=lambda value: (
            value["cite_key"],
            value["dimension"],
            value["label"],
        ),
    )


def derive_workflow_context(
    cite_key: str,
    data_source_labels: Sequence[str],
) -> str:
    labels = set(data_source_labels)
    if cite_key in HYBRID_WORKFLOW_KEYS:
        return "Hybrid model-coupled workflow"
    if labels == {"Historical data", "Synthetic data"}:
        return "Hybrid model-coupled workflow"
    if labels == {"Synthetic data"}:
        return "Simulation-driven workflow"
    if labels == {"Historical data"}:
        return "Historical-data-driven workflow"
    return "Not explicitly identified"


def write_outputs(
    studies: list[dict[str, str]],
    labels: list[dict[str, str]],
    suffix: str,
    metrics: dict[str, object],
) -> tuple[Path, Path, Path]:
    library = ROOT / "paper_library"
    label_path = library / f"unified_evidence_labels{suffix}.csv"
    study_path = library / f"unified_evidence_studies{suffix}.csv"
    metrics_path = library / f"unified_evidence_runtime{suffix}.json"

    with label_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(labels[0].keys()))
        writer.writeheader()
        writer.writerows(labels)

    by_study: dict[str, dict[str, list[str]]] = defaultdict(
        lambda: defaultdict(list)
    )
    for label in labels:
        by_study[label["cite_key"]][label["dimension"]].append(label["label"])

    wide_rows = []
    for study in studies:
        dimensions = by_study[study["cite_key"]]
        out = dict(study)
        for dimension in DIMENSION_PATTERNS:
            out[dimension] = "; ".join(sorted(set(dimensions[dimension])))
        out["workflow_context"] = derive_workflow_context(
            study["cite_key"],
            sorted(set(dimensions["data_source"])),
        )
        out["complete_alluvial"] = (
            "yes"
            if dimensions["family"]
            and (dimensions["doe_strategy"] or dimensions["data_source"])
            and dimensions["pattern"]
            and dimensions["validation"]
            else "no"
        )
        out["complete_model_target_trust"] = (
            "yes"
            if dimensions["family"]
            and dimensions["target"]
            and dimensions["trust"]
            else "no"
        )
        out["complete_doe_pair"] = (
            "yes"
            if dimensions["data_source"] and dimensions["doe_strategy"]
            else "no"
        )
        wide_rows.append(out)

    with study_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(wide_rows[0].keys()))
        writer.writeheader()
        writer.writerows(wide_rows)
    metrics_path.write_text(
        json.dumps(metrics, indent=2, ensure_ascii=True),
        encoding="utf-8",
    )
    return label_path, study_path, metrics_path


def main() -> None:
    args = parse_args()
    started = time.perf_counter()
    manifest = [
        row
        for row in read_csv(MANIFEST)
        if not REVIEW_RE.search(row.get("title", ""))
    ]
    bib = load_bib_text()
    extended_review_re = re.compile(
        r"\b(review|survey|bibliometric|scientometric|systematic literature|"
        r"research progress|state of the art)\b",
        re.IGNORECASE,
    )
    manifest = [
        row
        for row in manifest
        if not extended_review_re.search(
            " ".join(
                (
                    row.get("title", ""),
                    bib.get(row["cite_key"], {}).get("abstract", ""),
                )
            )
        )
    ]
    pdf_paths = load_pdf_paths()
    selected = representative_subset(manifest, pdf_paths, args.smoke)
    selected_keys = {row["cite_key"] for row in selected}

    pages_by_key: dict[str, list[dict[str, object]]] = {}
    extraction_seconds: dict[str, float] = {}
    cache_hits = 0
    cache_misses = 0
    pdf_selected = {
        row["cite_key"]: pdf_paths[row["cite_key"]]
        for row in selected
        if row["cite_key"] in pdf_paths
    }
    with ThreadPoolExecutor(max_workers=max(1, args.workers)) as executor:
        futures = {
            executor.submit(
                load_or_extract,
                key,
                pdf,
                args.max_pages,
                args.refresh_cache,
            ): key
            for key, pdf in pdf_selected.items()
        }
        for future in as_completed(futures):
            key = futures[future]
            pages, cache_hit, duration = future.result()
            pages_by_key[key] = pages
            extraction_seconds[key] = duration
            cache_hits += int(cache_hit)
            cache_misses += int(not cache_hit)

    labels = []
    studies = []
    for row in selected:
        key = row["cite_key"]
        pages = pages_by_key.get(key, [])
        labels.extend(classify_study(row, bib.get(key, {}), pages))
        studies.append(
            {
                "cite_key": key,
                "year": row.get("year", ""),
                "title": row.get("title", ""),
                "primary_bucket": row.get("primary_bucket", ""),
                "has_pdf": "yes" if key in pdf_paths else "no",
                "extracted_pages": str(len(pages)),
                "has_abstract": (
                    "yes" if bib.get(key, {}).get("abstract") else "no"
                ),
            }
        )
    labels = merge_manual(labels, selected_keys)
    labels = merge_followup_wide(labels, selected_keys)
    labels = merge_targeted_manual(labels, selected_keys)
    labels = derive_evidence_equivalents(labels)
    if not labels:
        raise RuntimeError("The unified audit produced no accepted labels.")

    elapsed = time.perf_counter() - started
    counts = Counter(label["dimension"] for label in labels)
    by_study: dict[str, set[str]] = defaultdict(set)
    for label in labels:
        by_study[label["cite_key"]].add(label["dimension"])
    metrics = {
        "mode": "smoke" if args.smoke else "full",
        "requested_smoke_records": args.smoke,
        "selected_records": len(selected),
        "selected_pdf_records": len(pdf_selected),
        "selected_abstract_records": sum(
            bib.get(row["cite_key"], {}).get("abstract", "") != ""
            for row in selected
        ),
        "max_pages": args.max_pages,
        "workers": args.workers,
        "cache_hits": cache_hits,
        "cache_misses": cache_misses,
        "extracted_pages": sum(
            len(pages) for pages in pages_by_key.values()
        ),
        "pdf_extraction_seconds_sum": round(
            sum(extraction_seconds.values()), 3
        ),
        "wall_seconds": round(elapsed, 3),
        "accepted_labels_by_dimension": dict(sorted(counts.items())),
        "records_with_any_label": sum(bool(value) for value in by_study.values()),
        "estimated_full_uncached_minutes": (
            round(
                elapsed
                * max(len(pdf_paths), 1)
                / max(len(pdf_selected), 1)
                / 60,
                1,
            )
            if args.smoke and cache_misses
            else None
        ),
    }
    suffix = "_smoke" if args.smoke else ""
    paths = write_outputs(studies, labels, suffix, metrics)
    print(json.dumps(metrics, indent=2))
    for path in paths:
        print(f"wrote {path}")


if __name__ == "__main__":
    main()
