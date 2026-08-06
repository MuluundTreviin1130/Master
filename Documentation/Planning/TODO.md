# TODO

## Active

- [ ] Follow-up after HP MILP COP fix (2026-08-06): gate remaining central DH design
  bounds (`district_thermal_storage_kwh_th`, wood/biomass/gas/biogas/geothermal, …) by
  `technology_activation` in `Settings/problem/bounds.py` so inactive techs cannot
  accumulate CAPEX in Gold/teacher evaluations. HP MILP asset capacity is already
  zeroed in IES; bounds gating is still open for the broader DH set.

- [ ] ThermFlex-Paper: Two-stage-MILP als methodischen Unsicherheits-/Preis-Pfad festziehen:
  - klaeren, ob `milp_two_stage` mit historischen Preis-/Wetter-Szenarien nur als Robustheitscheck oder als eigener Sensitivitaetsblock berichtet wird
  - Settings-Vertrag fuer `stochastic_enabled`, historische Preisquellen, Szenarioanzahl und Reduktion dokumentieren
  - gegen deterministischen `milp_day_ahead` abgrenzen, damit historische Preiszeitreihen und historische Preisunsicherheit nicht vermischt werden

- [ ] ThermFlex-Paper: Surrogatbasierte Sensitivitaetsanalyse als Auswertungsdesign festziehen:
  - Hauptblock: ThermFlex-Policy, Duration und Rebound-/DH-Bus-Tau (`tau = 2/4/8/12`)
  - Wetterblock: kalte Wintertage, Shoulder-Tage, milde Low-Load-Tage und CHP-switching Tage
  - Economic-Block: Strompreis-, Gaspreis- und ggf. CHP-electric-value-Regime; Emissionsfaktoren bleiben fix
  - neue Truth gezielt ueber `Learning/datasets/` wiederverwendbar machen, nicht als isolierte Run-Artefakte auswerten

- [ ] ThermFlex-Paper: Main-Paper-Tabellen schlank halten und bevorzugt mit MILP-Truth belegen:
  - Kern-Tabellen im Paper auf ca. 3-4 Tabellen begrenzen; Detailraster und Zusatz-KPIs ins SI schieben
  - zentrale Ergebnistabelle als ein gemeinsamer Block aufsetzen:
    - zuerst `Days`
    - dann `Weeks`
    - unten `Heating period`
  - Spalten fuer die Haupttabelle:
    - `Use case`
    - `Relaxation`
    - `Duration [h]`
    - `Evaluation window`
    - `Window ID`
    - Kosten- und CO2-Deltas jeweils prozentual **und** absolut
    - `shifted heat`
    - `rebound heat`
    - `rebound / shifted`
    - `peak change`
  - `comfort violation` und `source` nicht in die Main-Result-Tabelle ziehen
  - `best day` fuer Prozentstory nicht ueber instabile Tages-Prozentmaxima definieren; stattdessen robuster Selektor mit Mindest-Referenzkosten oder Pareto-/Window-Regel
  - aktuelle Luecke: fuer `upper+lower 2K` fehlt noch ein sauberer Full-Heating-Period-Screen; vorhandener `lb20p5_dur4_evt24_20260513_partial` ist nur Partial-Truth (`2023-01-01` bis `2023-04-09`)
  - Overnight-Run vorbereiten:
    - `upper+lower 2K` fuer `dur1/4/8/12`
    - gleiche Day-/Week-/Heating-period-KPI-Exports wie fuer die 1K-/upper-only-Faelle
    - danach Main-Tabelle mit konsistenten Vollperiodenwerten neu befuellen
  - Use-case-/Methodentabelle: Policy-Familie, upper-only vs. upper+lower, Relaxation, Duration, `tau = 4` als Main-Figure-/Main-Table-Basis
  - Surrogat-Validation-Tabelle: R2 je KPI-/Use-case-Familie dokumentieren; Surrogat primaer fuer tau-/duration-/month-/price-Sensitivitaeten verwenden
  - `best day` vorab ueber eine klare Regel definieren, z.B. Pareto-gutes Kosten-/CO2-Ergebnis bei akzeptablem Rebound, Peak und Komfort, damit die Auswahl nicht wie Cherry-Picking wirkt

- [ ] ThermFlex-Paper: Sensitivitaetsquadrant / Performance-Map als naechsten Figure-Block konkretisieren:
  - bestehende Use-case-Trade-off-Story aus dem Scatter nicht doppeln, sondern klar von der eigentlichen Sensitivitaetsaussage trennen
  - bevorzugter Aufbau aktuell:
    - Scatter/Quadrant fuer Kosten- vs. CO2-Ergebnisraum
    - genau **eine** tau-duration-Heatmap statt doppelter Heatmap
    - Tornado fuer Treiber-Ranking inkl. Preisannahmen (`gas`, `electricity`, `CO2`, ggf. `CHP electric value`)
    - optional Spider/Radar nur fuer wenige repraesentative Strategieprofile
  - Strategieprofile nicht willkuerlich waehlen, sondern als repraesentative Punkte aus dem Ergebnisraum:
    - `baseline`
    - `conservative`
    - `cost-oriented`
    - `CO2-oriented`
    - `balanced`
  - bei jeder spaeteren Sensitivitaetsfigur die zugehoerige Surrogatguete / R2 je KPI-Familie mitfuehren

- [ ] Fig. 12 naechsten Kandidaten selektiv rendern, nicht alle Varianten starten:
  - Dec-Mar-Wochenscreen mit `event_preheat_peak_bound_multiplier = 1.50` ist abgeschlossen
  - Output: `Documentation/Papers/thermflex_paper/figures/fig_12_dec_mar_multiplier15_week_screen.csv`
  - bester All-KPI-Kandidat ist Woche ab `2023-03-05` und wurde als `march_peak_reduction` gerendert:
    - Cost `-0.715 %`, CO2 `-0.721 %`
    - Peak-Boiler-Energie `0.177 -> 0.034 GWh` (`-80.9 %`)
    - Peak-Boiler-Peak `53.7 -> 33.8 MW` (`-37.0 %`)
    - Plot: `Documentation/Papers/thermflex_paper/figures/fig_12_march_peak_reduction_dispatch_shift.png`
    - CSV: `Documentation/Papers/thermflex_paper/figures/fig_12_march_peak_reduction_dispatch_shift.csv`
  - `2023-02-26` ggf. als Zusatzcheck nutzen, wenn mehr absolute Boiler-Energie wichtiger ist als starke prozentuale Reduktion
  - Dezemberwochen nur als Sensitivitaet betrachten: sie reduzieren Boiler absolut, erhoehen aber meist heat-allocated CO2 leicht
  - `tau = 2 h`-Sensitivitaet fuer `2023-03-05` wurde als `march_peak_reduction_tau2` ergaenzt und gerendert:
    - Cost `-2.687 %`, CO2 `-2.560 %`
    - Peak-Boiler-Energie `1.480 -> 0.485 GWh` (`-67.2 %`)
    - Peak-Boiler-Peak `238.6 -> 122.2 MW` (`-48.8 %`)
    - Plot: `Documentation/Papers/thermflex_paper/figures/fig_12_march_peak_reduction_tau2_dispatch_shift.png`
    - CSV: `Documentation/Papers/thermflex_paper/figures/fig_12_march_peak_reduction_tau2_dispatch_shift.csv`
  - naechster Schritt:
    - entscheiden, ob `tau = 2 h` als Fig.-12-Sensitivitaet/Alternativplot genutzt wird oder ob der Basiscase bei `tau = 4 h` bleibt
    - zusaetzlichen Boiler-Penalty nur als nachgelagerte Sensitivitaet pruefen, falls `tau = 2 h` fachlich nicht tragfaehig ist
  - Tau-2-Winterscreen fuer Dezember, Januar und Februar ist abgeschlossen:
    - Screen: `Documentation/Papers/thermflex_paper/figures/fig_12_tau2_winter_week_screen.csv`
    - bester Winter-Kompromiss ist `2023-02-26`
    - Plot: `Documentation/Papers/thermflex_paper/figures/fig_12_february_peak_reduction_tau2_dispatch_shift.png`
    - CSV: `Documentation/Papers/thermflex_paper/figures/fig_12_february_peak_reduction_tau2_dispatch_shift.csv`
    - KPIs: Cost `-1.620 %`, CO2 `-1.571 %`, Boiler `3.646 -> 2.455 GWh`, Peak `262.2 -> 230.5 MW`
    - offene Entscheidung: Februar `tau=2` wirkt winterlicher und hat mehr absolute Boiler-Energie; Maerz `tau=2` hat staerkere Peak- und prozentuale Boiler-Reduktion
  - Februar-`tau=2` Boiler-OPEX-Sensitivitaet ist abgeschlossen:
    - Screen: `Documentation/Papers/thermflex_paper/figures/fig_12_february_tau2_boiler_opex_sensitivity_screen.csv`
    - gerenderter Mittelweg: `february_peak_reduction_tau2_boiler_opex30`
    - Plot: `Documentation/Papers/thermflex_paper/figures/fig_12_february_peak_reduction_tau2_boiler_opex30_dispatch_shift.png`
    - CSV: `Documentation/Papers/thermflex_paper/figures/fig_12_february_peak_reduction_tau2_boiler_opex30_dispatch_shift.csv`
    - KPIs: Cost `-1.927 %`, CO2 `-1.382 %`, Boiler `3.646 -> 1.586 GWh`, Peak `262.2 -> 175.7 MW`
    - offene Entscheidung: `+30 EUR/MWh_th` als dokumentierte Peak-/Cycling-Sensitivitaet nutzen oder `+50 EUR/MWh_th` nur als obere Sensitivitaet nachrendern

- [ ] Review-Paper "Surrogate models for MOO of multi-energy systems"
  (`Documentation/Papers/review_surrogate_modeling/`):
  - [x] Ordnerstruktur, READMEs, raw Scopus-Export, Tier-A/B-Filter,
    OpenAlex-Anreicherung, Manuskript-Skelett, Zitatselector
  - [x] Frueheren MOO-/Multicriteria-Export aus Downloads importiert und
    als `raw/moo_multicriteria_scopus_export_2026-05-06.bib` gesichert
  - [x] Kombinierte Bibliografie `review_mes_moo_surrogates.bib` gebaut:
    2906 DOI-/Key-deduplizierte Eintraege, 0 doppelte Cite-Keys
  - [x] Manuskripttitel/Abstract und Bib-Pfad auf den verengten Scope
    Surrogates x MOO x MES umgestellt
  - [x] Sektionen 1-3 (Introduction, Background, Taxonomy) ausformuliert
    mit 103 unique Cite-Keys (alle bib-validiert)
  - [x] Story-aligned Paper-Library `paper_library/` aufgesetzt:
    - `select_paper_library.py` als deterministisches Auswahltool
    - `review_paper_library.bib` (260 Eintraege, alle 103 Mandatory-Cites enthalten)
    - `review_paper_library_manifest.csv` (per-paper Provenance + Bucket)
    - `review_paper_library_buckets.csv` (Long-Format Bucket -> cite_key)
    - `review_paper_library_citation_plan.md` (pro Sektion sortierte Cite-Keys, `*` markiert bereits zitierte)
    - 27 Story-Buckets (B01_cornerstone_reviews ... B27_mcdm), 1:1 zu den Manuskriptsektionen 1-9
  - [ ] Sektionen 1-3 stilistisch/fachlich auf den neuen Scope
    Surrogates x MOO x MES zuschneiden (Material bleibt, aber Fokus enger)
  - [x] Sektionen 4-9 (DoE, Integration Patterns, Validation,
    Applications, Open Challenges, Conclusion) ausformuliert:
    - Sektion 4 `04_training_data_doe.tex` -- Datenquellen, statische
      Designs, adaptive Sampling, Multi-Fidelity, energy-data-Pitfalls
    - Sektion 5 `05_integration_patterns.tex` -- Fuenf-Pattern-
      Klassifikation P1/P2/P3/P4/P5 als cross-cutting framework
    - Sektion 6 `06_validation_decision_aware.tex` -- sechs
      Diagnostik-Klassen, RMSE-zu-Regret-Argumentation
    - Sektion 7 `07_application_evidence_map.tex` -- pro Domain
      dominante Patterns + Cites + Synthese
    - Sektion 8 `08_open_challenges.tex` -- sechs konkrete
      Forschungsrichtungen
    - Sektion 9 `09_conclusion.tex` -- knappe Zusammenfassung
    - Appendix `appendix.tex` -- Search Strategy + Run-Statistiken
    - 233 Mandatory-Cites aus den 9 Sektionen + Appendix; 260 Library-
      Eintraege; Voll-Coverage-Check 0 missing
  - [x] T1-T7 Uebersichtstabellen befuellt (abstract-/metadatengestuetzt,
    fuer Submission analog zu Sektion 4-9 volltextzupruefen):
    - T1 Taxonomy: 10 Surrogat-Familien mit Output, Optimizer-Compat,
      Strengths/Failure Modes/Where-it-dominates + Cite-Refs
    - T2 Task-x-Role-Matrix: 8 ESM-Tasks x 5 Patterns (P1-P5),
      `$\star$` markiert dominantes Pattern pro Zeile
    - T3 Training/DoE: 9 Strategien (LHS, Sobol, FD, adaptive,
      active learning, multi-fidelity, transfer, synthetic,
      historical) mit Surrogat-Pairing + Cite-Refs
    - T4 Validation: nun mit Cite-Refs pro Metrik / Test-Design
      (Standard-/Decision-Aware-/Test-Designs, dreigliedrig)
    - T5 Integration Patterns: P1-P5 mit Solver Layer, Safety Hooks,
      Typical Pitfalls + Cite-Refs
    - T6 Evidence Map: deterministischer Builder
      `tables/build_table_T6_evidence_map.py` rendert eine
      `longtable` aus `paper_library/review_paper_library_manifest.csv`
      (260 Eintraege; Sortierung year DESC, citations DESC, key)
    - T7 Related Reviews (Meta-Review): jetzt 17 verifizierte
      Reviews in vier Block-Gruppen (Surrogate / MES / MOO /
      ESM-Optimization + Bibliometric); drei Falsch-Klassifikationen
      (`Xiao2018`, `Cao2023`, `Perera2019191`) durch Abstract-Audit
      identifiziert und entfernt; 10 neue Reviews aus Domain- und
      Bibliometric-Suche ergaenzt (`Tan2026`,
      `agha_kassab_comprehensive_2024`,
      `nallolla_multi-objective_2023`, `malla_sg_optimization_2024`,
      `salgueiro_multi-objective_2019`, `vahidinasab_overview_2020`,
      `Conti2026`, `arar_tahir_scientific_2023`,
      `batista_optimizing_2023`, `velasquez_intelligence_2023`)
  - [x] Sektion 2 "Related reviews and the gap addressed by this
    work" eingefuehrt; bestehende Sektionen 02-09 zu 03-10
    renumeriert; main.tex und main_overleaf_rser.tex entsprechend
    angepasst; nach T7-Erweiterung ueberarbeitet (Block-Paragraphen
    pro Domain + drei strukturelle Beobachtungen am Ende)
  - [x] Strikten Review-Klassifikator als reproduzierbares
    Audit-Werkzeug `references/scan_review_candidates.py` angelegt:
    Title + Abstract + Keyword-Signale, Domain-Tagging
    (surrogate / moo / mes / esm_opt / off_topic), strict vs weak
    Trennung; ergibt 22 strict + 10 weak in-scope Hits aus 2906
    Eintraegen
  - [x] `select_paper_library.py`: `collect_mandatory_cites`
    scannt jetzt zusaetzlich `tables/*.tex`, damit Cite-Keys, die
    nur in Tabellen-Files leben (z.B. T7-Reviews), automatisch
    als mandatory eingelesen werden
  - [x] ``match_literatur_pdfs_to_bib.py``: Ordner ``Literatur/<section>/``
    rekursiv mit ``review_paper_library.bib`` abgleichen (DOI +
    Fuzzy-Titel/Autoren); Artefakte ``_tmp_pdf_author_title_match_*.csv/json``
    (~33 PDFs ohne Treffer weiter manuell)
  - [ ] **Pro First-Level-Section eigenen PDF-Volltext-Korpus
    aufbauen** (User-Wunsch 2026-05-08, in Anlehnung an den
    T7/T8-Verify-Workflow):
    - Pro Sektion (Introduction, Background, Taxonomy,
      Training/DoE, Integration Patterns, Validation,
      Applications, Open Challenges, Conclusion, Appendix) die
      darin zitierten Schluesselpapers manuell als PDFs
      runterladen und in
      `Documentation/Papers/review_surrogate_modeling/paper_library/fulltexts/by_section/<sec>/`
      ablegen.
    - Naming-Konvention: Cite-Key als Dateiname (z.B.
      `Khaloie2025.pdf`); analog zu der bestehenden Konvention im
      `fulltexts/`-Root-Ordner (siehe `fulltexts/README.md`).
    - Sobald ein Section-Korpus liegt, kann der Agent jede
      Aussage in der Sektion gegen den Volltext pruefen (RMSE-
      to-Regret-Argumente, Speedup-Zahlen, Pattern-Zuordnung,
      Tool-Mentions) -- analog zum
      `paper_library/verify_T8_software_cites.py` Workflow fuer
      die Software-Tabelle: ein Skript scant alle PDFs auf
      Aussage-Anker und liefert pro Cite die Belegquellen.
    - Reihenfolge: empfohlen Section 4 (Taxonomy) zuerst, weil
      hier Methoden-Klassifikationen die haerteste Volltext-
      Belegung brauchen, danach Section 6 (Integration Patterns),
      Section 7 (Validation), Section 8 (Applications);
      Sections 1-3 + 9-10 zuletzt (sind Synthese-Sektionen, in
      denen der Volltext-Bedarf geringer ist).
  - [ ] Volltext-Verifikation der Manuskript-Aussagen vor Submission
    (kritisch! die ausformulierten Sektionen 4-9 sind abstract- und
    metadatengestuetzt, nicht volltextgeprueft):
    - Quelle pro Cite ist primaer das `abstract`-Feld aus dem
      Scopus-BibTeX-Export plus Title, Author/Index Keywords, OpenAlex
      `primary_topic`/`cited_by_count`, und die `matched_*_terms`
      aus `surrogates_esm_screening.csv`
    - Aussagen, die zwingend Volltext brauchen:
      - alle quantitativen Klauseln im Manuskript ("one to three
        orders of magnitude", "low single-digit per cent regret",
        "10x-100x speedup", "~5% feasibility violation", ...) -> als
        domain-typische Groessenordnungen formuliert, aber nicht pro
        Paper geprueft
      - jeder Cite-Block mit 5+ Keys -> stichprobenartig pruefen,
        ob die zitierten Papers tatsaechlich die im Satz behauptete
        Methodik / Anwendung / Pattern-Zuordnung haben
      - alle B25/B26/B27-Cites (NSGA, MOO-Metaheuristiken, MCDM aus
        2025-2026) -> hier ist das Risiko falscher Einordnung am
        groessten, da diese Eintraege ueber den
        `moo_multicriteria_scopus_export` reingekommen sind und nur
        knapp ueber Title/Abstract klassifiziert wurden
      - Pattern-Zuordnung pro Cite (P1 Replace, P2 Accelerate,
        P3 Warm-Start, P4 Decompose, P5 Uncertainty) ist
        abstract-basiert; Volltext kann ergeben, dass eine Studie
        eigentlich in einem anderen Pattern sitzt
    - empfohlene Reihenfolge:
      1. Cornerstone-PDFs (96 high-priority OpenAlex-Hits, markiert
         im `paper_library/review_paper_library_manifest.csv`) ueber
         Zotero + Uni-Proxy beschaffen und im Volltext lesen
      2. quantitative Klauseln im Manuskript identifizieren und gegen
         die Cornerstones spot-checken; bei Unstimmigkeit konservativ
         umformulieren ("up to two orders of magnitude" o.ae.)
      3. pro Sektion einen Cite-Block-Audit machen: 2-3 Stichproben
         pro 10er-Block, dabei `matched_*_terms` und das Abstract
         als Vor-Filter nutzen, Volltext zur Bestaetigung
      4. Ergebnisse des Audits in `references/screening_log.md`
         als neuen Abschnitt "Audit log" festhalten, sodass die
         Submission reproduzierbar ist
    - Risiko-Klassen (im Zweifel zuerst pruefen):
      - hoch: alle quantitativen Aussagen (Speedup, Regret,
        Feasibility-Raten)
      - mittel: spezifische Pattern-Zuordnungen, MOO/NSGA-Cites
        aus 2025-2026, MCDM-Cites
      - niedrig: methodische Familien-Statements und
        Klassifikationsaussagen ("X has been used for Y") -- die
        sind durch Abstract+matched_terms relativ robust belegt
  - [ ] Tier-B-Kandidaten manuell sichten; Tops in Tier A heben
  - [ ] Better-BibTeX-Auto-Export einrichten, damit
    `surrogates_esm.bib` aus Zotero stabile ASCII-Keys bekommt
  - [ ] Cornerstone-PDFs (96 high-priority, ggf. via Uni-Proxy in
    Zotero) lokal beschaffen, dann inhaltlich tiefer einarbeiten
  - [ ] Overleaf-Bibliografie auf `paper_library/review_paper_library.bib`
    umstellen (oder `\bibliography`-Pfad im Manuskript anpassen, falls die
    Library als Manuskript-Bib genutzt werden soll)
  - [x] Scopus-Metadaten aus `paper_library/review_paper_library.bib`
    entfernen (Whitelist-Cleaner in `select_paper_library.py`):
    - `url` -> Scopus-Link gestrippt (260/260 Eintraege)
    - `note` -> "Cited by"/"Open Access" gestrippt (258/260)
    - `type`, `source`, `publication_stage` immer entfernt (258/260 each)
    - `author_keywords` immer entfernt (246/260)
    - Source-Pool `references/review_mes_moo_surrogates.bib` bleibt
      unangetastet; Cleanup nur beim Schreiben des Subset-Bib im
      `paper_library/`-Layer
    - Run-End-Summary listet die abgezogenen Felder auf, damit der
      Effekt im Build-Log nachvollziehbar bleibt
    - LaTeX-Kommentar-Aware Mandatory-Scan ergaenzt, damit
      `\cite{...}`-Beispiele in `%`-Kommentaren nicht als
      Pflicht-Cites zaehlen


- [ ] DH-Bus-Aggregation / Netztraegheit als expliziten Methodenpfad pruefen:
  - Quellenanker liegen in `Documentation/Sources/dh_bus_aggregation_quellen.md`
  - keine kuenstlichen Nutzungsprofile fuer Raumwaerme einfuehren
  - Gebaeudeseite bleibt physikalisch ueber Innentemperatur, Wetter und Huelle getrieben
  - Dispatchseite optional ueber kausale, settingsgefuehrte DH-Bus-Verzoegerung/Glaettung fuehren
  - Energieerhaltung, Aktivierung und Parameter ausschliesslich ueber Settings/SSOT
  - getrennte KPI-Semantik festhalten:
    - Komfort/ThermFlex/Gebaeude-KPIs auf Gebaeudeseite
    - Erzeugermix/Kosten/CO2/Peak-Boiler-KPIs am DH-Bus bzw. Kraftwerksinput
  - Sensitivitaet fuer Bus-Traegheit spaeter im Paper ausweisen; aktueller Vorcheck nutzt `tau_h = 0/4/8/12`
  - visueller Vorcheck nutzt `tau_h = 0/4/8/12` auf Fig.-11/12-Wochensignal
  - experimenteller MILP-/Gold-Pfad ist fuer `tau_h = 0/4/8` eingebaut und in Table 13 fuer drei Wochen getestet:
    - Top-savings-Woche um `2023-11-01`
    - kalte Peak-Woche um `2023-01-15`
    - Dezember-Woche um `2023-12-10`
  - Befund fuer `tau_h = 4/8`:
    - Kosten, CO2 und Peak-Boiler-Energie bleiben in den getesteten Wochen negativ gegenueber Referenz
    - Effektgroessen werden aber stark kleiner als ohne DH-Bus-Traegheit
    - `tau_h = 4` ist eher plausibler Basiskandidat; `tau_h = 8` eher starke Sensitivitaet / Upper Bound
  - vor Paper-Festlegung noch klaeren:
    - ob `tau_h = 4` Basiscase oder Sensitivitaet bleibt
    - wie die Endzustands-/Boundary-Policy fuer Wochen- und Jahreslaeufe formuliert wird
    - ob langsamere CHP-Dynamik / Rampenlogik als getrennte Erzeuger-Sensitivitaet noetig ist, weil Peak-Boiler fachlich schnell reagieren koennen
  - nach Waste-Must-run-Fix alle Table-13-/Jahres-KPIs neu rechnen:
    - bisherige Table-13-Cachewerte sind methodisch stale
    - Fig. 12 rechnet bereits mit Waste-Must-run und `tau_h = 4`
    - Cold-week-Plot zeigt fast nur einen letzten Boiler-Drop; vor Paper-Verwendung Boundary-/Terminal-Policy pruefen
  - nach Day-ahead-Preisprofil-/Gas-CHP-Fix alle Fig.-12-, Table-09-/13- und Jahres-KPIs neu rechnen:
    - bisher fiel der gekoppelte Dispatch ohne `day_ahead_price` im Profil auf einen konstanten Verbrauchstarif zurueck
    - Gas-CHP-Stromwert ist nun expliziter CHP-Kuppelprodukterloes, nicht Grid-Import-Kostenersatz
    - `piecewise_power_heat_v1` bleibt vorerst kein Paper-Basiscase, weil der stündliche Power-Gate-Pfad optisch und fachlich zu sprunghaft war
    - aktiver Paper-Basiscase nutzt wieder `fixed_ratio` mit `gas_chp_before_peak_boiler = true`
    - Grid-Import-/Export-Terme werden nicht mehr als DH-Kosten-KPI gezaehlt, wenn sie nicht im Dispatch-Objective aktiv sind
    - Beispielcheck Aprilwoche `2023-04-01`: Gas-CHP als Mittellast, Peak-Boiler absolut klein, Kosten ca. `-10,6 %`, CO2 ca. `-2,0 %`
  - Sensitivitaeten im Paper nicht als separaten Nachsatz behandeln:
    - passende Sensitivitaetsparameter frueh in die jeweilige Ergebnisdarstellung integrieren
    - bei Hauptfiguren/-tabellen klar zwischen Basiscase und Sensitivitaetslinien/-bändern unterscheiden
    - interne Diagnoseplots wie der Tau-Vorcheck muessen nicht als Paper-Hauptgrafik erscheinen
    - Ziel: Sensitivitaeten stuetzen die Story direkt bei Kosten, CO2, Dispatch, Peak-Boiler und Shift-KPIs, statt erst spaet im Appendix isoliert aufzutauchen
- [ ] Wiener DH-/Thermflex-Surrogatpfad auf `xgb` schneiden:
  - Vergleichsfaelle `baseline_constant_no_thermflex`, `day_night_no_thermflex`, `day_night_thermflex`
  - Inputs um Policy-/Control-Mode-Features erweitern
  - Targets auf DH-Dispatch-/Thermflex-/CO2-Pfad umstellen
  - RF-spezifische Unsicherheitsreste im Surrogat-Layer bereinigen
  - fuer `xgb` explizit entscheiden, ob der aktuelle Ensemble-/Quantil-Feasibility-Pfad erweitert oder fuer nicht-ensemblefaehige Modelle separat behandelt wird
- [ ] Surrogat-Strategie fuer den Gebaeudepfad explizit auf den Nachfolger des heutigen ROM ausrichten:
  - nicht auf ein einziges monolithisches "alles-in-einem"-Surrogat gehen
  - stattdessen einen kohärenten Stack schneiden:
    - `EnergyPlus` bleibt Teacher / Truth-Layer
    - learned building-response surrogate als Nachfolger des heutigen Reduced-Order-Modells
    - separater System-/Dispatch-Surrogat-Layer fuer Cost / CO2 / Peak / Flows
  - der erste aktive Ersatzpfad soll das heutige ROM ersetzen, nicht nur zusaetzlich danebenstehen
  - Fokus fuer den learned building-response surrogate:
    - stateful / sequenziell
    - stündliche Dynamik statt nur KPI-Regression
    - Outputs: `T_in`, `q_heat`, Rebound, Komfortnaehe, Shift-/Release-Dynamik
- [ ] Unsicherheitsbewussten Surrogatpfad mit Truth-Fallback aufbauen:
  - nicht nur Punktvorhersagen, sondern auch Unsicherheitsmass / Konfidenz
  - unsichere Punkte explizit an Teacher/Gold zurueckgeben
  - Ziel:
    - keine falsche Sicherheit in den Optimierungsregionen
    - gezielterer Einsatz des knappen Truth-Budgets
- [ ] Active-Learning-Schleife fuer den Thermflex-Surrogatpfad aufsetzen:
  - neue Teacher-/Gold-Laeufe nicht breit zufaellig, sondern gezielt dort nachziehen, wo das Modell heute schwach ist
  - Prioritaetsregime:
    - kalte Hochlasttage
    - starke Solar-/Shoulder-Tage
    - hohe Rebound-Tage
    - KPI-Trade-off-Tage
    - Punkte nahe Komfort- und Flex-Bounds
  - Ziel:
    - bessere Holdout-Metriken pro zusaetzlichem Truth-Budget
    - robustere Pareto-/Optimierungsregionen
- [ ] Learned building-response surrogate als moeglicher Nachfolger des heutigen Reduced-Order-Modells schneiden:
  - technischer Zielentwurf liegt in `Documentation/Planning/building_surrogate_layer2_design.md`
  - V1 nicht als ROM-Korrektur finalisieren, sondern als EnergyPlus-Teacher -> Learning -> stateful building-surrogate Runtime-Pfad aufbauen
  - vorhandene EnergyPlus-Teacher-Exports als Basis verwenden:
    - `T_in`
    - `q_heat`
    - Fenster-/Solar-Gewinne
    - Infiltration/Ventilation
    - Outdoor-Air-Heat-Balance
    - interne Gains und Setpoints
  - erster standardisierter hourly transition dataset builder im `Learning/`-Layer ist angelegt:
    - `Learning/building_response/schema.py`
    - `Learning/building_response/build_transition_dataset.py`
    - Smoke-Output: `Learning/datasets/building_response_v1_smoke/`
  - naechster Ausbau:
    - Builder auf alle geeigneten Teacher-Runs anwenden
      - Status: erledigt fuer vorhandene Teacher-Runs; `building_response_v1` enthaelt 7008 Transition-Zeilen aus 96 Runs
    - direkte neuere EnergyPlus-Air-Path-Spalten in den Teacher-Exports nachziehen
    - erste Modelltrainings-/Rollout-Validation im bestehenden `Learning/`-Stil anschliessen
      - Status: erster `RandomForestRegressor`-Prototyp liegt unter `Learning/models/building_response_v1/`
      - One-step ist stark (`T_in_next` R2 0.986, `q_heat` R2 0.926)
      - rekursiver Rollout zeigt erwartbaren Drift und muss vor Runtime-Nutzung gezielt verbessert werden
      - KPI-nahe Aggregatmetriken liegen jetzt als `aggregate_kpi_metrics.csv` vor:
        - `complete`-Pfad: `Learning/models/building_response_v1_complete/`
        - Direct-Flow-Subset: `Learning/models/building_response_v1_direct_flows/`
      - Direct-Flow-Subset zeigt, dass direkte EnergyPlus-Air-Path-Flows gut lernbar sind, aber aktuell nur 17 Teacher-Runs abdecken
    - naechste Validierungsverbesserung:
      - alte Teacher-Runs mit den neueren direkten Air-Path-Exports neu erzeugen, damit Direct-Flow-Targets nicht nur als kleines Subset trainierbar sind
      - Split nach kompletten Experiment-/Kohorten-Kombinationen statt nur Teacher-ID pruefen
      - 24/48h-Rollout je Kohorte und Experiment ausweisen
        - Status: erste Gruppenauswertung liegt fuer `building_response_v1_complete` vor
        - groesster Temperatur-Rollout-Ausreisser: `winter_free_float_72h` / `non_residential_1975_1990`
        - naechster Schritt: free-float separat validieren oder eigenes Regime/Modell behandeln, bevor Runtime-Freigabe diskutiert wird
      - Reference-only Runtime-Regime separat halten:
        - aktueller bester V1-Baseline-Lauf: `Learning/models/building_response_v1_reference/`
        - 24h-Rollout `T_in` MAE 0.137 C und `q_heat` MAE 0.837 kWh
        - dieses Regime ist der naechste Kandidat fuer strengere Event-/Kohorten-Validation
      - Hard-Split-Validation liegt vor:
        - `Learning/models/building_response_v1_reference_hard_split/`
        - Split nach kompletten `cohort_id + experiment_id`-Kombinationen
        - 24h-Rollout `T_in` MAE 0.140 C und `q_heat` MAE 0.981 kWh
        - globale KPI-Aggregat-R2 bleibt hoch
        - naechster Gate-Block: Event-Rebound und Komfortverletzungen fachlich schaerfer schneiden
      - Scope fuer Building-Surrogat-Validation ist bewusst building-nah:
        - `T_in`, `q_heat`, Heat-balance-Flows, Komfort, Rollout, Event-Shift/Release/Rebound
        - Dispatchkosten, CO2, Boiler-/CHP-Mix und Peak-Outcome bleiben Gate des Dispatch-/System-Surrogats bzw. des End-to-End-Gold-Rechecks
      - Komfortverletzungs-False-Negatives und Event-Rebound-Metriken ergaenzen
        - Status: Komfort-False-Negatives im Rollout werden gezaehlt
        - Status: Event-Response-Metriken liegen als `event_response_metrics.csv` vor
        - neuer Split-Modus `event_bundle` haelt Event und passende Referenz gemeinsam aus Train/Test heraus
        - Status: explizite Event-/Control-Features und thermische Abstandsfeatures sind im Transition-Datensatz enthalten
        - Status: der EnergyPlus-Teacher exportiert fuer neue Runs direkte Event-/Control-Spalten:
          - `reference_heating_setpoint_c`
          - `heating_setpoint_delta_c`
          - `event_active`, `event_elapsed_h`, `event_remaining_h`
        - Status: `teacher_reference_heating_setpoint_c = 22.0 C` ist als Teacher-SSOT gesetzt
        - Status: `upper_only` wird im Building-Dataset als `lower_bound_c = reference_heating_setpoint_c` und `upper_bound_active = 0` gefuehrt
        - Status: Event-Teacher-Batch wurde mit 22-C-Setpoint neu erzeugt (`8` Kohorten x `5` Event-/Referenzexperimente)
        - Status: `building_response_v1` wurde danach neu gebaut (`7008` Transition-Zeilen aus `96` Teacher-Runs)
        - aktueller `event_bundle`-Lauf auf neuem 22-C-Teacher-Stand:
          - 24h-Rollout `T_in` MAE `0.209 C`
          - 24h-Rollout `q_heat` MAE `0.471 kWh`
          - Heizenergie-Aggregat: MAE `15.0 kWh`, R2 `0.9993`
          - heldout Event-Net-Heat-Delta-Fehler im Mittel:
            - Preheat `13.0 kWh`
            - Cutback `9.7 kWh`
            - Recovery `31.9 kWh`
        - aktueller Befund: aggregierte Heizenergie und Flow-KPIs sind stark, aber Preheat-Delta-T/Shift-Amplitude und Recovery-Generalisation bleiben die relevanten Modell-Gates
        - naechster Modellhebel: mehr Upper-only-/Preheat-Teacher-Laeufe mit variierenden Dauern/Tagen ergaenzen und danach XGBoost/Target-spezifische Modelle benchmarken
      - Modellstrategie:
        - aktueller V1-Baseline-Pfad bleibt `RandomForestRegressor` als multi-output transition model
        - erster XGBoost-Benchmark nach 22-C-Teacher-Rerun ist erledigt:
          - Artefakt: `Learning/models/building_response_v1_reference_event_bundle_split_xgb/`
          - Vergleich: `Learning/models/building_response_v1_rf_xgb_benchmark.csv`
          - Diagnose: erster XGB-Lauf hat niedrige Heizlaststunden systematisch ueberprognostiziert
          - `log1p(q_heat)` war keine Verbesserung, weil aggregiert starke Unterprognose entsteht
          - tieferer `qheat`-Preset verbessert XGB-`q_heat` deutlich:
            - 24h `T_in` MAE `0.059 C`
            - 24h `q_heat` MAE `0.668 kWh`
            - Heizenergie-Aggregat MAE `19.2 kWh`
          - bester Gesamtkompromiss aktuell:
            - `hybrid_temp_xgb_heat_rf`
            - XGB fuer `T_in_next`
            - RF fuer `q_heat` und Heat-balance-Flows
            - 24h `T_in` MAE `0.076 C`
            - 24h `q_heat` MAE `0.471 kWh`
            - Heizenergie-Aggregat MAE `15.0 kWh`
          - Paper-tauglichere reine XGB-Alternative wurde geprueft:
            - `xgb_target_blocks`
            - ein Modellfamilienansatz mit XGB-balanced fuer `T_in_next` und XGB-qheat fuer Heizenergie/Flows
            - Seed-42: 24h `T_in` MAE `0.076 C`, 24h `q_heat` MAE `0.669 kWh`, Heizenergie-Aggregat MAE `19.2 kWh`
            - fuenf-Split-Robustheit: gleiche mittlere Temperaturguete wie Hybrid (`0.109 C`), aber schlechtere Heizenergie (`0.910` vs. `0.878 kWh`) und schlechterer Preheat-Delta-Fehler (`18.4` vs. `11.9 kWh`)
            - Bewertung: methodisch eleganter, aber aktuell nicht der bevorzugte V1-Kandidat
          - Flow-Verbesserungscheck fuer XGB-Target-Blocks:
            - Rel-MAE Seed-42 vor Feature-Erweiterung:
              - `window_heat_gain` `3.42 %`
              - `zone_total_heating` `1.95 %`
              - `zone_windows_transmitted_solar` `1.86 %`
              - `window_heat_loss` `1.51 %`
            - Zeit-/Solar-Lag-Features verbessern Heizenergie leicht (`1.95 % -> 1.90 %`) und Window-gain minimal (`3.42 % -> 3.41 %`)
            - dieselben Features verschlechtern Solar-transmitted und Window-loss leicht
            - separater `solar_window`-Preset verschlechtert die Fensterziele und wird nicht priorisiert
            - naechster echter Hebel: mehr gezielte Teacher-Coverage fuer sonnige Winter-/Schultertage, Preheat+Solar-Rebound und periodenspezifische Glazing-/SHGC-Variation
            - Status Teacher-Coverage-Hebel:
              - acht neue 96h Repday-Reference/Preheat-Experimente in Settings-SSOT angelegt
              - selektiver EnergyPlus-Batch erzeugt `64` neue Teacher-Laeufe
              - Datensatz: `13088` Transition-Zeilen aus `160` Teacher-Runs
              - augmentierter Seed-42-Vergleich RF vs. XGB target blocks:
                - `zone_total_heating` rel-MAE `3.10 %` vs. `2.53 %`
                - `zone_windows_transmitted_solar` rel-MAE `3.36 %` vs. `1.85 %`
                - `window_heat_gain` rel-MAE `3.88 %` vs. `3.11 %`
                - `window_heat_loss` rel-MAE `2.21 %` vs. `2.26 %` nach eigenem Window-loss-Preset
                - `approx_ventilation_loss` rel-MAE `1.26 %` vs. `0.04 %`
                - `approx_infiltration_loss` rel-MAE `0.90 %` vs. `0.02 %`
                - `internal_gains` rel-MAE `0.52 %` vs. `0.001 %`
              - Befund: XGB-Blocks ist nach Teacher-Coverage und Window-loss-Preset bei fast allen Targets besser als RF; Window-loss ist nur noch minimal schlechter
              - Weiterer Dauerpunkt:
                - Building-Surrogat kontinuierlich verbessern, sobald neue Teacher-/Paper-Runs entstehen
                - insbesondere Event-Amplitude, Rebound, Window-loss und weitere Solar-/Glazing-Coverage als aktive Qualitätshebel tracken
                - fuer den aktuellen Arbeitsstand reicht die XGB-Target-Blocks-Variante als paperfreundlicher V1-Kandidat aus
        - naechster Modellschritt:
          - Hybridpfad weiter validieren
            - Status: Robustheitscheck ueber Seeds `7, 21, 42, 84, 126` erledigt
            - Artefakte: `Learning/models/building_response_v1_robustness_event_bundle/`
            - Ergebnis:
              - RF mittlerer 24h `T_in` MAE `0.272 C`
              - Hybrid mittlerer 24h `T_in` MAE `0.109 C`
              - RF mittlerer 24h `q_heat` MAE `0.880 kWh`
              - Hybrid mittlerer 24h `q_heat` MAE `0.878 kWh`
              - Heat-Aggregat bleibt identisch, weil der Hybrid Heizenergie/Flows bewusst vom RF-Teil nimmt
            - Bewertung: Hybrid ist V1-Kandidat fuer weitere Side-by-side-Validierung, aber noch kein produktiver Runtime-Ersatz
          - zusaetzliche Upper-only-/Preheat-Teacher-Laeufe fuer Event-Amplitude/Rebound nachziehen
          - danach pruefen, ob ein separater Event-Delta-Corrector noetig ist
      - erledigte Teacher-Rerun-Reihenfolge:
        - Event-Batch mit neuem 22-C-Teacher-Setpoint erzeugt
        - `Learning.building_response.build_transition_dataset` neu gebaut
        - `event_bundle`-Retrain und KPI-Vergleich neu gerechnet
        - naechster Schritt: XGBoost-Benchmark und zusaetzliche Upper-only-Teacher-Designs
      - pruefen, ob direktere EnergyPlus-Air-Path Targets besser als approximierte Infiltration/Ventilation sind
  - Zielkontrakt bleibt:
    - `state_t + exogenous_t + control_t + cohort_context -> state_t+1 + q_heat_t + heat-balance diagnostics`
    - `Technical_model` bleibt fuer EnergyPlus-Teacher und kanonische physikalische Exporte zustaendig
    - `Learning` ist fuer Feature-/Target-Building, Dataset-Store, Training, Validation und Artefakte zustaendig
    - fehlende Pflichtspalten hart validieren
    - keine stillen Null-Fallbacks fuer aktive physikalische Pfade zulassen
  - direkt aus `EnergyPlus`-Teacher-Daten trainieren
  - stateful / sequenziell, nicht nur KPI-Regression
  - Kernoutputs:
    - `T_in`
    - `q_heat`
    - Rebound
    - Komfortgrenznaehe / thermischer Spielraum
    - mehrstuendige Shift-/Release-Dynamik
  - moegliche Modellklassen:
    - neural state-space
    - structured recurrent / physics-guided models
    - hybrid grey-box + ML corrector
- [ ] Hybrid-/Residual-Lernpfad explizit mitpruefen:
  - physikalischen Kern nicht sofort komplett verwerfen
  - stattdessen pruefen, ob ein ML-Corrector auf Residuen / Modellfehlern den saubersten ersten Schritt liefert
  - das ist besonders attraktiv, wenn full learned building dynamics noch nicht stabil genug fuer lange Horizonte sind
- [ ] Transfer-Learning-Pfad fuer Archetypen, Wetterjahre und spaetere Szenariowelten vorbereiten:
  - nicht fuer jeden neuen Archetyp / jedes Jahr ein vollstaendig neues Surrogat bei null trainieren
  - stattdessen Vortraining auf breiter `EnergyPlus`-Teacher-Basis und gezieltes Fine-Tuning mit kleinen Zusatzdatensaetzen
  - besonders relevant fuer spaetere Generalisierung ueber mehr Wetterjahre, Settings und Systemvarianten
- [ ] `Learning/thermflex_daily_results/` vom Struktur-Skeleton zum ersten lauffaehigen Datensatzpfad ausbauen:
  - Truth-Quellen und Pflichtspalten aus `Data/surrogate_training_cache/...bundle_stop/` und den Gold-Daily-Screens explizit festziehen
  - Day-row-Vertrag definieren:
    - Policy-Inputs
    - Tageskontext
    - Reference-Day-Features
    - Result-Targets
  - grouped Holdout ueber ganze Screen-Bundles / Fallfamilien / Zeitbloecke explizit schneiden
  - erste XGB-Baseline erst nach stabilem Datensatzvertrag aufsetzen
  - Aggregationspfad so halten, dass spaeter `Table 09`, Scatter, Sensitivitaeten und Ranking-Exports auf derselben Tagesbasis liegen
  - vor Persistenz noch explizit entscheiden, wie mit aktuell sichtbaren Label-Inkonsistenzen umgegangen wird:
    - nur `policy_case_label_canonical` als Trainings-Policy verwenden
    - exportierte Paper-Labels nur als Rohmetadaten behalten
    - Pilot-/Legacy-Bundles ggf. getrennt gewichten oder aus einzelnen Train/Holdout-Splits ausschliessen
- [ ] ThermFlex-Daily-Results-Baseline nach dem ersten Infrastruktur-Lauf fachlich verbessern:
  - aktueller Datensatz / erstes Modell stehen, aber Holdout-Qualitaet ist noch zu schwach
  - zuerst gezielt pruefen:
    - mehr kompatible `daily_thermflex_screen_*`-Bundles aus `Optimization/run/results/Vienna/gold/` kuratieren
    - Legacy-Bundles separat ein-/ausschalten und Holdout-Effekt messen
    - Pilot-/Partial-Bundles nur fuer spaetere augmentation nutzen, nicht fuer die Standard-Baseline
    - alternativen Target-Schnitt pruefen:
      - erst robuste KPI-Ziele
      - spaeter Rebound-/Shift-Ziele separat oder mit anderem Feature-/Modelldesign
  - danach erneut XGB-Baseline fahren und gegen den ersten Stand vergleichen:
    - Datensatz: `Learning/datasets/e0df98cac99aa1215507ccf8936833ed9df90cb71c857312ab15635aa3364de8/`
    - Modell: `Learning/models/thermflex_daily_results_xgb_e0df98cac99a/`
  - zusaetzlicher Vergleichsstand bereits vorhanden:
    - mit `dur8`-Checkpoint und Legacy drin:
      - Datensatz `Learning/datasets/5896cea66bbaf7b4351bee3ee983be0fa75e8811658d093be206c48d7b1b6011/`
      - Modell `Learning/models/thermflex_daily_results_xgb_5896cea66bba/`
    - mit `dur8`-Checkpoint, aber ohne Legacy:
      - Datensatz `Learning/datasets/6161b53af912319129fbba0ab5c5984a97b74be6ce7359e1489c0661be5ac31d/`
      - Modell `Learning/models/thermflex_daily_results_xgb_6161b53af912/`
  - naechste konkrete Hebel:
    - weitere echte Vollbundles fuer `dur8`, `12h`, `2K` und spaetere `tau`-Faelle rechnen bzw. aus Caches aufnehmen
    - ersten robusteren Zielkatalog separat schneiden:
      - Kosten/CO2
      - Peak-boiler delta
      - Rebound-/Shift-Ziele zunaechst separat

- [ ] Fig. 14 Lower-Relaxation-Pfad nach technischer Grundlage inhaltlich testen:
  - eigenen `case_label`/Cache-Key fuer `upper_plus_lower_relaxation` in den Fig.-/Table-Runnern verwenden
  - erste nicht-rendernde Vergleichslaeufe fuer `upper_only` vs. `upper_plus_lower_relaxation` mit `0.5/1/2 K` Lower-Relaxation vorbereiten
  - danach erst neue Fig. 14 rendern und die Darstellung der spaeteren Preheat/Cutback- und `T_in`-Reihen final entscheiden
  - Table-13-/Mechanism-Table-Builder bei Bedarf variantfaehig machen, sodass KPIs fuer `reference`, `upper_only` und `upper_plus_lower_relaxation` getrennt reported werden

- [ ] Peak-Boiler-Startkosten-Sensitivitaet methodisch einordnen:
  - `50 EUR/MW/start` plus `15 %` Mindestlast eliminiert den Boiler in der Februar-`tau=2`-Woche im Flexfall.
  - Kostenwirkung ist stark, weil der Referenzfall Starts zahlt und der Flexfall keine; daher als Sensitivitaet kennzeichnen, nicht still als Hauptkalibrierung.
  - Vor Paper-Finalisierung pruefen:
    - ob `EUR/MW/start` auf installierte/verfuegbare Gesamtleistung oder auf gestartete Einzelkessel-Leistung bezogen werden soll
    - ob die 50/50 Oel/Gas-Boiler-CO2-Logik zusammen mit Startkosten in der Ergebnisstory sauber getrennt wird
    - ob die Figur besser mit Startkosten-Sensitivitaet oder mit reiner Fuel/CO2/OPEX-Objective gezeigt wird

- [ ] CHP-Stromwert im DH-Kostenpfad methodisch festziehen:
  - `gas_chp_electric_value` ist aktuell ein expliziter negativer Objective-Term, der CHP-Strom zum Day-Ahead-Preis bewertet
  - fachlich vertretbar als KWK-Koproduktwert, aber nur wenn der Paperpfad klar als System-/Betreiberperspektive formuliert wird
  - pruefen, ob der Hauptpfad diesen Wert voll nutzt oder ob er in eine Sensitivitaet / gedeckelte Power-led-Komponente gehoert
  - besonders wichtig, weil ein zu starker Stromwert Gas-CHP-Spitzen in der Waermebereitstellung erzeugen kann
  - Apr-4/5-Isolation zeigt: Ohne `gas_chp_electric_value` wird freie Waste/External-Waerme zum Preheat genutzt; mit vollem CHP-Stromwert nicht
  - naechster Paperpfad-Kandidat: Waerme-Objective ohne ungebremsten CHP-Stromwert, CHP-Stromwert separat berichten oder als Sensitivitaet / power-led Betriebsmodus fuehren
  - als Sensitivitaet aufnehmen: Hauptpfad ohne `gas_chp_electric_value`, Zusatzfall mit vollem CHP-Stromwert zur Wirkung der KWK-Stromwert-Allokation
- [ ] ThermFlex-Event-Bounds kalibriert, aber nicht zu streng halten:
  - neue Settings fuer Preheat-/Cutback-Peak- und Energie-Multiplikatoren liegen vor
  - Fig. 12 testet zunaechst `1.25x` Preheat-Peak und `1.25x` Preheat-Energie bei weiterhin aktivem Cooldown
  - spaeter systematisch `1.0`, `1.25`, `1.5` gegen Fig.-12-Mechanik und Paper-KPIs vergleichen
- [ ] Upper-only-Eventlogik methodisch neu schneiden:
  - `max_flex_events_per_day=24` ist praktisch nicht limitierend, aber Event-Energy-Bounds skalieren aktuell mit der Zahl der Event-Starts
  - ein kompletter Wegfall aller Event-Grenzen kann viele künstliche Preheat-Impulse erlauben
  - sinnvoller Kandidat: Upper-only als kontinuierlichen Flexzustand modellieren, aber Preheat-Peak/Energie über Rolling- oder Tagesbudgets statt über Event-Start-Zählung begrenzen
  - 12h-Cooldown-Test löst das Waste-Tal in Fig. 12 April nicht ausreichend; nächster Test sollte Event-Energy-Bounds vs. Objective-/Preislogik getrennt isolieren
- [ ] Fig.-12-Dispatchdarstellung bei finalen Paper-Laeufen erneut pruefen:
  - aktueller Stand: Waste und External Heat sind fuer den Paper-Day-Ahead-Pfad als Must-run abgebildet; die Stackflaechen zeigen bus-allokierte Nutzwaerme ohne Speicherentladung/-ladung, damit Spillage und Speicher nicht als Ueberdeckung ueber der Nachfrage erscheinen
  - bei finalen Jahres-/Heizperiodenlaeufen sicherstellen, dass CSV-Spalten und Caption klar zwischen verfuegbarer Must-run-Waerme, bus-allokierter Waerme und System-KPIs unterscheiden
  - Heat Pump bleibt in der Darstellungsreihenfolge als Mittellastquelle zwischen Biomass CHP und External Heat, nicht als Peak-Lueckenfueller
  - April-Mechanismus gezielt pruefen: Wenn geglaettete DH-Buslast unter Waste-/External-Must-run-Angebot faellt, sollte Upper-only-Preheat diese Gratiswaerme nutzen und spaeter Gas-CHP/Peak-Boiler reduzieren; falls nicht, Optimierer-/Objective-Logik klaeren
  - Naechste Methodentests:
    - Dispatch generell als Rolling-Lookahead testen: z. B. `horizon_h = 48`, `rolling_commit_h = 24`, damit Tagesgrenzen nicht den Preheat-Mechanismus abschneiden
    - ThermFlex-Event-Bounds fuer Upper-only lockern/pruefen: `enforce_event_peak_bounds`, `enforce_event_energy_bounds`, `enforce_recovery_cooldown`
    - Gas-CHP-CO2-/Kostenaccounting pruefen: Fuel-CO2 vs. Waerme-/Strom-Allokation bzw. marginale Delta-Perspektive fuer KWK-Waerme
- [ ] Gebaeudeseitige thermische Speicherkapazitaet des an Wiener Fernwaerme angeschlossenen Bestands abschaetzen:
  - Zielgroesse: nutzbare Waermespeicherkapazitaet des Building Stocks in `MWh/K` bzw. fuer den erlaubten ThermFlex-Temperaturhub
  - dafuer Flaechen nach Archetyp/Kohorte, effektive thermische Masse, Komfortband und DH-Anschlussanteil konsistent zusammenfuehren
  - Ergebnis soll als Plausibilitaetsanker neben DH-Netz-/Speichertraegheit und Wiener Warmwasserspeicher gestellt werden
- [ ] Surrogat-Architektur konsistent schneiden und dokumentieren:
  - aktuellen Stand explizit festhalten: welches Surrogat existiert heute, welche Targets es lernt, welche Rolle es gegenueber ROM/Gold/EnergyPlus hat
  - Zielbild klaeren: EnergyPlus als Teacher, learned building-response surrogate fuer `T_in`, `q_heat`, Rebound und Komfortdynamik; separates System-/KPI-Surrogat nur fuer schnelle Optimierung/Screening
  - vermeiden, dass Random-Forest/XGBoost/ROM uneinheitlich nebeneinander stehen, ohne klare methodische Begruendung fuer das Paper
  - naechster Schritt: kurze Architekturentscheidung mit Vor-/Nachteilen und Migrationspfad vom heutigen ROM zu einem EnergyPlus-gelernten Gebaeude-Surrogat

- [ ] Cursor SDK als optionalen Tooling-/Automationspfad evaluieren:
  - moegliche Nutzung: Figure-/Table-Rebuilds, Stale-KPI-Checks, Repo-Diff-/PR-Workflows und wiederholbare Paper-Run-Kommandos skripten
  - nicht als Modellbestandteil behandeln; nur pruefen, ob es die Agent-/Paper-Produktionsworkflows reproduzierbarer und token-/zeitaermer macht

- [ ] Wiener DH-Speicher fachlich nachschaerfen:
  - aktueller MILP-Pfad begrenzt `district_thermal_storage_charge/discharge` nur ueber Energiekapazitaet, nicht ueber Anschlussleistung
  - dadurch kann der Speicher in einer Stunde fast den halben Speicherinhalt liefern; das ist fuer Fig. 12 / kalte Woche methodisch zu grosszuegig
  - Quellenanker:
    - Wien Simmering: `11.000 m3`, `850 MWh`, rund `145.000 MWh/a` Entnahme ueber `2.200 h/a` => ca. `65,9 MW` mittlere Entladeleistung
    - Urban DH Extended: voller Speicher maximal `145 MW` ueber `6 h`
  - naechster sauberer Schritt:
    - `max_charge_kw_th` und `max_discharge_kw_th` in `DistrictThermalStorageConfig` aufnehmen
    - Werte in Paper-Overrides explizit setzen, keine Runtime-Hardcodes
    - Fig. 12 und Table 13 danach neu rechnen
  - Status `2026-04-29`:
    - Codepfad und Paper-Overrides sind auf `850 MWh` / `145 MW` umgestellt
    - Fig. 12 ist neu gerechnet
    - Table 13 muss mit dem neuen Speicherlimit noch neu erzeugt werden, bevor sie paperfaehig ist
  - Status `2026-04-30`:
    - Aktiv-/Inaktiv-Schalten im Dispatch-Pfad gehaertet: deaktivierter Speicher wird als `0`-Kapazitaets-Asset und ohne Speicherverluste an den MILP uebergeben
    - Fig.-12-No-Storage-Pfad ist fuer April lauffaehig; vor Paper-Entscheidung noch fachlich klaeren, ob Main-Paper-Figuren Speicher komplett ausschliessen oder Speicher als eigene Sensitivitaet zeigen

- [ ] Heat-Pump-Dispatchlogik fuer Wien 2023 pruefen:
  - aktuelle Grosswaermepumpe hat nur Kapazitaetsgrenze und COP, aber keine Mindestlast, Verfuegbarkeit, Laufzeitlogik oder Start-/Rampenkosten
  - dadurch kann sie im MILP als stundenweiser Lueckenfueller erscheinen
  - fachlich eher wie Biomasse-KWK / Mittellastquelle schneiden:
    - explizite `min_partload`-Settings
    - optional Verfuegbarkeit / Wartungsfenster
    - keine Peak-Boiler-ähnliche Rolle in Interpretation und Plot
  - erst nach Settings-SSOT-Entscheidung in den aktiven Paperpfad uebernehmen

- [ ] Gas-CHP-Betriebslogik fuer den Thermflex-2023-Paperpfad finalisieren:
  - aktiver Fig.-12-/Paper-Day-Ahead-Zwischenproxy seit `2026-04-29`:
    - `district_gas_chp.installed_kw_el_max = 1,44 GW_el`
    - `eta_el = 0,50`, `eta_th = 0,35`
    - daraus `~1,01 GW_th` konstante Waermeleistung im aktuellen Fixed-Ratio-MILP-Pfad
  - Begruendung:
    - balancierter Mischproxy zwischen rein stromgefuehrtem CCGT-Schnitt (`0,55/0,30`, zu viel Boiler) und dem vorherigen `0,40/0,45` Schnitt, der Fig. 12 mit `~1,62 GW_th` Gas-CHP-Waerme optisch und systemisch zu stark dominierte
    - Peak-Boiler bleibt in kalten Wochen sichtbar, aber unter dem Wiener `1,45 GW_th` Kapazitaetsanker
  - naechster fachlicher Endpfad:
    - nicht bei starrem Fixed-Ratio-Betrieb stehen bleiben
    - piecewise `power_led` / `mixed` / `heat_led` Betriebsbereich sauber im Dispatch abbilden
    - Day-ahead-Strompreis als exogener Betriebsmodus-/Opportunity-Cost-Treiber nutzen, aber keinen `grid_import/export`-Kostenpfad als DH-Paper-Objective verstecken
    - CHP-Waerme nur soweit erzeugen, wie DH-Bus/Speicher sie aufnehmen koennen; Spillage nicht als implizites Ventil fuer falsche Betriebslogik verwenden

- [ ] Fig. 12 Stacks semantisch bereinigen:
  - aktuelle Stackflaechen zeigen teilweise erzeugte Waerme, waehrend die Lastlinie die DH-Buslast zeigt
  - bei Must-run Waste / CHP kann die Flaeche deshalb ueber der Demand-Linie liegen, wenn Waerme gespillt oder in den Speicher geladen wird
  - nach Umstellung auf Winterwochen und `145 MW` Speicherlimit ist die optische Speicherueberdeckung kleiner, aber die Bruttoerzeugungs-/Spillage-Semantik bleibt methodisch zu klaeren
  - Peak-Boiler-Ueberdeckung wurde als Aggregat-Min-Partload-Artefakt identifiziert:
    - `2.2 GW_th * 0.15 = 330 MW_th` Mindestoutput war fuer einen modularen Spitzenkesselpark zu grob
    - Paper-Day-Ahead-Overrides wurden auf `district_gas_boiler.min_partload = 0.0` gesetzt
    - nach Neurechnung bleibt nur noch eine sehr kleine Ueberdeckung (`~1 MW` stündlich, `~92.8 MWh/Woche`), die mit der allgemeinen Bruttostack-/Speicherverlust-Semantik bereinigt werden soll
  - Paper-tauglicher waere:
    - Hauptstack = nutzbare Waerme zur Deckung von DH-Buslast plus Speicherladung
    - Spillage / must-run Ueberschuss separat schraffiert oder als eigene transparente Flaeche
    - Flex-Effekt nur im Delta-Panel bzw. ueber ref-vs-flex ausweisen
- [ ] Domestic-hot-water-Zeitreihe fuer das Paper sauber dokumentieren und pruefen:
  - aktueller Methodentext: "Residential domestic-hot-water demand was represented by a floor-area-based annual intensity, while its hourly distribution was imposed exogenously through a standardized domestic-hot-water profile"
  - die Erklaerung zur verwendeten DHW-Zeitreihe aus der Repo-Dokumentation in Methoden / Appendix uebernehmen
  - konkret nachvollziehbar machen:
    - welcher standardisierte Warmwasserprofilpfad verwendet wird
    - wie annuale Intensitaet, Flaeche und stundenweise Profilform zusammengefuehrt werden
    - ob das Profil normalisiert ist und wie es auf den Jahresbedarf skaliert wird
  - sicherstellen, dass diese Annahme nicht mit der Raumwaerme-/Thermflex-Story vermischt wird
- [ ] Paper-Figurenlayout pruefen: Tagesmechanikplots ggf. durch Wochenmechanikplots ersetzen:
  - Fig. 11 zeigt den Shift-Mechanismus ueber eine Woche klarer als einzelne Tagespanels
  - spaeter pruefen, ob Fig. 02 als Tages-Panelgrafik im Main Paper bleibt oder in den Appendix wandert
  - moeglicher Main-Paper-Pfad:
    - eine robuste Savings-Woche um `2023-11-04`
    - optional eine Trade-off-/Late-season-Woche als Kontrast
  - dabei auf Solverkosten achten: 169h-Gold-Flex-Solves sind deutlich teurer als Tages-Slices
- [ ] Validation-Layer fuer Surrogates aufraeumen:
  - neuen Pfad `Optimization/run/validation` als Primaerpfad etablieren
  - `validation_old` spaeter erst entfernen, wenn keine Legacy-Consumers mehr darauf haengen
  - Holdout-/Gate-Outputs auf aktuelle DH-/Thermflex-Ziele zuschneiden
  - kritische vs. sekundaere Targets explizit ueber Settings dokumentieren
- [ ] Dispatch-/Thermflex-Ergebnis-SSOT weiter haerten:
  - `dispatch_kpis.json` / `dispatch_kpis.csv` als operativen Exportpfad pflegen
  - spaeter auch Surrogat-Laeufe auf denselben KPI-Schnitt heben, soweit keine Truth-`raw_results` verfuegbar sind
  - `thermflex_hourly.csv` nur bei Bedarf aktiv halten
  - keine stillen Fallbacks im Export-/Truth-Pfad dulden; fehlende Pflichtfelder hart melden und `0` nur bei explizit deaktivierten Features/Technologien zulassen
  - Legacy-Sweep fuer alte Analyse-/Validation-Skripte mit `.get(..., 0.0)` / impliziten Fallbacks separat durchziehen, ohne den produktiven Hauptpfad zu destabilisieren

- [ ] Thermflex-Papermechanismen weiter schaerfen:
  - Solar-Gains-Seitenstrang spaeter explizit als Analyseplot `Savings vs. midday irradiance / solar-gains proxy` darstellen; der harte Counterfactual mit `runtime_solar_shading_factor = 0` zeigt bereits, dass die Top-Savings-Tage stark solargetragen sind
    - bei der Heizperioden-Solaranalyse nicht nur "mehr Solar = besser" erzaehlen:
      - der neue `dur24`-Screen zeigt zwar mehr verschobene MWh in hohen Solar-Bins
      - die mittleren Cost-/CO2-Vorteile sind dort aber nicht maximal, weil spaete Schultertage mit viel Solar und wenig Restheizbedarf die Systemvorteile wieder verduennen
  - Archetypen-/Kohortenstory im Paper nicht naiv als "neuere Gebaeude shiften mehr kWh" formulieren
    - explizit unterscheiden zwischen:
      - kurzfristiger Eventenergie / verschobenen `kWh`
      - thermischer Persistenz / Dauer-Sensitivitaet
    - alte Bundles zeigen derzeit eher:
      - alte Kohorten verschieben mehr in `dur1`
      - moderne Residential-Kohorten profitieren staerker von laengeren Dauern
  - CO2-Trade-off-Tage als eigenen Nebenstrang dokumentieren:
    - nicht jeder Tag verbessert alle KPIs gleichzeitig
    - typischer Mechanismus aktuell: weniger Boiler, aber mehr gasbasierte CHP-Waerme
    - nach dem Thermflex-Aktivierungsfix den vollstaendigen Heizperioden-Screen erneut rechnen, weil fruehere `dur24`-Rankingwerte ohne aktive Flex-Abweichungsgates erzeugt wurden
  - Paper-Ergebnisworkflow bewusst zweistufig halten:
    - jetzt zuerst Tabellen-/Figurenstruktur und KPI-Schnitt stabilisieren
    - finale Zahlen erst nach einem konsistenten Full-Rerun aller relevanten Paper-Cases einfrieren
    - alle aktuell aus Legacy-Bundles uebernommenen Werte in Tabellen/Figuren als Struktur-/Plausibilisierungswerte behandeln, nicht als finale Paper-Ergebnisse
  - `table_05` nach dem Full-Rerun neu aufbauen:
    - als Haupttabelle nicht den lower-bound/cutback-Dispatchwert verwenden, sondern die Gebaeudepersistenz aus `tau`, `C_eff`, Halbwertszeit und retained thermal state zeigen
    - Dispatchwerte (`MWh`, `Wh/m2`) separat als Mechanik-/Appendix-Tabelle behandeln, weil sie Heizlastpotenzial und Speicherpersistenz mischen
    - nach dem post-fix Table-05-Replay ist klar: der aktuelle `lb21`-Duration-Case misst primaer cutback-/Heizlastpotenzial, nicht moderne Speicherpersistenz
    - fuer die eigentliche Persistenzstory eine getrennte Metrik schneiden:
      - upper-only preheat mit gleicher Komfortobergrenze
      - oder fixed equal-energy pulse / temperature-decay diagnostic je Kohorte
      - Auswertung ueber `T_in`-Abklingung, Release-Dauer, rebound timing und Wh/m2 relativ zum Referenzwaermebedarf
    - Ursachencheck gemeinsam mit Referenzlast, Event-/Aktivierungsstunden, `T_in`-Pfad, Solar gains und Kalibrierparametern (`H_total`, `tau`, Eventbounds) fuehren
    - aktuelle Table-05-Struktur fuer Paper beibehalten und spaeter mit finalen Full-Rerun-Werten erneuern:
      - Persistenzparameter je Kohorte
      - realisierte Kohortenbeitraege auf einem Top-Savings-Tag
      - Duration-Vergleich nicht ueber realisierte Optimierer-`shifted Wh/m2`, sondern ueber vergleichbare `1 K`-Speicherpuls-Retention (`C_eff * exp(-h/tau)`) fuer `1/4/12/24 h`
      - System-KPI-Kontext nur auf Tagesebene, nicht kohortenspezifisch
  - `1 K lower-bound` nicht nur als "mehr Peak-Shaving" zeigen, sondern den systemischen Trade-off explizit machen:
    - staerkere Boilerentlastung
    - haeufig hoehere Kosten und CO2
    - aktueller Hauptmechanismus: Verlagerung in `district_gas_chp`
  - Seitenanalyse-Strang fuer verschiedene Tage explizit im Paper vorsehen:
    - gute Savings-Tage mit starkem Mittags-Preheat-/Abend-Release-Muster
    - kalte Kontrasttage mit wenig Effekt
    - CO2-Trade-off-Tage, auf denen nicht alle KPIs gleichzeitig besser werden
    - fuer diese Tagtypen die Mechanismen getrennt erzaehlen:
      - Solar-/Preheat-Beitrag
      - Boiler-/CHP-Verschiebung
      - kohortenspezifische Shift-Unterschiede
  - Kohortenspezifische Tagesgrafik fuer representative days vorbereiten:
    - fuer ausgewaehlte Tage (`2023-11-04`, `2023-03-04`, ein kalter Kontrasttag, ein CO2-Trade-off-Tag) stundenweise je Residential-Kohorte zeigen
    - Kernlinien/-Flaechen: `q_heat - q_ref` bzw. shifted/cutback heat, `T_in`, Komfortgrenze und ggf. Solar-gains-Proxy
    - Ziel: sichtbar machen, wann vorgeheizt wird, wie stark `T_in` steigt, welche Kohorte wie lange speichern kann und wie das mit den KPI-Aenderungen zusammenhaengt
  - Duration-spezifische Kohortenfigur als Ergebnisplot vorbereiten:
    - Status: erster 8-Tage-Prototyp umgesetzt:
      - `Documentation/Papers/thermflex_paper/figures/fig_05_cohort_duration_mechanism.png`
      - `Documentation/Papers/thermflex_paper/figures/fig_05_cohort_duration_mechanism_data.csv`
    - aktuelle Lesefassung:
      - Shift-/Release-Balken als Tagessummen je Kohorte und Duration
      - `T_in - setpoint` als Tagesverlauf nur fuer `1/4/12 h`
    - entkoppelte Tagessummen-Figure liegt zusaetzlich vor:
      - `Documentation/Papers/thermflex_paper/figures/fig_06_cohort_duration_daily_sums.png`
      - Temperaturverlaeufe separat halten, nicht in diese Summenfigur mischen
    - Dimensionen:
      - representative days / Top-Savings- und Trade-off-Tage
      - `max_flex_duration_h = 1, 4, 12, 24`
      - Residential-Kohorten
    - optimiererabhaengige Metriken:
      - realized shifted `Wh/m2`
      - realized release/cutback `Wh/m2`
      - net heat change `Wh/m2`
      - max `T_in` above setpoint
    - keine `active hours` in der Hauptgrafik zeigen:
      - `active` ist nur ein Kontroll-/Nutzungsindikator
      - fuer Paper-Lesbarkeit reichen Energieverschiebung und Temperaturantwort
    - Paneltitel nur als Tag-/Duration-Bezeichnung nutzen:
      - keine Cost-/CO2-Werte im Paneltitel
      - System-KPIs separat in einer Referenztag-Tabelle ausweisen
    - System-KPI-Tabelle separat pflegen:
      - cost change
      - CO2 change
      - boiler energy / boiler peak change
    - Ziel:
      - sichtbar machen, ob laengere Dauerfenster moderne Kohorten relativ staerker nutzbar machen
      - gleichzeitig zeigen, wann der Optimierer trotzdem alte Kohorten bevorzugt, weil dort mehr Referenzheizlast und groesserer Systemnutzen liegt
  - Kohortenspezifischen `T_in`-Tagesverlauf als eigene Figure-Komponente vorbereiten:
    - je ausgewaehltem Referenztag und Duration-Setting stundenweise `T_in - setpoint` zeigen
    - Linien nach Residential-Kohorte kodieren
    - Komfortobergrenze bzw. Setpoint als Referenzlinie zeigen
    - Ziel:
      - sichtbar machen, wann Preheat tatsaechlich den Innenzustand anhebt
      - zeigen, ob moderne Kohorten die Temperaturerhoehung laenger halten
      - direkt mit den shifted/release-Balken und der separaten KPI-Tabelle lesbar machen
  - schwache Surrogat-Holdout-Metriken fuer papernahe Targets explizit verbessern:
    - insbesondere `dispatch_operating_cost_eur` und Thermflex-Shift-/Rebound-Ziele
    - Sampling-/Feasibility-Schnitt, Target-Semantik und Feature-Satz dafuer gezielt nachziehen

- [ ] J1 core package API explizit machen: `DesignSpace`, `Evaluator`, `SurrogateModel`, `BudgetScheduler`, `FeasibilityGate`, `TruthAllocator`, `ExperimentRunner`
- [ ] Truth allocation / multi-fidelity explizit als eigene Komponente im Framework verankern
- [ ] Tariff-aware Surrogat- und Validierungspfad produktionsreif machen
- [ ] Reproduzierbare Benchmark-Suite für J1 definieren
- [ ] FeasibilityGate mit echtem Scheduler-Lauf verifizieren und Ranking-Semantik (`lexicographic`/`penalty`) kalibrieren

## Next

- [ ] Größeren, aber noch kontrollierten nativen Retrain für die klassische Family fahren
- [ ] EV-/Grid-/NPC-Bottlenecks im internen Gate gezielt analysieren
- [ ] Entscheidung vorbereiten, wie `legacy_import`-Modelle intern gegatet oder explizit als Production-Baseline markiert werden
- [ ] J1-Roadmap in Arbeitspakete schneiden
- [ ] Scheduler-Meta-Run-IDs gegen Parallel-Kollision härten (aktuell nur timestamp-basiert)
- [ ] Eigenen Szenario-Layer erst nach stabilem, plausiblen und effizienten Volloptimierungs-Hauptpfad schneiden; vorher keine zusätzliche Szenarioabstraktion einziehen

## Multi-Energy

- [ ] Wind v2: Small- und Large-Wind nicht auf derselben vereinfachten Geschwindigkeits-/Kennlinienlogik lassen
- [ ] Run-of-river / run-off hydro als eigene Stromtechnologie ergänzen
- [ ] Wiener Laufwasserkraft explizit integrieren: Donaukraftwerk Freudenau als bestehende Wien-Run-of-river-SSOT nachziehen; vorerst als bestehender, nicht weiter ausbaubarer Asset-Block behandeln
  - gegebene Referenzwerte: `installed_kw = 172000`, `annual_generation_gwh = 1052`
  - Kleinwasserkraftwerk Nussdorf im selben Pfad mitfuehren; vorerst auf derselben Donau-Klimatologie und mit offiziellem Leistungsanker `4,8 MW`
  - keine zusätzliche neue Wasserkraft in Wien unterstellen; Freudenau daher im Szenariopfad nicht als ausbaubare Neubauoption, sondern als bestehende Erzeugung mit datengetriebener saisonaler/stündlicher Verfügbarkeit modellieren
  - dafür einen sauberen Jahresgang-/`p_max_pu`-Pfad aus hydrologischem Proxy oder Messdaten ableiten, dann auf `1052 GWh/a` normieren
  - später Economics/LCA als bestehender Wasserkraftblock ergänzen
- [ ] Zielbild für erneuerbares Multi-Energy-System festlegen
- [ ] Entscheidung treffen, ob Wärme-/Gas-/H2-Netze auf Component-Ebene oder Netzebene modelliert werden
- [ ] Prüfen, wie `pandapipes` als optionale Netzschicht integriert werden kann, ohne den Core zu verkomplizieren
- [ ] LCA-Datenlage systematisch in Technologieblöcke und Netzblöcke überführen
- [ ] Speicherlogik im IES von der aktuellen einfachen Heuristik auf den geplanten Dispatch-/MILP-Pfad umstellen
- [ ] `dh_unserved_heat` aktuell nur als Diagnosewert behandeln; später durch DH-Speicher, weitere DH-Quellen oder Spitzenlasttechnologien (z. B. Biomasse/Gas/KWK/Boiler) sauber ersetzen
- [ ] Quellengetrennte DH-Abrechnung und Environmental Indicators auf Basis des `dh_bus` aktiv verdrahten
- [ ] Geothermie-LCA aktuell als ORC-/KWK-Proxy dokumentieren und später gegen wärmespezifische Datengrundlage oder explizite Allokation absichern
- [ ] Erdgas-KWK-LCA aktuell als CCGT-/CHP-Proxy dokumentieren und später gegen belastbare CHP-Datengrundlage oder explizite Allokation absichern
- [ ] Historische Day-Ahead-Preiszeitreihen für stochastic dispatch datenlogisch bereinigen: `MC Auction`-Lücken/partielle Jahre sauber behandeln, belastbaren nutzbaren Zeitraum festziehen und später eine saubere Lösung für die Preiszeitreihen ohne Ad-hoc-Fallbacks festziehen
- [ ] Gasbeschaffung für DH-/CHP-Dispatch energiemarktwirtschaftlich sauber schneiden:
  - nicht bei konstantem `fuel_eur_per_m3` stehen bleiben
  - Gas nicht naiv wie Strom vollständig hourly-spotbasiert bewerten
  - als Zielbild einen mehrschichtigen Beschaffungspfad prüfen:
    - Hedge-/Portfolio-Layer über `CEGH/EEX Futures` (z. B. Month / Quarter / Season)
    - Prompt-Layer über täglichen `CEGHIX` / `CEGH Day Ahead`
    - optional Balancing-/Imbalance-Layer über `Within-Day` / `Hourly`
  - offene Methodenentscheidung:
    - zunächst exogener Hedge-Anteil + täglicher Prompt-Preis
    - oder echte Gas-Beschaffungsvariablen im `milp_two_stage` modellieren
  - Datenlage und Historie dafür separat festziehen:
    - welche CEGH/EEX-Spot-/Futures-Zeitreihen tatsächlich lokal / lizenziert verfügbar sind
    - wie weit die Historie zurückreicht
    - wie tägliche bzw. stündliche Gaspreise sauber auf den Dispatchhorizont gemappt werden
- [ ] Gemeinsamen historischen stochastic Datenblock für Wetter/PV/Preis weiter schließen: mit PVGIS-`P` als PV-SSOT ist der aktuell belastbare gemeinsame Zeitraum nur `2020-01-01` bis `2023-12-31`; 2024/2025 fehlen auf der PV-Seite noch und sollten später nachgezogen oder methodisch sauber überbrückt werden
- [ ] Similar-Day-/Residual-Filter für historische stochastic Szenarien später methodisch sauber festziehen und erst dann aktivieren
  Was: optionaler Filter vor der Szenarioreduktion auf der Residual-Bibliothek, nicht als Ersatz für `baseline + residual`
  Wie: erst nach Literatur-/Methodenentscheid, z. B. über validierte Similar-Day-Metrik oder k-NN auf standardisierten Tagesvektoren
  Wo: primär in [historical_data.py](/c:/Users/Philipp%20Thunshirn/Desktop/PhD/Python%20model/Master/dispatch/scenarios/historical_data.py) vor `build_ies_historical_scenarios(...)`, ggf. mit Zusatzdiagnostik in [historical.py](/c:/Users/Philipp%20Thunshirn/Desktop/PhD/Python%20model/Master/dispatch/scenarios/historical.py)
  Status: aktuell bewusst **nicht** im Code aktiv
- [ ] Systemgrenze des stochastic IES-Pfads explizit festziehen und später erweitern:
  `milp_two_stage` läuft aktuell im gekoppelten IES-Pfad mit historischen Szenarien, `thermflex` und `H2`, aber noch ohne `v2h`, `biogas_engine` und `wood_gasifier`.
  Der volle Feature-Stack läuft derzeit nur im heuristischen Wien-Alltech-Pfad.
  Vor einer echten stochastic Optimierung später bewusst entscheiden, ob diese Features in den MILP-Zweistufenpfad integriert oder dort weiterhin ausgeschlossen bleiben.
- [ ] Wiener Building-Stock-/DH-Nachfragepfad sauber nachziehen:
  aktueller neuer Wien-`building_stock` interpretiert Citiwatt-`Heat demand` bewusst als Gesamt-Wärmeanker (`space_heat + hotwater`) für den Gebäudebestand;
  der ältere Pfad in `dh_demand.py`/`precompute.py` kam dagegen direkt aus `space_heat_member_2d` plus `hotwater_member_2d` und war noch nicht explizit an den Citiwatt-Jahresanker gekoppelt.
  Später sauber validieren, wie dieser Gesamtwärmeanker je Kohorte auf `space_heat` und `hotwater` aufgeteilt wird; für `non_residential` bleibt Warmwasser vorerst ausgeklammert.
  Der aktuell im Repo verwendete Warmwasserpfad kommt nicht aus Citiwatt, sondern aus `Data/profiles/common/usage/usage_profiles.xlsx` über `Warmwasserbedarf_W_m2` in [household_hotwater.py](/c:/Users/Philipp%20Thunshirn/Desktop/PhD/Python%20model/Master/Technical_model/technologies/household_hotwater.py); die Einheit ist explizit `W/m2`, also flächenbezogene stündliche DHW-Intensität.
  Daraus ergibt sich aktuell implizit eine Jahresintensität von rund `15.5 kWh/m2a`; auf die Wiener Residential-GFA angewandt entspräche das grob `1.38 TWh/a` bzw. rund `11.9 %` des aktuellen Citiwatt-Residential-Wärmeankers.
  Für die Paper- und Modell-Dokumentation später explizit nachziehen, wie die DHW-Komponente in der DH-Berechnung begründet wird:
  - Jahresanker für Residential-DHW mit belastbarer Literatur-/Normbasis festziehen (z. B. `ÖNORM B 8110-5`, `TABULA/EPISCOPE`)
  - stündliche DHW-Profilform mit belastbarer Methodenquelle dokumentieren (z. B. `EN 12831-3` / EPB-Demo-Spreadsheet)
  - klar trennen zwischen Jahresintensität, stündlicher Profilform und aktuell verwendeter Repo-Zeitreihe
  - die verwendeten Referenzen und die Datenbasis explizit im DH-Methodenteil des Papers verankern
  Der neue Wiener Stromanker skaliert im Kohortenpfad aktuell zunächst nur die exogenen `load_profile`-Zeitreihen je Kohorte;
  die später zusätzlich modellierte HVAC-/DHW-Elektrizität kommt darauf noch obendrauf.
  Der Stromschnitt ist dafür jetzt explizit getrennt in:
  - offizieller sektoraler Stromanker (`annual_electricity_official_kwh`)
  - exogener Profilanker (`annual_electricity_target_kwh`)
  Im aktuellen 2023-Kalibrierungsstand sind beide Größen bewusst nicht mehr gleich gesetzt:
  der exogene Profilanker ist jetzt aus einem expliziten Wien-2023-End-Use-Proxy abgeleitet
  (`official - lokale thermische Elektrizität`).
  Später sauber festziehen, ob der Wiener Jahresstromanker die reine Basislast oder die gesamte Endstromnachfrage abbilden soll.
- [ ] Für den expliziten Wien-2023-Referenzfall den aktuellen Elektrifizierungsgrad außerhalb von DH nachziehen:
  - Nicht-DH-Raumwärme im Status quo nicht implizit als voll-elektrische HP-Welt modellieren
  - lokales Warmwasser außerhalb DH ebenfalls nicht implizit voll-elektrisch modellieren
  - als grobe Status-quo-Anker dafür aktuell nutzen:
    - Wien Energiebericht 2025 / Heizungsart in Hauptwohnsitzwohnungen (`Fernwärme`, `Zentral`, `Elektroheizung`, `Einzelofen`)
    - Smart-City-Wien-Dokumentation für Energieträgeranteile von Raumwärme und Warmwasser
    - MA20-Studie `Gasetagenheizungen im Licht der Energiewende in Wien` für die Warmwasser-Diskussion
- [ ] Semantik und Quellen der neuen Wiener `thermal_archetypes` sauber dokumentieren und später validieren:
  `wall_area_per_gfa`, `window_area_per_gfa`, `roof_area_per_gfa` und `floor_exposed_per_gfa` sind einfache Flächenratios relativ zur `gross floor area (GFA)`;
  also z. B. `A_wall = wall_area_per_gfa * represented_gfa_m2` je Kohorte.
  Die aktuellen Residential-V1-Geometriewerte sind jetzt datenbasiert aus Austrian TABULA / EPISCOPE
  (TABULA Final Report Appendix Volume, Table 62, Apartment Blocks Austria):
  `roof_area_per_gfa = 0.37`, `window_area_per_gfa = 0.18`, `wall_area_per_gfa = 0.82`,
  `floor_exposed_per_gfa = 0.36`.
  Die periodenspezifischen Residential-U-Werte sind als erster Anker aus Austrian TABULA/EPISCOPE
  (`AT Austria`, Statistic S-1.2.2 "U-values and energy use for heating") genommen.
  Der `non_residential`-Geometriepfad ist dagegen weiterhin nur ein pragmatischer V1-Startwert,
  weil die nichtwohnliche Datenlage in EPISCOPE/TABULA deutlich schwächer ist.
  `c_th_wh_per_m2k` bleibt ebenfalls vorerst ein pragmatischer Startwert und ist nicht Wien-gemessen.
  Später gegen belastbarere Wiener oder österreichische Bestandsdaten prüfen und ggf. sektor-/bauperiodenspezifisch nachschärfen.
- [ ] `dh_connected_share` im neuen Wiener Kohortenpfad bleibt vorerst global über `district_heating.share`;
  spätere kohortenspezifische Überschreibungen (`dh_connected_share_override` je Kohorte) nicht vergessen, sobald belastbare sektor-/bauperiodenspezifische DH-Anschlussannahmen vorliegen.
- [ ] Einen standardisierten Wien-Benchmark-Smoke definieren:
  heuristisch all-tech, `milp_day_ahead` mit realistischem DH-Setup und `milp_two_stage` mit definierter Systemgrenze;
  damit spätere Refactors/Optimierungsläufe gegen denselben Referenzfall geprüft werden können.
  Den heutigen Wiener DH-Mix dabei vorerst nur als Plausibilitätsbenchmark verwenden:
  - grob gegen offizielle Wiener Statistikquellen prüfen
  - zusätzlich methodisch gegen Journal-/Utility-Literatur plausibilisieren
  - aber bewusst nicht hart auf historische Quellanteile überkalibrieren
- [ ] Wiener DH-Referenzmix 2023 um zwei fehlende Referenzblöcke ergänzen:
  - `district_external_heat` als expliziten `Bezug Abwaerme`-/Industrieabwaerme-Block führen, nicht als generischen "zugekauften" Wärmeblock
  - offizieller Anker aus Enable DHC / Wien 2023: `Bezug Abwaerme = 1.200,9 GWh`, also grob `22,1 %` relativ zu `Absatz Fernwaerme = 5.427,4 GWh`
  - `Heizzentralen = 206,3 GWh` vorerst nicht als eigene Technologie aufblasen, sondern im 2023-Benchmark pragmatisch als gasdominierten Restblock dokumentieren
  - `Spitzenkessel = 522,3 GWh` plus `Heizzentralen = 206,3 GWh` vorerst zusammen ueber `district_gas_boiler` abbilden
  - installierte Spitzen-/Reservekesselleistung fuer den Thermflex-2023-Paperpfad ist in den aktiven `*paper_day_ahead*.json`-Overrides auf `1,45 GW_th` umgestellt:
    - Quellenanker aus Wien-Energie-/Fernheizwerk-Angaben:
      Spittelau `400 MW_th`, Arsenal `340 MW_th`, Kagran `200 MW_th`, Inzersdorf `340 MW_th`, Leopoldau `170-230 MW_th`
    - daraus `1,45-1,51 GW_th` inklusive Leopoldau
    - offizieller 2023-Jahresenergieanker `Spitzenkessel = 522,3 GWh/a` ist damit konsistent, weil das bei `~1,45 GW_th` rund `360` Vollbenutzungsstunden ergibt
    - der bisherige `2,2 GW_th` Wert bleibt nur als alter winter-fit Benchmark-Proxy dokumentiert und soll nicht als historische Wien-Kesselleistung interpretiert werden
    - Fig. 12 ist mit `1,45 GW_th` neu gerechnet; Full-season-/Table-13-/Paper-KPIs muessen spaeter im finalen konsistenten Rerun nachgezogen werden
    - Widerspruch inzwischen für den Thermflex-2023-Paperpfad aufgelöst:
      offizieller Wiener 2023-Anker für `Muell- und Sondermuellverbrennung (eigene) = 1.199,981 GWh_th`
      ersetzt den älteren Repo-Potenzialanker `district_waste_incineration_gwh_per_year_max = 811,11`
    - aktueller Paper-Schnitt:
      `district_waste_incineration_gwh_per_year_max = 1200,0` und
      `district_waste_incineration.installed_kw_th_fixed = 160000` bei `7500 h/a`
  - spaeter fuer NPC/LCA getrennt festziehen, sobald die Brightway-/Ecoinvent-Mappings dafuer sauber stehen
- [ ] Demand Response im künftigen Dispatch explizit modellieren: thermische Flexibilität (`space_heat`), verschiebbare elektrische Lasten, ggf. Curtailment mit Penalty und rollierende Re-Dispatch-Logik
- [ ] Gebäude-Thermflex-Constraint-SSOT explizit schneiden und nicht implizit im Regler verstecken:
  - `reference_control_mode` bewusst setzbar lassen (`constant` als Default, `day_night` ebenfalls als Referenzfall)
  - `comfort_band_k`, `max_flex_duration_h` und `max_flex_events_per_day` als agnostische Settings führen
  - Literaturanker dafür sauber dokumentieren:
    - Komfortband in Anlehnung an Ghilardi/Lavinia (`±1...±2 K` als plausibler Bereich)
    - zeitliche Aktivierung eher als DR-/Thermflex-Event mit begrenzter Dauer statt dauerhaft aktivem Band
  - Komfortband später nicht als permanentes Setpoint-Absenken missbrauchen, sondern als optimizer-aktivierbare Abweichung modellieren
- [ ] `milp_two_stage`-Thermflexpfad jetzt gezielt validieren und härten:
  Temperaturzustand `T_in[t,m]`, endogene DH-Raumwärme, `comfort_band_k`, `max_flex_duration_h`, `max_flex_events_per_day`
  und Rolling-State-Übergabe sind jetzt im Zweistufenpfad drin.
  - expliziten Wien-`milp_two_stage`-Smoke/Debug-Runner mit Szenariolabels, Wahrscheinlichkeiten und KPI-Ausgabe pflegen
  - Rechenlast/Tractability für größere Horizonte und reduzierte Szenariobündel sauber benchmarken
  - Indoor-Temperatur/Flex nicht heuristisch verwässern; optimizergetriebete Nutzung des Komfortbands mit Dauer-/Event-Limits beibehalten
- [ ] Dokumentation nicht implizit über Overrides oder verstreute Run-Dateien tragen; später einen eigenen Documentation-Layer für reproduzierbare Run-Cases, Modellsemantik und Thermflex-/Dispatch-Annahmen schneiden
- [ ] Inneren MILP-/Dispatchpfad stärker über Settings modularisieren statt Logik zu verstreuen:
  - operative Objective-Namen (`dispatch_cost_eur`, `fuel_cost_eur`, `mc_auction_import_cost_proxy_eur`, ...)
  - Thermflex-MILP-Parameter (`comfort_band_k`, `max_flex_duration_h`, `max_flex_events_per_day`, Penalties, ggf. Terminalbedingungen)
  - keine doppelte Abbildung derselben stündlichen MILP-Constraints im äußeren `Settings/problem/constraints.py`
- [ ] DH-Economics gegen Technologie-Katalog weiter härten:
  - `district_gas_boiler` ist jetzt mit Katalog-Proxy für CAPEX/fixed O&M/variable O&M ergänzt; diesen Schnitt später noch gegen Wien-/AT-spezifische Kostenquellen plausibilisieren
  - `district_heat_pump.capex_eur_per_kw_th = 900` ist derzeit nur plausibel, aber noch nicht sauber auf einen konkreten Katalogfall (Quelle/Größe/Temperaturniveau) gemappt
  - `district_thermal_storage.capex_eur_per_kwh_th = 40` ist noch nicht aus einer belastbaren katalognahen Speicher-SSOT abgesichert
  - `district_external_heat.variable_opex_eur_per_kwh_th = 0.0` bleibt vorerst eine Modellannahme und keine validierte Kataloggröße
  - `district_biomass_chp` und `district_gas_chp` wirtschaftlich noch systematisch gegen Katalog prüfen; aktuelle Größenordnungen wirken plausibel, sind aber noch nicht sauber als katalogbasierter Referenzschnitt dokumentiert
  - bei CHP-Kosten die Leistungsbasis (`kW_el` vs. `kW_th`) über die aktiven Technologieblöcke hinweg harmonisieren oder die unterschiedliche Basis explizit dokumentieren
- [ ] Weitergehende Demand-Response-Strategie nach dem ersten day-ahead Dispatch vertiefen; aktueller Fokus zuerst auf sauberem Dispatch-Kern ohne voll ausgebautes DR-/Marktmodell
- [ ] Verkehrs- und Industriepfad für den neuen Wiener Gebäudekohorten-Schnitt bewusst separat halten:
  Industrie vorerst nicht in die Gebäudekohorten mischen, sondern später als eigener exogener Sektorblock (`industry_electric_demand`, ggf. `industry_process_heat_demand`) behandeln;
  Verkehr vorerst ebenfalls außerhalb der Gebäudekohorten halten und nur den bestehenden EV-/V2H-Pfad separat berücksichtigen.
  Für den EV-Block liegen jetzt erste Wien-Anker vor:
  - aktueller BEV-Bestand grob `~45.300` als Inferenz aus Statistik Austria `741.985 Pkw in Wien` und `6,1 % Elektro-Pkw`
  - grober heutiger EV-Stromanker `~118 GWh/a` als V1-Inferenz aus `0,2 kWh/km` und `13.000 km/a`
  - offizielle Wiener Zukunfts-Szenarien aus `Stadt am Strom(e)`:
    - `2030: 697-915 GWh/a`
    - `2040: 1.775-2.802 GWh/a`
  Diese EV-Größen sollen später als separater Verkehrsblock in die Gesamtstrombilanz eingehen und nicht in `residential` oder `non_residential` hineingezwungen werden.
  Aktueller Fokus für die Kohortenmodellierung bleibt damit auf `residential` und `non_residential_buildings`.
- [ ] Agent-based / multi-agent Dispatch als späteren alternativen Dispatch-Pfad evaluieren; erst nach stabilem zentralem MILP-/IES-Dispatch
- [ ] AI-/RL-Dispatch nur mit verstärkter Constraint-Behandlung aufbauen: Action-/Feasibility-Projection, harte Nebenbedingungen und spätere zusätzliche Restriktionen explizit absichern
- [ ] Learning später intelligent an stochastic dispatch andocken: Unsicherheit nicht nur exogen vorgeben, sondern gelernte Komponenten für Szenario-/Fehlerstruktur und insbesondere Second-Stage-/Recourse-Approximation prüfen
- [ ] Für stochastic dispatch später prüfen, welche Recourse-Größen sich günstig durch Learning approximieren lassen (`expected_recourse_cost`, `worst_case_unserved`, Speicher-/HP-/Grid-Nachregelbedarf), ohne die harte erste Stufe oder Kern-Constraints aufzugeben
- [ ] Pakete/Tooling für probabilistische Forecasts, Szenariogenerierung und gelernte Recourse-Approximation evaluieren, damit die spätere Learning-Kopplung auf etablierten Methoden statt Eigenbau aufsetzt
- [ ] `run_optimization.py`-/Scheduler-/Reporting-Drumherum für den neuen IES-Pfad weiter härten; direkte Gold-/Surrogate-Läufe funktionieren, aber der volle orchestrierte Hauptpfad sollte noch gegen Meta-Run-/Reporting-Ränder verifiziert werden
- [ ] `district_solar_thermal` und `district_waste_incineration` erst dann in Bounds/Optimizer/NPC/LCA als echte Designvariablen ziehen, wenn dafür belastbare bestehende SSOT-Strukturen vorliegen: echte Bounds, validierte Standortkosten und saubere KPI-/LCA-Anbindung; bis dahin bewusst keine impliziten Default-Zahlen oder stillen Null-Fallbacks
- [ ] Bis zur echten Optimizer-Anbindung `district_solar_thermal` und `district_waste_incineration` nur über explizite Settings-Fixed-Capacities fahren (`settings.district_solar_thermal.installed_kw_th_fixed`, `settings.district_waste_incineration.installed_kw_th_fixed`); keine impliziten Param-Defaults
- [ ] Solarthermie als temperaturfähige DH-Quelle modellieren statt nur als generische `kWh_th`-Quelle:
  direktes Einspeisen nur wenn das Quelltemperaturniveau den erforderlichen DH-Vorlauf wirklich erreicht;
  sonst nur Rücklaufvorwärmung / Speicherladung / Booster-Pfad zulassen.
  Dafür ein einfaches thermisches Quellenmodell mit `q_solar_useful`, Temperatur-/Feasibility-Check für `direct_feed` und Diagnose des maximal auf Vorlauf bringbaren Massenstroms aufbauen; erst danach entscheiden, ob dafür später wirklich `pandapipes` nötig ist.
  Die Netztemperatur dafür in v1 nicht frei erfinden, sondern wettergeführt ansetzen:
  `network_supply_temp_c = heating_curve(T_outdoor)` mit Wiener historischen Ankern aus Umweltbundesamt `REP-0074`
  (`95 C` Sommerminimum, gleitend bis `150 C` Wintermaximum; Rücklauf typischerweise `55-75 C`).
  `pinch_point_c` als explizites Setting führen.
  Der erste feste Wien-v1-Referenzschnitt liegt jetzt in
  [network_temperature_curve.py](/c:/Users/Philipp%20Thunshirn/Desktop/PhD/Python%20model/Master/Data/district_heating/Vienna/network_temperature_curve.py)
  als lineare Legacy-Kurve zwischen den dokumentierten Ankern; spaeter bei Bedarf mit mehr Stuetzpunkten aus den Wien-Energie-Kurvenblaettern verfeinern.
  Für die Kollektorphysik v1 im Produktionspfad `oemof.thermal` als schlanken Paketanker bevorzugen;
  `TESPy` vorerst nicht in den Hauptpfad ziehen, sondern nur später als separates Sidecar-Validierungswerkzeug für ausgewählte Temperatur-/Massenstromfälle verwenden.
  Wenn `collector_tilt_deg` und `collector_azimuth_deg` im Paketpfad aktiv genutzt werden,
  muss die Strahlungszerlegung explizit festgelegt sein; v1-Annahme dafuer:
  `irradiance_decomposition_model = "erbs"`.
  Kein stilles Erfinden von `diffuse`-Strahlung.
  Der jetzige Repo-Schnitt ist:
  - `irradiance` im Wiener Profilpfad = `GHI`
  - `GHI -> Erbs -> DHI/DNI`
  - `oemof.thermal` fuer den Kollektorertrag
  - vektorisierte Verfuegbarkeitsvorbereitung ueber die Stundenserie
  - im heuristischen IES-Pfad jetzt `direct -> preheat -> storage -> spill` am DH-Bus umgesetzt
  - im gekoppelten MILP-Pfad jetzt derselbe Schnitt ueber
    `district_solar_thermal_direct_available_th` und
    `district_solar_thermal_total_useful_available_th`;
    `district_solar_thermal_direct_feed`, `district_solar_thermal_preheat` und
    `district_solar_thermal_storage_charge` werden im Result explizit ausgewiesen
  Wichtige aktuelle methodische Einschraenkung:
  - `oemof.thermal.flat_plate_precalc(...)` bewertet den Kollektorertrag auf einem vorgegebenen Temperaturniveau,
    berechnet aber nicht von selbst die maximal einspeisbare Netztemperatur.
  - Diese Temperaturfaehigkeit muss fuer den DH-Pfad daher zusaetzlich modelliert werden
    (z. B. ueber `direct_feed`/`return_preheat`/`storage`-Logik oder iterative Temperatursuche).
  Noch offen:
  - die Interaktion mit HP/CHP/Boiler spaeter noch staerker temperaturseitig absichern, statt `preheat` nur als Restlastreduktion zu behandeln
  Verwendete v1-Parameter dokumentiert in `Documentation/Sources/solarthermie_dh_literatur.md`:
  - verglaster Flachkollektor `eta_0 = 0.78`, `a_1 = 3.2`, `a_2 = 0.015`
  - `specific_nominal_capacity_kw_per_m2 = 0.671`
  - `collector_azimuth_deg = 180`
  - `collector_tilt_deg = 50`
- [ ] KPI-/Kosten-/LCA-Pfad für neue DH-Technologien nachziehen; aktuell berücksichtigen `compute_objectives` und `financial_model` im Wesentlichen nur PV/BESS/Grid/H2 sowie `wood_gasifier`
- [ ] LCA-Anbindung der neuen DH-/IES-Technologien erst nachziehen, wenn die Systemgrenzen und Proxy-Annahmen sauber festgezogen sind
- [ ] Cost-/Data-Struktur lesbarer schneiden: standortbezogene Preise unter `location`, technologiespezifische Preise/Kosten in technologiespezifische Unterstrukturen auslagern
- [ ] Offline-Kalibrierungspipeline fuer thermische Archetypen anlegen:
  - High-Fidelity-Teacher bewusst ausserhalb des Runtime-Dispatchs halten
  - V1 darf weiterhin mit einem gemeinsamen thermischen `usage_profile` fuer alle Kohorten arbeiten; kohortenspezifische Nutzungs-/Belegungs-/ACH-Profile erst spaeter als Upgrade einfuehren
  - je Archetyp/Kohorte standardisierte Anregungsfaelle definieren:
    - freier Auskuehltest
    - Preheat-Test
    - Cutback-/Abschalttest
    - Recovery-/Rebound-Test
    - Sommer-/Winter-/Uebergangstag
  - daraus reduzierte Runtime-Parameter fitten:
    - `UA`
    - `C_th`
    - effektive Preheat-Kapazitaet
    - zulaessige Absenkdauer
    - Rebound-/Recovery-Kennwerte
  - kalibrierte Archetypen als eigene SSOT-Datenebene versionieren statt im Solver zu verstecken
  - Runtime-Anbindung spaeter ueber Kohorten-/Archetypen-Mapping in den bestehenden Thermflex-/Building-Pfad schneiden
  - nach dem erfolgreichen Wien-`pseudo_epw`-Mini-Smoke den naechsten Schritt schneiden:
    - [x] Teacher-Input aus bestehenden Archetypen/Kohorten ableiten
    - [x] standardisierte Experimente (`free_float`, `preheat`, `cutback`, `recovery`) definieren
    - [x] erster echter Teacher-Pilot aus `teacher_inputs_v1.json` und `experiment_library_v1.json`
    - [x] Teacher-Schedule-Skalierung fuer interne Gewinne / Infiltration / Ventilation korrigieren, damit
      absolute Zeitreihen nicht nochmals als rohe `Fraction`-Schedules missinterpretiert werden
    - [ ] Reduced-order-Fitter fertigziehen:
      - [x] erster fail-fast Fit fuer `reference + free_float`
        - Export von `H_total`, `UA_transmission`, `C_th`, `tau`
        - Batch-Outputs unter `Technical_model/technologies/buildings/calibration/_reduced_order_fits/`
      - [x] Rebound-/Recovery-Kennwerte aus Event-Experimenten nachziehen
        - explizite `cold_year`-Baselines gleicher Dauer verwenden
        - keine Vergleiche ueber unterschiedliche Wetterjahre hinweg
      - [x] klaren Exportpfad fuer `calibrated_v1` schneiden
        - Sidecar-SSOT unter `Data/thermal_archetypes/Vienna/`
        - Runtime-Anbindung bleibt als explizite Folgeentscheidung offen
    - [ ] den ersten Teacher-Pilot fachlich plausibilisieren:
      - pruefen, ob die reparierte Schedule-Skalierung fuer weitere Kohorten/Experimente stabil bleibt
      - Referenz-Setpoint-Schnitt
      - vereinfachte Teacher-Geometrie / Solargewinne
      - bei Bedarf spaeter exakte `EnergyPlus`-Heat-Balance-Outputs fuer Solar/Luftwechsel nachziehen; V1 nutzt hier bewusst transparente Approximationen statt stiller Annahmen
      - erst danach Batch-Lauf ueber weitere Kohorten/Experimente
- [ ] Vor dem ersten echten `npc_eur + climate_change`-/All-Impact-Lauf den Cost-/LCA-Pfad explizit komplettieren:
  - Economics-SSOT festziehen, welche aktiven Technologien als investierbare Assets und welche als bestehende/exogene Referenzblöcke behandelt werden
  - für `district_solar_thermal` und `district_waste_incineration` validierte Standortkostenblöcke nachziehen und `validated=True` erst nach belastbarer Datengrundlage setzen
  - für `district_external_heat` und `district_gas_boiler` explizit entscheiden, ob Opex-only als Benchmark-Proxy reicht oder ob Capex/O&M ebenfalls in `financial_model` rein müssen
  - Brightway-/Ecoinvent-kompatible LCA-SSOT pro aktivem Technologieblock anlegen; mindestens für:
    `district_external_heat`, `district_gas_boiler`, `district_heat_pump`, `district_thermal_storage`,
    `district_wood_chip_boiler`, `district_biomass_chp`, `district_biogas_chp`, `district_gas_chp`,
    `district_geothermal`, `district_solar_thermal`, `district_waste_incineration`
    sowie zusätzlich für `small_wind`, `large_wind`, `biogas_engine`, `wood_gasifier`, falls diese im Lauf aktiv bleiben
  - statische Export-/Importkette in `Data/LCA_data/static/<country>/` und `Data/LCA_data/lca_facade.py` auf diese Technologien erweitern; aktuell werden dort im Wesentlichen nur `PV`, `BESS`, `Grid`, `ELY`, `H2_TANK` und `fuel_cell_PEM` injiziert
  - `Optimization/framework/engines/kpi.py` erweitern: `_require_dh_lca_coverage(...)` ist schon fail-fast, aber `_total_lca_metric(...)` summiert aktuell neue DH-/IES-Technologien noch nicht mit
  - nach Daten- und KPI-Erweiterung einen kleinen Gold-Einpunkt-/Smoke-Lauf mit `objectives = ['npc_eur', 'climate_change']` auf dem aktuellen Wien-Referenzpfad fahren
  - erst wenn Gold damit stabil läuft, den Surrogat-Pfad auf die aktuelle Wien-Signatur und Ziele `npc_eur`/`climate_change` retrainen und danach `successive_halving`/`hyperband` aufsetzen

## Szenario- und Transformationsblock spaeter konkretisieren

- [ ] Schlanken `scenario`-Top-Layer vorsehen statt verstreuter Year-/Policy-/Price-Overrides.
- [ ] Zeitscheiben voraussichtlich `2023 -> 2030 -> 2035 -> 2040` als Transformationspfad schneiden.
- [ ] `2023` als Referenz-/Startwelt fixieren; spaetere Jahre als Transformationspfad behandeln.
- [ ] `allow_new_fossil_build = false` fuer neue fossile Strom-/DH-Kapazitaeten als explizite Szenarioannahme pruefen und spaeter im Szenario-Layer abbilden.
- [ ] Fossilrueckgang moeglichst nicht primaer exogen fixieren, sondern aus `GHG cap + Nachfragepfad + EE-/DH-/Speicher-Ausbau` ableiten.
- [ ] Nur schlanke Policy-/Transition-Limits als Leitplanken vorsehen:
  - `existing_fossil_capacity_max_by_year`
  - optional `existing_fossil_max_full_load_hours_by_year`
  - optional Rest-/Reservebetrieb bis spaetere Jahre
- [ ] Wiener Klimafahrplan / Waermeplan als Begruendung fuer steigenden DH-Anteil, keinen abrupten fossilen Sofortausstieg und eine Peak-/Reserve-Rolle gasbasierter Anlagen im Uebergang dokumentieren.
- [ ] Exakte Schwellenjahre und Reduktionssaetze (`2030/2035/2040`) als Modellannahmen transparent festziehen; diese kommen nicht 1:1 aus Wiener Vorgaben.
- [ ] Preis-/Marktlogik zunaechst als exogene Zukunftswelten statt internem Marktmodell schneiden:
  - Stromimport-/Exportpreise
  - Gaspreis
  - Biomasse-/Biogaspreise
  - CO2-Preis
- [ ] Technologie-Kostendegressionen spaeter aus Literatur/Reports hinterlegen:
  - PV/Wind eher IRENA-/offizielle Kostenreports
  - H2/Elektrolyse eher EU/IEA-/Marktberichte
- [ ] `H2-ready`-/Wasserstoff-Reservepfad nicht als Basisszenario, sondern hoechstens als eigene Zukunftswelt fuehren.
- [ ] Szenariologik zuerst als fachlichen Blueprint finalisieren und erst danach implementieren.
- [ ] Diesen gesamten Szenario-/Transformations-/Preiswelt-Block bewusst als moegliches separates Journal-Paper-Thema behandeln und nicht in den engeren Wiener Gebaeude-Thermflex-Scope hineinziehen.
- [ ] Zu den neuen `surrogate_train`-Faellen auch fuer `baseline_constant_no_thermflex` und `day_night_no_thermflex` groeßere Trainingslaeufe ziehen, damit die drei Vergleichsmodi nicht nur als Mini-Smokes vorliegen.
- [ ] `surrogate_ready` spaeter wieder aufnehmen:
  - `milp_two_stage`
  - Teacher-Kosten reduzieren oder kleinere Trainingssaetze/Parallelisierung pruefen
  - erst dann als ernsthafter Truth-naeherer Ausbaupfad verwenden
- [ ] Reuse-/Caching-Pfad fuer den Click-Trainingspfad verbessern:
  - `Optimization/run/runners/train_surrogate.py` / `auto_train_surrogate(...)` staerker an den nativen `Learning/training/train_surrogate.py`-Dataset-Append-/Reuse-Mechanismus anbinden
  - identische Family-Samples nicht erneut als Teacher rechnen, wenn bereits im aktiven Dataset vorhanden
- [ ] Teacher-Parallelisierung fuer die neuen `surrogate_train`-Faelle kontrolliert pruefen:
  - zuerst `milp_day_ahead` mit kleinem `teacher_n_workers > 1`
  - spaeter `milp_two_stage` nur vorsichtig wegen RAM-/Solver-Druck
- [ ] Thermflex-/Flex-SSOT fuer Paper und Export weiter festziehen:
  - Peak-Aenderung
  - zusaetzliche Raumwaermeenergie
  - Rebound
  - Aktivierungsstunden
  - terminale Zustaende
  - heat-up / heat-down ramps
  - effective thermal storage
  - max preheat headroom
- [ ] Aus der Thermflex-/Marktliteratur gezielt uebernehmen und sauber dokumentieren:
  - `schedule-based` vs. `price-based` Vergleichslogik
  - Peak-/Mehrenergie-/Komfort gemeinsam reporten, nicht nur verschobene Energie
  - Marktintegration nach Zeitstufen denken:
    `day-ahead`, `intraday`, `balancing`
  - DH-/Flex-Metriken nach direkter Quantifizierung schneiden:
    Rampen, Input-Limits, Speicherkapazitaet statt nur Black-Box-Simulation
- [ ] DH-Bus-Scaling fuer die Building-Calibration spaeter an einen echten Szenario-/DH-SSOT anbinden:
  - nicht dauerhaft nur ueber Laufargument `--dh-share`
  - aber auch nicht wieder still im Calibration-Config hardcodieren
- [ ] Teacher-Solarwelt nach dem neuen Review differenzieren:
  - kohortenspezifische Glazing-/SHGC-Annahmen nur mit expliziter Quellenbasis
  - kohortenspezifische Shading-/Solar-Expositionsannahmen sauber in die Archetypen-SSOT ziehen
  - keine impliziten oder ad-hoc gesetzten Solar-Multiplikatoren in den Teacher schmuggeln
  - Residential-V1 jetzt explizit ueber Austrian TABULA/EPISCOPE weiterziehen:
    - `construction_period -> window typology class`
    - danach erst `window_u_value` und `g/SHGC` sauber in die Archetypen-SSOT schneiden
  - die periodische Residential-`window_typology_class` ist jetzt bereits im neuen Archetypen-/Teacher-Input-SSOT verdrahtet; numerische `g/SHGC`-Werte bleiben aber noch offen
  - TABULA-Verfahrenswerte (`Fsh`, `FF`, `FW`) hoechstens als methodische Fallback-/Plausibilitaetsanker verwenden, nicht als versteckte Wiener Kohortenwahrheit
  - OIB-Referenzwerte (`g = 0.67`, `20 C`, `26 C`, Luftwechselanker) nur als oesterreichische Plausibilitaetschecks nutzen
  - fuer `non_residential` gezielt bessere Quellenbasis suchen:
    - zuerst pruefen, ob `ZEUS` / `ImmoZEUS` oder andere oesterreichische Nichtwohn-Daten verfuegbar sind
    - solange nicht, bleibt `non_residential`-Geometrie/Solar im Repo bewusst als offener V1-Block markiert
- [ ] Nach `calibrated_v1` explizit entscheiden, wie die Runtime-Anbindung aussehen soll:
  - [x] selektive Uebernahme von `H_total` / `C_th` / effektiven Verlustparametern in den bestehenden Thermflex-/Runtime-Pfad
  - [x] expliziten Variant-Schalter `default | calibrated_v1` statt stiller Umschaltung
  - [x] `event_response_v1` aktiv als Peak-/Eventenergie-/Recovery-Cooldown-Bounds in den Thermflex-Pfad schneiden
  - [ ] `recovery_rebound_energy_kwh` entscheiden:
    - KPI/Penalty belassen
    - oder spaeter als harte Rebound-Constraint einziehen
  - [x] Paper-SSOT nachziehen:
    - aktive Event-Bounds und deren Quelle in den Dispatch-/Thermflex-KPIs mit ausweisen
  - [x] Wiener `milp_day_ahead`-Paperfaelle auf gemeinsame explizit feasible Designbasis unter `calibrated_v1` umstellen
  - [ ] Spaeter pruefen, ob die gemeinsame Paper-Designbasis aus einem dedizierten Benchmark-/Sizing-Schritt
    statt aus einem gemeinsamen feasiblem Surrogat-Truth-Punkt abgeleitet werden soll
  - [x] Thermflex fuer den Paper-Schnitt auch als sauberen konstanten Isolationsfall rechnen:
    - `constant_no_thermflex`
    - `constant_thermflex`
    - ohne Mischwirkung aus `day_night`
  - [ ] fuer den konstanten Thermflex-Isolationsfall spaeter noch bewusst entscheiden, ob:
    - `constant_lower_bound_c = 21.0` der finale Paper-Schnitt bleibt
    - oder ein alternativer konstanter Komfortboden separat als Sensitivitaet gerechnet wird
  - [ ] Surrogat nach dem neuen Thermflex-/`calibrated_v1`-Schnitt nachziehen:
    - [x] Truth-Dataset / Holdout mit aktiven Event-Bounds neu pruefen
    - [x] `xgb + gold_recheck` auf dem leichteren `milp_day_ahead`-Pfad stabilisieren
    - [x] Trainingsdaten-SSOT als Family-Dataset-Layer explizit schneiden und dokumentieren:
      - `Learning/datasets/<family_hash>/` als offizieller Dataset-Pfad
      - `truth_dataset.csv` und `truth_dataset.meta.json` als lesbarer Truth-Export
      - `family_spec.json` und `source_runs.json` zur Einordnung und Reproduzierbarkeit
      - `teacher_eval/summary.json` und `teacher_eval/infeasible_points.csv` fuer Teacher-Audit
      - `truth_dataset.csv` nur ueber den offiziellen CSV-Exportpfad erzeugen, nicht ad hoc
      - Reuse/Caching nicht nur fuer feasible, sondern auch fuer bereits bekannte infeasible Truth-Punkte
    - [x] fokussierten Surrogat-Targetschnitt als explizite `target_profile`-SSOT schneiden:
      - `dispatch_publish_core`
      - `dispatch_optimization_core`
      - keine stille heuristische Target-Aufblaehung mehr im Runtime-Code
    - [ ] den aktuellen Wiener Optimierungs-Surrogatpfad weiter ausbauen:
      - `dispatch_optimization_core` als aktive Arbeitsbasis halten
      - naechsten Append-Lauf auf derselben Family fahren statt neue Silos aufzubauen
      - `dispatch_operating_cost_eur` weiter beobachten:
        - aktuell extrem geringe Varianz im feasiblem Raum
        - `R2` daher wenig aussagekraeftig trotz sehr kleinem rel. Fehler
      - [x] erste echte Surrogat-Optimierung auf diesem 11-Target-Schnitt fahren
      - [x] expliziten Top-k-Gold-Recheck-Layer fuer Surrogat-Pareto-Punkte einfuehren
      - [ ] den Recheck-Layer jetzt systematisch als SSOT nutzen:
        - Surrogat-Top-k immer zuerst gegen Gold `milp_day_ahead`
        - danach nur beste day-ahead-feasible Kandidaten gegen `milp_two_stage`
      - [ ] naechsten Suchraum-/Ranking-Schritt explizit entscheiden:
        - [x] expliziten Multiobjective-Schnitt pruefen
          (`dispatch_cost_eur` + `co2_emissions_total_t`)
        - [x] die biobjektive Pareto-Menge fuer die naechste Optimierungsrunde
          systematisch ausduennen:
          - `biobj_cost_end`
          - `biobj_co2_end`
          - `biobj_mid_tradeoff`
          - nur explizit gold-feasible Kandidaten akzeptieren
        - [x] finale Auswahl zusaetzlich zu `pareto_points.csv` explizit exportieren
          fuer Recheck-/Paper-Auswahl:
          - `selection_summary.json`
          - `selection_audit.csv`
          - echte Gold-Runs unter `Optimization/run/results/Vienna/gold/biobj_gold_candidates_*`
        - Grund: der aktuelle single-objective Cost-Schnitt ist zu flach; der biobjektive
          Pfad liefert im Recheck robustere day-ahead-feasible Kandidaten
      - [ ] die biobjektive Gold-Auswahl jetzt als Paper-Hauptpfad auswerten:
        - `day_night_thermflex` gegen
          - `biobj_cost_end`
          - `biobj_co2_end`
          - `biobj_mid_tradeoff`
        - Kernaussagen fuer Cost/CO2/Thermflex/Dispatch-Mix komprimieren
      - [ ] den neuen triobjektiven Peak-Pfad methodisch sauber machen, bevor er
        paperseitig interpretiert wird:
        - `dh_total_peak_change_kw` ist jetzt technisch als SSOT verdrahtet
        - auf dem aktiven `upper_only dur24 evt24`-Jan-17-Smoke bleibt der
          absolute `dh_total`-Peak aber unveraendert
        - Gold-Recheck zeigt:
          - Peakstunde bleibt bei `hour 4`
          - fast die gesamte sichtbare DH-total-Abweichung faellt nur in der
            letzten Stunde an
          - Ursache ist der aktuell noch ausnutzbare Terminal-Deviation-Pfad,
            nicht fehlendes Objective-Plumbing
        - naechste saubere Methodenentscheidung:
          - entweder `allow_terminal_deviation` fuer diesen Peak-Pfad schliessen
          - oder laengeren Solve-Horizont rechnen und nur ein inneres 24h-Fenster
            fuer Peak-/Cost-/CO2-KPIs auswerten
        - erst danach `cost + co2 + dh_total_peak_change_kw` erneut als echte
          Thermflex-Peakstory bewerten
      - [ ] alle Paper- und Surrogat-Referenzlaeufe nach dem Gebaeudelast-Einheitenfix neu aufsetzen:
        - Root cause lag in `Technical_model/consumption/heating_anc_cooling_consumption/heating_and_cooling.py`
        - die alten KPI-Staende mit explodierter Kuehllast sind fuer Paper-Interpretation nicht mehr gueltig
        - mindestens neu rechnen:
          - `baseline_constant_no_thermflex`
          - `baseline_constant_thermflex`
          - `day_night_no_thermflex`
          - `day_night_thermflex`
        - danach:
          - Paper-Vergleichsplots neu bauen
          - Surrogat-Truth-Store fuer betroffene Families erneuern oder klar versionieren
      - [ ] aus dem konstanten Thermflex-Sensitivitaetsblock jetzt die eigentliche Modellentscheidung ziehen:
        - vorhandene Befunde unter
          - `paper_dispatch_comparison_20260403_114641`
          - `paper_dispatch_comparison_20260403_124056`
        - explizit auswerten:
          - reicht ein globales `max_flex_duration_h` fuer den Paper-Hauptpfad?
          - oder braucht es kohortenspezifische Dauer-/Event-Grenzen?
        - [x] dafuer die Kohortenwirkung direkt sichtbar machen:
          - `constant_thermflex_cohort_utilization_hourly.csv`
          - `constant_thermflex_cohort_utilization_summary.csv`
          - `constant_thermflex_cohort_utilization.png`
          - pro Kohorte realisierte `preheat`-/`cutback`-Energie
          - aktive Flexdauer
          - Recovery/Rebound
        - Ziel:
          - nicht nur System-KPIs, sondern auch Kohorten-Use/Underuse sichtbar machen
        - erst danach entscheiden, ob:
          - globales Dauer-Cap ausreicht
          - kohortenspezifische Bounds noetig sind
          - oder `milp_two_stage` fuer diese Fragestellung zusaetzlich gebraucht wird
      - [x] gezielten `milp_two_stage`-Endpunkt-Check fuer die wichtigsten biobjektiven Kandidaten fahren:
        - `biobj_co2_end`
        - `biobj_mid_tradeoff`
        - initialer Befund:
          - die fruehen Endpoint-Replays kippten
          - explizit dokumentiert ueber `two_stage_endpoint_summary.json`
      - [x] die erste wesentliche Two-Stage-Luecke fuer den Paperpfad analysieren und schliessen:
        - erster harter Two-Stage-Bruch war der fehlende member-level Thermflex-Export im gekoppelten Pfad
        - das ist jetzt in `dispatch/modes/milp_two_stage.py` geschlossen
        - zusaetzlicher Fix auf dem Weg:
          - CO2-Tagesproxy im historischen Szenariobau von der Gaspreislogik entkoppelt
        - reproduzierter Ladder-Status fuer `biobj_co2_end`:
          - `raw1_red1`: feasible
          - `raw4_red1`: feasible
          - `raw8_red2`: feasible
          - `raw16_red3`: feasible
          - `raw48_red6`: feasible
      - [ ] optionalen zweiten Voll-Recheck fuer `biobj_mid_tradeoff` ziehen, wenn dieser Kandidat im Haupttext oder in einer Robustheitsfigur gezeigt werden soll:
        - nicht mehr noetig, um die grundsaetzliche `day_ahead -> two_stage`-Bruecke zu belegen
        - aber sinnvoll, falls mehr als ein biobjektiver Endpunkt explizit im Paper als Two-Stage-Beispiel auftaucht
      - [ ] Surrogatguete fuer den aktiven Wiener DH-/Thermflex-Pfad deutlich verbessern, bevor der Layer im Paper staerker getragen wird:
        - der aktuelle Hauptlauf `surrogate_opt_l96` ist als Such-/Rankinghilfe brauchbar, aber noch nicht stark genug fuer alle Kern-KPIs
        - insbesondere `dispatch_operating_cost_eur` und `thermflex_shifted_space_heat_kwh` sind aktuell nicht ausreichend getroffen
        - naechste Hebel:
          - mehr feasible Teacher-Punkte im relevanten DH-/Thermflex-Bereich
          - fokussierterer Targetschnitt statt zu breiter gemeinsamer Ziellandschaft
          - Sampling staerker auf aktive Thermflex-/DH-Regionen konzentrieren
          - getrennte oder besser geschnittene Modelle fuer physische Flows vs. cost-/penalty-dominierte Ziele pruefen
      - [ ] `milp_two_stage` fuer das Paper explizit als historischer Robustheitscheck rahmen:
        - nicht als Hauptsuchpfad
        - nicht als impliziter Replay derselben Stundenentscheidung
        - sondern als:
          - gleicher Design-/Policy-Punkt
          - neue stochastische Dispatch-Optimierung
          - ueber reduzierte historische Tagesszenarien
      - [ ] Szenarioreduktionspfad fuer den Two-Stage-DH-Schnitt methodisch finalisieren:
        - `scenario_feature_keys` und `distance_metric` sind jetzt explizit verdrahtet
        - aktuellen aktiven Default im Paper sauber begruenden:
          - `ambient_temperature_c`
          - `grid_import_price`
          - `district_space_heat_demand`
          - `co2_price_eur_per_tco2`
        - Gaspreis optional halten; nicht unnötig aufblasen, solange nur Monats-Proxy
      - [ ] Szenarioreduktions-Sensitivitaet dokumentieren:
        - fuer denselben Two-Stage-Kandidaten `n_reduced = 1, 2, 3, 6` gegenchecken
        - zeigen, dass die Richtung bei Cost/CO2/Thermflex nicht voellig kippt
        - den finalen `48 -> 6`-Schnitt damit methodisch begruenden
      - [ ] historische Unsicherheitsbasis fuer das Paper sauber beschreiben:
        - Representative Days als Mechanismus-/Policy-Ebene
        - Two-Stage-Historicalszenarien als Robustheitsebene
        - nicht als Ersatz fuereinander, sondern als zwei komplementaere Auswertungsebenen
      - [ ] den neuen Representative-Day-Block jetzt in eine eigentliche Paper-Entscheidung uebersetzen:
        - Artefakte:
          - `Optimization/run/results/Vienna/gold/dh_thermflex_run_20260403_140316`
          - `Optimization/run/results/Vienna/gold/constant_thermflex_representative_day_summary_20260403`
        - entscheiden:
          - welches globale Thermflex-Setting als Paper-Hauptpfad verwendet wird
          - ob der Hauptpfad bewusst ein globales Setting bleibt
          - und welche Representative-Day-Ergebnisse als Sensitivitaetsfigur gezeigt werden
        - aktuelle Befundlage:
          - kein universell dominanter Policy-Fall ueber alle Day-Types
          - `lb21p0_dur24_evt1` oft stark auf Preis-/typischen/Schultertagen
          - `constant_no_thermflex` auf Peak-Heat-/Sunny-Winter-Tagen teils bei Cost/CO2 vorne
      - [ ] zusaetzliche Paper-Figur fuer den Shift-Mechanismus pruefen:
        - ueber den Tag zeigen, welcher Anteil der Energie aktuell thermisch
          variabel / verschiebbar ist
        - im Hintergrund eine Linie fuer `T_in` oder eine daraus abgeleitete
          Innenraumtemperatur-Naehe zum Komfort-/Aktivierungsband legen
        - Ziel:
          sichtbar machen, wann thermischer Spielraum vorhanden ist und wann
          die Gebaeude faktisch ausgereizt sind
      - [ ] Teacher-/EnergyPlus-Figuren fuer die Archetypen als 2x2-Hauptblock kuratieren:
        - Ziel: sichtbar machen, wie sich die Archetypen physikalisch unterscheiden, bevor der Systemdispatch gezeigt wird
        - alle 8 Wiener Archetypen in gemeinsamen Flow-Panels zeigen, nicht als acht separate Small-Multiples
        - bevorzugt 2x2-Quadranten mit je einem Flow pro Panel und farblicher Archetypenkodierung
        - Figure A:
          - Winter-Referenztag / `winter_reference_week`
          - gleiche Zeitachse fuer alle 8 Archetypen
          - erste gute Lesefassung jetzt: `T_in`, `heating`, `window solar gains`, `total losses`
        - Figure B:
          - `winter_cutback_event`
          - gleiches Flow-Set mit Eventfenster
        - Figure C:
          - optional spaeter aggregierter Archetypenvergleich ueber Tagessummen bzw. charakteristische Kennwerte
        - alle 8 aktiven Kohorten explizit mitnehmen:
          - `residential_pre1975`
          - `residential_1975_1990`
          - `residential_1990_2000`
          - `residential_2000_2014`
          - `non_residential_pre1975`
          - `non_residential_1975_1990`
          - `non_residential_1990_2000`
          - `non_residential_2000_2014`
      - [ ] Teacher-Solarpfad nach der neuen periodenspezifischen Residential-Glazing-Zuordnung neu rechnen und beurteilen:
        - `window_typology_class -> SHGC / visible transmittance` ist jetzt im Teacher-Setup explizit verdrahtet
        - als naechstes:
          - Teacher-Inputs/Plots fuer die relevanten Referenzfaelle neu erzeugen
          - pruefen, ob `window solar gains` zwischen den vier Residential-Perioden jetzt sinnvoll sichtbar differenzieren
          - entscheiden, ob `window solar gains` in die Hauptfigur kommen oder nur Appendix bleiben
        - methodische Einordnung:
          - Residential jetzt periodenspezifisch im Teacher angedeutet
          - `non_residential` bleibt expliziter globaler V1-Glazingpfad
      - [ ] Teacher-Figuren von einem einzelnen Referenztag auf papernaehere repräsentative Tagesausschnitte umstellen:
        - der aktuelle Teacher-Hauptplot basiert noch auf `winter_reference_week` und damit effektiv auf einem 24h-Schnitt
        - fuer die naechste Runde besser:
          - die bereits selektierten repräsentativen Tagtypen als Plotfenster aufgreifen
          - oder dafuer explizite Teacher-Experimente an genau diesen Tagen aufsetzen
        - keine schiefe Mischfigur aus nicht gerechneten Tagen bauen; erst den Teacher-Pfad fuer diese Tage sauber definieren
        - Status:
          - explizite 2023-Teacher-Experimente fuer die 5 repräsentativen Day-Types sind jetzt angelegt
          - naechster Schritt ist deren Batch-Ausfuehrung und der Umbau der aktiven Figure-0-Logik darauf
      - [ ] nach dem Nichtwohn-Debug explizit entscheiden, wie `non_residential_2000_2014` im Paper erzaehlt wird:
        - der Null-Fall auf `2023-01-08` ist kein genereller Bug
        - aber fuer die Darstellung sollte klar werden:
          - dass diese Kohorte ueber das Jahr Raumwaerme hat
          - und dass der Null-Fall ein Day-Type-Effekt ist
      - [ ] expliziten Surrogat-Feasibility-Screen weiter nur experimentell halten:
        - erster KNN-Screen ist sauber integriert
        - verbessert den Hauptpfad aber noch nicht robust genug
        - deshalb nicht still als Default aktivieren
    - `milp_two_stage` weiter nur fuer gezielte Truth-/Paper-Endpunkte nutzen
    - Teacher-Reuse/Caching weiter verbessern, damit wiederholte Truth-Punkte nicht unnötig neu gerechnet werden

## Done

- [x] Learning-Layer als Top-Level-Struktur eingeführt
- [x] Family-/Registry-/Bootstrap-Grundlage aufgebaut
- [x] Native Modell- und Dataset-Store in `Learning/` verankert
- [x] Interner Gate-Mechanismus mit `eligible`/`blocked`-Status eingeführt
- [x] Auto-Remediation für geblockte Kandidaten als erster Wurf eingebaut
- [x] Optimierungsresolver so verschärft, dass `candidate`/`blocked`-Native nicht verwendet werden
- [x] Externe Validierung kann dasselbe Artefakt über `Learning` auflösen
- [x] Externe Validierung kann Promotion in `Learning` settings-gesteuert auslösen
- [x] Feasibility-SSOT im Settings-Layer auf schlankes Hybrid-Gate umgestellt
- [x] Erster zentraler FeasibilityGate-Kern im Framework eingeführt
- [x] Scheduler-/Trial-Ranking auf Gate-Labels statt rohe `G<=0`-Logik umgestellt
- [x] Learning-/Surrogat-Layer für `district_solar_thermal` und `district_waste_incineration` auf Wien-all-tech-Signatur erweitert; kontrollierter nativer Retrain plus kurzer Surrogat-Gegencheck laufen
- [x] Dispatch-agnostischen DH-Kern mit `dh_demand.py`, `dh_buildings.py` und `dh_bus.py` eingeführt
- [x] `integrated_energy_system.py` als neuen allgemeinen IES-Systempfad eingeführt
- [x] DH-Großwärmepumpe als erste aktive DH-Quelle in den IES-Pfad eingebunden
- [x] Lokale Heizbereitstellung für den DH-angeschlossenen Anteil im IES-Pfad sauber von der lokalen Haus-HP getrennt
- [x] Zentralen DH-Speicher als `district_thermal_storage_kwh_th` an `dh_bus` und den IES-Pfad angebunden
- [x] Hackschnitzel-Heizwerk als grundlastfähige DH-Quelle mit `district_wood_chip_boiler_kw_th`, Teillast und Fuel-Input in `kg` angebunden
- [x] DH-Technologie-Aktivierung in zentralen `technology_activation`-Block verschoben und DH-Settings/Variablen auf `district_*`-Benennung umgestellt
- [x] Geothermie als nicht regelbare ORC-KWK-Quelle mit `district_geothermal_kw_el`, Strom-/Wärme-Co-Output und geplanter Sommerrevision in den IES-Pfad eingebunden
- [x] Erdgas-KWK als regelbare DH-Quelle mit `district_gas_chp_kw_el`, Strom-/Wärme-Co-Output, Fuel in `kWh`/`m3` und geplanter Sommerrevision in den IES-Pfad eingebunden
- [x] Biogas-KWK als regelbare DH-Quelle mit `district_biogas_chp_kw_el`, Strom-/Wärme-Co-Output, Fuel in `kWh`/`Nm3` und Teacher-/Gold-Flow-Anbindung in den IES-Pfad eingebunden
- [x] Holz-KWK als regelbare DH-Quelle mit `district_biomass_chp_kw_th`, Strom-/Wärme-Co-Output, Fuel in `kWh`/`kg` und Teacher-/Gold-Flow-Anbindung in den IES-Pfad eingebunden
- [ ] Cohort runtime solar path after the dispatch fix still review for
  `non_residential_2000_2014`.
  - Dispatch-level status:
    - the aggregated Vienna cohort path no longer collapses to zero on the
      critical `2023-01-08` slice
    - `district_space_heat_demand_ref` in the `constant_no_thermflex`
      `milp_day_ahead` reference run is now strictly positive across the day
  - Implemented root-cause fix:
    - cohort runtime solar gains now come from
      `irradiance + window transmission` instead of direct reuse of the legacy
      `Solar_gains.csv` profile
    - coupled thermflex now also consumes this member-level solar matrix
  - Remaining review item:
    - `non_residential_2000_2014` still reaches several zero raw hours on the
      same sunny winter day
    - aggregate dispatch demand stays plausible, but the cohort should be
      checked against paper/story expectations before final interpretation
  - Follow-up if needed:
    - inspect whether non-residential V1 glazing / orientation assumptions
      should stay global
    - or whether the paper should simply frame this cohort explicitly as the
      weakest V1 building block
- [ ] Migrate the remaining legacy non-cohort and cooling-side building-demand
  paths off `heating_and_cooling.py` once the active Vienna cohort heating path
  is fully stable.
- [ ] Heizlastpfad nochmals sauber prüfen:
  - exakt klären, was in den aktuellen Plots und Runtime-Serien als `heating` bzw. Raumwärmelast dargestellt wird
  - prüfen, ob diese Größe wirklich die beabsichtigte Heizlast ist oder nur eine abgeleitete Bilanz-/Restgröße
  - für Teacher-, Runtime- und Dispatch-Pfad explizit abgleichen, ob dieselbe physikalische Größe gemeint ist
  - danach entscheiden, welche Heizlastgröße paperseitig gezeigt und wie sie benannt werden soll
- [ ] Thermflex-Paperpfad auf einen expliziten "fixed current system" Boiler-Peak-Test schneiden:
  - `district_gas_boiler_peak_kw` ist jetzt als Objective/KPI technisch sauber verfügbar
  - der erste Mar-15-Smoke mischt aber noch Asset- und Thermflex-Effekt, weil die aktiven DH-Kapazitätsbounds im Surrogatlauf offen bleiben
  - nächster sauberer Schritt:
    - heutiges Wien-System fixieren
    - nur Thermflex-/Dispatchentscheidung variieren
    - dann `dispatch_cost_eur`, `co2_emissions_total_t`, `district_gas_boiler_peak_kw` über die repräsentativen Tage vergleichen
  - gezielt prüfen:
    - warum auf Mar-15 Kosten, CO2 und Boiler-Energie schon sinken
    - aber der absolute Boiler-Peak bei Stunde `4` stehen bleibt
- [ ] Paperfigur-Idee weiterverfolgen:
  - Tages-Shiftplot mit zusÃ¤tzlicher Hintergrundlinie fÃ¼r den thermischen Freiheitsgrad / die noch variable Energie
  - diese Linie soll Ã¼ber den Innenzustand bzw. die NÃ¤he zur oberen Temperaturgrenze erzÃ¤hlen, damit sichtbar wird, wann weiteres Vorheizen Ã¼berhaupt noch mÃ¶glich ist
- [ ] Oil-Sensitivitaet fuer den fossilen Peak-Boiler in die generelle Paper-Sensitivitaetsanalyse integrieren:
  - aktiver v2-Proxy ist seit `2026-05-05` `1/2 Gas + 1/2 Heizoel extra leicht`
  - Effekte auf `dispatch_cost_eur`, `co2_emissions_total_t`, `district_gas_boiler_peak_kw` und Day-Ranking vergleichen
  - nicht als separaten Hauptpfad oder separaten Ergebnisstrang behandeln
  - nur im konsistenten Sensitivitaetsblock ausweisen
- [ ] Generelle Sensitivitaetsanalyse fuer das Paper sauber planen und spaeter konsistent durchziehen:
  - Peak-Boiler-Fuel-Mix (`Gas/Oel`)
    - Baseline Gas-Peak-Boiler
    - Variante `2/3 Gas + 1/3 Heizoel extra leicht`
    - aktive Variante `1/2 Gas + 1/2 Heizoel extra leicht`
    - KPIs: Cost, CO2, Boiler-Energy, Boiler-Peak, shifted/rebound
  - ggf. Wetter-/Tageselektion
  - ggf. Thermflex-Settings (`upper_only`, Dauer, Bounds)
  - nur auf final bereinigtem Hauptpfad und nicht mit Zwischenstaenden vermischen
- [ ] Trade-off-Tage als eigenen Seitenanalyse-Strang dokumentieren:
  - systematisch Tage sammeln, auf denen sichtbares Shifting keine Savings bringt oder KPI-seitig kippt
  - dafuer mindestens `cost`, `CO2`, `district_gas_boiler_peak`, `rebound_over_shifted_pct` und Tageskontext (`T_outdoor`, Preise, Solar gains) gemeinsam lesen
  - Ziel: explizit zeigen, wann Thermflex im aktuellen System nicht hilft oder gegenlaeufig wirkt
- [ ] Beitrag der Solar Gains zur Thermflex-Einsparung explizit quantifizieren:
  - zunaechst als Analyse-KPI ueber den Heizperioden-Screen: Savings vs. `solargains_proxy_sum`
  - der erste Solar-Counterfactual-Plot wurde bewusst aus dem aktiven Figure-Layer nach `figures/old/` verschoben; die Story ist derzeit in Tabellenform klarer
  - spaeter nach finalem Heizperioden-Rerun erneut mit finalen Zahlen ziehen
  - danach ggf. als haerterer Counterfactual:
    - ausgewaehlte Tage mit unveraendertem Thermflex-Setting, aber kuenstlich deaktivierten oder reduzierten Solar Gains gegentesten
  - Ziel: trennen, welcher Teil der Savings aus Preis-/Dispatchlogik kommt und welcher Teil aus passivem Wiederaufheizen
- [ ] Outcome-Atlas nach finalem Heizperioden-Rerun aktualisieren:
  - `fig_07_flexibility_outcome_atlas.png` ist als Ergebnisstruktur angelegt und liest Table 09
  - nach finaler Korrektur der Modellpfade alle Table-09-Werte neu schreiben und Fig. 07 erneut rendern
  - bei Bedarf Duration-Dimension in eine Appendix-Variante auslagern, damit die Hauptfigur lesbar bleibt
- [ ] Innenraumtemperatur in den Thermflex-Paperfiguren expliziter zeigen:
  - mindestens fuer ausgewaehlte Top-Savings-/Trade-off-Tage eine Hintergrund- oder Nebenlinie fuer `T_in` pruefen
  - Ziel: sichtbar machen, wie nah die Gebaeude an der oberen/unteren Komfortgrenze fahren und wann thermischer Spielraum erschopft ist
- [ ] Archetypspezifische Thermflex-Darstellung fuer den Paper-/Appendixpfad vorbereiten:
  - explizit zeigen, welche Kohorten / Archetypen stark und welche schwach shiften
  - insbesondere pruefen und sichtbar machen, ob die aelteren Bestandskohorten im aktuellen Modell tatsaechlich weniger shiftbare Energie realisieren
  - moegliche Metriken:
    - shifted space heat je Kohorte
    - rebound je Kohorte
    - aktive Flexstunden je Kohorte
    - `T_in`-Naehe zu den Bounds je Kohorte
- [ ] Representative-day set nach dem vollen Heizperioden-Screen aktualisieren:
  - aktueller Screen-Bundle: `Optimization/run/results/Vienna/gold/daily_thermflex_screen_20260421_160246`
  - starke gemeinsame Cost-/CO2-Tage liegen aktuell eher bei `2023-11-04`, `2023-03-04`, `2023-03-18`, `2023-02-21`, `2023-03-16`, `2023-03-23`
  - prÃ¼fen, welche 4-6 Tage davon die beste Paper-Story tragen
  - `2023-04-24` als bisheriger April-Tag ist KPI-seitig schwach und sollte voraussichtlich ersetzt werden
- [ ] Nach der Waste-/External-Heat-Korrektur alle aktiven Thermflex-Paperzahlen neu screenen:
  - aktiver 2023-Fixed-System-Pfad hat jetzt `district_waste_incineration = true`
  - Waste und External Heat sind je `160 MW_th` bei `thermal_availability = 1.0`
  - alte Table-09-/Heizperioden-KPIs sind dadurch nicht mehr final interpretierbar
  - zuerst Tages-/Wochen-Smokes plausibilisieren, danach vollen Heizperioden-Screen neu laufen lassen
  - beachten: die aktiven Override-Dateien unter `Optimization/validation/` sind aktuell git-ignored; fuer einen reproduzierbaren Paperpfad spaeter als getrackte Paper-Settings oder Generator-SSOT materialisieren
- [x] Wiener fossilen Peak-Boiler nach der neuen `1/2 Gas + 1/2 Heizoel extra leicht` Economics-SSOT gegen ausgewaehlte Fig.-12-Wochen screenen:
  - Output: `Documentation/Papers/thermflex_paper/figures/fig_12_peak_boiler_mix50_screen.csv`
  - geprueft ohne Fig.-12-Render:
    - `good_dec`, `good_jan`, `good_feb`, `good_mar`, `march_savings`
  - Befund:
    - `march_savings`: Peak boiler `0.601 -> 0.412 GWh` (`-31.4 %`), Peak `138.2 -> 132.5 MW`, Cost `-0.285 %`, CO2 `-0.244 %`
    - `good_feb`: Peak boiler `0.346 -> 0.303 GWh` (`-12.5 %`), Cost `-0.243 %`, CO2 `-0.271 %`
    - `good_mar`: kleiner absoluter Boiler, aber alle Ziel-KPIs sinken
    - `good_jan`: grosser Boiler, aber Flex-Reduktion bleibt praktisch null
    - `good_dec`: Boiler sinkt um ca. `5 %`, aber heat-allocated CO2 steigt leicht (`+0.112 %`) wegen mehr Gas-CHP-Waerme
- [ ] Gas-CHP methodisch sauberer schneiden:
  - aktueller Pfad ist noch ein fixes `eta_el` / `eta_th`-Modell
  - fÃ¼r die Wien-/Thermflex-Story spÃ¤ter prÃ¼fen, ob ein variables Extraktions-/Kondensations-Kennfeld gebraucht wird
  - das nur mit belastbarer Literatur-/Katalogbasis umstellen, nicht heuristisch
  - Status `2026-04-29`:
    - Recherche bestaetigt, dass die installierte Wiener KWK-/DH-Waermekapazitaet viel hoeher ist als der bisherige `~368 MW_th` Paperproxy
    - plausible Groessenordnung:
      - Simmering 1 `450-500 MW_th`
      - Simmering 2 `150 MW_th`
      - Simmering 3 `350-450 MW_th`
      - Donaustadt `350 MW_th`
      - Leopoldau historisch `~170 MW_th`
      - damit grob `1,4-1,6 GW_th` Gas-/KWK-Waermekapazitaet vor Biomasse/Abwaerme/Waste
    - reines Hochsetzen im Fixed-Ratio-Pfad ist aber nicht paperfaehig:
      - mit `eta_el=0.40`, `eta_th=0.45`, `installed_kw_el=1.44 GW` wird CHP thermisch plausibler gross
      - der Dispatch ueberproduziert dann in milderen Winterwochen Waerme, weil Strom-/Waerme-Kopplung und Grid-Import-Objective die CHP zu stark treiben
    - sauberer naechster Schritt:
      - Gas-CHP-Kapazitaet und Betriebsmodus trennen
      - heat-led / power-led piecewise Pfad reaktivieren oder eine explizite heat-only dispatch allocation fuer den DH-Paperpfad definieren
      - `grid_import_cost` darf fuer den DH-Waerme-Dispatch nicht der versteckte CHP-Treiber sein
- [ ] DH-Waerme-Cost-KPI in allen ThermFlex-Paper-Auswertungen konsequent umstellen:
  - fuer die Paper-Story `dispatch_heat_operating_cost_eur = fuel_cost_eur + co2_cost_eur + variable_opex_eur` verwenden
  - `dispatch_operating_cost_eur` nur noch als legacy/globales System-KPI interpretieren, weil darin `grid_import_cost_eur` enthalten ist
  - Table 09, Screening-Rankings, Pareto-/Surrogat-Ziele und Figure-KPI-Boxen nach der finalen Modellpfad-Festlegung auf das Waerme-KPI umstellen
  - CHP-Stromwert separat als Sensitivitaet / Sektorkopplungsfall fuehren, nicht im Haupt-Cost-KPI verstecken
- [ ] Fig. 12 Wochen selektiv auf aktive Heat-Cost-Version nachziehen:
  - nicht pauschal alle Wochen neu rendern
  - vor dem naechsten Vollwochenrender zuerst einen kleinen Smoke mit der neuen Gas-CHP-Heat-Allocation-Objective fahren
  - aktive Testkomponenten: `heat_allocated_fuel_cost`, `heat_allocated_co2_cost`, `variable_opex`
  - 24h/48h/96h-`good_feb`-Piecewise-Smokes laufen technisch durch und nutzen `heat_led`
  - Haupt-CO2 fuer Fig. 12 ist jetzt `dispatch_heat_allocated_co2_t`; physische Gesamt-CO2 bleiben Diagnose/Sensitivitaet
  - 96h plus 24h-Warm-up `good_feb` zeigt in der Waerme-Systemgrenze: Heat-Cost und heat-allocated CO2 sinken, Peak-Boiler ist praktisch 0
  - `good_feb` wurde final mit 24h Warm-up und piecewise Gas-CHP gerendert:
    - Datei: `Documentation/Papers/thermflex_paper/figures/fig_12_good_week_february_dispatch_shift.png`
    - CSV: `Documentation/Papers/thermflex_paper/figures/fig_12_good_week_february_dispatch_shift.csv`
    - Heat operating cost `-0.345 %`, waermeallokierte CO2 `-0.399 %`, Peak boiler `0.0 %`
  - `good_jan` wurde final mit 24h Warm-up und piecewise Gas-CHP gerendert:
    - Datei: `Documentation/Papers/thermflex_paper/figures/fig_12_good_week_january_dispatch_shift.png`
    - CSV: `Documentation/Papers/thermflex_paper/figures/fig_12_good_week_january_dispatch_shift.csv`
    - Heat operating cost `-0.032 %`, waermeallokierte CO2 `-0.036 %`, Peak boiler energy `-0.361 %`
  - `good_jan` wurde danach mit Peak-Boiler-OPEX-Addierer `+0.006 EUR/kWh_th` neu gerechnet:
    - Heat operating cost `-0.034 %`, waermeallokierte CO2 `-0.036 %`, Peak boiler energy `-0.353 %`
    - Befund: der Aufschlag macht den Boiler formal teurer, loest aber die Talnutzung am `2023-01-18 12-21` und `2023-01-20 12-18` nicht robust aus
    - naechster Check: Gebaeude-/Event-Bounds und thermischer Zustand in diesen Talfenstern statt weitere Boiler-Kostenaufschlaege
  - `good_jan` wurde zusaetzlich mit Gas-CHP-`eta_total=0.75` gerechnet:
    - maximale Gas-CHP-Waerme sinkt auf ca. `1178 MW_th`
    - Heat operating cost `-0.032 %`, waermeallokierte CO2 `-0.033 %`, Peak boiler energy `-0.131 %`
    - Befund: die Kapazitaetsreduktion macht die betrachteten Taeler nicht besser; dort laeuft nun teilweise bereits Peak-Boiler
    - vor Uebernahme in den Hauptpfad klaeren, ob `eta_total=0.75` methodisch zur Anlagenkalibrierung passt oder die Fig.-12-Mechanik eher verschlechtert
  - `good_jan` wurde danach mit Gas-CHP-`eta_total=0.80` gerechnet:
    - maximale Gas-CHP-Waerme sinkt gegenueber `0.85` moderat auf ca. `1309 MW_th`
    - Heat operating cost `-0.033 %`, waermeallokierte CO2 `-0.034 %`, Peak boiler energy `-0.188 %`
    - Befund: Peak-Boiler laeuft im Januar deutlich (`50.098 -> 50.004 GWh`, Peak ca. `666 MW`), die genannten Taeler bleiben aber Ref/Flex praktisch identisch
    - wichtiger Logikcheck: Strompreisphasen treiben im aktiven Fig.-12-Hauptpfad keinen `power_led`-Mode, weil `power_priority_mode = "free"` und kein Stromwert/Gridpreis in der Objective ist
  - `good_mar` wurde mit dem aktuellen Gas-CHP-`eta_total=0.80`-Pfad neu gerechnet:
    - Heat operating cost `-0.080 %`, waermeallokierte CO2 `-0.144 %`, Peak boiler energy `-4.917 %`
    - Peak-Boiler ist absolut fast null (`0.031 -> 0.029 GWh`), daher als Mechanikplot nur begrenzt aussagekraeftig fuer Boiler-Vermeidung
  - Jan/Feb/Maerz-Kandidatensuche:
    - `good_feb` wurde auf eta80 nachgezogen: Peak boiler `0.346 -> 0.310 GWh`, Heat operating cost `-0.238 %`, CO2 `-0.266 %`
    - `march_savings` wurde auf eta80 nachgezogen: Peak boiler `0.601 -> 0.453 GWh`, Heat operating cost `-0.233 %`, CO2 `-0.243 %`
    - Diagnosewoche `2023-03-05` zeigt relativ die beste Boiler-Reduktion (`0.177 -> 0.050 GWh`, ca. `-71.9 %`), aber absolut sehr kleinen Boiler-Einsatz
    - ein perfekter Fall "relevanter Ref-Boiler, Flex-Boiler = 0" wurde in den geprueften Wochenstarts nicht gefunden
    - Auswahlentscheidung offen:
      - `good_jan`: starke Boiler-Relevanz, aber kaum relative Reduktion
      - `march_savings`/`2023-03-05`: bessere relative Edge-Story, aber kleiner absoluter Boiler
  - Ankercheck:
    - Peak-Boiler `1450 MW_th` passt zum dokumentierten `~1.45-1.50 GW_th`-Anker
    - Waste und External Heat mit je `160 MW_th` und `7500 h/a` treffen die `~1200 GWh/a`-Anker
    - Gas-CHP eta80 ergibt ca. `1309 MW_th` und liegt unter dem dokumentierten `~1.4-1.6 GW_th`-Waermeleistungsanker
  - aktuelle eta80-Suche Anfang Dezember bis Ende Maerz ohne alten Daily-Screen:
    - alter Daily-Screen nicht als Evidenz verwenden; er ist wegen altem Dispatch-/Gas-CHP-Stand nicht vergleichbar
    - `2023-12-01`: Peak boiler `29.933 -> 29.933 GWh`
    - `2023-12-08`: Peak boiler `19.771 -> 19.771 GWh`
    - `2023-01-22`: Peak boiler `40.080 -> 40.080 GWh`
    - `2023-02-05`: Peak boiler `11.639 -> 11.639 GWh`
    - weiterer eta80-Screen liegt in `Documentation/Papers/thermflex_paper/figures/fig_12_eta80_week_candidate_screen.csv`
    - geprueft wurden zusaetzlich `2023-12-15`, `2023-12-22`, `2023-01-29`, `2023-02-12`, `2023-02-26`, `2023-03-05`
    - kein Fall mit relevanter Ref-Boiler-Energie und Flex-Boiler nahe null gefunden
    - beste relative Reduktion: `2023-03-05` mit `0.177 -> 0.050 GWh`, aber absolut sehr klein
    - Befund: relevante Boiler-Wochen existieren, aber Upper-only reduziert den Boiler im aktuellen eta80-Hauptpfad dort praktisch nicht
  - Demand-Anker nicht zu klein: aktiver `district_heating.share = 0.35`, letzter Full-year-Check `6.138 TWh/a` gegen offiziellen Fernwaermeabsatz `5.427 TWh/a`
  - Tau-/Nachfragesensitivitaet vom 2026-05-05:
    - `district_heating.share = 0.40` erzeugt mehr Boiler, aber keine deutlich bessere Boiler-Reduktion
    - `tau_h = 2` zeigt mehr Boiler-Reduktion, aber nicht sauber durch Gas-CHP-Vorheizen, weil die Gas-CHP-Wochensumme im besten Sensitivitaetsfall sinkt
    - fuer den Paperplot daher nicht methodisch auf hoeheren Demand oder kleineres tau umstellen, solange dies nicht separat begruendet wird
  - Boiler-OPEX-/Peak-Boiler-Energy-Sensitivitaet vom 2026-05-05:
    - `+20 EUR/MWh_th` und `+50 EUR/MWh_th` reduzieren die Boiler-Energie im `march_savings`-Fall, entfernen die Spitzen aber nicht vollstaendig
    - effektiver ThermFlex-Speicher laut Diagnostics ca. `3.2 GWh`, Ref-Boiler-Wochenenergie nur ca. `0.60 GWh`
    - naechster Diagnosepunkt: Timing/State pruefen, besonders ob die fruehen Morgenpeaks wegen Rolling-Horizon-/Bus-Inertia-/Event-Zuschnitt nicht rechtzeitig genug vorgeheizt werden
    - dafuer am besten einen kompakten hourly ThermFlex-State-Export fuer Fig. 12 ergaenzen oder aktivieren: `T_in`, Upper-Headroom, Preheat-/Cutback-Delta, Active-Member-Stunden je Stunde
  - Hourly ThermFlex-State-Diagnostic ist jetzt vorhanden:
    - `build_fig_12_thermflex_state_diagnostic.py`
    - `fig_12_march_savings_thermflex_state_diagnostic.csv/png`
    - Befund: erster grosser Morgenpeak `2023-03-02 03:00-07:00` wird nicht vorgeheizt; alle Member bleiben bei `22.5 C` und Flex-Aktivitaet ist null
    - spaeterer Peak `2023-03-05 05:00-08:00` wird dagegen nach echtem Vortags-Preheat deutlich reduziert
    - naechster konkreter Check: Rolling-Block-/Boundary-Diagnose, ob der `2023-03-02`-Peak im Vortagsblock anders gesehen wird als im committed/stitchten Block oder ob ThermFlex-Zustaende/Bus-Inertia am Blockwechsel effektiv zurueckgesetzt werden
  - potenzielle Mechanismusplots fuer "Gas-CHP preheat -> spaetere Boiler-Reduktion":
    - `fig_12_march_weekly_dispatch_shift.csv`: Gas-CHP-Vorheizstunden am 2023-03-02/03, spaetere Boiler-Reduktion; im Zeitraum Anfang Dezember bis Ende Maerz
    - `fig_12_good_week_november_dispatch_shift.csv`: staerkere Gas-CHP-Vorheizsignatur und Boiler-Reduktion, aber ausserhalb des zuletzt gesuchten Dec-Mar-Fensters
  - Boundary-Probe fuer den ersten `march_savings`-Peak:
    - einzelner 36h-Block zeigt keinen harten Rolling-State-Reset
    - mit extremem Boiler-OPEX-Addierer `+500 EUR/MWh_th` wird der Peak voll vorgeheizt und der Boiler im Peakfenster auf `0` gedrueckt
    - offener methodischer Entscheid: nur realistisch kalibrierten Boiler-Kosten-/CO2-Schnitt im Hauptpfad verwenden oder eine explizite Peak-Boiler-Avoidance-Sensitivitaet als Diagnose-/Mechanismusplot fuehren
- [ ] Fig. 06b Cohort-Duration-Figure fertig rendern:
  - neuer Builder ist angelegt: `Documentation/Papers/thermflex_paper/figures/build_fig_06b_cohort_duration_upper_lower.py`
  - Ziel: tau 4, drei Fig.-15-Perioden, `upper-only` vs. `upper+lower 1K`, Duration-Balken `1/4/8/12/24 h`
  - aktueller Blocker: `upper+lower 1K` mit Duration-Budget ist im MILP sehr langsam; erster lower-Case schreibt nach 60 Minuten keinen Cache
  - vor weiterem Full-Render gezielt pruefen:
    - ob lower-relaxation mit hartem `max_flex_duration_h` methodisch fuer diese Mechanismusfigur noetig ist
    - ob eine kleinere Diagnoseperiode oder ein gezielter lower-duration Smoke-Test reicht
    - ob solverseitig Time-Limit/MIP-Gap/Presolve-Optionen fuer diese reine Mechanismusfigure vertretbar sind
    - ob lower-row alternativ als fixed `24 h` lower-relaxation erzaehlt und die Duration-Dimension nur fuer upper-only gezeigt wird

  - Peak-Boiler-Mix-Fix ist umgesetzt:
    - `district_gas_boiler_day_ahead_price_eur_per_mwh_fuel` wird nun aus der Wiener Boiler-Economics-SSOT an den MILP uebergeben
    - `milp_day_ahead.py` und `milp_two_stage.py` nutzen fuer Peak-Boiler-Fuel-Cost nicht mehr die Gas-CHP-Gaspreisreihe
    - naechster Check: `march_savings` und ggf. `good_feb`/`good_mar` selektiv neu rendern und pruefen, ob Boiler-Energie/Peak jetzt ohne freie Lambda-Objective staerker fallen
  - vor weiteren Wochen nur selektiv per `--variant <slug>` rendern; nicht alle Varianten pauschal starten
  - zuerst gezielt entscheiden, ob nur die `good_*` Wochen oder auch `november_savings`/`march_savings` aktualisiert werden sollen
  - neuer robuster Pfad: `build_fig_12_weekly_dispatch_shift.py --variant <slug>` nutzt validierte Ref/Flex-Seriencaches je Variante und Case
  - bei November zuerst einzeln mit langem Timeout versuchen; bei erneutem Haenger waere Rolling-Block-Caching im Dispatchpfad der naechste, groessere Eingriff
- [ ] Fig.-06b Duration-Plot vor Full-Render bewusst freigeben:
  - erledigter pragmatischer Plotpfad: Fig.-06b nutzt jetzt nur noch `upper-only` mit `1, 4, 8, 12 h`
  - `upper+lower 1K` bleibt in Fig. 15 und wird nicht mehr als Duration-Sweep in Fig.-06b gezeigt
  - offener methodischer Technikpunkt bleibt fuer spaeter: Rolling-Block-Caching/Resume waere noetig, falls upper+lower-Duration-Sweeps wieder aufgenommen werden
- [ ] Paperfigur-Idee weiterverfolgen:
  - Tages-Shiftplot mit zusätzlicher Hintergrundlinie für den thermischen Freiheitsgrad / die noch variable Energie
  - diese Linie soll über den Innenzustand bzw. die Nähe zur oberen Temperaturgrenze erzählen, damit sichtbar wird, wann weiteres Vorheizen überhaupt noch möglich ist
- [ ] Ergebnis-Scatter fuer ThermFlex-Paper pruefen:
  - Arbeitsidee: `Flexibility performance map` als Scatterplot fuer Ergebnisdarstellung statt weiterer Tabelle.
  - Achsen:
    - x: Kosteneinsparung [%] (`-cost_delta_pct`)
    - y: CO2-Einsparung [%] (`-co2_delta_pct`)
  - Punktgroesse:
    - Peak-boiler-Reduktion, z. B. absolute MWh oder Prozentreduktion.
  - Kodierung:
    - Farbe nach Zeitraum/Saison (`December`, `February/March`, `April`)
    - Markerform nach Falltyp (`upper-only`, `upper+lower 1K`, ggf. Tau-Sensitivitaet)
  - Layoutidee:
    - Quadranten bei 0% Kosten- und 0% CO2-Einsparung.
    - oben rechts = no-regret / lower cost + lower CO2.
    - Trade-off-Quadranten dezent hinterlegen.
    - Nur ausgewaehlte Punkte labeln, keine Trendlinie.
  - Workflow:
    - zunaechst explorativ ggf. mit Plotly/Altair pruefen.
    - finale Paper-Figure besser in Matplotlib/Seaborn fuer kontrollierten statischen Export.
  - Konzeptbild liegt aktuell rein schematisch unter:
    - `Documentation/Papers/thermflex_paper/figures/fig_scatter_concept_flexibility_performance_map.png`
  - erster datenbasierter Fig.-16-Builder ist angelegt:
    - `Documentation/Papers/thermflex_paper/figures/build_fig_16_flexibility_performance_map.py`
    - Output: `fig_16_flexibility_performance_map.png/.csv`
  - naechste Layout-/Datenentscheidung:
    - Punktgroesse aktuell = prozentuale Peak-Boiler-Energie-Reduktion
    - fuer Paper ggf. besser absolute Peak-Boiler-Reduktion in MWh/GWh verwenden, damit kleine Ausgangswerte nicht uebergewichtet werden
    - nach stabilem Layout optional weitere Monate/Wochen per neuen MILP-Laeufen ergaenzen
- [ ] Gas-CHP-V1 nach dem ersten piecewise Smoke-Test inhaltlich weiterziehen:
  - technischer Smoke-Test auf `2023-03-04` läuft, aber der Dispatch wählt aktuell in allen 24 Stunden nur `power_led`
  - deshalb ist `piecewise_power_heat_v1` auf diesem Tag noch identisch zum bisherigen `fixed_ratio`-Pfad
  - nächster Check:
    - weitere Top-Savings- und Trade-off-Tage gegenprüfen
    - prüfen, ob niedrigere Strompreise / höherer DH-Druck / andere Boiler-Economics wärmelastigere CHP-Modi auslösen
    - erst danach entscheiden, ob die Betriebsregion schärfer oder die Markt-/Anlagenlogik weiter angepasst werden muss
- [ ] Gas-CHP-V1 vorerst nicht in den aktiven Paperpfad übernehmen:
  - auch nach explizitem `price_spike_gated_v1`-Test und Objective-Schnitt ohne `grid_export_revenue` zeigt der neue CHP-Pfad auf `2023-03-04` keinen sinnvollen Zusatznutzen
  - aktiver Paper-/Figure-Pfad bleibt daher bis auf Weiteres beim bisherigen `fixed_ratio`
  - nur wieder aufgreifen, wenn spätere Tests auf anderen Top-Savings-/Trade-off-Tagen eine klare Verbesserung zeigen
- [ ] Spaeteren Lern-/Beschleunigungspfad fuer die Gebaeudeseite gezielt pruefen:
  - Zielbild waere stark: moeglichst viel der `EnergyPlus`-Teacher-Physik beibehalten, aber den Online-/Dispatchpfad mit einem lernbasierten Archetyp-Response-Modell beschleunigen
  - dabei die Rollen sauber getrennt halten:
    - Reduced-Order-Modell = zustandsfaehiges Runtime-Gebaeudemodell fuer `T_in`, Preheat, Rebound und Komfortgrenzen
    - aktuelles Surrogat = KPI-/Search-Beschleuniger fuer System-/Dispatch-Ergebnisse
  - spaeter explizit pruefen:
    - ob ein archetypspezifischer learned response layer aus `EnergyPlus` den aktuellen Reduced-Order-Fit sinnvoll ergaenzen oder ersetzen kann
    - ob Grey-box- oder andere learned building-response Varianten fuer die wenigen Archetypen stabil genug sind
    - ob Holdout-/Generalization-Qualitaet gegenueber dem heutigen Surrogatpfad wirklich besser wird
  - explizit nicht als End-to-End-Blackbox fuer alles aufziehen, solange Mehrstundendynamik, Rebound und Komfortgrenzen nicht sauber validiert sind
- [ ] Surrogat-Holdout-Qualitaet spaeter gezielt verbessern:
  - die aktuellen Holdout-Metriken sind fuer einige paper-relevante Targets noch zu schwach, vor allem bei Kosten- und Shift-KPIs
  - explizit pruefen:
    - mehr / besserer feasible Trainingsraum
    - klarerer KPI-/Target-Schnitt
    - robustere Features fuer Thermflex- und Wetter-/Solar-Zustaende
    - ob ein building-response-naher Lernpfad besser generalisiert als der aktuelle KPI-Surrogatpfad
- [ ] Uncertainty-aware Surrogatpfad als naechsten AI-Hebel pruefen und moeglichst bald umsetzen:
  - Surrogat soll nicht nur Punktvorhersagen liefern, sondern auch Unsicherheit / Vertrauensmass
  - diese Unsicherheit soll explizit fuer Truth-Fallbacks genutzt werden:
    - unsichere Punkte an `Gold` / `Teacher` zurueckgeben
    - sichere Punkte im schnellen Pfad belassen
  - moegliche erste Varianten:
    - Ensembles / quantile-basierte Modelle
    - Bayesian NN / SVGP
    - spaeter ggf. conformal prediction fuer kalibrierte Intervalle
- [ ] Active-Learning-Schleife fuer den Thermflex-Surrogatpfad aufsetzen:
  - neue Teacher-/Gold-Laeufe nicht breit zufaellig, sondern gezielt dort nachziehen, wo das Modell heute schwach ist
  - Prioritaetsregime:
    - kalte Hochlasttage
    - starke Solar-/Shoulder-Tage
    - hohe Rebound-Tage
    - KPI-Trade-off-Tage
    - Punkte nahe Komfort- und Flex-Bounds
  - Ziel:
    - bessere Holdout-Metriken pro zusätzlichem Truth-Budget
    - robustere Pareto-/Optimierungsregionen
- [ ] Learned building-response surrogate als moeglicher Nachfolger des heutigen Reduced-Order-Modells schneiden:
  - direkt aus `EnergyPlus`-Teacher-Daten trainieren
  - stateful / sequenziell, nicht nur KPI-Regression
  - Kernoutputs:
    - `T_in`
    - `q_heat`
    - Rebound
    - Komfortgrenznaehe / thermischer Spielraum
    - mehrstuendige Shift-/Release-Dynamik
  - moegliche Modellklassen:
    - neural state-space
    - structured recurrent / physics-guided models
    - hybrid grey-box + ML corrector
- [ ] Hybrid-/Residual-Lernpfad explizit mitpruefen:
  - physikalischen Kern nicht sofort komplett verwerfen
  - stattdessen pruefen, ob ein ML-Corrector auf Residuen / Modellfehlern den saubersten ersten Schritt liefert
  - das ist besonders attraktiv, wenn full learned building dynamics noch nicht stabil genug fuer lange Horizonte sind
- [ ] Transfer-Learning-Pfad fuer Archetypen, Wetterjahre und spaetere Szenariowelten vorbereiten:
  - nicht fuer jeden neuen Archetyp / jedes Jahr ein vollstaendig neues Surrogat bei null trainieren
  - stattdessen Vortraining auf breiter `EnergyPlus`-Teacher-Basis und gezieltes Fine-Tuning mit kleinen Zusatzdatensaetzen
  - besonders relevant fuer spaetere Generalisierung ueber mehr Wetterjahre, Settings und Systemvarianten
- Learning / Surrogates:
  - zentralen Artefakt-Katalog aktiv weiter nutzen:
    - `Learning/datasets/artifact_inventory.json`
    - `Learning/datasets/artifact_inventory.csv`
    - `Learning/datasets/artifact_inventory_summary.json`
  - naechster Reuse-Schritt:
    - `thermflex_daily_results_v1` weiter nur aus `daily_thermflex_screen_*` speisen
    - alte ThermFlex/System-`truth_dataset.csv` als separaten Family-Pfad `thermflex_system_results_v1` schneiden, nicht mit Tages-Screens mischen
  - Building-Surrogat:
    - `160` katalogisierte `teacher_hourly.csv`-Teacher-Runs als zentrale Trainingsbasis pruefen / kuratieren
  - ThermFlex-Daily-Results:
    - die `9` eindeutigen Day-Screen-Bundles gezielt erweitern:
      - mehr volle Bundles fuer `dur8`, `dur12`, `2K`, spaeter `tau`
    - robuste erste Zielmenge priorisieren:
      - Kosten
      - CO2
      - Peak-Boiler
    - aktueller robuster Zielzuschnitt `robust_kpi` ist eingefuehrt; naechste Schwerpunkte:
      - Kostenziel nach `signed_log1p`-Hebel weiter beobachten / ggf. weitere cost-spezifische Features pruefen
      - `robust_kpi_absolute` wurde als expliziter Testpfad eingefuehrt, war aber schwacher als `robust_kpi`; deshalb Prozent-vs.-Absolutdelta vorerst nicht als Haupthebel weiterverfolgen
      - stattdessen als naechstes pruefen:
        - reichere Tages-Kontextfeatures
        - mehr volle Bundles fuer weitere Duration-/Lower-/Tau-Kombinationen
      - Shift/Rebound spaeter separat oder mit engerem Modellzuschnitt behandeln
      - current-only-Test ist bereits gelaufen und war nicht besser als der gemischte Stand
      - neuer ausfuehrbarer Table-09-Surrogatpfad steht jetzt:
        - `Learning/thermflex_daily_results/predict.py`
        - `Learning/thermflex_daily_results/aggregate.py`
        - `Documentation/Papers/thermflex_paper/tables/build_table_09_heating_season_kpis_surrogate.py`
      - Daily-Profil `table_09_paper` ist trainiert, aber noch nicht paper-ready:
        - `Learning/models/thermflex_daily_results_xgb_table_09_paper_5896cea66bba/`
        - grouped-holdout `mean R2 = -0.048`
      - aktueller Engpass fuer surrogate Table 09:
        - `thermflex_shifted_space_heat_kwh`
        - `thermflex_rebound_kwh`
        - Boiler-Energie ist nach engineered Features + partial bundles deutlich besser (`R2 ~ 0.60`), aber noch nicht auf Paper-Niveau
      - naechster Daily-Hebel:
        - shift/rebound nicht mehr nur als generischen KPI-Block behandeln
        - explizit reichere Features / separaten Modellzuschnitt fuer diese beiden Tagesziele pruefen
        - gezielt mehr Truth fuer `dur4/dur8/evt24`-Lower-Relax und weitere shift-starke Tage sammeln, statt nur weitere Boiler-/Cost-Tage
        - `LOWER1K_DUR8_EVT24` ist jetzt als expliziter Resume-Fall vorbereitet, aber:
          - `1%` HiGHS-Gap loest den ersten schweren fehlenden Tag (`2023-03-25`) noch nicht innerhalb `600 s`
          - auf `2023-03-24` verschiebt `1%` Gap die paperkritischen KPI-Groessen (Boiler, shifted, rebound) schon deutlich
        - deshalb vorerst:
          - keinen stillen lockeren Gap-Vertrag fuer Daily-Truth einfuehren
          - stattdessen fehlende Truth eher ueber weitere tractable Lower-Relax-Faelle / andere Tage sammeln oder schwerere Faelle gezielt separat behandeln
        - Partial-Truth ist jetzt explizit operationalisiert:
          - Daily-Screen-Runs koennen mit `--allow-incomplete-days` und `--day-solver-time-limit-s` weiterlaufen
          - bekannte Heavy-Day-Luecken muessen bei Resumes nicht erneut geloest werden
          - naechster Nutzungsschritt:
            - `LOWER1K_DUR8_EVT24` weiter durch die Heizperiode ziehen
            - `LOWER1K_DUR12_EVT24` vorerst nicht priorisieren; erster Partial-Test war teuer und fuer den Daily-`Table 09`-Pfad nicht hilfreich
            - statt `dur12` als naechste Breite eher `2K`-Faelle priorisieren
        - bei kuratierten Daily-Datensaetzen `Optimization/run/results/.../gold` als erste `source_root` vor Snapshot-Caches verwenden, damit live Failure-Manifeste und neuere Partial-Bundles nicht von aelteren Snapshot-Dubletten ueberdeckt werden
        - aktueller brauchbarer gold-first Daily-Table-09-Stand:
          - neuer aktueller Best-Stand:
            - Datensatz:
              - `Learning/datasets/f77eafde5cdc366ee47282e6755eaac41fec0f8da18321c709a6f4a094828e98/`
            - Modell:
              - `Learning/models/thermflex_daily_results_xgb_table_09_paper_f77eafde5cdc/`
            - grouped-holdout `mean R2 ~ 0.334`
            - `dispatch_operating_cost_pct_change ~ 0.595`
            - `co2_emissions_total_pct_change ~ 0.228`
            - `district_gas_boiler_peak_kw_delta ~ -0.063`
            - `district_gas_boiler_generation_kwh_delta ~ 0.241`
            - `thermflex_shifted_space_heat_kwh ~ 0.525`
            - `thermflex_rebound_kwh ~ 0.475`
          - wichtig:
            - der bisherige Negativbereich bei `shifted` / `rebound` ist verlassen
            - Boiler-Peak und Boiler-Energie bleiben noch schwach
            - fuer die Daily-KPIs sind wir weiter deutlich unter `R2 >= 0.95`
        - `dur12`-Partial-Test hat einen schwaecheren neuen Daily-Stand erzeugt:
          - Datensatz:
            - `Learning/datasets/9fb347f1b280ed6d3fded1ac7257e1f35989d68222b9f15c9a97261ffa85bc8e/`
          - Modell:
            - `Learning/models/thermflex_daily_results_xgb_table_09_paper_9fb347f1b280/`
          - grouped-holdout `mean R2 ~ -0.21`
          - diesen Stand nicht als bevorzugte Baseline verwenden
        - naechster Daily-Hebel:
          - `LOWER2K_DUR4_EVT24` weiter auffuellen; das ist aktuell die tractable Truth-Familie mit dem besten Signal fuer `shifted` / `rebound`
          - danach `LOWER2K_DUR8_EVT24` nur als Traktabilitaetsprobe antesten, nicht blind voll rechnen
          - fuer Boiler-Peak/-Energie separaten Target-Sweep pruefen, da der aktuelle `shifted/rebound`-Tuningstand diese Ziele nicht mitzieht
        - bereits erledigt / aktueller Stand:
          - `LOWER2K_DUR4_EVT24` ist bis in den Februar hinein gewachsen und bleibt tractable
          - `LOWER2K_DUR8_EVT24` 3-Tages-Probe ist loesbar, aber deutlich teurer
          - target-spezifischer Sweep fuer:
            - `thermflex_shifted_space_heat_kwh`
            - `thermflex_rebound_kwh`
            - `district_gas_boiler_peak_kw_delta`
            - `district_gas_boiler_generation_kwh_delta`
            - `co2_emissions_total_pct_change`
            ist im Daily-Trainingspfad eingezogen
        - aktueller bevorzugter Daily-Stand bleibt:
          - Datensatz:
            - `Learning/datasets/f77eafde5cdc366ee47282e6755eaac41fec0f8da18321c709a6f4a094828e98/`
          - Modell:
            - `Learning/models/thermflex_daily_results_xgb_table_09_paper_f77eafde5cdc/`
          - grouped-holdout:
            - `dispatch_operating_cost_pct_change ~ 0.595`
            - `co2_emissions_total_pct_change ~ 0.432` (best target-specific sweep result on the tuned daily path)
            - `district_gas_boiler_peak_kw_delta ~ 0.033`
            - `district_gas_boiler_generation_kwh_delta ~ 0.417`
            - `thermflex_shifted_space_heat_kwh ~ 0.525`
            - `thermflex_rebound_kwh ~ 0.475`
          - Gesamtziel `R2 >= 0.95` fuer Daily ist weiterhin weit entfernt; System-/globaler KPI-Pfad bleibt der starke Surrogatpfad
  - ThermFlex-System-/MILP-Run-Surrogat:
    - separaten Family-Pfad `thermflex_system_results_v1` weiter ausbauen
    - Quelle: die `106` katalogisierten alten ThermFlex/System-`truth_dataset.csv`-Runs
    - nicht mit `thermflex_daily_results_v1` mischen
    - erstes Ziel:
      - allgemeine MILP-/System-Run-KPIs und Designpunkte als separater Surrogatpfad
      - spaeter fuer breite Sensitivitaeten und Kandidatenscreening nutzen
    - aktueller robuster Zielzuschnitt `robust_heat_system` ist eingefuehrt; naechste Schwerpunkte:
      - Boiler-Outputs sind nach den neuen Run-Slug-Kontextfeatures stark verbessert; Fokus jetzt auf weitere Stabilisierung / Generalisierung
      - CHP- und Storage-Ziele sind nach target-spezifischem Tuning ebenfalls klar verbessert; aktueller Stand im robusten Profil:
        - Gas-CHP `R2 ~ 0.80`
        - Storage `R2 ~ 0.68-0.69`
        - Boiler `R2 ~ 0.97`
        - Cost `R2 ~ 0.47`
      - Kostenziel nach `log1p` + Kontextfeatures + costspezifischem XGB-Tuning weiter beobachten; bleibt innerhalb des robusten Profils der schwaechste KPI
      - als naechstes gezielt pruefen:
        - ob getrennte KPI-Profile fuer Cost-only / Heat-System-Flows sinnvoller sind als ein gemeinsames robustes Profil
        - wie der System-Truthvertrag um explizite CO2-Ziele erweitert werden kann; derzeit gibt es im `thermflex_system_results_v1`-Truth noch kein CO2-Target
        - weitere anchor-day Markt-/Wetterfeatures wurden bereits getestet, waren aber auf dem grouped holdout nicht besser als der einfachere Run-Slug-Kontextpfad
      - paper-day-ahead-only-Test ist bereits gelaufen und war nicht besser als der nicht-smoke Gesamtstand
      - KPI-angereicherte Family aus `truth_dataset.csv + dispatch_kpis.json` ist jetzt aufgebaut:
        - Datensatz:
          - `Learning/datasets/612be5461a303ff3cbfd0fd044e124fe36662098497280403e3246ca7ddc5aab/`
        - aktueller bevorzugter paper-KPI-Zuschnitt:
          - Modell:
            - `Learning/models/thermflex_system_results_xgb_dispatch_kpi_paper_612be5461a30/`
          - grouped-holdout `mean R2 = 0.980`
        - Grund fuer den neuen paper-Zuschnitt:
          - `dispatch_heat_operating_cost_eur` ist fuer die Waermekostenstory sauber und stark lernbar
          - der alte `dispatch_operating_cost_eur` bleibt als grid-tainted Aggregat schwach und soll nicht mehr als primaerer Paper-KPI behandelt werden
        - naechste Schwerpunkte auf diesem Pfad:
          - pruefen, welche weiteren Paper-/Sensitivity-KPIs noch in den paper-Zuschnitt gehoeren
          - optional separaten Auxiliary-/Carbon-Split-Pfad fuer `district_gas_chp_co2_t` schneiden, falls dieser Split spaeter explizit gebraucht wird
          - spaeter Smoke-/weitere Runfamilien nur kontrolliert an den KPI-Vertrag andocken, nicht still mischen
          - diesen starken System-KPI-Pfad jetzt fuer saisonale Sensitivitaets- und Ranking-Auswertungen nutzen, auch wenn der Daily-Table-09-Pfad noch nachgeschaerft werden muss
  - Daily-Dur8-/Lower-Relax-Truth nach den letzten Partial-Runs weiterziehen.
    - `LOWER2K_DUR8_EVT24`
      - ueber Maerz hinaus weiterziehen, solange der Partial-Truth-Vertrag noch viele tractable Tage liefert
      - bekannte Heavy-Day-Liste explizit nutzen statt dieselben `maxTimeLimit`-Tage erneut zu rechnen
    - `LOWER1K_DUR8_EVT24`
      - Train-Checkpoint weiter vergroessern; der aktuelle grouped split testet auf `dur8`
    - Daily-Modellpfad:
      - gemeinsamen `table_09_paper`-Block nicht blind weiter retrainieren
      - stattdessen pruefen, ob ein eigener Daily-Targetpfad nur fuer:
        - `thermflex_shifted_space_heat_kwh`
        - `thermflex_rebound_kwh`
        - optional `co2_emissions_total_pct_change`
        mit engerer Feature-/Split-Logik sinnvoller ist
    - letzter strenger Daily-Holdout:
      - Modell:
        - `Learning/models/thermflex_daily_results_xgb_table_09_paper_2b65d41fa479/`
      - grouped-holdout `mean R2 = -0.007`
      - positive Ziele:
        - Cost
        - Boiler peak
        - Boiler energy
      - weiterhin negativ:
        - CO2
        - shifted
        - rebound
    - naechster konkreter Modellschritt:
      - erledigt: separaten Daily-Targetpfad nur fuer
        - `thermflex_shifted_space_heat_kwh`
        - `thermflex_rebound_kwh`
      aufgesetzt
      - Befund:
        - Profiltrennung allein reicht nicht; `shifted` / `rebound` bleiben auch dort negativ
      - daher als naechstes:
        - noch mehr `dur8`- und `2K`-Trainbreite
        - erledigt: taegliches CO2 separat untersucht
        - Befund: `co2_only` ist nicht besser als CO2 im gemeinsamen Daily-Block
        - pruefen, ob fuer die Daily-Mechanik ein engerer Holdout-/Group-Schnitt sinnvoller ist als der aktuelle harte Bundle-Holdout
        - mit dem aktuellen Truth-Stand weiter `LOWER2K_DUR8_EVT24` und `LOWER1K_DUR8_EVT24` Richtung spaete Heizperiode ziehen
        - sobald der reine Truth-Hebel weiter abflacht:
          - erledigt: Daily-Truthvertrag um zusaetzliche Aussentemperatur-Metriken erweitert
          - Befund:
            - hilft Cost
            - hilft nicht genug fuer `shifted` / `rebound` / taegliches `CO2`
          - erledigt: Daily-Truthvertrag um taegliche Kohortenmix-Features erweitert
          - Befund:
            - taegliche `dh_space_heat_share_*`-Anteile je Kohorte plus Residential/Non-Residential-Mix helfen dem Daily-`Table 09`-Pfad nicht robust
            - CO2 wird positiv, aber `shifted` / `rebound` verschlechtern sich
          - als naechstes:
            - Daily-Truthvertrag um zusaetzliche State-/Komfortmetriken pruefen, falls in bestehenden Artefakten sauber verfuegbar
            - vorbereitet:
              - neue Daily-Screens exportieren jetzt bereits
                - `thermflex_t_in_min_c`
                - `thermflex_t_in_max_c`
                - `thermflex_temperature_violation_degree_hours_total`
              - sobald neue `dur8`-/Lower-Relax-Bundles damit vorliegen:
                - Auxiliary-Target-Test fuer Temperatur/Komfort aufsetzen
            - andernfalls weiter gezielt `dur8`-Truth verbreitern und den starken Systempfad fuer Paper-Sensitivitaeten priorisieren
  - Hourly-Thermflex-Mechanikpfad jetzt als eigener Hebel weiterziehen.
    - bereits erledigt:
      - separater Layer `Learning/thermflex_hourly_mechanism/`
      - generischer Hydrator fuer fehlende reusable Hourly-Exports aus `selected_runs.json`
      - Scope explizit auf
        - `paper_dispatch_comparison_*`
        - `dh_thermflex_run_*/paper_core`
      begrenzt
      - Hourly-Truthbasis von einem deduplizierten 13er-Set auf `16` Run-Dirs / `5` Bundles verbreitert
    - aktueller bester Hourly-Pfad:
      - flaechennormiertes Energieprofil
      - Datensatz:
        - `Learning/datasets/f8f5fa261ac29180f4272a22c77b1f779495415b1cd6e3e57a66c9f43b5da54d/`
      - Modell:
        - `Learning/models/thermflex_hourly_mechanism_xgb_mechanism_energy_intensive_f8f5fa261ac2/`
      - grouped-holdout:
        - `mean R2 ~ 0.20`
        - `cohort_preheat_extra_wh_per_m2 ~ 0.32`
        - `cohort_temperature_violation_degree_h ~ 0.27`
    - zentrale Befunde:
      - Hourly ist fuer Mechanik plausibler als der reine Daily-Featurepfad
      - absolute kWh-Ziele generalisieren schlechter als flaechennormierte Kohortenziele
      - Rueckaggregation auf holdout-`shifted/rebound` ist aber noch nicht robust positiv
    - naechste Hourly-Hebel:
      - weitere explizite thermflex Runfamilien fuer reusable Hourly-Truth inventarisieren, falls kompatibel
      - pruefen, ob zusaetzliche teacher-nahe State-Ziele (`T_in_min/max`, Komfortverletzung) als Auxiliary-Targets den Hourly-Pfad stabilisieren
      - erledigt:
        - erste Segmentierung `constant_only` vs `day_night_only`
      - Befund:
        - `constant_only` verbessert den besten Hourly-Mechanikpfad deutlich:
          - Datensatz:
            - `Learning/datasets/6fc7ad11f8bae814f2e29bff77ecea84c51425aa23a23d8f786e1ee7c8c960a5/`
          - Modell:
            - `Learning/models/thermflex_hourly_mechanism_xgb_mechanism_energy_intensive_6fc7ad11f8ba/`
          - grouped-holdout `mean R2 ~ 0.34`
        - `day_night_only` ist aktuell nicht validierbar:
          - nur ein einziger expliziter `day_night_thermflex`-Run (`192` Zeilen)
          - grouped holdout scheitert korrekt mit nur einer Gruppe
      - daraus folgt als naechstes:
        - erledigt: Truthbasis fuer `day_night` gezielt ueber direkte Gold-Run-Dirs erweitert
        - erledigt: `evt1` vs `evt24` als weiterer Segment-Hebel explizit getestet
        - neuer Fokus:
          - `day_night`-Hourly-Pfad als solved family fuer Mechanik nutzen
          - `constant_evt1_only` weiter verbessern, vor allem fuer Rebound
          - nicht weiter auf `constant_evt1_lower_relax_only` setzen; der Slice wurde getestet und war schlechter als `constant_evt1_only`
          - erledigt: `constant_evt24_only` truthseitig homogenisiert und um direkte Peak/Price/Sunny/Winter/Shoulder-Goldruns erweitert
          - neuer Fokus fuer `evt24`:
            - Rebound verbessern, nicht mehr nur Truth suchen
            - beruecksichtigen:
              - im aktuellen Hourly-V1 werden Targets targetweise getrennt trainiert
              - reine Auxiliary-Zielspalten verbessern `q_delta` / `cutback` / `rebound` daher nicht direkt
            - stattdessen priorisieren:
              - family-routed Nutzung
              - Truth-Diversitaet innerhalb homogener Familien
              - schlanken Featurevertrag fuer `evt24` pruefen
            - erledigt:
              - expliziten `evt24_compact`-Feature-Mode als first-class Profil eingebaut
            - Befund:
              - trainierbar und intern stabil
              - aber aktuell kein klarer KPI-/Figure-Gewinner gegen den Vollmodus
            - daher als naechstes:
              - family-routed KPI-Vergleiche weiter priorisieren
              - Truth-Diversitaet innerhalb derselben `evt24`-Regime weiter staerken
            - insbesondere mehr unabhaengige Holdout-Gruppen erzeugen; die aktuelle KPI-Rueckaggregation fuer `evt24` basiert teils nur auf `2` Holdout-Tagen / `2` Holdout-Runs und ist dadurch noch fragil
            - erledigt:
              - figure-nahe `paper_mechanism_bundle_*`-Tage als generische Hourly-Truth-Familie angeschlossen
              - bestehende Bundles hydriert und Builder auf direkten Generic-Export erweitert
            - neuer Fokus nach dem haerteren Figure-Holdout:
              - `peak` im konstanten `evt24` verbessern
              - `upper_only dur24 evt24` als eigenes Figure-Regime weiter verbreitern und KPI-first pruefen
              - `mechanism_energy_intensive` fuer `evt24` als bevorzugtes Hourly-Zielprofil beibehalten; `mechanism_core` und `mechanism_energy` verschlechtern `shifted/rebound/peak` auf dem erweiterten Holdout
              - drittes `dur24 upper_only`-Mechanism-Bundle ist jetzt eingebunden; naechster Resthebel innerhalb `upper_only` ist explizit `rebound`
              - den gemischten `constant_evt24_only`-Pfad fuer `peak` konservieren, weil er nach der Bundle-Erweiterung schon fast neutral ist (`peak_r2` nahe 0)
              - repo-weiter Check ist erledigt: es gibt aktuell keinen weiteren versteckten `upper_only dur24 evt24`-Truthpool; weitere Verbesserungen dort brauchen neue Figure-Tage oder einen Fokuswechsel auf die staerkeren `lower_relax`-/gemischten Pfade
              - exakte Paper-`lower_relax`-Bundles fuer `LOWER1K_DUR4_EVT24` und `LOWER2K_DUR4_EVT24` sind jetzt angeschlossen; naechster Resthebel dort ist explizit `rebound`
              - `lower_relax` verbessert `peak` bereits stark; den Slice jetzt nicht wieder mit breiteren Zielprofilen verwässern
            - pruefen, ob family-routed Nutzung sinnvoll ist:
              - `day_night_only` fuer tagweise Mechanik
              - `constant_evt24_lower_relax_only` bzw. `constant_evt24_upper_only` fuer konstante `evt24`
          - danach pruefen, ob ein family-routed Hourly-Mechanikpfad (`day_night` + `constant_evt1`) die Daily-Table-09-Rekonstruktion fuer `shifted/rebound` schon robust genug schlaegt
          - neuer Stand:
            - expliziter KPI-level-Rebound-Postprocessor fuer `constant_evt24_lower_relax_only` ist jetzt vorhanden
              - Profil:
                - `lower_relax_evt24_conservative_v1`
              - Effekt:
                - `rebound_r2` von `~ -7.06` auf `~ 0.324`
                - `shifted` und `peak` unveraendert
            - naechster spezifischer Resthebel:
              - geprueft:
                - `upper_only dur24 evt24` profitiert aktuell **nicht** robust von einem analogen konservativen KPI-Sonderpfad
              - neuer Fokus dort:
                - neue unabhaengige Figure-Tage oder breitere homogene `upper_only`-Truth
              - gemischter `constant_evt24_only`-Stand:
                - als gemeinsamer `shifted/rebound`-Pfad weiter zu heterogen
                - aber als `peak`-Pfad brauchbar
                - expliziter Peak-Postprocessor ist jetzt vorhanden
                  - verbessert `peak_r2` dort von `~ 0.31` auf `~ 0.44`
              - daraus folgt:
                - `peak` im gemischten `evt24` konservieren
                - `shifted/rebound` weiter family-routed lassen
              - neuer model-first Rahmen steht:
                - `Learning/model_target_matrix.py` als explizite SSOT für KPI-/Target-Ownership
              - naechste Verbesserungsarbeit daran ausrichten:
                - Daily:
                  - `co2_emissions_total_pct_change`
                  - `district_gas_boiler_*`
                - Hourly:
                  - echte `tau`-Variation in die Truthbasis bringen (`3/4/5/6 h` usw.), jetzt wo `policy_tau_h` explizit im Hourly-Vertrag steckt
                  - `constant_evt24_upper_only` über neue unabhängige Truth-Tage
                  - `constant_evt24_lower_relax_only` Rebound-Sonderpfad beibehalten und gegen neue Truth weiter prüfen
                - neue Infrastruktur dafür steht bereits:
                  - `emit_tau_evt24_grid_overrides.py`
                  - `run_tau_evt24_heating_season_screen_bundle.py`
                - nächster echte Trainingshebel:
                  - die `LOWER1K_DUR4_EVT24`-Tau-Screens tatsächlich rechnen und in Daily-/Hourly-Truth aufnehmen

## Current tau4 surrogate follow-ups

- Done:
  - tau4 lower-relax `evt24` now uses the 27-day Hourly-Truth basis.
  - `group_stratified_shuffle` with `stratify_column=month` is available for grouped KPI holdouts.
  - Candidate model:
    - `Learning/models/thermflex_hourly_mechanism_xgb_mechanism_energy_intensive_74d382eb0b73/`
  - With `shifted_postprocessor.json`, the best current tau4 holdout gives:
    - `shifted_r2 ~ 0.977`
    - `rebound_r2 ~ 0.984`
    - `peak_r2 ~ 0.593`
  - Repeated-holdout diagnostics are persisted under:
    - `Learning/models/thermflex_hourly_mechanism_xgb_mechanism_energy_intensive_74d382eb0b73/diagnostics/`
    - 10-seed median with state-feature shifted postprocessor:
      - `shifted_r2 ~ 0.986`
      - `rebound_r2 ~ 0.293`
      - `peak_r2 ~ 0.549`
- Next:
  - improve tau4 `peak`, especially negative peak-reduction days
  - improve repeated-holdout robustness for `rebound`, not only the best seed
  - tau3 check is done and currently truth-limited:
    - only 9 days
    - shifted-state median `~ -1.58`
    - rebound median `~ -0.316`
    - peak median `~ -0.944`
  - next truth expansion should target tau3 transition days before broadening tau5-8 further

## Current surrogate quality blockers after 2026-05-15 tests

- Daily KPI blocker:
  - Current grouped daily holdout is still below the requested `R2 >= 0.95`.
  - Strongest current daily signals:
    - shifted around `0.90-0.93`
    - boiler generation around `0.87-0.89`
    - absolute cost delta around `0.86-0.87`
  - Weak targets:
    - CO2 daily deltas / pct
    - district boiler peak
    - thermflex peak
    - rebound
  - Do not spend more runs on blind chronological lower/upper daily truth before the target contract is improved.
  - Next useful Daily step:
    - promote target-specific estimator routing from diagnostics into the train/predict path:
      - XGB for cost-like targets
      - ExtraTrees smooth for CO2/boiler peak/shifted/rebound/thermflex peak
    - train/evaluate a new Daily profile on the newly exported heat-cost/source-dispatch component columns once enough new v3 screen rows exist.

- Hourly upper-only blocker:
  - Added `30+` independent upper-only mechanism days and fixed duplicate `run_dir` weighting.
  - Current upper-only hourly reaggregation is still not close to `0.95`.
  - Next useful Hourly step:
    - improve the state/mechanism contract, not just add more upper-only days:
      - richer daily/hourly state postprocessor features
      - explicit zero/nonzero rebound classifier with calibrated abstention
      - separate peak-reduction vs peak-increase regimes
      - check whether `compute_thermflex_series_metrics` reconstruction from hourly cohort truth matches the daily screen KPI definition on identical dates.

- Solver/runtime blocker:
  - `2023-12-25` upper-only mechanism replay hung under the current mechanism-bundle helper.
  - Before retrying that date:
    - add an explicit solver envelope to mechanism-bundle replays or run it as an isolated single-day job with `THERMFLEX_HIGHS_TIME_LIMIT_S` and `THERMFLEX_HIGHS_MIP_REL_GAP`.

## Rolling-Horizon surrogate truth next step

- Current finding:
  - Paper figures use a different solve contract than most Learning truth:
    - 36 h dispatch horizon
    - 24 h rolling commit
    - warmup trimming
    - DH-bus inertia tau
  - Daily and Hourly dataset contracts now carry the dispatch solve-state features explicitly.
- Next useful implementation step before broad overnight truth:
  - add a dedicated rolling-window truth export instead of forcing 36/24 figure caches into `thermflex_daily_results_v1`.
  - minimum contract:
    - visible evaluation date/window
    - warmup hours
    - horizon/rolling commit/lookahead
    - tau
    - case family and duration/lower-relaxation
    - KPI block for cost, CO2, boiler energy/peak, shifted, rebound, peak-change.
- Overnight priority if no new exporter is implemented first:
  - continue tractable 24/24 screens only for tau3/tau4 lower-relax `evt24` and avoid broad upper-only random filling.
  - use explicit per-day solver envelope:
    - time limit around `600 s`
    - MIP gap around `0.01`
    - allow incomplete days so single hard days do not block the run.

- Done 2026-05-16:
  - tau3/tau4 lower-relax `evt24` screens were expanded across the heating season.
  - This improved daily Rebound and DH-Peak but did not solve cost/CO2/boiler-peak R2.
- Next:
  - implement dedicated `thermflex_paper_figure_rolling_v1` Learning export from weekly/rolling figure truth.
  - add regime labels for source-stack switches:
    - CHP constrained vs free
    - boiler-start/partload active
    - peak-boiler increase vs reduction
    - upper-only vs lower-relax vs tau family
  - avoid another blind 24/24 Daily truth expansion until that contract exists.

## Dispatch economics surrogate targets

- Do not use net `dispatch_operating_cost_eur` percentage change as the primary daily/window cost target when CHP electric value is active; the denominator can be near zero or negative.
- Prefer these training targets for cost/CO2 table KPIs:
  - absolute `dispatch_heat_operating_cost_eur` or cost delta over 1-3 day windows
  - `dispatch_heat_allocated_co2_t` / absolute CO2 deltas over 1-3 day windows
  - keep CHP electric value, boiler/CHP CO2, boiler peak, and source shares as explicit regime/features.
- For the next truth/export contract, include:
  - `gas_chp_electric_value_eur`
  - `dispatch_heat_operating_cost_eur`
  - `dispatch_heat_allocated_co2_t`
  - `district_gas_chp_heat_allocated_co2_t`
  - boiler/CHP fuel input and generation totals.

- Updated finding:
  - existing v3 tau3/tau4 truth shows that cost/CO2 errors are driven mainly by gas-CHP generation deltas, not by the peak-boiler CO2 factor or pure target scaling.
  - External heat and waste-incineration deltas are already easy for the surrogate; CHP thermal generation is currently the blocker.
- Updated 2026-05-16:
  - Flow reconstruction is the preferred path for cost/CO2:
    - train CHP thermal/electric, boiler and other source-flow deltas
    - reconstruct heat cost and CO2 from components/flows
    - avoid direct net-cost blackbox training as the primary objective
  - Current two-stage CHP-regime diagnostic improves reconstructed Daily cost/CO2 to roughly `R2 0.50`; oracle CHP regime is roughly `R2 0.68-0.70`.
  - Storage is not a current modeling priority for dispatch-cost/CO2 improvement.
- Next truth/export step:
  - run new daily screens with the updated export contract so each row carries:
    - `dispatch_heat_allocated_co2_t_*`
    - `district_thermal_storage_charge_kwh_*`
    - `district_thermal_storage_discharge_kwh_*`
    - `district_thermal_storage_soc_mean_kwh_*`
    - `district_thermal_storage_soc_end_kwh_*`
  - then add a `dispatch_economics_storage` feature mode or extend the existing mode once enough complete rows exist.
- Next modeling step before another broad overnight:
  - target sampling to CHP-switching days:
    - March/April shoulder days with high CHP delta
    - October shoulder days with high CHP delta and low boiler delta
    - selected winter days where CHP increases while boiler falls.
  - improve CHP regime model:
    - classify CHP up/down/neutral first
    - train CHP thermal/electric regressors within regime
    - check errors by regime before collecting another broad truth block.
  - Current preferred regime split:
    - `strong_down/down/neutral/up/strong_up` using CHP thermal delta thresholds.
    - Avoid pure sign-based regimes; current diagnostics are weaker.
  - Next targeted truth families:
    - fill tau5-8 for missing CHP `down/neutral/strong_down` dates first.
    - then repeat the same CHP-stratified date set for:
      - `LOWER1K_DUR8_EVT24`
      - `LOWER2K_DUR4_EVT24`
      - `LOWER2K_DUR8_EVT24`
    - keep `evt24` fixed until CHP source-stack quality improves.
  - Candidate dates for missing CHP regimes from tau3/tau4 truth:
    - `2023-04-01`, `2023-10-06`, `2023-04-23`, `2023-04-22`, `2023-04-10`, `2023-10-12`, `2023-10-03`, `2023-10-02`
    - `2023-03-10`, `2023-03-23`, `2023-02-23`, `2023-11-03`, `2023-04-30`, `2023-03-11`, `2023-03-16`
    - `2023-10-21`, `2023-10-07`, `2023-10-28`, `2023-04-11`, `2023-04-25`
    - add neutral fillers if runtime permits: `2023-03-22`, `2023-03-17`, `2023-01-23`, `2023-02-14`, `2023-12-06`.

## Hourly dispatch surrogate next steps

- Current contract:
  - `Learning/thermflex_hourly_dispatch` learns dispatch source-stack deltas from:
    - policy/tau/duration features
    - hourly weather/price/DH-state
    - REF dispatch state
    - upstream ThermFlex load response (`dh_bus_load_kwh_delta`, later predicted by mechanism surrogate).
- Current quality signal:
  - With oracle upstream load delta and the expanded Truth basis:
    - Global Daily Heat-Cost is around median `R2 ~= 0.96`.
    - Global Daily CO2 is around median `R2 ~= 0.99`.
    - Hourly CO2 is around median `R2 ~= 0.96`.
    - Hourly Heat-Cost remains lower, around median `R2 ~= 0.92`.
  - Family-specific Daily Heat-Cost still has gaps below `0.95`, especially upper-only and some tau/relaxation slices.
- Next targeted modeling tasks:
  - Train/validate the upstream hourly mechanism-to-DH-load path so `dh_bus_load_kwh_delta` can be predicted, not only supplied as oracle truth.
  - Add a component reconstruction diagnostic:
    - predict CHP/Boiler/fuel/electric-value components hourly
    - reconstruct `dispatch_heat_operating_cost_eur_delta` from components
    - compare against direct cost-target regression.
  - Add family-/regime-aware routing for Dispatch-Cost:
    - at minimum split or route by upper-only vs lower-relax, duration, tau and CHP/electric-value regime.
    - evaluate global-train/family-test metrics, not only global medians.
  - Improve Daily Heat-Cost:
    - focus on boiler/fuel-cost and `gas_chp_electric_value_eur_delta` residuals.
    - add more dates with strong boiler variation and mixed CHP/electric-value regimes before broad family expansion.
  - Once `LOWER1K_DUR4` is stable, repeat the same CHP-stratified date set for tau5-8 and duration/lower-relax families.
- Updated 2026-05-17:
  - Treat the Mechanism-to-DH-load path as the current bottleneck:
    - Oracle-load dispatch is already strong enough for global Daily Cost/CO2/flows.
    - predicted-load end-to-end dispatch is not strong enough.
  - Next modeling step:
    - evaluate and improve the upstream mechanism/load surrogate by family, tau, duration and weather/economic regime.
    - only then re-run end-to-end Dispatch.
  - Next truth step:
    - collect continuous multi-day/weekly truth windows for rolling/figure periods.
    - avoid interpreting family R2 for near-zero peak-delta slices without MAE/scale diagnostics.
- Updated after slice diagnostics:
  - Build the next mechanism/load candidate as a family-aware KPI path:
    - keep lower-relax tau4 shifted state-postprocessor as known good candidate.
    - add/test upper-only daily KPI postprocessor or direct daily load-delta model.
    - add/test broader lower-relax shifted/rebound postprocessors by tau/duration/weather regime.
  - Expand mechanism truth only where the slice diagnostics show real gaps:
    - upper-only shoulder and winter days.
    - lower-relax tau5-8/tau12 with enough independent run groups.
    - duration variants beyond the current sparse dur4/dur24 mix.
- Direct-Daily diagnosis result:
  - Use ExtraTrees as first Direct-Daily candidate, not XGB, for the small mechanism KPI sets.
  - Keep `lower_relax` direct Daily path for `shifted` and `peak`.
  - Do not treat `rebound` as solved; test either a stronger explicit rebound classifier/regressor or collect targeted rebound-active truth.
  - Do not treat `upper_only` as solved; collect or route upper-only days separately, especially shoulder/winter and high-rebound cases.
- Updated after Two-Stage/Profile tests:
  - Do not spend another broad modeling pass on generic 24h profile features before new truth; the tested profile block did not close the upper-only/rebound gap.
  - Treat these as the next targeted truth priorities:
    - `upper_only` winter/shoulder days with high shifted/rebound/peak-change signal.
    - lower-relax rebound-active shoulder/winter days where positive post-reduction load is material.
    - tau8/tau12 and tau2 edge cases only where they are needed for sensitivity figures/tables, not as generic bulk expansion.
    - continuous 3-7 day windows for rolling/weekly/Figure-15-like validation once isolated daily gaps are under control.
  - Re-evaluate with:
    - family-aware Direct-Daily KPI models for daily shifted/rebound/peak.
    - hourly mechanism shape diagnostics for figure-driving load profiles.
    - end-to-end dispatch using predicted load only after the mechanism path improves.
- Updated after targeted upper-only truth:
  - Upper-only has materially more truth now, but Direct-Daily `shifted/rebound/peak` is still not solved.
  - Next upper-only modeling step should be state-/sequence-aware:
    - inspect hourly predicted-vs-true heat-shape errors on the new targeted days.
    - split upper-only days into rebound-active, rebound-zero, peak-reduction and near-neutral states.
    - train routed KPI/state models instead of one shared upper-only Direct-Daily regressor.
  - Dispatch path can keep using the expanded dataset:
    - Oracle-load Daily CO2 is strong.
    - Heat-Cost still needs attention in upper-only Electric-Value/Fuel-Regime slices before claiming all upper-only costs are consistently `R2 >= 0.95`.
- Updated after Upper-only screen-artifact reuse:
  - Do not expect generic additional Upper-only Daily-Truth alone to lift `shifted/rebound/peak` to `R2 >= 0.95`; the expanded `137`-day Mechanism slice made the holdout more honest but not better.
  - Keep `no_hourly_grid` as the current best Direct-Daily diagnostic preset for Upper-only; full 24h grid and prior-state features overfit or degrade the small daily sample.
  - Next high-value options:
    - derive an explicit sequence/state target for Upper-only rebound and shifted mass from hourly `q_delta` sign runs, then route/regress by that state.
    - test a deterministic or semi-physical reconstruction from predicted component profiles instead of blackbox Daily `shifted/rebound`.
    - if more truth is collected, prefer continuous windows and missing regime states over more isolated generic days.
    - for paper tables/figures that only need a handful of Upper-only days, consider using persisted truth for those selected days until the state-aware surrogate is validated.
- Updated after comparing against the old Rebound fix:
  - Do not reuse the lower-relax Deadband-Rebound fix for Upper-only:
    - lower-relax had false-positive Rebound activation.
    - Upper-only mainly underpredicts real positive Rebound/Shift mass.
  - Keep the new explicit `daily_xgb_rebound_v1` path as a diagnostic/candidate only; it improves the symptom but is not sufficient.
  - Next modeling task:
    - change the Upper-only Mechanism path to learn `preheat_extra`, `cutback_shed` and resulting sign-run sequence mass more directly.
    - evaluate whether identity/positive-target transforms or a routed component model produce skalenrichtige hourly masses.
    - only then re-evaluate Daily `shifted/rebound/peak` and end-to-end dispatch.
- Updated after simple-analogy tests:
  - Keep `no_case_label` and `mechanism_mass_identity` as useful candidate contracts, but do not mark them preferred yet.
  - Broad `constant_evt24_only` training helps the aggregate and lower-relax slices, but does not solve Upper-only.
  - Do not pursue naive sample weighting on large `q_delta`; first smoke made holdout KPIs worse.
  - Next Upper-only work should stay simple:
    - compare predicted vs true `preheat_extra` and `cutback_shed` by hour/regime.
    - build a component-based Upper-only reconstruction from those two masses before adding new model complexity.
    - use the existing lower-relax KPI-layer pattern only after the component masses are skalenrichtig.
- Updated after Rebound decomposition:
  - Treat Upper-only Rebound as a two-error problem:
    - false-active zero-Rebound days.
    - active-Rebound days with underpredicted/timing-shifted positive mass after the first negative trigger.
  - Next small model test:
    - build an explicit two-stage Upper-only Rebound postprocessor:
      - stage 1 active-vs-zero classifier from ex-ante daily state plus raw reconstructed KPI diagnostics.
      - stage 2 mass regressor/scaler only on active days.
    - compare against the existing lower-relax deadband profile and the current `daily_xgb_rebound_v1`.
  - Do not apply the lower-relax deadband profile wholesale to Upper-only.
- Updated after two-stage Rebound smoke:
  - Keep `upper_only_rebound_twostage_sequence_et_v1` as a diagnostic candidate, not preferred.
  - The simple Daily-XGB Rebound postprocessor still performs better than the ET two-stage candidate in the current smoke checks.
  - Do not invest more in Rebound-only postprocessing until the upper-only hourly mass/sequence fit improves.
- Updated after cohort/family Rebound decomposition:
  - Add a cohort-family routing test before collecting more truth:
    - old buildings: `pre1975`, `1975_1990`
    - modern buildings: `1990_2000`, `2000_2014`
    - residential vs non-residential as secondary split.
  - Evaluate upper-only `q_delta`/positive-mass/negative-mass models separately for these cohorts/families.
  - Penalize or gate false activation in `2000_2014`, especially non-residential, because it currently contributes too much predicted Rebound.
- Updated after q_delta sequence error decomposition:
  - Build the first simple Upper-only Sequence-Router with these axes:
    - cohort age: old (`pre1975`, `1975_1990`) vs modern (`1990_2000`, `2000_2014`)
    - season: winter vs spring/autumn shoulder
    - regime: high-price/high-DH vs low-DH
    - hour block: early trigger (`0-6`), morning/preheat (`7-14`), evening/timestep boundary (`21-23`)
  - Train/evaluate positive and negative `q_delta` components per routed bucket.
  - Reconstruct daily `shifted/rebound/peak` from routed hourly predictions before any further Rebound-only postprocessor tuning.
- Updated after reproducible Upper-only sequence-router diagnostic:
  - Keep `evaluate_sequence_router_holdouts.py` as the reusable diagnostic harness for routed hourly q_delta component tests.
  - Do not promote `age_hour` router yet:
    - it improves `shifted` in the reproducible seed-42 check, but leaves `rebound` clearly too weak.
    - 24h vector learning per cohort/day did not close the gap.
    - direct ex-ante Daily KPI learning also remains weak for Upper-only shifted/rebound.
  - Next high-value Upper-only work:
    - collect or reuse targeted truth in rebound-/shift-active winter and shoulder states.
    - include old-building-heavy families explicitly in the truth plan.
    - test an explicit active-state/sequence contract before further generic model complexity.
    - avoid `case_label`/date-label leakage as a shortcut.
- Updated after Upper-only oracle ablation:
  - Do not use plain family/hour mass scaling as the next fix; first smoke improved shifted but worsened rebound/peak.
  - Split the Upper-only problem into two explicit subcontracts:
    - Winter/old-building mass contract for shifted and absolute positive/negative q_delta mass.
    - Shoulder rebound gate/timing contract to suppress false rebound on no-cutback or late-cutback days.
  - Next implementation target:
    - derive train/test labels for `rebound_zero`, `late_or_no_negative_trigger`, and `winter_old_mass_underprediction`.
    - evaluate those labels before any new learner is promoted.
- Updated after Upper-only subcontract evaluation:
  - Promote the Family-Day mass contract as the next candidate for `shifted` improvement, but keep it diagnostic until repeated holdouts are run.
  - Do not spend more effort on plain raw-sequence rebound scaling.
  - For Rebound, target the narrow ambiguity zone:
    - shoulder days with mean outdoor temperature roughly `12-15 C`.
    - low/medium reference heat days around `~7-12 GWh/day`.
    - predicted early negative trigger around hour `2`.
    - include paired examples with true zero rebound and true high rebound.
  - Also keep winter old-family high-mass days in the truth plan, because they drive shifted mass and winter rebound underprediction.
- Updated after repeated Upper-only subcontract checks:
  - Treat the Family-Day mass contract as promising but not sufficient:
    - robust mass target R2 is high, but daily shifted remains around `0.77-0.83` over repeated checks.
    - true Family-mass oracle can reach shifted `~0.97`, so the remaining gap is precision/timing, not the KPI definition.
  - Do not promote the tested Daily Shifted corrector; repeated checks did not improve over mass-corrected shifted.
  - Next targeted work:
    - add truth or templates for family timing/cancellation, especially winter old-family days.
    - add paired shoulder zero/high rebound days for gate separation.
- Updated after full Upper-only-dur24 truth coverage:
  - Do not collect more Upper-only-dur24 truth from the current `heating_season_screen_joined.csv`; the 212-day screen inventory has been exhausted.
  - Treat current Full-Truth result as:
    - shifted: close but still below target (`R2 ~0.92` via Family-Mass path).
    - rebound: still blocked by Zero-/Late-trigger gate (`R2 ~0.45`, oracle-zero `~0.91`).
    - peak: still weak (`R2 ~0.47`).
  - Next work should be model-contract, not more generic truth:
    - learn `late_or_no_negative_trigger` explicitly.
    - reconstruct rebound from predicted first-negative timing plus mass-corrected sequence.
    - add a dedicated false-active suppressor for zero/low rebound days.
    - only then revisit peak, because peak depends on the same timing contract.
  - Fix/extend diagnostics:
    - keep split strategy encoded in model IDs for all future train runs.
    - add a repeated-holdout evaluator for the candidate Zero-/Late-trigger contract.
- Updated after Zero-/Late-trigger contract diagnostic:
  - Keep `evaluate_upper_only_trigger_contract.py` as the reproducible gate/magnitude evaluator.
  - Do not promote the current gate model:
    - clean best Upper-only rebound remains only around `R2 ~0.52`.
    - optional predicted preheat/cutback component features did not help.
  - Next Upper-only work:
    - define a direct trigger/timing target from hourly truth, e.g. `late_or_no_negative_trigger`, `first_negative_hour`, and `positive_after_first_negative_kwh`.
    - train/evaluate that target by family/season instead of another global daily Rebound regressor.
    - if collecting more truth, prioritize paired shoulder zero/high-rebound cases and tau/duration families that expose the trigger boundary.
  - For immediate paper table/figure production:
    - use persisted truth for selected Upper-only days where available.
    - use the surrogate confidently for lower-relax/family dispatch KPIs, but flag Upper-only Rebound/Peak until the timing contract is solved.
- Updated after Timing/Template/Deep-XGB checks:
  - Do not spend more time on generic XGB capacity sweeps for Upper-only:
    - Deep-XGB made Daily subcontracts worse.
  - Do not use average sign-run templates for paper outputs:
    - they smooth away timing and damage shifted/peak.
  - Next concrete work:
    - build a Boundary-Truth plan for paired Shoulder cases:
      - true zero/low rebound with false predicted early trigger.
      - nearby high-rebound cases with similar weather/reference-load state.
      - repeat across tau/duration families where sensitivity output needs coverage.
    - add/export explicit Mechanism state targets if available:
      - actual event start/recovery boundary,
      - cutback trigger hour,
      - recovery start hour,
      - positive-after-cutback mass.
    - retrain/evaluate the active-state gate on those state targets before touching Dispatch again.
- Updated after Boundary-Truth batch preparation:
  - Next executable truth path is ready:
    - emit grid overrides with `Optimization/run/analysis/emit_upper_only_tau_duration_grid_overrides.py`
    - run compact tier-0/1 boundary truth with `Optimization/run/analysis/run_upper_only_boundary_truth_batch.py`
  - Recommended run order:
    - Tier 0 first: `tau4/dur24`, low/high boundary anchors, 18 date-family rows.
    - Tier 1 next: `tau4/dur1/4/8`, same anchors.
    - Tier 2 only if time remains: `tau2/8/12` at `dur24`.
  - After any real batch:
    - hydrate/register the new hourly dispatch/mechanism truth into `Learning/datasets/`.
    - retrain the mechanism model and rerun:
      - `evaluate_upper_only_subcontracts.py`
      - `evaluate_upper_only_trigger_contract.py`
      - `evaluate_upper_only_timing_contract.py`
- Updated after Upper-only tau4/dur24 truth expansion:
  - Do not mix old Upper-only `policy_tau_h == 0` artifacts into tau4 training/evaluation except as exploratory candidate selectors.
  - Current tau4/dur24 usable status:
    - shifted is near target but still below `0.95` (`~0.93` on the latest balanced holdout).
    - rebound remains below target (`~0.60` best trigger contract).
    - peak daily R2 remains unstable because the target has many zero/near-zero days and shares the same timing boundary.
  - Next highest-leverage work:
    - build a true mechanism-state target, not another generic regressor:
      - true rebound-active at paper threshold,
      - first cutback/negative-trigger hour,
      - positive mass after trigger,
      - false-active shifted-without-rebound state.
    - evaluate a router by:
      - winter mostly-low regime,
      - shoulder active/low boundary,
      - October/November false-active boundary.
    - only collect more tau4 truth if the state-target analysis identifies a missing cell; generic winter high probes already mostly collapsed to Low-Rebound.
  - For tau sensitivity (`tau 2/8/12`) and duration sensitivity:
    - use the prepared override grid and batch runner,
    - keep each tau/duration family separate in `Learning/datasets/`,
    - avoid evaluating sparse tau families with unstratified random group splits.
- Updated after Upper-only state-target tests:
  - Keep `mechanism_core` as the preferred Rebound-state candidate for Upper-only tau4/dur24 diagnostics:
    - current clean best `rebound_r2 ~0.81`.
    - best cross-router candidate `~0.82`.
  - Keep `mechanism_energy_intensive` / family-mass path for shifted and energy-mass diagnostics:
    - shifted remains around `0.93-0.95` depending on feature mode.
  - Do not promote broad timeblock/ex-ante profile features yet:
    - they overfit or degrade the small grouped holdout.
  - Next high-leverage work for `R2 >= 0.95`:
    - collect or identify paired Upper-only tau4/dur24 truth around the remaining false-active boundary:
      - `2023-11-05`, `2023-11-21`, `2023-11-23`.
      - paired high-rebound anchors around `2023-10-14/15` and `2023-11-16`.
    - add explicit event-state targets if available from truth:
      - `cohort_event_start_count`,
      - first negative/cutback hour,
      - recovery/positive-after-trigger mass,
      - false-active shifted-without-rebound label.
    - then rerun the Core-state gate and cross-router evaluation before adding more generic truth.
- Updated after Upper-only tau4/dur24 Boundary expansion round 2:
  - Do not treat the enlarged 133-day Upper-only tau4/dur24 set as solved:
    - best old comparable holdout improved only slightly to `rebound_r2 ~0.823` via `raw_positive_mass`.
    - enlarged Boundary holdouts expose new failures and can score near/under zero with the current gate/magnitude contract.
  - Next work should be structural, not another broad truth/model sweep:
    - persist explicit daily/hourly trigger labels:
      - true rebound active at the paper threshold,
      - first negative/cutback hour,
      - positive mass after first negative/cutback,
      - shifted-without-rebound false-active label.
    - train the gate/router on those labels by regime:
      - shoulder zero/high boundary,
      - October/November false-active boundary,
      - winter low-rebound mass timing.
    - keep duration families separate:
      - use dur1/4/8 truth for duration-router diagnostics,
      - do not merge dur1/4/8 directly into the dur24 model.
  - Also fix the screen markdown writer so zero/near-zero boiler peak percentage rows do not fail after successful CSV generation.
- Updated after Trigger-State label export:
  - Screen markdown writer is fixed; remove this as a blocker for future truth batches.
  - Next Upper-only modeling step:
    - train/evaluate a two-stage state router from `daily_trigger_state_labels.csv`:
      - first classify `true_shifted_without_rebound` vs `true_rebound_active`,
      - then learn `positive_after_cutback_kwh` only inside the active state,
      - keep shoulder/winter regimes explicit.
    - use `hourly_trigger_state_labels.csv` to inspect whether the wrong signal is early predicted cutback hour or only excessive positive tail.
  - Do not collect more generic Upper-only tau4/dur24 truth until this state-router result is evaluated.
- Updated after first Trigger-State router:
  - State routing is promising but not sufficient:
    - best hard-holdout rebound improved to `R2 ~0.47`.
    - active-state F1 is around `0.78`.
  - Next router refinement:
    - split shoulder zero/high boundary from winter low-rebound before fitting magnitude.
    - add a dedicated shifted-without-rebound classifier and use it as an explicit veto before active rebound.
    - inspect the hourly labels for early predicted cutback hours on false-active days.
- Updated after shifted-without-rebound veto and context-profile test:
  - The veto does not improve hard-holdout Rebound beyond `R2 ~0.47`.
  - Extra daily price/weather/load context overfits in the current 100-train-day router; keep it available as `state_plus_daily_context`, but prefer `compact_state` until more boundary truth exists.
  - Next highest-leverage action:
    - run targeted Upper-only boundary truth from
      `.../upper_only_boundary_truth_plan_current/upper_only_boundary_truth_run_plan_core.csv`.
    - start with Tier 1 duration variants around the paired low/high shoulder boundary days:
      - low anchors: `2023-03-05`, `2023-04-13`, `2023-10-30`.
      - high anchors: `2023-03-07`, `2023-04-08`, `2023-10-04`.
    - then hydrate/register the new bundles and retrain separate duration-family routers.
  - Do not rely on direct Daily-KPI regression for this Upper-only slice yet:
    - direct daily ExtraTrees remained weak for rebound on the 133-day family (`mean R2 ~0.18`).
- Updated after overnight Upper-only truth expansion:
  - Best current tau4/dur24 Upper-only router candidate:
    - dataset `f658c724ffb1...` with 142 days.
    - model `thermflex_hourly_mechanism_xgb_mechanism_core_event_f658c724ffb1...`.
    - state router `rebound R2 ~0.68`, Active-F1 `~0.92`.
  - Do not blindly add all target-plan days into one dur24/tau4 router:
    - the broader 168-day dataset `573814bf8d82...` reduced best router R2 to `~0.50`.
    - next training should compare route families rather than one pooled model:
      - shoulder zero/high boundary,
      - winter mass/timing,
      - high-tail rebound.
  - For tau sensitivity, use the newly registered datasets:
    - evt24 tau sensitivity `c16e77c05ac0...`.
    - full tau-duration family `fbdca3592839...`.
  - Next modeling step:
    - build a family-router that selects between the 142-day tau4/dur24 router and separate winter/high-tail routes.
    - run repeated grouped holdouts before promoting the broader 168-day data.
- Updated after 2026-05-19 targeted Shoulder-Boundary run:
  - Preferred current diagnostic stand for the old `f658...` anchor:
    - dataset `1f41fdd475cf...`.
    - model `thermflex_hourly_mechanism_xgb_mechanism_core_event_1f41fdd475cf...`.
    - old-anchor daily rebound `R2 ~0.935`, Active-F1 `1.0`.
  - Remaining gap to `R2 >= 0.95` is active-day rebound magnitude, not active/inactive classification.
  - Do not promote the colder `target2` expansion (`86a559fc3b86...`) without further split diagnostics; it worsened the old anchor to `~0.79`.
  - Next useful step:
    - add an explicit train-only active-day magnitude calibration/diagnostic contract, or
    - collect only paired high/low Shoulder truth close to the April/October failure pattern; avoid broad colder Shoulder additions.
  - Lagged daily context was tested as `state_plus_lagged_context`; it did not improve the old anchor beyond `~0.935`.
  - Keep `state_plus_daily_context` as the preferred clean profile for now.

- Updated after ThermFlex paper sensitivity-quadrant / LOWER2K overnight prep:
  - Main sensitivity artifact path is now explicit:
    - figure builder:
      - `Documentation/Papers/thermflex_paper/figures/build_fig_scatter_concept_flexibility_performance_map.py`
    - overnight LOWER2K tau-duration bundle:
      - `Optimization/run/analysis/run_lower2k_tau_evt24_heating_season_screen_bundle.py`
  - Next overnight truth block should target:
    - `LOWER2K`
    - durations `1/4/8/12 h`
    - tau grid `2/4/8/12 h`
    - heating-season screens first; then refill the quadrant/table outputs from those explicit screen folders.
  - Current quadrant contract:
    - Panel A: seasonal cost-vs-CO2 savings quadrant from heating-season screens.
    - Panel B: tau-duration heatmap for one explicit family (`upper_lower_2k` by default).
    - Panel C: daily state/price/weather driver ranking.
    - Panel D: representative strategy-profile radar.
  - Current heatmap coverage is intentionally incomplete until the overnight LOWER2K tau grid exists; render incomplete coverage only explicitly with `--allow-incomplete-heatmap`.

- Updated after central MILP table-runner setup:
  - Main-paper central-results workflow can now be started directly from:
    - `Documentation/Papers/thermflex_paper/tables/run_main_table_central_truth_tau4.py`
  - Next practical run sequence:
    - first full central MILP table run for upper-only + lower `1K/2K × 1/4/8/12`
    - then dedicated `LOWER2K × tau × duration` overnight truth for the sensitivity quadrant
    - then rerender:
      - `table_main_central_results_tau4.*`
      - `fig_scatter_concept_flexibility_performance_map.*`
- Updated after hybrid surrogate-filled central table draft:
  - Inspect `table_main_central_results_tau4_hybrid_surrogate_filled.*` only as a draft.
  - The Daily-Table09 surrogate used for missing central-table rows has modest holdout R2:
    - cost pct `~0.59`, CO2 pct `~0.43`, shifted `~0.53`, rebound `~0.48`, boiler peak `~0.03`.
  - Treat `2K dur4/dur8` surrogate rows as suspect: current draft predicts identical full-period values, so duration separation is not reliable there.
  - Before using the hybrid table in the paper, either:
    - solve targeted MILP anchors for the missing duration cases, or
    - train/promote a stronger duration-aware daily/window surrogate with complete `1K/2K x dur1/4/8/12` coverage.
- Updated after targeted strongest-horizon overnight start:
  - Let Scheduled Task `ThermFlexTau4Overnight_20260520_1448` finish the targeted candidate plan.
  - Next check:
    - inspect `Documentation/Papers/thermflex_paper/tables/targeted_milp_overnight_tau4_20260520_145054.log`.
    - verify `targeted_milp_candidate_plan_tau4_runs.csv` has all candidate cases.
    - rebuild/inspect `table_main_strongest_horizons_tau4.*` and especially `table_main_strongest_horizons_tau4_sources.csv`.
  - If remaining `maxTimeLimit` dates affect selected strongest day/week rows, rerun only those explicit case/date gaps with a higher day time limit rather than broadening the full season.

- Updated after stopping the heavy full-season main-table MILP path:
  - Use `Documentation/Papers/thermflex_paper/tables/run_main_table_central_truth_tau4.py`
    only in the selected-window mode:
    - one shared explicit `--selected-day`
    - `December`, `February/March`, `April` week
  - Do not resume the old "full heating-season first, then slice" table path for
    the central paper table unless a separate full-period claim is explicitly needed.
  - Next step:
    - choose the shared selected day
    - rerun the central MILP table with `1K/2K x dur1/4/8/12`
    - then continue with `LOWER2K x tau x duration` truth for the sensitivity quadrant.

- Updated after consolidating the surrogate-quality lessons:
  - Do not promote the old `thermflex_daily_results` Table09 hybrid fill as the
    general ThermFlex surrogate. Its Table09-oriented percent targets remain too
    weak and partly methodologically unstable.
  - Treat Table09 and the central paper tables as consumers of a broader
    ThermFlex KPI surrogate, not as the model contract.
  - Use the successful `thermflex_system_results` / `dispatch_kpi_paper` contract
    as the architectural anchor:
    - primary paper cost target: `dispatch_heat_operating_cost_eur`
    - component targets: `fuel_cost_eur`, `co2_cost_eur`, `variable_opex_eur`
    - carbon target: `co2_emissions_total_t`
    - ThermFlex behavior: shifted/additional/rebound heat and peak change
  - Avoid `dispatch_operating_cost_eur` and derived percent targets as primary
    paper learning targets because the net operating-cost value is affected by
    CHP/grid/electric-value terms and can be near zero or sign-sensitive.
  - Next implementation step:
    - build a duration-/tau-/family-aware season surrogate V2 that predicts
      absolute daily/window KPI components and aggregates them to week/season
      percent values only after summing the absolute reference/flex/delta values.
    - keep `upper_only`, `upper_lower_1k`, `upper_lower_2k`, duration and tau
      families explicit in features, split groups and reported validation slices.
    - validate against complete MILP season screens where available and against
      selected-window MILP anchors for the missing full-season cases.
  - Direct season-level system surrogate check is diagnostic only:
    - `build_main_table_season_surrogate_v2_tau4.py` showed that the current
      run-level system model does not cover the exact evt24 duration grid well
      enough for missing full-season table rows.
    - Do not use `table_main_season_surrogate_v2_tau4.*` rows marked
      `system_surrogate_v2_diagnostic_not_promoted` as paper values.
  - Next promoted route:
    - continue with the hourly-dispatch / daily-sum KPI family
      `fe23b4c1322061eb3f4d7f54084e840c7830bf784aad1453fcb9ce0fd9cecd49`.
    - use the oracle-load/daily-sum KPI contract for full-season table fills,
      because predicted-load end-to-end is still weak and not needed for the
      central season table.
    - build a season aggregation evaluator that predicts daily heat-cost/CO2
      deltas for the 212-day template per exact case and validates sums against
      complete V2 screens and selected-window MILP anchors.
  - Updated after tau4 oracle-dispatch coverage report:
    - `upper_only_dur24` and `upper_lower_1k_dur1_evt24` already have
      V2-compatible complete full-season MILP truth; do not replace these with
      surrogate values in the central season table.
    - Missing `upper+lower` duration rows cannot yet be promoted from the
      oracle-load dispatch model alone, because the current strong family has
      only `24-48` complete hourly oracle days per missing case.
    - Next practical step is to build or reuse a load/mechanism template for the
      missing 212-day case grids, then feed that into the already strong
      hourly-dispatch/daily-sum KPI model.
  - Updated after tau4 daily-anchor/checkpoint consolidation:
    - Keep using full V2 MILP truth for `upper_only_dur24` and
      `upper_lower_1k_dur1_evt24`.
    - For central full-season tau4 rows, the current promoted-candidate evidence
      strength is:
      - strong/near-complete: `upper_lower_2k_dur1_evt24` (`205/212` V2 days)
      - partial: `upper_lower_1k_dur4_evt24` (`161/212` V2 days)
      - weak/sparse: `upper_lower_1k_dur8_evt24` (`36` days),
        `upper_lower_1k_dur12_evt24`, `upper_lower_2k_dur4_evt24`,
        `upper_lower_2k_dur8_evt24`, `upper_lower_2k_dur12_evt24` (`22` days)
    - Before treating the weak/sparse season rows as paper values, either:
      - collect targeted V2 truth for the missing duration cases, preferably
        filling the same weather/month gaps rather than rerunning solved days, or
      - promote a stronger load/mechanism template with validation against the
        complete and near-complete cases.
    - Do not forget interrupted checkpoints in future learning inventories;
      they are valid reusable daily anchors when the row-level screen contract is
      compatible.
  - Updated after first targeted gap fills:
    - `upper_lower_2k_dur1_evt24` is now complete as merged V2 daily anchors
      (`212/212`).
    - `upper_lower_1k_dur4_evt24` is near-full (`181/212`) with `31` days still
      missing (`2023-11-24` to `2023-12-31`).
    - Next targeted truth priority:
      - `1K dur4` is now effectively complete (`211/212`); only `2023-12-24`
        is an explicit `maxTimeLimit` gap under the 900 s / 1% solve contract.
      - then choose whether to broaden sparse duration cases (`1K dur8/12`,
        `2K dur4/8/12`) by full-season runs or by a smaller stratified
        weather/month sample before relying on surrogate season fills.
  - Updated after long-duration tau4 skip-contract runs:
    - Current promoted-candidate coverage:
      - `1K dur4`: `211/212`, only explicit hard gap `2023-12-24`.
      - `1K dur8`: `142/212`, partial evidence.
      - `2K dur4`: `132/212`, partial evidence.
      - `2K dur8`: `123/212`, now partial evidence.
    - Next truth priorities:
      - continue `1K dur8` toward near-full if time allows, because its season
        cost/CO2 estimate changed materially when anchors were added.
      - start `1K/2K dur12`; these remain sparse and should not be treated as
        final paper-grade full-season rows without either more truth or explicit
        surrogate validation slices.
      - optionally continue `2K dur8` toward near-full after the dur12 cases
        have a comparable partial anchor basis.
      - keep the pragmatic skip contract for hard days; do not let individual
        max-time-limit dates block broad season coverage.
  - Updated after first duration-12 broadening:
    - `1K dur12`: `68/212`, still sparse but currently cheaper to solve.
    - `2K dur12`: `72/212`, still sparse and more uneven; keep small guarded
      blocks because some days approach or hit the `900 s` limit.
    - Next practical priority:
      - continue `1K dur12` in moderate chunks while it remains cheap.
      - add `2K dur12` only in smaller chunks or as stratified weather/month
        samples unless a longer overnight run is explicitly allocated.
  - Updated after central tau4 anchor broadening:
    - Long-duration rows are now promoted to at least partial evidence:
      - `1K dur8`: `142/212`
      - `1K dur12`: `134/212`
      - `2K dur4`: `147/212`
      - `2K dur8`: `135/212`
      - `2K dur12`: `123/212`
    - Keep using full/near-full MILP truth where available and use the daily
      anchor season aggregator as the promoted candidate for missing full-season
      table rows.
    - Next priority is not blind full-season MILP: add targeted daily truth for
      the weakest long-duration/2K gaps, especially shoulder/autumn days that
      materially shift cost, CO2, and rebound season estimates.
    - After the next truth block, rerun the season aggregation table and compare
      whether `2K dur8/12` and `1K dur12` estimates stabilize before using them
      as paper-grade central full-heating-period values.
  - Updated after additional shoulder/autumn truth broadening:
    - Current partial-anchor coverage:
      - `1K dur8`: `151/212`
      - `1K dur12`: `152/212`
      - `2K dur4`: `162/212`
      - `2K dur8`: `135/212`
      - `2K dur12`: `127/212`
    - For the next session, prioritize either:
      - pushing `2K dur8/12` upward with small guarded blocks, because they are
        still the thinnest 2K long-duration rows, or
      - switching from more truth to explicit uncertainty reporting for partial
        anchor rows if table production is more urgent.
    - Keep evidence labels in the central table; do not present partial rows as
      complete MILP truth.
  - Updated after weekend broadening start:
    - Current coverage:
      - `1K dur8`: `151/212`
      - `1K dur12`: `171/212`
      - `2K dur4`: `179/212`
      - `2K dur8`: `149/212`
      - `2K dur12`: `151/212`
    - Continue with small guarded blocks on `1K dur8`, `2K dur8`, and
      `2K dur12`; move to `2K dur4` only if the faster remaining days justify
      it, because new hard days have started to appear there too.
    - Rebuild `table_main_season_sparse_anchor_tau4.*` after each meaningful
      fill block and watch whether cost/CO2 percent deltas stabilize.
  - Updated after weekend queue broadening:
    - Current central tau4 long-duration anchor state:
      - `1K dur8`: `201` solved + `11` unresolved explicit failures.
      - `1K dur12`: `209` solved + `3` unresolved explicit failures.
      - `2K dur4`: `209` solved + `3` unresolved explicit failures.
      - `2K dur8`: `196` solved + `16` unresolved explicit failures.
      - `2K dur12`: `204` solved + `8` unresolved explicit failures.
    - No unknown missing dates remain for these rows under the current daily
      V2 anchor inventory; remaining gaps are the explicit `900 s` / `1%`
      solve-contract failures.
    - Next useful step is not more blind daily filling under the same contract.
      Either keep the current evidence-tagged near-full anchor rows, or decide
      explicitly whether hard failure days deserve a different solve contract
      before paper finalization.
    - Use the rebuilt `table_main_season_sparse_anchor_tau4.*` as the current
      promoted season-table candidate and keep evidence labels visible.
