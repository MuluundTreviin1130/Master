# Tables layer

Active review tables for the surrogate modeling paper.

## Active tables

- `table_T1_taxonomy.tex` — surrogate model families (output type,
  optimizer compatibility, typical failure modes, suitable energy-system
  task classes)
- `table_T2_task_role_matrix.tex` — energy-system task class x surrogate
  role (replace, accelerate, screening, MOO, uncertainty)
- `table_T3_training_doe.tex` — sampling and design strategies
  (Latin hypercube, Sobol, adaptive, active learning, multi-fidelity,
  transfer)
- `table_T4_validation.tex` — validation and reporting standards (point /
  interval metrics, decision-aware metrics, stress tests, OOD checks)
- `table_T5_integration_patterns.tex` — surrogate ↔ optimizer integration
  patterns (MIP-friendly linearization, convex surrogates, warm start,
  decomposition, scenario screening)
- `table_T6_evidence_map.tex` — long evidence map; **canonical TeX** under
  `../manuscript/appendix/table_T6_evidence_map.tex`. Auto-generated from
  `paper_library/review_paper_library_manifest.csv` via
  `build_table_T6_evidence_map.py` (the script also writes a synced copy
  here for `inline_tables_into_sections.py`).
- `table_T7_related_reviews.tex` — meta-review of 32 related reviews
  along four scope axes (method, application, MOO, MES) plus
  decision-aware-validation auxiliary axis
- `table_T8_software_packages.tex` — software-package landscape;
  auto-generated from `build_table_T8_software_packages.py`, which
  consumes the PDF-verified mention map produced by
  `paper_library/verify_T8_software_cites.py`
- `citations_sec_training_doe_key_doi_title_venue.md` — human-readable
  overview table (Key, DOI, title, venue) for all `\cite{…}` keys in
  `manuscript/05_training_data_doe.tex`; regenerate with
  `build_citations_sec_training_doe_md.py`
- `citations_sec_integration_patterns_key_doi_title_venue.md` — same for
  `manuscript/06_integration_patterns.tex`; regenerate with
  `build_citations_sec_integration_patterns_md.py`

## Builders

- `build_table_T6_evidence_map.py` — regenerates T6 from the curated
  library manifest
- `build_table_T8_software_packages.py` — regenerates T8 from the
  static package definition list inside the script combined with
  the verified review-mention map
- `build_citations_sec_training_doe_md.py` — writes
  `citations_sec_training_doe_key_doi_title_venue.md` from the section
  text and main bibliography file
- `build_citations_sec_integration_patterns_md.py` — writes
  `citations_sec_integration_patterns_key_doi_title_venue.md`
- `inline_tables_into_sections.py` — **always run after any table
  edit** (see Hard rule below)

## Hard rule: never `\input{../tables/...}` in section files

The Overleaf single-file template (`manuscript/main_overleaf_rser.tex`)
breaks when a pasted section body references `\input{../tables/<name>}`
because the sibling `tables/` folder is not visible from the pasted
section. Therefore every section file under `manuscript/` must contain
the table body **inline**, not via `\input`.

This folder is the single source of truth: edit
`tables/table_T*.tex`, then run

    py tables/inline_tables_into_sections.py

to push the current table body into the matching
`% BEGIN inlined table <name>` / `% END inlined table <name>` region
of every section file under `manuscript/`. The inliner is idempotent
(safe to re-run) and also converts any leftover
`\input{../tables/<name>}` references on first sight.
