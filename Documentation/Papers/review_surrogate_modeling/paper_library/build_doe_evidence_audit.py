"""Audit DoE strategy and training-data source for the curated evidence cards.

The vocabulary follows Section 7 of the current manuscript. Classification is
fail-closed: only explicit phrases in title, abstract, keywords, evidence-card
PDF prose, or the available PDF are accepted. Ambiguous studies remain
unassigned and are excluded from quantitative figures.
"""

from __future__ import annotations

import csv
import re
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Dict, Iterable, Tuple

from build_surrogate_target_audit import (
    extract_pdf_with_timeout,
    load_bib_text,
    load_pdf_paths,
    normalize,
    read_cards,
)


ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "paper_library" / "doe_evidence_audit.csv"
SUMMARY = ROOT / "paper_library" / "doe_evidence_audit_summary.csv"

STRATEGY_ORDER = (
    "Latin hypercube sampling",
    "Quasi-Monte Carlo / sparse-grid collocation",
    "Factorial / response-surface design",
    "Adaptive sampling",
    "Active learning",
    "Multi-fidelity training",
    "Transfer learning",
)

SOURCE_ORDER = (
    "Synthetic data",
    "Historical data",
    "Hybrid data",
)

# These expressions intentionally require named methods or explicit workflow
# language. Generic words such as sampling, data, training, or simulation are
# not sufficient evidence.
STRATEGY_PATTERNS: Dict[str, Tuple[Tuple[str, int], ...]] = {
    "Latin hypercube sampling": (
        (r"\blatin hypercube sampling\b", 8),
        (r"\blatin hypercube design\b", 8),
        (r"\bmaximin latin hypercube\b", 8),
        (r"\b(?:lhs|olhs)\s+(?:design|sampling|samples|points)\b", 7),
    ),
    "Quasi-Monte Carlo / sparse-grid collocation": (
        (r"\bquasi[- ]monte carlo\b", 8),
        (r"\b(?:sobol|halton)\s+(?:sequence|sampling|points)\b", 8),
        (r"\bsparse[- ]grid\s+(?:quadrature|collocation|sampling|points|nodes)\b", 8),
        (r"\b(?:stochastic|polynomial chaos)\s+collocation\b", 7),
        (r"\b(?:gauss|gaussian)[- ](?:hermite|legendre)\s+quadrature\b", 7),
    ),
    "Factorial / response-surface design": (
        (r"\bfull factorial design\b", 8),
        (r"\bfractional factorial design\b", 8),
        (r"\bbox[- ]behnken design\b", 8),
        (r"\bcentral composite design\b", 8),
        (r"\btaguchi\s+(?:design|method|array)\b", 7),
        (r"\bresponse surface methodology\b", 7),
        (r"\bdesign of experiments?\s*\(?(?:doe)?\)?\b", 5),
    ),
    "Adaptive sampling": (
        (r"\badaptive sampling\b", 8),
        (r"\badaptive design of experiments\b", 8),
        (r"\bsequential design of experiments\b", 8),
        (r"\binfill(?:ing)?\s+(?:criterion|criteria|strategy|sampling|point|points)\b", 7),
        (r"\badaptive refinement\b", 7),
        (r"\btruth[- ]model\s+(?:update|refinement|evaluation)\b", 6),
    ),
    "Active learning": (
        (r"\bactive learning\b", 8),
        (r"\bbayesian optimization\b", 8),
        (r"\bacquisition function\b", 8),
        (r"\bexpected improvement\b", 7),
        (r"\blower confidence bound\b", 7),
        (r"\buncertainty sampling\b", 7),
    ),
    "Multi-fidelity training": (
        (r"\bmulti[- ]fidelity\b", 8),
        (r"\bco[- ]kriging\b", 8),
        (r"\bmultiple fidelity levels\b", 8),
        (r"\blow[- ]fidelity\s+.+\s+high[- ]fidelity\b", 7),
        (r"\bhigh[- ]fidelity\s+.+\s+low[- ]fidelity\b", 7),
    ),
    "Transfer learning": (
        (r"\btransfer learning\b", 8),
        (r"\bdomain adaptation\b", 8),
        (r"\bfine[- ]tun(?:e|ed|ing)\s+(?:a\s+)?pretrained\b", 7),
        (r"\bpretrained\s+.+\s+new\s+(?:domain|condition|context)\b", 7),
    ),
}

SOURCE_PATTERNS: Dict[str, Tuple[Tuple[str, int], ...]] = {
    "Synthetic data": (
        (r"\bsynthetic(?:ally generated)?\s+(?:training\s+)?data\b", 8),
        (r"\bsimulation[- ]generated\s+(?:training\s+)?data\b", 8),
        (r"\btraining data\s+(?:are|were|is|was)\s+generated\s+(?:by|from|using)\s+(?:a\s+)?(?:simulation|simulator|optimization|optimisation)\b", 8),
        (r"\bgenerate(?:d|s|ing)?\s+(?:the\s+)?training (?:set|data)\s+(?:by|from|using)\s+(?:repeated\s+)?(?:simulation|optimization|optimisation|model evaluation)\b", 8),
        (r"\brepeated\s+(?:high[- ]fidelity\s+)?(?:model|simulator|simulation|optimization|optimisation)\s+(?:runs|evaluations|solves)\b", 7),
        (r"\blabels?\s+(?:are|were|is|was)\s+(?:obtained|generated)\s+(?:by|from)\s+(?:solving|simulating|running)\b", 7),
    ),
    "Historical data": (
        (r"\bhistorical\s+(?:operational\s+|operation\s+|measurement\s+|measured\s+|time[- ]series\s+)?data\b", 8),
        (r"\bhistorical\s+(?:records|measurements|observations|operation)\b", 8),
        (r"\bmeasured\s+(?:operational\s+|field\s+|real[- ]world\s+)?data\b", 8),
        (r"\boperational\s+(?:records|measurements|data)\b", 8),
        (r"\bfield[- ]measured\s+data\b", 8),
        (r"\bscada\s+data\b", 8),
        (r"\breal[- ]world\s+(?:measurement|operational)\s+data\b", 7),
    ),
    "Hybrid data": (
        (r"\bhybrid\s+(?:training\s+)?data(?:set)?\b", 9),
        (r"\bcombine(?:d|s|ing)?\s+(?:historical|measured|operational)\s+data\s+with\s+(?:synthetic|simulated|simulation[- ]generated)\s+data\b", 10),
        (r"\bcombine(?:d|s|ing)?\s+(?:synthetic|simulated|simulation[- ]generated)\s+data\s+with\s+(?:historical|measured|operational)\s+data\b", 10),
        (r"\b(?:historical|measured)\s+and\s+(?:synthetic|simulated)\s+data\b", 10),
        (r"\b(?:synthetic|simulated)\s+and\s+(?:historical|measured)\s+data\b", 10),
    ),
}


def score_patterns(
    text: str, patterns: Iterable[Tuple[str, int]]
) -> Tuple[int, str]:
    """Return bounded phrase score and a compact auditable snippet."""
    score = 0
    best_weight = 0
    snippet = ""
    for pattern, weight in patterns:
        matches = list(re.finditer(pattern, text, re.IGNORECASE))
        if not matches:
            continue
        score += weight + min(len(matches) - 1, 2)
        if weight > best_weight:
            match = matches[0]
            start = max(0, match.start() - 110)
            end = min(len(text), match.end() + 150)
            snippet = re.sub(r"\s+", " ", text[start:end]).strip()
            best_weight = weight
    return score, snippet


def classify_dimension(
    patterns_by_label: Dict[str, Tuple[Tuple[str, int], ...]],
    order: Tuple[str, ...],
    title: str,
    abstract: str,
    keywords: str,
    card_prose: str,
    pdf_text: str,
) -> Dict[str, str]:
    """Classify one dimension with bibliographic evidence taking priority."""
    sources = (
        ("title", normalize(title), 4),
        ("abstract/keywords", normalize(f"{abstract} {keywords}"), 3),
        ("evidence-card PDF prose", normalize(card_prose), 3),
        ("pdf", normalize(pdf_text[:45000]), 1),
    )
    scores: Counter[str] = Counter()
    evidence: Dict[str, Tuple[str, str, int]] = {}

    for label in order:
        best_source = ("", "", 0)
        weighted_total = 0
        for source_name, text, multiplier in sources:
            raw_score, snippet = score_patterns(text, patterns_by_label[label])
            weighted = raw_score * multiplier
            weighted_total += weighted
            if weighted > best_source[2]:
                best_source = (source_name, snippet, weighted)
        scores[label] = weighted_total
        evidence[label] = best_source

    ranked = scores.most_common()
    best_label, best_score = ranked[0]
    runner_up, runner_up_score = ranked[1]
    source, snippet, source_score = evidence[best_label]

    # One explicit named method in an abstract/card is enough; PDF-only
    # assignment requires at least two supporting hits or one stronger phrase.
    high = (
        best_score >= 21
        and best_score - runner_up_score >= 7
        and source_score >= 21
    )
    return {
        "label": best_label if high else "",
        "confidence": "high" if high else "unassigned",
        "score": str(best_score),
        "runner_up": runner_up,
        "runner_up_score": str(runner_up_score),
        "evidence_source": source if high else "",
        "evidence_snippet": snippet if high else "",
        "all_scores": "; ".join(f"{label}={scores[label]}" for label in order),
    }


def classify_card(
    card: Dict[str, str],
    bib_row: Dict[str, str],
    pdf_text: str,
) -> Tuple[Dict[str, str], Dict[str, str]]:
    title = bib_row.get("title") or card.get("system", "")
    abstract = bib_row.get("abstract", "")
    keywords = bib_row.get("keywords", "")
    strategy = classify_dimension(
        STRATEGY_PATTERNS,
        STRATEGY_ORDER,
        title,
        abstract,
        keywords,
        card.get("doe_prose", ""),
        pdf_text,
    )
    source = classify_dimension(
        SOURCE_PATTERNS,
        SOURCE_ORDER,
        title,
        abstract,
        keywords,
        "",
        pdf_text,
    )
    return strategy, source


def main() -> None:
    cards = read_cards()
    bib = load_bib_text()
    pdf_paths = load_pdf_paths()
    preliminary: Dict[str, Tuple[Dict[str, str], Dict[str, str]]] = {}
    pdf_candidates: Dict[str, Path] = {}

    for card in cards:
        key = card["cite_key"]
        result = classify_card(card, bib.get(key, {}), "")
        preliminary[key] = result
        if (
            result[0]["confidence"] != "high"
            or result[1]["confidence"] != "high"
        ) and key in pdf_paths:
            pdf_candidates[key] = pdf_paths[key]

    pdf_texts: Dict[str, str] = {}
    with ThreadPoolExecutor(max_workers=8) as executor:
        futures = {
            executor.submit(extract_pdf_with_timeout, pdf, 12): key
            for key, pdf in pdf_candidates.items()
        }
        for future in as_completed(futures):
            pdf_texts[futures[future]] = future.result()

    rows = []
    for card in cards:
        key = card["cite_key"]
        strategy, source = preliminary[key]
        pdf_text = pdf_texts.get(key, "")
        if pdf_text:
            strategy, source = classify_card(card, bib.get(key, {}), pdf_text)
        rows.append(
            {
                "cite_key": key,
                "family": card.get("family", ""),
                "pattern": card.get("pattern", ""),
                "section": card.get("section", ""),
                "doe_strategy": strategy["label"],
                "strategy_confidence": strategy["confidence"],
                "strategy_score": strategy["score"],
                "strategy_runner_up": strategy["runner_up"],
                "strategy_runner_up_score": strategy["runner_up_score"],
                "strategy_evidence_source": strategy["evidence_source"],
                "strategy_evidence_snippet": strategy["evidence_snippet"],
                "strategy_all_scores": strategy["all_scores"],
                "data_source": source["label"],
                "source_confidence": source["confidence"],
                "source_score": source["score"],
                "source_runner_up": source["runner_up"],
                "source_runner_up_score": source["runner_up_score"],
                "source_evidence_source": source["evidence_source"],
                "source_evidence_snippet": source["evidence_snippet"],
                "source_all_scores": source["all_scores"],
                "has_pdf_text": "yes" if len(pdf_text) > 200 else "no",
                "has_abstract": "yes" if bib.get(key, {}).get("abstract") else "no",
            }
        )

    with OUT.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)

    summary_rows = []
    for dimension, field, order in (
        ("strategy", "doe_strategy", STRATEGY_ORDER),
        ("data_source", "data_source", SOURCE_ORDER),
    ):
        counts = Counter(row[field] or "Unassigned" for row in rows)
        for label in (*order, "Unassigned"):
            summary_rows.append(
                {"dimension": dimension, "label": label, "n": counts[label]}
            )
    with SUMMARY.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["dimension", "label", "n"])
        writer.writeheader()
        writer.writerows(summary_rows)

    complete = sum(
        row["strategy_confidence"] == "high"
        and row["source_confidence"] == "high"
        and row["pattern"] not in {"", "--"}
        for row in rows
    )
    print(f"cards={len(rows)} complete_plot_assignments={complete}")
    for row in summary_rows:
        print(f"{row['dimension']} | {row['label']}: {row['n']}")
    print(f"wrote {OUT}")


if __name__ == "__main__":
    main()
