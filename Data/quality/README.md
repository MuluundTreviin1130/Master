# Data Quality

This sublayer collects data-quality diagnostics that belong closer to the
`Data/` package than to a generic top-level analysis bucket.

Current contents:

- `plot_pedigree_heatmap.py`
  builds pedigree/data-quality visualizations from the active LCA/data inputs
- `outputs/`
  generated example outputs kept as explicit diagnostics

Intent:

- keep data-quality checks near the data layer they diagnose
- avoid a vague top-level `Analysis/` bucket for one narrow purpose
