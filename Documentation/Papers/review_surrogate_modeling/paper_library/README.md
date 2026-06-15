# Paper library

Curated, story-aligned subset of `references/review_mes_moo_surrogates.bib`
that is meant to be copied into Overleaf as the manuscript bibliography.

## Why this layer exists

The combined bibliography (`review_mes_moo_surrogates.bib`, ~2900 entries)
is the *full* literature pool that supports the screening pipeline and
the appendix evidence map. The Overleaf manuscript should not carry that
much weight: most journal templates and bibliography styles slow down or
break with thousands of unused entries.

`paper_library/` therefore contains a deterministic, reproducible cut
that is sized to the actual manuscript:

- every cite key already used in `manuscript/*.tex` is included
  (mandatory keys, currently 103),
- the rest is filled up with the highest-impact papers per *story
  bucket* (Sections 1-9 of the draft),
- the final size is around 240-260 entries, which is dense enough for
  a top-tier review without being unwieldy in Overleaf.

## Files

| File | Purpose |
| ---- | ------- |
| `select_paper_library.py` | Selection script (single source of truth) |
| `review_paper_library.bib` | Overleaf-ready BibTeX subset |
| `review_paper_library_manifest.csv` | Per-paper provenance (bucket, mandatory flag, citation count, ...) |
| `review_paper_library_buckets.csv` | Long-format `bucket -> cite_key` listing |
| `review_paper_library_citation_plan.md` | Markdown plan: which key fits which manuscript section |
| `verify_T8_software_cites.py` | Scan review PDF texts for mentions of optimisation / ML tooling (T8) |
| `match_literatur_pdfs_to_bib.py` | Map local ``Literatur/<section>/*.pdf`` downloads to bib keys → `_tmp_pdf_author_title_match_*` artifacts |
| `build_surrogate_target_audit.py` | Fail-closed target classification from bibliography text and available PDFs |
| `build_doe_evidence_audit.py` | Fail-closed DoE-strategy and training-data-source audit for quantitative figures |
| `build_alluvial_evidence_audit.py` | Full-library evidence audit for model class, DoE, integration pattern, and validation |
| `build_unified_evidence_audit.py` | Shared cached audit for model class, target, trust, DoE/data source, integration, and multi-label validation |
| `README.md` | This file |

## Unified figure audit

The unified runner is the common evidence source for the alluvial, model-class,
DoE, and validation figures. It extracts each matched PDF once and stores
page-level text in `paper_library/cache/unified_pdf_text/`.

Smoke test:

```powershell
cd Documentation/Papers/review_surrogate_modeling
..\..\..\.venv\Scripts\python.exe paper_library/build_unified_evidence_audit.py --smoke 16 --max-pages 20
```

Full overnight run:

```powershell
cd Documentation/Papers/review_surrogate_modeling
..\..\..\.venv\Scripts\python.exe paper_library/build_unified_evidence_audit.py --max-pages 35 --workers 4
```

The smoke and full modes use the same classifiers and schema. Smoke outputs
carry the `_smoke` suffix. The long-format label CSV is the auditable source;
the study CSV is a derived wide view for plotting and coverage checks.

The `.bib` file is auto-generated. **Do not edit it by hand.** Adjust the
selection logic in `select_paper_library.py` and rebuild.

## How the selection works

1. **Mandatory keys**
   `select_paper_library.py` walks every `\cite{...}` in
   `manuscript/*.tex`, deduplicates, and forces those keys into the
   library. If any mandatory key is missing from the source pool the
   script fails fast (no silent drops).

2. **Story buckets**
   Each bucket mirrors one part of the manuscript (cornerstone reviews,
   surrogate families, integration patterns, applications, MOO
   algorithms, validation, ...). A bucket is defined by:

   - a *predicate* on the merged pool row
     (title text + the `matched_*` tags from the screening CSVs), and
   - a *target quota* (how many entries that section should carry).

   Mandatory keys count towards the bucket quota; top-up is filled from
   the highest-cited remaining papers that satisfy the predicate.

3. **Global top-up**
   If the bucket-driven library is still below the global target
   (240 entries), the script fills the gap with the highest-cited
   MOO+MES+Surrogate-tagged papers from the pool that have not been
   selected yet. They are tagged `B99_misc` in the manifest.

4. **Hard cap**
   The library is capped at 260 entries. Mandatory keys are never
   dropped; only trailing top-up is.

The whole process is deterministic: same inputs -> same library.

## Literatur-folder PDF ↔ Bib key matching

Bulk-downloaded PDFs often carry publisher-coded filenames instead of BibTeX
keys. Before you align manuscript claims with underlying PDF passages, reconcile
downloads against the bibliography snapshots:

```powershell
cd <repo>/Documentation/Papers/review_surrogate_modeling
py -3 paper_library/match_literatur_pdfs_to_bib.py
```

The matcher **merges** (by default) ``references/review_mes_moo_surrogates.bib``
*and* ``review_paper_library.bib``, scans PDF text for bare DOIs plus
``doi:/https://doi.org`` forms, tries **article-first** DOIs (text before a
``References`` block, else the first ~12k characters) before using the full
snippet, consumes up to ``--extract-pages`` front matter
(per default ``28``) for textual anchors, and **only emits an accepted pairing**
when a DOI overlaps the bib record *or* a long bib-title token window plus
matching surnames is found in the extraction (see the module docstring for the
literal thresholds). Rows that fail either proof land in ``unmatched`` rather
than being guessed silently.

Companion artefacts:

| File | Meaning |
| ---- | ------- |
| ``_tmp_pdf_author_title_match_map.csv`` | per-PDF adjudication incl. provisional vs final rows |
| ``_tmp_pdf_author_title_match_report.json`` | aggregates + cite keys lacking bib rows / lacking PDF |
| ``_tmp_manuscript_cite_pdf_coverage.csv`` | manuscript + ``tables/*.tex`` cite universe ↔ verified PDF |

Flags of note: repeatable ``--bib path1 path2``, ``--tables-dir``, ``--extract-pages``.

Erweiterte Optionen (Defaults: mehr Treffer bei unveränderter DOI-/Titel-Verifikation):

| Flag | Rolle |
| ---- | ----- |
| ``--extract-hard-cap`` | Seitenobergrenze beim Tiefen-Scan (Default 260) |
| ``--deep-extract-unmatched`` / ``--no-deep-extract-unmatched`` | Zweiter Textdurchlauf über die gecappte Voll-PDF-Länge, wenn kein verifiziertes Match erreicht wird (Default an) |
| ``--deep-extract-ambiguous`` | dasselbe bei DOI/Fuzzy-Kollisionen (teuer, selten hilfreich, Default aus) |
| ``--reverse-bib-doi-reconcile`` / ``--no-reverse-bib-doi-reconcile`` | Nach dem PDF-Durchlauf: cite keys ohne PDF versuchen, an das eindeutige lokale PDF anzudocken, wenn die Bib einen DOI trägt, der im (Tief-)Text vorkommt und erneut per DOI verifiziert wird (Default an) |

Zusätzlich werden Fingerprints auch aus Bib-Feldern ``url``, ``howpublished`` und einer ``eprint``-Zeile mit ``10.`` gewonnen.

## Bucket map

The buckets are intentionally aligned with the existing draft so the
citation plan can be used directly when filling in the next sections.
See `select_paper_library.py` (`BUCKETS` list) for the authoritative
predicates and `review_paper_library_citation_plan.md` for the current
keys per bucket.

| Bucket | Manuscript section | Topic |
| ------ | ------------------ | ----- |
| B01_cornerstone_reviews    | Sec. 1, 2, 8 | Reviews / surveys / comparative meta-studies |
| B02_gp_kriging             | Sec. 3.2     | Gaussian process / kriging emulators |
| B03_pce_response_surface   | Sec. 3.1     | Polynomial chaos / response surfaces |
| B04_rbf_kernel             | Sec. 3.3     | Radial basis functions / kernel regressors |
| B05_tree_ensembles         | Sec. 3.4     | Random forests, gradient boosting |
| B06_neural_surrogates      | Sec. 3.5     | MLP / CNN / RNN / GNN |
| B07_constraint_aware       | Sec. 3.6     | Constraint-aware / structure-preserving |
| B08_hybrid_pinn            | Sec. 3.7     | Hybrid and physics-informed |
| B09_decision_focused_l2o   | Sec. 3.8     | Decision-focused, learn-to-optimize |
| B10_doe_active_learning    | Sec. 4.2-4.3 | LHS / Sobol / active learning / DoE |
| B11_multi_fidelity         | Sec. 4.4     | Multi-fidelity / transfer learning |
| B12_bayes_accel            | Sec. 5.2     | Bayesian / surrogate-assisted optimization |
| B13_warm_start             | Sec. 5.3     | Warm-start and primal-dual proxies |
| B14_decomposition          | Sec. 5.4     | Surrogate-enabled decomposition |
| B15_uncertainty            | Sec. 5.5     | Uncertainty handling with surrogates |
| B16_validation             | Sec. 6       | Decision-aware validation |
| B17_ed_uc                  | Sec. 7.1     | Economic dispatch / unit commitment |
| B18_opf                    | Sec. 7.2     | Optimal power flow surrogates |
| B19_capacity_expansion     | Sec. 7.3     | Capacity / generation expansion |
| B20_district_heating       | Sec. 7.4     | District heating / thermal storage |
| B21_mes_sector_coupling    | Sec. 7.5     | Multi-energy / sector coupling |
| B22_microgrid_hub          | Sec. 7.6     | Microgrids / hubs / communities |
| B23_moo_design             | Sec. 7.7     | Multi-objective MES design |
| B24_stochastic_robust      | Sec. 7.8     | Stochastic / robust planning |
| B25_moo_algorithms_nsga    | Sec. 5, 7.7  | NSGA-II/III, MOEA/D, RVEA |
| B26_moo_metaheuristics     | Sec. 5, 7.7  | Other MOO metaheuristics (PSO, DE, GWO, ...) |
| B27_mcdm                   | Sec. 7.7, 8  | MCDM (TOPSIS, AHP, VIKOR, ...) |
| B99_misc                   | -            | Story-relevant top-cited fallback |

A small bucket (e.g. B13 warm-start) does not indicate a script bug; it
reflects the actual scarcity of that combination in the screened pool.
That gap is itself a finding for the open-challenges section.

## Rebuilding the library

```powershell
cd Documentation/Papers/review_surrogate_modeling/paper_library
py select_paper_library.py
```

The script reads only `manuscript/`, `references/` and writes only into
`paper_library/`. It never edits the source pool.

## Overleaf workflow

1. Upload `paper_library/review_paper_library.bib` to the Overleaf
   project (rename to `references.bib` or keep the long name; just keep
   `\bibliography{...}` in `main.tex` consistent).
2. Use `review_paper_library_citation_plan.md` while writing each
   section: the cite keys for that section are listed under the matching
   bucket, sorted by citation impact, with mandatory cites pre-flagged.
3. When you add a new `\cite{...}` to `manuscript/*.tex`, rerun the
   selection script: the new key becomes mandatory automatically, so
   the library stays consistent with the manuscript.
