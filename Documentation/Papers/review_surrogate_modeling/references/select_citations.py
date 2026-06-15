"""Print curated citation lists from the enriched screening CSV.

Used during manuscript drafting to pick representative \\cite{} keys
per surrogate family and per energy-system task class without rummaging
through 1270 raw bib entries.

Each "bucket" defined below is a small set of substring criteria over
the matched-term columns plus an optional OpenAlex ``primary_topic``
allowlist. We then sort each bucket by citation count and print the
top ``--top`` entries.

Usage::

    python select_citations.py --top 10 --csv surrogates_esm_screening_enriched.csv
"""

from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path
from typing import Callable, Dict, List


def matches_terms(row: Dict[str, str], col: str, terms: List[str]) -> bool:
    """Return True if any of *terms* appears in row[col] (case-insensitive)."""

    bag = (row.get(col, "") or "").lower()
    return any(t.lower() in bag for t in terms)


def topic_in(row: Dict[str, str], topics: List[str]) -> bool:
    if not topics:
        return True  # no constraint
    pt = (row.get("primary_topic", "") or "").lower()
    return any(t.lower() in pt for t in topics)


def cit(row: Dict[str, str]) -> int:
    try:
        return int(row.get("cited_by_count", "") or 0)
    except ValueError:
        return 0


# Bucket definitions: (display name, term-column matchers, topic filter).
# The tuples in ``surr_terms`` use the surrogate-term column from the
# screening CSV; topic filter is optional and uses the OpenAlex
# ``primary_topic`` column.
BUCKETS = [
    {
        "name": "Gaussian process / kriging",
        "surr": ["gaussian process", "kriging", "co-kriging", "gp regression", "gaussian process emulator", "gp emulator"],
        "topics": [],
    },
    {
        "name": "Polynomial chaos / response surface",
        "surr": ["polynomial chaos", "response surface", "response surface methodology"],
        "topics": [],
    },
    {
        "name": "Radial basis function / kernel",
        "surr": ["radial basis function", "rbf network", "rbf surrogate"],
        "topics": [],
    },
    {
        "name": "Surrogate (general; explicit term)",
        "surr": ["surrogate"],
        "topics": [],
    },
    {
        "name": "Metamodel (explicit term)",
        "surr": ["metamodel", "meta-model", "meta model", "metamodelling", "metamodeling"],
        "topics": [],
    },
    {
        "name": "Surrogate-assisted optimization",
        "surr": ["surrogate-assisted", "surrogate assisted"],
        "topics": [],
    },
    {
        "name": "Learning-to-optimize / decision proxy",
        "surr": ["learning to optimize", "learning-to-optimize", "optimization proxy", "neural proxy", "proxy model"],
        "topics": [],
    },
    {
        "name": "Statistical / data-driven emulator",
        "surr": ["neural emulator", "neural network emulator", "machine learning emulator", "deep learning emulator", "data-driven emulator", "gaussian process emulator", "gp emulator", "statistical emulator", "computer model emulator"],
        "topics": [],
    },
    # Task-class buckets use the ESM-term column of the screening CSV.
    {
        "name": "Capacity / generation expansion",
        "surr": [],
        "esm": ["capacity expansion", "generation expansion"],
        "topics": [],
    },
    {
        "name": "Unit commitment / economic dispatch",
        "surr": [],
        "esm": ["unit commitment", "economic dispatch"],
        "topics": [],
    },
    {
        "name": "Optimal power flow",
        "surr": [],
        "esm": ["optimal power flow"],
        "topics": [],
    },
    {
        "name": "District heating",
        "surr": [],
        "esm": ["district heating", "district energy"],
        "topics": [],
    },
    {
        "name": "Multi-energy / sector coupling",
        "surr": [],
        "esm": ["multi-energy", "multi energy", "integrated energy", "sector coupling"],
        "topics": [],
    },
    {
        "name": "Microgrid / energy hub",
        "surr": [],
        "esm": ["microgrid", "energy hub", "virtual power plant"],
        "topics": [],
    },
    {
        "name": "Multi-objective system design",
        "surr": [],
        "opt": ["multi-objective", "multi objective", "pareto"],
        "topics": [],
    },
    {
        "name": "Stochastic / robust planning",
        "surr": [],
        "opt": ["stochastic programming", "robust optimization", "chance constraint", "scenario reduction"],
        "topics": [],
    },
    {
        "name": "Reviews and surveys (any task)",
        "surr": [],
        "topics": [],
        "review_only": True,
    },
]


def build_predicate(bucket: Dict) -> Callable[[Dict[str, str]], bool]:
    """Return a row predicate from a bucket definition."""

    def pred(row: Dict[str, str]) -> bool:
        if row.get("tier") != "A":
            return False

        if bucket.get("review_only"):
            title = (row.get("title", "") or "").lower()
            review_in_title = any(kw in title for kw in ("review", "survey", "roadmap", "state of the art"))
            return review_in_title

        if bucket.get("surr") and not matches_terms(row, "matched_surrogate_terms", bucket["surr"]):
            return False
        if bucket.get("esm") and not matches_terms(row, "matched_esm_terms", bucket["esm"]):
            return False
        if bucket.get("opt") and not matches_terms(row, "matched_opt_terms", bucket["opt"]):
            return False
        if not topic_in(row, bucket.get("topics", [])):
            return False
        return True

    return pred


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--csv",
        type=Path,
        default=Path("surrogates_esm_screening_enriched.csv"),
        help="enriched screening CSV",
    )
    parser.add_argument(
        "--top",
        type=int,
        default=12,
        help="how many entries per bucket to print",
    )
    parser.add_argument(
        "--bucket",
        type=str,
        default="",
        help="optional substring filter on bucket name",
    )
    args = parser.parse_args(argv)

    rows = list(csv.DictReader(args.csv.open(encoding="utf-8")))

    for bucket in BUCKETS:
        if args.bucket and args.bucket.lower() not in bucket["name"].lower():
            continue
        pred = build_predicate(bucket)
        hits = [r for r in rows if pred(r)]
        hits.sort(key=cit, reverse=True)
        print(f"### {bucket['name']}  ({len(hits)} entries)")
        for r in hits[: args.top]:
            print(f"  {r['cite_key']:<25}  cit={r['cited_by_count']:>5}  oa={r['oa_status']:<8}  {r['title'][:90]}")
        print()
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
