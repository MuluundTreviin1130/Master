r"""Import and screen the MOO / multicriteria Scopus bibliography export.

This script complements ``filter_bib.py``. The original surrogate search
was intentionally broad over surrogate-model terminology. The user's
existing review draft, however, is built on a separate Scopus export about
multi-objective / multicriteria optimization in multi-energy systems.

The purpose here is therefore not to replace the surrogate bibliography,
but to add a second reproducible literature layer:

- ``moo_multicriteria_screening.csv``
    all entries from the MOO export with explicit keyword flags
- ``moo_mes_focus.bib`` / ``moo_mes_focus.csv``
    entries that match both the MOO and the MES / microgrid / HRES scope
- ``moo_mes_surrogate_focus.bib`` / ``moo_mes_surrogate_focus.csv``
    the smaller intersection where the MOO/MES paper also contains an
    explicit or implicit surrogate signal

Run from the ``references`` folder:

    python import_moo_multicriteria_export.py \
        raw/moo_multicriteria_scopus_export_2026-05-06.bib

The script is dependency-free and reuses the BibTeX parser and surrogate
vocabularies from ``filter_bib.py`` so all screening logic stays in one
auditable place.
"""

from __future__ import annotations

import argparse
import csv
import re
import sys
import unicodedata
from collections import Counter
from pathlib import Path
from typing import Dict, Iterable, List, Tuple

from filter_bib import (
    ML_TERMS,
    PROXY_HINTS,
    SURR_TERMS,
    BibEntry,
    parse_bib,
    write_bib,
)


# ---------------------------------------------------------------------------
# Focus vocabularies
#
# The MOO export already comes from a targeted Scopus query, but the raw
# file still contains broad renewable-energy and single-technology studies.
# These terms make the focus layer explicit and reproducible.
# ---------------------------------------------------------------------------

MOO_TERMS: Tuple[str, ...] = (
    "multi-objective",
    "multi objective",
    "multiobjective",
    "many-objective",
    "many objective",
    "multi-criteria",
    "multi criteria",
    "multicriteria",
    "pareto",
    "non-dominated",
    "nondominated",
    "nsga",
    "nsga-ii",
    "nsga ii",
    "nsga-iii",
    "nsga iii",
    "mopso",
    "moea",
    "moea/d",
    "spea2",
    "sms-emoa",
    "hypervolume",
)

MES_TERMS: Tuple[str, ...] = (
    "multi-energy",
    "multi energy",
    "integrated energy",
    "integrated electricity-heat",
    "electricity-heat",
    "electricity-gas",
    "sector coupling",
    "sector-coupling",
    "energy hub",
    "virtual power plant",
    "microgrid",
    "micro-grid",
    "micro grid",
    "microgrids",
    "energy community",
    "energy communities",
    "hybrid renewable energy system",
    "hybrid renewable energy systems",
    " hres",
    "off-grid",
    "stand-alone",
    "standalone",
    "distributed energy",
    "distributed resources",
    "distributed generation",
    "cchp",
    "combined cooling, heating, and power",
    "combined cooling heating and power",
    "combined heat and power",
    "chp",
    "district heating",
    "district cooling",
    "power-to-x",
    "power to x",
    "hydrogen",
    "electric vehicle",
    "electric vehicles",
)

MCDM_TERMS: Tuple[str, ...] = (
    "mcdm",
    "madm",
    "multi-criteria decision",
    "multi criteria decision",
    "multicriteria decision",
    "topsis",
    "vikor",
    "promethee",
    "ahp",
    "anp",
    "electre",
    "waspas",
    "codas",
)

ALGORITHM_TERMS: Tuple[str, ...] = (
    "genetic algorithm",
    "ga",
    "nsga",
    "particle swarm",
    "pso",
    "mopso",
    "differential evolution",
    "de algorithm",
    "grey wolf",
    "gwo",
    "beluga whale",
    "cuckoo search",
    "bat algorithm",
    "moea",
    "moea/d",
    "spea",
    "sms-emoa",
    "cma-es",
    "evolution strategy",
    "bayesian optimization",
    "reference vector",
)


def ascii_fold(text: str) -> str:
    """Lower-case and strip accents so matching is stable across exports."""

    return unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode("ascii").lower()


def clean_field(value: str) -> str:
    """Normalize whitespace in a BibTeX field for CSV output."""

    return re.sub(r"\s+", " ", value or "").strip()


def entry_year(entry: BibEntry) -> str:
    """Return a year from common Scopus / Better-BibTeX field names.

    Zotero-style exports often use ``date = {2024}``, while Scopus'
    native BibTeX export uses ``year = {2024}``. We fail fast only if
    neither field exists; missing years are retained as empty strings in
    the CSV because a few conference proceedings use odd metadata.
    """

    raw = clean_field(entry.fields.get("year") or entry.fields.get("date") or "")
    match = re.search(r"(19|20)\d{2}", raw)
    return match.group(0) if match else ""


def journal_name(entry: BibEntry) -> str:
    """Return journal / venue from the common field variants."""

    return clean_field(
        entry.fields.get("journal")
        or entry.fields.get("journaltitle")
        or entry.fields.get("booktitle")
        or entry.fields.get("publisher")
        or ""
    )


def text_bag(entry: BibEntry) -> str:
    """Build the screening text bag from title, abstract and keywords."""

    return ascii_fold(
        " \n ".join(
            [
                entry.fields.get("title", ""),
                entry.fields.get("abstract", ""),
                entry.fields.get("keywords", ""),
                entry.fields.get("author_keywords", ""),
            ]
        )
    )


def hits(bag: str, vocab: Iterable[str]) -> List[str]:
    """Return vocabulary terms that occur in ``bag``."""

    return [term for term in vocab if term in bag]


def classify(entry: BibEntry) -> Dict[str, object]:
    """Classify one entry for the narrowed review scope."""

    bag = text_bag(entry)
    moo_hits = hits(bag, MOO_TERMS)
    mes_hits = hits(bag, MES_TERMS)
    mcdm_hits = hits(bag, MCDM_TERMS)
    algo_hits = hits(bag, ALGORITHM_TERMS)
    surr_hits = hits(bag, SURR_TERMS)
    ml_hits = hits(bag, ML_TERMS)
    proxy_hits = hits(bag, PROXY_HINTS)

    is_moo = bool(moo_hits)
    is_mes = bool(mes_hits)
    is_mcdm = bool(mcdm_hits)

    # Explicit surrogate terms are high confidence. The implicit rule is
    # deliberately stricter: ML alone in energy systems is too broad, so
    # it must co-occur with proxy / approximation language.
    surrogate_signal = bool(surr_hits) or bool(ml_hits and proxy_hits)

    if is_moo and is_mes and surrogate_signal:
        focus = "moo_mes_surrogate"
    elif is_moo and is_mes:
        focus = "moo_mes"
    elif is_moo:
        focus = "moo_only"
    elif is_mes:
        focus = "mes_only"
    else:
        focus = "out"

    return {
        "focus": focus,
        "is_moo": is_moo,
        "is_mes": is_mes,
        "is_mcdm": is_mcdm,
        "surrogate_signal": surrogate_signal,
        "moo_hits": moo_hits,
        "mes_hits": mes_hits,
        "mcdm_hits": mcdm_hits,
        "algorithm_hits": algo_hits,
        "surrogate_hits": surr_hits,
        "ml_hits": ml_hits,
        "proxy_hits": proxy_hits,
    }


def write_rows(rows: List[Dict[str, str]], path: Path) -> None:
    """Write screening rows with a stable column order."""

    fieldnames = [
        "cite_key",
        "year",
        "type",
        "title",
        "journal",
        "doi",
        "focus",
        "is_moo",
        "is_mes",
        "is_mcdm",
        "surrogate_signal",
        "matched_moo_terms",
        "matched_mes_terms",
        "matched_mcdm_terms",
        "matched_algorithm_terms",
        "matched_surrogate_terms",
        "matched_ml_terms",
        "matched_proxy_hints",
    ]
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def main(argv: List[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "raw_bib",
        type=Path,
        help="raw MOO/multicriteria Scopus BibTeX export",
    )
    parser.add_argument("--screening-out", type=Path, default=Path("moo_multicriteria_screening.csv"))
    parser.add_argument("--focus-csv-out", type=Path, default=Path("moo_mes_focus.csv"))
    parser.add_argument("--focus-bib-out", type=Path, default=Path("moo_mes_focus.bib"))
    parser.add_argument(
        "--surrogate-csv-out",
        type=Path,
        default=Path("moo_mes_surrogate_focus.csv"),
    )
    parser.add_argument(
        "--surrogate-bib-out",
        type=Path,
        default=Path("moo_mes_surrogate_focus.bib"),
    )
    args = parser.parse_args(argv)

    if not args.raw_bib.exists():
        sys.stderr.write(f"error: raw bib not found: {args.raw_bib}\n")
        return 2

    entries = parse_bib(args.raw_bib)
    if not entries:
        sys.stderr.write(f"error: no BibTeX entries parsed from {args.raw_bib}\n")
        return 2

    rows: List[Dict[str, str]] = []
    focus_entries: List[BibEntry] = []
    surrogate_entries: List[BibEntry] = []

    for entry in entries:
        result = classify(entry)
        rows.append(
            {
                "cite_key": entry.key,
                "year": entry_year(entry),
                "type": entry.type,
                "title": clean_field(entry.fields.get("title", "")),
                "journal": journal_name(entry),
                "doi": clean_field(entry.fields.get("doi", "")),
                "focus": str(result["focus"]),
                "is_moo": "1" if result["is_moo"] else "0",
                "is_mes": "1" if result["is_mes"] else "0",
                "is_mcdm": "1" if result["is_mcdm"] else "0",
                "surrogate_signal": "1" if result["surrogate_signal"] else "0",
                "matched_moo_terms": "; ".join(result["moo_hits"]),
                "matched_mes_terms": "; ".join(result["mes_hits"]),
                "matched_mcdm_terms": "; ".join(result["mcdm_hits"]),
                "matched_algorithm_terms": "; ".join(result["algorithm_hits"]),
                "matched_surrogate_terms": "; ".join(result["surrogate_hits"]),
                "matched_ml_terms": "; ".join(result["ml_hits"]),
                "matched_proxy_hints": "; ".join(result["proxy_hits"]),
            }
        )

        if result["focus"] in {"moo_mes", "moo_mes_surrogate"}:
            focus_entries.append(entry)
        if result["focus"] == "moo_mes_surrogate":
            surrogate_entries.append(entry)

    write_rows(rows, args.screening_out)
    write_rows(
        [row for row in rows if row["focus"] in {"moo_mes", "moo_mes_surrogate"}],
        args.focus_csv_out,
    )
    write_rows(
        [row for row in rows if row["focus"] == "moo_mes_surrogate"],
        args.surrogate_csv_out,
    )
    write_bib(focus_entries, args.focus_bib_out)
    write_bib(surrogate_entries, args.surrogate_bib_out)

    focus_counts = Counter(row["focus"] for row in rows)
    print(f"Parsed entries                 : {len(entries)}")
    print(f"DOI coverage                   : {sum(1 for row in rows if row['doi'])}/{len(rows)}")
    print()
    print("Focus distribution:")
    for key, value in focus_counts.most_common():
        print(f"  {key:<18} {value}")
    print()
    print(f"Wrote screening CSV            : {args.screening_out}")
    print(f"Wrote MOO+MES CSV/Bib          : {args.focus_csv_out} / {args.focus_bib_out}")
    print(f"Wrote MOO+MES+Surrogate CSV/Bib: {args.surrogate_csv_out} / {args.surrogate_bib_out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
