# Run Cases

## Wiener DH-/Thermflex-Vergleichsfaelle

Die stabilen SSOT-Run-Cases liegen unter:

- [thermflex](/c:/Users/Philipp%20Thunshirn/Desktop/PhD/Python%20model/Master/Optimization/validation/model_validation/overrides/thermflex)

Aktive Vergleichsfaelle:

- [vienna_ref2023_dh_baseline_constant_no_thermflex_two_stage.json](/c:/Users/Philipp%20Thunshirn/Desktop/PhD/Python%20model/Master/Optimization/validation/model_validation/overrides/thermflex/vienna_ref2023_dh_baseline_constant_no_thermflex_two_stage.json)
  - Konstanter Referenzfall ohne Thermflex

- [vienna_ref2023_dh_day_night_no_thermflex_two_stage.json](/c:/Users/Philipp%20Thunshirn/Desktop/PhD/Python%20model/Master/Optimization/validation/model_validation/overrides/thermflex/vienna_ref2023_dh_day_night_no_thermflex_two_stage.json)
  - Day/Night-Regelung ohne Thermflex

- [vienna_ref2023_dh_day_night_thermflex_two_stage.json](/c:/Users/Philipp%20Thunshirn/Desktop/PhD/Python%20model/Master/Optimization/validation/model_validation/overrides/thermflex/vienna_ref2023_dh_day_night_thermflex_two_stage.json)
  - Day/Night-Regelung mit Thermflex

Hinweis:

- Der fruehere Override [vienna_ref2023_dh_thermflex_operations_two_stage.json](/c:/Users/Philipp%20Thunshirn/Desktop/PhD/Python%20model/Master/Optimization/validation/model_validation/overrides/thermflex/vienna_ref2023_dh_thermflex_operations_two_stage.json) bleibt als Legacy-Fall im Repo, damit bestehende Pfade nicht brechen.
- `run_optimization.py` zeigt ohne CLI-Argumente jetzt auf den standardisierten Fall `day_night_thermflex`.

## Wiener Paper-Faelle (`milp_day_ahead`, `calibrated_v1`)

Aktive Paper-Run-Cases:

- [vienna_ref2023_dh_baseline_constant_no_thermflex_paper_day_ahead.json](/c:/Users/Philipp%20Thunshirn/Desktop/PhD/Python%20model/Master/Optimization/validation/model_validation/overrides/thermflex/vienna_ref2023_dh_baseline_constant_no_thermflex_paper_day_ahead.json)
  - konstanter Referenzfall ohne Thermflex

- [vienna_ref2023_dh_baseline_constant_thermflex_paper_day_ahead.json](/c:/Users/Philipp%20Thunshirn/Desktop/PhD/Python%20model/Master/Optimization/validation/model_validation/overrides/thermflex/vienna_ref2023_dh_baseline_constant_thermflex_paper_day_ahead.json)
  - konstanter Referenzfall mit aktivem Thermflex
  - sauberer Isolationsfall fuer "Thermflex generell" ohne Mischwirkung aus `day_night`

- [vienna_ref2023_dh_day_night_no_thermflex_paper_day_ahead.json](/c:/Users/Philipp%20Thunshirn/Desktop/PhD/Python%20model/Master/Optimization/validation/model_validation/overrides/thermflex/vienna_ref2023_dh_day_night_no_thermflex_paper_day_ahead.json)
  - Day/Night-Regelung ohne Thermflex

- [vienna_ref2023_dh_day_night_thermflex_paper_day_ahead.json](/c:/Users/Philipp%20Thunshirn/Desktop/PhD/Python%20model/Master/Optimization/validation/model_validation/overrides/thermflex/vienna_ref2023_dh_day_night_thermflex_paper_day_ahead.json)
  - Day/Night-Regelung mit Thermflex und aktiven Event-Bounds

Gemeinsame explizite Benchmark-Basis:

- alle drei Paper-Faelle setzen `thermal_archetypes.variant = calibrated_v1` explizit im Override
- alle drei Paper-Faelle nutzen dieselbe feste DH-Designbasis
- diese feste Designbasis stammt bewusst aus einem **gemeinsam feasiblem** Punkt des aktuellen
  `vienna_ref2023_dh_day_night_thermflex_surrogate_train`-Truth-Pfads
- konkret ist es der gemeinsame feasible Referenzpunkt `row 10` ueber:
  - `baseline_constant_no_thermflex_paper_day_ahead`
  - `day_night_no_thermflex_paper_day_ahead`
  - `day_night_thermflex_paper_day_ahead`

Aktive gemeinsame feste DH-Kapazitaeten:

- `district_heat_pump_kw_th = 28402.2`
- `district_thermal_storage_kwh_th = 1110490.3`
- `district_biomass_chp_kw_th = 16027.5`
- `district_gas_chp_kw_el = 675590.0`

Zweck:

- solver- und exportseitig gemeinsame Vergleichsbasis fuer den Paper-Schnitt
- keine implizite Abhaengigkeit mehr von einem alten, unter `calibrated_v1 + event bounds` teilweise unfeasiblem Benchmark

Konstanter Thermflex-Isolationsschnitt:

- der konstante Thermflex-Fall nutzt dieselbe feste DH-Designbasis wie der konstante Referenzfall
- beide Faelle haben:
  - `reference_control_mode = constant`
  - `control_mode = constant`
  - `constant_setpoint_c = 22.5`
- der Unterschied ist damit bewusst nur:
  - Thermflex `off`
  - Thermflex `on`
- aktueller expliziter Thermflex-Schnitt fuer den konstanten Fall:
  - `constant_lower_bound_c = 21.0`
  - `max_flex_duration_h = 4`
  - `max_flex_events_per_day = 1`
  - `constrain_upper_temperature = false`
  - Event-Bounds aktiv

## Wiener DH-/Thermflex-Surrogatfaelle

Aktive Surrogat-Trainingsfaelle:

- [vienna_ref2023_dh_baseline_constant_no_thermflex_surrogate_mini.json](/c:/Users/Philipp%20Thunshirn/Desktop/PhD/Python%20model/Master/Optimization/validation/model_validation/overrides/thermflex/vienna_ref2023_dh_baseline_constant_no_thermflex_surrogate_mini.json)
  - kleiner `xgb`-Smoke fuer den Baseline-Fall

- [vienna_ref2023_dh_day_night_no_thermflex_surrogate_mini.json](/c:/Users/Philipp%20Thunshirn/Desktop/PhD/Python%20model/Master/Optimization/validation/model_validation/overrides/thermflex/vienna_ref2023_dh_day_night_no_thermflex_surrogate_mini.json)
  - kleiner `xgb`-Smoke fuer den Day/Night-Fall ohne Thermflex

- [vienna_ref2023_dh_baseline_constant_no_thermflex_surrogate_train.json](/c:/Users/Philipp%20Thunshirn/Desktop/PhD/Python%20model/Master/Optimization/validation/model_validation/overrides/thermflex/vienna_ref2023_dh_baseline_constant_no_thermflex_surrogate_train.json)
  - erster sinnvoller `xgb`-Trainingsfall fuer den konstanten Baseline-Modus

- [vienna_ref2023_dh_day_night_no_thermflex_surrogate_train.json](/c:/Users/Philipp%20Thunshirn/Desktop/PhD/Python%20model/Master/Optimization/validation/model_validation/overrides/thermflex/vienna_ref2023_dh_day_night_no_thermflex_surrogate_train.json)
  - erster sinnvoller `xgb`-Trainingsfall fuer den Day/Night-Modus ohne Thermflex

- [vienna_ref2023_dh_day_night_thermflex_surrogate_mini.json](/c:/Users/Philipp%20Thunshirn/Desktop/PhD/Python%20model/Master/Optimization/validation/model_validation/overrides/thermflex/vienna_ref2023_dh_day_night_thermflex_surrogate_mini.json)
  - kleiner `xgb`-Smoke fuer den Day/Night-Thermflex-Fall

- [vienna_ref2023_dh_day_night_thermflex_surrogate_train.json](/c:/Users/Philipp%20Thunshirn/Desktop/PhD/Python%20model/Master/Optimization/validation/model_validation/overrides/thermflex/vienna_ref2023_dh_day_night_thermflex_surrogate_train.json)
  - erster sinnvoller `xgb`-Trainingsfall mit `milp_day_ahead` und groesserem LHS-Sample

- [vienna_ref2023_dh_day_night_thermflex_surrogate_train_l48.json](/c:/Users/Philipp%20Thunshirn/Desktop/PhD/Python%20model/Master/Optimization/validation/model_validation/overrides/thermflex/vienna_ref2023_dh_day_night_thermflex_surrogate_train_l48.json)
  - vergroesserter `xgb`-Trainingsfall mit `48` LHS-Punkten auf demselben `milp_day_ahead + calibrated_v1 + event bounds`-Truth-Pfad

- [vienna_ref2023_dh_day_night_thermflex_surrogate_focus_l48.json](/c:/Users/Philipp%20Thunshirn/Desktop/PhD/Python%20model/Master/Optimization/validation/model_validation/overrides/thermflex/vienna_ref2023_dh_day_night_thermflex_surrogate_focus_l48.json)
  - fokussierter Publish-/Analyse-Schnitt mit `20` expliziten KPI-Targets statt des frueheren breiten System-Slices

- [vienna_ref2023_dh_day_night_thermflex_surrogate_opt_l96.json](/c:/Users/Philipp%20Thunshirn/Desktop/PhD/Python%20model/Master/Optimization/validation/model_validation/overrides/thermflex/vienna_ref2023_dh_day_night_thermflex_surrogate_opt_l96.json)
  - engerer Optimierungs-Schnitt mit `11` Targets und `96` LHS-Punkten fuer den eigentlichen Surrogat-Dispatchpfad

- [vienna_ref2023_dh_day_night_thermflex_surrogate_opt_append_l64.json](/c:/Users/Philipp%20Thunshirn/Desktop/PhD/Python%20model/Master/Optimization/validation/model_validation/overrides/thermflex/vienna_ref2023_dh_day_night_thermflex_surrogate_opt_append_l64.json)
  - Append-Lauf auf derselben `dispatch_optimization_core`-Family zur vergroesserten Truth-Basis ohne neuen Family-Silo

- [vienna_ref2023_dh_day_night_thermflex_surrogate_ready.json](/c:/Users/Philipp%20Thunshirn/Desktop/PhD/Python%20model/Master/Optimization/validation/model_validation/overrides/thermflex/vienna_ref2023_dh_day_night_thermflex_surrogate_ready.json)
  - erster schwererer `xgb`-Trainingsfall mit `milp_two_stage`

Hinweis:

- `train_surrogate.py` zeigt ohne CLI-Argumente jetzt auf den standardisierten Fall `day_night_thermflex_surrogate_train`.
- Die drei Vergleichsmodi liegen aktuell als getrennte Surrogat-Familien vor; ein spaeterer gemeinsamer Multi-Case-Trainingspfad bleibt als eigener Ausbauschritt offen.
- `vienna_ref2023_dh_day_night_thermflex_surrogate_train.json` setzt `thermal_archetypes.variant = calibrated_v1` jetzt explizit im Override statt still ueber den globalen Default.
- `vienna_ref2023_dh_day_night_thermflex_surrogate_train_l48.json` nutzt dieselbe Family wie der normale Thermflex-Trainingsfall und vergroessert den Truth-Datensatz deshalb ueber den bestehenden Dataset-SSOT statt einen neuen Family-Silo aufzubauen.
- `vienna_ref2023_dh_day_night_thermflex_surrogate_focus_l48.json` deaktiviert die automatische Active-Technology-Target-Erweiterung explizit, damit der gelernte KPI-Schnitt vollstaendig aus dem Override/Settings-SSOT lesbar bleibt.
- `vienna_ref2023_dh_day_night_thermflex_surrogate_opt_l96.json` ist aktuell der engste aktive Wiener Optimierungs-Surrogatpfad.

## Wiener Surrogat-Optimierung und Recheck

Aktiver Hauptpfad fuer schnelle Surrogat-Optimierung:

- [vienna_ref2023_dh_day_night_thermflex_surrogate_optimize_smoke.json](/c:/Users/Philipp%20Thunshirn/Desktop/PhD/Python%20model/Master/Optimization/validation/model_validation/overrides/thermflex/vienna_ref2023_dh_day_night_thermflex_surrogate_optimize_smoke.json)
  - kleiner NSGA2-Smoke auf dem aktiven `dispatch_optimization_core`-Artefakt

- [vienna_ref2023_dh_day_night_thermflex_surrogate_optimize.json](/c:/Users/Philipp%20Thunshirn/Desktop/PhD/Python%20model/Master/Optimization/validation/model_validation/overrides/thermflex/vienna_ref2023_dh_day_night_thermflex_surrogate_optimize.json)
  - erster echter Surrogat-Optimierungsfall auf dem Wiener Thermflex-Day-Ahead-Schnitt

- [vienna_ref2023_dh_day_night_thermflex_surrogate_optimize_biobj_smoke.json](/c:/Users/Philipp%20Thunshirn/Desktop/PhD/Python%20model/Master/Optimization/validation/model_validation/overrides/thermflex/vienna_ref2023_dh_day_night_thermflex_surrogate_optimize_biobj_smoke.json)
  - biobjektiver Smoke mit `dispatch_cost_eur + co2_emissions_total_t`

- [vienna_ref2023_dh_day_night_thermflex_surrogate_optimize_biobj.json](/c:/Users/Philipp%20Thunshirn/Desktop/PhD/Python%20model/Master/Optimization/validation/model_validation/overrides/thermflex/vienna_ref2023_dh_day_night_thermflex_surrogate_optimize_biobj.json)
  - aktiver biobjektiver Wiener Surrogat-Optimierungspfad mit `dispatch_cost_eur + co2_emissions_total_t`

Expliziter experimenteller Screen-Pfad:

- [vienna_ref2023_dh_day_night_thermflex_surrogate_optimize_screened_smoke.json](/c:/Users/Philipp%20Thunshirn/Desktop/PhD/Python%20model/Master/Optimization/validation/model_validation/overrides/thermflex/vienna_ref2023_dh_day_night_thermflex_surrogate_optimize_screened_smoke.json)
  - Smoke mit explizitem `surrogate_feasible_probability_guard`

- [vienna_ref2023_dh_day_night_thermflex_surrogate_optimize_screened.json](/c:/Users/Philipp%20Thunshirn/Desktop/PhD/Python%20model/Master/Optimization/validation/model_validation/overrides/thermflex/vienna_ref2023_dh_day_night_thermflex_surrogate_optimize_screened.json)
  - experimenteller Optimierungsfall mit explizitem Family-basiertem Feasibility-Screen

Recheck-Runner:

- [run_vienna_thermflex_surrogate_recheck.py](/c:/Users/Philipp%20Thunshirn/Desktop/PhD/Python%20model/Master/Optimization/run/papers/dh_thermflex/run_vienna_thermflex_surrogate_recheck.py)
  - validiert Surrogat-Pareto-Punkte gegen Gold `milp_day_ahead`
  - replayt optional den besten day-ahead-feasiblen Kandidaten mit `milp_two_stage`
  - nimmt jetzt explizit `--sort-column`, damit Kosten- und CO2-Enden getrennt recheckbar bleiben

Aktueller Stand:

- Der ungescreente Hauptpfad liefert im Gold-Recheck unter den Top-10 zwei day-ahead-feasible Kandidaten; der beste liegt auf `rank 4`.
- Der erste explizite KNN-Screen bleibt experimentell; im ersten Recheck lagen unter den Top-10 keine day-ahead-feasiblen Kandidaten.
- Der biobjektive Pfad liefert jetzt eine echte Pareto-Menge ueber `dispatch_cost_eur + co2_emissions_total_t`.
- Im Gold-Recheck des biobjektiven Pfads:
  - kosten-sortiert: `7/10` day-ahead-feasible, bester feasible auf `rank 2`
  - CO2-sortiert: `7/10` day-ahead-feasible, bester feasible auf `rank 3`
- `milp_two_stage` bleibt auch auf dem biobjektiven Pfad Endpunkt-Validierung; der kosten-sortierte ausgewaehlte Kandidat blieb dort infeasible.

Expliziter Gold-Kandidaten-Runner fuer publish-faehige Pareto-Vertreter:

- [run_vienna_thermflex_biobj_gold_candidates.py](/c:/Users/Philipp%20Thunshirn/Desktop/PhD/Python%20model/Master/Optimization/run/papers/dh_thermflex/run_vienna_thermflex_biobj_gold_candidates.py)
  - liest die biobjektive Pareto-Menge
  - waehlt explizit drei day-ahead-gold-feasible Vertreter:
    - `biobj_cost_end`
    - `biobj_co2_end`
    - `biobj_mid_tradeoff`
  - schreibt daraus echte Gold-Runs plus Vergleichsartefakte

Aktueller Gold-Kandidaten-Output:

- [biobj_gold_candidates_20260403_093146](/c:/Users/Philipp%20Thunshirn/Desktop/PhD/Python%20model/Master/Optimization/run/results/Vienna/gold/biobj_gold_candidates_20260403_093146)
  - inklusive:
    - `selection_summary.json`
    - `selection_audit.csv`
    - drei echte Gold-Runs
    - `paper_comparison/`

Aktuelle Auswahl:

- `biobj_cost_end`
  - Kosten-Ende der Pareto-Menge
- `biobj_co2_end`
  - CO2-Ende der Pareto-Menge
- `biobj_mid_tradeoff`
  - expliziter Mittelkandidat ueber normierte Distanz zum Pareto-Zentrum

Gezielter Zweistufen-Endpunkt-Runner:

- [run_vienna_selected_candidate_two_stage.py](/c:/Users/Philipp%20Thunshirn/Desktop/PhD/Python%20model/Master/Optimization/run/papers/dh_thermflex/run_vienna_selected_candidate_two_stage.py)
  - liest ein exportiertes `selected_candidate.json`
  - replayt denselben Designpunkt explizit mit `milp_two_stage`
  - schreibt auch bei Infeasibility eine explizite `two_stage_endpoint_summary.json`

## Wiener Paper-Analyse

Aktiver Analyse-Runner:

- [run_vienna_thermflex_paper_analysis.py](/c:/Users/Philipp%20Thunshirn/Desktop/PhD/Python%20model/Master/Optimization/run/papers/dh_thermflex/run_vienna_thermflex_paper_analysis.py)
  - zieht die neuesten drei Wiener Paper-Runs automatisch aus `Optimization/run/results/Vienna/gold/`
  - baut daraus CSV/JSON/Markdown/Plot ueber den generischen Analysis-Layer

Aktueller Vergleichsoutput:

- [paper_dispatch_comparison_20260402_195332](/c:/Users/Philipp%20Thunshirn/Desktop/PhD/Python%20model/Master/Optimization/run/results/Vienna/gold/paper_dispatch_comparison_20260402_195332)
  - inklusive `selected_runs.json`, damit die Auswertung nicht still auf unbekannten Run-Staenden basiert

- [run_vienna_constant_thermflex_paper_analysis.py](/c:/Users/Philipp%20Thunshirn/Desktop/PhD/Python%20model/Master/Optimization/run/papers/dh_thermflex/run_vienna_constant_thermflex_paper_analysis.py)
  - baut explizit den isolierten Zwei-Fall-Vergleich:
    - `constant_no_thermflex`
    - `constant_thermflex`

- [paper_dispatch_comparison_20260403_102050](/c:/Users/Philipp%20Thunshirn/Desktop/PhD/Python%20model/Master/Optimization/run/results/Vienna/gold/paper_dispatch_comparison_20260403_102050)
  - isolierter konstanter Thermflex-Vergleich
  - enthaelt:
    - `paper_dispatch_comparison.csv`
    - `paper_dispatch_comparison.md`
    - `paper_dispatch_comparison.png`
    - `selected_runs.json`

- [paper_dispatch_comparison_20260403_102843](/c:/Users/Philipp%20Thunshirn/Desktop/PhD/Python%20model/Master/Optimization/run/results/Vienna/gold/paper_dispatch_comparison_20260403_102843)
  - gleicher isolierter Vergleich mit zusaetzlichem fokussiertem Plotblock
  - zusaetzliche Artefakte:
    - `constant_thermflex_isolation.png`
    - `constant_thermflex_isolation_summary.json`
    - `constant_thermflex_isolation_summary.md`

- [paper_dispatch_comparison_20260403_110810](/c:/Users/Philipp%20Thunshirn/Desktop/PhD/Python%20model/Master/Optimization/run/results/Vienna/gold/paper_dispatch_comparison_20260403_110810)
  - **korrigierter** isolierter konstanter Thermflex-Vergleich nach Einheitenfix im Runtime-Gebaeudelastpfad
  - nur dieser Vergleich ist fuer die aktuelle KPI-Interpretation gueltig
  - basiert auf den neu gerechneten Runs:
    - [20260403_110620_vienna_ref2023_dh_baseline_constant_no_thermflex_paper_day_ahead](/c:/Users/Philipp%20Thunshirn/Desktop/PhD/Python%20model/Master/Optimization/run/results/Vienna/gold/20260403_110620_vienna_ref2023_dh_baseline_constant_no_thermflex_paper_day_ahead)
    - [20260403_110655_vienna_ref2023_dh_baseline_constant_thermflex_paper_day_ahead](/c:/Users/Philipp%20Thunshirn/Desktop/PhD/Python%20model/Master/Optimization/run/results/Vienna/gold/20260403_110655_vienna_ref2023_dh_baseline_constant_thermflex_paper_day_ahead)
  - enthaelt:
    - `paper_dispatch_comparison.csv`
    - `paper_dispatch_comparison.md`
    - `paper_dispatch_comparison.png`

- [paper_dispatch_comparison_20260403_111854](/c:/Users/Philipp%20Thunshirn/Desktop/PhD/Python%20model/Master/Optimization/run/results/Vienna/gold/paper_dispatch_comparison_20260403_111854)
  - korrigierter konstanter Isolationsvergleich mit zusaetzlichem 24h-Zeitreihenplot
  - enthaelt zusaetzlich:
    - [constant_thermflex_timeseries.png](/c:/Users/Philipp%20Thunshirn/Desktop/PhD/Python%20model/Master/Optimization/run/results/Vienna/gold/paper_dispatch_comparison_20260403_111854/constant_thermflex_timeseries.png)
    - [constant_thermflex_timeseries_settings.json](/c:/Users/Philipp%20Thunshirn/Desktop/PhD/Python%20model/Master/Optimization/run/results/Vienna/gold/paper_dispatch_comparison_20260403_111854/constant_thermflex_timeseries_settings.json)
    - [constant_thermflex_timeseries_settings.md](/c:/Users/Philipp%20Thunshirn/Desktop/PhD/Python%20model/Master/Optimization/run/results/Vienna/gold/paper_dispatch_comparison_20260403_111854/constant_thermflex_timeseries_settings.md)
  - zeigt explizit:
    - `district_space_heat_demand_ref` vs `district_space_heat_demand`
    - `district_gas_boiler_generation`
    - `district_gas_chp_thermal_generation`
    - `district_heat_pump_generation`
    - jeweils mit identischen installierten Kapazitaetslinien fuer beide Faelle

- [run_vienna_constant_thermflex_sensitivity_cases.py](/c:/Users/Philipp%20Thunshirn/Desktop/PhD/Python%20model/Master/Optimization/run/papers/dh_thermflex/run_vienna_constant_thermflex_sensitivity_cases.py)
  - rechnet einen kleinen expliziten Sensitivitaetsblock fuer den konstanten
    Thermflex-Isolationsfall
  - Fallachse:
    - `constant_lower_bound_c`
    - `max_flex_duration_h`
    - `max_flex_events_per_day`

- [run_vienna_constant_thermflex_sensitivity_analysis.py](/c:/Users/Philipp%20Thunshirn/Desktop/PhD/Python%20model/Master/Optimization/run/papers/dh_thermflex/run_vienna_constant_thermflex_sensitivity_analysis.py)
  - loest die neuesten Gold-Runs fuer den expliziten Sensitivitaetsblock auf
  - erzeugt daraus einen kompakten Vergleich ueber den Analysis-Layer
  - keine stillen Fallbacks:
    - jede benoetigte Run-Signatur muss vorhanden sein
    - KPI-Spalten muessen exakt mit dem Export-Schema uebereinstimmen

- [paper_dispatch_comparison_20260403_114641](/c:/Users/Philipp%20Thunshirn/Desktop/PhD/Python%20model/Master/Optimization/run/results/Vienna/gold/paper_dispatch_comparison_20260403_114641)
  - Sensitivitaetsbundle fuer den konstanten Thermflex-Isolationsfall
  - enthaelt:
    - `paper_dispatch_comparison.csv`
    - `constant_thermflex_sensitivity.png`
    - `constant_thermflex_sensitivity_summary.json`
    - `constant_thermflex_sensitivity_summary.md`
    - `selected_runs.json`
  - ausgewertete Faelle:
    - `lb21p0_dur1_evt1`
    - `constant_no_thermflex`
    - `lb21p0_dur2_evt1`
    - `lb21p0_dur4_evt1`
    - `lb21p0_dur6_evt1`
    - `lb21p0_dur8_evt1`
    - `lb22p5_dur4_evt1_upper_only`
    - `lb22p5_dur24_evt24_upper_only_proxy`
    - `lb21p5_dur4_evt1`
    - `lb20p0_dur4_evt1`
    - `lb21p0_dur4_evt2`
  - wichtigster Dauerbefund fuer `lower = 21.0 C`, `events = 1`:
    - `2 h -> 4 h` bringt noch sichtbare Kostensenkung
    - `4 h -> 6 h -> 8 h` verbessert vor allem Peak-Glattung, waehrend
      `shifted heat` weitgehend saturiert

- [paper_dispatch_comparison_20260403_124056](/c:/Users/Philipp%20Thunshirn/Desktop/PhD/Python%20model/Master/Optimization/run/results/Vienna/gold/paper_dispatch_comparison_20260403_124056)
  - erweiterter Sensitivitaetsbundle fuer den konstanten Thermflex-Isolationsfall
  - enthaelt zusaetzlich zum KPI-Vergleich:
    - `constant_thermflex_cohort_utilization_hourly.csv`
    - `constant_thermflex_cohort_utilization_summary.csv`
    - `constant_thermflex_cohort_utilization_summary.json`
    - `constant_thermflex_cohort_utilization_summary.md`
    - `constant_thermflex_cohort_utilization.png`
  - neue explizite Zusatzfaelle:
    - `lb21p0_dur1_evt1`
    - `lb22p5_dur4_evt1_upper_only`
    - `lb22p5_dur24_evt24_upper_only_proxy`
  - Zweck:
    - nicht nur System-KPIs, sondern die realisierte Kohorten-Nutzung des globalen
      `duration`-/`event`-Rahmens sichtbar machen
  - erste Kernbefunde:
    - `lb22p5_dur4_evt1_upper_only` und `lb22p5_dur24_evt24_upper_only_proxy`
      sind im aktuellen 24h-Slice praktisch identisch
    - `non_residential_2000_2014` nutzt im gezeigten Winterslice praktisch keine Flex
    - `residential_2000_2014` profitiert stark von laengeren Dauern
    - mehrere andere Kohorten sind schon bei `lb21 / evt1` am globalen Cap oder
      an ihren eigenen Teacher-Bounds gesaettigt

- [paper_dispatch_comparison_20260403_131344](/c:/Users/Philipp%20Thunshirn/Desktop/PhD/Python%20model/Master/Optimization/run/results/Vienna/gold/paper_dispatch_comparison_20260403_131344)
  - weiterer erweiterter Sensitivitaetsbundle fuer den konstanten Thermflex-Isolationsfall
  - neue explizite Zusatzfaelle:
    - `lb21p0_dur24_evt1`
    - `lb21p0_dur24_evt24`
  - wichtige Befunde:
    - `lb21p0_dur24_evt1` und `lb21p0_dur24_evt24` sind im aktuellen 24h-Slice identisch
    - im Unterschied zum Upper-only-Proxy bringt `dur24` bei erlaubtem Abkuehlen auf `21.0 C`
      noch zusaetzlichen Systemnutzen gegenueber `dur8`
    - `non_residential_2000_2014` bleibt auch bei `dur24` komplett inaktiv und hat
      im gesamten Slice `q_heat_ref = 0`

- [paper_comparison](/c:/Users/Philipp%20Thunshirn/Desktop/PhD/Python%20model/Master/Optimization/run/results/Vienna/gold/biobj_gold_candidates_20260403_093146/paper_comparison)
  - erweitert den Drei-Fall-Papervergleich um:
    - `biobj_cost_end`
    - `biobj_co2_end`
    - `biobj_mid_tradeoff`
  - enthaelt:
    - `paper_dispatch_comparison.csv`
    - `paper_dispatch_comparison.md`
    - `paper_dispatch_comparison.png`
    - `selected_runs.json`

Aktueller Zweistufen-Endpunktbefund:

- [two_stage_endpoint_summary.json](/c:/Users/Philipp%20Thunshirn/Desktop/PhD/Python%20model/Master/Optimization/run/results/Vienna/gold/biobj_gold_candidates_20260403_093146/20260403_093214_biobj_co2_end_gold_day_ahead/20260403_095255_biobj_co2_end_gold_two_stage/two_stage_endpoint_summary.json)
  - `biobj_co2_end` bleibt in `milp_two_stage` infeasible

- [two_stage_endpoint_summary.json](/c:/Users/Philipp%20Thunshirn/Desktop/PhD/Python%20model/Master/Optimization/run/results/Vienna/gold/biobj_gold_candidates_20260403_093146/20260403_093239_biobj_mid_tradeoff_gold_day_ahead/20260403_095255_biobj_mid_tradeoff_gold_two_stage/two_stage_endpoint_summary.json)
  - `biobj_mid_tradeoff` bleibt in `milp_two_stage` infeasible

- Einordnung:
  - der publish-faehige Hauptpfad bleibt aktuell:
    - Surrogat-Suche
    - Gold-Validierung mit `milp_day_ahead`
  - `milp_two_stage` bleibt harter Endpunkt-Check und aktuell noch nicht robust fuer diese biobjektiven Kandidaten

- [dh_thermflex_run_20260403_140316](/c:/Users/Philipp%20Thunshirn/Desktop/PhD/Python%20model/Master/Optimization/run/results/Vienna/gold/dh_thermflex_run_20260403_140316)
  - kuratierter Ergebnisbundle fuer den aktuellen DH-Thermflex-Analyseblock
  - enthaelt:
    - `paper_core/`
    - `nonres_2000_2014_debug/`
    - `representative_days/`
    - `teacher_day_plots/`
    - `README.md`
    - `manifest.json`
  - Zweck:
    - die verteilten Einzelartefakte des aktuellen Blocks an einer Stelle buendeln
    - schnell sichtbar machen, was fuer Paper-/Modellentscheidungen schon belastbar vorliegt

- [constant_thermflex_representative_day_summary_20260403](/c:/Users/Philipp%20Thunshirn/Desktop/PhD/Python%20model/Master/Optimization/run/results/Vienna/gold/constant_thermflex_representative_day_summary_20260403)
  - Vergleich des konstanten Thermflex-Isolationsfalls ueber 5 explizit selektierte Representative Days
  - enthaelt:
    - `representative_day_case_summary.csv`
    - `representative_day_case_summary.json`
    - `representative_day_case_summary.md`
    - `representative_day_case_summary.png`
    - `run_manifest.json`
    - `selected_representative_days.json`
  - wichtige Einordnung:
    - es gibt keine ueber alle Tage dominante globale Thermflex-Policy
    - `lb21p0_dur24_evt1` ist oft stark auf Preis-/typischen/Schultertagen
    - `constant_no_thermflex` bleibt auf Peak-Heat- und Sunny-Winter-Tagen bei Cost/CO2 teilweise vorne
