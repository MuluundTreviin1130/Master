# References layer

This folder is the single source of truth for the bibliography of the
surrogate modeling review.

## Files

- `raw/` — snapshots of original database exports (read-only, never edited
  by hand). Each file is named with the export date so multiple exports can
  coexist without overwriting each other.
- `surrogates_esm.bib` — curated bibliography that the manuscript points
  at via `\bibliography{...}`. Only contains entries that are confirmed
  surrogate-modeling-in-energy-systems work (Tier A from the offline
  filter, plus manually accepted Tier B entries).
- `surrogates_esm_candidates.bib` — entries that look implicit but plausible
  (Tier B from the offline filter). They are not yet part of the manuscript
  bibliography. Each entry must be confirmed or rejected during manual
  screening; once accepted it moves to `surrogates_esm.bib`.
- `surrogates_esm_screening.csv` — per-entry decision log produced by the
  offline filter (cite key, title, year, journal, tier, matched terms).
  Use this as the evidence map seed: it can be enriched with task-class,
  surrogate-family and integration-pattern columns once we read the entries.
- `moo_multicriteria_screening.csv` — per-entry decision log for the user's
  earlier Scopus / Zotero export that underlies the existing MOO-in-MES
  review draft.
- `moo_mes_focus.bib` / `moo_mes_focus.csv` — focused MOO+MES subset from
  the earlier export. This is the broad multi-objective / multicriteria
  MES literature base.
- `moo_mes_surrogate_focus.bib` / `moo_mes_surrogate_focus.csv` — smaller
  subset where a MOO+MES paper also contains an explicit or implicit
  surrogate signal.
- `review_mes_moo_surrogates.bib` — manuscript bibliography that combines
  `surrogates_esm.bib` with `moo_mes_focus.bib` and deduplicates by DOI
  first, citation key second.
- `review_mes_moo_surrogates_manifest.csv` — source manifest for the
  combined bibliography, recording whether each entry came from the
  surrogate search, the MOO/MES export, or both.
- `filter_bib.py` — offline filter that turns a raw Scopus export into the
  curated bib + candidate bib + screening CSV using the tiered criteria
  documented in `screening_log.md`.
- `import_moo_multicriteria_export.py` — importer/filter for the user's
  MOO / multicriteria Scopus export.
- `build_review_bibliography.py` — deterministic builder for the combined
  manuscript bibliography.
- `screening_log.md` — search strings, inclusion / exclusion criteria, the
  tiered offline filter and any manual decisions taken during screening.

## Workflow

1. Run a Scopus query (see `screening_log.md` for the active strings).
2. Export the result as BibTeX into `raw/scopus_export_YYYY-MM-DD.bib`.
3. Run `filter_bib.py` against that raw file to produce
   `surrogates_esm.bib`, `surrogates_esm_candidates.bib` and
   `surrogates_esm_screening.csv`.
4. Manually screen `surrogates_esm_candidates.bib`: move accepted entries
   into `surrogates_esm.bib` (or simply re-tag them in the screening CSV
   and re-run the script with a manual override, see the script header).
5. Import the user's earlier MOO / multicriteria export with
   `import_moo_multicriteria_export.py` to produce the MOO+MES focus layer.
6. Run `build_review_bibliography.py` to combine the surrogate and MOO+MES
   pools.
7. The manuscript points at `review_mes_moo_surrogates.bib`.
