"""Enrich the merged review bibliography with OpenAlex country data.

The current BibTeX exports do not contain affiliation/country metadata.
OpenAlex can recover this for many DOI records through the ``authorships``
field. This script reads the merged bibliography manifest, queries OpenAlex
for missing DOIs (reusing ``.openalex_cache.jsonl``), and exports country
coverage tables for Excel / map figures.

Outputs (default):

- ``../figures/openalex_country_records.csv``
- ``../figures/openalex_country_counts.csv``
- ``../figures/openalex_country_data.xlsx``

Counting:

- full count: each country appearing on a paper receives 1 count
- fractional count: each country receives 1 / number_of_countries_on_paper
- first-author count: countries on the first authorship receive 1 count

Country codes are ISO alpha-2 codes from OpenAlex. Excel's filled map charts
can usually use these directly.
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
import time
from collections import Counter, defaultdict
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Set

import pandas as pd

from enrich_openalex import append_cache, fetch_one, load_cache


ROOT = Path(__file__).resolve().parents[1]
REF = ROOT / "references"
FIG = ROOT / "figures"

COUNTRY_NAMES = {
    "AE": "United Arab Emirates",
    "AR": "Argentina",
    "AT": "Austria",
    "AU": "Australia",
    "BE": "Belgium",
    "BR": "Brazil",
    "CA": "Canada",
    "CH": "Switzerland",
    "CL": "Chile",
    "CN": "China",
    "CO": "Colombia",
    "CZ": "Czechia",
    "DE": "Germany",
    "DK": "Denmark",
    "DZ": "Algeria",
    "EG": "Egypt",
    "ES": "Spain",
    "FI": "Finland",
    "FR": "France",
    "GB": "United Kingdom",
    "GR": "Greece",
    "HK": "Hong Kong",
    "ID": "Indonesia",
    "IE": "Ireland",
    "IN": "India",
    "IQ": "Iraq",
    "IR": "Iran",
    "IT": "Italy",
    "JP": "Japan",
    "KR": "South Korea",
    "LB": "Lebanon",
    "MA": "Morocco",
    "MX": "Mexico",
    "MY": "Malaysia",
    "NG": "Nigeria",
    "NL": "Netherlands",
    "NO": "Norway",
    "NZ": "New Zealand",
    "PK": "Pakistan",
    "PL": "Poland",
    "PT": "Portugal",
    "QA": "Qatar",
    "RO": "Romania",
    "RU": "Russia",
    "SA": "Saudi Arabia",
    "SE": "Sweden",
    "SG": "Singapore",
    "TH": "Thailand",
    "TN": "Tunisia",
    "TR": "Turkey",
    "TW": "Taiwan",
    "UA": "Ukraine",
    "US": "United States",
    "ZA": "South Africa",
}


def norm_doi(doi: str) -> str:
    """Normalize DOI strings to the cache key used by ``enrich_openalex``."""

    value = (doi or "").strip().lower()
    if value.startswith("https://doi.org/"):
        value = value[len("https://doi.org/") :]
    if value.startswith("doi:"):
        value = value[4:]
    return value


def country_name(code: str) -> str:
    """Resolve ISO alpha-2 country code to name if pycountry is installed."""

    if code in COUNTRY_NAMES:
        return COUNTRY_NAMES[code]
    try:
        import pycountry  # type: ignore

        country = pycountry.countries.get(alpha_2=code)
        return country.name if country else code
    except Exception:
        return code


def countries_from_authorship(authorship: Dict) -> Set[str]:
    """Extract country codes from one OpenAlex authorship object."""

    countries: Set[str] = set()

    # Newer OpenAlex records may expose country codes directly here.
    for code in authorship.get("countries") or []:
        if code:
            countries.add(str(code).upper())

    # The most reliable path is institutions[*].country_code.
    for inst in authorship.get("institutions") or []:
        code = inst.get("country_code")
        if code:
            countries.add(str(code).upper())

    return countries


def work_country_data(work: Dict) -> Dict[str, object]:
    """Summarise country metadata from an OpenAlex work."""

    authorships = work.get("authorships") or []
    paper_countries: Set[str] = set()
    first_author_countries: Set[str] = set()
    institution_names: Set[str] = set()

    for idx, authorship in enumerate(authorships):
        auth_countries = countries_from_authorship(authorship)
        paper_countries.update(auth_countries)
        if idx == 0:
            first_author_countries.update(auth_countries)

        for inst in authorship.get("institutions") or []:
            name = inst.get("display_name")
            if name:
                institution_names.add(str(name))

    return {
        "country_codes": sorted(paper_countries),
        "first_author_country_codes": sorted(first_author_countries),
        "institution_count": len(institution_names),
    }


def read_manifest(path: Path) -> List[Dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def write_csv(rows: List[Dict[str, object]], path: Path, fieldnames: List[str]) -> None:
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def main(argv: List[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--manifest",
        type=Path,
        default=REF / "review_mes_moo_surrogates_manifest.csv",
    )
    parser.add_argument(
        "--cache",
        type=Path,
        default=REF / ".openalex_cache.jsonl",
    )
    parser.add_argument("--mailto", type=str, default="")
    parser.add_argument("--rate-sleep", type=float, default=0.12)
    parser.add_argument(
        "--max",
        type=int,
        default=0,
        help="maximum new OpenAlex fetches for this run; 0 means no limit",
    )
    parser.add_argument(
        "--records-out",
        type=Path,
        default=FIG / "csv" / "openalex_country_records.csv",
    )
    parser.add_argument(
        "--counts-out",
        type=Path,
        default=FIG / "csv" / "openalex_country_counts.csv",
    )
    parser.add_argument(
        "--xlsx-out",
        type=Path,
        default=FIG / "source_data" / "openalex_country_data.xlsx",
    )
    args = parser.parse_args(argv)

    manifest = read_manifest(args.manifest)
    cache = load_cache(args.cache)
    print(f"Manifest records: {len(manifest)}")
    print(f"OpenAlex cache  : {len(cache)} DOI records")

    new_fetches = 0
    stop_fetching = False
    record_rows: List[Dict[str, object]] = []
    full_counts: Counter[str] = Counter()
    fractional_counts: defaultdict[str, float] = defaultdict(float)
    first_author_counts: Counter[str] = Counter()

    doi_rows = [row for row in manifest if norm_doi(row.get("doi", ""))]
    print(f"Records with DOI: {len(doi_rows)}")

    for idx, row in enumerate(manifest, 1):
        doi = norm_doi(row.get("doi", ""))
        work: Dict = {}
        has_openalex = False

        if doi:
            if doi in cache:
                work = cache[doi]
            elif not stop_fetching:
                work = fetch_one(doi, mailto=args.mailto)
                append_cache(args.cache, doi, work)
                cache[doi] = work
                new_fetches += 1
                if args.rate_sleep > 0:
                    time.sleep(args.rate_sleep)
                if args.max and new_fetches >= args.max:
                    stop_fetching = True
                    sys.stderr.write(
                        f"reached --max={args.max}; remaining uncached DOIs will be skipped\n"
                    )

        has_openalex = bool(work)
        data = work_country_data(work) if work else {
            "country_codes": [],
            "first_author_country_codes": [],
            "institution_count": 0,
        }
        countries = list(data["country_codes"])
        first_countries = list(data["first_author_country_codes"])

        if countries:
            for code in countries:
                full_counts[code] += 1
                fractional_counts[code] += 1.0 / len(countries)
        for code in first_countries:
            first_author_counts[code] += 1

        record_rows.append(
            {
                "cite_key": row.get("cite_key", ""),
                "year": row.get("year", ""),
                "title": row.get("title", ""),
                "venue": row.get("venue", ""),
                "doi": doi,
                "sources": row.get("sources", ""),
                "has_openalex": "1" if has_openalex else "0",
                "has_country": "1" if countries else "0",
                "country_codes": ";".join(countries),
                "country_count": len(countries),
                "first_author_country_codes": ";".join(first_countries),
                "institution_count": data["institution_count"],
                "openalex_id": work.get("id", "") if work else "",
            }
        )

        if idx % 250 == 0:
            print(f"  processed {idx}/{len(manifest)}; new fetches {new_fetches}")

    count_rows: List[Dict[str, object]] = []
    for code, full_count in full_counts.most_common():
        count_rows.append(
            {
                "country_code": code,
                "country_name": country_name(code),
                "papers_full_count": full_count,
                "papers_fractional_count": round(fractional_counts[code], 4),
                "first_author_papers": first_author_counts[code],
            }
        )

    write_csv(
        record_rows,
        args.records_out,
        [
            "cite_key",
            "year",
            "title",
            "venue",
            "doi",
            "sources",
            "has_openalex",
            "has_country",
            "country_codes",
            "country_count",
            "first_author_country_codes",
            "institution_count",
            "openalex_id",
        ],
    )
    write_csv(
        count_rows,
        args.counts_out,
        [
            "country_code",
            "country_name",
            "papers_full_count",
            "papers_fractional_count",
            "first_author_papers",
        ],
    )

    coverage = pd.DataFrame(
        [
            {"metric": "manifest_records", "value": len(manifest)},
            {"metric": "records_with_doi", "value": len(doi_rows)},
            {"metric": "records_with_openalex", "value": sum(1 for r in record_rows if r["has_openalex"] == "1")},
            {"metric": "records_with_country", "value": sum(1 for r in record_rows if r["has_country"] == "1")},
            {"metric": "unique_countries", "value": len(count_rows)},
            {"metric": "new_openalex_fetches", "value": new_fetches},
        ]
    )

    with pd.ExcelWriter(args.xlsx_out, engine="openpyxl") as writer:
        pd.DataFrame(record_rows).to_excel(writer, sheet_name="records_country", index=False)
        pd.DataFrame(count_rows).to_excel(writer, sheet_name="country_counts", index=False)
        coverage.to_excel(writer, sheet_name="coverage", index=False)
        for sheet in writer.book.worksheets:
            sheet.freeze_panes = "A2"
            for column_cells in sheet.columns:
                max_len = max(len(str(cell.value)) if cell.value is not None else 0 for cell in column_cells)
                sheet.column_dimensions[column_cells[0].column_letter].width = min(max(max_len + 2, 10), 70)

    print()
    print(f"Records with OpenAlex match: {coverage.loc[coverage.metric == 'records_with_openalex', 'value'].iloc[0]}")
    print(f"Records with country data  : {coverage.loc[coverage.metric == 'records_with_country', 'value'].iloc[0]}")
    print(f"Unique countries           : {len(count_rows)}")
    print(f"New OpenAlex fetches       : {new_fetches}")
    print()
    print(f"Wrote {args.records_out}")
    print(f"Wrote {args.counts_out}")
    print(f"Wrote {args.xlsx_out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
