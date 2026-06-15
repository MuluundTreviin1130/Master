"""Enrich the screening CSV with OpenAlex metadata.

For every entry in ``surrogates_esm_screening.csv`` that has a DOI, this
script queries the public OpenAlex Works API and adds:

- ``oa_status``               : open / closed / hybrid / bronze / green
- ``oa_pdf_url``              : best free PDF URL OpenAlex knows about
- ``cited_by_count``          : OpenAlex citation count
- ``referenced_works_count``  : how many references the paper itself has
- ``primary_topic``           : OpenAlex primary topic display name
- ``oa_full_text_available``  : 1 if ``oa_pdf_url`` is set, else 0
- ``read_priority``           : simple heuristic ranking
                                 (``high`` if cited_by_count >= 50 OR is a
                                 review or survey, ``medium`` if 10..49,
                                 ``low`` otherwise)

Why OpenAlex: free, no API key required for this volume, very accurate
DOI lookup and OA-detection. We add a polite mailto for the "polite
pool" (faster, more reliable rate limits) and we cache responses so the
script is restartable.

Usage::

    python enrich_openalex.py \
        --in surrogates_esm_screening.csv \
        --out surrogates_esm_screening_enriched.csv \
        --mailto your.address@example.com

The script never overwrites the input file; it always writes to a new
output file. The cache lives at ``.openalex_cache.jsonl`` so a second run
only fetches DOIs that were not seen before.
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Dict, Iterable, Optional


# ---------------------------------------------------------------------------
# OpenAlex client
# ---------------------------------------------------------------------------
#
# We deliberately use only ``urllib`` from the standard library so this
# script stays dependency-free and runs on any plain Python install.
# OpenAlex' API is pleasant: a single GET per DOI returns everything we
# care about, and the public rate limit (10 requests/second) is more
# than enough.

OPENALEX_ENDPOINT = "https://api.openalex.org/works/doi:"


def fetch_one(doi: str, mailto: Optional[str], timeout: float = 20.0) -> Dict:
    """Fetch a single Work by DOI from OpenAlex.

    Returns the parsed JSON dict on success, or ``{}`` on any error so
    the caller does not have to wrap each call in a try/except. Errors
    are logged on stderr to keep the main loop simple and resumable.
    """

    # Normalize the DOI: OpenAlex expects the bare ``10.xxxx/...`` form,
    # without ``https://doi.org/`` or trailing whitespace.
    doi_norm = doi.strip()
    if doi_norm.lower().startswith("https://doi.org/"):
        doi_norm = doi_norm[len("https://doi.org/"):]
    if doi_norm.lower().startswith("doi:"):
        doi_norm = doi_norm[4:]

    if not doi_norm:
        return {}

    # URL-encode the DOI; some entries contain ``/`` and uppercase letters.
    url = OPENALEX_ENDPOINT + urllib.parse.quote(doi_norm, safe="")
    if mailto:
        url += "?mailto=" + urllib.parse.quote(mailto, safe="@.")

    req = urllib.request.Request(url, headers={"User-Agent": "review-surrogate-modeling/1.0"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except Exception as exc:
        sys.stderr.write(f"  openalex: {doi_norm}: {exc}\n")
        return {}


def best_oa_pdf(work: Dict) -> str:
    """Return the best free PDF URL for a Work, or '' if none is known.

    OpenAlex stores OA pointers in several places; we check them in
    decreasing order of trustworthiness so the first hit is good enough
    for "is this freely downloadable in one click?".
    """

    best = work.get("best_oa_location") or {}
    if best.get("pdf_url"):
        return best["pdf_url"]
    primary = work.get("primary_location") or {}
    if primary.get("is_oa") and primary.get("pdf_url"):
        return primary["pdf_url"]
    for loc in work.get("locations", []) or []:
        if loc.get("is_oa") and loc.get("pdf_url"):
            return loc["pdf_url"]
    return ""


def is_review_like(work: Dict) -> bool:
    """Heuristic: does this look like a review / survey paper?

    OpenAlex stores ``type`` (``article``, ``review``, …) and we also
    check the title for the typical review markers. Reviews are
    high-priority for full-text reading even when their citation count
    is still small, because they are how we anchor the manuscript's
    narrative arcs.
    """

    if (work.get("type") or "").lower() == "review":
        return True
    title = (work.get("title") or "").lower()
    return any(kw in title for kw in ("review", "survey", "roadmap", "state of the art"))


def read_priority(work: Dict) -> str:
    """Bucket each work into ``high`` / ``medium`` / ``low`` for triage.

    The heuristic is intentionally simple: we want the user to know
    where to focus full-text reading time. Reviews are forced to
    ``high`` so the narrative anchors are read first.
    """

    if not work:
        return ""
    if is_review_like(work):
        return "high"
    cit = work.get("cited_by_count") or 0
    if cit >= 50:
        return "high"
    if cit >= 10:
        return "medium"
    return "low"


# ---------------------------------------------------------------------------
# Cache helpers
# ---------------------------------------------------------------------------


def load_cache(path: Path) -> Dict[str, Dict]:
    """Load the JSONL cache mapping ``doi -> openalex_json``.

    Each line is one JSON object ``{"doi": ..., "work": ...}``. We use
    JSONL rather than a single big JSON so an interrupted run still
    yields a parseable cache for the next attempt.
    """

    if not path.exists():
        return {}
    cache: Dict[str, Dict] = {}
    with path.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                rec = json.loads(line)
            except json.JSONDecodeError:
                continue
            doi = rec.get("doi")
            if doi:
                cache[doi.lower()] = rec.get("work") or {}
    return cache


def append_cache(path: Path, doi: str, work: Dict) -> None:
    """Append a single record to the JSONL cache."""

    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps({"doi": doi, "work": work}, ensure_ascii=False) + "\n")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def iter_csv_rows(path: Path) -> Iterable[Dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        yield from reader


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--in",
        dest="in_csv",
        type=Path,
        default=Path("surrogates_esm_screening.csv"),
        help="screening CSV produced by filter_bib.py",
    )
    parser.add_argument(
        "--out",
        dest="out_csv",
        type=Path,
        default=Path("surrogates_esm_screening_enriched.csv"),
        help="output CSV with OpenAlex columns appended",
    )
    parser.add_argument(
        "--cache",
        type=Path,
        default=Path(".openalex_cache.jsonl"),
        help="JSONL cache so re-runs are cheap",
    )
    parser.add_argument(
        "--mailto",
        type=str,
        default="",
        help="email for the OpenAlex polite pool (recommended)",
    )
    parser.add_argument(
        "--only-tier-a",
        action="store_true",
        help="only enrich Tier A entries (default: all rows with a DOI)",
    )
    parser.add_argument(
        "--max",
        type=int,
        default=0,
        help="stop after N new fetches (0 means no limit)",
    )
    parser.add_argument(
        "--rate-sleep",
        type=float,
        default=0.12,
        help="seconds to sleep between fetches (default 0.12 = ~8 req/s)",
    )
    args = parser.parse_args(argv)

    if not args.in_csv.exists():
        sys.stderr.write(f"error: input csv not found: {args.in_csv}\n")
        return 2

    cache = load_cache(args.cache)
    print(f"Cache: {len(cache)} cached DOIs in {args.cache}")

    rows = list(iter_csv_rows(args.in_csv))
    print(f"Read {len(rows)} rows from {args.in_csv}")

    fieldnames = list(rows[0].keys()) + [
        "oa_status",
        "oa_pdf_url",
        "cited_by_count",
        "referenced_works_count",
        "primary_topic",
        "oa_full_text_available",
        "read_priority",
    ]

    fetched = 0
    stop_fetching = False  # set once --max is hit; we then only read from cache
    enriched_rows: list[Dict[str, str]] = []
    for i, row in enumerate(rows, 1):
        doi = (row.get("doi") or "").strip().lower()
        tier = row.get("tier", "")
        do_enrich = bool(doi) and (not args.only_tier_a or tier == "A")

        work: Dict = {}
        if do_enrich:
            if doi in cache:
                # The cache is the cheap path; it never counts against --max.
                work = cache[doi]
            elif not stop_fetching:
                work = fetch_one(doi, mailto=args.mailto)
                append_cache(args.cache, doi, work)
                fetched += 1
                if args.rate_sleep > 0:
                    time.sleep(args.rate_sleep)
                if args.max and fetched >= args.max:
                    sys.stderr.write(
                        f"reached --max={args.max} fetches; "
                        "remaining rows will only be enriched from cache\n"
                    )
                    stop_fetching = True
            # else: skipping this DOI silently because --max was reached.

            if (i % 200) == 0:
                print(f"  ... processed {i}/{len(rows)} rows, fetched {fetched} new")

        if work:
            row["oa_status"] = (work.get("open_access") or {}).get("oa_status", "") or ""
            row["oa_pdf_url"] = best_oa_pdf(work)
            row["cited_by_count"] = str(work.get("cited_by_count") or "")
            row["referenced_works_count"] = str(work.get("referenced_works_count") or "")
            primary = work.get("primary_topic") or {}
            row["primary_topic"] = primary.get("display_name", "") if primary else ""
            row["oa_full_text_available"] = "1" if row["oa_pdf_url"] else "0"
            row["read_priority"] = read_priority(work)
        else:
            row["oa_status"] = ""
            row["oa_pdf_url"] = ""
            row["cited_by_count"] = ""
            row["referenced_works_count"] = ""
            row["primary_topic"] = ""
            row["oa_full_text_available"] = ""
            row["read_priority"] = ""

        enriched_rows.append(row)

    with args.out_csv.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for r in enriched_rows:
            writer.writerow(r)

    print()
    print(f"Wrote {len(enriched_rows)} rows to {args.out_csv}")
    print(f"New fetches this run: {fetched}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
