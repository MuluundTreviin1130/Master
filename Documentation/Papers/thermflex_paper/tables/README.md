# Thermflex Paper Tables

This folder stores the active table-layer assets for the Thermflex paper.

Scope:
- main-paper tables
- compact table builders or table-ready markdown exports when needed

Working rule:
- keep this layer lean
- put long source explanations and extended stock/assumption dumps into the
  appendix, not into separate table-side notes here

Current target tables:
- `table_02_residential_cohort_building_summary.md`
- `table_03_representative_day_kpi_summary.md`
- `table_04_preheat_timing_solar_contribution.md`
- `table_05_residential_cohort_duration_sensitivity.md`
- `table_06_indoor_temperature_response_upper_only.md`
- `table_07_upper_only_duration_response_top_days.md`
- `table_08_lb21_vs_upper_residential_cohort_shift_top_days.md`
- `table_09_tradeoff_day_summary_upper_only_dur24.md`
- `table_10_mechanism_day_classes_upper_only_dur24.md`
- `table_11_solar_bin_summary_upper_only_dur24.md`
- `table_12_selected_day_residential_cohort_intensity_upper_only_dur24.md`

Builders:
- `build_table_09_heating_season_kpis.py`
- `build_mechanism_tables_from_latest_bundle.py`

Superseded tables live under `old/`.
