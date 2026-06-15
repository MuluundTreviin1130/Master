from __future__ import annotations

import csv
import re
from pathlib import Path

from convert_main_md_to_tex import SPLIT_CITE_REPLACEMENTS, keys_from_span, normalize_citation_spans


ROOT = Path(__file__).resolve().parent
REVIEW_ROOT = ROOT.parent
MD_SOURCE = ROOT / "main.md"
BIB_SOURCE = REVIEW_ROOT / "paper_library" / "review_paper_library.bib"
PDF_COVERAGE = REVIEW_ROOT / "_tmp_manuscript_cite_pdf_coverage.csv"
CONTEXT_AUDIT = REVIEW_ROOT / "_tmp_main_md_claim_context_audit.csv"
SUMMARY_OUT = REVIEW_ROOT / "_tmp_main_md_claim_context_audit_summary.md"


STOPWORDS = {
    "about",
    "across",
    "also",
    "because",
    "between",
    "could",
    "energy",
    "model",
    "models",
    "optimization",
    "paper",
    "review",
    "section",
    "surrogate",
    "surrogates",
    "system",
    "systems",
    "therefore",
    "these",
    "this",
    "through",
    "which",
    "while",
}


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


def parse_bib_entries() -> dict[str, str]:
    text = read_text(BIB_SOURCE)
    entries: dict[str, str] = {}
    for match in re.finditer(r"@\w+\s*\{\s*([^,]+),(.*?)(?=\n@\w+\s*\{|\Z)", text, flags=re.S):
        key = match.group(1).strip()
        body = match.group(2)
        fields = []
        for field in ("title", "abstract", "keywords", "journal", "booktitle"):
            field_match = re.search(field + r"\s*=\s*\{(.*?)\}\s*,", body, flags=re.I | re.S)
            if field_match:
                fields.append(field_match.group(1))
        entries[key] = " ".join(fields)
    return entries


def parse_pdf_counts() -> dict[str, int]:
    counts: dict[str, int] = {}
    if not PDF_COVERAGE.exists():
        return counts
    with PDF_COVERAGE.open("r", encoding="utf-8", newline="") as handle:
        for row in csv.DictReader(handle):
            try:
                counts[row["cite_key"]] = int(row.get("verified_pdf_count") or 0)
            except ValueError:
                counts[row["cite_key"]] = 0
    return counts


def tokens(text: str) -> set[str]:
    raw = re.findall(r"[A-Za-z][A-Za-z\-]{4,}", text.lower())
    return {token for token in raw if token not in STOPWORDS}


def iter_contexts(md: str):
    lines = md.splitlines()
    in_table = False
    paragraph: list[str] = []
    paragraph_start = 1

    def flush_paragraph():
        nonlocal paragraph
        if paragraph:
            text = " ".join(paragraph)
            start = paragraph_start
            paragraph = []
            return start, False, text
        return None

    for lineno, line in enumerate(lines, 1):
        stripped = line.strip()
        if stripped.startswith("::::") and "table*" in stripped:
            item = flush_paragraph()
            if item:
                yield item
            in_table = True
            continue
        if in_table and stripped in {"::::", ":::::"}:
            in_table = False
            continue
        if in_table:
            if "@" in line:
                yield lineno, True, line
            continue
        if not stripped:
            item = flush_paragraph()
            if item:
                yield item
            paragraph_start = lineno + 1
            continue
        if not paragraph:
            paragraph_start = lineno
        paragraph.append(line)

    item = flush_paragraph()
    if item:
        yield item


def citation_keys(context: str) -> list[str]:
    keys: list[str] = []
    for span in re.findall(r"\[[^\]]*@[^\]]*\]", context):
        keys.extend(keys_from_span(span))
    return sorted(set(keys))


def context_without_cites(context: str) -> str:
    return re.sub(r"\[[^\]]*@[^\]]*\]", "", context)


def main() -> None:
    md = normalize_citation_spans(read_text(MD_SOURCE))
    for split_key, normalized in SPLIT_CITE_REPLACEMENTS.items():
        md = md.replace(f"@{split_key}", f"@{normalized}")

    bib_entries = parse_bib_entries()
    pdf_counts = parse_pdf_counts()
    rows: list[dict[str, object]] = []

    for line_no, in_table, context in iter_contexts(md):
        keys = citation_keys(context)
        if not keys:
            continue
        context_tokens = tokens(context_without_cites(context))
        key_scores = []
        missing = []
        no_pdf = []
        weak_metadata = []
        for key in keys:
            evidence = bib_entries.get(key, "")
            if not evidence:
                missing.append(key)
                key_scores.append(f"{key}:missing_bib")
                continue
            overlap = sorted(context_tokens & tokens(evidence))
            score = len(overlap)
            if score < 2:
                weak_metadata.append(key)
            if pdf_counts.get(key, 0) == 0:
                no_pdf.append(key)
            key_scores.append(f"{key}:{score}")
        risk_flags = []
        if missing:
            risk_flags.append("missing_bib")
        if weak_metadata:
            risk_flags.append("weak_metadata_overlap")
        if no_pdf:
            risk_flags.append("no_verified_pdf")
        rows.append(
            {
                "line_no": line_no,
                "context_type": "table" if in_table else "paragraph",
                "cite_keys": ";".join(keys),
                "missing_bib_keys": ";".join(missing),
                "no_verified_pdf_keys": ";".join(no_pdf),
                "weak_metadata_keys": ";".join(weak_metadata),
                "key_overlap_scores": ";".join(key_scores),
                "risk_flags": ";".join(risk_flags),
                "context_excerpt": context_without_cites(context)[:500],
            }
        )

    with CONTEXT_AUDIT.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()) if rows else [])
        writer.writeheader()
        writer.writerows(rows)

    missing_rows = [row for row in rows if row["missing_bib_keys"]]
    weak_rows = [row for row in rows if row["weak_metadata_keys"]]
    no_pdf_rows = [row for row in rows if row["no_verified_pdf_keys"]]
    table_rows = [row for row in rows if row["context_type"] == "table"]
    summary = [
        "# main.md citation-context audit",
        "",
        f"- Contexts with citations: {len(rows)}",
        f"- Table contexts with citations: {len(table_rows)}",
        f"- Contexts with missing BibTeX keys: {len(missing_rows)}",
        f"- Contexts with at least one key lacking verified local PDF: {len(no_pdf_rows)}",
        f"- Contexts with weak title/abstract/keyword overlap: {len(weak_rows)}",
        "",
        "## Missing BibTeX contexts",
    ]
    for row in missing_rows[:25]:
        summary.append(
            f"- line {row['line_no']} ({row['context_type']}): {row['missing_bib_keys']} -- {row['context_excerpt']}"
        )
    summary.append("")
    summary.append("## Highest-priority weak/no-PDF contexts")
    for row in [r for r in rows if r["risk_flags"] and not r["missing_bib_keys"]][:40]:
        summary.append(
            f"- line {row['line_no']} ({row['context_type']}): {row['risk_flags']} -- {row['cite_keys']}"
        )
    SUMMARY_OUT.write_text("\n".join(summary) + "\n", encoding="utf-8", newline="\n")

    print(f"wrote {CONTEXT_AUDIT}")
    print(f"wrote {SUMMARY_OUT}")
    print(f"contexts={len(rows)} missing_contexts={len(missing_rows)} no_pdf_contexts={len(no_pdf_rows)} weak_contexts={len(weak_rows)}")


if __name__ == "__main__":
    main()
