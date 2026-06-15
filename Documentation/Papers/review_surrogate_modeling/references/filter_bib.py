"""Offline filter for the surrogate modeling review.

This script turns a raw Scopus BibTeX export into:

- ``surrogates_esm.bib``             -> Tier A entries (high confidence)
- ``surrogates_esm_candidates.bib``  -> Tier B entries (manual review)
- ``surrogates_esm_screening.csv``   -> per-entry decision log

The tiered logic (Tier A explicit, Tier B implicit, NOISE rejection) is
documented in ``screening_log.md`` and is intentionally implemented in a
single readable file with no external dependencies, so the screening can
be reproduced from a clean Python environment.

Run from the references folder:

    python filter_bib.py raw/scopus_export_2026-05-05.bib

Optional flags:

    --tier-a-out PATH   override default surrogates_esm.bib output
    --tier-b-out PATH   override default surrogates_esm_candidates.bib
    --csv-out    PATH   override default surrogates_esm_screening.csv

The script never edits the input file; the raw Scopus export under
``raw/`` is treated as a read-only SSOT artefact.
"""

from __future__ import annotations

# We import only standard-library modules so the script runs from any
# clean Python install without `pip install`. This is consistent with the
# repo rule of preferring simple, additive structures.
import argparse
import csv
import re
import sys
import unicodedata
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Tuple


# ---------------------------------------------------------------------------
# Tier vocabulary
#
# Each list is a closed vocabulary; matching is substring-based on a
# single ASCII-folded, lower-cased text bag built from
# ``title + abstract + author_keywords + keywords``. Keeping the lists
# explicit (rather than using fancy regex with word boundaries everywhere)
# makes the screening criteria auditable and easy to extend during
# manual screening.
#
# All terms are kept lower-case; ASCII folding (e.g. "doğan" -> "dogan")
# happens on the search text, not on the vocabulary.
# ---------------------------------------------------------------------------

# Tier A: explicit surrogate-method terminology.
#
# Note on ``emulator`` / ``emulation``: in the power-systems literature
# these words almost always refer to *hardware* concepts (PV emulator,
# battery emulator, virtual inertia emulation, generator emulation in
# converter control), not to a numerical surrogate of an expensive
# model. The bare tokens are therefore deliberately *not* in this list.
# We only count them when they appear in a phrase that unambiguously
# implies a data-driven emulator of an underlying simulator / optimizer.
SURR_TERMS: Tuple[str, ...] = (
    "surrogate",
    "metamodel",
    "meta-model",
    "meta model",
    "metamodelling",
    "metamodeling",
    "response surface",
    "response surface methodology",
    "kriging",
    "co-kriging",
    "gaussian process",
    "gp regression",
    "polynomial chaos",
    "radial basis function",
    "rbf network",
    "rbf surrogate",
    "learning to optimize",
    "learning-to-optimize",
    "optimization proxy",
    "neural proxy",
    "proxy model",
    "surrogate-assisted",
    "surrogate assisted",
    # Emulator phrases that clearly mean a numerical / data-driven
    # surrogate, not hardware-in-the-loop emulation.
    "neural emulator",
    "neural network emulator",
    "neural-network emulator",
    "machine learning emulator",
    "machine-learning emulator",
    "deep learning emulator",
    "deep-learning emulator",
    "data-driven emulator",
    "data driven emulator",
    "gp emulator",
    "gaussian process emulator",
    "gaussian-process emulator",
    "surrogate emulator",
    "simulator emulator",
    "simulation emulator",
    "computer model emulator",
    "computer-model emulator",
    "statistical emulator",
)

# ML / regression methods that *might* be used as a surrogate. Tier B
# requires one of these AND a proxy hint AND optimization context AND
# energy-system context.
ML_TERMS: Tuple[str, ...] = (
    "neural network",
    "deep learning",
    "machine learning",
    "random forest",
    "gradient boosting",
    "xgboost",
    "support vector",
    "regression tree",
    "regression model",
    "data-driven model",
    "learned model",
    "learning-based",
    "convolutional neural",
    "recurrent neural",
    "lstm",
    "transformer model",
    "graph neural",
    "physics-informed neural",
    "polynomial regression",
    "decision tree regressor",
)

# Optimization context: the entry must be about a real optimization /
# decision-making task in the energy domain, not a stand-alone forecasting
# or classification paper.
OPT_TERMS: Tuple[str, ...] = (
    "optimization",
    "optimisation",
    "dispatch",
    "unit commitment",
    "economic dispatch",
    "optimal power flow",
    "capacity expansion",
    "generation expansion",
    "energy planning",
    "scheduling",
    "milp",
    "mixed-integer",
    "mixed integer",
    "multi-objective",
    "multi objective",
    "pareto",
    "bilevel",
    "stochastic programming",
    "robust optimization",
    "chance constraint",
    "scenario reduction",
    "model predictive",
)

# Energy-system context: keeps the review scoped to ESM rather than
# generic ML literature.
ESM_TERMS: Tuple[str, ...] = (
    "energy system",
    "power system",
    "electricity system",
    "electric power system",
    "district heating",
    "district energy",
    "multi-energy",
    "multi energy",
    "integrated energy",
    "sector coupling",
    "unit commitment",
    "economic dispatch",
    "optimal power flow",
    "capacity expansion",
    "generation expansion",
    "microgrid",
    "smart grid",
    "renewable energy",
    "power grid",
    "energy planning",
    "energy dispatch",
    "combined heat and power",
    " chp ",
    "heat pump",
    "thermal storage",
    "energy hub",
    "virtual power plant",
)

# Proxy / surrogate-indicator phrases. Tier B requires at least one of
# these; together with ML + OPT + ESM they signal that the ML model is
# used as a stand-in for an expensive component (which is exactly the
# definition of a surrogate, even when the term itself is absent).
PROXY_HINTS: Tuple[str, ...] = (
    "proxy",
    "approximate",
    "approximation",
    "computationally expensive",
    "computational cost",
    "computation time",
    "reduce computation",
    "speed up",
    "speedup",
    "accelerate",
    "acceleration",
    "replace",
    "replacing the",
    "instead of",
    "in lieu of",
    "surrogate",
    "emulate",
    "emulating",
    "fast evaluation",
    "expensive simulation",
    "expensive model",
    "cheap evaluation",
    "expensive function",
    "train on",
    "trained on simulator",
    "trained on the optimizer",
)

# Noise terms: typical topics that show up as false positives when a
# paper uses ML on energy data but is not a surrogate-for-optimization
# study.
NOISE_TERMS: Tuple[str, ...] = (
    "fault diagnosis",
    "fault detection",
    "fault classification",
    "transformer fault",
    "wind speed forecasting",
    "load forecasting",
    "price forecasting",
    "site selection",
    "siting",
    "image recognition",
    "computer vision",
    "drug discovery",
    "molecular dynamics",
    "speech recognition",
    "text classification",
)


# ---------------------------------------------------------------------------
# BibTeX parser
#
# The Scopus BibTeX format used by this export is consistent enough to
# be parsed with a small custom state machine. We deliberately do not use
# bibtexparser because that would add a hard dependency for a one-off
# screening step.
#
# The parser scans the raw text, finds each ``@TYPE{key, ...}`` block by
# matching outer braces, and then extracts each ``name = {value}`` field
# from the body, again with a brace counter. This handles:
#   - multi-line abstracts that break naively on ``}\n``
#   - values containing nested braces (rare in Scopus exports but cheap
#     to support)
#   - tab-indented and space-indented field lines
# ---------------------------------------------------------------------------


@dataclass
class BibEntry:
    """Minimal in-memory representation of a single BibTeX entry."""

    type: str  # e.g. "ARTICLE", "INPROCEEDINGS"
    key: str   # citation key, e.g. "Lv2026"
    fields: Dict[str, str] = field(default_factory=dict)
    raw: str = ""  # the original block text, used for re-emit


def _scan_braced_block(text: str, start: int) -> Tuple[int, int]:
    """Return (open_brace_index, close_brace_index) for the block that
    starts with ``@`` at *start*, with both indices inclusive.

    Raises ``ValueError`` if the block is malformed.
    """

    # Find the opening ``{`` after the type name.
    open_idx = text.find("{", start)
    if open_idx == -1:
        raise ValueError("Missing '{' after entry type")

    # Walk forward, counting brace depth.
    depth = 1
    i = open_idx + 1
    while i < len(text) and depth > 0:
        ch = text[i]
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
        i += 1

    if depth != 0:
        raise ValueError("Unbalanced braces in entry")
    return open_idx, i - 1  # i was advanced past the closing brace


def _parse_fields(body: str) -> Dict[str, str]:
    """Parse ``name = {value}`` pairs from an entry body.

    The body is the text between the outer ``{...}`` of the entry, with
    the leading ``key,`` already stripped.
    """

    fields: Dict[str, str] = {}
    i = 0
    n = len(body)
    while i < n:
        # Skip whitespace and field separators.
        while i < n and body[i] in " \t\r\n,":
            i += 1
        if i >= n:
            break

        # Read field name up to '='.
        name_start = i
        while i < n and body[i] != "=":
            i += 1
        if i >= n:
            break
        name = body[name_start:i].strip().lower()
        i += 1  # skip '='

        # Skip whitespace, then expect '{'.
        while i < n and body[i] in " \t\r\n":
            i += 1
        if i >= n or body[i] != "{":
            # Some fields use raw values (e.g. year = 2026) without braces.
            # Read until next ','.
            value_start = i
            while i < n and body[i] != ",":
                i += 1
            fields[name] = body[value_start:i].strip()
            continue

        # Read braced value with a depth counter.
        i += 1  # skip the opening '{'
        depth = 1
        value_start = i
        while i < n and depth > 0:
            ch = body[i]
            if ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0:
                    break
            i += 1
        fields[name] = body[value_start:i]
        i += 1  # skip closing '}'

    return fields


def parse_bib(path: Path) -> List[BibEntry]:
    """Parse a Scopus BibTeX export into a list of :class:`BibEntry`.

    The function is intentionally tolerant: malformed entries are skipped
    with a warning on stderr rather than raising, so a single
    bad block does not abort the whole screening run.
    """

    text = path.read_text(encoding="utf-8", errors="replace")
    entries: List[BibEntry] = []

    # Pre-compile the entry-start regex; we only care about ``@`` followed
    # by a word and then ``{`` because some Scopus exports include a
    # leading "Scopus" / "EXPORT DATE" header that must be ignored.
    starts = [m.start() for m in re.finditer(r"@\w+\s*\{", text)]
    starts.append(len(text))  # sentinel so pairwise iteration covers the last entry

    for start, next_start in zip(starts[:-1], starts[1:]):
        try:
            # Type = chars between '@' and the first '{'.
            open_brace = text.find("{", start)
            type_str = text[start + 1:open_brace].strip().upper()

            # Outer block braces.
            open_idx, close_idx = _scan_braced_block(text, start)

            inner = text[open_idx + 1:close_idx]
            # The first comma separates the citation key from the body.
            comma_idx = inner.find(",")
            if comma_idx == -1:
                raise ValueError("Missing ',' after citation key")
            key = inner[:comma_idx].strip()
            body = inner[comma_idx + 1:]

            entry = BibEntry(
                type=type_str,
                key=key,
                fields=_parse_fields(body),
                raw=text[start:close_idx + 1],
            )
            entries.append(entry)
        except Exception as exc:  # pragma: no cover - defensive
            sys.stderr.write(
                f"warning: skipping malformed entry near offset {start}: {exc}\n"
            )

    return entries


# ---------------------------------------------------------------------------
# Tier classification
# ---------------------------------------------------------------------------


def _ascii_fold(text: str) -> str:
    """Lower-case and strip diacritics so substring matches are robust to
    German umlauts, Polish/Spanish accents, etc. Without this, terms like
    "Doğan" or "Müller" would not match keyword lists written in plain
    ASCII.
    """

    folded = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode("ascii")
    return folded.lower()


def _build_text_bag(entry: BibEntry) -> str:
    """Concatenate the screen-relevant fields into a single search bag.

    We deliberately include all four fields so a single keyword in the
    abstract or in Scopus-supplied index terms is enough to flag an
    entry. Spaces are added so phrase matches across field boundaries
    don't accidentally fire (e.g. ``...modeloptimization...``).
    """

    parts = [
        entry.fields.get("title", ""),
        entry.fields.get("abstract", ""),
        entry.fields.get("author_keywords", ""),
        entry.fields.get("keywords", ""),
    ]
    return _ascii_fold(" \n ".join(parts))


def _matched_terms(bag: str, vocab: Tuple[str, ...]) -> List[str]:
    """Return the list of vocabulary terms that occur in *bag*.

    Each vocabulary item is a plain substring; we compare it directly
    against the lower-cased text bag. Word-boundary correctness is not
    necessary because the vocabulary is curated to avoid problematic
    short tokens (e.g. ``" chp "`` is wrapped with spaces explicitly).
    """

    return [t for t in vocab if t in bag]


def classify_entry(entry: BibEntry) -> Dict[str, object]:
    """Run the tier-A / tier-B / reject classification for one entry.

    Returns a dict with the decision and the matched-term lists, ready
    to be written into the screening CSV.
    """

    bag = _build_text_bag(entry)

    surr_hits = _matched_terms(bag, SURR_TERMS)
    ml_hits = _matched_terms(bag, ML_TERMS)
    opt_hits = _matched_terms(bag, OPT_TERMS)
    esm_hits = _matched_terms(bag, ESM_TERMS)
    proxy_hits = _matched_terms(bag, PROXY_HINTS)
    noise_hits = _matched_terms(bag, NOISE_TERMS)

    # Tier A: any explicit surrogate term plus an energy-system context.
    if surr_hits and esm_hits:
        tier = "A"
        decision = "accept"

    # Tier B: implicit surrogate, requires the full ML+OPT+ESM+PROXY pattern.
    elif ml_hits and opt_hits and esm_hits and proxy_hits:
        # Strong noise demotes Tier B to a reject so the candidate file
        # does not fill up with pure forecasting / fault-diagnosis papers.
        if len(noise_hits) >= 2:
            tier = "B-noisy"
            decision = "reject"
        else:
            tier = "B"
            decision = "candidate"

    else:
        tier = "out"
        decision = "reject"

    return {
        "tier": tier,
        "decision": decision,
        "surr_hits": surr_hits,
        "ml_hits": ml_hits,
        "opt_hits": opt_hits,
        "esm_hits": esm_hits,
        "proxy_hits": proxy_hits,
        "noise_hits": noise_hits,
    }


# ---------------------------------------------------------------------------
# Output writers
# ---------------------------------------------------------------------------


def write_bib(entries: List[BibEntry], path: Path) -> None:
    """Write a list of entries to a BibTeX file as one block per entry,
    separated by a single blank line. The original raw block is reused
    so we keep the exact field formatting Scopus produced.
    """

    with path.open("w", encoding="utf-8") as f:
        f.write("% Generated by filter_bib.py from raw/scopus_export_*.bib\n")
        f.write("% Do not edit by hand: the file is regenerated whenever\n")
        f.write("% the screening filter is re-run.\n\n")
        for e in entries:
            f.write(e.raw)
            f.write("\n\n")


def write_screening_csv(rows: List[Dict[str, object]], path: Path) -> None:
    """Write one row per entry with the decision and matched-term lists.

    The CSV is the seed of the evidence map: each row will eventually be
    enriched with the manual columns (``task_class``, ``surrogate_family``,
    ``role``, ``data_source``, ``decision_impact_reported``, etc.).
    """

    fieldnames = [
        "cite_key",
        "year",
        "type",
        "title",
        "journal",
        "doi",
        "tier",
        "decision",
        "matched_surrogate_terms",
        "matched_ml_terms",
        "matched_opt_terms",
        "matched_esm_terms",
        "matched_proxy_hints",
        "matched_noise_terms",
    ]
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for r in rows:
            writer.writerow(r)


# ---------------------------------------------------------------------------
# Driver
# ---------------------------------------------------------------------------


def main(argv: List[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "raw_bib",
        type=Path,
        help="path to the raw Scopus BibTeX export (e.g. raw/scopus_export_2026-05-05.bib)",
    )
    parser.add_argument(
        "--tier-a-out",
        type=Path,
        default=Path("surrogates_esm.bib"),
        help="output path for the Tier A bibliography",
    )
    parser.add_argument(
        "--tier-b-out",
        type=Path,
        default=Path("surrogates_esm_candidates.bib"),
        help="output path for the Tier B candidate bibliography",
    )
    parser.add_argument(
        "--csv-out",
        type=Path,
        default=Path("surrogates_esm_screening.csv"),
        help="output path for the screening CSV",
    )
    args = parser.parse_args(argv)

    if not args.raw_bib.exists():
        sys.stderr.write(f"error: raw bib not found: {args.raw_bib}\n")
        return 2

    print(f"Reading {args.raw_bib} ...")
    entries = parse_bib(args.raw_bib)
    print(f"Parsed {len(entries)} entries.")

    tier_a: List[BibEntry] = []
    tier_b: List[BibEntry] = []
    rejected: List[BibEntry] = []
    rows: List[Dict[str, object]] = []

    for entry in entries:
        result = classify_entry(entry)

        rows.append({
            "cite_key": entry.key,
            "year": entry.fields.get("year", "").strip(),
            "type": entry.type,
            "title": entry.fields.get("title", "").strip().replace("\n", " "),
            "journal": entry.fields.get("journal", "").strip(),
            "doi": entry.fields.get("doi", "").strip(),
            "tier": result["tier"],
            "decision": result["decision"],
            "matched_surrogate_terms": "; ".join(result["surr_hits"]),
            "matched_ml_terms": "; ".join(result["ml_hits"]),
            "matched_opt_terms": "; ".join(result["opt_hits"]),
            "matched_esm_terms": "; ".join(result["esm_hits"]),
            "matched_proxy_hints": "; ".join(result["proxy_hits"]),
            "matched_noise_terms": "; ".join(result["noise_hits"]),
        })

        if result["tier"] == "A":
            tier_a.append(entry)
        elif result["tier"] == "B":
            tier_b.append(entry)
        else:
            rejected.append(entry)

    write_bib(tier_a, args.tier_a_out)
    write_bib(tier_b, args.tier_b_out)
    write_screening_csv(rows, args.csv_out)

    print()
    print("Tier A (explicit surrogate)      :", len(tier_a))
    print("Tier B (implicit, manual review) :", len(tier_b))
    print("Rejected                         :", len(rejected))
    print()
    print("Wrote:")
    print(" ", args.tier_a_out)
    print(" ", args.tier_b_out)
    print(" ", args.csv_out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
