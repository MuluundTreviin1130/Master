"""Extract DOIs from the merged review PDF ``Reviews zusammen.pdf`` and map
them to ``review_paper_library.bib`` citation keys (DOI-normalised index).

Outputs (next to this script):

- ``reviews_zusammen_pdf_doi_map.json`` — machine-readable map
- ``reviews_zusammen_pdf_doi_map.md`` — human-readable summary

Run::

    py map_reviews_zusammen_pdf.py

Override paths with env vars ``REVIEWS_ZUSAMMEN_PDF`` and ``PAPER_LIBRARY_BIB``
if needed.
"""

from __future__ import annotations

import json
import os
import re
from pathlib import Path

DOI_RE = re.compile(r"10\.\d{4,9}/[^\s\]\}\"'>,\)\}]+", re.I)


def norm_doi(s: str) -> str:
    s = s.strip().rstrip(".,;)")
    s = re.sub(r"^https?://(dx\.)?doi\.org/", "", s, flags=re.I)
    return s.lower()


def parse_bib_doi_index(bib_text: str) -> tuple[dict[str, list[str]], dict[str, str]]:
    """Return (doi_lower -> [cite_keys], cite_key -> doi_lower)."""

    doi_to_keys: dict[str, list[str]] = {}
    key_to_doi: dict[str, str] = {}
    for m in re.finditer(r"@(\w+)\{([^,]+),\s*", bib_text):
        key = m.group(2)
        start = m.end()
        nxt = bib_text.find("@", start)
        block = bib_text[start:] if nxt == -1 else bib_text[start:nxt]
        dm = re.search(r"doi\s*=\s*\{([^}]+)\}", block, re.I)
        if not dm:
            continue
        d = norm_doi(dm.group(1))
        key_to_doi[key] = d
        doi_to_keys.setdefault(d, []).append(key)
    return doi_to_keys, key_to_doi


def main() -> int:
    here = Path(__file__).resolve().parent
    pdf = Path(
        os.environ.get(
            "REVIEWS_ZUSAMMEN_PDF",
            r"c:\Users\Philipp Thunshirn\Desktop\PhD\Papers\Journals\Review\Literatur\Reviews\Reviews zusammen.pdf",
        )
    )
    bib = Path(
        os.environ.get(
            "PAPER_LIBRARY_BIB",
            str(here / "review_paper_library.bib"),
        )
    )
    if not pdf.exists():
        print(f"Missing PDF: {pdf}")
        return 1
    if not bib.exists():
        print(f"Missing bib: {bib}")
        return 1

    bib_text = bib.read_text(encoding="utf-8", errors="replace")
    doi_to_keys, _key_to_doi = parse_bib_doi_index(bib_text)

    import fitz  # PyMuPDF

    found: set[str] = set()
    with fitz.open(str(pdf)) as doc:
        n_pages = doc.page_count
        for i in range(n_pages):
            text = doc[i].get_text()
            for d in DOI_RE.findall(text):
                found.add(norm_doi(d))
            if (i + 1) % 100 == 0:
                print(f"pages {i + 1}/{n_pages} unique_dois {len(found)}")

    matched: list[tuple[str, list[str]]] = []
    missing: list[str] = []
    for d in sorted(found):
        if d in doi_to_keys:
            matched.append((d, doi_to_keys[d]))
        else:
            missing.append(d)

    stats = {
        "pdf_path": str(pdf),
        "bib_path": str(bib),
        "pdf_pages": n_pages,
        "unique_dois_in_pdf": len(found),
        "matched_in_library": len(matched),
        "doi_in_pdf_not_in_library": len(missing),
    }
    payload = {
        "stats": stats,
        "matched": {d: ks for d, ks in matched},
        "missing_in_library": missing,
    }
    (here / "reviews_zusammen_pdf_doi_map.json").write_text(
        json.dumps(payload, indent=2),
        encoding="utf-8",
    )

    lines = [
        "# DOI → cite_key (``Reviews zusammen.pdf``)",
        "",
        f"- PDF pages: **{n_pages}**",
        f"- Unique DOIs detected in PDF: **{len(found)}**",
        f"- Matched to ``review_paper_library.bib``: **{len(matched)}**",
        f"- DOIs in PDF but **not** in library: **{len(missing)}**",
        "",
        "## Matched",
        "",
    ]
    for d, ks in sorted(matched, key=lambda x: x[0]):
        lines.append(f"- `{d}` → `{', '.join(ks)}`")
    lines.extend(["", "## Not in library (first 300)", ""])
    for d in sorted(missing)[:300]:
        lines.append(f"- `{d}`")
    if len(missing) > 300:
        lines.append(f"- … *{len(missing) - 300} more in JSON*")
    (here / "reviews_zusammen_pdf_doi_map.md").write_text(
        "\n".join(lines) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(stats, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
