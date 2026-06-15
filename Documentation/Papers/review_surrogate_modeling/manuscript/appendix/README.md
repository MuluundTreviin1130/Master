# Appendix snippets

- `table_T6_evidence_map.tex` — MES-focused evidence map (`Table~\ref{tab:T6-evidence-map}`) as one `longtable`. Included from `08_application_evidence_map.tex` and mirrored under `tables/table_T6_evidence_map.tex`.
- Regenerate rows: `py tables/build_table_T6_evidence_map.py` (from repo root) or `cd tables` then `py build_table_T6_evidence_map.py`. The script updates this file and mirrors the same TeX into `tables/table_T6_evidence_map.tex` for legacy tooling (e.g. `inline_tables_into_sections.py`).
