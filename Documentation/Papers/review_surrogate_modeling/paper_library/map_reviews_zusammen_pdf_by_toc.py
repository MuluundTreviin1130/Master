"""Map merged ``Reviews zusammen.pdf`` articles to ``review_paper_library``
cite_keys.

The PDF outline (TOC) titles are reliable, but *bookmark page numbers* are
often wrong after ``PDF24`` merging (many entries still say page~1). We
therefore **search the document** for a short prefix of each level-1 title
and anchor the DOI scan on the **found page**.

Outputs:

- ``reviews_zusammen_pdf_toc_map.md`` / ``.json`` — unique DOI → cite_key list

Run::

    py map_reviews_zusammen_pdf_by_toc.py
"""

from __future__ import annotations

import json
import os
import re
import unicodedata
from pathlib import Path

DOI_RE = re.compile(r"10\.\d{4,9}/[^\s\]\}\"'>,\)\}]+", re.I)


def norm_doi(s: str) -> str:
    s = s.strip().rstrip(".,;)")
    s = re.sub(r"^https?://(dx\.)?doi\.org/", "", s, flags=re.I)
    return s.lower()


def parse_bib_doi_index(bib_text: str) -> dict[str, list[str]]:
    doi_to_keys: dict[str, list[str]] = {}
    for m in re.finditer(r"@(\w+)\{([^,]+),\s*", bib_text):
        key = m.group(2)
        start = m.end()
        nxt = bib_text.find("@", start)
        block = bib_text[start:] if nxt == -1 else bib_text[start:nxt]
        dm = re.search(r"doi\s*=\s*\{([^}]+)\}", block, re.I)
        if not dm:
            continue
        d = norm_doi(dm.group(1))
        doi_to_keys.setdefault(d, []).append(key)
    return doi_to_keys


def fold(s: str) -> str:
    s = unicodedata.normalize("NFKD", s)
    return "".join(c for c in s if not unicodedata.combining(c))


def plausible_article_title(title: str) -> bool:
    t = title.strip()
    if len(t) < 25:
        return False
    low = fold(t).lower()
    skip = (
        "introduction",
        "references",
        "acknowledg",
        "appendix",
        "credit",
        "declaration",
        "data availability",
        "supplementary",
        "nomenclature",
        "institutional release",
        "conflict of interest",
        "remarks on the topology",
        "microgrid sizing approaches",
        "microgrid energy management",
        "discussion",
        "conclusions",
        "materials and methods",
        "results and discussion",
        "references",
    )
    if any(low.startswith(s) for s in skip):
        return False
    return True


def title_search_prefix(title: str, max_len: int = 55) -> str:
    """Short literal prefix for ``search_for`` (avoid special chars)."""

    t = fold(title.replace("\u00a0", " "))
    t = re.sub(r"\s+", " ", t).strip()
    if len(t) <= max_len:
        return t
    # break at last space before max_len
    cut = t[:max_len]
    sp = cut.rfind(" ")
    return cut if sp < 20 else cut[:sp]


def first_doi_on_pages(doc, page0: int, n_pages: int = 3) -> str | None:
    for i in range(page0, min(page0 + n_pages, doc.page_count)):
        text = doc[i].get_text()
        m = DOI_RE.search(text)
        if m:
            return norm_doi(m.group(0))
    return None


def locate_title_page(doc, title: str, hint_page0: int) -> int | None:
    """Return 0-based page index where title appears, or None."""

    prefix = title_search_prefix(title)
    if len(prefix) < 12:
        return None
    # search hint window first (bookmark might be correct)
    for p in range(max(0, hint_page0 - 2), min(doc.page_count, hint_page0 + 40)):
        hits = doc[p].search_for(prefix[:40], quads=False)
        if hits:
            return p
    # full scan (slow once)
    for p in range(doc.page_count):
        hits = doc[p].search_for(prefix[:40], quads=False)
        if hits:
            return p
    return None


def main() -> int:
    here = Path(__file__).resolve().parent
    pdf = Path(
        os.environ.get(
            "REVIEWS_ZUSAMMEN_PDF",
            r"c:\Users\Philipp Thunshirn\Desktop\PhD\Papers\Journals\Review\Literatur\Reviews\Reviews zusammen.pdf",
        )
    )
    bib = Path(os.environ.get("PAPER_LIBRARY_BIB", str(here / "review_paper_library.bib")))
    if not pdf.exists() or not bib.exists():
        print("missing pdf or bib")
        return 1

    doi_to_keys = parse_bib_doi_index(bib.read_text(encoding="utf-8", errors="replace"))

    import fitz

    articles: list[dict] = []
    with fitz.open(str(pdf)) as doc:
        toc = doc.get_toc()
        l1 = [(t[1].strip(), int(t[2])) for t in toc if t[0] == 1]
        seen: set[str] = set()
        uniq: list[tuple[str, int]] = []
        for title, p in l1:
            if title in seen:
                continue
            seen.add(title)
            uniq.append((title, p))

        for title, bookmark_page1 in uniq:
            if not plausible_article_title(title):
                continue
            hint0 = max(0, bookmark_page1 - 1)
            found0 = locate_title_page(doc, title, hint0)
            if found0 is None:
                articles.append(
                    {
                        "toc_title": title,
                        "bookmark_page_1based": bookmark_page1,
                        "search_page_1based": None,
                        "doi_guess": None,
                        "cite_keys": [],
                        "in_library": False,
                        "note": "title not found in PDF text",
                    }
                )
                continue
            doi = first_doi_on_pages(doc, found0, n_pages=3)
            keys = doi_to_keys.get(doi, []) if doi else []
            articles.append(
                {
                    "toc_title": title,
                    "bookmark_page_1based": bookmark_page1,
                    "search_page_1based": found0 + 1,
                    "doi_guess": doi,
                    "cite_keys": keys,
                    "in_library": bool(keys),
                    "note": "",
                }
            )

    # unique by DOI (one row per paper)
    by_doi: dict[str, dict] = {}
    for a in articles:
        d = a.get("doi_guess")
        if not d or not a["cite_keys"]:
            continue
        if d not in by_doi:
            by_doi[d] = {
                "doi": d,
                "cite_keys": a["cite_keys"],
                "toc_title": a["toc_title"],
                "search_page_1based": a["search_page_1based"],
            }

    matched = sorted(by_doi.values(), key=lambda x: x["toc_title"].lower())
    no_doi = [a for a in articles if not a.get("doi_guess")]
    doi_not_lib = [a for a in articles if a.get("doi_guess") and not a["cite_keys"]]

    stats = {
        "pdf": str(pdf),
        "toc_level1_unique_titles": len(uniq),
        "plausible_article_titles": len(articles),
        "unique_dois_matched_to_library": len(matched),
        "title_not_found": len([a for a in articles if a.get("note")]),
        "doi_found_but_not_in_library": len(doi_not_lib),
    }
    payload = {
        "stats": stats,
        "unique_articles_matched": matched,
        "doi_not_in_library": doi_not_lib,
        "no_doi_or_failed": no_doi,
    }
    (here / "reviews_zusammen_pdf_toc_map.json").write_text(
        json.dumps(payload, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    lines = [
        "# ``Reviews zusammen.pdf`` → cite_key (Titelsuche + DOI)",
        "",
        f"- Eindeutige Artikel mit DOI-Match in ``review_paper_library.bib``: **{len(matched)}**",
        f"- DOI gefunden, aber nicht in der Library: **{len(doi_not_lib)}**",
        f"- Titel im PDF-Text nicht auffindbar: **{len([a for a in articles if a.get('note')])}**",
        "",
        "## Eindeutige Zuordnung (DOI → cite_key)",
        "",
    ]
    for row in matched:
        ck = ", ".join(row["cite_keys"])
        lines.append(
            f"- `{ck}` ← `{row['doi']}` (TOC: _{row['toc_title'][:100]}…_, erste Fundseite ≈ S. {row['search_page_1based']})"
            if len(row["toc_title"]) > 100
            else f"- `{ck}` ← `{row['doi']}` (_{row['toc_title']}_, erste Fundseite ≈ S. {row['search_page_1based']})"
        )
    if doi_not_lib:
        lines.extend(["", "## DOI nicht in der Paper-Library", ""])
        for a in doi_not_lib:
            lines.append(
                f"- `{a['doi_guess']}` — {a['toc_title'][:120]}"
            )
    if no_doi:
        lines.extend(["", "## Kein DOI / Titelsuche fehlgeschlagen", ""])
        for a in no_doi[:25]:
            lines.append(f"- {a['toc_title'][:100]} … — {a.get('note', '')}")
    (here / "reviews_zusammen_pdf_toc_map.md").write_text(
        "\n".join(lines) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(stats, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
