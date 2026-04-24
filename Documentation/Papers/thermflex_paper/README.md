# Thermflex Paper

This folder is the curated manuscript workspace for the Vienna district-heating
thermflex paper.

Purpose:

- keep manuscript text, figure plans, appendix notes, and source-run mappings in
  one place
- separate paper-facing interpretation from raw run artifacts under
  `Optimization/run/results/`
- make the path from model result to paper figure/table explicit and auditable

Core principle:

- raw results remain in `Optimization/run/results/...`
- this folder contains the curated paper layer that references those results

Main manuscript files:

- `manuscript/00_title_abstract_keywords.md`
- `manuscript/01_introduction.md`
- `manuscript/02_methods.md`
- `manuscript/03_results.md`
- `manuscript/04_discussion.md`
- `manuscript/05_conclusion.md`
- `manuscript/06_limitations.md`
- `manuscript/07_appendix_overview.md`
- `manuscript/08_figure_table_plan.md`
- `manuscript/09_references.md`

Subfolders:

- `manuscript/`
  main paper text organized in standard scientific sections
- `results/`
  curated paper-facing result summaries and source-bundle mappings
- `figures/`
  final paper figures plus figure-specific notes
- `tables/`
  final paper tables plus table-specific notes
- `appendix/`
  appendix-specific material linked from the main manuscript
- `notes/`
  working notes that support the manuscript but are not themselves manuscript text
- `manifests/`
  mappings from figures/tables to source runs and source files

Recommended workflow:

1. raw runs under `Optimization/run/results/...`
2. curated interpretation under `results/`
3. manuscript text under `manuscript/`
4. figures and tables derived from the curated results layer
