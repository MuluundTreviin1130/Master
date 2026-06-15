"""Build a high-confidence four-stage audit for the taxonomy alluvial figure.

The audit covers the complete curated paper-library manifest rather than only
the Section-8 evidence cards. Review and survey papers are excluded because
they do not represent one study-level workflow. Assignments require explicit
title, abstract, keyword, or available-PDF evidence; bucket tags are not used
as a fallback.
"""

from __future__ import annotations

import csv
import re
import sys
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Dict, Iterable, Tuple

from build_doe_evidence_audit import (
    SOURCE_PATTERNS,
    STRATEGY_ORDER,
    STRATEGY_PATTERNS,
    score_patterns,
)
from build_surrogate_target_audit import (
    load_bib_text,
    load_pdf_paths,
    normalize,
)

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tables"))
import build_table_T6_evidence_map as t6  # noqa: E402

MANIFEST = ROOT / "paper_library" / "review_paper_library_manifest.csv"
OUT = ROOT / "paper_library" / "alluvial_evidence_audit.csv"
SUMMARY = ROOT / "paper_library" / "alluvial_evidence_audit_summary.csv"

FAMILY_ORDER = (
    "PCE / RSM",
    "GP / kriging",
    "Neural network",
    "RBF / kernel",
    "Tree ensembles",
)
FAMILY_PATTERNS: Dict[str, Tuple[Tuple[str, int], ...]] = {
    "PCE / RSM": (
        (r"\bpolynomial chaos expansion\b", 9),
        (r"\bsparse polynomial chaos\b", 9),
        (r"\b(?:pce|spce)\s+(?:surrogate|model|metamodel|approximation)\b", 8),
        (r"\bresponse surface methodology\b", 9),
        (r"\bresponse surface model(?:ing)?\b", 8),
        (r"\bpolynomial response surface\b", 8),
    ),
    "GP / kriging": (
        (r"\bgaussian process(?:es)?\b", 9),
        (r"\bgaussian process regression\b", 9),
        (r"\bkriging\b", 9),
        (r"\bco[- ]kriging\b", 9),
    ),
    "Neural network": (
        (r"\bartificial neural network\b", 8),
        (r"\bdeep neural network\b", 8),
        (r"\bfeed[- ]forward neural network\b", 8),
        (r"\bmultilayer perceptron\b", 8),
        (r"\bgraph neural network\b", 8),
        (r"\bconvolutional neural network\b", 8),
        (r"\brecurrent neural network\b", 8),
        (r"\blong short[- ]term memory\b", 8),
        (r"\bneural network surrogate\b", 8),
        (r"\bphysics[- ]informed neural network\b", 10),
        (r"\bphysics[- ]guided neural network\b", 10),
        (r"\bconstraint[- ]aware neural network\b", 10),
        (r"\binput[- ]convex neural network\b", 10),
        (r"\bmonotone neural network\b", 10),
        (r"\bgraph neural network\b", 9),
    ),
    "RBF / kernel": (
        (r"\bradial basis function\b", 9),
        (r"\brbf\s+(?:network|surrogate|model|interpolation)\b", 8),
        (r"\bsupport vector regression\b", 9),
        (r"\bsupport vector machine\b", 8),
        (r"\bkernel regression\b", 8),
    ),
    "Tree ensembles": (
        (r"\brandom forest\b", 9),
        (r"\bgradient boosting\b", 9),
        (r"\bxgboost\b", 9),
        (r"\blightgbm\b", 9),
        (r"\bextra[- ]trees\b", 9),
        (r"\bdecision tree ensemble\b", 8),
    ),
}

PATTERN_ORDER = (
    "P1 replacement",
    "P2 acceleration",
    "P3 solution proxy",
    "P4 decomposition",
    "P5 uncertainty",
)

ALLUVIAL_DOE_ORDER = (
    *STRATEGY_ORDER,
    "Simulation-generated data",
    "Historical operational data",
    "Hybrid data",
)
ALLUVIAL_DOE_PATTERNS = {
    **STRATEGY_PATTERNS,
    "Simulation-generated data": SOURCE_PATTERNS["Synthetic data"],
    "Historical operational data": SOURCE_PATTERNS["Historical data"],
    "Hybrid data": SOURCE_PATTERNS["Hybrid data"],
}
PATTERN_PATTERNS: Dict[str, Tuple[Tuple[str, int], ...]] = {
    "P1 replacement": (
        (r"\breplac(?:e|es|ed|ing)\s+(?:the\s+)?(?:expensive|computationally expensive|time-consuming)\s+(?:simulation|simulator|model|calculation|evaluation|solver|optimization|optimisation)\b", 10),
        (r"\breplac(?:e|es|ed|ing)\s+(?:repeated\s+)?(?:simulation|simulator|model|power[- ]flow|load[- ]flow|optimal power flow|opf)\s+(?:runs|evaluations|calculations|solves)?\b", 9),
        (r"\bsubstitut(?:e|es|ed|ing)\s+for\s+(?:the\s+)?(?:simulation|simulator|model|solver|power flow|optimization|optimisation)\b", 9),
        (r"\bproxy\s+(?:for|of)\s+(?:the\s+)?(?:power flow|optimal power flow|economic dispatch|simulation|simulator|optimization|optimisation)\b", 9),
        (r"\b(?:surrogate|metamodel|emulator)\s+(?:is\s+)?used\s+instead of\s+(?:the\s+)?(?:full|original|high[- ]fidelity)\s+(?:model|simulation|solver)\b", 10),
        (r"\b(?:surrogate|metamodel|emulator)\s+(?:of|for)\s+(?:the\s+)?(?:power flow|load flow|network model|energy system model|building simulation|system performance|objective function|cost function|constraint function|feasibility region)\b", 8),
        (r"\bapproximat(?:e|es|ed|ing)\s+(?:the\s+)?(?:power flow|load flow|network equations|system response|objective function|cost function|constraint function|feasibility region|conversion losses)\b", 9),
        (r"\bfast\s+(?:surrogate|metamodel|emulator)\s+(?:of|for)\s+(?:the\s+)?(?:simulation|model|power flow|opf|system response)\b", 9),
        (r"\b(?:simulation|simulator)[- ]based\s+(?:surrogate|metamodel|emulator)\b", 8),
    ),
    "P2 acceleration": (
        (r"\bsurrogate[- ]assisted\s+(?:optimization|optimisation|search|evolutionary algorithm)\b", 9),
        (r"\bsurrogate[- ]based\s+(?:optimization|optimisation)\b", 8),
        (r"\b(?:surrogate|metamodel)\s+(?:is\s+)?used\s+to\s+(?:screen|rank|select|preselect)\s+(?:candidate|design|solution)s?\b", 9),
        (r"\b(?:bayesian optimization|expected improvement|acquisition function)\b", 8),
        (r"\b(?:efficient global optimization|efficient global optimisation)\b", 9),
        (r"\b(?:infill|adaptive sampling)\b.{0,180}\b(?:optimization|optimisation|search)\b", 8),
    ),
    "P3 solution proxy": (
        (r"\bpredict(?:s|ed|ing)?\s+(?:the\s+)?(?:optimal|near[- ]optimal)\s+(?:solution|decision|dispatch|schedule|set[- ]point|allocation)\b", 10),
        (r"\blearn(?:s|ed|ing)?\s+(?:the\s+)?(?:optimal\s+)?(?:solution|decision|dispatch|policy)\s+(?:map|mapping)\b", 10),
        (r"\blearning[- ]to[- ]optimi[sz]e\b", 10),
        (r"\boptimization prox(?:y|ies)\b", 10),
        (r"\bend[- ]to[- ]end\s+(?:optimal power flow|economic dispatch|unit commitment|optimization|optimisation)\b", 9),
    ),
    "P4 decomposition": (
        (r"\bbenders decomposition\b", 10),
        (r"\bcolumn generation\b", 10),
        (r"\bvalue function approximation\b", 10),
        (r"\brecourse function approximation\b", 10),
        (r"\bsurrogate\s+(?:cut|cuts|subproblem|recourse|value function)\b", 9),
        (r"\bapproximate(?:s|d|ing)?\s+(?:the\s+)?(?:subproblem|recourse|value function)\b", 9),
    ),
    "P5 uncertainty": (
        (r"\bsurrogate\b.{0,180}\b(?:chance[- ]constrained|robust optimization|robust optimisation|uncertainty propagation)\b", 9),
        (r"\b(?:polynomial chaos|gaussian process|surrogate|emulator)\b.{0,180}\b(?:chance constraint|probabilistic constraint|uncertainty quantification)\b", 9),
        (r"\bapproximat(?:e|es|ed|ing)\s+(?:the\s+)?(?:chance constraint|violation probability|uncertainty distribution|probabilistic response)\b", 10),
        (r"\buncertainty propagation\s+(?:using|with|through)\s+(?:a\s+)?(?:surrogate|polynomial chaos|gaussian process|emulator)\b", 10),
    ),
}

VALIDATION_PRIORITY = (
    "Decision-aware",
    "Stress test",
    "Interval calibration",
    "Feasibility",
    "Problem UQ",
    "Point metrics",
)
VALIDATION_PATTERNS: Dict[str, Tuple[Tuple[str, int], ...]] = {
    "Point metrics": (
        (r"\broot mean squared error\b", 8),
        (r"\bnormalized root mean squared error\b", 9),
        (r"\bnormalised root mean squared error\b", 9),
        (r"\bmean absolute error\b", 8),
        (r"\bmean absolute percentage error\b", 8),
        (r"\bmean squared error\b", 7),
        (r"\b(?:rmse|nrmse|mae|mse|mape)\b", 7),
        (r"\bcoefficient of determination\b", 8),
        (r"\br[- ]?squared\b", 7),
        (r"\brelative (?:prediction )?error\b", 7),
        (r"\bmaximum (?:relative )?error\b", 7),
        (r"\bprediction accuracy\b", 7),
    ),
    "Feasibility": (
        (r"\bfeasibility rate\b", 9),
        (r"\bfeasible solution rate\b", 9),
        (r"\bconstraint violation(?:s)?\b", 8),
        (r"\binfeasibility rate\b", 9),
        (r"\bpercentage of feasible solutions\b", 9),
    ),
    "Problem UQ": (
        (r"\buncertainty quantification\b", 8),
        (r"\buncertainty propagation\b", 8),
        (r"\bprobabilistic validation\b", 8),
        (r"\bmean and variance\b", 7),
        (r"\bprobability distribution\b.{0,180}\b(?:compare|validation|agreement)\b", 8),
    ),
    "Interval calibration": (
        (r"\bprediction interval coverage\b", 10),
        (r"\bcoverage probability\b", 9),
        (r"\bcalibration curve\b", 9),
        (r"\breliability diagram\b", 9),
        (r"\bprobability integral transform\b", 9),
        (r"\bcalibrat(?:e|ed|ion)\s+(?:prediction|credible|confidence)\s+interval\b", 9),
    ),
    "Decision-aware": (
        (r"\boptimality gap\b", 10),
        (r"\bregret\b", 10),
        (r"\bcost gap\b", 10),
        (r"\bobjective gap\b", 10),
        (r"\bpareto front\s+(?:quality|distance|error)\b", 9),
        (r"\bdecision quality\b", 9),
    ),
    "Stress test": (
        (r"\bstress test(?:ing|s)?\b", 10),
        (r"\bextreme weather scenario(?:s)?\b", 9),
        (r"\bpeak[- ]load scenario(?:s)?\b", 9),
        (r"\blow[- ]renewable scenario(?:s)?\b", 9),
        (r"\bcold[- ]spell scenario(?:s)?\b", 9),
        (r"\bout[- ]of[- ]distribution\s+(?:test|evaluation|scenario)\b", 9),
    ),
}

REVIEW_RE = re.compile(
    r"\b(review|survey|bibliometric|scientometric|systematic literature)\b",
    re.IGNORECASE,
)


def read_manifest() -> list[dict[str, str]]:
    with MANIFEST.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def classify_dimension(
    patterns_by_label: Dict[str, Tuple[Tuple[str, int], ...]],
    order: Tuple[str, ...],
    title: str,
    abstract: str,
    keywords: str,
    pdf_text: str,
) -> Dict[str, str]:
    """Return one explicit, separated assignment or fail closed."""
    sources = (
        ("title", normalize(title), 4),
        ("abstract/keywords", normalize(f"{abstract} {keywords}"), 3),
        ("pdf", normalize(pdf_text[:220000]), 1),
    )
    scores: Counter[str] = Counter()
    evidence: Dict[str, Tuple[str, str, int]] = {}
    for label in order:
        total = 0
        best = ("", "", 0)
        for source, text, multiplier in sources:
            raw, snippet = score_patterns(text, patterns_by_label[label])
            weighted = raw * multiplier
            total += weighted
            if weighted > best[2]:
                best = (source, snippet, weighted)
        scores[label] = total
        evidence[label] = best

    ranked = scores.most_common()
    label, score = ranked[0]
    runner_up, runner_score = ranked[1]
    source, snippet, source_score = evidence[label]
    source_threshold = 8 if source == "pdf" else 21
    high = (
        score >= source_threshold
        and score - runner_score >= 5
        and source_score >= source_threshold
    )
    return {
        "label": label if high else "",
        "confidence": "high" if high else "unassigned",
        "score": str(score),
        "runner_up": runner_up,
        "runner_up_score": str(runner_score),
        "evidence_source": source if high else "",
        "evidence_snippet": snippet if high else "",
    }


def classify_validation(
    title: str,
    abstract: str,
    keywords: str,
    pdf_text: str,
) -> Dict[str, str]:
    """Select the highest-order explicitly reported validation signal."""
    qualified: Dict[str, Dict[str, str]] = {}
    for label in VALIDATION_PRIORITY:
        result = classify_dimension(
            {label: VALIDATION_PATTERNS[label], "_other": ((r"(?!x)x", 1),)},
            (label, "_other"),
            title,
            abstract,
            keywords,
            pdf_text,
        )
        if result["confidence"] == "high":
            qualified[label] = result
    for label in VALIDATION_PRIORITY:
        if label in qualified:
            return qualified[label]
    return {
        "label": "",
        "confidence": "unassigned",
        "score": "0",
        "runner_up": "",
        "runner_up_score": "0",
        "evidence_source": "",
        "evidence_snippet": "",
    }


def classify_record(
    row: dict[str, str],
    bib_row: dict[str, str],
    pdf_text: str,
) -> dict[str, Dict[str, str]]:
    title = bib_row.get("title") or row.get("title", "")
    abstract = bib_row.get("abstract", "")
    keywords = bib_row.get("keywords", "")
    return {
        "family": classify_dimension(
            FAMILY_PATTERNS,
            FAMILY_ORDER,
            title,
            abstract,
            keywords,
            pdf_text,
        ),
        "doe": classify_dimension(
            ALLUVIAL_DOE_PATTERNS,
            ALLUVIAL_DOE_ORDER,
            title,
            abstract,
            keywords,
            pdf_text,
        ),
        "pattern": classify_dimension(
            PATTERN_PATTERNS,
            PATTERN_ORDER,
            title,
            abstract,
            keywords,
            pdf_text,
        ),
        "validation": classify_validation(
            title,
            abstract,
            keywords,
            pdf_text,
        ),
    }


def extract_pdf_text(pdf: Path) -> str:
    """Read enough of the paper to include methods and validation results."""
    text = t6.extract_pdf_text(pdf, max_pages=35)
    # References frequently repeat taxonomy terms from unrelated studies. The
    # audit concerns the focal workflow, so discard a conventional reference
    # section before scoring the article body.
    reference = re.search(
        r"(?im)^\s*(references|bibliography|literature cited)\s*$",
        text,
    )
    return text[: reference.start()] if reference else text


def main() -> None:
    manifest = [
        row for row in read_manifest() if not REVIEW_RE.search(row.get("title", ""))
    ]
    bib = load_bib_text()
    pdf_paths = load_pdf_paths()
    preliminary: dict[str, dict[str, Dict[str, str]]] = {}
    pdf_candidates: dict[str, Path] = {}

    for row in manifest:
        key = row["cite_key"]
        result = classify_record(row, bib.get(key, {}), "")
        preliminary[key] = result
        if any(value["confidence"] != "high" for value in result.values()):
            if key in pdf_paths:
                pdf_candidates[key] = pdf_paths[key]

    pdf_texts: dict[str, str] = {}
    with ThreadPoolExecutor(max_workers=6) as executor:
        futures = {
            executor.submit(extract_pdf_text, path): key
            for key, path in pdf_candidates.items()
        }
        for future in as_completed(futures):
            pdf_texts[futures[future]] = future.result()

    rows = []
    for row in manifest:
        key = row["cite_key"]
        result = preliminary[key]
        pdf_text = pdf_texts.get(key, "")
        if pdf_text:
            result = classify_record(row, bib.get(key, {}), pdf_text)
        out = {
            "cite_key": key,
            "year": row.get("year", ""),
            "title": row.get("title", ""),
            "has_pdf_text": "yes" if len(pdf_text) > 200 else "no",
            "has_abstract": "yes" if bib.get(key, {}).get("abstract") else "no",
        }
        for dimension in ("family", "doe", "pattern", "validation"):
            value = result[dimension]
            out[dimension] = value["label"]
            out[f"{dimension}_confidence"] = value["confidence"]
            out[f"{dimension}_score"] = value["score"]
            out[f"{dimension}_runner_up"] = value["runner_up"]
            out[f"{dimension}_runner_up_score"] = value["runner_up_score"]
            out[f"{dimension}_evidence_source"] = value["evidence_source"]
            out[f"{dimension}_evidence_snippet"] = value["evidence_snippet"]
        out["complete"] = (
            "yes"
            if all(
                result[dimension]["confidence"] == "high"
                for dimension in ("family", "doe", "pattern", "validation")
            )
            else "no"
        )
        rows.append(out)

    with OUT.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)

    summary_rows = []
    orders = {
        "family": FAMILY_ORDER,
        "doe": ALLUVIAL_DOE_ORDER,
        "pattern": PATTERN_ORDER,
        "validation": VALIDATION_PRIORITY,
    }
    for dimension, order in orders.items():
        counts = Counter(row[dimension] or "Unassigned" for row in rows)
        for label in (*order, "Unassigned"):
            summary_rows.append(
                {"dimension": dimension, "label": label, "n": counts[label]}
            )
    summary_rows.append(
        {
            "dimension": "complete",
            "label": "All four dimensions",
            "n": sum(row["complete"] == "yes" for row in rows),
        }
    )
    with SUMMARY.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["dimension", "label", "n"])
        writer.writeheader()
        writer.writerows(summary_rows)

    print(
        f"non_review_records={len(rows)} "
        f"pdf_candidates={len(pdf_candidates)} "
        f"complete={sum(row['complete'] == 'yes' for row in rows)}"
    )
    for row in summary_rows:
        print(f"{row['dimension']} | {row['label']}: {row['n']}")
    print(f"wrote {OUT}")


if __name__ == "__main__":
    main()
