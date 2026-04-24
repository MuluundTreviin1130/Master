# Vienna Building Model Parameters Appendix

Generated at UTC: `2026-04-16T15:34:37+00:00`

## Scope

- Appendix scope: Vienna cohort-based building model parameters for the current paper path.
- Active runtime variant: thermal_archetypes.variant = calibrated_v1.
- The appendix separates literature-backed fields, pragmatic V1 assumptions, and legacy compatibility fields.
- Case-specific paper JSON overrides can change the global control and thermflex settings; the archetype and calibrated sidecar tables here are the repo SSOT at generation time.

## Notes

- The calibrated_v1 layer keeps the base envelope and geometry fields intact and adds calibration_v1 as a sidecar payload.
- Runtime thermal dynamics use the calibrated reduced-order fields (effective loss coefficient, effective heat capacity, and tau) when calibrated_v1 is active.
- Event-response bounds use the calibrated preheat/cutback/recovery metrics when the corresponding thermflex constraint switches are enabled.
- Non-residential hot water is intentionally zero in the current Vienna V1 building-stock path.
- Residential archetypes represent apartment-block-like multi-family reference buildings; non-residential archetypes are pragmatic service/office-like V1 proxies.
- The base residential U-values are TABULA-informed cohort seed values, not direct one-to-one TABULA WebTool extractions.

## Table A. Cohort scaling and stock anchors

These values define the Vienna cohort members that enter the paper runs. They control cohort scale, annual heat anchors, hot-water inclusion, and the mapping from each cohort to a thermal archetype.

| Cohort | Sector | Period | GFA [m2] | Volume [m3] | Annual space heat [kWh/a] | Annual hot water [kWh/a] | HW? | DH share override | Load mix | Sources |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| residential_pre1975 | residential | pre1975 | 48,559,035 | 145,677,642 | 5,584,485,867 | 752,665,042 | yes | n/a | H0=1.00 | BS-1, BS-2, BS-R1 |
| residential_1975_1990 | residential | 1975_1990 | 21,581,793 | 64,745,619 | 2,481,993,719 | 334,517,797 | yes | n/a | H0=1.00 | BS-1, BS-2, BS-R1 |
| residential_1990_2000 | residential | 1990_2000 | 3,596,966 | 10,790,936 | 413,665,620 | 55,752,966 | yes | n/a | H0=1.00 | BS-1, BS-2, BS-R1 |
| residential_2000_2014 | residential | 2000_2014 | 15,287,104 | 45,861,480 | 1,758,078,884 | 236,950,106 | yes | n/a | H0=1.00 | BS-1, BS-2, BS-R1 |
| non_residential_pre1975 | non_residential | pre1975 | 24,835,441 | 74,505,691 | 3,227,863,636 | 0 | no | n/a | G0=0.25; G1=0.25; G2=0.25; G3=0.25 | BS-1, BS-2, BS-R1 |
| non_residential_1975_1990 | non_residential | 1975_1990 | 11,037,974 | 33,113,640 | 1,434,606,061 | 0 | no | n/a | G0=0.25; G1=0.25; G2=0.25; G3=0.25 | BS-1, BS-2, BS-R1 |
| non_residential_1990_2000 | non_residential | 1990_2000 | 1,839,662 | 5,518,940 | 239,101,010 | 0 | no | n/a | G0=0.25; G1=0.25; G2=0.25; G3=0.25 | BS-1, BS-2, BS-R1 |
| non_residential_2000_2014 | non_residential | 2000_2014 | 7,818,565 | 23,455,495 | 1,016,179,293 | 0 | no | n/a | G0=0.25; G1=0.25; G2=0.25; G3=0.25 | BS-1, BS-2, BS-R1 |

## Table B. Base envelope and geometry archetype parameters

These are the base Vienna archetype parameters before the calibrated_v1 sidecar is applied. The fields remain part of the active runtime path. The residential period ladder is TABULA-informed, but the values are simplified cohort seed values rather than direct one-to-one TABULA WebTool extractions.

| Archetype | U_wall | U_window | U_roof | U_floor | Wall/GFA | Window/GFA | Roof/GFA | Floor/GFA | Cond. floor share | Sources |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| residential_pre1975 | 1.40 | 2.30 | 1.70 | 1.20 | 0.82 | 0.18 | 0.37 | 0.36 | 1.00 | AR-1, AR-2, AR-5, AR-7 |
| residential_1975_1990 | 1.10 | 2.70 | 0.80 | 0.80 | 0.82 | 0.18 | 0.37 | 0.36 | 1.00 | AR-1, AR-2, AR-5, AR-7 |
| residential_1990_2000 | 0.60 | 2.50 | 0.50 | 0.50 | 0.82 | 0.18 | 0.37 | 0.36 | 1.00 | AR-1, AR-2, AR-5, AR-7 |
| residential_2000_2014 | 0.35 | 1.40 | 0.20 | 0.40 | 0.82 | 0.18 | 0.37 | 0.36 | 1.00 | AR-1, AR-2, AR-5, AR-7 |
| non_residential_pre1975 | 1.40 | 2.30 | 1.70 | 1.20 | 0.30 | 0.12 | 0.30 | 0.30 | 1.00 | AR-1, AR-2, AR-5, AR-7 |
| non_residential_1975_1990 | 1.10 | 2.70 | 0.80 | 0.80 | 0.30 | 0.12 | 0.30 | 0.30 | 1.00 | AR-1, AR-2, AR-5, AR-7 |
| non_residential_1990_2000 | 0.60 | 2.50 | 0.50 | 0.50 | 0.30 | 0.12 | 0.30 | 0.30 | 1.00 | AR-1, AR-2, AR-5, AR-7 |
| non_residential_2000_2014 | 0.35 | 1.40 | 0.20 | 0.40 | 0.30 | 0.12 | 0.30 | 0.30 | 1.00 | AR-1, AR-2, AR-5, AR-7 |

## Table C. Base thermal-mass, comfort, and window metadata

These fields are still attached to the archetype layer. Source quality is mixed: some fields are literature-backed, while others remain pragmatic V1 assumptions and are marked accordingly.

| Archetype | c_th [Wh/m2K] | T_min [C] | T_max [C] | Window typology class | Glazing source tag | Solar/shading assumption | Sources |
| --- | --- | --- | --- | --- | --- | --- | --- |
| residential_pre1975 | 80.0 | 21.00 | 27.00 | single_glazing_box_type_or_wood_frame | AT_TABULA_ScientificReport_AEA_period_window_typologies | TABULA_common_procedure_standard_shading_values_pending_cohort_specific_refinement | AR-2, AR-3, AR-4, AR-6, AR-R1 |
| residential_1975_1990 | 75.0 | 21.00 | 27.00 | double_glazing_composite_window | AT_TABULA_ScientificReport_AEA_period_window_typologies | TABULA_common_procedure_standard_shading_values_pending_cohort_specific_refinement | AR-2, AR-3, AR-4, AR-6, AR-R1 |
| residential_1990_2000 | 70.0 | 21.00 | 27.00 | heat_protection_glazing | AT_TABULA_ScientificReport_AEA_period_window_typologies | TABULA_common_procedure_standard_shading_values_pending_cohort_specific_refinement | AR-2, AR-3, AR-4, AR-6, AR-R1 |
| residential_2000_2014 | 65.0 | 21.00 | 27.00 | triple_glazing_or_high_performance_window | AT_TABULA_ScientificReport_AEA_period_window_typologies | TABULA_common_procedure_standard_shading_values_pending_cohort_specific_refinement | AR-2, AR-3, AR-4, AR-6, AR-R1 |
| non_residential_pre1975 | 70.0 | 21.00 | 27.00 | n/a | non_residential_v1_placeholder_no_source_backed_window_typology | TABULA_common_procedure_standard_shading_values_pending_cohort_specific_refinement | AR-2, AR-3, AR-4, AR-6, AR-R1 |
| non_residential_1975_1990 | 65.0 | 21.00 | 27.00 | n/a | non_residential_v1_placeholder_no_source_backed_window_typology | TABULA_common_procedure_standard_shading_values_pending_cohort_specific_refinement | AR-2, AR-3, AR-4, AR-6, AR-R1 |
| non_residential_1990_2000 | 60.0 | 21.00 | 27.00 | n/a | non_residential_v1_placeholder_no_source_backed_window_typology | TABULA_common_procedure_standard_shading_values_pending_cohort_specific_refinement | AR-2, AR-3, AR-4, AR-6, AR-R1 |
| non_residential_2000_2014 | 55.0 | 21.00 | 27.00 | n/a | non_residential_v1_placeholder_no_source_backed_window_typology | TABULA_common_procedure_standard_shading_values_pending_cohort_specific_refinement | AR-2, AR-3, AR-4, AR-6, AR-R1 |

## Table D. Reference-building runtime geometry and legacy solar compatibility fields

These values describe one reference building per archetype on the current teacher-scale reference body. They are not Vienna-wide sums. The reference gross floor area is taken from the building-calibration SSOT. The solar multipliers and glazing-g values are still legacy compatibility fields in the runtime path and are not yet fully cohort-specific literature-backed SSOT.

| Archetype | Ref. GFA [m2] | Ref. volume [m3] | A_floor [m2] | A_wall [m2] | A_window_total [m2] | A_roof [m2] | Room height [m] | cp_air | g_glazing | g_glazing_shaded | Solar multipliers | Sources |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| residential_pre1975 | 1,000 | 3,000 | 1,000 | 820 | 180 | 370 | 3.00 | 0.34 | 0.60 | 0.00 | south=1.00; east=0.20; west=0.20; north=0.00 | RT-1, CAL-3, LEG-1 |
| residential_1975_1990 | 1,000 | 3,000 | 1,000 | 820 | 180 | 370 | 3.00 | 0.34 | 0.60 | 0.00 | south=1.00; east=0.20; west=0.20; north=0.00 | RT-1, CAL-3, LEG-1 |
| residential_1990_2000 | 1,000 | 3,000 | 1,000 | 820 | 180 | 370 | 3.00 | 0.34 | 0.60 | 0.00 | south=1.00; east=0.20; west=0.20; north=0.00 | RT-1, CAL-3, LEG-1 |
| residential_2000_2014 | 1,000 | 3,000 | 1,000 | 820 | 180 | 370 | 3.00 | 0.34 | 0.60 | 0.00 | south=1.00; east=0.20; west=0.20; north=0.00 | RT-1, CAL-3, LEG-1 |
| non_residential_pre1975 | 1,000 | 3,000 | 1,000 | 300 | 120 | 300 | 3.00 | 0.34 | 0.60 | 0.00 | south=1.00; east=0.20; west=0.20; north=0.00 | RT-1, CAL-3, LEG-1 |
| non_residential_1975_1990 | 1,000 | 3,000 | 1,000 | 300 | 120 | 300 | 3.00 | 0.34 | 0.60 | 0.00 | south=1.00; east=0.20; west=0.20; north=0.00 | RT-1, CAL-3, LEG-1 |
| non_residential_1990_2000 | 1,000 | 3,000 | 1,000 | 300 | 120 | 300 | 3.00 | 0.34 | 0.60 | 0.00 | south=1.00; east=0.20; west=0.20; north=0.00 | RT-1, CAL-3, LEG-1 |
| non_residential_2000_2014 | 1,000 | 3,000 | 1,000 | 300 | 120 | 300 | 3.00 | 0.34 | 0.60 | 0.00 | south=1.00; east=0.20; west=0.20; north=0.00 | RT-1, CAL-3, LEG-1 |

## Table E. Calibrated reduced-order runtime parameters for the reference building

These are the EnergyPlus-teacher-derived reduced-order parameters that the current calibrated_v1 runtime path actually uses for thermal dynamics. Both the normalized per-square-meter values and the resulting parameters for the reference building are shown.

| Archetype | H_total [W/m2K] | H_trans [W/m2K] | C_eff [Wh/m2K] | tau [h] | H_total ref [W/K] | H_trans ref [W/K] | C_eff ref [Wh/K] | Air-loss scale | Sources |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| residential_pre1975 | 1.264 | 1.264 | 25.020 | 19.79 | 1,264.4 | 1,264.4 | 25,019.7 | 0.000 | CAL-1, CAL-2, CAL-3, CAL-4 |
| residential_1975_1990 | 1.045 | 1.038 | 22.253 | 21.30 | 1,044.8 | 1,038.1 | 22,253.4 | 0.014 | CAL-1, CAL-2, CAL-3, CAL-4 |
| residential_1990_2000 | 0.791 | 0.734 | 20.432 | 25.83 | 791.2 | 734.1 | 20,432.0 | 0.115 | CAL-1, CAL-2, CAL-3, CAL-4 |
| residential_2000_2014 | 0.478 | 0.342 | 21.196 | 44.31 | 478.4 | 341.7 | 21,195.8 | 0.276 | CAL-1, CAL-2, CAL-3, CAL-4 |
| non_residential_pre1975 | 0.900 | 0.900 | 25.705 | 28.55 | 900.4 | 900.4 | 25,704.5 | 0.000 | CAL-1, CAL-2, CAL-3, CAL-4 |
| non_residential_1975_1990 | 0.719 | 0.673 | 22.112 | 30.77 | 718.7 | 673.5 | 22,112.0 | 0.091 | CAL-1, CAL-2, CAL-3, CAL-4 |
| non_residential_1990_2000 | 0.544 | 0.480 | 19.504 | 35.84 | 544.3 | 479.5 | 19,504.3 | 0.131 | CAL-1, CAL-2, CAL-3, CAL-4 |
| non_residential_2000_2014 | 0.322 | 0.208 | 19.192 | 59.64 | 321.8 | 208.2 | 19,191.7 | 0.229 | CAL-1, CAL-2, CAL-3, CAL-4 |

## Table F. Calibrated event-response parameters

These are the cohort-specific thermflex sidecar parameters fitted from the EnergyPlus teacher experiments. They constrain preheat, cutback, and recovery behavior when event-response bounds are active.

| Cohort | Preheat energy [kWh] | Preheat peak [kW] | Cutback shed [kWh] | Cutback peak [kW] | Recovery rebound [kWh] | Recovery peak [kW] | Recovery time [h] | Sources |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| residential_pre1975 | 79.01 | 12.31 | 76.11 | 11.54 | 50.24 | 7.93 | 1.00 | CAL-1, CAL-2, CAL-3, CAL-4 |
| residential_1975_1990 | 71.96 | 11.71 | 69.69 | 10.82 | 50.75 | 7.96 | 1.00 | CAL-1, CAL-2, CAL-3, CAL-4 |
| residential_1990_2000 | 64.76 | 10.86 | 60.40 | 9.83 | 49.29 | 7.65 | 1.00 | CAL-1, CAL-2, CAL-3, CAL-4 |
| residential_2000_2014 | 51.12 | 9.07 | 44.70 | 7.08 | 40.60 | 5.89 | 1.00 | CAL-1, CAL-2, CAL-3, CAL-4 |
| non_residential_pre1975 | 67.66 | 11.19 | 64.42 | 10.23 | 49.20 | 7.78 | 1.00 | CAL-1, CAL-2, CAL-3, CAL-4 |
| non_residential_1975_1990 | 61.38 | 10.53 | 58.42 | 9.39 | 48.49 | 7.63 | 1.00 | CAL-1, CAL-2, CAL-3, CAL-4 |
| non_residential_1990_2000 | 55.24 | 9.67 | 50.88 | 8.21 | 45.23 | 7.02 | 1.00 | CAL-1, CAL-2, CAL-3, CAL-4 |
| non_residential_2000_2014 | 42.99 | 7.48 | 33.75 | 4.05 | 30.73 | 4.50 | 1.00 | CAL-1, CAL-2, CAL-3, CAL-4 |

## Table G. Global heating-control parameters

These are global building-operation settings from the Settings layer. They are not archetype-specific and may be overridden by explicit paper-case JSON overrides, but they still belong to the active building model path.

| Parameter | Value | Role | Sources |
| --- | --- | --- | --- |
| reference_control_mode | constant | global default | HC-1 |
| control_mode | constant | global default | HC-1 |
| constant_setpoint_c | 22.00 | global default | HC-1 |
| day_setpoint_c | 22.00 | global default | HC-1 |
| night_setpoint_c | 19.00 | global default | HC-1 |
| day_start_hour | 6 | global default | HC-1 |
| night_start_hour | 22 | global default | HC-1 |
| hysteresis_band_k | 1.00 | global default | HC-1 |
| comfort_band_enabled | no | global default | HC-1 |
| comfort_band_k | 0.00 | global default | HC-1 |
| max_heating_power_mode | archetype_design | global default | HC-1 |
| max_heating_power_w_per_m2 | 60.0 | global default | HC-1 |
| max_heating_power_multiplier | 1.00 | global default | HC-1 |
| design_indoor_temp_c | 22.00 | global default | HC-1 |
| design_outdoor_temp_c | -12.00 | global default | HC-1 |
| design_ventilation_mode | p95 | global default | HC-1 |
| design_internal_gains_w_per_m2 | 0.00 | global default | HC-1 |
| design_solar_gains_w_per_m2 | 0.00 | global default | HC-1 |
| enable_active_cooling | yes | global default | HC-1 |
| cooling_setpoint_c | 27.00 | global default | HC-1 |
| max_cooling_power_w_per_m2 | 40.0 | global default | HC-1 |

## Table H. Global thermflex constraint parameters

These are the global thermflex/bound settings from the Settings layer. Representative-day and paper sensitivity runs override a subset of them.

| Parameter | Value | Role | Sources |
| --- | --- | --- | --- |
| use_explicit_lower_bounds | no | scenario-dependent | TF-1 |
| constant_lower_bound_c | n/a | scenario-dependent | TF-1 |
| day_lower_bound_c | n/a | scenario-dependent | TF-1 |
| night_lower_bound_c | n/a | scenario-dependent | TF-1 |
| comfort_band_k | 0.00 | scenario-dependent | TF-1 |
| reference_deadband_k | 0.50 | scenario-dependent | TF-1 |
| constrain_upper_temperature | no | scenario-dependent | TF-1 |
| use_event_response_bounds | no | scenario-dependent | TF-1 |
| enforce_event_peak_bounds | yes | scenario-dependent | TF-1 |
| enforce_event_energy_bounds | yes | scenario-dependent | TF-1 |
| enforce_recovery_cooldown | yes | scenario-dependent | TF-1 |
| max_flex_duration_h | 0 | scenario-dependent | TF-1 |
| max_flex_events_per_day | 0 | scenario-dependent | TF-1 |
| activation_penalty_eur_per_member_h | 0.000100 | scenario-dependent | TF-1 |
| temperature_violation_penalty_eur_per_degree_h | 1,000,000 | scenario-dependent | TF-1 |
| allow_terminal_deviation | yes | scenario-dependent | TF-1 |
| terminal_band_k | 0.00 | scenario-dependent | TF-1 |

## Bibliography and Source Notes

- **BS-1**: Citiwatt indicators Vienna local snapshot; used via Data/building_stock/Vienna/building_stock.py.
  Note: Building-stock scale anchors: total heat, GFA, volume, and period shares.
- **BS-2**: Vienna Energy Report 2025 and repo notes in Documentation/Sources/wien_und_dispatch_quellen.md.
  Note: Official Vienna electricity anchors and building-sector context used in the stock layer.
- **BS-R1**: Repo-derived V1 stock assumptions in Data/building_stock/Vienna/building_stock.py.
  Note: Includes the explicit non-residential hot-water exclusion and the current exogenous electricity calibration anchors.
- **AR-1**: Austrian TABULA / EPISCOPE country page: https://episcope.eu/building-typology/country/at/
  Note: Residential period-specific U-value and typology anchor.
- **AR-2**: Austrian TABULA Scientific Report: https://episcope.eu/fileadmin/tabula/public/docs/scientific/AT_TABULA_ScientificReport_AEA.pdf
  Note: Residential period ladder, window typologies, and Austrian multi-family context.
- **AR-3**: TABULA common calculation procedure: https://episcope.eu/building-typology/tabula-structure/calculation/
  Note: Standard shading and usage procedure values; method anchor, not cohort-specific Vienna truth.
- **AR-4**: TABULA WebTool FAQ: https://episcope.eu/building-typology/webtool/
  Note: Important caution that the 45 Wh/(m2K) procedure value is too coarse for research use.
- **AR-5**: TABULA Final Report Appendix Volume: https://episcope.eu/fileadmin/tabula/public/docs/report/TABULA_FinalReport_AppendixVolume.pdf
  Note: Residential envelope-area ratios per conditioned floor area.
- **AR-6**: OIB-Richtlinie 6 / Kostenoptimalitaet: https://www.oib.or.at/sites/default/files/kostenoptimalitaet_0.pdf
  Note: Austrian plausibility anchors for setpoints, g-values, and air-change assumptions.
- **AR-7**: TABULA Thematic Report No. 3 / Non-Residential Buildings: https://episcope.eu/building-typology/tabula-structure/non-residential/
  Note: Explains why non-residential geometry and exposure assumptions remain less certain than residential ones.
- **AR-R1**: Repo-internal V1 assumption in Data/thermal_archetypes/Vienna/thermal_archetypes.py.
  Note: Areal heat capacities and some non-residential fields are still pragmatic start values, not direct Vienna observations.
- **RT-1**: Runtime derivation in Technical_model/technologies/buildings/runtime_building_params.py.
  Note: Cohort-scale areas, room height, and effective runtime fields are derived from the stock + archetype SSOT.
- **LEG-1**: Legacy compatibility fields in Data/technology_data/building.py and runtime_building_params.py.
  Note: solar_multipliers, g_glazing, and g_glazing_shaded remain active compatibility placeholders and are not yet fully recalibrated Vienna SSOT.
- **CAL-1**: Open-Meteo Historical Weather API: https://open-meteo.com/en/docs/historical-weather-api
  Note: Weather driver for the pseudo-EPW and calibration path.
- **CAL-2**: Climate.OneBuilding Vienna EPW template: https://climate.onebuilding.org/WMO_Region_6_Europe/AUT_Austria/index.html
  Note: Header and format anchor for pseudo-EPW generation.
- **CAL-3**: EnergyPlus 26.1.0 and repo calibration teacher path.
  Note: Teacher model used to derive reduced-order and event-response fits.
- **CAL-4**: Repo-generated calibration exports: Data/thermal_archetypes/Vienna/calibrated_v1.py plus reduced_order_fit_summary.csv and event_response_fit_summary.csv.
  Note: Direct source of the fitted reduced-order and event-response sidecar parameters.
- **HC-1**: Settings/technical/heating_control.py
  Note: Global heating and cooling control defaults; scenario-specific overrides may change them in paper runs.
- **TF-1**: Settings/constraints/thermflex.py
  Note: Global thermflex-bound defaults; representative-day and paper runs override a subset of them explicitly.
