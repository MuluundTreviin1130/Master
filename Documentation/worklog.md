# Worklog

## 2026-05-10

### Kritischen Settings-/Learning-Validation-Importcrash behoben

- Daily Bug-Inspection der juengsten Commits durchgefuehrt.
- Kritischer Befund:
  - `Settings/get_settings.py` und `Settings/settings_model.py` referenzierten `Settings.validation.holdout`, der neue `Settings/validation`-Layer fehlte aber nach dem Repo-Umzug.
  - `Learning/training/train_surrogate.py` referenzierte `Learning.validation.evaluate_gate`, der neue `Learning/validation`-Layer fehlte ebenfalls.
- Fix:
  - `Settings/validation/holdout.py` mit dem Holdout-Settings-Vertrag und expliziten Learning-Runtime-Override-Feldern ergaenzt.
  - `Learning/validation/evaluate_gate.py` als fail-closed Holdout-Gate fuer native Surrogate-Trainings ergaenzt.
  - fokussierte Regressionstests unter `tests/test_validation_modules.py` hinzugefuegt.

## 2026-04-24

### Layer-2 Building-Surrogate-Zielbild festgezogen

- Aktuellen Repo-Schnitt fuer den geplanten ROM-Nachfolger inventarisiert:
  - `EnergyPlus`-Teacher liegt unter `Technical_model/technologies/buildings/calibration/teachers/energyplus.py`
  - aktueller Runtime-Gebaeudepfad liegt unter `runtime_space_heat.py`, `thermal_building_state.py` und `thermal_flex_controller.py`
  - bestehender `Learning/`-Layer soll fuer Dataset-/Artefakt-/Validation-/Retrain-Logik wiederverwendet werden
- Neues Planning-Dokument angelegt:
  - `Documentation/Planning/building_surrogate_layer2_design.md`
- Zielbild:
  - `EnergyPlus` bleibt Teacher / Truth
  - `Learning/` trainiert und verwaltet den learned building-response surrogate
  - der neue Layer 2 ersetzt langfristig das Reduced-Order-Runtime-Modell
  - bestehender Dispatch-/KPI-Surrogatlayer bleibt separat
- EnergyPlus-Teacher exportiert bereits zentrale stundenweise Signale fuer V1:
  - Innen-/Aussentemperatur
  - Heizlast
  - Fenster-/Solar-Gewinne
  - Infiltration/Ventilation
  - Outdoor-Air-Heat-Balance
  - interne Gains, Setpoints und Wetterfenster
- Naechster Umsetzungsschritt:
  - standardisierten hourly transition dataset builder vorbereiten
  - harte Validierung der Pflichtspalten einbauen
  - danach erstes Multi-Target-Building-Surrogat im bestehenden Learning-Layer trainieren und ueber 24/48h-Rollouts pruefen

## 2026-04-19

### `upper_only dur24 evt24`-Screen und kompakter Trade-off-Tabellenschnitt

- Neuer sauberer `upper_only`-Paper-Override mit gelockerter Zeit-/Eventgrenze angelegt:
  - `vienna_ref2023_dh_baseline_constant_thermflex_lb22p5_dur24_evt24_upper_only_paper_day_ahead.json`
- Vollstaendigen Heizperioden-Screen fuer diesen neuen `dur24 evt24`-Fall gerechnet:
  - `Optimization/run/results/Vienna/gold/daily_thermflex_screen_dur24_20260422_151407/`
- Befund:
  - die Hauptfamilie der Top-Savings-Tage bleibt gegenueber `dur1 evt1` weitgehend stabil
  - `dur24` aendert einige Rebound-/Peakdetails, ordnet die besten Tage aber nicht komplett neu
- Fuer den Trade-off-Seitenstrang eine kompaktere Tabelle statt weiterer Plot-Ueberladung angelegt:
  - `Documentation/Papers/thermflex_paper/tables/table_09_tradeoff_day_summary_upper_only_dur24.md`
- Der Trade-off-Schnitt nutzt jetzt bewusst:
  - `cost change`
  - `CO2 change`
  - `boiler energy change`
  - `boiler peak change`
  - `rebound / shifted`
- Hintergrund dafuer:
  - `rebound / shifted` ist mechanistisch wichtig, aber im Balkenplot schwer lesbar
  - die Tagesmechanik (`wann preheat`, `T_in`, kohortenspezifischer Shift) bleibt besser in den separaten Mechanismus-/Innenraumtemperaturtabellen aufgehoben
- Anschliessend Thermflex-Aktivierungsbug gefunden und behoben:
  - vorher konnte `q_heat` von `q_ref` abweichen, obwohl `therm_flex_active = 0`
  - dadurch griffen Dauer-/Eventgrenzen nicht sauber und `preheat_extra` blieb trotz realer Verschiebung bei `0`
  - gefixt in `milp_day_ahead` und `milp_two_stage`: ohne aktive Flex gilt nun effektiv `q_heat == q_ref`; Abweichungen werden durch `therm_flex_active` gegatet
  - Smoke auf `2023-03-04` nach Fix:
    - `active_member_hours_total = 75`
    - `preheat_extra ~= 2.10 GWh`
    - `max T_in - setpoint ~= 2.59 K`
    - inactive Stunden haben keine relevante `q_heat - q_ref`-Abweichung mehr
- Betroffene Tabellen post-fix nachgezogen:
  - `table_06_indoor_temperature_response_upper_only.md`
  - `table_09_tradeoff_day_summary_upper_only_dur24.md`
- `table_05` um flaechenbezogene Shift-Intensitaeten (`Wh/m2`) ergaenzt; die zugrunde liegende Legacy-Sensitivitaet sollte vor finalen Paperzahlen ebenfalls post-fix neu gerechnet werden.
- Paper-Ergebnisworkflow in `Documentation/Planning/TODO.md` explizit als zweistufiger Prozess festgehalten: zuerst Tabellen-/Figurenstruktur stabilisieren, finale Werte erst nach konsistentem Full-Rerun aller Paper-Cases einfrieren.
- `table_05` zusaetzlich als Legacy-/Strukturwert markiert und die auffaellige Nicht-Monotonie `1975-1990 > 1990-2000` als noch nicht final interpretierbaren Pruefpunkt dokumentiert.
- Kohortenspezifische Tagesgrafik fuer representative days als Figure-TODO ergaenzt: stundenweise `q_heat - q_ref`, `T_in`, Komfortgrenze und optional Solar-gains-Proxy, damit Preheat, Speicherwirkung und KPI-Aenderungen zusammen gelesen werden koennen.
- Table-05-Sensitivity-Replay mit aktuellem Thermflex-Aktivierungsfix ausgefuehrt:
  - Output: `Optimization/run/results/Vienna/gold/paper_dispatch_comparison_20260423_120713`
  - Ergebnis: die fruehere Nicht-Monotonie war ein Artefakt aus Legacy-Run/Normalisierung/Diagnostik.
  - Post-fix zeigt der `lb21`-Duration-Case eine klare Heizlast-/Cutback-Reihung (`pre1975 > 1975-1990 > 1990-2000 > 2000-2014` in `Wh/m2`).
  - Interpretation korrigiert: diese Tabelle misst nicht moderne Speicherpersistenz, sondern lower-bound/cutback-Potenzial je DH-angeschlossener Flaeche.
  - `table_05_residential_cohort_duration_sensitivity.md` auf post-fix Replay-Werte und DH-connected-GFA-Normalisierung umgestellt.
- Table 05 danach auf die eigentliche Paperstory zurueckgeschnitten:
  - Haupttabelle zeigt nun die Gebaeudepersistenz aus den aktiven ROM-Parametern (`C_eff`, `tau`, heat-state half-life, retained state nach 4/8/24 h).
  - Damit ist die fachlich erwartete Reihung sichtbar: moderne Kohorten halten einen gleichen thermischen Ladezustand laenger.
  - Der post-fix Dispatch-Duration-Befund bleibt als Mechanik-/Appendix-Kandidat, aber nicht als Persistenztabelle.
- Table 05 erneut als kombinierte Ergebnis-/Mechanismustabelle erweitert:
  - bestehende Persistenzspalten bleiben erhalten
  - zusaetzlich realisierte Kohortenbeitraege fuer den Top-Savings-Tag `2023-11-04` im aktiven `upper_only dur24 evt24`-Pfad:
    - shifted heat je DH-connected m2
    - release/cutback je DH-connected m2
    - net heat change
    - release/shifted ratio
    - aktive Stunden
    - max. `T_in` ueber Setpoint
  - Kosten/CO2 bleiben bewusst als Systemkontext in der Tabellen-Note, nicht als kohortenspezifische KPIs.
- Table 05 um einen gezielten `upper_only`-Duration-Vergleich auf `2023-11-04` erweitert:
  - gezielte Gold-Evaluierungen fuer `max_flex_duration_h = max_flex_events_per_day = 1, 4, 12, 24`
  - zusaetzliche Spalten `Shifted 1 h`, `Shifted 4 h`, `Shifted 12 h`, `Shifted 24 h`
  - Befund: die modernste Kohorte zeigt im 4h-Fenster die staerkste flaechenbezogene Aufnahme, dominiert aber nicht die 12/24h-Systemnutzung, weil ihre Referenzheizlast und damit die nutzbare Release-Menge kleiner ist.
- Table 05 methodisch erneut geschaerft:
  - die `1/4/12/24 h`-Duration-Spalten sind jetzt nicht mehr realisierte Optimierer-`shifted`-Werte, sondern vergleichbare `1 K`-Speicherpuls-Retention (`C_eff * exp(-h/tau)`)
  - damit passt die fachliche Erwartung: alte Kohorten halten kurzfristig mehr Energie, moderne Kohorten behalten nach 24 h mehr thermischen Zustand
  - realisierte `upper_only`-Dispatchwerte bleiben nur als 24h-Systemkontextspalten (`shifted`, `release`, active hours, max T_in)
- Duration-spezifische Kohortenfigur als naechsten Paper-Plot in TODO ergaenzt:
  - representative days x `max_flex_duration_h = 1/4/12/24` x Residential-Kohorten
  - optimiererabhaengige Metriken: shifted, release/cutback, net heat, active hours, max `T_in`
  - System-KPIs nur als Panelkontext, nicht kohortenspezifisch
- Figure-Spezifikation nachgeschaerft:
  - `active hours` nicht in die Hauptgrafik aufnehmen
  - Paneltitel nur mit Tag-/Duration-Bezeichnung, nicht mit KPIs
  - System-KPIs separat in einer Referenztag-Tabelle berichten
  - kohortenspezifischen `T_in - setpoint`-Tagesverlauf als eigene Figure-Komponente vorsehen
- Neue duration-spezifische Kohortenmechanismus-Figure umgesetzt:
  - Builder: `Documentation/Papers/thermflex_paper/figures/build_fig_05_cohort_duration_mechanism.py`
  - Output: `Documentation/Papers/thermflex_paper/figures/fig_05_cohort_duration_mechanism.png`
  - Daten-Export: `Documentation/Papers/thermflex_paper/figures/fig_05_cohort_duration_mechanism_data.csv`
  - Inhalt:
    - 8 kuratierte Referenztage
    - `max_flex_duration_h = 1/4/12/24`
    - oben je Tag stundenweises `q_heat - q_ref [Wh/m2h]` als gruppierte Balken
    - unten je Tag kohortenspezifisches `T_in - setpoint [K]`
  - Die initiale 10-Tage-Datenbasis bleibt in der CSV nutzbar; die aktive Figure filtert auf 8 Tage.
- Figure 05 vereinfacht:
  - Shift-/Release-KPIs sind jetzt Tagessummen je Kohorte und Duration statt stundenweise Balken
  - `T_in - setpoint` bleibt als Tagesverlauf, aber nur fuer `1/4/12 h`
  - neue Version wurde aus der bestehenden CSV gerendert, ohne weitere MILP-Laeufe
- Neue entkoppelte Tagessummen-Figure erzeugt:
  - Builder: `Documentation/Papers/thermflex_paper/figures/build_fig_06_cohort_duration_daily_sums.py`
  - Output: `Documentation/Papers/thermflex_paper/figures/fig_06_cohort_duration_daily_sums.png`
  - Datenexport: `Documentation/Papers/thermflex_paper/figures/fig_06_cohort_duration_daily_sums.csv`
  - Inhalt: nur daily shifted/release `Wh/m2` je Referenztag, Duration und Residential-Kohorte
  - Temperaturverlaeufe bleiben als separater Figure-Pfad erhalten.
- Figure 06 auf drei Duration-Stufen reduziert (`1/4/12 h`) und neu gerendert.
- Figure 06 visuell nachgeschaerft:
  - Duration-Kontrast ueber Alpha/Saettigung erhoeht (`12 h` am staerksten gesaettigt)
  - y-Achse asymmetrisch auf `-100` bis `+150 Wh/m2` begrenzt, damit positive Preheat-Spitzen sichtbar bleiben und negative Release-Werte nicht ueberdehnt werden
  - positive und negative Balken verwenden nun dieselbe Alpha-/Saettigungslogik je Duration
  - Interpretation fuer Late-season geprueft: `2023-04-04` zeigt netto positive Waermezufuhr ohne Release, passt daher zu den zuvor beobachteten schwachen/teilweise gegenlaeufigen System-KPIs.
- Figure 06 wieder auf fuenf Duration-Stufen erweitert (`1/4/8/12/24 h`):
  - fehlende `8 h`-Rohdaten fuer die 8 kuratierten Tage gezielt nachgerechnet und an `fig_05_cohort_duration_mechanism_data.csv` angehaengt
  - `fig_06_cohort_duration_daily_sums.png` und `fig_06_cohort_duration_daily_sums.csv` neu gerendert
  - Semantik festgehalten: die Duration ist eine Obergrenze fuer erlaubte Abweichungsstunden; der Optimierer entscheidet die tatsaechliche Nutzung innerhalb dieser Grenze.
- Figure 06 Lesbarkeit verbessert:
  - positive Balken bleiben volle Kohortenfarbe fuer `shifted / preheat`
  - negative Balken (`release / cutback`) sind nun heller und schraffiert
  - Legende um die Richtung der Balken ergaenzt
- Paper-Artefakte aufgeraeumt:
  - folgende aktive Figure-PNGs nach `Documentation/Papers/thermflex_paper/figures/old/` verschoben:
    - `fig_00_teacher_residential_overlay_comparison.png`
    - `fig_01_use_case_shift_boiler.png`
    - `fig_02_representative_upper_only_shift.png`
    - `fig_04_tradeoff_day_map.png`
  - `fig_05_cohort_duration_mechanism.png`, zugehoerige CSV und Builder entfernt, weil `fig_06` die entkoppelte Nachfolgegrafik ist
  - `table_01_scenario_overview.md` nach `Documentation/Papers/thermflex_paper/tables/old/` verschoben
  - `Documentation/Papers/thermflex_paper/tables/old/README.md` angelegt
- Neue Source-Notiz zu Guelpa/Verda und Demand Response angelegt:
  - `Documentation/Sources/guelpa_demand_response_notes.md`

### Thermflex-2x2 fuer Representative Days auf `upper_only`, `dur1`

- Paper-Figure-Layer um eine schlanke 2x2-Shift-Figur fuer vier bereits vorhandene Representative Days erweitert:
  - `winter_peak_heat_day`
  - `winter_price_spike_day`
  - `winter_sunny_heat_day`
  - `shoulder_typical_day`
- Neue Figure:
  - `Documentation/Papers/thermflex_paper/figures/fig_02_representative_upper_only_shift.png`
- Neuer Builder:
  - `Documentation/Papers/thermflex_paper/figures/build_fig_02_representative_upper_only_shift.py`
- Darstellung bewusst reduziert:
  - Referenz in grau
  - `upper_only`-Fall in Farbe
  - nur `district_space_heat_demand_ref` vs. `district_space_heat_demand`
  - kein Gas-Peak-Boiler-Panel mehr in dieser Figur
- Figure-Story danach gezielt auf `3 aktive + 1 praktisch inaktiven` Upper-only-Fall umgeschnitten:
  - kalter Peak-Tag als Kontrast ohne sichtbaren intra-day shift
  - danach auf `3 aktive + 1 praktisch inaktiven` Fall
  - spaeter auf sechs Panels erweitert, um zusaetzliche sichtbare Februar-, November- und Fruehjahrs-Faelle mitzunehmen
  - fuer die Plotlogik wird ein `25 h`-Solve-Horizont gerechnet und die ersten `24 h` gezeigt, damit der aktuelle Horizon-Endeffekt nicht als Hauptmechanismus in der Figur landet
  - aktive Plotgroesse jetzt `dh_total_demand` statt nur `district_space_heat_demand_ref`
  - Rohkurven wieder entfernt; aktive Darstellung ist jetzt die geglaettete `2 h`-Paperkurve
- Im Override-Layer den bisher fehlenden expliziten Fall fuer `upper_only` mit `duration = 1 h` als SSOT-Datei angelegt:
  - `Optimization/validation/model_validation/overrides/thermflex/vienna_ref2023_dh_baseline_constant_thermflex_lb22p5_dur1_evt1_upper_only_paper_day_ahead.json`

## 2026-04-01

### Dispatch-/Thermflex-Export-SSOT

- Bestehenden `Settings/reporting`-Layer erweitert statt parallele Exportstruktur einzuziehen.
- Neue Reporting-SSOT fuer operative Exporte:
  - `dispatch_kpis.json`
  - `dispatch_kpis.csv`
  - optional `thermflex_hourly.csv`
- Dateinamen, KPI-Liste und Normierungsfenster liegen jetzt im Reporting-Settings-Layer.

### Operative KPI-Exporte

- Gold-Truth-Pfad schreibt Dispatch-/Thermflex-KPIs jetzt ohne Re-Evaluierung direkt waehrend der Gold-Evaluation.
- Export basiert auf bestehenden `raw_results["dispatch_diagnostics"]` und den bereits vorhandenen Solver-Diagnostics.
- Summary greift den neuen Export auf und fuegt einen kompakten Dispatch-/Thermflex-Block an.

### Offene Anschlussarbeiten

- Surrogat-Layer auf `xgb` und den Wiener DH-/Thermflex-Fall umstellen.
- Validation-Layer fuer die neuen Dispatch-/Thermflex-Ziele aufraeumen.
- Vergleichsfaelle `baseline_constant_no_thermflex`, `day_night_no_thermflex`, `day_night_thermflex` als stabile SSOT-Runs schneiden.

### Vergleichsfaelle als SSOT-Runs

- Drei stabile Wiener DH-/Thermflex-Run-Cases als eigene Override-Dateien angelegt:
  - `baseline_constant_no_thermflex`
  - `day_night_no_thermflex`
  - `day_night_thermflex`
- `run_optimization.py` zeigt im Click-Default jetzt auf den standardisierten `day_night_thermflex`-Fall.
- Legacy-Override bleibt bewusst im Repo, um bestehende Pfade nicht zu brechen.

### Surrogat-Vorbereitung

- Default-Targets im Surrogat-Layer auf den Wiener DH-/Thermflex-/CO2-Fall vorbereitet.
- Feature-Schnitt um Policy-/Control-Mode-Informationen erweitert:
  - `reference_control_mode`
  - `control_mode`
  - Setpoints
  - untere Grenzen
  - Thermflex-Dauer/Event-Limits
- Gold schreibt dafuer jetzt auch scalar Thermflex-/CO2-Diagnostics in die Truth-Flow-Ebene, sodass diese als Surrogat-Targets verfuegbar sind.
- `xgboost` ist in der aktuellen lokalen `.venv` noch nicht installiert; deshalb wurde der Surrogat-Default noch nicht hart auf `xgb` umgestellt, um keinen stillen Fallback oder halb fertigen Zustand einzuziehen.

### Surrogat-Validierung und Artefakte

- Validation-Gate von alten `core_energy`-Defaults auf den aktuellen DH-/Thermflex-/CO2-Fall erweitert.
- Primare Surrogat-Artefakte sind jetzt modellagnostisch als `surrogate_bundle.*` geschnitten.
- Legacy-Dateinamen `surrogate_rf.*` werden parallel weitergeschrieben bzw. weiter aufgeloest, damit bestehende Registry-/Bootstrap-/Run-Pfade nicht brechen.
- Validation-Spiegelung laeuft jetzt parallel nach:
  - `Optimization/run/validation/...`
  - `Optimization/run/validation_old/...`
- `xgboost` ist kein Bestandteil von `scikit-learn`; fuer den spaeteren Wechsel auf `xgb` muss das Paket explizit in der `.venv` installiert werden.

### Surrogat-Trainingspfade vereinheitlicht

- Der aeltere `auto_train_surrogate(...)`-Pfad trainiert jetzt ebenfalls modellagnostisch ueber die zentrale Modellfabrik statt implizit immer nur `RandomForest`.
- Der RF-spezifische Helper bleibt als Legacy-Wrapper bestehen, damit keine bestehenden Aufrufer brechen.
- Der Uncertainty-/Feasibility-Pfad ist weiterhin bewusst nur fuer Ensemble-Modelle mit `estimators_` freigeschaltet; fuer `xgb` muss diese Logik noch separat entschieden oder erweitert werden.

### XGBoost-Installationsstand

- `xgboost` ist jetzt in der lokalen `.venv` installiert.
- SSOT-Entscheidung jetzt explizit gezogen:
  - globaler Surrogat-Default = `xgb`
  - globaler Feasibility-Default = `gold_recheck`
- Damit ist der Standardpfad fuer den Surrogatbetrieb konsistent und haengt nicht mehr am alten `hybrid`-Unsicherheitspfad.
- Ein eigener `xgb`-Unsicherheitspfad bleibt spaeter moeglich, ist aber nicht mehr Blocker fuer den Standardbetrieb.

### XGBoost-Defaults

- In der Modellfabrik liegen jetzt sinnvolle `xgb`-Basisdefaults:
  - `objective = reg:squarederror`
  - `tree_method = hist`
  - `n_estimators = 300`
  - `max_depth = 6`
  - `learning_rate = 0.05`
  - `subsample = 0.8`
  - `colsample_bytree = 0.8`

### DH-/Thermflex-Surrogat-Run-Cases

- Drei kleine `surrogate_mini`-Faelle fuer die Vergleichsmodi angelegt:
  - `baseline_constant_no_thermflex`
  - `day_night_no_thermflex`
  - `day_night_thermflex`
- Zusaetzlich ein erster schwererer `day_night_thermflex_surrogate_ready`-Fall mit `milp_two_stage`.
- `train_surrogate.py` zeigt ohne CLI-Argumente jetzt auf den standardisierten `day_night_thermflex_surrogate_mini`-Fall.
- Kurzer Smoke des neuen Trainings-Entrypoints zeigt den richtigen Laufpfad:
  - Sampling startet
  - Teacher-Eval startet
  - `integrated_energy_system` wird aufgebaut
  - `dispatch.milp_day_ahead` erreicht den Solver-Aufruf

### Erster sinnvoller Trainingsfall

- Neuer `day_night_thermflex_surrogate_train`-Fall angelegt.
- Schnitt:
  - `milp_day_ahead`
  - `24h`
  - `lhs n=16`
  - `xgb`
  - `gold_recheck`
- Ziel dieses Falls:
  - erster wirklich interpretierbarer Holdout-Lauf
  - ohne den sehr schweren `milp_two_stage`-Teacher sofort zum Standard zu machen
- `train_surrogate.py` zeigt im Click-Default jetzt auf diesen Trainingsfall.
- Trainingslauf erfolgreich durch:
  - `lhs n=16`
  - `milp_day_ahead`
  - Laufzeit ca. `10.4 min`
- Ergebnis:
  - erster brauchbarer Holdout statt reinem Smoke-Test
  - `R2 (median) = 0.796` ueber den `F`-Block
  - `dispatch_cost_eur` Holdout `R2 = 0.856`
- Ein erster `surrogate_ready`-Versuch mit `milp_two_stage` wurde ebenfalls gestartet, war aber fuer einen fruehen Standardfall noch zu teuer:
  - nach ca. `1 h` erst `3/16` Teacher-Punkte
  - deshalb bleibt `surrogate_ready` vorerst Ausbaupfad, nicht Click-Default

### Vergleichsmodi auf Trainingsniveau angehoben

- Zusaetzlich zu `day_night_thermflex_surrogate_train` wurden auch zwei analoge `surrogate_train`-Faelle angelegt:
  - `baseline_constant_no_thermflex_surrogate_train`
  - `day_night_no_thermflex_surrogate_train`
- Damit liegen die drei Paper-/Vergleichsmodi jetzt nicht mehr nur als Mini-Smokes, sondern auch als sinnvoll skalierte Trainingsfaelle vor.

### Export-/Truth-Pfad ohne stille Fallbacks gehaertet

- `dispatch_kpis`- und `summary`-Export lesen Reporting-Dateinamen jetzt nur noch aus dem Settings-SSOT.
- Fehlende Pflichtwerte in `dispatch_diagnostics`, `objective_terms`, Thermflex-Serien oder `truth_dataset.csv` werden nicht mehr implizit als `0` geschrieben.
- Explizite `0` bleiben nur dort zulaessig, wo Features oder Technologien laut Settings deaktiviert sind.
- `dispatch_cost`-Breakdown kann jetzt im strikten Modus fehlende Objective-Terme hart melden.

### Open-Meteo-Wetterarchiv fuer Wien im Data-Layer

- Offenen Downloader fuer das Wiener Open-Meteo-Archiv angelegt:
  - `Data/profiles/Vienna/weather/fetch_openmeteo_archive_vienna.py`
- Neuer repo-lokaler SSOT-Pfad:
  - `Data/profiles/Vienna/weather/openmeteo_hourly_archive_2016_2025.csv`
- Schnitt:
  - `2016-01-01` bis `2025-12-31`
  - stuenliche Open-Meteo-Archivdaten
  - Temperatur / Feuchte / Wolken / Wind / Niederschlag / Strahlung
- Der Downloader arbeitet fail-fast:
  - keine stillen Fallbacks bei fehlenden Variablen
  - harte Checks fuer Zeilenanzahl, Zeitstempel und Chunk-Metadaten
- Jahresweise Chunk-Downloads und lokaler Cache verhindern, dass API-Limits den gesamten Lauf unbrauchbar machen.

### Reproduzierbare Jahresauswahl fuer die erste Building-Kalibrierung

- Aus dem Open-Meteo-Wetterarchiv wurde ein eigener Auswahlschritt fuer repraesentative Jahre eingefuehrt:
  - `Data/profiles/Vienna/weather/select_representative_openmeteo_years.py`
- Outputs:
  - `openmeteo_year_summary_2016_2025.csv`
  - `openmeteo_representative_years_2016_2025.json`
- Erste Auswahl fuer Wien:
  - `average_year = 2020`
  - `cold_year = 2021`
  - `mild_year = 2024`
- Der Schnitt ist bewusst reproduzierbar und fail-fast:
  - `cold_year`/`mild_year` ueber `HDD18`
  - `average_year` ueber minimale z-standardisierte Distanz auf Temperatur-/Strahlungs-/Wintermetriken

### Pseudo-EPW-V1 fuer die ersten Wien-Kalibrierungsjahre

- Neuer Calibration-SSOT:
  - `Settings/technical/building_calibration.py`
- Neuer Builder im Gebaeude-Kalibrierungspfad:
  - `Technical_model/technologies/buildings/calibration/weather/pseudo_epw.py`
- Gebaute Dateien:
  - `average_year = 2020`
  - `cold_year = 2021`
  - `mild_year = 2024`
- Schnitt:
  - Open-Meteo-Archivdaten als eigentliche Wetterwahrheit
  - vorhandene Wien-EPW-Datei nur als Header-/Formatanker
  - lokale Standardzeit `UTC+1` ohne DST fuer den EPW-Output
  - horizontale Himmels-Langwellenstrahlung ueber explizites `Clark-Allen`-Modell
  - einige nicht belastbar belegte Felder bleiben bewusst als EPW-Missing-Codes statt still erfunden zu werden

### EnergyPlus-Mini-Smoke vorbereitet

- Neuer Teacher-/Smoke-Pfad:
  - `Technical_model/technologies/buildings/calibration/teachers/energyplus.py`
  - `Technical_model/technologies/buildings/calibration/run_energyplus_smoke.py`
- Der Runner ist bewusst fail-fast:
  - sucht `energyplus.exe` zuerst ueber explizites Setting
  - dann ueber `PATH` / typische `Program Files`-Orte
  - ohne Fund harter Fehler statt stiller Degradation
- Aktueller Stand:
  - Mini-Smoke-Runner ist angeschlossen
  - offizieller lokaler `EnergyPlus 26.1.0`-Build wurde als Workspace-Vendor unter
    `Technical_model/technologies/buildings/calibration/_vendor/` abgelegt
  - `Settings/technical/building_calibration.py` zeigt jetzt explizit auf diesen Build
  - Mini-Smoke erfolgreich fuer:
  - `average_year = 2020`
  - `cold_year = 2021`
  - `mild_year = 2024`
  - damit ist der `pseudo_epw`-Pfad jetzt nicht nur formal gebaut, sondern durch einen echten
    EnergyPlus-Lauf validiert

### Teacher-Setup und Experimentbibliothek fuer die Offline-Kalibrierung

- Neuer Vorbau fuer den naechsten Kalibrierungsschritt:
  - `Technical_model/technologies/buildings/calibration/schemas.py`
  - `Technical_model/technologies/buildings/calibration/from_repo.py`
  - `Technical_model/technologies/buildings/calibration/experiments.py`
  - `Technical_model/technologies/buildings/calibration/run_prepare_teacher_setup.py`
- `Settings/technical/building_calibration.py` traegt jetzt zusaetzlich:
  - gemeinsames `usage_profile` als explizite SSOT-Abhaengigkeit
  - erforderliche Usage-Spalten
  - kleine erste Experimentbibliothek fuer `reference`, `free_float`, `preheat`, `cutback`, `recovery`
- Neuer Setup-Export erfolgreich erzeugt:
  - `Data/profiles/Vienna/weather/calibration_setup/teacher_inputs_v1.json`
  - `Data/profiles/Vienna/weather/calibration_setup/experiment_library_v1.json`
- Schnitt:
  - Teacher-Inputs werden aus bestehendem Wien-`building_stock` und `thermal_archetypes` abgeleitet
  - dieselbe Runtime-Gebaeudesemantik wird weiterverwendet, statt eine zweite Gebaeudelogik einzufuehren
  - keine stillen Fallbacks bei:
    - fehlender `usage_profile`-Datei oder Sheet
    - fehlenden Pflichtspalten
    - fehlenden reprasentativen Jahren
    - fehlenden `pseudo_epw`-Dateien
    - doppelten `cohort_id`s

### Erster echter EnergyPlus-Teacher-Pilot

- Neuer Pilot-Runner:
  - `Technical_model/technologies/buildings/calibration/run_energyplus_teacher_pilot.py`
- `teachers/energyplus.py` kann jetzt einen echten kohorten-/experimentbasierten Teacher-Run fahren:
  - liest `teacher_inputs_v1.json`
  - liest `experiment_library_v1.json`
  - baut ein vereinfachtes, normiertes Ein-Zonen-Gebaeude mit `IdealLoads`
  - nutzt explizite Jahres-Schedules aus dem gemeinsamen `usage_profile`
  - schreibt `teacher_hourly.csv` und `teacher.meta.json`
- Wichtiger Schnitt:
  - die Bibliothek umfasst weiterhin 6 Standardexperimente
  - der produktive Pilot-Default laeuft aber bewusst nur **einen** kleinen Fall:
    - `cohort_id = residential_1975_1990`
    - `experiment_id = winter_reference_week`
- Erster echter Pilot erfolgreich durchgelaufen:
  - Output unter
    `Technical_model/technologies/buildings/calibration/_teacher_runs/residential_1975_1990/winter_reference_week/`
- Fachlicher Befund aus dem ersten Pilot:
  - der aktuelle Winter-Referenzfall ist deutlich **kuehlungsdominiert**
  - also erst die Teacher-Annahmen fuer:
    - interne Gewinne
    - Setpoint-Schnitt
    - einfache Geometrie / Solargewinne
    sauber plausibilisieren, bevor der Reduced-Order-Fit in Serie geht

### Teacher-Schedule-Skalierung repariert und Winterpilot plausibilisiert

- In `teachers/energyplus.py` war die erste Schedule-Uebersetzung fuer den Teacher fachlich inkonsistent:
  - `internal_gains_w_m2`
  - `infiltration_ach`
  - `ventilation_ach`
  wurden als bereits absolute Zeitreihen exportiert, in `EnergyPlus` aber zusaetzlich als `Fraction`-Schedules interpretiert.
- Fix:
  - `teacher_schedules.csv` enthaelt jetzt **beides**:
    - die absoluten Debug-/Fachgroessen
    - explizit normierte `*_fraction`-Spalten fuer `EnergyPlus`
  - der IDF-Pfad nutzt fuer `ElectricEquipment`, `ZoneInfiltration` und `ZoneVentilation` nur noch diese normierten `Fraction`-Schedules
  - fehlende oder ungueltige normierte Schedule-Spalten brechen weiterhin fail-fast
- Derselbe Pilot wurde danach erneut gefahren:
  - `cohort_id = residential_1975_1990`
  - `experiment_id = winter_reference_week`
- Neuer Befund:
  - der Winter-Referenzfall ist jetzt **heizdominiert** statt kuehlungsdominiert
  - Mittelwert `T_zone ~= 21.03 C`
  - `161/168` Stunden mit Heizleistung
  - keine realen Kuehlstunden mehr
- Damit ist die urspruengliche Ueberhitzung nicht mehr dem Wetter, sondern der frueheren Teacher-Schedule-Skalierung zuzuordnen.
- Offener naechster Punkt bleibt damit enger geschnitten:
  - Geometrie-/Solarvereinfachung und Referenzannahmen weiter plausibilisieren
  - erst danach den Reduced-Order-Fit fuer `UA`, `C_th`, Rebound und Recovery seriell aufsetzen

### Plausibilitaets-Export fuer den Teacher-Pilot eingebaut

- Der Teacher-Run schreibt jetzt zusaetzlich:
  - `teacher_plausibility_hourly.csv`
  - `teacher_plausibility_summary.json`
  - `teacher_plausibility_overview.png`
- Inhalt des Plausibilitaets-Exports:
  - exakte Teacher-/EnergyPlus-Groessen:
    - `zone_mean_air_temperature_c`
    - `site_outdoor_air_drybulb_c`
    - `zone_total_heating_rate_w`
    - `zone_total_cooling_rate_w`
  - explizit als solche markierte Approximationen / Treiber:
    - `internal_gains_total_w` aus dem Schedule
    - `approx_transmission_loss_seed_ua_w`
    - `approx_infiltration_loss_w`
    - `approx_ventilation_loss_w`
    - `epw_ghi_wh_m2`, `epw_dni_wh_m2`, `epw_dhi_wh_m2`
- Bewusster Schnitt:
  - Solar-/Luftwechselbeitraege werden fuer V1 **nicht** still als exakte `EnergyPlus`-Heat-Balance-Outputs behauptet
  - stattdessen werden die exakten Zustands-/Lastsignale aus dem Teacher mit transparenten Seed-/Weather-basierten Plausibilitaetsgroessen kombiniert
- Damit ist der naechste Schritt klarer:
  - Geometrie und Solaranahmen zuerst ueber diese Plausibilitaetsartefakte pruefen
  - exaktere Heat-Balance-Outputs aus `EnergyPlus` spaeter gezielt nachziehen, falls fuer die Kalibrierung wirklich noetig

### DH-Bus-Scaling aus dem Calibration-SSOT entfernt

- `teacher_dh_connected_share_for_bus_scaling = 0.4` wurde wieder aus `Settings/technical/building_calibration.py` entfernt.
- Neuer Schnitt:
  - DH-Bus-Scaling ist **kein** stiller Calibration-Default mehr
  - stattdessen optional explizit ueber `--dh-share` in:
    - `run_energyplus_teacher_pilot.py`
    - `run_energyplus_teacher_plausibility_batch.py`
- Aufloesungslogik fuer das Scaling:
  - zuerst `cohort.dh_connected_share_override`
  - dann explizites Laufargument `--dh-share`
  - dann `district_heating.share`, aber nur wenn dort wirklich `> 0`
  - sonst `unset` und die DH-Bus-Felder bleiben `null`
- Verifiziert:
  - ohne `--dh-share` schreibt der Teacher jetzt sauber `dh_connected_share_used = null`
  - mit `--dh-share 0.4` liefert der Batch wieder explizit busskalierte Vergleichswerte

### Exakte Fenster-/Solaroutputs in den Teacher gezogen

- `teachers/energyplus.py` schreibt jetzt zusaetzlich exakte Fenster-/Solar-Groessen aus `EnergyPlus`:
  - `Enclosure Windows Total Transmitted Solar Radiation Rate`
  - `Zone Windows Total Heat Gain Rate`
  - `Zone Windows Total Heat Loss Rate`
- Diese Groessen werden in:
  - `teacher_hourly.csv`
  - `teacher_plausibility_hourly.csv`
  - `teacher_plausibility_summary.json`
  weitergefuehrt.
- Der Plausibilitaetsplot zeigt jetzt explizit:
  - Innen-/Aussentemperatur und Setpoints
  - Heiz-/Kuehlleistung, interne Gewinne und Fenster-Solargewinne
  - Transmission, Infiltration, Ventilation und Fenster-Waermeverluste
- Fuer den Batch gibt es jetzt zusaetzlich:
  - `teacher_geometry_solar_review.csv`
  - `teacher_geometry_solar_review.json`
- Fachlicher Befund aus dem Review:
  - `window_solar_transmitted_kwh_per_window_m2` ist aktuell ueber die Kohorten fast identisch
  - das ist kein Exportfehler, sondern ein klares Signal, dass die Teacher-Solarwelt noch zu homogen ist:
    - gleiche vereinfachte Boxgeometrie
    - gleiche Orientierungslogik
    - gleiches einfaches Glazing-/SHGC-Niveau
    - noch keine kohortenspezifischen Shading-/Solarannahmen
- Konsequenz:
  - der Teacher ist jetzt fuer Temperatur-/Verlust-/Heizlast-Plausibilisierung deutlich besser
  - fuer eine wirklich kohortenspezifische Solar-/Geometriekalibrierung brauchen wir als naechsten Schritt belastbare Archetyp-Inputs fuer Glazing/Shading/Solar-Exposition, nicht neue implizite Defaults

## 2026-04-02

### Quellenstand fuer Glazing / Shading / Solar Exposure nachgeschaerft

- `Documentation/Sources/building_calibration_quellen.md` wurde inhaltlich nachgeschaerft und trennt jetzt klar:
  - source-backed Residential-Basis
  - methodische Verfahrenswerte
  - offene Punkte fuer `non_residential`
- Neuer sauberer Befund:
  - die frueheren `Solar_gains.csv`- und `Strahlungsdaten_Felixgasse22.csv`-Pfade sind fuer den neuen `EnergyPlus`-Teacher **nicht** mehr Wetter-/Solar-SSOT
  - sie bleiben nur noch Legacy-/Vergleichsartefakte
- Residential ist jetzt quellenmaessig besser abgesichert:
  - Austrian TABULA / EPISCOPE liefert periodische Fenstertypologien
  - TABULA Appendix stuetzt die heute genutzten Apartment-Block-Geometrieratios
  - OIB-Richtlinie 6 liefert zusaetzliche oesterreichische Plausibilitaetsanker fuer `g`, Luftwechsel und Solltemperaturen
- Gleichzeitig ist klarer dokumentiert:
  - TABULA-Shadingwerte (`Fsh`, `FF`, `FW`) sind eher Verfahrens-/Fallbackwerte als Wiener Kohortenwahrheit
  - `non_residential` bleibt fuer Geometrie / Solar / effektive thermische Kapazitaet weiterhin deutlich offener als `residential`

### Residential-Glazing-Metadaten in die Archetypen-SSOT gezogen

- Die Wiener `thermal_archetypes` tragen jetzt fuer `residential` explizit:
  - `window_typology_class`
  - `glazing_source`
  - `solar_shading_assumption`
- Der Teacher-Input-Export in `teacher_inputs_v1.json` fuehrt diese Felder jetzt ebenfalls mit.
- Wichtige Einordnung:
  - das ist bewusst noch **Metadaten-/Quellenintegration**
  - numerische `g/SHGC`-Werte wurden dabei noch nicht still erfunden oder implizit aus Altpfaden uebernommen

### Erster Reduced-Order-Fit aus Teacher-Runs

- Neuer Fit-Pfad:
  - `Technical_model/technologies/buildings/calibration/fit_reduced_order.py`
  - `Technical_model/technologies/buildings/calibration/run_fit_reduced_order.py`
- Schnitt:
  - nutzt nur bereits vorhandene Teacher-Runs
  - braucht explizit:
    - `winter_reference_week`
    - `winter_free_float_72h`
  - keine stillen Fallbacks bei fehlenden Runs/Spalten/Artefakten
- Export:
  - pro Kohorte JSON unter
    `Technical_model/technologies/buildings/calibration/_reduced_order_fits/<cohort_id>/`
  - Batch-Zusammenfassung als:
    - `reduced_order_fit_summary.csv`
    - `reduced_order_fit_summary.json`
- Inhaltlich wird aktuell gefittet:
  - `H_total`
  - `UA_transmission`
  - approximierte Luftverlustanteile
  - `C_th`
  - `tau`
  - Fehlermae gegen Referenz-Heizlast und Free-Float-Temperatur
- Methodischer Punkt:
  - der Fit nutzt eine **nichtnegative Zwei-Feature-Verlustdekomposition**
    aus Seed-Transmission und approximierten Luftverlusten
  - damit kippen die modernen Kohorten nicht mehr in negative `UA`-Schaetzungen
- Batch ueber alle 8 Wiener Kohorten lief erfolgreich durch.

### Event-Response-Fit mit expliziten Cold-Year-Baselines

- Der erste Event-Fit war fachlich nicht sauber, weil `winter_reference_week`
  aus dem `average_year` gegen Event-Runs aus dem `cold_year` verglichen wurde.
- Neuer sauberer Schnitt:
  - `winter_event_reference_96h`
  - `winter_recovery_reference_120h`
  als explizite SSOT-Experimente im `cold_year`
- Diese Baselines werden jetzt fuer:
  - `preheat`
  - `cutback`
  - `recovery`
  gegen gleiches Wetter, gleiche Dauer und gleiche lokalen Zeitstempel verwendet.
- Kein stiller Fallback:
  - fehlen diese Baseline-Experimente oder passen die Zeitfenster nicht,
    bricht `fit_event_response.py` hart ab.
- Neuer Event-Fit-Pfad:
  - `Technical_model/technologies/buildings/calibration/fit_event_response.py`
  - `Technical_model/technologies/buildings/calibration/run_fit_event_response.py`
- Outputs:
  - `Technical_model/technologies/buildings/calibration/_event_response_fits/event_response_fit_summary.csv`
  - `Technical_model/technologies/buildings/calibration/_event_response_fits/event_response_fit_summary.json`
  - pro Kohorte `event_response_fit.json`
- Batch ueber alle 8 Wiener Kohorten lief erfolgreich durch.
- Erste sichtbare Kennwerte:
  - `residential_pre1975`: `preheat_added_energy_kwh = 79.0`, `cutback_shed_energy_kwh = 76.1`, `recovery_rebound_energy_kwh = 50.2`
  - `residential_2000_2014`: `preheat_added_energy_kwh = 51.1`, `cutback_shed_energy_kwh = 44.7`, `recovery_rebound_energy_kwh = 40.6`
  - `non_residential_2000_2014`: `preheat_added_energy_kwh = 43.0`, `cutback_shed_energy_kwh = 33.7`, `recovery_rebound_energy_kwh = 30.7`

### `calibrated_v1`-Export geschnitten

- Neuer Exportpfad:
  - `Technical_model/technologies/buildings/calibration/export_calibrated_archetypes.py`
  - `Technical_model/technologies/buildings/calibration/run_export_calibrated_v1.py`
- Export schreibt jetzt:
  - [calibrated_v1.json](/c:/Users/Philipp%20Thunshirn/Desktop/PhD/Python%20model/Master/Data/thermal_archetypes/Vienna/calibrated_v1.json)
  - [calibrated_v1.py](/c:/Users/Philipp%20Thunshirn/Desktop/PhD/Python%20model/Master/Data/thermal_archetypes/Vienna/calibrated_v1.py)
- Schnitt:
  - bestehende Archetypenfelder bleiben intakt
  - kalibrierte Teacher-Seitenprodukte haengen als Sidecar unter `calibration_v1`
  - `reduced_order_v1`
  - `event_response_v1`
- Der Export bleibt bewusst Sidecar-SSOT:
  - Runtime-Archetypen werden noch nicht automatisch ersetzt
  - voller Ersatz erst nach expliziter Anbindungsentscheidung

### Runtime-Pfad auf kalibrierte effektive Parameter umgestellt

- Neuer aktiver Standardschnitt in `get_settings()`:
  - `thermal_archetypes.variant = calibrated_v1`
  - explizit rueckschaltbar ueber Override auf `default`
- Die Umstellung betrifft bewusst nur die **effektiven dynamikrelevanten Parameter**:
  - `effective_total_loss_coefficient_w_per_k`
  - `effective_transmission_loss_coefficient_w_per_k`
  - `effective_air_loss_scale`
  - `effective_heat_capacity_wh_per_k`
  - `effective_tau_h`
- Andockpunkte:
  - `Settings/data/thermal_archetypes.py`
  - `Settings/get_settings.py`
  - `Technical_model/technologies/buildings/runtime_building_params.py`
  - `Technical_model/consumption/heating_anc_cooling_consumption/heating_and_cooling.py`
  - `Technical_model/consumption/heating_anc_cooling_consumption/thermflex_linear_model.py`
  - `Technical_model/energy_system/systems/integrated_energy_system.py`
  - `Technical_model/energy_system/systems/EC_FLEX.py`
- Kein stiller Fallback:
  - `calibrated_v1` muss pro Archetyp `reduced_order_v1` und `event_response_v1` liefern
  - fehlende effektive Runtime-Felder brechen im Hauptpfad hart ab
- Wichtige Korrektur im IES-/EC-FLEX-Pfad:
  - `heat_capacity` wird dort jetzt nicht mehr nochmals mit `A_floor` multipliziert
  - die Runtime-Semantik ist jetzt konsistent: `heat_capacity` steht fuer `Wh/K`

### Event-Response-Bounds aktiv in den Thermflex-Pfad integriert

- Neuer aktiver Schnitt fuer die Wiener Thermflex-Paperfaelle:
  - `constraints.thermflex.use_event_response_bounds = true`
  - `enforce_event_peak_bounds = true`
  - `enforce_event_energy_bounds = true`
  - `enforce_recovery_cooldown = true`
- Andockpunkte:
  - `Settings/constraints/thermflex.py`
  - `Technical_model/consumption/heating_anc_cooling_consumption/thermflex_linear_model.py`
  - `Technical_model/energy_system/systems/integrated_energy_system.py`
  - `dispatch/modes/milp_day_ahead.py`
  - `dispatch/modes/milp_two_stage.py`
- Aktive Logik:
  - Peak-Bounds pro aktivem Thermflex-Event
  - Event-Energiebudgets fuer `preheat` und `cutback`
  - Recovery-Cooldown auf Basis `max_flex_duration_h + recovery_time_to_reference_h`
- Bewusst noch **nicht** hart integriert:
  - `recovery_rebound_energy_kwh` bleibt vorerst KPI-/Analysewert und keine MILP-Zwangsbedingung
- Kein stiller Fallback:
  - Event-Bounds laufen nur, wenn `calibration_event_response_v1` pro Member vorliegt
  - `teacher_reference_gfa_m2` muss explizit im Settings-SSOT verfuegbar sein
  - fehlende oder negative Event-Kennwerte brechen hart ab
- Echten Integrationsfehler behoben:
  - `building_calibration` war zuerst noch nicht am globalen `Settings`-Objekt verdrahtet
  - ist jetzt als eigener Settings-Block in `Settings/settings_model.py` und `Settings/get_settings.py` eingebunden
- Parametrik-Smoke erfolgreich:
  - aktiver Wien-Thermflex-Fall laedt `building_calibration.teacher_reference_gfa_m2 = 1000.0`
  - Event-Bounds werden auf den aktiven `stock_scale = district_heating.share` skaliert

### Dispatch-/Thermflex-KPI-Export auf aktive Event-Bounds vervollstaendigt

- Der Dispatch-/Thermflex-KPI-Export fuehrt jetzt die aktiven Event-Bound-Informationen explizit als SSOT mit:
  - `thermflex_event_response_bounds_active`
  - `thermflex_event_peak_bounds_active`
  - `thermflex_event_energy_bounds_active`
  - `thermflex_event_recovery_cooldown_active`
  - `thermflex_preheat_event_energy_limit_kwh_total`
  - `thermflex_cutback_event_energy_limit_kwh_total`
  - `thermflex_recovery_rebound_energy_kwh_total`
  - `thermflex_recovery_time_to_reference_h_mean`
  - `thermflex_recovery_time_to_reference_h_max`
  - `thermflex_preheat_peak_excess_kwh_per_step_max`
  - `thermflex_cutback_peak_shed_kwh_per_step_max`
  - `thermflex_event_preheat_extra_realized_kwh`
  - `thermflex_event_cutback_shed_realized_kwh`
- Die Export-SSOT dazu liegt in:
  - `Settings/reporting/reporting.py`
  - `Optimization/run/analysis/csv_exports.py`
  - `Optimization/run/analysis/summary.py`
- Kein stiller Fallback:
  - wenn Thermflex aktiv ist, muessen die benoetigten Diagnosefelder oben in `dispatch_diagnostics` vorhanden sein
  - fehlt ein Pflichtfeld, bricht der Export hart ab

### Top-Level-Dispatch-Aggregation fuer Thermflex vervollstaendigt

- Der gekoppelte IES-Dispatch aggregiert die Thermflex-KPIs jetzt oben in `dispatch_diagnostics`, statt nur implizit in `day_blocks`.
- Wichtige Korrekturen:
  - volle Periodenmetriken aus den aggregierten Raumwaermereihen statt naive Blocksumme
  - `district_space_heat_demand_ref` explizit als Gesamtserie im IES-Resultat
  - `thermflex_member_count` als echte blockkonstante Diagnose grob pruefen und dann oben aggregieren
- Dadurch brechen Gold-/Paper-/Exportpfade nicht mehr an fehlenden Top-Level-Thermflex-Feldern.

### Surrogat-Truth-Pfad auf `milp_day_ahead + calibrated_v1 + event bounds` stabilisiert

- `evaluate_teacher_dataset(...)` auditiert infeasible Punkte jetzt explizit statt sie still zu verlieren.
- Neue Surrogat-Train-SSOT:
  - `teacher_infeasible_policy = drop_and_audit`
  - `teacher_min_feasible_samples = 8`
  - `teacher_max_infeasible_share = 0.5`
- Outputs pro Trainingslauf:
  - `teacher_eval/summary.json`
  - `teacher_eval/infeasible_points.csv`
- Der aktuelle `xgb + gold_recheck`-Trainingslauf auf
  `vienna_ref2023_dh_day_night_thermflex_surrogate_train`
  lief erfolgreich durch:
  - Ergebnisordner:
    [surrogate_20260402_175737](/c:/Users/Philipp%20Thunshirn/Desktop/PhD/Python%20model/Master/Optimization/run/results/Vienna/vienna_ref2023_dh_day_night_thermflex_surrogate_train/surrogate_20260402_175737)
  - Teacher-Audit:
    - `requested = 16`
    - `feasible = 11`
    - `infeasible = 5`
    - `infeasible_share = 0.3125`
  - promoted Artifact:
    [45be7f776faa37b244fab08e82f96107f160104c76f5ca0d81063d76a4d61962](/c:/Users/Philipp%20Thunshirn/Desktop/PhD/Python%20model/Master/Optimization/run/artifacts/surrogates/45be7f776faa37b244fab08e82f96107f160104c76f5ca0d81063d76a4d61962)
- `milp_two_stage` bleibt damit bewusst nicht mehr der breite Teacher-Standard, sondern nur noch Endpunkt-/Truth-Validierung.

### Wiener Paper-Day-Ahead-Faelle auf gemeinsame feasible Designbasis umgestellt

- Die fruehere feste Paper-Benchmark-Kombination war unter `calibrated_v1 + event bounds` nicht mehr fuer alle drei Faelle solverseitig tragfaehig.
- Neuer sauberer Schnitt:
  - gemeinsame feste DH-Designbasis aus dem aktuellen Truth-Pfad
  - explizit im Override dokumentiert, nicht still im Runtime-Code
  - `thermal_archetypes.variant = calibrated_v1` in allen drei Paper-Overrides explizit gesetzt
- Vorgehen:
  - gemeinsames feasible Design aus dem aktuellen
    `vienna_ref2023_dh_day_night_thermflex_surrogate_train`-LHS rekonstruiert
  - auf die Schnittmenge ueber alle drei Paper-Settings getestet:
    - `baseline_constant_no_thermflex_paper_day_ahead`
    - `day_night_no_thermflex_paper_day_ahead`
    - `day_night_thermflex_paper_day_ahead`
  - als gemeinsame Basis gewaehlt: `row 10`
- Aktive feste DH-Kapazitaeten im Paper-SSOT:
  - `district_heat_pump_kw_th = 28402.2`
  - `district_thermal_storage_kwh_th = 1110490.3`
  - `district_biomass_chp_kw_th = 16027.5`
  - `district_gas_chp_kw_el = 675590.0`

### Drei Wiener Paper-Faelle laufen jetzt sauber durch

- Runner:
  - `Optimization/run/papers/dh_thermflex/run_vienna_thermflex_paper_cases.py`
- Erfolgreiche Run-Outputs:
  - [20260402_183931_vienna_ref2023_dh_baseline_constant_no_thermflex_paper_day_ahead](/c:/Users/Philipp%20Thunshirn/Desktop/PhD/Python%20model/Master/Optimization/run/results/Vienna/gold/20260402_183931_vienna_ref2023_dh_baseline_constant_no_thermflex_paper_day_ahead)
  - [20260402_183951_vienna_ref2023_dh_day_night_no_thermflex_paper_day_ahead](/c:/Users/Philipp%20Thunshirn/Desktop/PhD/Python%20model/Master/Optimization/run/results/Vienna/gold/20260402_183951_vienna_ref2023_dh_day_night_no_thermflex_paper_day_ahead)
  - [20260402_184012_vienna_ref2023_dh_day_night_thermflex_paper_day_ahead](/c:/Users/Philipp%20Thunshirn/Desktop/PhD/Python%20model/Master/Optimization/run/results/Vienna/gold/20260402_184012_vienna_ref2023_dh_day_night_thermflex_paper_day_ahead)
- Laufzeiten:
  - Baseline: `20.16 s`
  - Day/Night ohne Thermflex: `21.11 s`
  - Day/Night mit Thermflex: `39.36 s`
- Dispatch-KPI-Exports liegen fuer alle drei Faelle sauber vor.
- Wichtiger Exportfix dabei:
  - `thermflex_member_count` wurde als Top-Level-Pflichtdiagnose in der IES-Aggregation nachgezogen
  - vorher war der Thermflex-Paperfall solverseitig bereits optimal, brach aber im KPI-Export.

### Coding-Regeln fuer künftige Aufgaben geschaerft

- `AGENTS.md` und `Documentation/coding_rules.md` wurden als Task-Start-SSOT geschaerft.
- Neu explizit festgehalten:
  - vor Codeaenderungen zuerst `AGENTS.md` und `Documentation/coding_rules.md` konsultieren
  - Uebersichtlichkeit, Logik, Klarheit und Erweiterbarkeit sind zentrale Kriterien fuer jede Codeerweiterung

### Ziel-Layer und Repo-Regeln weiter geschaerft

- Neuer Ziel-Layer unter `Documentation/Target/` angelegt.
- Darin das uebergeordnete Zielsystem fuer die Energiesystemmodellierung dokumentiert:
  - Wien-2040-MES mit weitgehend dekarbonisierten Sektoren `Strom`, `Waerme` und `Verkehr`
  - aktueller Wiener DH-/Thermflex-Paperschnitt als bewusst enger Teil dieses groesseren Zielbilds
  - J1-/AI-Layer als Beschleuniger fuer schnelle, praezise und cachingfaehige Modellierung
- `AGENTS.md` und `Documentation/coding_rules.md` nochmals verschaerft:
  - Einfachheit in Logik und Struktur jetzt explizit als Kriterium
  - neue nicht-triviale Logik soll sehr dicht erklaert werden:
    warum sie existiert, warum sie so geschrieben ist und was sie bedeutet
  - neue langlebige Ordner/Sub-Layer sollen immer ein aussagekraeftiges `README.md` haben
- Fehlende `README.md` fuer neue langlebige Ordner nachgezogen:
  - `Learning/datasets/`
  - `Technical_model/technologies/buildings/calibration/`
- Den neuen Trainingsdaten-SSOT-Schnitt direkt im offenen Surrogat-Task in `Documentation/Planning/TODO.md` verankert:
  - `truth_dataset.csv`
  - `truth_dataset.meta.json`
  - `family_spec.json`
  - `source_runs.json`
  - `teacher_eval/...`

### Paper-Analyse-Runner und vergroesserter Thermflex-Truth-Lauf

- Neuer reproduzierbarer Paper-Analyse-Runner:
  - `Optimization/run/papers/dh_thermflex/run_vienna_thermflex_paper_analysis.py`
  - zieht die neuesten drei Wiener Paper-Gold-Runs automatisch ueber die bekannten Run-Suffixe
  - nutzt den generischen Analysis-Helper `Optimization/run/analysis/build_paper_dispatch_comparison.py`
  - schreibt zusaetzlich `selected_runs.json`, damit der konkrete Run-Stand explizit dokumentiert bleibt
- Der Analysis-Layer unter `Optimization/run/analysis/` hat jetzt ein eigenes `README.md`.
- Neuer vergroesserter Thermflex-Trainingsfall:
  - `vienna_ref2023_dh_day_night_thermflex_surrogate_train_l48.json`
  - gleicher Truth-Pfad wie der Standardfall:
    `milp_day_ahead + calibrated_v1 + event bounds`
  - aber `lhs n=48` statt `n=16`
- Ergebnis des L48-Laufs:
  - Run:
    `Optimization/run/results/Vienna/vienna_ref2023_dh_day_night_thermflex_surrogate_train_l48/surrogate_20260402_195420`
  - Teacher-Eval:
    `requested = 48`, `feasible = 36`, `infeasible = 12`
  - Family-Dataset:
    `Learning/datasets/8f528a83a425cbb458e4d19bce5af824faa973fd746ed501897bd5400e8725d7`
  - Dataset-Stand danach:
    `n_samples = 47`, `n_existing_samples = 11`, `n_new_samples = 36`, `n_known_infeasible_samples = 17`
  - Holdout:
    median `R2 = 0.776`
- Die Family-Reuse-Logik wurde dabei praktisch bestaetigt:
  - bestehende Family erkannt
  - bestehender Dataset-Stand geladen
  - nur neue Truth-Punkte gerechnet
- Die Paper-Vergleichsartefakte wurden mit dem neuen Runner erneut gebaut unter:
  - `Optimization/run/results/Vienna/gold/paper_dispatch_comparison_20260402_195332`
- Repo-Regeln weiter geschaerft:
  - bei groesseren Repo-Aenderungen regelmaessig sauber committen und auf GitHub pushen

### Fokussierter Surrogat-Targetschnitt fuer Wiener DH-/Thermflex-Optimierung

- `Settings/surrogate/train.py` fuehrt jetzt explizite `target_profile`-SSOT statt nur einer breiten Default-Targetliste:
  - `full_system_default`
  - `dispatch_publish_core`
  - `dispatch_optimization_core`
- `Optimization/framework/engines/Surrogat_model/features.py` loest diesen Schnitt jetzt fail-fast auf:
  - erst explizite `targets`
  - sonst explizites `target_profile`
  - kein stilles Zurueckfallen auf heuristische Runtime-Targetwahl
- `append_active_technology_targets` bleibt moeglich, ist aber jetzt ein expliziter Settings-Schalter statt stiller Target-Aufblaehung.

### Teacher-Scaling-Bug im fokussierten Surrogatpfad behoben

- Im Teacher-Pfad `evaluate_teacher.py` wurde ein echter Semantikfehler gefunden:
  - `co2_emissions_total_t`
  - `thermflex_peak_change_kw`
  - `thermflex_rebound_kwh`
  - `thermflex_t_in_min_c`
  - `thermflex_t_in_max_c`
  - weitere Dispatch-Diagnostics
  wurden faelschlich mit `lifetime_years` skaliert.
- Das war inkonsistent zum Gold-/Truth-Pfad und fuehrte im ersten Fokuslauf zu physikalisch unsinnigen Temperaturwerten.
- Der Fix ist jetzt drin:
  - Dispatch-Diagnostics bleiben slice-level
  - nur echte Lifetime-Energiefluesse werden weiter mit `lifetime_years` multipliziert
- Der erste fehlerhafte Fokus-Datensatz wurde bewusst verworfen und danach sauber neu aufgebaut.

### Fokussierte Thermflex-Surrogatlaeufe

- Neuer Publish-/Analyse-Schnitt:
  - `vienna_ref2023_dh_day_night_thermflex_surrogate_focus_l48.json`
  - `20` explizite Targets
  - darunter Kostenkern, CO2, zentrale Thermflex-KPIs und wichtiger Waermemix
- Korrigierter Fokuslauf:
  - `Optimization/run/results/Vienna/vienna_ref2023_dh_day_night_thermflex_surrogate_focus_l48/surrogate_20260402_202414`
  - Family-Dataset:
    `Learning/datasets/cfb4d20ab3cad9a15e188657f38d49dcd2637b7b45e5209cbe15e4080f296941`
  - `requested = 48`, `feasible = 36`, `infeasible = 12`
  - Holdout:
    - Median `R2 = 0.059`
    - aber bereits gute Einzeltargets fuer:
      - `co2_emissions_total_t`
      - `E_district_heat_pump_thermal_generation_kWh`
      - `E_district_biomass_chp_thermal_generation_kWh`
      - `E_district_gas_chp_thermal_generation_kWh`
      - `E_district_gas_boiler_generation_kWh`
- Wichtiger Befund aus dem Fokus-Datensatz:
  - `dh_unserved_heat` und `thermflex_additional_space_heat_kwh` sind im aktuellen feasiblem Raum konstant `0`
  - sie sind fuer den Optimierungs-Surrogatpfad damit derzeit kein hilfreicher Lerninhalt

### Engerer Optimierungs-Surrogatpfad

- Neuer engerer Optimierungs-Schnitt:
  - `vienna_ref2023_dh_day_night_thermflex_surrogate_opt_l96.json`
  - `11` Targets:
    - `dispatch_operating_cost_eur`
    - `dispatch_objective_eur`
    - `dispatch_penalty_total_eur`
    - `co2_emissions_total_t`
    - `thermflex_shifted_space_heat_kwh`
    - `thermflex_peak_change_kw`
    - `thermflex_temperature_violation_degree_hours_total`
    - zentrale DH-Waermemix-Fluesse
- Lauf erfolgreich:
  - `Optimization/run/results/Vienna/vienna_ref2023_dh_day_night_thermflex_surrogate_opt_l96/surrogate_20260402_203051`
  - Family-Dataset:
    `Learning/datasets/2783a44e4b4bbe22db739fd5be816c8ebee5680733862daaf81aec95db35de6d`
  - Teacher-Audit:
    - `requested = 96`
    - `feasible = 55`
    - `infeasible = 41`
    - `infeasible_share = 0.427`
- Holdout-Ergebnis dieses engeren Opt-Schnitts:
  - Median `R2 = 0.747`
  - starke Targets:
    - `thermflex_peak_change_kw: R2 = 0.747`
    - `co2_emissions_total_t: R2 = 0.827`
    - `E_district_heat_pump_thermal_generation_kWh: R2 = 0.923`
    - `E_district_biomass_chp_thermal_generation_kWh: R2 = 0.928`
    - `E_district_gas_chp_thermal_generation_kWh: R2 = 0.955`
    - `E_district_gas_boiler_generation_kWh: R2 = 0.834`
- Einordnung:
  - `dispatch_operating_cost_eur` bleibt im aktuellen Designraum sehr varianzarm
  - deshalb ist `R2` dort wenig aussagekraeftig, obwohl der relative Fehler extrem klein bleibt
  - fuer Ranking/Optimierung ist aktuell `dispatch_objective_eur` plus die expliziten Mix-/CO2-/Thermflex-KPIs der robustere Lernschnitt

### Append-Lauf und erste echte Wiener Surrogat-Optimierung

- `dispatch_optimization_core` wurde auf derselben Family erweitert statt einen neuen Family-Silo zu erzeugen:
  - neuer Append-Fall:
    `vienna_ref2023_dh_day_night_thermflex_surrogate_opt_append_l64.json`
  - Run:
    `Optimization/run/results/Vienna/vienna_ref2023_dh_day_night_thermflex_surrogate_opt_append_l64/surrogate_20260402_205753`
- Ergebnis des Append-Laufs:
  - `requested = 64`
  - `feasible = 41`
  - `infeasible = 23`
  - Family-Dataset:
    `Learning/datasets/2783a44e4b4bbe22db739fd5be816c8ebee5680733862daaf81aec95db35de6d`
  - Dataset-Stand danach:
    `n_samples = 96`, `n_existing_samples = 55`, `n_new_samples = 41`
- Holdout nach dem Append:
  - starke Fluesse bleiben:
    - `co2_emissions_total_t`
    - `E_district_heat_pump_thermal_generation_kWh`
    - `E_district_biomass_chp_thermal_generation_kWh`
    - `E_district_gas_chp_thermal_generation_kWh`
    - `E_district_gas_boiler_generation_kWh`
  - `dispatch_operating_cost_eur` bleibt praktisch varianzlos
  - `thermflex_shifted_space_heat_kwh` bleibt fuer den direkten Opt-Schnitt noch zu schwach

### Runtime-Konsistenz fuer echte Surrogat-Optimierung

- `run.tag` wurde aus dem Surrogat-Signaturkontext entfernt:
  - Tags sind Provenienz
  - sie duerfen die Family-/Artefakt-Kompatibilitaet nicht veraendern
- Trainings- und Runtime-Signatur nutzen jetzt denselben `system_flags`-Block aus
  `Optimization/framework/engines/Surrogat_model/features.py`
- Der Loader erkennt jetzt auch das primaere promovierte
  `surrogate_bundle.joblib` unter
  `Optimization/run/artifacts/surrogates/<signature_hash>/`
- Der Surrogat-Engine-Pfad kann `dispatch_cost_eur` jetzt explizit direkt aus dem
  gelern­ten `dispatch_objective_eur`-Target lesen, solange:
  - keine physischen Runtime-Constraints rekonstruiert werden muessen
  - und die Objective-Zuordnung vollstaendig im Target-Schnitt vorhanden ist
- Das ist keine stille Fallback-Heuristik, sondern eine explizite aliasierte SSOT-Regel:
  - `dispatch_cost_eur == dispatch_objective_eur`

### Echte Surrogat-Optimierung und Gold-Recheck

- Surrogat-Optimierungs-Smoke erfolgreich:
  - `Optimization/run/results/Vienna/surrogate/20260402_210835_vienna_ref2023_dh_day_night_thermflex_surrogate_optimize_smoke`
- Erste echte Surrogat-Optimierung erfolgreich:
  - `Optimization/run/results/Vienna/surrogate/20260402_210922_vienna_ref2023_dh_day_night_thermflex_surrogate_optimize`
- Neuer expliziter Recheck-Runner:
  - `Optimization/run/papers/dh_thermflex/run_vienna_thermflex_surrogate_recheck.py`
  - liest `pareto_points.csv`
  - validiert Top-k gegen Gold `milp_day_ahead`
  - replayt optional den besten day-ahead-feasiblen Kandidaten mit `milp_two_stage`
- Recheck des ungescreenten Hauptpfads:
  - Output:
    `Optimization/run/results/Vienna/surrogate/20260402_210922_vienna_ref2023_dh_day_night_thermflex_surrogate_optimize/surrogate_recheck/20260402_213100`
  - `top_k = 10`
  - `n_topk_feasible_day_ahead = 2`
  - bester day-ahead-feasibler Kandidat erst auf `rank = 4`
  - `milp_two_stage` fuer diesen Kandidaten weiter infeasible
- Einordnung:
  - der schnelle Surrogat-Search ist wertvoll
  - aber `milp_day_ahead`-Gold-Recheck auf Top-k bleibt zwingend
  - `milp_two_stage` bleibt weiter Endpunkt-Validierung statt breiter Teacher

### Expliziter Surrogat-Feasibility-Screen als Experiment

- Neuer expliziter Surrogat-Screen aus demselben Family-Dataset:
  - `Optimization/framework/engines/Surrogat_model/feasibility_screen.py`
  - nutzt auditiertes `truth_dataset` + `teacher_eval/infeasible_points.csv`
  - lernt eine `feasible_probability`
  - gibt einen expliziten Constraint
    `surrogate_feasible_probability_guard`
    als `g(x) = min_feasible_probability - p_feasible`
- Wichtiger Schnitt:
  - der Screen ist **nicht** still im Hauptpfad aktiv
  - die gescreenten Override-Pfade sind explizit separat:
    - `vienna_ref2023_dh_day_night_thermflex_surrogate_optimize_screened_smoke.json`
    - `vienna_ref2023_dh_day_night_thermflex_surrogate_optimize_screened.json`
  - der Hauptpfad bleibt:
    - `vienna_ref2023_dh_day_night_thermflex_surrogate_optimize.json`
    - ohne aktiven Screen
- Ergebnis des gescreenten Experiments:
  - Run:
    `Optimization/run/results/Vienna/surrogate/20260402_212308_vienna_ref2023_dh_day_night_thermflex_surrogate_optimize`
  - Recheck:
    `Optimization/run/results/Vienna/surrogate/20260402_212308_vienna_ref2023_dh_day_night_thermflex_surrogate_optimize/surrogate_recheck/20260402_212758`
  - `n_topk_feasible_day_ahead = 0`
- Fazit:
  - der erste explizite KNN-Screen ist als Experiment sauber integriert
  - verbessert den Hauptpfad aktuell aber noch nicht robust genug
  - bleibt deshalb bewusst **experimentell** statt Default

### Multiobjective-Surrogat-Optimierung statt flacher Single-Objective-Kostensuche

- Der bisherige Single-Objective-Schnitt `dispatch_cost_eur` ist im aktuellen feasiblem Wiener
  Day-Ahead-Raum zu flach:
  - die Surrogat-Pareto-Punkte lagen kostenmaessig extrem dicht beieinander
  - damit fehlt der Suche ein ausreichend starkes Ranking-Signal
- Konsequenz:
  - expliziter biobjektiver Pfad eingefuehrt:
    - `dispatch_cost_eur`
    - `co2_emissions_total_t`
  - neue Overrides:
    - `vienna_ref2023_dh_day_night_thermflex_surrogate_optimize_biobj_smoke.json`
    - `vienna_ref2023_dh_day_night_thermflex_surrogate_optimize_biobj.json`
- Technischer Fix dafuer:
  - `co2_emissions_total_t` ist jetzt explizit als KPI-Objective in
    `Optimization/framework/engines/kpi.py` unterstuetzt
  - das ist keine implizite Umdeutung von `climate_change`, sondern die explizite
    operative DH-CO2-Groesse aus dem bestehenden KPI-/Teacher-Schnitt
- Recheck-Runner erweitert:
  - `Optimization/run/papers/dh_thermflex/run_vienna_thermflex_surrogate_recheck.py`
  - neuer expliziter Parameter `--sort-column`
  - dadurch koennen Kosten- und CO2-Ende getrennt gegen Gold validiert werden
- Lern-/Runtime-Konsistenz:
  - der explizite native Retrain-Pfad ueber `force_native_retrain` war im Strict-Loader blockiert
  - `Optimization/framework/engines/Surrogat_model/surrogate_engine.py` wurde so korrigiert,
    dass der dokumentierte explizite Retrainpfad tatsaechlich ausfuehrbar ist
  - fuer den biobjektiven Schnitt war kein neues Truth-Dataset noetig; die bestehende
    `dispatch_optimization_core`-Family bleibt die Datengrundlage
- Ergebnisse:
  - Smoke:
    `Optimization/run/results/Vienna/surrogate/20260402_215759_vienna_ref2023_dh_day_night_thermflex_surrogate_optimize_biobj_smoke`
  - echter Lauf:
    `Optimization/run/results/Vienna/surrogate/20260402_215831_vienna_ref2023_dh_day_night_thermflex_surrogate_optimize_biobj`
  - Pareto-Export enthaelt jetzt:
    - `F_dispatch_cost_eur`
    - `F_co2_emissions_total_t`
- Gold-Recheck biobjektiv:
  - kosten-sortiert:
    `Optimization/run/results/Vienna/surrogate/20260402_215831_vienna_ref2023_dh_day_night_thermflex_surrogate_optimize_biobj/surrogate_recheck/20260402_220000`
    - `n_topk_feasible_day_ahead = 7`
    - bester feasible Kandidat auf `rank = 2`
    - `milp_two_stage` fuer den ausgewaehlten Kandidaten weiter infeasible
  - CO2-sortiert:
    `Optimization/run/results/Vienna/surrogate/20260402_215831_vienna_ref2023_dh_day_night_thermflex_surrogate_optimize_biobj/surrogate_recheck/20260402_220435`
    - `n_topk_feasible_day_ahead = 7`
    - bester feasible Kandidat auf `rank = 3`
    - zweistufiger Replay bewusst uebersprungen, um zuerst den Day-Ahead-Befund sauber zu sichern
- Einordnung:
  - der biobjektive Schnitt ist aktuell der bessere Suchpfad als reine Kostensuche
  - `milp_day_ahead`-Gold-Recheck bleibt zwingend
  - `milp_two_stage` bleibt weiterhin Endpunkt-Check und nicht breiter Such-/Teacherpfad

### Drei explizite biobjektive Gold-Kandidaten fuer den Paper-Schnitt

- Neuer expliziter Runner:
  - `Optimization/run/papers/dh_thermflex/run_vienna_thermflex_biobj_gold_candidates.py`
- Schnitt:
  - liest die biobjektive Pareto-Menge aus dem aktiven Wiener Surrogatlauf
  - prueft Gold-Feasibility explizit ueber `milp_day_ahead`
  - waehlt danach drei reproduzierbare Vertreter:
    - `biobj_cost_end`
    - `biobj_co2_end`
    - `biobj_mid_tradeoff`
  - schreibt daraus echte Gold-Runs und einen erweiterten Paper-Vergleich
- Wichtige Fail-fast-Regeln:
  - keine impliziten Auswahlheuristiken
  - fehlende Objective-Spalten oder leere Spannen fuehren zu hartem Fehler
  - jeder ausgewaehlte Kandidat muss vor dem Export explizit gold-feasible sein
- Output-Gruppe:
  - `Optimization/run/results/Vienna/gold/biobj_gold_candidates_20260403_093146`
  - darin:
    - drei Gold-Runs
    - `selection_summary.json`
    - `selection_audit.csv`
    - `paper_comparison/`
- Konkrete Auswahl:
  - `biobj_cost_end`
    - `pareto_idx = 1`
    - `surrogate_dispatch_cost_eur = 576801341440.0`
    - `surrogate_co2_emissions_total_t = 12554.9443359375`
    - `gold_dispatch_cost_eur_recheck = 576805889379.5038`
  - `biobj_co2_end`
    - `pareto_idx = 6`
    - `surrogate_dispatch_cost_eur = 576851410944.0`
    - `surrogate_co2_emissions_total_t = 10774.078125`
    - `gold_dispatch_cost_eur_recheck = 576871893122.6747`
  - `biobj_mid_tradeoff`
    - `pareto_idx = 4`
    - `surrogate_dispatch_cost_eur = 576820477952.0`
    - `surrogate_co2_emissions_total_t = 11676.3125`
    - `gold_dispatch_cost_eur_recheck = 576827900094.7069`
- Erweiterter Paper-Vergleich:
  - `Optimization/run/results/Vienna/gold/biobj_gold_candidates_20260403_093146/paper_comparison/paper_dispatch_comparison.md`
  - enthaelt jetzt:
    - `baseline_constant_no_thermflex`
    - `day_night_no_thermflex`
    - `day_night_thermflex`
    - `biobj_cost_end`
    - `biobj_co2_end`
    - `biobj_mid_tradeoff`
- Wichtigste KPI-Befunde relativ zu `day_night_thermflex`:
  - `biobj_cost_end`
    - `dispatch_objective_eur`: `-10.25 Mio EUR` bzw. `-0.00178 %`
    - `co2_emissions_total_t`: `+82.82 t` bzw. `+0.67 %`
    - `thermflex_shifted_space_heat_kwh`: `-0.98 GWh`
  - `biobj_co2_end`
    - `dispatch_objective_eur`: `+55.76 Mio EUR` bzw. `+0.00967 %`
    - `co2_emissions_total_t`: `-1663.69 t` bzw. `-13.49 %`
    - `thermflex_shifted_space_heat_kwh`: `+0.04 GWh`
  - `biobj_mid_tradeoff`
    - `dispatch_objective_eur`: `+11.76 Mio EUR` bzw. `+0.00204 %`
    - `co2_emissions_total_t`: `-525.55 t` bzw. `-4.26 %`
    - `thermflex_shifted_space_heat_kwh`: `+1.21 GWh`
- Einordnung:
  - der biobjektive Suchpfad liefert jetzt nicht nur robustere day-ahead-feasible Kandidaten,
    sondern auch direkt publish-faehige Vergleichspunkte
  - besonders `biobj_co2_end` ist aktuell der staerkste Paper-Kandidat:
    spuerbar niedrigere operative CO2-Emissionen bei praktisch unveraendertem Objective-Niveau

### Gezielter `milp_two_stage`-Endpunktcheck fuer die biobjektiven Paper-Kandidaten

- Neuer expliziter Replay-Runner:
  - `Optimization/run/papers/dh_thermflex/run_vienna_selected_candidate_two_stage.py`
- Schnitt:
  - liest `selected_candidate.json`
  - nutzt den aktiven Wiener Day-Ahead-Optimierungsschnitt als strukturelle SSOT
  - schaltet nur den Dispatch-Block explizit auf `milp_two_stage`
  - schreibt auch bei solverseitiger Infeasibility eine explizite
    `two_stage_endpoint_summary.json`
- Gepruefte Kandidaten:
  - `biobj_co2_end`
  - `biobj_mid_tradeoff`
- Outputs:
  - `Optimization/run/results/Vienna/gold/biobj_gold_candidates_20260403_093146/20260403_093214_biobj_co2_end_gold_day_ahead/20260403_095255_biobj_co2_end_gold_two_stage/two_stage_endpoint_summary.json`
  - `Optimization/run/results/Vienna/gold/biobj_gold_candidates_20260403_093146/20260403_093239_biobj_mid_tradeoff_gold_day_ahead/20260403_095255_biobj_mid_tradeoff_gold_two_stage/two_stage_endpoint_summary.json`
- Befund:
  - beide Kandidaten sind im aktuellen `milp_two_stage`-Pfad solverseitig infeasible
  - Fehlerbild explizit:
    - `NoFeasibleSolutionError`
    - kein stilles Wegschlucken im Endpoint-Runner
- Einordnung:
  - fuer publish-faehige KPI-Ergebnisse bleibt `milp_day_ahead` derzeit der robuste Gold-Hauptpfad
  - `milp_two_stage` ist weiter der richtige Endpunkt-Check, aber aktuell kein
    bestaetigender Pfad fuer die biobjektiven Pareto-Kandidaten
  - naechster methodischer Schritt ist daher eher:
    - Ursachenanalyse der Zweistufen-Infeasibility
    - statt den Paper-Hauptpfad auf den noch instabilen Zweistufenbefund zu stuetzen

### Konstanter Thermflex-Isolationsfall fuer den Paper-Schnitt

- Neuer expliziter Override:
  - `Optimization/validation/model_validation/overrides/thermflex/vienna_ref2023_dh_baseline_constant_thermflex_paper_day_ahead.json`
- Ziel:
  - "Thermflex generell" von der `day_night`-Regelung trennen
  - deshalb zwei wirklich direkt vergleichbare Faelle:
    - `constant_no_thermflex`
    - `constant_thermflex`
- Schnitt des neuen Falls:
  - `reference_control_mode = constant`
  - `control_mode = constant`
  - `constant_setpoint_c = 22.5`
  - `constant_lower_bound_c = 21.0`
  - `max_flex_duration_h = 4`
  - `max_flex_events_per_day = 1`
  - `constrain_upper_temperature = false`
  - Event-Bounds aktiv
- Gold-Run erfolgreich:
  - `Optimization/run/results/Vienna/gold/20260403_101909_vienna_ref2023_dh_baseline_constant_thermflex_paper_day_ahead`
- Neuer isolierter Analyse-Runner:
  - `Optimization/run/papers/dh_thermflex/run_vienna_constant_thermflex_paper_analysis.py`
- Vergleichsoutput:
  - `Optimization/run/results/Vienna/gold/paper_dispatch_comparison_20260403_102050`
- Wichtige Befunde `constant_thermflex` vs `constant_no_thermflex`:
  - `dispatch_objective_eur`: `-70.99 %`
    - fast vollstaendig getrieben durch Penalty-Reduktion
  - `dispatch_penalty_total_eur`: `-99.9998 %`
  - `dispatch_operating_cost_eur`: praktisch gleich, `-0.000125 %`
  - `co2_emissions_total_t`: `+5.02 %`
  - `dh_unserved_heat_kwh`: von `1.41 GWh` auf `0`
  - `thermflex_shifted_space_heat_kwh`: `7.02 GWh`
  - `thermflex_rebound_kwh`: `5.81 GWh`
  - `thermflex_peak_change_kw`: `-0.782 GW`
- Einordnung:
  - der konstante Isolationsfall bestaetigt die bisherige Richtung:
    - Thermflex liefert hier vor allem Service-/Feasibility-Gewinn und reale Lastverschiebung
    - die physischen Betriebskosten bleiben nahezu unveraendert
  - der scheinbare `objective`-Gewinn ist auch hier fast vollstaendig ein Penalty-Effekt

### Fokussierter Plotblock fuer den konstanten Thermflex-Isolationsvergleich

- Neuer Analyse-Helper:
  - `Optimization/run/analysis/build_constant_thermflex_isolation.py`
- Verdrahtet in:
  - `Optimization/run/papers/dh_thermflex/run_vienna_constant_thermflex_paper_analysis.py`
- Output:
  - `Optimization/run/results/Vienna/gold/paper_dispatch_comparison_20260403_102843`
- Neue fokussierte Artefakte:
  - `constant_thermflex_isolation.png`
  - `constant_thermflex_isolation_summary.json`
  - `constant_thermflex_isolation_summary.md`
- Gezeigte Metriken:
  - `dispatch_operating_cost_eur`
  - `dh_unserved_heat_kwh`
  - `co2_emissions_total_t`
  - `thermflex_shifted_space_heat_kwh`
  - `thermflex_rebound_kwh`
  - `thermflex_peak_change_kw`
- Zusaetzliche Einordnung im Summary:
  - Cost-Component-Deltas:
    - `grid_import_cost_eur`
    - `fuel_cost_eur`
    - `co2_cost_eur`
    - `variable_opex_eur`
  - Dispatch-Mix-Deltas:
    - `district_gas_boiler_generation_kwh`
    - `district_gas_chp_thermal_generation_kwh`
    - `district_heat_pump_generation_kwh`
- Wichtigster Erklaerungsbefund:
  - die operating costs sinken im konstanten Thermflex-Fall zwar leicht, aber nur sehr wenig,
    weil der Gesamtblock `dispatch_operating_cost_eur` stark vom sehr grossen
    `grid_import_cost_eur` dominiert wird
  - gleichzeitig sinkt der Gasboiler-Einsatz deutlich, waehrend Gas-KWK und Waermepumpe ansteigen;
    daher steigen `fuel_cost_eur` und `co2_cost_eur` trotz geringerem Kesseleinsatz

### Korrektur des konstanten Paper-Vergleichs nach Einheitenfix im Runtime-Gebaeudelastpfad

- Root cause der absurden Kosten-/CO2-Groessenordnungen war **kein Preisfehler**, sondern ein
  Einheitenfehler in:
  - `Technical_model/consumption/heating_anc_cooling_consumption/heating_and_cooling.py`
- Der Fehler:
  - `QH` und `QC` wurden als whole-building Energie in `Wh` berechnet
  - aber als `Heizlast [kWh/m²]` bzw. `Kühllast [kWh/m²]` exportiert
  - spaeter wurden diese Reihen in `get_heating_load_on_days()` / `get_cooling_load_on_days()` nochmals mit `A_floor` multipliziert
  - dadurch wurden Heiz- und vor allem Kuehllasten fuer grosse Kohorten um die gesamte Bodenflaeche ueberhoeht
- Der Fix:
  - Export in `calculate_dynamic_heating_cooling()` jetzt korrekt als
    `whole-building Wh / (1000 * A_floor)` -> `kWh/m²`
  - keine stillen Fallbacks, sondern explizite `A_floor > 0`-Validierung
- Direkter Plausibilitaetsbefund fuer die problematische Kohorte `non_residential_2000_2014`:
  - vor Fix explodierte `hp_elec_cool_member_2d` im 24h-Slice auf `1.6479e12 kWh`
  - nach Fix liegt derselbe Slice bei `210,764 kWh`
- Offizielle Konstantfaelle neu gerechnet:
  - `Optimization/run/results/Vienna/gold/20260403_110620_vienna_ref2023_dh_baseline_constant_no_thermflex_paper_day_ahead`
  - `Optimization/run/results/Vienna/gold/20260403_110655_vienna_ref2023_dh_baseline_constant_thermflex_paper_day_ahead`
- Neuer isolierter Vergleich:
  - `Optimization/run/results/Vienna/gold/paper_dispatch_comparison_20260403_110810`
- Korrigierte Befunde `constant_thermflex` vs `constant_no_thermflex`:
  - `dispatch_operating_cost_eur`: `-3.91 %`
  - `dispatch_penalty_total_eur`: praktisch `-100 %`
  - `dispatch_objective_eur`: `-99.999 %`
  - `co2_emissions_total_t`: `+4.96 %`
  - `dh_unserved_heat_kwh`: `-100 %`
  - `thermflex_shifted_space_heat_kwh`: `6.36 GWh`
  - `thermflex_rebound_kwh`: `5.17 GWh`
  - `thermflex_peak_change_kw`: `-617.65 MW`
  - `district_gas_boiler_generation_kwh`: `-19.47 %`
  - `district_gas_chp_thermal_generation_kwh`: `+25.73 %`
  - `district_heat_pump_generation_kwh`: `+53.33 %`
- Wichtige Einordnung:
  - die frueheren Aussagen zum konstanten Isolationsvergleich in diesem Abschnitt
    (`paper_dispatch_comparison_20260403_102050` / `20260403_102843`) sind
    nach dem Einheitenfix **nicht mehr gueltig**
  - fuer Paper/KPI-Interpretation ab jetzt nur noch die neu gerechneten Runs
    und Vergleiche unter `20260403_110620`, `20260403_110655` und
    `paper_dispatch_comparison_20260403_110810` verwenden

### Zeitreihenplot fuer den konstanten Thermflex-Isolationsfall

- `Optimization/run/analysis/build_constant_thermflex_isolation.py` erweitert:
  - erzeugt jetzt zusaetzlich einen 24h-Zeitreihenplot direkt aus dem offiziellen
    Modellpfad ueber die beiden Override-Dateien
  - keine stillen Fallbacks:
    - Override-Dateien muessen explizit vorhanden sein
    - die Zeitreihen werden ueber denselben `GoldEngine`-Pfad wie die Paper-Runs
      re-evaluiert
- `Optimization/run/papers/dh_thermflex/run_vienna_constant_thermflex_paper_analysis.py` angepasst:
  - uebergibt jetzt explizit die beiden konstanten Override-Dateien an den
    Isolations-Bundle-Builder
- Neuer Output:
  - `Optimization/run/results/Vienna/gold/paper_dispatch_comparison_20260403_111854`
  - neue Artefakte:
    - `constant_thermflex_timeseries.png`
    - `constant_thermflex_timeseries_settings.json`
    - `constant_thermflex_timeseries_settings.md`
- Inhaltlich zeigt der neue Plot:
  - `district_space_heat_demand_ref` vs `district_space_heat_demand`
  - `district_gas_boiler_generation`
  - `district_gas_chp_thermal_generation`
  - `district_heat_pump_generation`
  - jeweils fuer `constant_no_thermflex` vs `constant_thermflex`
  - inklusive horizontaler Kapazitaetslinien
- Expliziter Settings-/Slice-Befund:
  - analysierter Slice ist **nicht irgendein Tag**, sondern exakt:
    - `2023-01-08 00:00:00` bis `2023-01-08 23:00:00`
  - `constant_no_thermflex`:
    - `constant_setpoint_c = 22.5`
    - `constant_lower_bound_c = 22.5`
    - `max_flex_duration_h = 0`
    - `max_flex_events_per_day = 0`
  - `constant_thermflex`:
    - `constant_setpoint_c = 22.5`
    - `constant_lower_bound_c = 21.0`
    - `max_flex_duration_h = 4`
    - `max_flex_events_per_day = 1`
    - `constrain_upper_temperature = false`
  - installierte thermische Kapazitaeten bleiben in beiden Faellen identisch:
    - `district_gas_boiler_cap_kw_th = 2,200,000`
    - `district_gas_chp_thermal_equivalent_kw_th = 760,038.75`
    - `district_heat_pump_cap_kw_th = 28,402.2`
  - die beobachteten Mix-Aenderungen sind also **Dispatch-Verschiebungen innerhalb gleicher Kapazitaeten**,
    keine Kapazitaetsausweitung

### Sensitivitaetsblock fuer konstanten Thermflex-Fall (`lower bound`, `duration`, `events`)

- Ziel:
  - den konstanten Isolationsfall nicht nur fuer einen Punkt, sondern fuer einen
    kleinen, expliziten Settings-Block auszuwerten
  - Fokus:
    - `constant_lower_bound_c`
    - `max_flex_duration_h`
    - `max_flex_events_per_day`
- Neue explizite Override-Faelle:
  - `vienna_ref2023_dh_baseline_constant_thermflex_lb21p0_dur2_evt1_paper_day_ahead`
  - `vienna_ref2023_dh_baseline_constant_thermflex_lb21p0_dur6_evt1_paper_day_ahead`
  - `vienna_ref2023_dh_baseline_constant_thermflex_lb21p0_dur8_evt1_paper_day_ahead`
  - `vienna_ref2023_dh_baseline_constant_thermflex_lb21p5_dur4_evt1_paper_day_ahead`
  - `vienna_ref2023_dh_baseline_constant_thermflex_lb20p0_dur4_evt1_paper_day_ahead`
  - `vienna_ref2023_dh_baseline_constant_thermflex_lb21p0_dur4_evt2_paper_day_ahead`
- Neue Runner/Builder:
  - `Optimization/run/papers/dh_thermflex/run_vienna_constant_thermflex_sensitivity_cases.py`
  - `Optimization/run/papers/dh_thermflex/run_vienna_constant_thermflex_sensitivity_analysis.py`
  - `Optimization/run/analysis/build_constant_thermflex_sensitivity.py`
- Wichtiger Fix im Analyse-Builder:
  - kein Modellfehler, sondern expliziter Schemafehler
  - `paper_dispatch_comparison.csv` exportiert `thermflex_max_events_per_day`
  - der neue Sensitivitaets-Builder erwartete irrtuemlich
    `thermflex_max_flex_events_per_day`
  - korrigiert, keine stillen Alias-Fallbacks eingefuehrt
- Sensitivitaetslaeufe erfolgreich gerechnet:
  - `20260403_113942_vienna_ref2023_dh_baseline_constant_no_thermflex_paper_day_ahead`
  - `20260403_113955_vienna_ref2023_dh_baseline_constant_thermflex_paper_day_ahead`
  - `20260403_114026_vienna_ref2023_dh_baseline_constant_thermflex_lb21p0_dur2_evt1_paper_day_ahead`
  - `20260403_114108_vienna_ref2023_dh_baseline_constant_thermflex_lb21p0_dur6_evt1_paper_day_ahead`
  - `20260403_114137_vienna_ref2023_dh_baseline_constant_thermflex_lb21p0_dur8_evt1_paper_day_ahead`
  - `20260403_114214_vienna_ref2023_dh_baseline_constant_thermflex_lb21p5_dur4_evt1_paper_day_ahead`
  - `20260403_114236_vienna_ref2023_dh_baseline_constant_thermflex_lb20p0_dur4_evt1_paper_day_ahead`
  - `20260403_114336_vienna_ref2023_dh_baseline_constant_thermflex_lb21p0_dur4_evt2_paper_day_ahead`
- Auswertung erfolgreich gebaut:
  - `Optimization/run/results/Vienna/gold/paper_dispatch_comparison_20260403_114641`
  - Artefakte:
    - `constant_thermflex_sensitivity.png`
    - `constant_thermflex_sensitivity_summary.json`
    - `constant_thermflex_sensitivity_summary.md`
    - `selected_runs.json`
- Kernbefunde fuer `lower = 21.0 C`, `events = 1`:
  - `duration = 2 h`:
    - `dispatch_operating_cost_eur = 17.636 Mio`
    - `co2_emissions_total_t = 12,356.68`
    - `shifted = 6.331 GWh`
    - `rebound = 5.172 GWh`
    - `peak_change = -616.87 MW`
  - `duration = 4 h`:
    - `dispatch_operating_cost_eur = 17.511 Mio`
    - `co2_emissions_total_t = 12,460.45`
    - `shifted = 6.360 GWh`
    - `rebound = 5.172 GWh`
    - `peak_change = -617.65 MW`
  - `duration = 6 h`:
    - `dispatch_operating_cost_eur = 17.493 Mio`
    - `co2_emissions_total_t = 12,471.55`
    - `shifted = 6.315 GWh`
    - `rebound = 5.107 GWh`
    - `peak_change = -641.34 MW`
  - `duration = 8 h`:
    - `dispatch_operating_cost_eur = 17.487 Mio`
    - `co2_emissions_total_t = 12,463.99`
    - `shifted = 6.370 GWh`
    - `rebound = 5.168 GWh`
    - `peak_change = -648.02 MW`
- Einordnung:
  - laengere globale Dauer bringt im aktuellen 24h-Slice noch etwas mehr
    Kostenreduktion und Peak-Glattung
  - der Zusatznutzen von `6 -> 8 h` ist aber schon klein
  - reine globale Dauererhoehung ist deshalb ein brauchbarer erster Hebel,
    aber kein vollwertiger Ersatz fuer kohortenspezifische Flex-Settings

### Erweiterter Sensitivitaetsblock: `dur1`, Upper-only-Faelle und Kohorten-Utilization

- Auf Wunsch den expliziten Konstant-Thermflex-Sensitivitaetsblock erweitert um:
  - `vienna_ref2023_dh_baseline_constant_thermflex_lb21p0_dur1_evt1_paper_day_ahead`
  - `vienna_ref2023_dh_baseline_constant_thermflex_lb22p5_dur4_evt1_upper_only_paper_day_ahead`
  - `vienna_ref2023_dh_baseline_constant_thermflex_lb22p5_dur24_evt24_upper_only_proxy_paper_day_ahead`
- Wichtige Modellklarstellung:
  - `0.5 h` wurde **nicht** eingefuehrt
  - der aktuelle `milp_day_ahead` liest `max_flex_duration_h` als `int`
  - auf dem stündlichen Raster ist `1 h` damit die kleinste saubere Dauer
- Wichtige methodische Klarstellung:
  - `lb22p5_dur24_evt24_upper_only_proxy` ist **explizit nur ein Proxy-Fall**
  - er approximiert "nach oben frei, keine globalen Caps"
  - ist aber **kein** mathematisch reiner No-Cap-Fall, weil Recovery-/Cooldown-Logik weiterhin an `max_flex_duration_h` gekoppelt ist
- Neue explizite Artefakte unter:
  - `Optimization/run/results/Vienna/gold/paper_dispatch_comparison_20260403_124056`
  - darin neu:
    - `constant_thermflex_cohort_utilization_hourly.csv`
    - `constant_thermflex_cohort_utilization_summary.csv`
    - `constant_thermflex_cohort_utilization_summary.json`
    - `constant_thermflex_cohort_utilization_summary.md`
    - `constant_thermflex_cohort_utilization.png`
- Neue Analyse-/Codebausteine:
  - `Optimization/run/analysis/build_constant_thermflex_cohort_utilization.py`
  - `dispatch/modes/milp_day_ahead.py`
    - explizite Member-Metadaten und Member-Zeitreihen fuer Thermflex-Replay
  - `Technical_model/energy_system/systems/integrated_energy_system.py`
    - Member-Sidecar sauber bis ins Gold-Raw-Result durchgereicht
- Wichtige Bugfixes dabei:
  - `_thermflex_event_bound_payload(...)` hat ein gebautes Ergebnis-Dict nicht zurueckgegeben
    - korrigiert mit explizitem `return result`
  - `_build_dh_context(...)` hatte nach Patchkonflikt sein `return result` verloren
    - korrigiert
  - der Thermflex-Member-Sidecar am Ende von `integrated_energy_system.py` war zuerst unerreichbar, weil noch ein direktes `return { ... }` davor stand
    - auf expliziten `result`-Pfad korrigiert
  - kein stiller Fallback eingefuehrt; Fehler wurden an der Quelle behoben
- Neue Systembefunde aus dem erweiterten Sensitivitaetsbundle:
  - `lb21p0_dur1_evt1`:
    - `dispatch_operating_cost_eur = 17.653 Mio`
    - `co2_emissions_total_t = 12,380.20`
    - `shifted = 6.607 GWh`
    - `rebound = 5.501 GWh`
  - `lb22p5_dur4_evt1_upper_only` und `lb22p5_dur24_evt24_upper_only_proxy` sind im aktuellen 24h-Slice praktisch identisch
    - `dispatch_operating_cost_eur = 17.657 Mio`
    - `co2_emissions_total_t = 12,716.50`
    - `shifted = 6.168 GWh`
    - Interpretation:
      - die globale Aufweitung auf `24 h / 24 events` bringt unter aktivem Teacher-/Event-Bound-Schnitt hier **keinen** Zusatznutzen
- Neue Kohortenbefunde aus `constant_thermflex_cohort_utilization_summary.md`:
  - viele Kohorten haengen fuer `lb21 / evt1` bereits sichtbar am globalen Duration-/Event-Cap
  - `non_residential_2000_2014` nutzt im aktuellen Winterslice praktisch **gar keine** Flex
  - `residential_2000_2014` gewinnt deutlich von laengeren Dauern:
    - `dur=1h`: `617.8 MWh shifted`
    - `dur=4h`: `734.0 MWh shifted`
    - `dur=6h`: `1504.7 MWh shifted`
    - `dur=8h`: `1522.0 MWh shifted`
  - `residential_1990_2000` zeigt Sattigung:
    - `dur=6h`: `active_cap=0.500`
    - `dur=8h`: `active_cap=0.375`
  - daraus folgt:
    - globale Dauererhoehung hilft einzelnen moderneren Kohorten noch
    - andere Kohorten sind schon durch ihre eigenen Teacher-Bounds oder den Event-Cap gesaettigt

### Konstant-Thermflex: `dur24` bei `lower = 21.0 C`

- Den konstanten Sensitivitaetsblock um zwei explizite 24h-Faelle erweitert:
  - `vienna_ref2023_dh_baseline_constant_thermflex_lb21p0_dur24_evt1_paper_day_ahead`
  - `vienna_ref2023_dh_baseline_constant_thermflex_lb21p0_dur24_evt24_paper_day_ahead`
- Neue Artefakte liegen unter:
  - `Optimization/run/results/Vienna/gold/paper_dispatch_comparison_20260403_131344`
- Wichtige Befunde fuer den 24h-Slice `2023-01-08`:
  - `lb21p0_dur24_evt1` und `lb21p0_dur24_evt24` sind systemweit identisch
  - gegenueber `lb21p0_dur8_evt1` verbessert `dur24` den Fall noch messbar:
    - `dispatch_operating_cost_eur`: `17.487 Mio -> 17.362 Mio`
    - `co2_emissions_total_t`: `12,463.99 -> 12,288.66`
    - `thermflex_shifted_space_heat_kwh`: `6.370 GWh -> 6.714 GWh`
    - `thermflex_peak_change_kw`: `-648.0 MW -> -686.6 MW`
  - Interpretation:
    - ueber `8 h` hinaus kommt bei `lower = 21.0 C` noch Zusatznutzen
    - mehr als `1` Event pro Tag bringt im aktuellen Slice aber **keinen** Zusatznutzen
- Kohortenbefunde aus `constant_thermflex_cohort_utilization_summary.csv`:
  - `non_residential_2000_2014` bleibt auch bei `dur24 / evt24` komplett inaktiv:
    - `cohort_q_heat_ref_kwh = 0` im gesamten Slice
    - `cohort_t_in` bleibt konstant auf `22.5 C`
    - also in diesem Tag keine heizseitige Flex-Nutzung, nicht primär ein Bound-Problem
  - `residential_2000_2014` reagiert auf `dur24` anders als auf `dur8`:
    - `dur8`: `1.522 GWh shifted`
    - `dur24`: `1.201 GWh shifted`
    - also nicht einfach "mehr Dauer = mehr shifted heat", sondern ein anderer Dispatch-/Recovery-Schnitt bei laengerem globalem Spielraum
  - mehrere alte bzw. mittlere Kohorten nutzen `dur24` zusaetzlich, aber weiterhin nur mit `1` Event

### DH-Thermflex: Representative Days, Nichtwohn-Debug und kuratierter Run-Bundle

- Einen kuratierten Ergebnisordner fuer den laufenden DH-Thermflex-Block gebaut:
  - `Optimization/run/results/Vienna/gold/dh_thermflex_run_20260403_140316`
  - Inhalt:
    - `paper_core/`
    - `nonres_2000_2014_debug/`
    - `representative_days/`
    - `teacher_day_plots/`
    - `README.md`
    - `manifest.json`
- Neue Analysebausteine dafuer:
  - `Optimization/run/analysis/dh_thermflex_inputs.py`
  - `Optimization/run/analysis/build_nonres_2000_2014_debug.py`
  - `Optimization/run/analysis/select_vienna_dh_thermflex_representative_days.py`
  - `Optimization/run/analysis/build_energyplus_cohort_day_plots.py`
  - `Optimization/run/analysis/build_dh_thermflex_run_bundle.py`
  - `Optimization/run/analysis/build_constant_thermflex_representative_day_summary.py`
  - `Optimization/run/papers/dh_thermflex/run_vienna_dh_thermflex_bundle.py`
  - `Optimization/run/papers/dh_thermflex/run_vienna_constant_thermflex_representative_day_cases.py`

### Repo-Hygiene: zweite Strukturtranche

- Quellenlayer vereinheitlicht:
  - Root-Ordner `Quellen/` nach `Documentation/Sources/` ueberfuehrt
  - AGENTS-/Coding-Rules-/Doku-Referenzen auf `Documentation/Sources/` nachgezogen
- `run_of_river_hydro` unter `Data/technology_data/run_of_river_hydro/` einsortiert:
  - bestehende Vienna-Unterstruktur beibehalten
  - Importpfade in technischem Modell und Validation nachgezogen
- Wiener DH-Thermflex-Paper-Runner aus dem flachen `Optimization/run/`-Root gebuendelt unter:
  - `Optimization/run/papers/dh_thermflex/`
- Neue README-Layer angelegt:
  - `Optimization/run/README.md`
  - `Optimization/run/papers/README.md`
  - `Optimization/run/papers/dh_thermflex/README.md`
  - `Data/technology_data/run_of_river_hydro/README.md`

### Repo-Hygiene: dritte Strukturtranche

- `Data` weiter geschnitten:
  - Profil-Registry und Profile-Loader jetzt gemeinsam unter `Data/profiles/`
  - fruehere flache Assembly-Dateien jetzt unter `Data/assembly/`
  - neue READMEs und `__init__`-Exports fuer beide Layer angelegt
- `dispatch` weiter geschnitten:
  - `dispatch/core/` fuer Registry und Schemas
  - `dispatch/metrics/` fuer `thermflex_metrics`
  - Importpfade in Modes, Scenarios und IES-Pfad nachgezogen
- generische Runner aus dem flachen `Optimization/run/`-Root nach
  `Optimization/run/runners/` verschoben:
  - `run_optimization.py`
  - `train_surrogate.py`
- offener Aufgabenpfad vereinheitlicht:
  - `TODO.md` jetzt unter `Documentation/Planning/TODO.md`
  - AGENTS-/Coding-Rules-/README-Referenzen entsprechend nachgezogen
- breiter `py_compile`-Smoke fuer die umgezogenen Layer lief sauber; danach lokale `__pycache__`-Artefakte ausserhalb der virtuellen Umgebung wieder entfernt.

### Git-/Legacy-Hygiene: `datafile_Umstellung`

- Der alte Baum `datafile_Umstellung/` war nicht mehr physisch im Workspace vorhanden, sondern nur noch als historischer Git-Index-/Migrationsrest sichtbar.
- Deshalb kein echter Dateimove moeglich; stattdessen:
  - expliziten Legacy-Hinweis unter `legacy/datafile_Umstellung/README.md` angelegt
  - den alten `datafile_Umstellung`-Baum sowie `.idea/` per `git rm --cached` aus dem aktuellen Live-Schnitt herausgenommen
- Ergebnis:
  - die frueheren `AD`-Mischzustaende fuer diesen Altpfad sind verschwunden
  - verbleibender Git-Status ist jetzt deutlich klarer als Unterschied zwischen
    altem tracked Baum und neuer Root-Struktur lesbar

### Nichtwohn-Debug: `non_residential_2000_2014`

- Artefakte unter:
  - `Optimization/run/results/Vienna/gold/dh_thermflex_run_20260403_140316/nonres_2000_2014_debug`
- Ergebnis:
  - `paper_slice_date = 2023-01-08`
  - `paper_slice_space_heat_kwh = 0`
  - `annual_space_heat_kwh = 1.016 TWh`
  - `annual_hotwater_kwh = 0`
  - `n_nonzero_space_heat_days = 29`
  - `peak_space_heat_day = 2023-01-17`
- Einordnung:
  - der Null-Fall am bisherigen Paperslice ist **kein** genereller Kohortenbug
  - `non_residential_2000_2014` hat ueber das Jahr deutlich Raumwaerme
  - `hotwater = 0` ist hier modellseitig gewollt, erklaert aber nicht den Null-Heiztag
  - der bisherige Befund ist also tagesabhaengig und nicht primaer ein `Tmin`-/Event-Cap-Problem

### Representative-Day-Selector fuer Wien 2023

- Artefakte unter:
  - `Optimization/run/results/Vienna/gold/dh_thermflex_run_20260403_140316/representative_days`
- Selektierte Tage:
  - `winter_peak_heat_day = 2023-01-17`
  - `winter_price_spike_day = 2023-01-24`
  - `winter_sunny_heat_day = 2023-12-04`
  - `winter_typical_day = 2023-01-02`
  - `shoulder_typical_day = 2023-10-31`
- Auswahl basiert explizit auf:
  - DH-Waerme
  - Aussentemperatur
  - Solar-/Irradiance-Proxy
  - Day-ahead-Preis
  - Gaspreis
  - CO2-Preis
- Damit ist der bisherige Ein-Tages-Schnitt nicht mehr "einfach irgendein Tag", sondern durch einen expliziten Day-Type-Schnitt ergaenzbar

### EnergyPlus-Kohortenplots

- Artefakte unter:
  - `Optimization/run/results/Vienna/gold/dh_thermflex_run_20260403_140316/teacher_day_plots`
- Pro Kohorte und Teacher-Experiment stehen jetzt Tagesplots bereit fuer:
  - Indoor-/Outdoor-Temperatur
  - Heizleistung
  - interne Gewinne
  - Solar-/Fenstergewinne
  - Transmissions-, Infiltrations- und Ventilationsverluste
- Ziel:
  - thermische Plausibilisierung der Kohorten nicht nur ueber aggregierte Kennzahlen, sondern ueber Tagesverlaeufe

### Representative-Day-Sensitivitaet: Konstanter Thermflex-Fall

- Ergebnisordner:
  - `Optimization/run/results/Vienna/gold/constant_thermflex_representative_day_summary_20260403`
- Kernbefund:
  - es gibt **keine** global dominante Thermflex-Policy ueber alle Tagtypen
  - `lb21p0_dur24_evt1` ist stark auf Preis-/typischen/Schultertagen
  - `constant_no_thermflex` bleibt auf `winter_peak_heat_day` und `winter_sunny_heat_day` bei Cost/CO2 vorne
- Interpretation:
  - die Paper-Hauptaussage sollte nicht "eine universell beste Duration/Event-Policy" sein
  - sauberer ist:
    - Thermflex-Wirkung ist tagtypabhaengig
    - globale Settings bleiben eine modellierende Vereinfachung

### Paper-Anhang: Vienna Building Model Parameters

- Neuen Appendix-Layer angelegt:
  - `Documentation/Appendices/README.md`
  - `Documentation/Appendices/build_vienna_building_parameter_appendix.py`
- Generator schreibt jetzt reproduzierbar:
  - `Documentation/Appendices/vienna_building_model_parameters_appendix.md`
  - `Documentation/Appendices/vienna_building_model_parameters_appendix.docx`
- Inhalt des Anhangs:
  - kohortenspezifische Building-Stock-/Skalierungsparameter
  - archetypspezifische Huelle-/Geometrieparameter
  - archetypspezifische thermische Metadaten
  - kohortenspezifische runtime-abgeleitete Flaechen und effektive Parameter
  - kalibrierte `reduced_order_v1`- und `event_response_v1`-Tabellen
  - globale Heating-Control- und Thermflex-Settings
  - explizite Source-IDs und Literatur-/Quellenverzeichnis
- Wichtige inhaltliche Klarstellung im Appendix:
  - nicht alle aktiven Building-Felder sind gleich stark literaturgestuetzt
  - `solar_multipliers`, `g_glazing`, `g_glazing_shaded` werden explizit als Legacy-Kompatibilitaetsfelder markiert
  - `c_th`-Leiter und Teile der Non-Res-Logik bleiben als pragmatische V1-Annahmen sichtbar statt als voll kalibriert ausgegeben zu werden

### Paper-Anhang: Referenzgebaeude statt Wien-Summen

- `Documentation/Appendices/build_vienna_building_parameter_appendix.py` nachgeschaerft:
  - Table D zeigt jetzt runtime-abgeleitete Referenzflaechen pro Archetyp statt Wien-Gesamtsummen
  - Table E zeigt jetzt `calibrated_v1`-Reduced-Order-Werte sowohl normiert pro `m2` als auch auf das Referenzgebaeude skaliert
- Explizit klargestellt:
  - `residential_*` steht fuer apartment-block-/MFH-artige Referenzgebaeude
  - `non_residential_*` bleibt ein pragmatischer service-/office-artiger V1-Proxy
  - Residential-`U`-Werte sind TABULA-informierte Seed-Werte und **keine** 1:1-TABULA-WebTool-Extraktion
- Appendix-Markdown und `.docx` neu generiert:
  - `Documentation/Appendices/vienna_building_model_parameters_appendix.md`
  - `Documentation/Appendices/vienna_building_model_parameters_appendix.docx`

### Repo-Cleanup: Alte Run-Artefakte entfernt

- Konservativer Speicher-Cleanup im Workspace durchgefuehrt, ohne den aktiven schnellen Surrogat-Cache zu entfernen.
- Geloescht:
  - alte Surrogat-Result-Ordnner `Optimization/run/results/Vienna/surrogate/202602*`
  - alte Surrogat-Result-Ordnner `Optimization/run/results/Vienna/surrogate/202603*`
  - alte Scheduler-Metaordner `Optimization/run/scheduler/meta_202603*`
  - `Technical_model/technologies/buildings/calibration/_vendor/downloads/EnergyPlus-26.1.0-Windows-x86_64.zip`
- Behalten:
  - `Optimization/run/artifacts/surrogates` fuer schnelle Wiederverwendung von Surrogat-Artefakten
  - `Optimization/run/results/Vienna/gold`
  - aktuelle `202604*`-Surrogatlaeufe
- Frei gewordener Speicher:
  - ca. `32.84 GB`

### Externer Betreuer-Update-Stand: PhD-Roadmapgrafik

- Fuer den Pfad `C:\Users\Philipp Thunshirn\Desktop\PhD\Vorgangsweise u Fortschritte\PhD_scope_roadmap_2026-04-10` ein kleines Supervisor-Update-Bundle erzeugt:
  - `phd_scope_roadmap.svg`
  - `phd_scope_roadmap.html`
  - `phd_scope_roadmap.md`
  - `README.md`
- Inhaltlich verdichtet die Grafik den groesseren PhD-Scope:
  - `MedPower 2024` als MADM-/Entscheidungsunterbau
  - `EEEIC 2025` als hochaufgeloeste Komponentenmodellierung
  - `OL2A 2026` als Surrogat-/Multi-Fidelity-Beschleunigung
  - `SEST 2026` als Flexibilitaets- und Trade-off-Erweiterung
  - aktuelles Vienna-DH-Thermflex-Paper als Heat-System-Integrationsschritt
  - finales Ziel als integriertes Vienna-2040-MES mit Strom, Waerme und Mobilitaet

### Repo-Hygiene: erste sichere Aufraeumtranche

- `datafile_Umstellung` geprueft:
  - der Pfad ist aktuell **nicht** mehr als physischer Ordner im Workspace vorhanden
  - sichtbar war er nur noch als Git-Legacy-/Migrationsrest im `git status`
- Den unscharfen Top-Layer `Analysis/data_quality` nach `Data/quality` verschoben:
  - neue README unter `Data/quality/README.md`
  - leer gewordenen Top-Ordner `Analysis/` entfernt
- Root-Tmp-/Smoke-/IDE-Muell entfernt:
  - `.idea/`
  - `.vscode/`
  - `.tmp/`
  - `_tmp_pip/`
  - lose Root-Dateien `_tmp_*`, `tmp_*`, `*_stdout.log`, `*_stderr.log`
- Eine Root-`.gitignore` angelegt, damit derselbe Junk nicht sofort wieder im Repo-Status landet.

### Git-Hygiene: Legacy-Schnitt technisch geschlossen

- Fuer den finalen Git-Schnitt weitere generierte/externe Pfade aus dem Repo-Add ausgeschlossen:
  - `Data/profiles/Vienna/weather/.cache/`
  - `Data/profiles/Vienna/weather/_openmeteo_chunks/`
  - `Technical_model/technologies/buildings/calibration/_vendor/`
  - `Technical_model/technologies/buildings/calibration/_teacher_runs/`
  - `Technical_model/technologies/buildings/calibration/_reduced_order_fits/`
  - `Technical_model/technologies/buildings/calibration/_event_response_fits/`
  - `Technical_model/technologies/buildings/calibration/_smoke/`
- Ziel davon:
  - lange Vendor-Pfade und generierte Wetter-Caches nicht in den Hauptrepo-Stand ziehen
  - generierte Building-Calibration-Artefakte nicht als fachlichen SSOT einchecken
  - den neuen Root-Code sauber gegen den alten `datafile_Umstellung`-Baum aufloesen

### Repo-Hygiene-Smokes nach dem Strukturumbau

- Struktur-/Import-Smoke nach den Umzuegen ausgefuehrt.
- Zwei echte Move-Bugs im `Data/assembly`-Schnitt gefixt:
  - falscher relativer Import auf `Data.assembly.technology_data`
  - falscher relativer Import auf `Data.assembly.economic_data`
- Backward-Compatibility fuer `from Data import data as data` in `Data/__init__.py` explizit wiederhergestellt.
- Danach echten kleinen Wiener DH-MILP-Smoke gestartet.
- Dabei einen weiteren Move-Bug im Hydro-Datenpfad gefunden und gefixt:
  - `Data/technology_data/run_of_river_hydro/Vienna/freudenau.py` zeigte nach dem Move auf `.../Data/Data/profiles/...`
  - Projektwurzel-Aufloesung korrigiert

### Paper-Layer: DH Thermflex Vienna

- Neuen paperspezifischen Documentation-Layer angelegt:
  - `Documentation/Papers/README.md`
  - `Documentation/Papers/dh_thermflex_vienna.md`
- Dort jetzt explizit festgehalten:
  - enger Paperscope
  - kurze Forschungsfragen
  - Fallnamenslogik wie `lb21p0_dur24_evt1`
  - Rolle von `milp_day_ahead` vs. `milp_two_stage`
  - aktuelle Main-Case-Kandidaten
  - verbleibende Restpunkte bis zum fertigen Paper

### Two-Stage Gap Debug: first bridge into stochastic Thermflex replay

- Die `day_ahead -> two_stage`-Luecke fuer den Wiener DH-Thermflex-Paperpfad gezielt debuggt.
- Erster harter Befund:
  - der relevante `biobj_co2_end`-Kandidat loest in `milp_two_stage` bereits mit einem reduzierten Szenario optimal
  - der erste Bruch sass nicht im Solver, sondern im Kopplungsvertrag zum `integrated_energy_system`
  - `milp_two_stage` lieferte bisher nicht denselben member-level Thermflex-Hourly-Export wie `milp_day_ahead`
- In `dispatch/modes/milp_two_stage.py` den fehlenden member-level Export explizit nachgezogen:
  - `thermflex_member_q_heat_kwh`
  - `thermflex_member_q_heat_ref_kwh`
  - `thermflex_member_flex_active`
  - `thermflex_member_event_start`
  - `thermflex_member_temp_violation_degree_h`
  - `thermflex_member_t_in_c`
  - `thermflex_member_event_preheat_extra_kwh`
  - `thermflex_member_event_cutback_shed_kwh`
- Diese Two-Stage-Serien werden jetzt als szenariogewichtete Member-Trajektorien exportiert, damit der gekoppelte Thermflex-Pfad denselben Downstream-Vertrag wie im Day-Ahead-Fall sieht.
- Reproduzierbaren Debug-Runner angelegt:
  - `Optimization/run/papers/dh_thermflex/run_vienna_two_stage_gap_debug.py`
- Reproduzierter Ladder-Befund fuer `biobj_co2_end`:
  - `raw1_red1`: feasible
  - `raw4_red1`: feasible
  - `raw8_red2`: feasible
  - `raw16_red3`: feasible
- Der bisherige offene Restpunkt ist jetzt enger:
  - nicht mehr der Export-/Kopplungsvertrag
  - sondern der volle `48/6`-Schnitt, der aktuell vor allem als Laufzeit-/Skalierungsfrage offen bleibt

### Szenarioreduktion: Settings-Schnitt sauber verdrahtet

- Den Szenarioreduktionspfad im Settings-Layer explizit erweitert:
  - `Settings/dispatch/dispatch.py` traegt jetzt `scenario_feature_keys`
  - aktueller Default:
    - `ambient_temperature_c`
    - `grid_import_price`
    - `district_space_heat_demand`
    - `co2_price_eur_per_tco2`
- `dispatch_distance_metric` ist jetzt nicht mehr nur Deko im Settings-Layer:
  - in `dispatch/scenarios/historical.py` an die Reduktion durchgereicht
  - in `dispatch/scenarios/reduction.py` explizit ausgewertet
  - aktuell unterstuetzt:
    - `standardized_euclidean`
    - `standardized_manhattan`
- Historische CO2-Preise werden im Szenariobau jetzt explizit als Szenarioserie mitgefuehrt:
  - `dispatch/scenarios/historical_data.py`
  - Quelle bleibt die taegliche ETS-Monatsproxyserie aus
    `Data/profiles/common/co2/ets_monthly_daily_proxy_2020_2025.csv`
- Wichtige methodische Einordnung:
  - Strompreis und Wetter bleiben die staerksten hochaufgeloesten Historicals
  - Gas und CO2 sind aktuell taegliche Monats-Proxyserien
  - deshalb ist der neue Default bewusst klein und logisch, nicht maximal breit

### Paper-Manuskript-Layer: `thermflex_paper`

- Unter `Documentation/Papers/thermflex_paper/` einen kuratierten
  Manuskript-Workspace fuer das Wiener DH-Thermflex-Paper angelegt.
- Struktur jetzt explizit nach wissenschaftlichen Hauptteilen getrennt:
  - Titel/Abstract/Keywords
  - Introduction
  - Methods
  - Results
  - Discussion
  - Conclusion
  - Limitations
  - Appendix-Overview
  - Figure/Table-Plan
  - References
- Zusaetzliche saubere Unterlayer angelegt:
  - `figures/`
  - `tables/`
  - `appendix/`
  - `notes/`
  - `manifests/`
- Erste belastbare Manuskriptbausteine direkt vorgeschrieben:
  - `01_introduction.md`
  - `02_methods.md`
- Die beiden Texte verweisen explizit auf:
  - den bestehenden DH-Thermflex-Paperscope
  - die Vienna-/Dispatch-Quellen
  - die Building-Calibration-Quellen
  - den Building-Parameter-Appendix
  - Representative-Day-Resultate
- `Documentation/Papers/README.md` auf den neuen kuratierten Paper-Layer erweitert.

### Two-Stage Gap: `48 -> 6` jetzt operativ geschlossen

- Den bisher offenen vollen `48:6`-Gap-Run fuer `biobj_co2_end` erneut gestartet.
- Vor dem eigentlichen MILP-Lauf einen echten Fehler im historischen Szenariobau gefunden:
  - die ETS-/CO2-Proxydatei wurde ueber den Gaspreis-Loader gelesen
  - dadurch wurde fuer CO2 implizit eine `EUR/MWh`-Spalte erwartet, obwohl die Datei `EUR/tCO2` fuehrt
- In `dispatch/scenarios/historical_data.py` den Preis-Layer sauber getrennt:
  - allgemeiner expliziter Daily-Price-Loader
  - eigener Gas-Wrapper
  - eigener CO2-Wrapper
  - keine stillen Einheitsspruenge und keine heuristischen Fallbacks
- Danach den vollen Run erneut gerechnet:
  - `Optimization/run/papers/dh_thermflex/run_vienna_two_stage_gap_debug.py`
  - Kandidat: `biobj_co2_end`
  - Ladder: `48:6`
  - `milp_two_stage` solve done | termination=`optimal`
  - Block-Walltime rund `2375 s`
- Ergebnis:
  - die Gap-Leiter fuer `biobj_co2_end` ist jetzt bis `raw48_red6` gruen
  - der bisherige Restpunkt "voller `48/6`-Schnitt" ist damit geschlossen

### Paper-/TODO-Hygiene nach dem Two-Stage-Schluss

- Veraltete offene `48:6`-Hinweise aus dem aktiven Paper- und TODO-Layer entfernt bzw. umformuliert.
- `Documentation/Planning/TODO.md` jetzt klar getrennt in:
  - geschlossen:
    - erste wesentliche `day_ahead -> two_stage`-Luecke
    - voller `biobj_co2_end`-Ladder bis `raw48_red6`
  - offen:
    - Paper-Frame fuer `milp_two_stage` als historischer Robustheitscheck
    - Reduced-scenario-Sensitivitaet `1,2,3,6`
    - optionaler zweiter Voll-Recheck fuer `biobj_mid_tradeoff`
- `Documentation/Papers/dh_thermflex_vienna.md` und
  `Documentation/Papers/thermflex_paper/manuscript/02_methods.md` auf denselben
  Methodenstand gehoben.

### Paper-Results-Layer unter `thermflex_paper`

- Unter `Documentation/Papers/thermflex_paper/results/` einen eigenen kuratierten
  Results-Layer fuer das Wiener DH-Thermflex-Paper angelegt.
- Ziel:
  - paperrelevante Ergebnisse an einem Ort sammeln
  - keine grossen Rohartefakte duplizieren
  - Figures und Tables aus einem stabilen Paper-Zwischenlayer statt direkt aus
    verstreuten Gold-Ordnern bauen
- Angelegte Bausteine:
  - `source_manifest.json`
  - `00_source_bundles.md`
  - `01_core_dispatch_results.md`
  - `02_representative_day_results.md`
  - `03_two_stage_results.md`
  - `04_cohort_mechanism_results.md`
  - `05_biobjective_results.md`
- `Documentation/Papers/thermflex_paper/manuscript/03_results.md` zeigt jetzt
  explizit auf
  diesen neuen Results-Layer.
- `Documentation/Papers/thermflex_paper/README.md` dokumentiert den beabsichtigten
  Workflow:
  - Roh-Results
  - kuratierte Results
  - daraus Figures/Tables

### Thermflex-Paper-Layer auf `manuscript/` und kuratierte Hauptfiguren geschnitten

- Die textbasierten Manuskriptdateien im Wiener DH-Thermflex-Paper jetzt sauber
  unter `Documentation/Papers/thermflex_paper/manuscript/` gebuendelt.
- Neuer `manuscript/README.md` dokumentiert den Text-Layer getrennt von
  `results/`, `figures/`, `tables/` und `appendix/`.
- `Documentation/Papers/thermflex_paper/README.md` auf die neue Struktur
  umgestellt.
- `Documentation/Papers/thermflex_paper/results/06_surrogate_status.md`
  angelegt:
  - aktueller Hauptpfad: `surrogate_opt_l96`
  - Holdout-Median `R2 = 0.747`
  - stark fuer mehrere Dispatchmix-/CO2-Ziele
  - schwach fuer `dispatch_operating_cost_eur` und
    `thermflex_shifted_space_heat_kwh`
- `Documentation/Papers/thermflex_paper/manuscript/08_figure_table_plan.md`
  konkretisiert:
  - Figure 1: deterministischer Kernvergleich
  - Figure 2: Representative-Day-Vergleich
  - Figure 3: Kohortenmechanismus
  - optionale Two-Stage-Robustheitsfigur
  - Kern- und Appendix-Tabellenplan
- Drei aktive Figure-Ordner mit `figure.md`-Notizen und kuratierten PNG-Assets
  im Paper-Layer dokumentiert:
  - `fig_01_core_dispatch`
  - `fig_02_representative_days`
  - `fig_03_cohort_mechanism`

### Thermflex-Paper: naechste Aufgaben fuer Surrogatqualitaet und Teacher-Figuren geschärft

- In `Documentation/Planning/TODO.md` den Surrogat-Block fuer den aktiven Wiener
  DH-/Thermflex-Pfad verschaerft:
  - aktueller Holdout-Stand ist als Such-/Rankinghilfe brauchbar
  - aber fuer die Paper-Kern-KPIs noch nicht stark genug
  - insbesondere `dispatch_operating_cost_eur` und
    `thermflex_shifted_space_heat_kwh` bleiben offene Qualitaetsbaustellen
- Ebenfalls als aktiven Paper-Task aufgenommen:
  - ein 2x2-Teacher-/EnergyPlus-Figurenblock fuer die Archetypen
  - Fokus auf `T_in`, Heizen, interne Gewinne, solare Gewinne sowie
  Transmissions-, Ventilations- und Infiltrationsverluste
  - nach weiterer Schaerfung jetzt nicht mehr als Residential-vs-Non-Residential-Kontrast gedacht
  - stattdessen alle 8 Wiener Archetypen sichtbar als Small-Multiples-Raster

### Figures-Layer abgeflacht und Teacher-Flow-Quadranten gebaut

- Den bisherigen Figure-Layer bewusst abgeflacht:
  - keine Figure-Unterordner mehr
  - Assets, Figure-Notizen und paper-spezifische Builder direkt unter
    `Documentation/Papers/thermflex_paper/figures/`
- Bestehende Figure-Dateien entsprechend umbenannt und auf Root-Level verschoben:
  - `fig_01_core_dispatch_comparison.png`
  - `fig_02_representative_day_summary.png`
  - `fig_03_cohort_mechanism.png`
  - plus zugehoerige `fig_*.md`
- Der fruehere 8er-Teacher-Grid bleibt als explorativer Nebenpfad erhalten,
  ist aber nicht mehr die bevorzugte Hauptfigur.
- Neuer paper-spezifischer Builder:
  - `Documentation/Papers/thermflex_paper/figures/build_teacher_flow_quadrants.py`
- Neue lesbarere Teacher-Hauptassets:
  - `fig_00_teacher_flow_quadrant_winter_reference_week.png`
  - `fig_00_teacher_flow_quadrant_winter_cutback_event.png`
- Inhalt dieser neuen Quadranten:
  - alle 8 Wiener Archetypen in denselben Panels
  - farblich nach Archetyp kodiert
  - erste Lesefassung mit:
    - `T_in`
    - `heating`
    - `window solar gains`
    - `total losses`
- `manuscript/08_figure_table_plan.md` und `TODO.md` auf diesen neuen
  flow-basierten Figure-Schnitt aktualisiert.

### Teacher-Referenzplot auf gains/losses/heating fokussiert und alte Figuren archiviert

- Wunschgemaess den Figures-Layer nochmals geschnitten:
  - aktiver Root von `Documentation/Papers/thermflex_paper/figures/` bleibt sehr schlank
  - aeltere oder explorative Figuren liegen jetzt unter `figures/old/`
- Neuer aktiver Teacher-Hauptplot:
  - `fig_00_teacher_reference_flow_comparison.png`
- Neuer paper-spezifischer Builder:
  - `build_teacher_reference_flow_comparison.py`
- Inhalt des neuen Referenzplots:
  - Heizlast ohne Verschiebeevent
  - `internal gains`
  - `window solar gains`
  - `transmission loss`
  - `ventilation loss`
  - `infiltration loss`
  - `total losses`
  - alle 8 Archetypen farblich codiert
- Temperatur bewusst aus dieser Version entfernt, weil sie fuer den aktuellen
  Figurenzweck nicht prioritaer ist.
- `manuscript/08_figure_table_plan.md` auf diesen neuen Teacher-Referenzplot als
  aktiven Figure-0-Kandidaten umgestellt.

### Periodenspezifische Residential-Glazing-Optik in den EnergyPlus-Teacher verdrahtet

- Den Teacher-Solarpfad auf der vorhandenen SSOT weiter geschlossen:
  - `window_typology_class` aus den Wiener Residential-Archetypen wird jetzt
    nicht mehr nur als Metadatum mitgeschleppt, sondern explizit in
    `SimpleGlazingSystem`-Optikparameter fuer den Teacher uebersetzt.
- Neue explizite V1-Konfiguration in
  [building_calibration.py](/c:/Users/Philipp%20Thunshirn/Desktop/PhD/Python%20model/Master/Settings/technical/building_calibration.py):
  - monotone Residential-Zuordnung
    `window_typology_class -> SHGC / visible transmittance`
  - expliziter separater `non_residential`-V1-Glazingmodus statt stiller Fallbacks
- Teacher-Input-Schema und Repo-Resolver erweitert:
  - [schemas.py](/c:/Users/Philipp%20Thunshirn/Desktop/PhD/Python%20model/Master/Technical_model/technologies/buildings/calibration/schemas.py)
  - [from_repo.py](/c:/Users/Philipp%20Thunshirn/Desktop/PhD/Python%20model/Master/Technical_model/technologies/buildings/calibration/from_repo.py)
- EnergyPlus-Teacher nutzt jetzt kohortenspezifische Teacher-Glazingwerte aus dem
  vorbereiteten Input-Bundle statt global `0.6 / 0.6`:
  - [energyplus.py](/c:/Users/Philipp%20Thunshirn/Desktop/PhD/Python%20model/Master/Technical_model/technologies/buildings/calibration/teachers/energyplus.py)
- Den Teacher-Setup-Export danach bewusst neu erzeugt:
  - [teacher_inputs_v1.json](/c:/Users/Philipp%20Thunshirn/Desktop/PhD/Python%20model/Master/Data/profiles/Vienna/weather/calibration_setup/teacher_inputs_v1.json)
- Den aktiven Teacherpfad danach noch mit einem kleinen echten Pilotlauf geprueft:
  - [run_energyplus_teacher_pilot.py](/c:/Users/Philipp%20Thunshirn/Desktop/PhD/Python%20model/Master/Technical_model/technologies/buildings/calibration/run_energyplus_teacher_pilot.py)
  - `residential_pre1975`
  - `winter_reference_week`
  - lief sauber durch und schrieb neue Hourly-/Plausibility-Artefakte
- Wichtige Einordnung:
  - Residential-Solaroptik ist jetzt periodenspezifisch **explizit angedeutet**
  - die numerischen `SHGC`-Werte sind jetzt datenbasierter als **cross-TABULA-
    Proxy** nachgezogen:
    - AT-TABULA fuer die Typenfolge
    - DE/DK/PL-TABULA fuer numerische `g`-Wert-Anker aehnlicher Fenstertypen
  - `visible transmittance` bleibt dabei vorerst ein dokumentierter V1-Proxy
  - `non_residential` bleibt in diesem Punkt weiter ein expliziter globaler V1-Pfad

### Teacher-Referenzlaeufe nach neuer Glazing-Logik neu gerechnet

- Den `winter_reference_week`-Teacherbatch fuer alle 8 Kohorten neu gerechnet:
  - [run_energyplus_teacher_plausibility_batch.py](/c:/Users/Philipp%20Thunshirn/Desktop/PhD/Python%20model/Master/Technical_model/technologies/buildings/calibration/run_energyplus_teacher_plausibility_batch.py)
- Danach die aktive Paper-Figur neu gebaut:
  - [fig_00_teacher_reference_flow_comparison.png](/c:/Users/Philipp%20Thunshirn/Desktop/PhD/Python%20model/Master/Documentation/Papers/thermflex_paper/figures/fig_00_teacher_reference_flow_comparison.png)
- Neuer harter Befund:
  - `window solar gains` differenzieren jetzt auch innerhalb der vier Residential-Perioden klar:
    - `residential_pre1975`: `654.0 kWh`
    - `residential_1975_1990`: `572.5 kWh`
    - `residential_1990_2000`: `430.6 kWh`
    - `residential_2000_2014`: `343.7 kWh`
  - `non_residential` bleibt erwartungsgemaess auf identischem globalen V1-Niveau
  - `internal gains` bleiben ueber alle Kohorten gleich, weil der Nutzungsprofilpfad in V1 weiter global ist

### Kleines periodenspezifisches Fenster-SSOT in den Data-Layer gezogen

- Neues explizites Fenster-SSOT angelegt:
  - [windows.py](/c:/Users/Philipp%20Thunshirn/Desktop/PhD/Python%20model/Master/Data/thermal_archetypes/Vienna/windows.py)
- Inhalt:
  - periodische Residential-Fenstertypologie
  - `n_panes`
  - `glazing_family`
  - `frame_type`
  - `g_value`
  - `visible_transmittance`
  - Quelltyp und Einordnungsnotiz
- Bestehende Teacher-Glazing-Settings jetzt auf dieses Data-SSOT umgestellt:
  - [building_calibration.py](/c:/Users/Philipp%20Thunshirn/Desktop/PhD/Python%20model/Master/Settings/technical/building_calibration.py)
- Auch der Archetypenpfad zieht die Residential-Fenstertypologie jetzt aus demselben Data-SSOT:
  - [thermal_archetypes.py](/c:/Users/Philipp%20Thunshirn/Desktop/PhD/Python%20model/Master/Data/thermal_archetypes/Vienna/thermal_archetypes.py)
- Damit ist die Fensterlogik jetzt sauberer getrennt:
  - Data-Layer = periodische Window-SSOT
  - Settings-Layer = Teacher-Nutzung / Aktivierung

### Fenster-SSOT noch feiner periodenspezifisch ausdifferenziert

- Den neuen Window-SSOT nicht nur auf Typologie + `g` beschraenkt, sondern um
  weitere periodenspezifische Fenstermerkmale erweitert:
  - `window_pane_count`
  - `window_glazing_family`
  - `window_frame_type`
  - `window_has_low_e`
  - `window_has_inert_gas_fill`
  - `window_has_thermal_break`
  - `window_g_value`
  - `window_visible_transmittance`
  - `window_data_source_note`
- Diese Felder haengen jetzt auch explizit im Archetypen- und Teacher-Input-Pfad:
  - [thermal_archetypes.py](/c:/Users/Philipp%20Thunshirn/Desktop/PhD/Python%20model/Master/Data/thermal_archetypes/Vienna/thermal_archetypes.py)
  - [schemas.py](/c:/Users/Philipp%20Thunshirn/Desktop/PhD/Python%20model/Master/Technical_model/technologies/buildings/calibration/schemas.py)
  - [from_repo.py](/c:/Users/Philipp%20Thunshirn/Desktop/PhD/Python%20model/Master/Technical_model/technologies/buildings/calibration/from_repo.py)
- Teacher-Setup danach neu exportiert, damit die neuen Felder in
  [teacher_inputs_v1.json](/c:/Users/Philipp%20Thunshirn/Desktop/PhD/Python%20model/Master/Data/profiles/Vienna/weather/calibration_setup/teacher_inputs_v1.json)
  explizit mitlaufen.

### Teacher-Figuren: nächster sinnvoller Schnitt sind repräsentative Tage

- Den Plotpunkt bewusst nicht halbsauber umgesetzt:
  - ja, ein einzelner 24h-Referenztag ist fuer die Paperlogik zu eng
  - nein, daraus sollte keine improvisierte Mischfigur aus nicht gerechneten Tagen werden
- Als naechster sauberer Schritt festgehalten:
  - Teacher-Faelle explizit fuer repräsentative Tagtypen aufsetzen
  - dann erst die Teacher-Hauptfigur von `winter_reference_week` auf repräsentative Tage umstellen

### Historische 2023-Teacher-Tage fuer die repräsentativen Day-Types vorbereitet

- Den EPW-/Experimentpfad minimal erweitert, damit Teacher-Faelle auf den echten
  2023-Repräsentativtagen laufen koennen:
  - neuer expliziter EPW-Rollenpfad `historical_2023`
  - neue Teacher-Experimente:
    - `repday_winter_peak_heat_day`
    - `repday_winter_price_spike_day`
    - `repday_winter_sunny_heat_day`
    - `repday_winter_typical_day`
    - `repday_shoulder_typical_day`
- Betroffene Dateien:
  - [building_calibration.py](/c:/Users/Philipp%20Thunshirn/Desktop/PhD/Python%20model/Master/Settings/technical/building_calibration.py)
  - [experiments.py](/c:/Users/Philipp%20Thunshirn/Desktop/PhD/Python%20model/Master/Technical_model/technologies/buildings/calibration/experiments.py)
  - [pseudo_epw.py](/c:/Users/Philipp%20Thunshirn/Desktop/PhD/Python%20model/Master/Technical_model/technologies/buildings/calibration/weather/pseudo_epw.py)
- Neuen 2023-EPW gebaut:
  - [vienna_openmeteo_historical_2023_2023.epw](/c:/Users/Philipp%20Thunshirn/Desktop/PhD/Python%20model/Master/Data/profiles/Vienna/weather/epw/vienna_openmeteo_historical_2023_2023.epw)
- Teacher-Setup danach neu exportiert:
  - [experiment_library_v1.json](/c:/Users/Philipp%20Thunshirn/Desktop/PhD/Python%20model/Master/Data/profiles/Vienna/weather/calibration_setup/experiment_library_v1.json)
  - jetzt mit `13` Experimenten statt bisher `8`

### Repräsentative Teacher-Tage gerechnet und Figure 0 darauf umgestellt

- Die 5 neuen repräsentativen Teacher-Tage batchweise fuer alle 8 Kohorten gerechnet:
  - `repday_winter_peak_heat_day`
  - `repday_winter_price_spike_day`
  - `repday_winter_sunny_heat_day`
  - `repday_winter_typical_day`
  - `repday_shoulder_typical_day`
- Danach die aktive Figure-0-Logik von `winter_reference_week` auf diese Day-Types umgestellt:
  - [build_teacher_reference_flow_comparison.py](/c:/Users/Philipp%20Thunshirn/Desktop/PhD/Python%20model/Master/Documentation/Papers/thermflex_paper/figures/build_teacher_reference_flow_comparison.py)
  - [fig_00_teacher_reference_flow_comparison.png](/c:/Users/Philipp%20Thunshirn/Desktop/PhD/Python%20model/Master/Documentation/Papers/thermflex_paper/figures/fig_00_teacher_reference_flow_comparison.png)
- Aktueller Schnitt:
  - je ein Panel pro repräsentativem Tagtyp
  - alle 8 Archetypen gleichzeitig
  - Fokus auf `total losses` als stabilste day-type-uebergreifende Vergleichsgroesse

### Figure 0 auf kompakten Residential-Grid zurückgeschnitten

- Nach Sichtung der repräsentativen Mehrtagesfigur den Schnitt wieder gestrafft:
  - nicht mehr alle 8 Kohorten gleichzeitig
  - nicht mehr `residential` vs `non_residential` in derselben Hauptfigur
- Neuer aktiver Schnitt fuer Figure 0:
  - nur die 4 Residential-Perioden
  - 2x2 Grid
  - pro Periodenpanel zwei Achsen:
    - `heating` + `internal gains` + `solar gains` + `total gains`
    - `transmission` + `infiltration` + `ventilation` + `total losses`
  - Temperatur-/Setpoint-Panel entfernt
- Als Hauptschnitt derzeit ein repräsentativer Wintertag:
  - `repday_winter_typical_day`
- Aktualisiert:
  - [build_teacher_reference_flow_comparison.py](/c:/Users/Philipp%20Thunshirn/Desktop/PhD/Python%20model/Master/Documentation/Papers/thermflex_paper/figures/build_teacher_reference_flow_comparison.py)
  - [fig_00_teacher_reference_flow_comparison.png](/c:/Users/Philipp%20Thunshirn/Desktop/PhD/Python%20model/Master/Documentation/Papers/thermflex_paper/figures/fig_00_teacher_reference_flow_comparison.png)
### Figure 0 mit gemeinsamer y-Skalierung zwischen den Perioden rebuilt

- Die Residential-Grid-Figur so geschaerft, dass die vertikale Achse nicht mehr
  je Panel separat autoskaliert.
- Neuer Vergleichsschnitt:
  - eine gemeinsame y-Skala fuer alle `heating + gains`-Panels
  - eine gemeinsame y-Skala fuer alle `losses`-Panels
- Zweck:
  - aehnliche Kurvenformen bleiben sichtbar
  - Groessenordnungsunterschiede zwischen den Perioden werden nicht mehr
    optisch nivelliert
- Rebuilt:
  - [build_teacher_reference_flow_comparison.py](/c:/Users/Philipp%20Thunshirn/Desktop/PhD/Python%20model/Master/Documentation/Papers/thermflex_paper/figures/build_teacher_reference_flow_comparison.py)
  - [fig_00_teacher_reference_flow_comparison.png](/c:/Users/Philipp%20Thunshirn/Desktop/PhD/Python%20model/Master/Documentation/Papers/thermflex_paper/figures/fig_00_teacher_reference_flow_comparison.png)

### Figure 0 Layout weiter bereinigt

- Legenden aus den Achsen heraus nach rechts aussen verschoben, damit keine
  Kurven mehr ueberdeckt werden.
- Achsentitel der Subplots entfernt, um die Figur ruhiger zu machen.
- Periodentitel vereinfacht:
  - `pre1975`
  - `1975 | 1990`
  - `1990 | 2000`
  - `2000 | 2014`

### Figure 0: finaler Layout-Tweak fuer bessere Lesbarkeit

- Globalen Grafiktitel entfernt.
- Achsenbeschriftungen wieder aufgenommen:
  - `Gain / heating [kW]`
  - `Loss [kW]`
- Legenden- und Tick-Schrift etwas vergroessert.
- Paneltitel ebenfalls vergroessert, damit die Figur im Paperformat stabil lesbar bleibt.

### Figure 0: Legenden entdoppelt und Periodenlabels bereinigt

- Die wiederholten Legenden pro Panel entfernt.
- Stattdessen:
  - eine gemeinsame Gains-Legende fuer die ganze Figur
  - eine gemeinsame Losses-Legende fuer die ganze Figur
- Periodenlabels ebenfalls bereinigt:
  - `<1975`
  - `1975-1990`
  - `1990-2000`
  - `2000-2014`

### Figure 0: Legende komplett aus der Hauptfigur ausgelagert

- Die gemeinsame Figurlegende wieder aus der Hauptgrafik entfernt, weil sie den
  Satzspiegel noch stoert.
- Stattdessen ein separates, transparentes Legend-Asset exportiert:
  - [fig_00_teacher_reference_flow_comparison_legend.png](/c:/Users/Philipp%20Thunshirn/Desktop/PhD/Python%20model/Master/Documentation/Papers/thermflex_paper/figures/fig_00_teacher_reference_flow_comparison_legend.png)
- Gleichzeitig den Abstand zwischen den vier Periodenpanels weiter reduziert,
  damit die Hauptfigur kompakter bleibt.

### Neue Paper-Figur fuer den eigentlichen Thermflex-Mechanismus gebaut

- Neue paper-lokale Figur direkt im Manuskriptpfad aufgebaut:
  - [build_fig_01_use_case_shift_boiler.py](/c:/Users/Philipp%20Thunshirn/Desktop/PhD/Python%20model/Master/Documentation/Papers/thermflex_paper/figures/build_fig_01_use_case_shift_boiler.py)
  - [fig_01_use_case_shift_boiler.png](/c:/Users/Philipp%20Thunshirn/Desktop/PhD/Python%20model/Master/Documentation/Papers/thermflex_paper/figures/fig_01_use_case_shift_boiler.png)
- Schnitt:
  - kein eigener Referenz-Use-Case als Zeile
  - die graue Referenz (`constant_no_thermflex`) ist in jedem Panel eingebettet
  - zwei Use-Case-Zeilen:
    - `upper_only`
    - `full thermflex, dur1`
  - zwei Spalten:
    - `district space heat`
    - `gas boiler dispatch`
- Zweck:
  - zeigen, dass schon reines Vorheizen ohne abgesenkten unteren Setpoint reale
    Lastverschiebung erzeugt
  - und dass sich diese Verschiebung direkt im Gasboiler-Einsatz zeigt
## 2026-04-18 - Teacher-derived runtime space-heat path

- Replaced the active cohort-based runtime `space_heat_member_2d` path in
  [precompute.py](C:/Users/Philipp%20Thunshirn/Desktop/PhD/Python%20model/Master/Technical_model/energy_system/precompute/precompute.py)
  with a new teacher-derived helper in
  [runtime_space_heat.py](C:/Users/Philipp%20Thunshirn/Desktop/PhD/Python%20model/Master/Technical_model/technologies/buildings/runtime_space_heat.py).
- Removed the active heating-side dependency on the deprecated
  `heating_and_cooling.py` path for:
  - cohort runtime precompute
  - HP heating electricity reconstruction
  - thermflex linear input max-heating-power derivation
- Kept the non-cohort legacy branch and cooling branch explicit for now; they are
  not part of the current Vienna cohort paper path.
- Smoke checks:
  - `py_compile` passed for the touched runtime files
  - `space_heat_member_2d` on `2023-01-08` no longer collapses for the full
    former midday window, but two zero hours remain
  - the remaining zeros now come from the calibrated teacher-derived reduced-order
    fit itself, not from the deprecated runtime helper
- Conclusion:
  - architecture improved: active cohort runtime path no longer relies on the
    deprecated building load helper
  - physics issue not fully closed yet: reduced-order calibration still appears
    to understate building losses versus gains for some winter daylight hours

## 2026-04-18 - Direct EnergyPlus air-path export check

- Extended the EnergyPlus teacher export in
  [energyplus.py](C:/Users/Philipp%20Thunshirn/Desktop/PhD/Python%20model/Master/Technical_model/technologies/buildings/calibration/teachers/energyplus.py)
  so the plausibility bundle now requests and exports direct air-path signals
  from EnergyPlus instead of relying only on the old ACH-based proxy.
- Added:
  - `Output:VariableDictionary, IDF` so the teacher run exposes the actual
    variable inventory in `eplusout.rdd`
  - direct EnergyPlus infiltration energy outputs
  - direct ideal-loads outdoor-air sensible outputs for diagnosis
- Pilot run:
  - cohort: `residential_1975_1990`
  - experiment: `repday_winter_typical_day`
- Result:
  - direct `Zone Infiltration Sensible Heat Loss Energy` is present and closely
    matches the old approximation:
    - direct: `30.25 kWh`
    - old approx: `29.26 kWh`
  - direct `Zone Ventilation Sensible Heat Loss Energy` remains `0.0 kWh`
  - direct `Zone Ideal Loads Outdoor Air Sensible Heating Rate` also remains
    `0.0 kWh`
- Interpretation:
  - the old infiltration approximation is not the main problem
  - the old ventilation approximation looks structurally suspect for the current
    teacher setup, because its proxy says `180.37 kWh` while the direct
    EnergyPlus-side diagnostics currently stay at zero
  - next debugging target is therefore the ventilation / outdoor-air modeling
    path in the teacher IDF, not a random floor in the reduced-order fit

## 2026-04-18 - Direct outdoor-air teacher term moved into reduced-order fit

- Added direct `Zone Air Heat Balance Outdoor Air Transfer Rate` export to the
  EnergyPlus teacher bundle and propagated it into the plausibility hourly CSV.
- The reduced-order fit in
  [fit_reduced_order.py](C:/Users/Philipp%20Thunshirn/Desktop/PhD/Python%20model/Master/Technical_model/technologies/buildings/calibration/fit_reduced_order.py)
  no longer uses the old combined ACH-based air proxy as its primary air-side
  truth term.
- New fitting logic:
  - transmission is still fitted against the seed-UA transmission term
  - air-side losses now come from the direct teacher outdoor-air transfer term
  - direct teacher infiltration is used explicitly
  - ventilation is the residual between direct total outdoor-air loss and direct
    infiltration loss
- Batch reruns completed:
  - EnergyPlus teacher plausibility batch for all 8 cohorts on:
    - `winter_reference_week`
    - `winter_free_float_72h`
  - reduced-order fit batch for all 8 cohorts
  - `calibrated_v1` re-exported
- Important result:
  - the old ventilation proxy was indeed structurally wrong for the current
    teacher setup
  - but the problematic `2023-01-08` paper reference case still keeps two
    zero-hour `space_heat_member_2d` / `district_space_heat_demand_ref` points
    at `08:00` and `09:00`
- Conclusion:
  - the fit now uses a much cleaner teacher air-side term
  - the remaining daylight zero issue is no longer explained by the old
    ventilation proxy alone
  - next target is the balance between transmission / gains / reference
    setpoint enforcement in the new runtime heating model
- 2026-04-18
  - Figure fix for the thermflex use-case paper plot:
    - [build_fig_01_use_case_shift_boiler.py](/c:/Users/Philipp%20Thunshirn/Desktop/PhD/Python%20model/Master/Documentation/Papers/thermflex_paper/figures/build_fig_01_use_case_shift_boiler.py)
      now uses `dh_total_demand` on the left axis instead of
      `district_space_heat_demand_ref`.
    - Reason:
      - the paper question was about the actual DH system load, not the isolated
        runtime room-heating reference series
      - `district_space_heat_demand_ref` is currently known to contain implausible
        zero-hour artifacts in the active runtime coupling path
      - `dh_total_demand` stays positive on the same slice and is the safer
        system-level load series for the current paper figure
    - Rebuilt:
      - [fig_01_use_case_shift_boiler.png](/c:/Users/Philipp%20Thunshirn/Desktop/PhD/Python%20model/Master/Documentation/Papers/thermflex_paper/figures/fig_01_use_case_shift_boiler.png)

## 2026-04-18 - Cohort runtime solar path moved off legacy `Solar_gains.csv`

- Problem clarified:
  - the implausible dispatch-side zero hours were not a plot bug
  - they were already present in `space_heat_member_2d`
  - both the old `heating_and_cooling.py` path and the first new
    `runtime_space_heat.py` path reproduced them on the same `2023-01-08` slice
- Root cause isolated:
  - the active cohort runtime path still used the global legacy
    [Solar_gains.csv](/c:/Users/Philipp%20Thunshirn/Desktop/PhD/Python%20model/Master/Data/profiles/Vienna/solar_gains/Solar_gains.csv)
    profile directly
  - this series is already documented in
    [building_calibration_quellen.md](/c:/Users/Philipp%20Thunshirn/Desktop/PhD/Python%20model/Master/Documentation/Sources/building_calibration_quellen.md)
    as a legacy artifact and not as the active solar/weather SSOT
  - because the same solar-gain series hit every cohort, the whole stock could
    collapse together on sunny winter hours
- Implemented fix:
  - added explicit runtime solar settings in
    [thermal.py](/c:/Users/Philipp%20Thunshirn/Desktop/PhD/Python%20model/Master/Settings/technical/thermal.py):
    - `runtime_solar_gains_mode`
    - `runtime_solar_shading_factor`
    - `runtime_solar_frame_fraction`
    - `runtime_solar_non_perpendicular_factor`
  - added cohort-specific runtime solar resolver in
    [runtime_space_heat.py](/c:/Users/Philipp%20Thunshirn/Desktop/PhD/Python%20model/Master/Technical_model/technologies/buildings/runtime_space_heat.py)
    that now derives solar gains from:
    - hourly `irradiance`
    - window-to-floor ratio
    - cohort `g`-value
    - orientation multipliers
    - documented TABULA method factors (`Fsh`, `FF`, `FW`)
  - cohort precompute now stores this explicit member-level solar series in
    [precompute.py](/c:/Users/Philipp%20Thunshirn/Desktop/PhD/Python%20model/Master/Technical_model/energy_system/precompute/precompute.py)
    as `space_heat_solar_member_2d`
  - coupled thermflex inputs in
    [integrated_energy_system.py](/c:/Users/Philipp%20Thunshirn/Desktop/PhD/Python%20model/Master/Technical_model/energy_system/systems/integrated_energy_system.py)
    now use `space_heat_solar_member_2d` instead of one global solar series
- Additional structural fix:
  - `calibrated_v1` export had dropped the newer window metadata
  - [export_calibrated_archetypes.py](/c:/Users/Philipp%20Thunshirn/Desktop/PhD/Python%20model/Master/Technical_model/technologies/buildings/calibration/export_calibrated_archetypes.py)
    now preserves:
    - `window_g_value`
    - `window_visible_transmittance`
    - pane / glazing / frame fields
    - source note
  - `calibrated_v1.json` and `calibrated_v1.py` were re-exported
- Verified outcome:
  - aggregated `space_heat_member_2d` on `2023-01-08` now has `0` zero hours
  - `district_space_heat_demand_ref` in the full `constant_no_thermflex`
    `milp_day_ahead` reference run also has `0` zero hours on the same day
  - critical slice after the fix:
    - `district_space_heat_demand_ref[07:00..12:00]`
      `= [2000442.61, 1930869.66, 969947.51, 1777086.71, 1674375.73, 1544727.73]`
- Paper assets updated:
  - [fig_00_teacher_reference_flow_comparison.png](/c:/Users/Philipp%20Thunshirn/Desktop/PhD/Python%20model/Master/Documentation/Papers/thermflex_paper/figures/fig_00_teacher_reference_flow_comparison.png)
    rebuilt and now explicitly shown in `W/m²`
  - [fig_01_use_case_shift_boiler.png](/c:/Users/Philipp%20Thunshirn/Desktop/PhD/Python%20model/Master/Documentation/Papers/thermflex_paper/figures/fig_01_use_case_shift_boiler.png)
    rebuilt on the repaired dispatch path
## 2026-04-19 - Thermflex Figure 1 shift-plot correction

- Reworked `fig_01_use_case_shift_boiler` left-column logic away from a raw
  `district_space_heat_demand(case) - district_space_heat_demand(reference)`
  line.
- Verified numerically that the raw delta is nearly zero for most of the day on
  the selected slice and then dominated by a horizon-edge drop in the final
  hour, which made the figure visually misleading.
- Restored the left column to the same readable mechanism style as the older
  `constant_thermflex_timeseries` plot:
  - gray reference demand line,
  - colored case demand line,
  - shaded area between reference and case.
- Rebuilt:
  - `Documentation/Papers/thermflex_paper/figures/fig_01_use_case_shift_boiler.png`
- Updated:
  - `Documentation/Papers/thermflex_paper/figures/fig_01_use_case_shift_boiler.md`

## 2026-04-19 - Thermflex representative day shift figure reordered and DH-demand sanity check

- Reordered the active six-panel `upper_only` representative-day figure into a
  cleaner story sequence:
  - `2023-01-17`
  - `2023-02-06`
  - `2023-03-15`
  - `2023-04-24`
  - `2023-10-15`
  - `2023-11-20`
- Rebuilt:
  - `Documentation/Papers/thermflex_paper/figures/fig_02_representative_upper_only_shift.png`

## 2026-04-19 - Teacher flow comparison moved to a colder winter day

- Checked the residential teacher-side `zone_total_heating_rate_w / m²` magnitudes
  against the local appendix anchors and the existing TABULA/OIB source notes.
- Confirmed that the former comparison figure used a mild `2023-01-02` day with
  roughly `2.4..5.0 °C`, which kept the teacher-side heating rates too low for a
  load-oriented paper reading.
- Switched the figure builder away from the mild `repday_winter_typical_day` and
  then away from the too solar-dominated `repday_winter_sunny_heat_day`.
- Active figure cut now uses the last 24 h of `winter_event_reference_96h`
  (`2021-01-18`) as a colder baseline slice with stronger heating rates and no
  implausible midday collapse to zero in the older residential cohorts.
- Relabeled the heating series as `Space-heating rate` to avoid conflating it
  with norm/design heat load.
- Rebuilt:
  - `Documentation/Papers/thermflex_paper/figures/fig_00_teacher_reference_flow_comparison.png`

## 2026-04-19 - Added compact Thermflex paper tables layer

- Created `Documentation/Papers/thermflex_paper/tables/` as a lean table layer
  next to the active figures.
- Added a minimal `README.md` plus three paper-table markdown stubs:
  - `table_01_scenario_overview.md`
  - `table_02_residential_cohort_building_summary.md`
  - `table_03_representative_day_kpi_summary.md`
- Filled `table_03_representative_day_kpi_summary.md` with the current six-day
  `UPPER_1H` values from the active paper overrides:
  - mean outdoor temperature from the active Vienna temperature profile
  - day-slice dispatch KPIs from 24 h gold replays
  - peak reduction from the representative-day demand time series
- Checked the current Vienna DH magnitude against the active runtime setup:
  - building-stock annual total heat anchor: `17.536 TWh/a`
  - active DH share: `0.4`
  - implied runtime DH annual demand: `7.014 TWh/a`
  - full-year runtime DH peak: `3.525 GW`
- External Vienna reference values collected for comparison:
  - official 2023 heat sales statistic: `5.427 TWh/a`
  - city-level current DH magnitude on public info pages: about `6.1 TWh/a`
- Immediate implication:
  - the current runtime annual DH level is already above the public Vienna
    reference range before looking at dispatch behavior
  - with unchanged hourly shape, matching those annual ranges would imply a DH
    peak more around `2.73-3.07 GW` instead of `3.52 GW`

## 2026-04-19 - Vienna DH share reduced to 0.35 in active paper path

- Reduced the active paper day-ahead DH share from `0.4` to `0.35` in:
  - `Optimization/validation/model_validation/overrides/thermflex/vienna_ref2023_dh_baseline_constant_no_thermflex_paper_day_ahead.json`
  - `Optimization/validation/model_validation/overrides/thermflex/vienna_ref2023_dh_baseline_constant_thermflex_lb22p5_dur1_evt1_upper_only_paper_day_ahead.json`
- Rebuilt:
  - `Documentation/Papers/thermflex_paper/figures/fig_02_representative_upper_only_shift.png`
- Full-year check on the updated active reference path:
  - annual DH demand: `6.138 TWh`
  - peak DH demand: `3.084 GW`
  - `p99`: `2.739 GW`
- Key result:
  - lowering the share materially improves the annual level
  - but it does not close the peak gap against the reported Vienna record
    magnitude around `2.4 GW`
  - the residual bias is therefore not only a DH-share issue; the active
    hourly space-heat shape remains too peaky

## 2026-04-19 - Vienna cohort space-heat distribution switched to modeled sector-normalized split

- Added an explicit Vienna building-stock mode
  `space_heat_distribution_mode = sector_total_from_modeled_raw_profiles`.
- Active cohort precompute no longer forces identical annual residential
  `space_heat` intensity across all construction periods.
- New logic:
  - keep the explicit Citiwatt sector totals as the yearly anchor
  - use the modeled raw cohort `space_heat` profiles to distribute that sector
    total across construction periods
  - no hardcoded bauperiodenspezifische `kWh/m²a`
- Result on the active Vienna reference path:
  - `residential_pre1975`: `145.7 kWh/m²a`
  - `residential_1975_1990`: `111.3 kWh/m²a`
  - `residential_1990_2000`: `76.3 kWh/m²a`
  - `residential_2000_2014`: `31.7 kWh/m²a`
- Aggregate effect:
  - residential space-heat total remains anchored at `10.238 TWh/a`
  - active DH annual demand stays `6.138 TWh/a`
  - active DH peak drops further to about `2.941 GW`
- Rebuilt:
  - `Documentation/Papers/thermflex_paper/figures/fig_02_representative_upper_only_shift.png`

## 2026-04-19 - Experimental surrogate path prepared for upper-only biobjective search

- Added explicit `cost + CO2` surrogate optimize overrides for the active
  Vienna `upper_only` paper path with near-unbounded day-level thermflex guard
  rails:
  - `vienna_ref2023_dh_baseline_constant_thermflex_lb22p5_dur24_evt24_upper_only_surrogate_optimize_biobj_smoke.json`
  - `vienna_ref2023_dh_baseline_constant_thermflex_lb22p5_dur24_evt24_upper_only_surrogate_optimize_biobj.json`
- First strict surrogate run failed because no reusable Learning artifact was
  registered for the new family hash.
- Ran explicit native retrain for that family via
  `Learning/scripts/run_retrain.py --execute --force-native`.
- Retrain produced a native model artifact and appended additional truth points,
  but the Learning gate still blocked automatic promotion:
  - pass share improved only to `5 / 11`
  - `dispatch_operating_cost_eur` and `thermflex_peak_change_kw` now pass
  - `co2_emissions_total_t`, `thermflex_shifted_space_heat_kwh`,
    `E_district_heat_pump_thermal_generation_kWh`, and
    `E_district_gas_boiler_generation_kWh` remain below the active gate
- Added explicit experimental forced-model overrides so this blocked model can
  be used transparently for exploratory biobjective runs without changing the
  global gate behavior:
  - `vienna_ref2023_dh_baseline_constant_thermflex_lb22p5_dur24_evt24_upper_only_surrogate_optimize_biobj_smoke_forced_model.json`
  - `vienna_ref2023_dh_baseline_constant_thermflex_lb22p5_dur24_evt24_upper_only_surrogate_optimize_biobj_forced_model.json`
- Checked older gold paper comparison runs:
  - older `upper_only` variants with `share = 0.4` showed much stronger cost
    reductions and stronger space-heat peak shedding
  - those same runs also increased total CO2, so they are not directly a better
    `cost + CO2` story
- Executed both smoke and full experimental forced-model surrogate searches and
  gold-rechecked the representative Pareto points on the active `2023-01-08`
  24 h slice.
- Current-slice reference rerun with the active baseline override
  (`share = 0.35`, updated cohort distribution):
  - `dispatch_cost_eur = 18.899 M€`
  - `co2_emissions_total_t = 12,357.35 t`
- Best gold-rechecked candidates from the full biobjective forced-model run:
  - `biobj_cost_end`: `19.181 M€`, `11,462.15 t`
  - `biobj_mid_tradeoff`: `19.443 M€`, `11,104.71 t`
  - `biobj_co2_end`: `19.759 M€`, `10,603.81 t`
- Immediate implication:
  - on this active slice, `cost + CO2` does produce meaningful CO2 reduction
  - but none of the rechecked `upper_only` candidates beats the current
    reference on cost
  - the older stronger cost wins from the former `share = 0.4` path therefore
    appear tied to the older system state and not to a clean current
    `cost + CO2` improvement

## 2026-04-19 - DH-total peak objective added as dispatch/surrogate SSOT

- Added a new dispatch-facing KPI/objective
  `dh_total_peak_change_kw` to represent the change in the maximum of
  `dh_total_demand` against its reference path.
- The new KPI is now exported consistently through:
  - dispatch diagnostics
  - gold flows / KPI engine
  - surrogate teacher targets
  - reporting / dispatch KPI exports
  - Learning target blocks
- Kept the legacy `thermflex_peak_change_kw` unchanged for space-heat-specific
  diagnostics; the new KPI is additive and explicitly targets the paper-facing
  DH total-demand peak story.
- Added triobjective surrogate overrides for the active Vienna `upper_only`
  search:
  - `vienna_ref2023_dh_baseline_constant_thermflex_lb22p5_dur24_evt24_upper_only_surrogate_optimize_triobj_smoke.json`
  - `vienna_ref2023_dh_baseline_constant_thermflex_lb22p5_dur24_evt24_upper_only_surrogate_optimize_triobj.json`
- Native smoke-family retrain completed, but the Learning gate still blocks the
  model overall; the new `dh_total_peak_change_kw` target itself passes.
- Added transparent experimental forced-model triobjective overrides:
  - `vienna_ref2023_dh_baseline_constant_thermflex_lb22p5_dur24_evt24_upper_only_surrogate_optimize_triobj_smoke_forced_model.json`
  - `vienna_ref2023_dh_baseline_constant_thermflex_lb22p5_dur24_evt24_upper_only_surrogate_optimize_triobj_forced_model.json`
- Verified that the smoke triobjective surrogate optimization runs end-to-end
  with the forced model and recognizes the objective tuple:
  - `dispatch_cost_eur`
  - `co2_emissions_total_t`
  - `dh_total_peak_change_kw`

## 2026-04-21 - Jan-17 triobjective smoke exposes terminal-deviation artifact

- Re-ran the triobjective `upper_only` smoke on a better representative winter
  slice with an internal reference peak:
  - override:
    `vienna_ref2023_dh_baseline_constant_thermflex_lb22p5_dur24_evt24_upper_only_surrogate_optimize_triobj_smoke_jan17.json`
  - slice:
    `2023-01-17 00:00:00` for `24 h`
- The Jan-17 family still remains Learning-gate-blocked overall, but unlike the
  earlier `2023-01-08` slice the new target `dh_total_peak_change_kw` is now
  non-constant in validation and therefore methodically more informative.
- Added a matching explicit forced-model Jan-17 override and updated its
  `validation.holdout.model_id` to the newly trained native artifact:
  - `native_191d80baed9a54214a83cf2c3266725aa3c63de06c52e04906e554f165d370f1`
- Executed the Jan-17 triobjective surrogate smoke with the forced model:
  - run dir:
    `Optimization/run/results/Vienna/surrogate/20260421_135519_vienna_ref2023_dh_baseline_constant_thermflex_lb22p5_dur24_evt24_upper_only_surrogate_optimize_triobj_smoke_jan17_forced_model`
- Gold-rechecked representative Pareto points (`cost_end`, `co2_end`,
  `mid_tradeoff`) and found a sharper mechanism issue:
  - `thermflex_shifted_space_heat_kwh` remains substantial (`~670 MWh`)
  - but `dh_total_peak_change_kw` stays effectively zero for all rechecked
    points
  - `dh_total_demand` matches the reference exactly at the absolute peak hour
    (`hour 4`)
  - almost the entire visible DH-total deviation appears only in the final
    hour, where the current `upper_only dur24 evt24` configuration exploits the
    allowed terminal deviation
- Immediate implication:
  - the new peak objective plumbing is correct
  - but the current quasi-unbounded `upper_only` setup is still not a clean
    peak-shaving experiment
  - before interpreting cost/CO2/peak trade-offs further, the paper path needs
    either stricter terminal handling or an inner-window evaluation that
    prevents end-of-horizon dumping

## 2026-04-21 - Active Vienna paper/experiment overrides aligned to updated gas CHP and boiler efficiencies

- Updated the active Vienna DH paper and Jan-17 triobjective experiment
  overrides to the currently intended gas technology assumptions:
  - `district_gas_chp.eta_el = 0.55`
  - `district_gas_chp.eta_th = 0.30`
  - `district_gas_boiler.eta_th = 0.90`
- Applied this consistently to the active no-thermflex paper baseline, the
  active `upper_only` paper cases, and the Jan-17 triobjective smoke variants.
- Added a first explicit `48 h` inner-window experimental override:
  - `vienna_ref2023_dh_baseline_constant_thermflex_lb22p5_dur24_evt24_upper_only_surrogate_optimize_triobj_smoke_jan17_inner_window48_forced_model.json`
- Important current status of that inner-window path:
  - the override itself is now explicit and reproducible
  - but the surrogate engine still reports `artifact_mismatch` for the `48 h`
    provenance slice, so the actual `48 h` surrogate search still needs either
    a dedicated reusable artifact or a non-surrogate evaluation path

## 2026-04-21 - Gas-boiler-peak objective tested on Mar-15 representative day

- Added a new explicit SSOT KPI/objective `district_gas_boiler_peak_kw` across:
  - dispatch diagnostics
  - coupled IES outputs
  - gold flows / KPI engine
  - surrogate teacher targets
  - Learning target publication
  - reporting / dispatch KPI exports
- Created a simple representative-day surrogate smoke override that minimizes:
  - `dispatch_cost_eur`
  - `co2_emissions_total_t`
  - `district_gas_boiler_peak_kw`
  on `2023-03-15 00:00:00` for `24 h`
- Retrained the corresponding native model family and then ran the smoke
  optimization with an explicit forced-model override:
  - `vienna_ref2023_dh_baseline_constant_thermflex_lb22p5_dur24_evt24_upper_only_surrogate_optimize_triobj_boilerpeak_smoke_mar15_forced_model.json`
- Important interpretation:
  - this Mar-15 smoke run still co-optimizes DH asset sizes inside the active
    design bounds
  - it is therefore not yet a pure "thermflex only on today's fixed system"
    experiment
- Gold recheck of the current fixed-system Mar-15 cases nevertheless clarified
  the active mechanism:
  - `no_thermflex` current system:
    - dispatch cost `13.51 M€`
    - CO2 `9099 t`
    - gas boiler peak `1.369 GW`
    - gas boiler generation `14.01 GWh`
  - `upper_only` current system:
    - dispatch cost `13.34 M€`
    - CO2 `8632 t`
    - gas boiler peak `1.369 GW`
    - gas boiler generation `11.93 GWh`
    - shifted space heat `~1.70 GWh`
  - implication:
    - the active fixed-system `upper_only` case already reduces cost, CO2, and
      total gas-boiler generation on this representative day
    - but it does not reduce the absolute gas-boiler peak because the peak hour
      remains fixed at hour `4`
- Gold rechecks of representative surrogate Mar-15 candidate points showed that
  the current asset co-optimization path does not yet improve that story:
  - the surrogate `cost/boiler-peak` corner increased boiler peak to
    `~1.399 GW`
  - the surrogate `CO2` corner increased both cost and boiler peak further
  - gas CHP generation remained `0` across the checked Mar-15 gold cases, so
    the current tradeoff is not a CHP-shift story on this day

## 2026-04-21 - Vienna fossil peak-boiler economics shifted from pure gas proxy to explicit gas/oil mix

- Updated [vienna.py](/c:/Users/Philipp%20Thunshirn/Desktop/PhD/Python%20model/Master/Data/economic_data/location/vienna.py)
  so `district_gas_boiler` remains one technical dispatch block, but its
  Economics/CO2 proxy now explicitly represents a Vienna fossil peak-boiler mix:
  - `2/3 Erdgas`
  - `1/3 Heizoel extra leicht`
- Added explicit fuel-mix metadata to the Economics SSOT:
  - gas share
  - heating-oil share
  - heating-oil 2023 average price
  - heating-oil LHV proxy
  - mixed direct CO2 factor
- Active mixed-fuel proxy values:
  - `77.4 EUR/MWh_fuel`
  - `0.774 EUR/m3` gas-equivalent dispatch/finance proxy
  - `0.224 tCO2/MWh_fuel`
- Source notes updated in:
  - [dh_economics_quellen.md](/c:/Users/Philipp%20Thunshirn/Desktop/PhD/Python%20model/Master/Documentation/Sources/dh_economics_quellen.md)
  - [wien_und_dispatch_quellen.md](/c:/Users/Philipp%20Thunshirn/Desktop/PhD/Python%20model/Master/Documentation/Sources/wien_und_dispatch_quellen.md)
- Also documented the current gas-CHP limitation:
  the active `district_gas_chp` still uses a fixed `eta_el` / `eta_th` pair,
  not a variable extraction-condensing feasible region.
## 2026-04-21 - Heating-season daily screen for Vienna REF vs upper_only 1h

- Added [screen_vienna_constant_thermflex_heating_season_days.py](/c:/Users/Philipp%20Thunshirn/Desktop/PhD/Python%20model/Master/Optimization/run/analysis/screen_vienna_constant_thermflex_heating_season_days.py) to replay explicit daily 24 h gold slices for `REF` vs `UPPER_1H` across the Vienna heating season (`Oct-Apr` months only).
- The screen uses the active paper overrides directly and evaluates the degenerate lower-bound design through the gold engine, avoiding hidden optimizer passes.
- Persisted the first full screening result bundle under:
  [daily_thermflex_screen_20260421_160246](</c:/Users/Philipp Thunshirn/Desktop/PhD/Python model/Master/Optimization/run/results/Vienna/gold/daily_thermflex_screen_20260421_160246/>)
- Key ranking outcome under the current `2/3 gas + 1/3 Heizöl extra leicht` peak-boiler proxy:
  - strongest joint daily savings days cluster in late winter / mild winter and one mild November day,
  - top joint days are `2023-11-04`, `2023-03-04`, `2023-03-18`, `2023-02-21`, `2023-03-16`, `2023-03-23`,
  - the previously used paper days `2023-03-15` and `2023-11-20` remain decent but are not on the absolute top frontier,
  - `2023-04-24` remains weak for system KPIs despite visible shifting and should likely not stay a main KPI day.
- Added a separate candidate paper figure for the top-savings story without touching the existing representative-day figure:
  - builder: [build_fig_03_top_savings_upper_only_shift.py](/c:/Users/Philipp%20Thunshirn/Desktop/PhD/Python%20model/Master/Documentation/Papers/thermflex_paper/figures/build_fig_03_top_savings_upper_only_shift.py)
  - output: [fig_03_top_savings_upper_only_shift.png](/c:/Users/Philipp%20Thunshirn/Desktop/PhD/Python%20model/Master/Documentation/Papers/thermflex_paper/figures/fig_03_top_savings_upper_only_shift.png)
  - day set now expanded to `2023-01-17`, `2023-02-21`, `2023-03-04`, `2023-03-18`, `2023-03-16`, `2023-03-23`, `2023-04-01`, `2023-02-23`
- Updated [table_03_representative_day_kpi_summary.md](/c:/Users/Philipp%20Thunshirn/Desktop/PhD/Python%20model/Master/Documentation/Papers/thermflex_paper/tables/table_03_representative_day_kpi_summary.md) to the same 8-day top-savings set.

## 2026-04-21 - Gas-CHP V1 method cut documented

- Added [gas_chp_operating_region_v1.md](/c:/Users/Philipp%20Thunshirn/Desktop/PhD/Python%20model/Master/Documentation/Sources/gas_chp_operating_region_v1.md)
  as an explicit method note for the next `district_gas_chp` realism step.
- Defined the preferred V1 direction as a small **piecewise power-heat operating
  region** (`power_led`, `mixed`, `heat_led`) instead of heuristic
  time-varying `eta_el(t)` / `eta_th(t)`.
- This note is intentionally pre-implementation:
  it fixes the modeling direction first, but does not yet change the dispatch.
- Added a concrete DEA-/Balmorel-backed V1 parameter anchor:
  - use `eta_el_cond = 0.55` as the condensing reference point,
  - combine it with DEA extraction coefficients around `Cb = 1.8` and
    `Cv = 0.15`,
  - derive normalized V1 operating points for `power_led`, `mixed`, and
    `heat_led`.
- Important interpretation from this step:
  the active fixed CHP point is already roughly close to the heat-led end of
  the DEA extraction envelope; the missing realism is mainly the power-led
  counter-mode, not an arbitrary stronger heat mode.
- Re-cut the method note after the Vienna CCGT discussion:
  - Balmorel / DEA stay as the **model-form anchor** only,
  - the actual V1 edge points are now explicitly a Wien-/anlagenplausibler
    proxy:
    - `power_led = (eta_el 0.55, eta_th 0.30)`
    - `mixed = (eta_el 0.425, eta_th 0.425)`
    - `heat_led = (eta_el 0.30, eta_th 0.55)`
- Prepared the technical settings SSOT for this future dispatch upgrade in
  [Settings/technical/district_gas_chp.py](/c:/Users/Philipp%20Thunshirn/Desktop/PhD/Python%20model/Master/Settings/technical/district_gas_chp.py):
  - added `operating_mode_model`
  - added explicit `operating_points_v1`
  - kept the active default on `fixed_ratio`, so no runtime behavior changed yet.
- Implemented the first **code-side V1 scaffold** for gas-CHP operating-region support:
  - added fail-fast validation of the gas-CHP operating-region settings in
    [Settings/get_settings.py](/c:/Users/Philipp%20Thunshirn/Desktop/PhD/Python%20model/Master/Settings/get_settings.py)
  - restricted `piecewise_power_heat_v1` explicitly to
    `dispatch.mode='milp_day_ahead'` for now in
    [integrated_energy_system.py](/c:/Users/Philipp%20Thunshirn/Desktop/PhD/Python%20model/Master/Technical_model/energy_system/systems/integrated_energy_system.py)
  - exported the explicit CHP operating-point SSOT into the day-ahead dispatch
    input payload
  - upgraded [milp_day_ahead.py](/c:/Users/Philipp%20Thunshirn/Desktop/PhD/Python%20model/Master/dispatch/modes/milp_day_ahead.py)
    so `district_gas_chp` can run either
    - legacy `fixed_ratio`
    - or explicit `piecewise_power_heat_v1`
    without touching `milp_two_stage` yet.
- Ran a first gold smoke test for `piecewise_power_heat_v1` on `2023-03-04`
  with the active `upper_only dur1 evt1` paper case:
  - the solve is feasible,
  - CHP mode shares are now exported through `raw_results`,
  - but the dispatch picks `power_led` for all 24 hours.
- On that test day the new CHP region is therefore behaviorally identical to
  the legacy fixed-ratio point:
  - identical `dispatch_operating_cost_eur`,
  - identical `co2_emissions_total_t`,
  - identical `district_gas_boiler_peak_kw`,
  - identical CHP electric / thermal / fuel totals.
- Added the missing result transport in
  [integrated_energy_system.py](/c:/Users/Philipp%20Thunshirn/Desktop/PhD/Python%20model/Master/Technical_model/energy_system/systems/integrated_energy_system.py)
  so the optional CHP mode-share matrix and top-level CHP mode metadata now
  survive the full coupled-dispatch export path.
- Tested whether removing `grid_export_revenue` from the dispatch objective
  changes the new CHP-region behavior on `2023-03-04`:
  - it removes the small CHP export (`44.25 MWh`) and slightly reduces CHP
    electric / thermal / fuel output,
  - but `piecewise_power_heat_v1` still stays effectively on `power_led`.
- Added a V1 `power_priority_mode` gate for the piecewise CHP path:
  - `free`
  - `price_spike_gated_v1` with explicit `power_priority_price_quantile`
- Tested `price_spike_gated_v1` on `2023-03-04` with the more DH-relevant
  objective (without `grid_export_revenue`).
  Result: no meaningful change versus `free`; CHP mode choice and system KPIs
  stay effectively identical on the tested top-savings day.
- Conclusion from the current method cut:
  the new CHP operating-region path is technically viable, but it is not yet
  producing a useful paper-side improvement. The active paper path should
  therefore stay on the previous `fixed_ratio` CHP mode unless later tests on
  other days show a clear benefit.
- Checked the current top-savings and trade-off stories against the active
  `upper_only dur1 evt1` and `lb21.0 dur1 evt1` day-ahead paper cases:
  - `upper_only` keeps the more robust system-wide cost/CO2 story,
  - the `1 K` lower-bound case consistently reduces gas-boiler peak and boiler
    energy more strongly, but on the tested top-savings days it also raises
    total cost and CO2 versus `upper_only`.
- First solar-gain pattern check on top-savings days:
  - `2023-03-04` shows clear midday/afternoon positive `dh_total_demand` deltas
    followed by strong evening release, with high midday irradiance.
  - `2023-11-04` also shows strong midday preheat and evening release, again
    with the available irradiance concentrated before the evening reduction.
  - `2023-01-17` remains the clean cold contrast day with essentially no
    visible midday preheat or evening release.
- First cohort/archetype shift check on `2023-03-04`:
  the current model does **not** support the story that modern cohorts shift
  more. On this day the strongest shifted energy per m2 comes from older
  non-residential and pre-1975 residential cohorts, while the newest cohorts
  shift the least.
- 2026-04-21: Harte Mechanismus-Checks fuer den Thermflex-Paperpfad nachgezogen.
  - Solar-Gains-Gegencheck ueber echten Counterfactual mit `thermal.runtime_solar_shading_factor = 0.0` auf `2023-03-04`, `2023-11-04` und `2023-01-17` gerechnet.
  - Befund: Die Top-Savings-Tage verlieren ohne Solar fast den gesamten sichtbaren Mittags-Preheat-/Abend-Release-Mechanismus.
    - `2023-03-04`: `upper_only`-Kostenvorteil faellt von rund `-314 kEUR` auf `-63 kEUR`; CO2-Vorteil von rund `-937 t` auf `-183 t`; verschobene Raumwaerme von rund `3.62 GWh` auf `0.55 GWh`.
    - `2023-11-04`: `upper_only`-Kostenvorteil faellt von rund `-234 kEUR` auf `-42 kEUR`; CO2-Vorteil von rund `-822 t` auf `-149 t`; verschobene Raumwaerme von rund `4.27 GWh` auf `0.70 GWh`.
    - `2023-01-17`: kalter Kontrasttag; Solar spielt deutlich kleinere Rolle, Einsparungen bleiben auch ohne Solar in derselben Groessenordnung.
  - Damit ist die Paper-Hypothese "Solar Gains tragen materiell zum guten Mittags-Preheat-/Abend-Peak-Shaving-Muster bei" jetzt deutlich haerter gedeckt, auch wenn noch kein vollstaendiger strukturkausaler Beweis vorliegt.
  - CO2-Trade-off-Tag `2023-04-23` direkt zerlegt:
    - `upper_only` senkt Kosten leicht (`-42.8 kEUR`), erhoeht aber CO2 (`+362.8 t`).
    - Mechanismus: `district_gas_boiler` sinkt, aber `district_gas_chp` steigt stark; zusaetzlich mehr Stromexport.
    - Also kein generischer "schlechter Thermflex-Tag", sondern ein Tag mit Verlagerung von Boilerwaerme in gasbasierte CHP-Waerme.
  - `1 K lower-bound` gegen `upper_only` auf Top-Savings-Tagen erneut zerlegt:
    - `1 K` reduziert Boiler-Peak und Boiler-Arbeit staerker.
    - Systemisch wird der Fall aber teurer und CO2-intensiver, weil Boiler- und externe Waerme stark in gasbasierte CHP-Waerme verschoben werden.
    - Beispiel `2023-03-04`: gegen `upper_only` rund `+171 kEUR`, `+1746 t CO2`, trotz niedrigerem Boiler-Peak; gleichzeitig starke Zunahme von `district_gas_chp_thermal_generation`.
  - Archetypen-/Kohortenstory explizit gegen alte Ergebnisse geprueft:
    - aktueller `upper_only dur1`-Pfad zeigt hoehere verschobene `kWh` und `kWh/m2` fuer aeltere Kohorten.
    - alte Paper-Bundles zeigen jedoch, dass `residential_2000_2014` vor allem von laengeren Dauern profitiert.
    - damit im Moment kein klarer Bug-Nachweis; wahrscheinlicher ist ein Metrik-/Mechanismusunterschied:
      - alte Kohorten: hoehere Eventenergie / hoeherer kurzfristiger Shift
      - neue Kohorten: geringere Eventenergie, aber hoehere thermische Persistenz / groessere Dauer-Sensitivitaet
- 2026-04-21: Zwei neue Paper-Tabellen fuer die Mechanismusstory abgelegt.
  - [table_04_preheat_timing_solar_contribution.md](/c:/Users/Philipp%20Thunshirn/Desktop/PhD/Python%20model/Master/Documentation/Papers/thermflex_paper/tables/table_04_preheat_timing_solar_contribution.md)
    - zeigt fuer `2023-03-04` und `2023-11-04`, dass der Mittags-Preheat-/Abend-Release-Mechanismus ohne Solar fast zusammenbricht
  - [table_05_residential_cohort_duration_sensitivity.md](/c:/Users/Philipp%20Thunshirn/Desktop/PhD/Python%20model/Master/Documentation/Papers/thermflex_paper/tables/table_05_residential_cohort_duration_sensitivity.md)
    - trennt kurzfristigen `1 h`-Shift von Dauer-/Persistenzsensitivitaet und zeigt damit die modernere Kohortenstory sauberer als eine reine `dur1`-Lesart
  - [table_06_indoor_temperature_response_upper_only.md](/c:/Users/Philipp%20Thunshirn/Desktop/PhD/Python%20model/Master/Documentation/Papers/thermflex_paper/tables/table_06_indoor_temperature_response_upper_only.md)
    - zeigt, dass der aktive `upper_only dur1 evt1`-Fall auf den Top-Savings-Tagen kaum messbare zusaetzliche `T_in`-Erhoehung in den Residential-Kohorten erzeugt; der Shift ist aktuell eher ein System-/Source-Timing-Mechanismus als ein klarer Indoor-Temperaturexkurs
  - [table_07_upper_only_duration_response_top_days.md](/c:/Users/Philipp%20Thunshirn/Desktop/PhD/Python%20model/Master/Documentation/Papers/thermflex_paper/tables/table_07_upper_only_duration_response_top_days.md)
    - zeigt, dass `upper_only` zwar per Setting zeitlich begrenzt ist, die Dauergrenze auf den aktuellen Top-Savings-Tagen aber nur schwach oder gar nicht bindet
  - [table_08_lb21_vs_upper_residential_cohort_shift_top_days.md](/c:/Users/Philipp%20Thunshirn/Desktop/PhD/Python%20model/Master/Documentation/Papers/thermflex_paper/tables/table_08_lb21_vs_upper_residential_cohort_shift_top_days.md)
    - zeigt fuer die grossen Savings-Tage die kohortenspezifischen Shift-Unterschiede zwischen `upper_only` und dem `1 K`-Fall
- 2026-04-22: Ersten Trade-off-Figurenpfad fuer den Thermflex-Paperstrang gebaut.
  - Neue Figure:
    [fig_04_tradeoff_day_map.png](/c:/Users/Philipp%20Thunshirn/Desktop/PhD/Python%20model/Master/Documentation/Papers/thermflex_paper/figures/fig_04_tradeoff_day_map.png)
  - Neuer Builder:
    [build_fig_04_tradeoff_day_map.py](/c:/Users/Philipp%20Thunshirn/Desktop/PhD/Python%20model/Master/Documentation/Papers/thermflex_paper/figures/build_fig_04_tradeoff_day_map.py)
  - Revidierter Zuschnitt nach dem ersten Wurf:
    - nur noch gruppierte Balken, kein oberes Scatter-/Quadrantenpanel
    - klar getrennte Taggruppen:
      - kalter Kontrasttag
      - robuste Savings-Tage
      - Trade-off-/Kink-Tage
    - Balkenmetriken:
      - `cost change [%]`
      - `CO2 change [%]`
      - `district_gas_boiler_generation change [%]`
      - `district_gas_chp_thermal_generation change [%]`
  - Aktuelles 8er-Set:
    - `2023-01-17`
    - `2023-02-21`
    - `2023-03-04`
    - `2023-03-18`
    - `2023-11-04`
    - `2023-03-17`
    - `2023-04-22`
    - `2023-04-23`
  - Wichtiger methodischer Hinweis:
    - die Figure liegt weiterhin auf dem aktiven `upper_only dur1 evt1`-Paperpfad; die `1 h`-Grenze ist also settings-seitig aktiv, auch wenn sie auf einigen Top-Savings-Tagen nur schwach bindet
  - Danach nochmals vereinfacht:
    - `district_gas_chp_thermal_generation` als Balkenmetrik wieder entfernt, weil der aktuelle bereinigte `upper_only`-Pfad dort auf dem gezeigten 8er-Set praktisch keinen Effekt mehr zeigt
    - stattdessen `thermflex_rebound_over_shifted_pct` aufgenommen, weil diese Groesse die Trade-off-Logik auf den April-/Kink-Tagen im aktuellen Pfad deutlich besser erklaert
- 2026-04-22: Sauberen `upper_only dur24 evt24`-Paper-Override als naechsten Hauptpfad vorbereitet.
  - Neuer Override:
    [vienna_ref2023_dh_baseline_constant_thermflex_lb22p5_dur24_evt24_upper_only_paper_day_ahead.json](/c:/Users/Philipp%20Thunshirn/Desktop/PhD/Python%20model/Master/Optimization/validation/model_validation/overrides/thermflex/vienna_ref2023_dh_baseline_constant_thermflex_lb22p5_dur24_evt24_upper_only_paper_day_ahead.json)
  - Er uebernimmt den bereinigten aktuellen Paperpfad:
    - `district_heating.share = 0.35`
    - dispatch objective ohne `grid_export_revenue`
  - und setzt explizit:
    - `max_flex_duration_h = 24`
    - `max_flex_events_per_day = 24`
  - Dieser Override ist jetzt der saubere Kandidat fuer den naechsten Heizperioden-Screen und fuer den erneuten Vergleich `upper_only` vs. `1 K`.
- 2026-04-23: Zwei neue aktive Thermflex-Paperfiguren fuer Ergebnisdarstellung und Solar-Mechanismus gebaut.
  - Neue Outcome-Atlas-Figure:
    [fig_07_flexibility_outcome_atlas.png](/c:/Users/Philipp%20Thunshirn/Desktop/PhD/Python%20model/Master/Documentation/Papers/thermflex_paper/figures/fig_07_flexibility_outcome_atlas.png)
  - Neuer Outcome-Atlas-Builder:
    [build_fig_07_flexibility_outcome_atlas.py](/c:/Users/Philipp%20Thunshirn/Desktop/PhD/Python%20model/Master/Documentation/Papers/thermflex_paper/figures/build_fig_07_flexibility_outcome_atlas.py)
  - Neue Solar-Counterfactual-Figure:
    [fig_08_solar_assisted_shift_counterfactual.png](/c:/Users/Philipp%20Thunshirn/Desktop/PhD/Python%20model/Master/Documentation/Papers/thermflex_paper/figures/fig_08_solar_assisted_shift_counterfactual.png)
  - Neuer Solar-Builder:
    [build_fig_08_solar_assisted_shift_counterfactual.py](/c:/Users/Philipp%20Thunshirn/Desktop/PhD/Python%20model/Master/Documentation/Papers/thermflex_paper/figures/build_fig_08_solar_assisted_shift_counterfactual.py)
  - Beide Builder lesen die vorhandenen Paper-Tabellen und brechen bei fehlenden Pflichtspalten ab.
  - `build_fig_06_cohort_duration_daily_sums.py` wurde so angepasst, dass die aktive Tages-Summen-CSV nach dem Entfernen von Fig. 05 als reproduzierbarer Plot-Input dient.
- 2026-04-23: Den Solar-Counterfactual vorerst wieder aus dem aktiven Figure-Layer genommen.
  - nach `figures/old/` verschoben:
    - [fig_08_solar_assisted_shift_counterfactual.png](/c:/Users/Philipp%20Thunshirn/Desktop/PhD/Python%20model/Master/Documentation/Papers/thermflex_paper/figures/old/fig_08_solar_assisted_shift_counterfactual.png)
    - [fig_08_solar_assisted_shift_counterfactual.csv](/c:/Users/Philipp%20Thunshirn/Desktop/PhD/Python%20model/Master/Documentation/Papers/thermflex_paper/figures/old/fig_08_solar_assisted_shift_counterfactual.csv)
    - [build_fig_08_solar_assisted_shift_counterfactual.py](/c:/Users/Philipp%20Thunshirn/Desktop/PhD/Python%20model/Master/Documentation/Papers/thermflex_paper/figures/old/build_fig_08_solar_assisted_shift_counterfactual.py)
  - Grund:
    - als Tabelle bzw. knappe Seitenanalyse ist der Solar-Strang im aktuellen Manuskript lesbarer als als dritte aktive Mechanismusfigur
- 2026-04-23: Neue Quellen-Redispatch-Figure fuer den aktiven `upper_only dur24 evt24`-Pfad gebaut.
  - Neue Figure:
    [fig_10_source_redispatch_facets.png](/c:/Users/Philipp%20Thunshirn/Desktop/PhD/Python%20model/Master/Documentation/Papers/thermflex_paper/figures/fig_10_source_redispatch_facets.png)
  - Neuer Builder:
    [build_fig_10_source_redispatch_facets.py](/c:/Users/Philipp%20Thunshirn/Desktop/PhD/Python%20model/Master/Documentation/Papers/thermflex_paper/figures/build_fig_10_source_redispatch_facets.py)
  - Exportierte Summary:
    [fig_10_source_redispatch_facets.csv](/c:/Users/Philipp%20Thunshirn/Desktop/PhD/Python%20model/Master/Documentation/Papers/thermflex_paper/figures/fig_10_source_redispatch_facets.csv)
  - Inhaltlicher Befund:
    - auf dem aktiven Pfad wird der Nutzen an starken Savings-Tagen sichtbar ueber den Gas-Peak-Boiler erzielt
    - die `district_gas_chp_thermal_generation` bleibt auf den geprueften Tagen nahezu unveraendert
    - die Figur taugt damit weniger als "CHP-Nivellierung"-Nachweis, aber gut als saubere Aussage, dass die aktuelle Savings-Story vor allem Boiler-Entlastung und nicht CHP-Reshaping ist
- 2026-04-23: Bereinigten GitHub-Snapshot des aktuellen Repos nach `MuluundTreviin1130/Master` gepusht.
  - dafuer eine frische Exportkopie nur aus getrackten plus nicht-ignorierten Dateien gebaut
  - alte Run-Artefakte, grosse lokale Ignored-Outputs und die `old`-Paper-Unterordner dabei bewusst nicht in den Push genommen
  - Ziel war nicht ein "vollstaendiges lokales Laufwerk", sondern ein schlanker, pushbarer Repo-Stand ohne die teuren historischen Run-Bloecke
- 2026-04-23: Den Heizperioden-Screener auf den aktiven `upper_only dur24 evt24`-Pfad gehoben und einen neuen Mechanismus-Bundle-Runner gebaut.
  - [screen_vienna_constant_thermflex_heating_season_days.py](/c:/Users/Philipp%20Thunshirn/Desktop/PhD/Python%20model/Master/Optimization/run/analysis/screen_vienna_constant_thermflex_heating_season_days.py)
    - zeigt jetzt explizit auf den aktiven `dur24 evt24`-Override
    - schreibt kuenftig `daily_thermflex_screen_dur24_*`
    - traegt Solar-/Irradiance-Proxy und korrektes Flex-Label mit
  - Neuer Analyse-Builder:
    [build_vienna_constant_thermflex_mechanism_bundle.py](/c:/Users/Philipp%20Thunshirn/Desktop/PhD/Python%20model/Master/Optimization/run/analysis/build_vienna_constant_thermflex_mechanism_bundle.py)
  - Neuer Ergebnisordner:
    [paper_mechanism_bundle_20260423_211704](/c:/Users/Philipp%20Thunshirn/Desktop/PhD/Python%20model/Master/Optimization/run/results/Vienna/gold/paper_mechanism_bundle_20260423_211704)
  - Der Bundle zieht aus dem aktiven `dur24`-Screen drei Dinge konsistent aus demselben Pfad:
    - systematische Tagklassen (`best_joint_savings`, `robust_savings`, `cold_contrast`, `co2_tradeoff`, `late_season_near_neutral`)
    - Solar-Bin-Summary ueber die ganze Heizperiode
    - Residential-Kohortenbeitraege je ausgewaehltem Tag in `Wh/m2` plus `max Delta T_in`
  - Erste neue Lesart aus dem Bundle:
    - hoehere Solar-Bins erhoehen im Mittel die verschobene Waerme deutlich
    - die mittleren Cost-/CO2-Vorteile sind aber im hohen Solar-Bin nicht maximal, weil dort viele spaete Schultertage mit sichtbarer thermischer Aktivitaet, aber fast ohne Systemnutzen liegen
    - auf den ausgewaehlten Tagen dominieren bei `shifted Wh/m2` weiterhin die aelteren Residential-Kohorten; die moderne Kohorte `2000_2014` liegt besonders auf den Top-Savings-Tagen klar darunter
- 2026-04-23: Vollstaendigen aktiven `upper_only dur24 evt24`-Heizperioden-Screen neu gerechnet.
  - Neuer Full-Rerun:
    [daily_thermflex_screen_dur24_20260423_213718](/c:/Users/Philipp%20Thunshirn/Desktop/PhD/Python%20model/Master/Optimization/run/results/Vienna/gold/daily_thermflex_screen_dur24_20260423_213718)
  - Laufzeit grob:
    - `212` Heiztage
    - jeweils `REF` plus `UPPER_24H`
    - Gesamtlauf in dieser Session rund `41 min`
  - Der frische Rerun ersetzt den aelteren `dur24`-Screen als operativen Analysepfad fuer die naechsten Paper-Schritte.
  - Wichtige aktuelle Lesart aus dem neuen Full-Rerun:
    - Top-Joint-Day bleibt `2023-11-04`
    - weitere starke Tage verschieben sich leicht, z. B. jetzt `2023-11-06`, `2023-02-21`, `2023-02-23`, `2023-10-23`
    - die aktuellen `dur24`-Savings sind insgesamt konservativer als manche aelteren Zwischenstaende
    - mehrere starke Tage zeigen im aktuellen Pfad `rebound_over_shifted = 0 %`, also keine einfache "alles kommt als voller Rebound zurueck"-Story
- 2026-04-23: Neue Paper-Tabellen aus dem frischen Mechanismus-Bundle gebaut.
  - Neuer Bundle-Stand auf Basis des frischen Full-Reruns:
    [paper_mechanism_bundle_20260423_221857](/c:/Users/Philipp%20Thunshirn/Desktop/PhD/Python%20model/Master/Optimization/run/results/Vienna/gold/paper_mechanism_bundle_20260423_221857)
  - Neuer Table-Builder:
    [build_mechanism_tables_from_latest_bundle.py](/c:/Users/Philipp%20Thunshirn/Desktop/PhD/Python%20model/Master/Documentation/Papers/thermflex_paper/tables/build_mechanism_tables_from_latest_bundle.py)
  - Neue Tabellen:
    - [table_10_mechanism_day_classes_upper_only_dur24.md](/c:/Users/Philipp%20Thunshirn/Desktop/PhD/Python%20model/Master/Documentation/Papers/thermflex_paper/tables/table_10_mechanism_day_classes_upper_only_dur24.md)
    - [table_11_solar_bin_summary_upper_only_dur24.md](/c:/Users/Philipp%20Thunshirn/Desktop/PhD/Python%20model/Master/Documentation/Papers/thermflex_paper/tables/table_11_solar_bin_summary_upper_only_dur24.md)
    - [table_12_selected_day_residential_cohort_intensity_upper_only_dur24.md](/c:/Users/Philipp%20Thunshirn/Desktop/PhD/Python%20model/Master/Documentation/Papers/thermflex_paper/tables/table_12_selected_day_residential_cohort_intensity_upper_only_dur24.md)
  - Inhaltlicher Mehrwert:
    - `table_10` trennt jetzt sauber robuste Savings-Tage von kaltem Kontrast und spaeten Trade-off-/Near-neutral-Tagen
    - `table_11` zeigt explizit die neue Solar-Lesart:
      - mehr Solar -> mehr verschobene MWh
      - aber mittlere KPI-Vorteile sind im `mid solar`-Bin am staerksten, nicht im `high solar`-Bin
    - `table_12` zeigt fuer die ausgewaehlten `dur24`-Tage die kohortenspezifische Intensitaet in `Wh/m2` plus `max Delta T_in`
