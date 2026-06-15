"""Match Literatur/**/*.pdf files to BibTeX cite keys (merged bibliography sources).

For each PDF under ``Literatur/<folder>/**``.pdf``: pull metadata plus plain text from
many front pages (PyMuPDF, then ``pypdf``), harvest DOIs (URL/doi-prefix *and*
bare ``10.xx/yy``). DOI matching **prefers** DOIs from the article body *before* a
``References`` heading (first ~12k chars if no heading), then falls back to the
initial page window, and—when ``--deep-extract-unmatched`` is on (default)—to a
second pass over the capped whole document (``--extract-hard-cap``) so DOIs on
late pages can still verify. BibTeX fingerprints also harvest DOIs appearing in
``url`` / ``howpublished`` / ``eprint``. Reconcile against merged ``*.bib`` blocks supplied via
``--bib`` (defaults: ``references/review_mes_moo_surrogates.bib`` chained with
``review_paper_library.bib`` so DOIs absent from the short Overleaf bib can still lock a key).

Verification / fail-closed semantics (defaults lean toward correctness over recall):

* Stage-1 heuristic assigns a tentative cite key via DOI intersection or constrained fuzzy similarity.
* Stage-2 **requires** either (a) DOI overlap bib↔PDF, or (b) a long bib-title token window occurring in the extracted text **with** surname coverage versus the bib ``author`` field. Anything else falls back to ``unmatched``.
* Stage-3 (optional, default on) **reverse Bib-DOI reconcile**: any cited key that
  still lacks a verified PDF may attach to the *unique* PDF whose probed DOIs
  intersect that bib row, again only after DOI verification succeeds.

Typical invocation::

    py match_literatur_pdfs_to_bib.py

Emits::

    ``_tmp_pdf_author_title_match_report.json``
    ``_tmp_pdf_author_title_match_map.csv``
    ``_tmp_manuscript_cite_pdf_coverage.csv``
"""
from __future__ import annotations

import argparse
import csv
import difflib
import json
import re
import sys
import unicodedata
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Set, Tuple

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_LITERATUR = ROOT / "Literatur"
DEFAULT_BIB_PRIMARY = ROOT / "references" / "review_mes_moo_surrogates.bib"
DEFAULT_BIB_SECONDARY = Path(__file__).resolve().parent / "review_paper_library.bib"
DEFAULT_MANUSCRIPT_DIR = ROOT / "manuscript"
DEFAULT_TABLES_DIR = ROOT / "tables"
DEFAULT_JSON_OUT = ROOT / "_tmp_pdf_author_title_match_report.json"
DEFAULT_CSV_OUT = ROOT / "_tmp_pdf_author_title_match_map.csv"
DEFAULT_COVERAGE_CSV_OUT = ROOT / "_tmp_manuscript_cite_pdf_coverage.csv"

SECTION_TEX_FILES: Dict[str, Tuple[str, ...]] = {
    "Reviews": ("02_related_reviews.tex",),
    "Taxonomy": ("04_taxonomy_surrogates.tex",),
    "Training and DoE": ("05_training_data_doe.tex",),
    "Integration patterns": ("06_integration_patterns.tex",),
}

SKIP_MANUSCRIPT_TEX = {
    "main.tex",
    "main_overleaf_rser.tex",
}

TITLE_WEIGHT = 0.58
AUTHOR_WEIGHT = 0.42
MIN_COMBINED_FOR_ACCEPT = 0.78
MIN_TITLE_RATIO_FOR_ACCEPT = 0.70
AMBIEQ_GAP = 0.018

EXTRACT_PAGES = 28
# Safety ceiling when extracting "all" pages (--extract-pages-full or retry path).
DEFAULT_EXTRACT_HARD_CAP = 260
MIN_TITLE_WIN_TOKENS = 5
MIN_TITLE_WIN_CHARS_NORMALIZED = 36
MIN_AUTHOR_VERIFY_RATIO = 0.333334

SECTION_ORDER = tuple(SECTION_TEX_FILES.keys()) + ("Other",)

DOI_BRACKET_RE = re.compile(
    r"(?:doi:?\s*|https?://(?:dx\.)?doi\.org/)(10\.\d{4,9}/\S+)",
    re.I,
)
DOI_BARE_RE = re.compile(
    r"(?<![\w/])(10\.\d{4,9}/[^\s\]>\"'}\],]+)",
    re.I,
)


def _die(msg: str, code: int = 2) -> None:
    print(msg, file=sys.stderr)
    raise SystemExit(code)


def _extract_braced_value(block: str, field: str) -> Optional[str]:
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


def parse_bib(path: Path) -> Dict[str, str]:
    text = path.read_text(encoding="utf-8", errors="replace")
    pat = re.compile(r"@\w+\s*\{\s*([^,]+?)\s*,\s*", re.MULTILINE)
    blocks: Dict[str, str] = {}
    for m in pat.finditer(text):
        cid = m.group(1).strip()
        start = m.start()
        nxt = pat.search(text, m.end())
        end = nxt.start() if nxt else len(text)
        blocks[cid] = text[start:end]
    return blocks


def merge_bibliography_blocks(paths: Sequence[Path]) -> Dict[str, str]:
    merged: Dict[str, str] = {}
    usable = [p.resolve() for p in paths if p.is_file()]
    if not usable:
        _die("No readable paths after --bib expansion; supply at least one existing .bib file.")
    for pth in usable:
        for cite_key, block in parse_bib(pth).items():
            prev = merged.get(cite_key)
            if prev is not None and prev.strip() != block.strip():
                print(
                    f"[warn] duplicate cite key `{cite_key}` differs between bib "
                    f"files — overwriting with `{pth.name}`",
                    file=sys.stderr,
                )
            merged[cite_key] = block
    return merged


def strip_latex_escapes_simple(s: str) -> str:
    s = re.sub(r"\\([&%#$_{}])", r"\1", s)
    s = re.sub(r"\\([`'^~v]|[uU]rl|ldots|-)", " ", s)
    return s


def fold_unicode(s: str) -> str:
    s = unicodedata.normalize("NFKD", s)
    return "".join(c for c in s if not unicodedata.combining(c))


def normalize_blob(s: str) -> str:
    if not s:
        return ""
    s = strip_latex_escapes_simple(s)
    s = fold_unicode(s.lower())
    s = re.sub(r"[^a-z0-9]+", " ", s)
    return re.sub(r"\s+", " ", s).strip()


def normalize_title_slug(s: str) -> str:
    if not s:
        return ""
    s = strip_latex_escapes_simple(s)
    s = fold_unicode(s.lower())
    s = re.sub(r"[^\w\s-]+", " ", s, flags=re.UNICODE)
    return re.sub(r"\s+", " ", s).strip()


def bib_last_names(authors_field: Optional[str], max_authors: int = 6) -> List[str]:
    if not authors_field:
        return []
    raw = strip_latex_escapes_simple(authors_field)
    chunks = re.split(r"\s+and\s+", raw, flags=re.IGNORECASE)
    out: List[str] = []
    for ch in chunks[:max_authors]:
        ch = ch.strip()
        if not ch:
            continue
        last = ch.split(",")[0].strip() if "," in ch else (ch.split()[-1] if ch.split() else ch)
        last = normalize_blob(last.replace("-", ""))
        if len(last) >= 2:
            out.append(last)
    return out


def title_ratio(a: Optional[str], b: Optional[str]) -> float:
    if not a or not b:
        return 0.0
    return difflib.SequenceMatcher(None, a, b).ratio()


def author_hit_ratio(names: Sequence[str], blob: str) -> float:
    if not names:
        return 0.0
    blob_n = normalize_blob(blob)
    hits = sum(1 for nm in names if len(nm) >= 2 and nm in blob_n)
    return hits / float(len(names))


def _clean_doi(raw: str) -> str:
    s = raw.lower().strip()
    s = re.sub(r"<\s*mml:.*?>\s*", "", s)
    s = re.sub(r"(https?:.*)$", "", s)
    while s.endswith((".", ")", ",", ";", "]", "-")):
        s = s[:-1]
    return s


def _doi_candidate_plausible(d: str) -> bool:
    """Reject Elsevier truncation artefacts such as ``10.1016/j``."""

    if not (d.startswith("10.") and "/" in d):
        return False
    tail = d.split("/", 1)[1].strip(".")
    return len(tail) >= 4


def extract_inner_dois(blob: str) -> Set[str]:
    found: Set[str] = set()
    if not blob:
        return found
    blob_l = blob.lower()
    for m in DOI_BRACKET_RE.finditer(blob_l):
        d = _clean_doi(m.group(1))
        if _doi_candidate_plausible(d):
            found.add(d)
    for m in DOI_BARE_RE.finditer(blob_l):
        d = _clean_doi(m.group(1))
        if _doi_candidate_plausible(d):
            found.add(d)
    return found


def extract_prioritized_article_dois(text: str) -> Set[str]:
    """DOIs from main text *before* the ``References`` section (if detectable)."""

    if not text:
        return set()
    m = re.search(r"(?ims)^\s*references\b", text)
    pre = text[: m.start()] if m else text[:12000]
    return extract_inner_dois(pre.lower())


def extract_text_pages(
    pdf: Path,
    max_pages: int = EXTRACT_PAGES,
    *,
    hard_cap: int = DEFAULT_EXTRACT_HARD_CAP,
) -> str:
    """Plain text from the first *max_pages* pages, or as many as the document has.

    * ``max_pages <= 0`` means “read the whole file” subject to *hard_cap* (PyMuPDF page
      count can be large on corrupt PDFs).
    """

    if not pdf.exists():
        return ""
    try:
        import fitz  # type: ignore

        with fitz.open(str(pdf)) as doc:
            n_doc = len(doc)
            if max_pages and max_pages > 0:
                n = min(n_doc, max_pages)
            else:
                n = min(n_doc, max(1, int(hard_cap)))
            return "\n".join(doc[i].get_text() for i in range(n))
    except Exception:
        pass
    try:
        from pypdf import PdfReader

        r = PdfReader(str(pdf))
        n_doc = len(r.pages)
        if max_pages and max_pages > 0:
            n = min(n_doc, max_pages)
        else:
            n = min(n_doc, max(1, int(hard_cap)))
        return "\n".join((r.pages[i].extract_text() or "") for i in range(n))
    except Exception:
        return ""


def read_pdf_document_info(pdf: Path) -> Tuple[Optional[str], Optional[str]]:
    try:
        import fitz  # type: ignore

        with fitz.open(str(pdf)) as doc:
            meta = dict(doc.metadata or {})
            tit = meta.get("title") or meta.get("Title")
            auth = meta.get("author") or meta.get("Author")
            tit = tit.strip() if isinstance(tit, str) else None
            auth = auth.strip() if isinstance(auth, str) else None
            if tit in ("", "None"):
                tit = None
            if auth in ("", "None"):
                auth = None
            return tit, auth
    except Exception:
        pass
    try:
        from pypdf import PdfReader

        md = PdfReader(str(pdf)).metadata
        if md is None:
            return None, None
        tit = md.get("/Title")
        auth = md.get("/Author")
        tit = tit.strip() if isinstance(tit, str) else None
        auth = auth.strip() if isinstance(auth, str) else None
        return tit, auth
    except Exception:
        return None, None


def guess_title_from_page_text(page_snippet: str) -> Optional[str]:
    if not page_snippet:
        return None
    candidates: List[str] = []
    for line in page_snippet.splitlines():
        t = line.strip()
        if 15 < len(t) < 400 and not re.match(
            r"^(Article|ORIGINAL|PAPER|Contents)$",
            t,
            re.I,
        ):
            candidates.append(t)
    if not candidates:
        return None
    return max(candidates, key=len)


@dataclass
class BibFingerprint:
    key: str
    title_slug: str
    authors_raw: str
    last_names_norm: List[str]
    dois_norm: Set[str]


def cite_keys_from_tex_files(ms_dir: Path, rel_names: Iterable[str]) -> Set[str]:
    keys: Set[str] = set()
    for name in rel_names:
        tex = ms_dir / name
        if not tex.is_file():
            _die(f"Manuscript snippet missing while resolving section cites: {tex}")
        blob = tex.read_text(encoding="utf-8", errors="replace")
        for m in re.finditer(r"\\cite[pt]*\*?\{([^}]+)\}", blob):
            for k in m.group(1).split(","):
                kk = k.strip()
                if kk:
                    keys.add(kk)
    return keys


def manuscript_union_cite_keys(ms_dir: Path) -> Set[str]:
    keys: Set[str] = set()
    if not ms_dir.is_dir():
        _die(f"Manuscript folder not found: {ms_dir}")
    for tex in sorted(ms_dir.glob("*.tex")):
        if tex.name in SKIP_MANUSCRIPT_TEX:
            continue
        blob = tex.read_text(encoding="utf-8", errors="replace")
        for m in re.finditer(r"\\cite[pt]*\*?\{([^}]+)\}", blob):
            for k in m.group(1).split(","):
                kk = k.strip()
                if kk:
                    keys.add(kk)
    return keys


def table_tex_cite_keys(tbl_dir: Path) -> Set[str]:
    keys: Set[str] = set()
    if not tbl_dir.is_dir():
        return keys
    for tex in sorted(tbl_dir.glob("*.tex")):
        blob = tex.read_text(encoding="utf-8", errors="replace")
        for m in re.finditer(r"\\cite[pt]*\*?\{([^}]+)\}", blob):
            for k in m.group(1).split(","):
                kk = k.strip()
                if kk:
                    keys.add(kk)
    return keys


def union_repository_citations(ms_dir: Path, tbl_dir: Path) -> Set[str]:
    return manuscript_union_cite_keys(ms_dir) | table_tex_cite_keys(tbl_dir)


def title_window_substring_matches(
    bib_title_raw: Optional[str],
    pdf_plain: str,
) -> Tuple[bool, str]:
    if not bib_title_raw or not pdf_plain:
        return False, ""
    btokens = normalize_blob(bib_title_raw).split()
    pblob = normalize_blob(pdf_plain)
    if len(btokens) < 3:
        return False, ""
    win_lo = MIN_TITLE_WIN_TOKENS - 1
    for win_len in range(len(btokens), win_lo, -1):
        if win_len < MIN_TITLE_WIN_TOKENS:
            break
        for start in range(0, len(btokens) - win_len + 1):
            cand = " ".join(btokens[start : start + win_len])
            if len(cand) < MIN_TITLE_WIN_CHARS_NORMALIZED:
                continue
            if cand in pblob:
                return True, cand
    return False, ""


def verify_mapping(
    proposed_key: str,
    *,
    via_doi: bool,
    fingerprint_by_key: Dict[str, BibFingerprint],
    dois_pdf: Set[str],
    extended_pdf_text: str,
    pdf_meta_author: Optional[str],
    block_by_key: Dict[str, str],
) -> Tuple[bool, str, str]:
    fp = fingerprint_by_key.get(proposed_key)
    blk = block_by_key.get(proposed_key)
    if fp is None or blk is None:
        return False, "", "missing_bib_block_or_fingerprint"

    if via_doi:
        inter = fp.dois_norm & dois_pdf
        if inter:
            return True, "doi_pdf_bib_intersection", ""
        return False, "", "doi_tagged_match_without_normalized_overlap"

    ttl = _extract_braced_value(blk, "title")
    anchor_ok, phrase = title_window_substring_matches(ttl, extended_pdf_text)
    if not anchor_ok:
        return False, "", "bib_title_anchor_not_found_in_pdf"

    blob = " ".join(
        x for x in (pdf_meta_author or "", extended_pdf_text[:12000]) if x
    )
    auth_ratio = author_hit_ratio(fp.last_names_norm, blob)
    if auth_ratio + 1e-9 < MIN_AUTHOR_VERIFY_RATIO:
        msg = (
            f"surnames_below_{MIN_AUTHOR_VERIFY_RATIO:.3f}_got_{auth_ratio:.3f}"
        )
        return False, "", msg

    clipped = phrase[:96] + ("…" if len(phrase) > 96 else "")
    return True, "title_anchor_plus_authors|" + clipped, ""


def _dois_from_bib_block(blk: str) -> Set[str]:
    """Collect normalized DOIs from ``doi`` / ``url`` / ``eprint`` / ``howpublished``."""

    dois: Set[str] = set()
    doi_v = _extract_braced_value(blk, "doi")
    if doi_v:
        stripped = doi_v.strip().lower()
        if stripped.startswith("10.") and "/" in stripped:
            cd0 = _clean_doi(stripped)
            if _doi_candidate_plausible(cd0):
                dois.add(cd0)
        dois.update(
            dd
            for dd in extract_inner_dois(stripped)
            if _doi_candidate_plausible(dd)
        )
    for field in ("url", "howpublished"):
        raw = _extract_braced_value(blk, field)
        if raw:
            dois.update(
                dd
                for dd in extract_inner_dois(raw.lower())
                if _doi_candidate_plausible(dd)
            )
    eprint = _extract_braced_value(blk, "eprint")
    if eprint and "10." in eprint:
        dois.update(
            dd
            for dd in extract_inner_dois(eprint.lower())
            if _doi_candidate_plausible(dd)
        )
    return dois


def build_fingerprints(blocks: Dict[str, str]) -> Dict[str, BibFingerprint]:
    fps: Dict[str, BibFingerprint] = {}
    for key, blk in blocks.items():
        title = _extract_braced_value(blk, "title")
        slug = normalize_title_slug(title or "")
        auth = _extract_braced_value(blk, "author") or ""
        dois = _dois_from_bib_block(blk)
        fps[key] = BibFingerprint(
            key=key,
            title_slug=slug,
            authors_raw=auth,
            last_names_norm=bib_last_names(auth),
            dois_norm={_clean_doi(d) for d in dois if d.startswith("10.")},
        )
    return fps


def best_doi_matches(
    pdf_dois: Set[str],
    fps: Dict[str, BibFingerprint],
) -> Tuple[Optional[str], List[str]]:
    if not pdf_dois:
        return None, []
    hits = sorted(fp.key for fp in fps.values() if pdf_dois & fp.dois_norm)
    if len(hits) == 1:
        # Caller treats any non-empty second value as ambiguity — only >1 bib hit
        # should populate that list.
        return hits[0], []
    if len(hits) > 1:
        return None, hits
    return None, []


def score_pdf_to_bib(
    pdf_meta_title: Optional[str],
    pdf_meta_author: Optional[str],
    page_blob: str,
    fp: BibFingerprint,
) -> Tuple[float, float, float]:
    pt = normalize_title_slug(pdf_meta_title or "")
    if not pt:
        pt = normalize_title_slug(
            guess_title_from_page_text(page_blob[:2500]) or "",
        )
    tr = title_ratio(pt, fp.title_slug)
    blob = " ".join(x for x in (pdf_meta_author or "", page_blob[:4000]) if x)
    ar = author_hit_ratio(fp.last_names_norm, blob)
    combo = TITLE_WEIGHT * tr + AUTHOR_WEIGHT * ar
    return combo, tr, ar


def rank_pool(
    pdf_meta_title: Optional[str],
    pdf_meta_author: Optional[str],
    page_blob: str,
    pool_keys: Sequence[str],
    fps: Dict[str, BibFingerprint],
) -> List[Tuple[str, float, float, float]]:
    scores: List[Tuple[str, float, float, float]] = []
    for k in pool_keys:
        fp = fps[k]
        c, tr, ar = score_pdf_to_bib(pdf_meta_title, pdf_meta_author, page_blob, fp)
        scores.append((k, c, tr, ar))
    scores.sort(key=lambda x: x[1], reverse=True)
    return scores


def classify_match(
    ranked: Sequence[Tuple[str, float, float, float]],
) -> Tuple[Optional[str], str, float]:
    if not ranked:
        return None, "unmatched", 0.0
    k0, c0, t0, _a0 = ranked[0]
    k1, c1, _tr1, _a1 = (
        ranked[1] if len(ranked) > 1 else (None, 0.0, 0.0, 0.0)
    )
    gap = (c0 - c1) if k1 is not None else 1.0
    ambiguous = gap < AMBIEQ_GAP and len(ranked) > 1
    meets = (
        c0 >= MIN_COMBINED_FOR_ACCEPT
        and t0 >= MIN_TITLE_RATIO_FOR_ACCEPT
        and not ambiguous
    )
    if meets:
        return k0, "matched_unique", gap
    if ambiguous and c0 >= MIN_COMBINED_FOR_ACCEPT:
        return k0, "matched_ambiguous", gap
    return None, "unmatched", gap


def collect_pdfs(root: Path) -> List[Tuple[str, Path]]:
    if not root.is_dir():
        _die(f"Literatur folder missing: {root}")
    pairs: List[Tuple[str, Path]] = []
    for sub in sorted(root.iterdir()):
        if not sub.is_dir():
            continue
        sec = sub.name
        for pdf in sorted(sub.rglob("*.pdf")):
            pairs.append((sec, pdf))
    pairs.sort(key=lambda x: (x[0].lower(), str(x[1]).lower()))
    return pairs


def build_section_candidate_map(ms_dir: Path, cite_universe: Set[str]) -> Dict[str, Set[str]]:
    sec_map: Dict[str, Set[str]] = {}
    for folder, texs in SECTION_TEX_FILES.items():
        sec_map[folder] = cite_keys_from_tex_files(ms_dir, texs) & cite_universe
    sec_map["Other"] = set(cite_universe)
    return sec_map


def _harvest_pdf_dois(
    page_txt: str,
    pdf_meta_title: Optional[str],
    pdf_meta_author: Optional[str],
) -> Tuple[Set[str], Set[str]]:
    dois_full = set(extract_inner_dois(page_txt.lower()))
    if pdf_meta_title:
        dois_full |= extract_inner_dois(pdf_meta_title.lower())
    if pdf_meta_author:
        dois_full |= extract_inner_dois(pdf_meta_author.lower())
    dois_article = extract_prioritized_article_dois(page_txt)
    return dois_full, dois_article


def _pdf_match_attempt(
    *,
    section_folder: str,
    pdf_relpath: str,
    page_txt: str,
    pdf_meta_title: Optional[str],
    pdf_meta_author: Optional[str],
    fingerprint_by_key: Dict[str, BibFingerprint],
    block_by_key: Dict[str, str],
    pool_section: Sequence[str],
    pool_global: Sequence[str],
    allow_global_fallback: bool,
    extract_pass_label: str,
) -> Tuple[Dict[str, Any], Set[str]]:
    """One adjudication pass for a PDF + extracted text slice."""

    dois_full, dois_article = _harvest_pdf_dois(
        page_txt,
        pdf_meta_title,
        pdf_meta_author,
    )

    notes_parts: List[str] = [f"extract_pass={extract_pass_label}"]

    doi_key: Optional[str] = None
    doi_collision: List[str] = []

    def narrow_doi_collision(colls: Sequence[str]) -> Optional[str]:
        for pool_lab, cand_pool in (
            ("integration_section_pool", pool_section),
            ("manuscript_cite_union", pool_global),
        ):
            narrowed = sorted(set(colls) & set(cand_pool))
            if len(narrowed) == 1:
                notes_parts.append(f"doi_disambiguated_by_{pool_lab}")
                return narrowed[0]
        return None

    for doi_src_label, dois_set in (
        ("article_preface", dois_article),
        ("full_text", dois_full),
    ):
        if not dois_set:
            continue
        dk, dc = best_doi_matches(dois_set, fingerprint_by_key)
        if dk:
            doi_key, doi_collision = dk, []
            notes_parts.append(f"doi_primary_source={doi_src_label}")
            break
        if dc:
            narrowed_key = narrow_doi_collision(dc)
            if narrowed_key:
                doi_key, doi_collision = narrowed_key, []
                notes_parts.insert(
                    1,
                    f"doi_source_collided_then_narrowed={doi_src_label}",
                )
                break
            doi_collision = list(dc)

    mapped_key = ""
    provisional_status = "unmatched"
    match_scope = ""
    combined_top = 0.0
    title_ratio_top = 0.0
    author_ratio_top = 0.0
    gap_second = 0.0

    if doi_key:
        mapped_key = doi_key
        provisional_status = "matched_unique_via_doi"
        match_scope = "doi"
    elif doi_collision:
        provisional_status = "matched_ambiguous"
        notes_parts.append("doi_collision:" + ",".join(doi_collision))
    else:
        ranked_sec = rank_pool(
            pdf_meta_title,
            pdf_meta_author,
            page_txt,
            pool_section,
            fingerprint_by_key,
        )
        mk, st_sec, gp = classify_match(ranked_sec)
        if ranked_sec:
            combined_top = ranked_sec[0][1]
            title_ratio_top = ranked_sec[0][2]
            author_ratio_top = ranked_sec[0][3]

        if mk and st_sec == "matched_unique":
            mapped_key = mk
            provisional_status = "matched_section_unique"
            match_scope = "section_fuzzy"
            gap_second = gp
        elif allow_global_fallback and pool_global:
            ranked_g = rank_pool(
                pdf_meta_title,
                pdf_meta_author,
                page_txt,
                pool_global,
                fingerprint_by_key,
            )
            mk2, st_g, gp2 = classify_match(ranked_g)
            combined_top = ranked_g[0][1]
            title_ratio_top = ranked_g[0][2]
            author_ratio_top = ranked_g[0][3]

            if mk2 and st_g == "matched_unique":
                mapped_key = mk2
                provisional_status = "matched_global_unique"
                match_scope = "global_fuzzy"
                gap_second = gp2
            elif st_g == "matched_ambiguous":
                provisional_status = "matched_ambiguous"
                notes_parts.append("fuzzy_ambiguous")
            else:
                notes_parts.append("below_threshold")
        else:
            if st_sec == "matched_ambiguous":
                provisional_status = "matched_ambiguous"
                notes_parts.append("section_fuzzy_ambiguous")
            elif not ranked_sec:
                notes_parts.append("empty_section_pool")
            elif not pool_global:
                notes_parts.append("empty_global_manuscriptcite_pool")
            else:
                notes_parts.append(
                    "section_below_threshold_no_global_fallback",
                )

    verification_tier = ""
    verification_passed = False
    reject_detail = ""

    final_status = provisional_status
    if provisional_status == "matched_ambiguous" or doi_collision:
        final_status = "matched_ambiguous"
        if dois_full:
            notes_parts.append("pdf_dois=" + ";".join(sorted(dois_full)[:4]))
    elif (
        provisional_status.startswith("matched")
        and provisional_status != "matched_ambiguous"
        and mapped_key
    ):
        via_doi = provisional_status == "matched_unique_via_doi"
        ver_ok, verification_tier, reject_detail = verify_mapping(
            mapped_key,
            via_doi=via_doi,
            fingerprint_by_key=fingerprint_by_key,
            dois_pdf=dois_full,
            extended_pdf_text=page_txt,
            pdf_meta_author=pdf_meta_author,
            block_by_key=block_by_key,
        )
        if ver_ok:
            verification_passed = True
            final_status = provisional_status
        else:
            provisional_label = provisional_status
            bumped_key = mapped_key
            mapped_key = ""
            match_scope = ""
            final_status = "unmatched"
            trail = f"rejected_was_{provisional_label}:{bumped_key}|{reject_detail}"
            verification_tier = ""
            notes_parts.append(trail)

    elif provisional_status == "unmatched" or not mapped_key:
        pass

    if final_status == "unmatched" and dois_full:
        dk, dhits = best_doi_matches(dois_full, fingerprint_by_key)
        if dk is None and not dhits:
            notes_parts.append(
                "detected_dois_not_present_in_loaded_bibs="
                + ";".join(sorted(dois_full)[:6]),
            )

    row: Dict[str, Any] = {
        "section_folder": section_folder,
        "pdf_relpath": pdf_relpath,
        "mapped_key": mapped_key,
        "status": final_status,
        "provisional_status": provisional_status,
        "match_scope": match_scope if verification_passed else "",
        "verification_passed": verification_passed,
        "verification_tier": verification_tier,
        "verification_reject": reject_detail,
        "combined_score": round(combined_top, 4),
        "title_ratio": round(title_ratio_top, 4),
        "author_ratio": round(author_ratio_top, 4),
        "gap_to_second": round(gap_second, 4),
        "pdf_meta_title": (pdf_meta_title or "")[:500],
        "pdf_meta_author": (pdf_meta_author or "")[:500],
        "notes": "|".join([p for p in notes_parts if p]),
        "dois_in_pdf_snippet": ";".join(sorted(dois_full)[:12]),
    }
    return row, dois_full


def aggregate_section_statistics_from_final_rows(
    rows: Iterable[Dict[str, Any]],
) -> Dict[str, Dict[str, int]]:
    """Rebuild per-Literatur-folder counters strictly from adjudicated PDF rows."""

    inner_zero = {
        "unmatched": 0,
        "matched_section_unique_verified": 0,
        "matched_global_unique_verified": 0,
        "matched_unique_via_doi_verified": 0,
        "matched_unique_via_bib_reverse_verified": 0,
        "matched_ambiguous": 0,
        "verification_rejected": 0,
    }
    agg: Dict[str, Dict[str, int]] = {s: dict(inner_zero) for s in SECTION_ORDER}
    for r in rows:
        sec = str(r["section_folder"])
        if sec not in agg:
            agg[sec] = dict(inner_zero)
        rej = bool(r.get("verification_reject"))
        st = str(r["status"])
        vp = bool(r["verification_passed"])
        notes = str(r.get("notes") or "")
        tgt = agg[sec]
        if st == "matched_ambiguous":
            tgt["matched_ambiguous"] += 1
        elif vp:
            if st == "matched_unique_via_doi" and "reverse_bib_doi_lookup" in notes:
                tgt["matched_unique_via_bib_reverse_verified"] += 1
            elif st == "matched_unique_via_doi":
                tgt["matched_unique_via_doi_verified"] += 1
            elif st == "matched_global_unique":
                tgt["matched_global_unique_verified"] += 1
            elif st == "matched_section_unique":
                tgt["matched_section_unique_verified"] += 1
        elif rej:
            tgt["verification_rejected"] += 1
            tgt["unmatched"] += 1
        elif st == "unmatched":
            tgt["unmatched"] += 1
    return agg


def _pick_winning_attempt(
    attempts: List[Tuple[Dict[str, Any], Set[str]]],
) -> Tuple[Dict[str, Any], Set[str]]:
    verified = next((a for a in attempts if a[0]["verification_passed"]), None)
    if verified is not None:
        return verified
    return attempts[-1]


def _needs_deeper_pdf_extraction(
    row: Dict[str, Any],
    *,
    allow_on_ambiguous: bool,
) -> bool:
    """Whether a capped full-document text grab is worth attempting."""

    if row["verification_passed"]:
        return False
    st = str(row["status"])
    if st == "matched_ambiguous":
        return allow_on_ambiguous
    if row.get("verification_reject"):
        return True
    return st == "unmatched"


def _reverse_match_cites_to_pdfs_via_bib_doi(
    *,
    rows: List[Dict[str, Any]],
    cite_universe: Set[str],
    fingerprint_by_key: Dict[str, BibFingerprint],
    block_by_key: Dict[str, str],
    probe_by_relpath: Dict[str, Dict[str, Any]],
) -> int:
    """Keys still lacking a verified PDF attempt to latch onto the *unique* local PDF probe
    whose extracted DOI multiset intersects the bib fingerprints (post deep-extract snapshot).
    Each successful attach still clears ``verify_mapping(..., via_doi=True)``."""

    row_idx = {str(r["pdf_relpath"]): i for i, r in enumerate(rows)}
    total_attach = 0
    progressing = True
    guard = 0
    guard_cap = len(cite_universe) + 8

    while progressing and guard < guard_cap:
        guard += 1
        progressing = False
        claimed = {
            str(r["mapped_key"])
            for r in rows
            if str(r["mapped_key"]) and r["verification_passed"]
        }
        for ck in sorted(cite_universe):
            if ck in claimed:
                continue
            fp_row = fingerprint_by_key.get(ck)
            if fp_row is None or not fp_row.dois_norm:
                continue
            bib_dois = fp_row.dois_norm
            cand = sorted(
                rel
                for rel, probe in probe_by_relpath.items()
                if bib_dois & set(probe.get("dois_full") or ())
            )
            if len(cand) != 1:
                continue
            rel = cand[0]
            r_i = row_idx.get(rel)
            if r_i is None:
                continue
            victim = rows[r_i]
            cur_mk = str(victim["mapped_key"])
            if cur_mk and victim["verification_passed"] and cur_mk != ck:
                continue
            if cur_mk == ck and victim["verification_passed"]:
                continue
            probe = probe_by_relpath[rel]
            page_txt = str(probe.get("page_txt") or "")
            dois_full = set(probe.get("dois_full") or ())
            ma_probe = probe.get("pdf_meta_author")
            meta_a = ma_probe if isinstance(ma_probe, str) else None
            ok, tier, _rej = verify_mapping(
                ck,
                via_doi=True,
                fingerprint_by_key=fingerprint_by_key,
                dois_pdf=dois_full,
                extended_pdf_text=page_txt,
                pdf_meta_author=meta_a,
                block_by_key=block_by_key,
            )
            if not ok:
                continue
            prev_notes = str(victim.get("notes") or "")
            tail = "reverse_bib_doi_lookup"
            merged_notes = "|".join(p for p in (prev_notes, tail) if p)
            victim.update(
                {
                    "mapped_key": ck,
                    "status": "matched_unique_via_doi",
                    "provisional_status": "matched_unique_via_doi",
                    "match_scope": "doi",
                    "verification_passed": True,
                    "verification_tier": tier,
                    "verification_reject": "",
                    "combined_score": 0.0,
                    "title_ratio": 0.0,
                    "author_ratio": 0.0,
                    "gap_to_second": 0.0,
                    "notes": merged_notes,
                    "dois_in_pdf_snippet": ";".join(sorted(dois_full)[:12]),
                },
            )
            total_attach += 1
            progressing = True
            break

    return total_attach


def run(args: argparse.Namespace) -> Dict[str, Any]:
    bib_paths = [Path(p) for p in args.bib]
    lit_root = Path(args.literatur)
    ms_dir = Path(args.manuscript_dir)
    tbl_dir = Path(args.tables_dir)
    extract_n = max(4, int(args.extract_pages))
    hard_cap = max(extract_n, int(args.extract_hard_cap))

    merged_blocks = merge_bibliography_blocks(bib_paths)
    fps = build_fingerprints(merged_blocks)
    cite_universe = union_repository_citations(ms_dir, tbl_dir)

    unresolved_keys = sorted(k for k in cite_universe if k not in fps)
    if unresolved_keys:
        print(
            f"[warn] {len(unresolved_keys)} manuscript/table cite-keys are absent from merged "
            f"bibliography snapshots — regenerate bibs or add missing rows. First few: "
            f"{', '.join(unresolved_keys[:15])}",
            file=sys.stderr,
        )

    sec_map = build_section_candidate_map(ms_dir, cite_universe)
    pdfs_list = collect_pdfs(lit_root)
    rows: List[Dict[str, Any]] = []

    cite_pool_sig = cite_universe & set(fps.keys())
    probe_by_relpath: Dict[str, Dict[str, Any]] = {}

    for sec, pdf_path in pdfs_list:
        mt, ma = read_pdf_document_info(pdf_path)
        rel_pdf = str(pdf_path.relative_to(lit_root))
        cite_pool_loop = cite_pool_sig
        pool_section = sorted(sec_map.get(sec, cite_pool_loop) & set(fps.keys()))
        pool_global = sorted(set(fps.keys()) & cite_pool_loop)

        page_initial = extract_text_pages(
            pdf_path,
            max_pages=extract_n,
            hard_cap=hard_cap,
        )
        attempt_list: List[Tuple[Dict[str, Any], Set[str]]] = [
            _pdf_match_attempt(
                section_folder=sec,
                pdf_relpath=rel_pdf,
                page_txt=page_initial,
                pdf_meta_title=mt,
                pdf_meta_author=ma,
                fingerprint_by_key=fps,
                block_by_key=merged_blocks,
                pool_section=pool_section,
                pool_global=pool_global,
                allow_global_fallback=bool(args.allow_global_fallback),
                extract_pass_label=f"initial_pages_{extract_n}",
            ),
        ]

        doi_union, _ = _harvest_pdf_dois(page_initial, mt, ma)
        deepest_txt = page_initial

        if args.deep_extract_unmatched and _needs_deeper_pdf_extraction(
            attempt_list[-1][0],
            allow_on_ambiguous=args.deep_extract_ambiguous,
        ):
            page_deep = extract_text_pages(
                pdf_path,
                max_pages=0,
                hard_cap=hard_cap,
            )
            union_delta, _ = _harvest_pdf_dois(page_deep, mt, ma)
            doi_union |= union_delta
            attempt_list.append(
                _pdf_match_attempt(
                    section_folder=sec,
                    pdf_relpath=rel_pdf,
                    page_txt=page_deep,
                    pdf_meta_title=mt,
                    pdf_meta_author=ma,
                    fingerprint_by_key=fps,
                    block_by_key=merged_blocks,
                    pool_section=pool_section,
                    pool_global=pool_global,
                    allow_global_fallback=bool(args.allow_global_fallback),
                    extract_pass_label=f"deep_cap_{hard_cap}",
                ),
            )
            if len(page_deep) >= len(page_initial):
                deepest_txt = page_deep

        win_row, _win_dois = _pick_winning_attempt(attempt_list)

        probe_by_relpath[rel_pdf] = {
            "page_txt": deepest_txt,
            "dois_full": set(doi_union),
            "pdf_meta_author": ma,
        }

        rows.append(dict(win_row))

    reverse_attach = 0
    if args.reverse_bib_doi_reconcile:
        reverse_attach = _reverse_match_cites_to_pdfs_via_bib_doi(
            rows=rows,
            cite_universe=cite_universe,
            fingerprint_by_key=fps,
            block_by_key=merged_blocks,
            probe_by_relpath=probe_by_relpath,
        )

    sec_stats = aggregate_section_statistics_from_final_rows(rows)

    key_to_pdfs: Dict[str, List[str]] = defaultdict(list)
    for r in rows:
        mk = str(r["mapped_key"])
        if mk and r["verification_passed"] and r["status"] not in {
            "matched_ambiguous",
            "unmatched",
        }:
            key_to_pdfs[mk].append(str(r["pdf_relpath"]))

    collisions = {k: v for k, v in key_to_pdfs.items() if len(v) > 1}
    cites_missing_pdf = sorted(
        k for k in cite_universe if k not in key_to_pdfs or not key_to_pdfs[k]
    )

    coverage_rows: List[Dict[str, str]] = []
    for ck in sorted(cite_universe):
        lst = sorted(key_to_pdfs.get(ck, []))
        coverage_rows.append(
            {
                "cite_key": ck,
                "in_merged_bib": str(ck in fps),
                "verified_pdf_paths": ";".join(lst),
                "verified_pdf_count": str(len(lst)),
                "multiple_pdf_collision": ("yes" if len(lst) > 1 else ""),
            },
        )

    cov_path = Path(args.out_coverage_csv)
    if coverage_rows:
        with cov_path.open("w", encoding="utf-8", newline="") as fh:
            w = csv.DictWriter(fh, fieldnames=list(coverage_rows[0].keys()))
            w.writeheader()
            w.writerows(coverage_rows)
    else:
        cov_path.write_text("", encoding="utf-8")

    def _note(r: Dict[str, Any]) -> str:
        return str(r.get("notes") or "")

    status_counts = {
        "unmatched": sum(1 for r in rows if r["status"] == "unmatched"),
        "matched_section_unique_verified": sum(
            1
            for r in rows
            if r["verification_passed"] and r["status"] == "matched_section_unique"
        ),
        "matched_global_unique_verified": sum(
            1
            for r in rows
            if r["verification_passed"] and r["status"] == "matched_global_unique"
        ),
        "matched_unique_via_doi_verified": sum(
            1
            for r in rows
            if r["verification_passed"]
            and r["status"] == "matched_unique_via_doi"
            and "reverse_bib_doi_lookup" not in _note(r)
        ),
        "matched_unique_via_bib_reverse_verified": sum(
            1
            for r in rows
            if r["verification_passed"]
            and r["status"] == "matched_unique_via_doi"
            and "reverse_bib_doi_lookup" in _note(r)
        ),
        "matched_ambiguous": sum(
            1 for r in rows if r["status"] == "matched_ambiguous"
        ),
        "verification_rejected": sum(
            1 for r in rows if r["verification_reject"]
        ),
        "reverse_bib_doi_attachments": reverse_attach,
    }

    bib_source_str = ";".join(str(Path(p).resolve()) for p in bib_paths if Path(p).is_file())

    report: Dict[str, Any] = {
        "literatur_root": str(lit_root.resolve()),
        "bib_inputs_resolved": bib_source_str,
        "cite_universe_size": len(cite_universe),
        "cite_keys_missing_from_merged_bib": unresolved_keys,
        "verified_unique_keys_with_pdf": sorted(key_to_pdfs.keys()),
        "cites_without_verified_pdf": cites_missing_pdf,
        "verified_colliding_keys_multi_pdf": sorted(collisions.keys()),
        "total_pdfs": len(pdfs_list),
        "status_counts": status_counts,
        "by_section": sec_stats,
        "thresholds": {
            "extract_pages": extract_n,
            "extract_hard_cap_pages": hard_cap,
            "deep_extract_unmatched": bool(args.deep_extract_unmatched),
            "deep_extract_ambiguous": bool(args.deep_extract_ambiguous),
            "reverse_bib_doi_reconcile": bool(args.reverse_bib_doi_reconcile),
            "title_weight": TITLE_WEIGHT,
            "author_weight": AUTHOR_WEIGHT,
            "min_combined": MIN_COMBINED_FOR_ACCEPT,
            "min_title_ratio": MIN_TITLE_RATIO_FOR_ACCEPT,
            "ambiguous_gap": AMBIEQ_GAP,
            "min_author_verify_ratio": MIN_AUTHOR_VERIFY_RATIO,
            "min_title_window_tokens": MIN_TITLE_WIN_TOKENS,
            "min_title_window_chars": MIN_TITLE_WIN_CHARS_NORMALIZED,
        },
        "rows": rows,
    }

    Path(args.out_json).write_text(
        json.dumps(report, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    csv_path = Path(args.out_csv)
    if rows:
        with csv_path.open("w", encoding="utf-8", newline="") as fh:
            w = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
            w.writeheader()
            w.writerows(rows)
    else:
        csv_path.write_text("", encoding="utf-8")

    print(
        f"Wrote {args.out_json}, {args.out_csv}, {args.out_coverage_csv} "
        f"({len(pdfs_list)} PDFs). status_counts={status_counts} "
        f"| cites_without_verified_pdf={len(cites_missing_pdf)} "
        f"| key_collisions={len(collisions)} "
        f"| cite_keys_missing_bib_rows={len(unresolved_keys)}",
    )

    return report


def build_argparser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(
        description=(
            "Map Literatur PDFs to bibliography cite keys using strict downstream checks."
        ),
    )
    ap.add_argument("--literatur", type=Path, default=DEFAULT_LITERATUR)
    ap.add_argument(
        "--bib",
        type=Path,
        nargs="+",
        default=(
            DEFAULT_BIB_PRIMARY,
            DEFAULT_BIB_SECONDARY,
        ),
        help="One or more .bib databases merged in-order (later files override duplicate cite keys).",
    )
    ap.add_argument("--manuscript-dir", type=Path, default=DEFAULT_MANUSCRIPT_DIR)
    ap.add_argument("--tables-dir", type=Path, default=DEFAULT_TABLES_DIR)
    ap.add_argument("--extract-pages", type=int, default=EXTRACT_PAGES)
    ap.add_argument(
        "--extract-hard-cap",
        type=int,
        default=DEFAULT_EXTRACT_HARD_CAP,
        help=(
            "Max pages extracted when scanning the capped full document (--extract-pages-full "
            "semantics inside deep retry / union-DOI probes)."
        ),
    )
    ap.add_argument(
        "--deep-extract-unmatched",
        action=argparse.BooleanOptionalAction,
        default=True,
        help=(
            "If the shallow pass ends without verified mapping, OCR-free text extraction is "
            "retried across the capped full PDF (helps when DOIs sit past the headline pages)."
        ),
    )
    ap.add_argument(
        "--deep-extract-ambiguous",
        action=argparse.BooleanOptionalAction,
        default=False,
        help=(
            "Also run capped full-document extraction when the heuristic stage is ambiguous "
            "(expensive; rarely changes collisions)."
        ),
    )
    ap.add_argument(
        "--reverse-bib-doi-reconcile",
        action=argparse.BooleanOptionalAction,
        default=True,
        help=(
            "After PDF rows settle, cite keys that still lack a verified PDF retry against the "
            "unique PDF whose DOI multiset intersects the bib entry (still DOI-verified)."
        ),
    )
    ap.add_argument("--out-json", type=Path, default=DEFAULT_JSON_OUT)
    ap.add_argument("--out-csv", type=Path, default=DEFAULT_CSV_OUT)
    ap.add_argument(
        "--out-coverage-csv",
        type=Path,
        default=DEFAULT_COVERAGE_CSV_OUT,
    )
    ap.add_argument(
        "--allow-global-fallback",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Retry fuzzy matching against manuscripts+tables cite-key ∩ bib ∩ global pool.",
    )
    return ap


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = build_argparser().parse_args(list(argv) if argv is not None else None)
    run(args)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
