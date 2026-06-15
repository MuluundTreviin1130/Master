# `paper_library/fulltexts/`

Working copy of the review PDFs the user downloaded into
`C:\Users\Philipp Thunshirn\Desktop\PhD\Papers\Journals\Review\Literatur\Reviews`,
renamed to ASCII-only filenames so they can be opened by tooling that
trips on the original Scopus filenames. Each file is named after the
cite-key the corresponding entry now carries in `references/external_reviews.bib`
(or in the deduplicated bibliography `references/review_mes_moo_surrogates.bib`
for entries that come from the Scopus bulk export).

These PDFs are kept here only so that future agents and the human
author can re-read the abstracts and methodology sections without
chasing the original filenames again. They are not versioned (see
`.gitignore`).

## Mapping (cite-key -> source filename)

| Cite-key | Source PDF |
| --- | --- |
| `Bhosekar2018` | `1-s2.0-S0098135417303228-main.pdf` |
| `Westermann2019` | `1-s2.0-S0378778819302877-main.pdf` |
| `Manco2024` | `1-s2.0-S1359431123019002-main.pdf` |
| `Fattahi2020` | `1-s2.0-S1364032120304858-main.pdf` |
| `Klemm2021` | `1-s2.0-S1364032120304950-main.pdf` |
| `Li2025_hydrogen` | `1-s2.0-S2949720525000529-main.pdf` |
| `Khan2024_DT` | `A. Khan - Digital Twin and Artificial Intelligence ... .pdf` |
| `DiazManriquez2016` | `Computational Intelligence and Neuroscience - 2016 - ... .pdf` |
| `FernandezGodino2023` | `M. G. Fernandez-Godino - Review of multi-fidelity models [2016].pdf` |
| `Sahoo2025` | `A13_25_Sahoo+et+al.pdf` |
| `Etghani2025` | `TSP_EE_70668.pdf` |
| `Mohammadi2024` | `sustainability-16-09851.pdf` |
| `ChenRenZhou2023` | `1-s2.0-S2096511723000853-main.pdf` |
| `Elwy2024` | `main3.pdf` |
| `Zhang2026_building` | `1-s2.0-S0378778826002987-main.pdf` |

The remaining PDFs in the source folder (Tan2026, Khaloie2025,
Lim2025, Ruan2021221, Elsheikh2019622, Zhou2024__2,
vahidinasab_overview_2020, Conti2026, agha_kassab_comprehensive_2024,
Mylonopoulos202332697, malla_sg_optimization_2024,
nallolla_multi-objective_2023, salgueiro_multi-objective_2019,
arar_tahir_scientific_2023, batista_optimizing_2023,
velasquez_intelligence_2023) were already part of the Scopus bulk
export (`references/review_mes_moo_surrogates.bib`) and are therefore
referenced under their existing cite-keys.

## Merged bundle ``Reviews zusammen.pdf``

The user also keeps a **single merged PDF** (959 pages, created with
PDF24) under
``C:\Users\Philipp Thunshirn\Desktop\PhD\Papers\Journals\Review\Literatur\Reviews\Reviews zusammen.pdf``.
Because reference lists inside each article add hundreds of unrelated
DOIs, **do not** map that file by naïve full-text DOI extraction.

Instead run (from ``paper_library/``)::

    py map_reviews_zusammen_pdf_by_toc.py

This script uses the PDF outline (level-1 titles), searches for each
title in the page text to recover the true start page after merging,
reads the first few pages for the **article** DOI, and matches against
``review_paper_library.bib``.  It writes:

- ``reviews_zusammen_pdf_toc_map.md`` / ``.json`` — one row per unique
  matched DOI → cite_key

A naive DOI dump (every string ``10.xxxx/`` in the whole file) is kept
only for diagnostics as ``reviews_zusammen_pdf_doi_map.*`` from
``map_reviews_zusammen_pdf.py`` — **not** suitable as a paper list.

**Manual follow-ups** after each PDF24 merge: titles that are TOC
sections (not full paper titles), BOM-prefixed titles, or first-page
DOIs that belong to a *different* article must be checked against the
``.md`` report.
