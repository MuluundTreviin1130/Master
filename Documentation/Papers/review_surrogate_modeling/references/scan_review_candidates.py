"""Scan the full deduplicated bibliography for review papers
relevant to the Surrogates x MOO x MES intersection. The classifier
combines three signal sources -- title, abstract and author keywords
-- and flags an entry as a review only when at least one of the
sources carries an unambiguous review marker.

Sources:
- references/review_mes_moo_surrogates.bib           -> abstract + keywords
- references/review_mes_moo_surrogates_manifest.csv  -> all 2906 entries
- references/surrogates_esm_screening_enriched.csv   -> citation counts,
                                                        primary topic

Filter logic: each entry is scored on three axes; a review-flag
fires when any axis matches one of its strict patterns (see comments
below). ``comprehensive`` alone is not a review marker because it is
also a common adjective for engineering studies -- it only counts in
the phrase ``comprehensive review``.
"""
from __future__ import annotations

import csv
import re
import sys
from collections import Counter
from pathlib import Path
from typing import Dict, List, Tuple

REF_DIR = Path(__file__).resolve().parent
ROOT = REF_DIR.parent
MANIFEST = REF_DIR / "review_mes_moo_surrogates_manifest.csv"
ENRICHED = REF_DIR / "surrogates_esm_screening_enriched.csv"
LIB_MANIFEST = ROOT / "paper_library" / "review_paper_library_manifest.csv"
BIB = REF_DIR / "review_mes_moo_surrogates.bib"


# ---------------------------------------------------------------------------
# Strict review markers per signal source
#
# Title patterns: regex matched against the lower-cased title. A hit
# means the publication explicitly self-identifies as a review in its
# title. ``comprehensive`` alone is excluded; ``overview`` is allowed
# but only when followed by ``of`` to avoid catching study titles like
# ``Overview of system performance ...`` that are research papers.
# ---------------------------------------------------------------------------

TITLE_PATTERNS = [
    # "...: A Review" / "...-A Review" / "...—A Review" suffix
    r"[:\u2013\u2014-]\s*a\s+(systematic\s+|critical\s+|comprehensive\s+|brief\s+|short\s+|comparative\s+)?review\b",
    # explicit review/survey markers anywhere in the title
    r"\breview of\b",
    r"\breview on\b",
    r"\ba review\b",
    r"\bcomprehensive review\b",
    r"\bsystematic review\b",
    r"\bcritical review\b",
    r"\bliterature review\b",
    r"\bstate[-\s]of[-\s]the[-\s]art (review|survey)\b",
    r"\ba survey of\b",
    r"\ba survey on\b",
    r"\bsurvey on\b",
    r"\bsurvey of\b",
    # bibliometric / scientific mapping
    r"\bbibliometric (analysis|review|survey|study|mapping)\b",
    r"\bbibliometric\b",
    r"\bscientific mapping\b",
    # meta-analysis
    r"\bmeta-?analysis\b",
    r"\bmeta-?review\b",
    # overview / perspective
    r"\boverview of\b",
    r"\bperspective on\b",
    r"\ba perspective\b",
    # comprehensive analyses of literature only (not of a single system)
    r"\bcomprehensive (assessment|analysis|evaluation) of (the\s+)?(literature|methods|approaches|techniques|recent advances)\b",
]


# Abstract patterns: regex matched against the lower-cased abstract.
# These are first-person review-language markers ("we review",
# "this paper reviews", "this work surveys", "this review", etc.).
# They make a stronger statement than title alone, because a title
# can be advertising while an abstract that opens with "this paper
# reviews ..." is a positive content claim.

ABSTRACT_PATTERNS = [
    r"\bthis (paper|study|article|review|work|review article)\s+(presents|provides|reviews|surveys|gives|offers)\s+(a\s+)?(comprehensive\s+|systematic\s+|critical\s+|brief\s+)?(review|survey|overview|literature review)\b",
    r"\bin this (paper|study|article|review)\s*,\s*we\s+(review|survey)\b",
    r"\bwe (review|survey|present a review|present a survey)\b",
    r"\b(this is|the present) (paper|article|study|work) (is\s+)?a (systematic\s+|critical\s+|comprehensive\s+)?review\b",
    r"\b(comprehensive|systematic|critical|literature) review of\b",
    r"\bbibliometric (analysis|review|survey|study)\b",
    r"\b(meta-?analysis|state[-\s]of[-\s]the[-\s]art\s+review)\b",
    r"\bthe (review|survey)\s+(focuses|aims|covers|presents|provides|discusses|summari[sz]es)\b",
    r"\bsurveys (the|recent)\b",
    r"\breviews (the|recent)\b",
    r"\bthis review (paper\s+)?(focuses|aims|covers|presents|provides|discusses|summari[sz]es)\b",
    r"\bpurpose of (this|the present) review\b",
    r"\bobjective of (this|the present) review\b",
]


# Author / index keywords: tokens that indicate a review when they
# appear among the keywords. Many Scopus exports tag review papers
# with explicit ``Review`` or ``Literature review`` keywords.

KEYWORD_TOKENS = [
    "review",
    "literature review",
    "systematic review",
    "comprehensive review",
    "bibliometric",
    "bibliometric analysis",
    "survey",
    "state of the art",
    "state-of-the-art",
    "meta-analysis",
]


# ---------------------------------------------------------------------------
# Bib parsing -- we only need title, abstract, keywords per key
# ---------------------------------------------------------------------------


def parse_bib_minimal(path: Path) -> Dict[str, Dict[str, str]]:
    """Return ``{cite_key: {field: value}}`` with title, abstract and
    keywords. We re-parse here rather than reusing ``filter_bib`` so
    this audit script stays self-contained and importable from any
    CWD."""

    text = path.read_text(encoding="utf-8", errors="replace")
    out: Dict[str, Dict[str, str]] = {}

    # crude entry split: every '@type{key,'
    for m in re.finditer(r"@\w+\s*\{([^,]+),", text):
        key = m.group(1).strip()
        start = m.end()
        depth = 1
        i = start
        while i < len(text) and depth > 0:
            ch = text[i]
            if ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0:
                    break
            i += 1
        body = text[start:i]
        fields: Dict[str, str] = {}
        # within body, parse name = {value} pairs
        j = 0
        while j < len(body):
            mf = re.match(r"\s*([a-zA-Z_]+)\s*=\s*\{", body[j:])
            if not mf:
                # try comma separator
                k = body.find(",", j)
                if k == -1:
                    break
                j = k + 1
                continue
            name = mf.group(1).lower()
            j2 = j + mf.end()
            d = 1
            k = j2
            while k < len(body) and d > 0:
                ch = body[k]
                if ch == "{":
                    d += 1
                elif ch == "}":
                    d -= 1
                    if d == 0:
                        break
                k += 1
            fields[name] = body[j2:k]
            j = k + 1
        out[key] = fields
    return out


# ---------------------------------------------------------------------------
# Classification
# ---------------------------------------------------------------------------


def title_hit(title: str) -> List[str]:
    t = title.lower()
    hits = [p for p in TITLE_PATTERNS if re.search(p, t)]
    return hits


def abstract_hit(abstract: str) -> List[str]:
    a = abstract.lower()
    return [p for p in ABSTRACT_PATTERNS if re.search(p, a)]


def keyword_hit(keywords: str) -> List[str]:
    if not keywords:
        return []
    # keywords are typically separated by ';' or ','
    tokens = [t.strip().lower() for t in re.split(r"[;,]", keywords) if t.strip()]
    hits: List[str] = []
    for k in KEYWORD_TOKENS:
        for tok in tokens:
            if tok == k or tok == "review article":
                hits.append(k)
                break
    return hits


# ---------------------------------------------------------------------------
# Loaders for citation counts and library membership
# ---------------------------------------------------------------------------


def load_citations() -> Dict[str, int]:
    out: Dict[str, int] = {}
    if not ENRICHED.exists():
        return out
    with ENRICHED.open(newline="", encoding="utf-8") as f:
        for r in csv.DictReader(f):
            try:
                out[r["cite_key"]] = int(r.get("cited_by_count_value") or r.get("cited_by_count") or 0)
            except ValueError:
                out[r["cite_key"]] = 0
    return out


def load_library_keys() -> Dict[str, str]:
    out: Dict[str, str] = {}
    if not LIB_MANIFEST.exists():
        return out
    with LIB_MANIFEST.open(newline="", encoding="utf-8") as f:
        for r in csv.DictReader(f):
            out[r["cite_key"]] = r.get("primary_bucket", "")
    return out


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# Domain classification -- assigns each review candidate to one of the
# four scope axes that this paper targets, plus an "off-topic" bucket
# for hits that fire on a review marker but talk about something
# entirely different (AUVs, building heat waves, diesel engines, ...).
#
# A review can carry several domain tags (e.g. ``mes`` and ``moo``);
# the print routine emits all of them so the user can see at a glance
# whether a candidate matches the surrogate x MOO x MES intersection.
# ---------------------------------------------------------------------------

DOMAIN_TERMS = {
    "surrogate": [
        r"\bsurrogate\b", r"\bmetamodel", r"\bemulator\b",
        r"\bgaussian process", r"\bkriging\b", r"\bpolynomial chaos",
        r"\bneural network", r"\bdeep learning", r"\bmachine learning",
        r"\bphysics-informed", r"\bphysics-guided",
    ],
    "moo": [
        r"\bmulti-?objective\b", r"\bpareto\b", r"\bnsga\b",
        r"\bmoo\b", r"\bmulti-?criteria\b", r"\bmcdm\b",
    ],
    "mes": [
        r"\bmulti-?energy\b", r"\bmicrogrid\b", r"\benergy hub\b",
        r"\bintegrated energy\b", r"\bdistrict (heating|cooling|energy)\b",
        r"\bcombined heat and power\b", r"\bcchp\b", r"\bsector coupling\b",
        r"\bhybrid renewable\b", r"\bhres\b", r"\bccchp\b",
        r"\bmulti-?vector\b",
    ],
    "esm_opt": [
        r"\boptimi[sz]ation\b", r"\bdispatch\b", r"\bunit commitment\b",
        r"\boptimal power flow\b", r"\beconomic dispatch\b",
        r"\bcapacity expansion\b", r"\bplanning\b", r"\bsizing\b",
        r"\bexpansion planning\b", r"\bdistribution network\b",
        r"\bsmart grid\b", r"\bdemand-?side\b", r"\benergy management\b",
    ],
    "off_topic": [
        r"\bautonomous underwater\b", r"\bauv\b",
        r"\bdiesel engine\b", r"\binternal combustion\b",
        r"\bunderwater\b", r"\bship\b",
        r"\borganic rankine\b", r"\borc\b",
        r"\bbiodiesel\b", r"\bammonia.*combustion\b",
    ],
}


def domain_tags(title: str, abstract: str, keywords: str) -> List[str]:
    """Return the domain tags that fire on the combined haystack of
    title, abstract and keywords. Off-topic terms always win when
    they fire (we want to filter them out)."""

    hay = " ".join([title, abstract, keywords]).lower()
    tags: List[str] = []
    for tag, patterns in DOMAIN_TERMS.items():
        if any(re.search(p, hay) for p in patterns):
            tags.append(tag)
    return tags


def main() -> int:
    if not BIB.exists() or not MANIFEST.exists():
        print("missing inputs", file=sys.stderr)
        return 1

    bib = parse_bib_minimal(BIB)
    citations = load_citations()
    in_library = load_library_keys()

    rows = []
    with MANIFEST.open(newline="", encoding="utf-8") as f:
        for r in csv.DictReader(f):
            key = r["cite_key"]
            entry = bib.get(key, {})
            title = entry.get("title", "") or r.get("title", "")
            abstract = entry.get("abstract", "")
            keywords = entry.get("keywords", "") or entry.get("author_keywords", "")

            t_hits = title_hit(title)
            a_hits = abstract_hit(abstract)
            k_hits = keyword_hit(keywords)
            n_signals = (1 if t_hits else 0) + (1 if a_hits else 0) + (1 if k_hits else 0)
            if n_signals == 0:
                continue
            domains = domain_tags(title, abstract, keywords)
            rows.append(
                {
                    "key": key,
                    "year": r.get("year", ""),
                    "title": title,
                    "venue": r.get("venue", ""),
                    "citations": citations.get(key, 0),
                    "in_library": "yes" if key in in_library else "no",
                    "primary_bucket": in_library.get(key, ""),
                    "n_signals": n_signals,
                    "title_hits": "; ".join(t_hits) if t_hits else "",
                    "abstract_hits": "; ".join(a_hits) if a_hits else "",
                    "keyword_hits": "; ".join(k_hits) if k_hits else "",
                    "domains": ",".join(domains) if domains else "(none)",
                    "focus": r.get("focus", ""),
                }
            )

    # In-scope: at least one of {surrogate, moo, mes, esm_opt} fires.
    # Off-topic: only off_topic fires, or in-scope + off_topic both fire
    # but the off_topic terms are stronger -- we apply a simple rule:
    # if ``off_topic`` is the only domain tag, drop the candidate.
    in_scope_tags = {"surrogate", "moo", "mes", "esm_opt"}

    def is_in_scope(r):
        d = r["domains"].split(",") if r["domains"] != "(none)" else []
        in_scope = any(t in in_scope_tags for t in d)
        return in_scope

    strict = [r for r in rows if r["n_signals"] >= 2 or r["title_hits"]]
    weak = [r for r in rows if r not in strict]

    in_scope_strict = [r for r in strict if is_in_scope(r)]
    off_strict = [r for r in strict if not is_in_scope(r)]
    in_scope_weak = [r for r in weak if is_in_scope(r)]

    def fmt_row(r):
        return (
            f"{r['n_signals']:>3} | {r['citations']:>5} | "
            f"{r['in_library']:<3} | {r['year']:<4} | "
            f"{r['key']:<30} | {r['domains'][:24]:<24} | "
            f"{r['venue'][:28]:<28} | {r['title'][:80]}"
        )

    print(f"strict review hits          : {len(strict)}")
    print(f"  thereof in scope          : {len(in_scope_strict)}")
    print(f"  thereof off-topic         : {len(off_strict)}")
    print(f"weak review hits (1 signal) : {len(weak)}")
    print(f"  thereof in scope          : {len(in_scope_weak)}")
    print()

    print("=== strict in-scope reviews, sorted by citations ===")
    print(
        f"{'sig':>3} | {'cit':>5} | {'lib':<3} | {'year':<4} | "
        f"{'key':<30} | {'domains':<24} | {'venue':<28} | title"
    )
    in_scope_strict.sort(key=lambda r: (-r["citations"], r["year"], r["key"]))
    for r in in_scope_strict:
        print(fmt_row(r))

    print()
    print("=== strict in-scope reviews NOT in curated library ===")
    for r in [x for x in in_scope_strict if x["in_library"] == "no"]:
        print(fmt_row(r))

    print()
    print("=== weak in-scope reviews (only abstract or only keywords) ===")
    in_scope_weak.sort(key=lambda r: (-r["citations"], r["year"], r["key"]))
    for r in in_scope_weak:
        print(fmt_row(r))

    print()
    print("=== off-topic strict reviews (filtered out) ===")
    off_strict.sort(key=lambda r: (-r["citations"], r["year"], r["key"]))
    for r in off_strict:
        print(fmt_row(r))

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
