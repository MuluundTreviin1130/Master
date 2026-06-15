# Screening Log

This file documents the literature search and the offline screening pipeline
for the surrogate modeling review. It is the human-readable counterpart of
`filter_bib.py` and the per-entry record in `surrogates_esm_screening.csv`.

The goal is to keep the literature selection reproducible: anyone with this
log and the raw Scopus export should be able to regenerate the curated
bibliography exactly.

## 0. Current narrowed review scope

The review has been narrowed from the broad question "surrogates in energy
system modeling" to the more focused question:

> How are surrogate models used to accelerate or support multi-objective
> optimization of multi-energy systems?

This narrowed scope keeps the previous surrogate-in-ESM search as the
methodological backbone, but adds the user's earlier MOO / multicriteria
Scopus export as the application backbone for multi-energy systems (MES),
microgrids, energy communities, hybrid renewable energy systems (HRES),
district heating/cooling, CCHP and sector-coupled systems.

## 1. Database, scope, and time window

- Database: Scopus (advanced search).
- Time window: 2016 to 2026 inclusive (set via the Scopus year filter, not
  via `PUBYEAR` in the query string).
- Document types: Article, Review, Conference Paper.
- Language: English.
- Subject areas: Energy, Engineering, Computer Science, Environmental
  Science, Mathematics.

## 2. Active Scopus search strings

The search field is set to "Article title, Abstract, Keywords" in the UI;
the query body itself does not need a `TITLE-ABS-KEY()` wrapper.

### 2.1 Main search

```
( "surrogate model" OR "surrogate models" OR "surrogate modeling" OR "surrogate modelling" OR "surrogate assisted" OR metamodel* OR metamodeling OR metamodelling OR emulator OR emulators OR emulation OR "response surface" OR kriging OR "gaussian process" OR "polynomial chaos" OR "radial basis function" OR "support vector regression" OR "random forest" OR "gradient boosting" OR "neural network proxy" OR "machine learning surrogate" OR "data driven surrogate" OR "neural surrogate" OR "learning to optimize" OR "optimization proxy" OR "optimization proxies" )
AND
( "energy system" OR "power system" OR "electricity system" OR "electric power system" OR "district heating" OR "district energy" OR "multi energy" OR "multi energy system" OR "integrated energy system" OR "sector coupling" OR "sector coupled" OR "unit commitment" OR "economic dispatch" OR "optimal power flow" OR "capacity expansion" OR "generation expansion" OR "energy planning" OR "energy dispatch" OR "energy scheduling" OR microgrid* OR "smart grid" OR "renewable energy system" OR "power grid" )
AND
( optimization OR optimisation OR dispatch OR scheduling OR planning OR "stochastic programming" OR "robust optimization" OR "chance constraint" OR "multi objective" OR pareto OR milp OR "mixed integer" OR bilevel OR "scenario reduction" )
AND NOT
( "computational fluid dynamics" OR "reduced order model" OR "proper orthogonal decomposition" OR "structural optimization" OR aeroelastic OR aerospace OR pharmaceutic* OR pharmacokinetic* OR molecular OR genomics OR genome OR "drug discovery" )
```

### 2.3 Earlier MOO / multicriteria export

The user's existing review draft was based on an earlier mass export from
Scopus / Zotero stored as:

```
raw/moo_multicriteria_scopus_export_2026-05-06.bib
```

This export contains 2369 BibTeX entries and is treated as a separate raw
SSOT artifact. It is screened with `import_moo_multicriteria_export.py`.
The script tags each entry as:

- `moo_mes_surrogate` — MOO + MES context + explicit/implicit surrogate signal
- `moo_mes` — MOO + MES context without surrogate signal
- `moo_only` — MOO context without MES signal
- `mes_only` — MES context without MOO signal
- `out` — neither focus dimension matched

The 2026-05-06 run produced:

- 2369 parsed entries
- 2290 entries with DOI
- 1651 `moo_mes` entries
- 23 `moo_mes_surrogate` entries
- 680 `moo_only` entries
- 9 `mes_only` entries
- 6 `out` entries

The broad MOO+MES focus pool therefore contains 1674 entries before
deduplication (`moo_mes` + `moo_mes_surrogate`).

Notes on Scopus syntax:
- Wildcards are not allowed inside double quotes. We rely on Scopus loose
  matching to catch plurals (e.g. `"power system"` also matches `power systems`).
- Wildcards on bare tokens (`metamodel*`, `microgrid*`) require at least
  three characters before the asterisk.
- The year filter is set via the Scopus UI, not via `PUBYEAR > ...` in the
  query, because the user prefers to set it as a sidebar filter.

### 2.2 Helper searches

Two narrow helper queries are used to make sure the more nuanced sub-fields
are not lost in the noise of the main search. Their results should be
exported separately and merged in Zotero (de-duplication via DOI).

Surrogate x stochastic / robust:

```
( surrogate OR metamodel* OR emulator OR "neural network" OR "gaussian process" )
AND
( "stochastic programming" OR "robust optimization" OR "chance constraint" OR "scenario reduction" OR "scenario tree" )
AND
( "energy system" OR "power system" OR "unit commitment" OR "capacity expansion" OR "district heating" OR "multi energy" )
```

Surrogate x multi-objective:

```
( "surrogate assisted" OR surrogate OR metamodel* OR emulator OR "gaussian process" )
AND
( "multi objective" OR "many objective" OR pareto )
AND
( "energy system" OR "power system" OR "district heating" OR microgrid* OR "multi energy" OR renewable )
```

## 3. Why offline screening is needed

The Scopus export of the main search (2026-05-05) returned 3129 entries.
Spot-checking the first ~10 titles shows that a large share is generic ML
applied to energy data (load forecasting, fault diagnosis, site selection,
SCADA-driven prediction, etc.) rather than surrogate modeling for
optimization.

Forcing the term `surrogate` (or `metamodel`) in the query would remove
that noise but also removes legitimate surrogate work that is described
with neutral language such as "neural network proxy", "data-driven model
to replace expensive simulation" or "approximation of the unit commitment
operating cost". To handle this honestly we screen offline with a
tiered keyword logic instead.

## 4. Offline filter tiers (implemented in `filter_bib.py`)

For each entry, the filter builds a single text bag from `title +
abstract + author_keywords + keywords` (lower-cased, ASCII-folded).
Decisions are then taken on this bag.

## 4a. Combined manuscript bibliography

The manuscript bibliography is generated by `build_review_bibliography.py`.
It combines:

- `surrogates_esm.bib` — 1270 Tier-A surrogate-in-ESM entries from the
  broad surrogate search
- `moo_mes_focus.bib` — 1674 entries from the earlier MOO / multicriteria
  export that match the MOO+MES focus layer

The 2026-05-06 build produced:

- 2944 input entries
- 2906 deduplicated entries in `review_mes_moo_surrogates.bib`
- 38 duplicate identities collapsed
- 1235 entries only from `surrogates_esm.bib`
- 1662 entries only from `moo_mes_focus.bib`
- 9 entries appearing in both source pools

Deduplication is DOI-first and citation-key-second. The source of every kept
entry is recorded in `review_mes_moo_surrogates_manifest.csv`.

### Tier A — explicit surrogate work

The entry contains at least one of the explicit surrogate-method terms
(SURR_TERMS), AND at least one energy-system context term (ESM_TERMS):

- SURR_TERMS:
  `surrogate`, `metamodel`, `meta-model`, `meta model`,
  `emulator`, `emulation`,
  `response surface`, `response surface methodology`,
  `kriging`, `co-kriging`,
  `gaussian process`, `gp regression`,
  `polynomial chaos`,
  `radial basis function`, `rbf network`, `rbf surrogate`,
  `learning to optimize`, `learning-to-optimize`,
  `optimization proxy`, `neural proxy`, `proxy model`,
  `surrogate-assisted`, `surrogate assisted`.

- ESM_TERMS:
  `energy system`, `power system`, `electricity system`,
  `district heating`, `multi-energy`, `multi energy`,
  `integrated energy`, `sector coupling`,
  `unit commitment`, `economic dispatch`, `optimal power flow`,
  `capacity expansion`, `generation expansion`,
  `microgrid`, `smart grid`, `renewable energy`,
  `power grid`, `energy planning`, `energy dispatch`,
  `combined heat and power`, ` chp ` (with surrounding spaces),
  `heat pump`, `thermal storage`, `district energy`,
  `energy hub`, `virtual power plant`.

Tier A entries are written to `surrogates_esm.bib`.

### Tier B — implicit surrogate work

The entry does NOT match Tier A but does match all of:

1. ML / regression method term (ML_TERMS):
   `neural network`, `deep learning`, `machine learning`,
   `random forest`, `gradient boosting`, `xgboost`,
   `support vector`, `regression tree`, `regression model`,
   `data-driven model`, `learned model`, `learning-based`,
   `convolutional neural`, `recurrent neural`, `lstm`,
   `transformer model`, `graph neural`, `physics-informed neural`,
   `polynomial regression`, `decision tree regressor`.
2. Optimization context term (OPT_TERMS):
   `optimization`, `optimisation`, `dispatch`, `unit commitment`,
   `economic dispatch`, `optimal power flow`, `capacity expansion`,
   `generation expansion`, `energy planning`, `scheduling`,
   `milp`, `mixed-integer`, `mixed integer`,
   `multi-objective`, `multi objective`, `pareto`,
   `bilevel`, `stochastic programming`, `robust optimization`,
   `chance constraint`, `scenario reduction`, `model predictive`.
3. Energy-system context term (ESM_TERMS, see above).
4. At least one "surrogate-indicator" term (PROXY_HINTS) that signals the
   ML model is used as a proxy for an expensive component:
   `proxy`, `approximate`, `approximation`,
   `computationally expensive`, `computational cost`,
   `computation time`, `reduce computation`, `speed up`, `speedup`,
   `accelerate`, `acceleration`,
   `replace`, `replacing the`, `instead of`, `in lieu of`,
   `surrogate`, `emulate`, `emulating`,
   `fast evaluation`, `expensive simulation`, `expensive model`,
   `cheap evaluation`, `expensive function`,
   `train on`, `trained on simulator`, `trained on the optimizer`.

Tier B entries are written to `surrogates_esm_candidates.bib` and must be
manually screened. Once an entry is accepted, it is moved into
`surrogates_esm.bib` (or marked accepted in `surrogates_esm_screening.csv`
and re-emitted by re-running the script).

### Hard exclusions (NOISE_TERMS)

Even if the rules above match, an entry is dropped if its primary topic is
clearly not surrogate-for-optimization. The filter checks NOISE_TERMS and
records them in the screening CSV, but the final accept / reject decision
weights matched signals over a single noise word; the exact rule is:

- If the entry matches Tier A explicitly, NOISE_TERMS only flag it
  (still kept).
- If the entry only matches Tier B, then a strong noise signal (two or more
  of `fault diagnosis`, `fault detection`, `weather forecasting`,
  `wind speed forecasting`, `load forecasting only`, `image recognition`,
  `site selection`, `wildfire`) demotes it to "rejected".

NOISE_TERMS:
`fault diagnosis`, `fault detection`, `fault classification`,
`transformer fault`,
`wind speed forecasting`, `load forecasting`, `price forecasting`,
`site selection`, `siting`,
`image recognition`, `computer vision`,
`drug discovery`, `molecular dynamics`,
`speech recognition`, `text classification`.

## 5. Output artefacts

The filter run on `raw/scopus_export_2026-05-05.bib` produces:

- `surrogates_esm.bib` — Tier A entries (high confidence).
- `surrogates_esm_candidates.bib` — Tier B entries (manual review needed).
- `surrogates_esm_screening.csv` — per-entry decision log with columns
  `cite_key, year, type, title, journal, doi, tier, decision,
  matched_surrogate_terms, matched_ml_terms, matched_opt_terms,
  matched_esm_terms, matched_proxy_hints, matched_noise_terms`.

The CSV is the seed for the manuscript's evidence map (Table T6).
