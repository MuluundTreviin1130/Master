# Review: Surrogate Modeling in Energy System Modeling

This folder hosts the working assets for a literature review paper on
optimization-based surrogate models in energy system modeling.

## Research question

What are surrogate models, and how and for which purposes are they used in
energy system modeling, across deterministic dispatch, capacity expansion,
multi-objective and uncertainty-aware problems, in power, district heating
and multi-energy systems?

## Layer overview

- `manuscript/`
  Elsevier `elsarticle` LaTeX manuscript (one `.tex` file per section + `main.tex`).
- `references/`
  Single source of truth for the bibliography:
  - `raw/` keeps a snapshot of the original Scopus export for reproducibility
  - `surrogates_esm.bib` is the curated bib used by the manuscript (`\bibliography`)
  - `surrogates_esm_candidates.bib` is a holding area for entries that look
    like surrogate work but were not flagged explicitly by the search and
    still need a manual decision
  - `screening_log.md` documents the search strings, inclusion / exclusion
    criteria and the offline filter tiers
  - `filter_bib.py` is the offline filter script that turns the raw Scopus
    export into the curated bib + candidate bib + screening CSV
- `tables/`
  Markdown / LaTeX builders for the review tables (taxonomy, task-role
  matrix, training & DoE, validation, integration patterns, evidence map).
- `figures/`
  Conceptual figures (taxonomy overview, task-role matrix, evidence-map
  bubble plot).
- `appendix/`
  Long-form supporting material (extended evidence map, search dumps).

## Conventions

- Manuscript section files are LaTeX (`*.tex`), not Markdown, because the
  target template is Elsevier `elsarticle` with classical `bibtex` and
  `elsarticle-num`.
- The bibliography is managed as the single `references/surrogates_esm.bib`.
  Whether Zotero or the repo is the upstream source can be decided per
  workflow, but the manuscript only ever points at this file.
- Inclusion / exclusion criteria, search strings and the tiered offline
  filter are kept in `references/screening_log.md` so the literature
  selection is reproducible.
