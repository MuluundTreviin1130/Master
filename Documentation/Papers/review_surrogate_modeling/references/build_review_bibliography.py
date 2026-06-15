"""Build the combined bibliography for the narrowed review.

The review is now scoped towards surrogate models for multi-objective
optimization of multi-energy systems. That requires two complementary
literature pools:

1. the broad surrogate-in-energy-systems Tier-A set
   (``surrogates_esm.bib``), and
2. the user's prior MOO/MES Scopus export focus set
   (``moo_mes_focus.bib``).

This script merges both pools into one manuscript bibliography:

- ``review_mes_moo_surrogates.bib``
- ``review_mes_moo_surrogates_manifest.csv``

Deduplication is DOI-first, citation-key-second. If the same DOI appears
in both pools, the first occurrence is kept and the source flags are
merged in the manifest. Raw input files are never modified.
"""

from __future__ import annotations

import argparse
import csv
import re
from collections import Counter, defaultdict
from pathlib import Path
from typing import Dict, List, Tuple

from filter_bib import BibEntry, parse_bib


def normalized_doi(entry: BibEntry) -> str:
    """Return a stable DOI key or an empty string if absent."""

    doi = (entry.fields.get("doi") or "").strip().lower()
    doi = doi.removeprefix("https://doi.org/").removeprefix("doi:")
    return doi


def normalized_key(entry: BibEntry) -> str:
    """Return citation-key fallback for entries without DOI."""

    return entry.key.strip().lower()


def identity(entry: BibEntry) -> Tuple[str, str]:
    """DOI-first identity used for deduplication."""

    doi = normalized_doi(entry)
    if doi:
        return ("doi", doi)
    return ("key", normalized_key(entry))


def year(entry: BibEntry) -> str:
    raw = (entry.fields.get("year") or entry.fields.get("date") or "").strip()
    match = re.search(r"(19|20)\d{2}", raw)
    return match.group(0) if match else ""


def title(entry: BibEntry) -> str:
    return re.sub(r"\s+", " ", entry.fields.get("title", "")).strip()


def venue(entry: BibEntry) -> str:
    value = (
        entry.fields.get("journal")
        or entry.fields.get("journaltitle")
        or entry.fields.get("booktitle")
        or entry.fields.get("publisher")
        or ""
    )
    return re.sub(r"\s+", " ", value).strip()


def raw_with_key(entry: BibEntry, new_key: str) -> str:
    """Return the raw BibTeX block with the citation key replaced.

    We only rewrite the generated combined bibliography. Source pools stay
    untouched. This keeps Zotero / Scopus exports reproducible while making
    the manuscript bibliography BibTeX-safe.
    """

    return re.sub(
        r"^(@\w+\s*\{)\s*[^,]+",
        rf"\g<1>{new_key}",
        entry.raw,
        count=1,
        flags=re.MULTILINE,
    )


def load_pool(path: Path, label: str) -> List[Tuple[BibEntry, str]]:
    entries = parse_bib(path)
    if not entries:
        raise RuntimeError(f"no BibTeX entries parsed from {path}")
    return [(entry, label) for entry in entries]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--surrogate-bib", type=Path, default=Path("surrogates_esm.bib"))
    parser.add_argument("--moo-mes-bib", type=Path, default=Path("moo_mes_focus.bib"))
    parser.add_argument(
        "--extra-bib",
        type=Path,
        default=Path("external_reviews.bib"),
        help=(
            "Optional third source pool with externally-supplied reviews "
            "that fall outside the Scopus search-string keyword cone "
            "(e.g. Comp. Chem. Eng. or pure math venues) but are still "
            "directly relevant for the manuscript. Skipped if the file is "
            "absent."
        ),
    )
    parser.add_argument("--out-bib", type=Path, default=Path("review_mes_moo_surrogates.bib"))
    parser.add_argument(
        "--manifest-out",
        type=Path,
        default=Path("review_mes_moo_surrogates_manifest.csv"),
    )
    args = parser.parse_args()

    pools = []
    pools.extend(load_pool(args.surrogate_bib, "surrogate_esm_tier_a"))
    pools.extend(load_pool(args.moo_mes_bib, "moo_mes_focus"))
    if args.extra_bib.exists():
        pools.extend(load_pool(args.extra_bib, "external_reviews"))

    by_id: Dict[Tuple[str, str], BibEntry] = {}
    sources: Dict[Tuple[str, str], set[str]] = defaultdict(set)
    duplicates = 0

    for entry, label in pools:
        ident = identity(entry)
        if ident in by_id:
            duplicates += 1
        else:
            by_id[ident] = entry
        sources[ident].add(label)

    kept = list(by_id.items())

    # DOI-first deduplication does not guarantee unique BibTeX keys:
    # Scopus-generated keys such as Wang2025 or Zhang2025 can occur many
    # times for different papers. Keep the first key unchanged so existing
    # manuscript cites remain stable; suffix later occurrences in the
    # generated bibliography only.
    key_counts: Counter[str] = Counter()
    output_keys: Dict[Tuple[str, str], str] = {}
    renamed_keys: Dict[Tuple[str, str], str] = {}
    for ident, entry in kept:
        key_counts[entry.key] += 1
        if key_counts[entry.key] == 1:
            out_key = entry.key
        else:
            out_key = f"{entry.key}__{key_counts[entry.key]}"
            renamed_keys[ident] = out_key
        output_keys[ident] = out_key

    with args.out_bib.open("w", encoding="utf-8") as f:
        f.write("% Generated by build_review_bibliography.py.\n")
        f.write("% Combines surrogates_esm.bib and moo_mes_focus.bib.\n")
        f.write("% Do not edit by hand; edit the source pools and rebuild.\n\n")
        for ident, entry in kept:
            f.write(raw_with_key(entry, output_keys[ident]))
            f.write("\n\n")

    with args.manifest_out.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=[
                "cite_key",
                "original_cite_key",
                "identity_type",
                "identity_value",
                "year",
                "title",
                "venue",
                "doi",
                "sources",
            ],
        )
        writer.writeheader()
        for ident, entry in kept:
            writer.writerow(
                {
                    "cite_key": output_keys[ident],
                    "original_cite_key": entry.key,
                    "identity_type": ident[0],
                    "identity_value": ident[1],
                    "year": year(entry),
                    "title": title(entry),
                    "venue": venue(entry),
                    "doi": normalized_doi(entry),
                    "sources": ";".join(sorted(sources[ident])),
                }
            )

    source_counts = Counter()
    for labels in sources.values():
        source_counts["+".join(sorted(labels))] += 1

    print(f"Input entries                  : {len(pools)}")
    print(f"Deduplicated entries kept      : {len(kept)}")
    print(f"Duplicate identities collapsed : {duplicates}")
    print(f"Duplicate cite keys renamed    : {len(renamed_keys)}")
    print()
    print("Source composition:")
    for label, count in source_counts.most_common():
        print(f"  {label:<40} {count}")
    print()
    print(f"Wrote {args.out_bib}")
    print(f"Wrote {args.manifest_out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
