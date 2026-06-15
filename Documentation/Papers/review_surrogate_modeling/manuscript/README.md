# Manuscript layer

This folder holds the current manuscript text for the surrogate modeling
review.

## Current source of truth

- `main.md` is the downloaded current manuscript text.
- `Current_manuscript.tex` is the generated full LaTeX manuscript from
  `main.md`.
- `01_introduction.tex` through `13_conclusion.tex` are generated section
  files from the same current text and should be used for section-specific
  editing.
- `convert_main_md_to_tex.py` regenerates `Current_manuscript.tex`, the
  section files, and `_tmp_main_md_citation_audit.csv`.
- Section 11 is currently regenerated from a conservative override inside
  `convert_main_md_to_tex.py`, because the imported `main.md` software-package
  block mixed PDF-backed package mentions with broader package-property
  claims. See `../_tmp_sec11_software_package_audit.md`.

The current Overleaf/RSER bibliography is
`../paper_library/review_paper_library.bib` with `elsarticle-num`. In
Overleaf the `.bib` normally sits next to the main `.tex`, so the generated
full manuscript uses:

```tex
\bibliographystyle{elsarticle-num}
\bibliography{review_paper_library}
```

## Current section files

- `01_introduction.tex`
- `02_methodology.tex`
- `03_bibliometrical_analysis.tex`
- `04_conceptual_foundations.tex`
- `05_taxonomy_surrogates.tex`
- `06_meta_review.tex`
- `07_training_data_doe.tex`
- `08_integration_patterns.tex`
- `09_validation_decision_aware.tex`
- `10_application_evidence_map.tex`
- `11_software_packages.tex`
- `12_open_challenges.tex`
- `13_conclusion.tex`

Older overlapping section files were moved to `archive_previous_sections/`.
They are kept for reference only. Do not edit archived files as the current
manuscript. `main.tex` and `main_overleaf_rser.tex` are previous build
templates until explicitly synced to `Current_manuscript.tex`.

## Citation checks

Run:

```powershell
py manuscript/convert_main_md_to_tex.py
py manuscript/audit_main_md_claim_evidence.py
```

`_tmp_main_md_citation_audit.csv` checks whether every cite key in `main.md`
exists in `paper_library/review_paper_library.bib`. The claim-context audit
files `_tmp_main_md_claim_context_audit.csv` and
`_tmp_main_md_claim_context_audit_summary.md` triage citation contexts by
BibTeX availability, local PDF availability, and title/abstract/keyword
overlap. These are triage flags, not automatic correctness judgments.
