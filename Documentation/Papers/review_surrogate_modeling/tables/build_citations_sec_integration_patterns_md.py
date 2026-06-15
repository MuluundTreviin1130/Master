"""Emit markdown table: Key | DOI | Title | Venue for 06_integration_patterns.tex cites.

Run:

    py -3 Documentation/Papers/review_surrogate_modeling/tables/build_citations_sec_integration_patterns_md.py

Writes: tables/citations_sec_integration_patterns_key_doi_title_venue.md
"""
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TEX = ROOT / "manuscript" / "06_integration_patterns.tex"
BIB = ROOT / "references" / "review_mes_moo_surrogates.bib"
OUT = Path(__file__).resolve().parent / "citations_sec_integration_patterns_key_doi_title_venue.md"


def _extract_braced_value(block: str, field: str) -> str | None:
    m = re.search(rf"(?ms)^\s*{re.escape(field)}\s*=\s*\{{", block)
    if not m:
        return None
    i = m.end()
    depth = 1
    start = i
    while i < len(block) and depth:
        ch = block[i]
        if ch == "\\" and i + 1 < len(block):
            i += 2
            continue
        if ch == "{":
            depth += 1
            i += 1
            continue
        if ch == "}":
            depth -= 1
            if depth == 0:
                return block[start:i].strip()
            i += 1
            continue
        i += 1
    return None


def _venue(block: str) -> str:
    for fld in ("journal", "booktitle", "publisher", "school", "institution"):
        v = _extract_braced_value(block, fld)
        if v:
            return re.sub(r"\s+", " ", v)
    return ""


def _md_cell(s: str) -> str:
    return s.replace("|", "\\|")


def main() -> None:
    tex = TEX.read_text(encoding="utf-8")
    keys: set[str] = set()
    for m in re.finditer(r"\\cite\{([^}]+)\}", tex):
        for k in m.group(1).split(","):
            keys.add(k.strip())

    bib = BIB.read_text(encoding="utf-8", errors="replace")
    pat = re.compile(r"@\w+\s*\{\s*([^,]+?)\s*,\s*", re.MULTILINE)
    blocks: dict[str, str] = {}
    for m in pat.finditer(bib):
        cid = m.group(1).strip()
        start = m.start()
        nxt = pat.search(bib, m.end())
        end = nxt.start() if nxt else len(bib)
        blocks[cid] = bib[start:end]

    lines = [
        "# Integration patterns section — citations (overview)",
        "",
        "Generated from `manuscript/06_integration_patterns.tex` → "
        "`references/review_mes_moo_surrogates.bib`.",
        "**Venue** = journal, or conference/book series (`booktitle` / `publisher`).",
        "",
        "| BibTeX-Key | DOI | Titel | Verlag / Serie |",
        "|---|---|---|---|",
    ]

    for k in sorted(keys):
        blk = blocks.get(k)
        if not blk:
            lines.append(f"| {_md_cell(k)} | — | *(fehlt in .bib)* | — |")
            continue
        title = _extract_braced_value(blk, "title") or ""
        title = re.sub(r"\s+", " ", title)
        doi_m = re.search(r"(?msi)^\s*doi\s*=\s*\{([^}]*)\}", blk)
        doi = doi_m.group(1).strip() if doi_m else ""
        venue = _venue(blk)
        lines.append(
            "| "
            + " | ".join(_md_cell(x) for x in (k, doi, title, venue))
            + " |"
        )

    OUT.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"Wrote {OUT.relative_to(ROOT)} ({len(keys)} keys)")


if __name__ == "__main__":
    main()
