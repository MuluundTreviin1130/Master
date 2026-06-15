"""Extract auditable contexts for incomplete four-stage alluvial paths.

The automatic audit intentionally fails closed. This helper supports the next
manual adjudication step by collecting the most relevant abstract and PDF
passages for records that have exactly one unresolved dimension. It does not
assign labels. Every later override therefore remains tied to a page-numbered
passage that can be checked independently.
"""

from __future__ import annotations

import csv
import re
from pathlib import Path

from build_alluvial_fulltext_followup import extract_article_pages
from build_surrogate_target_audit import load_bib_text, load_pdf_paths


ROOT = Path(__file__).resolve().parent.parent
AUDIT = ROOT / "paper_library" / "alluvial_evidence_audit_followup.csv"
OUT = ROOT / "paper_library" / "alluvial_adjudication_contexts.csv"
DIMENSIONS = ("family", "doe", "pattern", "validation")

# Terms mirror the manuscript taxonomy. Broad workflow words are included only
# to locate candidate passages; they never become classifications by themselves.
DIMENSION_TERMS = {
    "family": re.compile(
        r"\b(polynomial chaos|response surface|gaussian process|kriging|"
        r"neural network|radial basis|support vector|random forest|"
        r"gradient boosting|xgboost|lightgbm|surrogate|metamodel)\b",
        re.IGNORECASE,
    ),
    "doe": re.compile(
        r"\b(latin hypercube|sobol|halton|sparse grid|factorial design|"
        r"response surface design|adaptive sampling|active learning|"
        r"multi[- ]fidelity|transfer learning|training data|training set|"
        r"historical data|operational data|measured data|simulation data|"
        r"synthetic data|design points|sample points)\b",
        re.IGNORECASE,
    ),
    "pattern": re.compile(
        r"\b(surrogate[- ]assisted|surrogate[- ]based|bayesian optimization|"
        r"expected improvement|acquisition function|replace|substitute|proxy|"
        r"approximate|predict.+optimal|solution mapping|learning[- ]to[- ]"
        r"optimi[sz]e|benders|column generation|recourse|value function|"
        r"chance constraint|robust optimi[sz]ation|uncertainty propagation|"
        r"optimization|optimisation|dispatch|unit commitment|power flow)\b",
        re.IGNORECASE,
    ),
    "validation": re.compile(
        r"\b(rmse|nrmse|mae|mse|mape|r[- ]?squared|prediction accuracy|"
        r"relative error|constraint violation|feasibility rate|optimality gap|"
        r"regret|cost gap|objective gap|uncertainty quantification|"
        r"uncertainty propagation|coverage probability|prediction interval|"
        r"stress test|out[- ]of[- ]distribution)\b",
        re.IGNORECASE,
    ),
}

# First-person and study-specific language increases the chance that a passage
# describes the focal paper rather than another method cited in the introduction.
OWN_USE = re.compile(
    r"\b(we (?:use|used|employ|employed|develop|developed|propose|proposed|"
    r"train|trained|construct|constructed|generate|generated|evaluate|evaluated)|"
    r"our (?:model|method|approach|framework|surrogate|study|results)|"
    r"this (?:paper|study|work) (?:uses|used|develops|developed|proposes|"
    r"proposed|presents|presented|evaluates|evaluated))\b",
    re.IGNORECASE,
)
RELATED_WORK = re.compile(
    r"\b(previous|prior|earlier|other|existing|literature|review|survey|"
    r"has been proposed|have been proposed|researchers|authors)\b",
    re.IGNORECASE,
)
CITATION = re.compile(r"(?:\[[0-9,\-– ]+\]|\([A-Z][A-Za-z-]+ et al\.,? \d{4}\))")
SENTENCE_SPLIT = re.compile(r"(?<=[.!?])\s+(?=[A-Z0-9])")


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def normalize(text: str) -> str:
    return re.sub(r"\s+", " ", text or "").strip()


def candidate_windows(text: str) -> list[str]:
    """Return compact three-sentence windows without fabricating boundaries."""
    sentences = [normalize(value) for value in SENTENCE_SPLIT.split(text)]
    sentences = [value for value in sentences if len(value) >= 35]
    windows = []
    for index, sentence in enumerate(sentences):
        start = max(0, index - 1)
        end = min(len(sentences), index + 2)
        windows.append(" ".join(sentences[start:end]))
    return windows


def score_context(dimension: str, text: str, source: str) -> int:
    """Rank evidence passages while leaving classification to adjudication."""
    term_hits = len(DIMENSION_TERMS[dimension].findall(text))
    if term_hits == 0:
        return 0
    score = min(term_hits, 5) * 3
    score += 5 if OWN_USE.search(text) else 0
    score += 2 if source == "abstract" else 0
    score -= 3 if RELATED_WORK.search(text) else 0
    score -= 2 if CITATION.search(text) and not OWN_USE.search(text) else 0
    return score


def main() -> None:
    audit_rows = read_csv(AUDIT)
    bib = load_bib_text()
    pdf_paths = load_pdf_paths()
    output = []

    for audit_row in audit_rows:
        missing = [
            dimension
            for dimension in DIMENSIONS
            if audit_row.get(f"{dimension}_confidence") != "high"
        ]
        if len(missing) != 1:
            continue

        key = audit_row["cite_key"]
        dimension = missing[0]
        contexts: list[tuple[int, str, str, str]] = []

        abstract = normalize(bib.get(key, {}).get("abstract", ""))
        for passage in candidate_windows(abstract):
            score = score_context(dimension, passage, "abstract")
            if score > 0:
                contexts.append((score, "abstract", "", passage))

        pdf = pdf_paths.get(key)
        if pdf:
            for page_number, page_text in extract_article_pages(pdf):
                for passage in candidate_windows(page_text):
                    score = score_context(dimension, passage, "pdf")
                    if score > 0:
                        contexts.append(
                            (score, "pdf", str(page_number), passage)
                        )

        # Deduplicate repeated abstract/header text and retain enough alternatives
        # to expose both the method description and the validation/results passage.
        seen = set()
        ranked = []
        for score, source, page, passage in sorted(
            contexts,
            key=lambda value: (-value[0], value[1] != "abstract", value[2]),
        ):
            fingerprint = re.sub(r"[^a-z0-9]+", "", passage.lower())[:220]
            if fingerprint in seen:
                continue
            seen.add(fingerprint)
            ranked.append((score, source, page, passage))
            if len(ranked) == 10:
                break

        if not ranked:
            output.append(
                {
                    "cite_key": key,
                    "title": audit_row["title"],
                    "missing_dimension": dimension,
                    "rank": "",
                    "score": "0",
                    "source": "",
                    "page": "",
                    "own_use_signal": "no",
                    "related_work_signal": "no",
                    "context": "",
                }
            )
            continue

        for rank, (score, source, page, passage) in enumerate(ranked, start=1):
            output.append(
                {
                    "cite_key": key,
                    "title": audit_row["title"],
                    "missing_dimension": dimension,
                    "rank": str(rank),
                    "score": str(score),
                    "source": source,
                    "page": page,
                    "own_use_signal": "yes" if OWN_USE.search(passage) else "no",
                    "related_work_signal": (
                        "yes" if RELATED_WORK.search(passage) else "no"
                    ),
                    "context": passage,
                }
            )

    if not output:
        raise RuntimeError("No one-missing-dimension records found.")
    with OUT.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(output[0].keys()))
        writer.writeheader()
        writer.writerows(output)
    print(f"records={len({row['cite_key'] for row in output})}")
    print(f"contexts={len(output)}")
    print(f"wrote {OUT}")


if __name__ == "__main__":
    main()
