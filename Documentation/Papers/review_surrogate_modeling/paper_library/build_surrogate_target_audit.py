"""Classify surrogate targets for PDF-backed evidence cards.

The target vocabulary is taken verbatim from the manuscript taxonomy:

* Exogenous inputs
* Objective values
* Physical states or constraints
* Probability distributions / chance-constraint terms
* Decisions / solution-related objects

Classification is fail-closed. Strong target phrases in the title/abstract are
weighted more than PDF-body phrases. A target is emitted only when its score
passes the threshold and is separated from the runner-up. The output preserves
the evidence source and snippet so every plotted assignment can be audited.
"""

from __future__ import annotations

import csv
import multiprocessing as mp
import re
import sys
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Dict, Iterable, List, Tuple


ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tables"))
import build_table_T6_evidence_map as t6  # noqa: E402


CARDS = ROOT / "paper_library" / "sec8_evidence_cards.csv"
BIB = ROOT / "paper_library" / "review_paper_library.bib"
PDF_MAP = ROOT / "_tmp_pdf_author_title_match_map.csv"
LITERATUR = ROOT / "Literatur"
OUT = ROOT / "paper_library" / "surrogate_target_audit.csv"
SUMMARY = ROOT / "paper_library" / "surrogate_target_audit_summary.csv"


TARGET_ORDER = (
    "Exogenous inputs",
    "Objective values",
    "Physical states or constraints",
    "Probability distributions / chance-constraint terms",
    "Decisions / solution-related objects",
)


# Patterns are deliberately specific. Broad words such as "optimization",
# "model", "prediction", or "surrogate" are not target evidence.
TARGET_PATTERNS: Dict[str, Tuple[Tuple[str, int], ...]] = {
    "Exogenous inputs": (
        (r"\b(load|demand|wind power|wind speed|solar power|photovoltaic power|pv power|weather|electricity price|market price)\s+forecast(?:ing|s|ed)?\b", 5),
        (r"\bforecast(?:ing|s|ed)?\s+(load|demand|wind|solar|photovoltaic|pv|price|weather)\b", 5),
        (r"\b(exogenous|input)\s+(uncertaint(?:y|ies)|forecast|variable|data)\b", 4),
        (r"\bforecast(?:s|ed)?\s+(?:as|for)\s+(?:an?\s+)?input\b", 5),
    ),
    "Objective values": (
        (r"\b(objective function|objective value|fitness value|performance indicator|system performance)\b", 5),
        (r"\b(annual|total|operating|investment|capital|energy)\s+costs?\b", 4),
        (r"\b(cost|emission|energy demand|energy consumption|efficiency|revenue)\s+(?:and\s+\w+\s+)?(?:prediction|estimate|estimation|response|output)\b", 4),
        (r"\bapproximat(?:e|es|ed|ing)\s+(?:the\s+)?(?:annual\s+|total\s+|operating\s+)?(?:cost|emission|energy demand|objective|fitness|performance)\b", 6),
        (r"\bmetamodel\s+(?:of|for)\s+(?:the\s+)?(?:cost|energy|performance|objective)\b", 5),
    ),
    "Physical states or constraints": (
        (r"\b(voltage magnitude|voltage profile|line flow|power flow|load flow|network state|system state|storage state|indoor temperature|thermal state|hydraulic state)\b", 5),
        (r"\b(feasibility region|feasible region|constraint function|constraint violation|security constraint|stability constraint|conversion loss(?:es)?)\b", 5),
        (r"\bapproximat(?:e|es|ed|ing)\s+(?:the\s+)?(?:ac\s+)?(?:power flow|network|constraint|feasibility|voltage|temperature|thermal|hydraulic|loss)\b", 6),
        (r"\b(?:surrogate|proxy|emulator)\s+(?:for|of)\s+(?:the\s+)?(?:power flow|network state|constraint|feasibility|voltage|thermal|hydraulic|conversion loss)\b", 6),
        (r"\bphysics[- ](?:informed|guided|induced)\b", 3),
    ),
    "Probability distributions / chance-constraint terms": (
        (r"\b(probability distribution|predictive distribution|posterior variance|posterior uncertainty|predictive uncertainty)\b", 6),
        (r"\b(quantile regression|quantile function|prediction interval|credible interval|chance[- ]constraint term)\b", 6),
        (r"\b(polynomial chaos expansion|polynomial chaos|sparse pce|general polynomial chaos)\b", 5),
        (r"\buncertainty quantification\b", 5),
        (r"\bchance[- ]constrained\b", 4),
        (r"\bprobabilistic\s+(?:load flow|power flow|response|prediction|model)\b", 5),
    ),
    "Decisions / solution-related objects": (
        (r"\b(learning[- ]to[- ]optimi[sz]e|learning to solve optimization|optimization prox(?:y|ies)|solution proxy|solution map)\b", 7),
        (r"\b(predict|learn|approximate|return|generate)(?:s|ed|ing)?\s+(?:the\s+)?(?:optimal|near-optimal)\s+(?:solution|decision|dispatch|schedule|allocation|set[- ]point)\b", 7),
        (r"\b(dispatch vector|dispatch schedule|unit commitment status|on/off status|active set|optimal power allocation|market-clearing decision)\b", 7),
        (r"\bend[- ]to[- ]end\s+(?:feasible\s+)?optimization\b", 7),
        (r"\bsolve\s+(?:the\s+)?(?:economic dispatch|unit commitment|optimal power flow|opf)\s+(?:problem\s+)?(?:using|with)\s+(?:a\s+)?(?:neural|learning|data-driven)\b", 6),
    ),
}


def normalize(text: str) -> str:
    return re.sub(r"\s+", " ", text or "").strip().lower()


def extract_braced_field(block: str, field: str) -> str:
    """Read one brace-delimited BibTeX field without truncating nested braces."""
    match = re.search(rf"\b{re.escape(field)}\s*=\s*\{{", block, re.IGNORECASE)
    if not match:
        return ""
    start = match.end()
    depth = 1
    index = start
    while index < len(block) and depth:
        if block[index] == "{":
            depth += 1
        elif block[index] == "}":
            depth -= 1
        index += 1
    return re.sub(r"[{}]", "", block[start : index - 1]) if depth == 0 else ""


def load_bib_text() -> Dict[str, Dict[str, str]]:
    text = BIB.read_text(encoding="utf-8", errors="replace")
    starts = [match.start() for match in re.finditer(r"@\w+\s*\{", text)]
    starts.append(len(text))
    records: Dict[str, Dict[str, str]] = {}
    for start, end in zip(starts[:-1], starts[1:]):
        block = text[start:end]
        key_match = re.match(r"@\w+\s*\{\s*([^,]+),", block)
        if not key_match:
            continue
        key = key_match.group(1).strip()
        records[key] = {
            "title": extract_braced_field(block, "title"),
            "abstract": extract_braced_field(block, "abstract"),
            "keywords": extract_braced_field(block, "keywords")
            or extract_braced_field(block, "author_keywords"),
        }
    return records


def load_pdf_paths() -> Dict[str, Path]:
    paths: Dict[str, Path] = {}
    with PDF_MAP.open(encoding="utf-8", newline="") as handle:
        for row in csv.DictReader(handle):
            key = (row.get("mapped_key") or "").strip()
            rel = (row.get("pdf_relpath") or "").strip().replace("\\", "/")
            pdf = LITERATUR / rel
            if key and key not in paths and pdf.is_file():
                paths[key] = pdf
    return paths


def first_match(text: str, patterns: Iterable[Tuple[str, int]]) -> Tuple[int, str]:
    """Return accumulated score and a compact snippet around the best hit."""
    score = 0
    best_weight = 0
    best_snippet = ""
    for pattern, weight in patterns:
        matches = list(re.finditer(pattern, text, re.IGNORECASE))
        if not matches:
            continue
        # Repeated mentions add limited support without allowing references or
        # boilerplate to dominate the classification.
        score += weight + min(len(matches) - 1, 2)
        if weight > best_weight:
            match = matches[0]
            start = max(0, match.start() - 110)
            end = min(len(text), match.end() + 150)
            best_snippet = re.sub(r"\s+", " ", text[start:end]).strip()
            best_weight = weight
    return score, best_snippet


def classify(title: str, abstract: str, keywords: str, pdf_text: str) -> Dict[str, str]:
    """Score targets with title/abstract evidence dominating PDF-body evidence."""
    title_blob = normalize(title)
    abstract_blob = normalize(f"{abstract} {keywords}")
    # Initial pages contain abstract, methods and formulation. Limiting text
    # reduces false hits from literature-review and reference sections.
    pdf_blob = normalize(pdf_text[:30000])

    scores: Counter[str] = Counter()
    evidence: Dict[str, Tuple[str, str, int]] = {}
    for target, patterns in TARGET_PATTERNS.items():
        title_score, title_snippet = first_match(title_blob, patterns)
        abstract_score, abstract_snippet = first_match(abstract_blob, patterns)
        pdf_score, pdf_snippet = first_match(pdf_blob, patterns)

        # Explicit title and abstract language is strongest. PDF evidence is
        # useful but receives a lower weight because contextual mentions of
        # other methods may occur in introductions.
        weighted = title_score * 4 + abstract_score * 3 + pdf_score
        scores[target] = weighted
        candidates = [
            ("title", title_snippet, title_score * 4),
            ("abstract/keywords", abstract_snippet, abstract_score * 3),
            ("pdf", pdf_snippet, pdf_score),
        ]
        evidence[target] = max(candidates, key=lambda item: item[2])

    ranked = scores.most_common()
    best_target, best_score = ranked[0]
    second_target, second_score = ranked[1]
    source, snippet, source_score = evidence[best_target]

    # High confidence requires explicit evidence and separation from competing
    # targets. Borderline or genuinely multi-target studies remain unassigned.
    high = best_score >= 15 and best_score - second_score >= 5 and source_score >= 10
    status = "high" if high else "unassigned"
    return {
        "target": best_target if high else "",
        "confidence": status,
        "score": str(best_score),
        "runner_up": second_target,
        "runner_up_score": str(second_score),
        "evidence_source": source if high else "",
        "evidence_snippet": snippet if high else "",
        "all_scores": "; ".join(f"{target}={scores[target]}" for target in TARGET_ORDER),
    }


def extract_pdf_worker(path: str, queue: mp.Queue) -> None:
    """Extract a small initial-page window in an isolated process."""
    queue.put(t6.extract_pdf_text(Path(path), max_pages=6))


def extract_pdf_with_timeout(pdf: Path, timeout_seconds: int = 18) -> str:
    """Prevent one malformed or image-heavy PDF from blocking the audit."""
    queue: mp.Queue = mp.Queue(maxsize=1)
    process = mp.Process(target=extract_pdf_worker, args=(str(pdf), queue))
    process.start()
    process.join(timeout_seconds)
    if process.is_alive():
        process.terminate()
        process.join()
        return ""
    if queue.empty():
        return ""
    return queue.get()


def main() -> None:
    cards = read_cards()
    bib = load_bib_text()
    pdf_paths = load_pdf_paths()
    rows: List[Dict[str, str]] = []
    preliminary: Dict[str, Dict[str, str]] = {}
    pdf_candidates: Dict[str, Path] = {}

    for card in cards:
        key = card["cite_key"]
        bib_row = bib.get(key, {})
        pdf = pdf_paths.get(key)
        # First use title, abstract and keywords. PDF extraction is reserved for
        # cases that are not already unambiguous from bibliographic evidence.
        result = classify(
            bib_row.get("title") or card.get("system", ""),
            bib_row.get("abstract", ""),
            bib_row.get("keywords", ""),
            "",
        )
        preliminary[key] = result
        if result["confidence"] != "high" and pdf:
            pdf_candidates[key] = pdf

    # Each parser runs in its own timeout-controlled process. Threads only
    # coordinate those independent processes and bound total audit runtime.
    pdf_texts: Dict[str, str] = {}
    with ThreadPoolExecutor(max_workers=8) as executor:
        futures = {
            executor.submit(extract_pdf_with_timeout, pdf, 12): key
            for key, pdf in pdf_candidates.items()
        }
        for future in as_completed(futures):
            key = futures[future]
            pdf_texts[key] = future.result()

    for card in cards:
        key = card["cite_key"]
        bib_row = bib.get(key, {})
        result = preliminary[key]
        pdf_text = pdf_texts.get(key, "")
        if result["confidence"] != "high" and pdf_text:
            result = classify(
                bib_row.get("title") or card.get("system", ""),
                bib_row.get("abstract", ""),
                bib_row.get("keywords", ""),
                pdf_text,
            )
        rows.append(
            {
                "cite_key": key,
                "family": card.get("family", ""),
                "pattern": card.get("pattern", ""),
                "section": card.get("section", ""),
                "target": result["target"],
                "confidence": result["confidence"],
                "score": result["score"],
                "runner_up": result["runner_up"],
                "runner_up_score": result["runner_up_score"],
                "evidence_source": result["evidence_source"],
                "evidence_snippet": result["evidence_snippet"],
                "all_scores": result["all_scores"],
                "has_pdf_text": "yes" if len(pdf_text) > 200 else "no",
                "has_abstract": "yes" if bib_row.get("abstract") else "no",
            }
        )

    with OUT.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)

    summary_rows = []
    counts = Counter(row["target"] or "Unassigned" for row in rows)
    for label in (*TARGET_ORDER, "Unassigned"):
        summary_rows.append({"target": label, "n": counts[label]})
    with SUMMARY.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["target", "n"])
        writer.writeheader()
        writer.writerows(summary_rows)

    print(f"cards={len(rows)} high_confidence={sum(row['confidence'] == 'high' for row in rows)}")
    for row in summary_rows:
        print(f"{row['target']}: {row['n']}")
    print(f"wrote {OUT}")


def read_cards() -> List[Dict[str, str]]:
    with CARDS.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


if __name__ == "__main__":
    main()
