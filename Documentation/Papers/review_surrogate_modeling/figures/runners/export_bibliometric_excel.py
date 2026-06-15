"""Export bibliometric data for manual Excel figure work.

The user wants to rebuild the bibliometric figure manually in Excel. This
script writes a multi-sheet workbook from the merged bibliography manifest
and the generated keyword-term table.

Output:

    bibliometric_data_review_mes_moo_surrogates.xlsx

Sheets:

- records_all
- yearly_counts
- yearly_by_source
- top_venues
- source_composition
- outlet_families
- keyword_terms
- notes
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[2]
REF = ROOT / "references"
FIG = ROOT / "figures"
CSV = FIG / "csv"
SOURCE_DATA = FIG / "source_data"


def classify_source(source: str) -> str:
    if source == "surrogate_esm_tier_a":
        return "Surrogate search only"
    if source == "moo_mes_focus":
        return "MOO/MES export only"
    if "surrogate_esm_tier_a" in source and "moo_mes_focus" in source:
        return "Both source pools"
    return "Other / unknown"


def classify_outlet_family(venue: str) -> str:
    v = (venue or "").lower()
    if any(
        token in v
        for token in (
            "applied energy",
            "energy",
            "energy conversion",
            "renewable",
            "journal of cleaner",
            "energy and buildings",
            "international journal of hydrogen",
        )
    ):
        return "Elsevier / energy journals"
    if any(token in v for token in ("ieee", "iet", "electric power", "power systems", "sustainable energy, grids")):
        return "IEEE / IET / power systems"
    if any(token in v for token in ("sustainability", "energies", "electronics", "frontiers", "automation")):
        return "MDPI / Frontiers / OA journals"
    if any(token in v for token in ("building", "district", "thermal", "applied thermal")):
        return "Buildings / district energy"
    return "Other venues"


def main() -> int:
    manifest = pd.read_csv(REF / "review_mes_moo_surrogates_manifest.csv")
    manifest["year"] = pd.to_numeric(manifest["year"], errors="coerce")
    manifest["source_group"] = manifest["sources"].fillna("").map(classify_source)
    manifest["outlet_family"] = manifest["venue"].fillna("").map(classify_outlet_family)

    records = manifest[
        [
            "cite_key",
            "original_cite_key",
            "year",
            "title",
            "venue",
            "doi",
            "sources",
            "source_group",
            "outlet_family",
        ]
    ].copy()

    records_valid_year = records.dropna(subset=["year"]).copy()
    records_valid_year["year"] = records_valid_year["year"].astype(int)

    yearly_counts = (
        records_valid_year.groupby("year", as_index=False)
        .size()
        .rename(columns={"size": "records"})
        .sort_values("year")
    )

    yearly_by_source = (
        records_valid_year.pivot_table(
            index="year",
            columns="source_group",
            values="cite_key",
            aggfunc="count",
            fill_value=0,
        )
        .reset_index()
        .sort_values("year")
    )

    top_venues = (
        records["venue"]
        .fillna("(unknown)")
        .replace("", "(unknown)")
        .value_counts()
        .rename_axis("venue")
        .reset_index(name="records")
    )

    source_composition = (
        records["source_group"]
        .value_counts()
        .rename_axis("source_group")
        .reset_index(name="records")
    )

    outlet_families = (
        records["outlet_family"]
        .value_counts()
        .rename_axis("outlet_family")
        .reset_index(name="records")
    )

    keyword_terms_path = CSV / "fig_06_keyword_terms.csv"
    keyword_terms = pd.read_csv(keyword_terms_path) if keyword_terms_path.exists() else pd.DataFrame()

    notes = pd.DataFrame(
        [
            {
                "item": "bibliography",
                "value": "references/review_mes_moo_surrogates.bib",
            },
            {
                "item": "manifest",
                "value": "references/review_mes_moo_surrogates_manifest.csv",
            },
            {
                "item": "record_count",
                "value": str(len(records)),
            },
            {
                "item": "country_data",
                "value": "Not available in current BibTeX export; use Scopus affiliation export or OpenAlex DOI enrichment.",
            },
            {
                "item": "created_by",
                "value": "figures/export_bibliometric_excel.py",
            },
        ]
    )

    out = SOURCE_DATA / "bibliometric_data_review_mes_moo_surrogates.xlsx"
    with pd.ExcelWriter(out, engine="openpyxl") as writer:
        records.to_excel(writer, sheet_name="records_all", index=False)
        yearly_counts.to_excel(writer, sheet_name="yearly_counts", index=False)
        yearly_by_source.to_excel(writer, sheet_name="yearly_by_source", index=False)
        top_venues.to_excel(writer, sheet_name="top_venues", index=False)
        source_composition.to_excel(writer, sheet_name="source_composition", index=False)
        outlet_families.to_excel(writer, sheet_name="outlet_families", index=False)
        keyword_terms.to_excel(writer, sheet_name="keyword_terms", index=False)
        notes.to_excel(writer, sheet_name="notes", index=False)

        # Make the workbook pleasant to use in Excel: freeze the header row
        # and apply a conservative column width cap.
        for sheet in writer.book.worksheets:
            sheet.freeze_panes = "A2"
            for column_cells in sheet.columns:
                max_len = max(len(str(cell.value)) if cell.value is not None else 0 for cell in column_cells)
                sheet.column_dimensions[column_cells[0].column_letter].width = min(max(max_len + 2, 10), 70)

    print(out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
