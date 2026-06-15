"""Full-PDF follow-up audit for incomplete alluvial study paths.

The primary audit deliberately uses a bounded PDF window. This follow-up reads
the complete article body for studies with exactly one missing alluvial
dimension, stops before the reference list, and records the strongest explicit
evidence with a PDF page number. Accepted assignments are written to a separate
override file and merged into ``alluvial_evidence_audit_followup.csv``.
"""

from __future__ import annotations

import csv
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Dict, Tuple

from pypdf import PdfReader

from build_alluvial_evidence_audit import (
    ALLUVIAL_DOE_ORDER,
    ALLUVIAL_DOE_PATTERNS,
    FAMILY_ORDER,
    FAMILY_PATTERNS,
    PATTERN_ORDER,
    PATTERN_PATTERNS,
    VALIDATION_PATTERNS,
    VALIDATION_PRIORITY,
    classify_dimension,
    classify_validation,
)
from build_surrogate_target_audit import load_bib_text, load_pdf_paths


ROOT = Path(__file__).resolve().parent.parent
BASE_AUDIT = ROOT / "paper_library" / "alluvial_evidence_audit.csv"
OUT_OVERRIDES = ROOT / "paper_library" / "alluvial_fulltext_followup.csv"
OUT_MERGED = ROOT / "paper_library" / "alluvial_evidence_audit_followup.csv"
MANUAL_OVERRIDES = (
    ROOT / "paper_library" / "alluvial_manual_adjudication.csv"
)

DIMENSIONS = ("family", "doe", "pattern", "validation")
ALLOWED_LABELS = {
    "family": set(FAMILY_ORDER),
    "doe": set(ALLUVIAL_DOE_ORDER),
    "pattern": set(PATTERN_ORDER),
    "validation": set(VALIDATION_PRIORITY),
}
REFERENCE_HEADING = re.compile(
    r"(?im)^\s*(references|bibliography|literature cited)\s*$"
)

# A named category phrase still needs workflow context on the same page. This
# prevents a method mentioned only as related work from becoming an assignment.
CONTEXT_PATTERNS = {
    "family": re.compile(
        r"\b(we (?:use|employ|develop|propose|train|construct)|"
        r"this (?:paper|study|work)|our (?:model|method|approach|surrogate)|"
        r"is (?:trained|fitted|developed|constructed)|surrogate model)\b",
        re.IGNORECASE,
    ),
    "doe": re.compile(
        r"\b(training (?:data|set|samples)|design points|sample points|"
        r"initial (?:design|sample)|experiments?|simulations?|"
        r"we (?:sample|generate|select|use|employ)|data generation|"
        r"sampling strategy|training process)\b",
        re.IGNORECASE,
    ),
    "pattern": re.compile(
        r"\b(optimization|optimisation|optimizer|solver|workflow|framework|"
        r"surrogate|metamodel|emulator|proxy|subproblem|dispatch|opf|"
        r"unit commitment|power flow)\b",
        re.IGNORECASE,
    ),
    "validation": re.compile(
        r"\b(results?|validation|evaluation|performance|accuracy|test set|"
        r"out-of-sample|comparison|error|feasibility|calibration)\b",
        re.IGNORECASE,
    ),
}


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def extract_article_pages(pdf: Path) -> list[tuple[int, str]]:
    """Extract article pages and omit the references and later appendices."""
    reader = PdfReader(str(pdf))
    pages: list[tuple[int, str]] = []
    for index, page in enumerate(reader.pages):
        text = page.extract_text() or ""
        if index >= 2 and REFERENCE_HEADING.search(text[:2500]):
            break
        if text.strip():
            pages.append((index + 1, text))
    return pages


def pattern_set(dimension: str):
    if dimension == "family":
        return FAMILY_PATTERNS, FAMILY_ORDER
    if dimension == "doe":
        return ALLUVIAL_DOE_PATTERNS, ALLUVIAL_DOE_ORDER
    if dimension == "pattern":
        return PATTERN_PATTERNS, PATTERN_ORDER
    raise ValueError(f"Unsupported dimension: {dimension}")


def classify_page(
    dimension: str,
    title: str,
    abstract: str,
    keywords: str,
    page_text: str,
) -> dict[str, str]:
    if dimension == "validation":
        return classify_validation(title, abstract, keywords, page_text)
    patterns, order = pattern_set(dimension)
    return classify_dimension(
        patterns,
        order,
        title,
        abstract,
        keywords,
        page_text,
    )


def audit_one(
    key: str,
    dimension: str,
    pdf: Path,
    bib_row: dict[str, str],
) -> dict[str, str]:
    """Select the strongest context-supported page-level assignment."""
    title = bib_row.get("title", "")
    abstract = bib_row.get("abstract", "")
    keywords = bib_row.get("keywords", "")
    candidates = []
    for page_number, page_text in extract_article_pages(pdf):
        result = classify_page(
            dimension,
            title,
            abstract,
            keywords,
            page_text,
        )
        if result["confidence"] != "high":
            continue
        # Context must occur in the local evidence passage. A method mentioned
        # elsewhere on the same page, for example in related work, is not
        # sufficient proof that the study itself used it.
        if not CONTEXT_PATTERNS[dimension].search(
            result.get("evidence_snippet", "")
        ):
            continue
        candidates.append((int(result["score"]), page_number, result))

    if not candidates:
        return {
            "cite_key": key,
            "dimension": dimension,
            "label": "",
            "confidence": "unassigned",
            "score": "0",
            "page": "",
            "evidence_source": "",
            "evidence_snippet": "",
        }

    score, page_number, result = max(candidates, key=lambda item: item[0])
    return {
        "cite_key": key,
        "dimension": dimension,
        "label": result["label"],
        "confidence": "high",
        "score": str(score),
        "page": str(page_number),
        "evidence_source": "full PDF follow-up",
        "evidence_snippet": result["evidence_snippet"],
    }


def main() -> None:
    base_rows = read_csv(BASE_AUDIT)
    bib = load_bib_text()
    pdf_paths = load_pdf_paths()
    candidates: list[Tuple[str, str, Path]] = []

    for row in base_rows:
        assigned = [
            dimension
            for dimension in DIMENSIONS
            if row.get(f"{dimension}_confidence") == "high"
        ]
        missing = [
            dimension
            for dimension in DIMENSIONS
            if row.get(f"{dimension}_confidence") != "high"
        ]
        if len(assigned) == 3 and len(missing) == 1 and row["cite_key"] in pdf_paths:
            candidates.append(
                (row["cite_key"], missing[0], pdf_paths[row["cite_key"]])
            )

    overrides = []
    with ThreadPoolExecutor(max_workers=4) as executor:
        futures = {
            executor.submit(
                audit_one,
                key,
                dimension,
                pdf,
                bib.get(key, {}),
            ): (key, dimension)
            for key, dimension, pdf in candidates
        }
        for future in as_completed(futures):
            overrides.append(future.result())

    overrides.sort(key=lambda row: (row["dimension"], row["cite_key"]))
    with OUT_OVERRIDES.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(overrides[0].keys()))
        writer.writeheader()
        writer.writerows(overrides)

    accepted = {
        (row["cite_key"], row["dimension"]): row
        for row in overrides
        if row["confidence"] == "high"
        # This record is a known Related-Work false positive: the cited RBF
        # belongs to another study, not to Kaewdornhan et al.'s own method.
        and not (
            row["cite_key"] == "Kaewdornhan2022130373"
            and row["dimension"] == "family"
        )
    }
    # Manual adjudications are deliberately stored as data rather than hidden
    # in classifier code. Each row must use an existing manuscript category
    # and retain a checkable abstract or page-numbered PDF passage.
    manual_rows = read_csv(MANUAL_OVERRIDES)
    for row in manual_rows:
        dimension = row.get("dimension", "")
        label = row.get("label", "")
        if dimension not in DIMENSIONS:
            raise ValueError(
                f"Invalid manual dimension for {row.get('cite_key')}: "
                f"{dimension}"
            )
        if label not in ALLOWED_LABELS[dimension]:
            raise ValueError(
                f"Invalid {dimension} label for {row.get('cite_key')}: "
                f"{label}"
            )
        if row.get("confidence") != "high":
            raise ValueError(
                f"Manual adjudication must be high confidence: "
                f"{row.get('cite_key')} {dimension}"
            )
        if not row.get("evidence_snippet") or not row.get("evidence_source"):
            raise ValueError(
                f"Manual adjudication lacks evidence: "
                f"{row.get('cite_key')} {dimension}"
            )
        accepted[(row["cite_key"], dimension)] = {
            **row,
            "score": "manual",
        }
    merged_rows = []
    for row in base_rows:
        merged = dict(row)
        for dimension in DIMENSIONS:
            override = accepted.get((row["cite_key"], dimension))
            if not override:
                continue
            merged[dimension] = override["label"]
            merged[f"{dimension}_confidence"] = "high"
            merged[f"{dimension}_score"] = override["score"]
            merged[f"{dimension}_runner_up"] = ""
            merged[f"{dimension}_runner_up_score"] = "0"
            merged[f"{dimension}_evidence_source"] = override["evidence_source"]
            merged[f"{dimension}_evidence_snippet"] = (
                f"p. {override['page']}: {override['evidence_snippet']}"
            )
        merged["complete"] = (
            "yes"
            if all(
                merged.get(f"{dimension}_confidence") == "high"
                for dimension in DIMENSIONS
            )
            else "no"
        )
        merged_rows.append(merged)

    with OUT_MERGED.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(merged_rows[0].keys()))
        writer.writeheader()
        writer.writerows(merged_rows)

    accepted_counts = {
        dimension: sum(
            row["confidence"] == "high" and row["dimension"] == dimension
            for row in overrides
        )
        for dimension in DIMENSIONS
    }
    print(f"followup_candidates={len(candidates)}")
    for dimension in DIMENSIONS:
        print(f"{dimension}_accepted={accepted_counts[dimension]}")
    print(
        "complete_after_followup="
        f"{sum(row['complete'] == 'yes' for row in merged_rows)}"
    )
    print(f"wrote {OUT_OVERRIDES}")
    print(f"wrote {OUT_MERGED}")


if __name__ == "__main__":
    main()
