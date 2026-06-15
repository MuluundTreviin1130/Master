# Figures

Final or currently reviewed PNG figures for the surrogate-modeling review.

## Structure

- `runners/`: reproducible Python builders.
- `csv/`: count tables and plotting data generated or consumed by builders.
- `source_data/`: Excel workbooks used for manual inspection or rebuilding.
- `old_figures/`: superseded drafts and archived PDF exports.
- `_natural_earth/`: cached map geometry.

Figure builders export PNG only by default. PDF should be produced explicitly
only when required for submission.

## Current evidence figures

- `fig_model_class_integration_bubble_evidence.png`: model class by integration
  pattern; bubble size is the number of high-confidence studies and color is
  the dominant surrogate target.
- `fig_doe_integration_bubble_evidence.png`: audited DoE strategy by integration
  pattern; bubble size is the study count and color is the dominant surrogate
  model class.
- `fig_taxonomy_alluvial_flow_evidence.png`: constant-cohort alluvial flow
  across model class, DoE/training strategy, integration pattern, and
  validation. Missing explicit evidence is retained as a grey node rather than
  inferred.
- `fig_bibliometric_keyword_wordcloud.png`: keyword-only word cloud for the
  bibliometrical analysis section; word size is curated paper-library
  keyword-field frequency and color indicates explicit keyword families.
- `fig_panel_d_application_targets_sorted.png`: standalone extraction of the
  four-panel draft's application-target panel, sorted by tagged paper count with
  the application legend outside the plotting area.

Builders and count tables:

- `runners/build_model_class_evidence_figures.py` ->
  `csv/fig_model_class_evidence_counts.csv`
- `runners/build_doe_integration_bubble_evidence.py` ->
  `csv/fig_doe_integration_bubble_evidence_counts.csv`
- `runners/build_taxonomy_flow_and_archetypes_draft.py` ->
  `csv/fig_taxonomy_flow_and_archetypes_draft_counts.csv`
- `runners/build_bibliometric_keyword_wordcloud.py` ->
  `csv/fig_bibliometric_keyword_wordcloud_terms.csv` and
  `csv/fig_bibliometric_keyword_wordcloud_unclassified_terms.csv`
- `runners/build_panel_d_application_targets_sorted.py` ->
  `csv/fig_four_panel_final_candidate_draft_counts.csv`
