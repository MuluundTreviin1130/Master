# Worklog

## 2026-05-19

### Thermflex: Main-Paper-Table Scope

- Main-Paper-Tabellenplan konsolidiert: zentrale Claims bevorzugt mit MILP-Truth, Surrogat primaer fuer breite tau-/duration-/month-/price-Sensitivitaeten.
- TODO ergaenzt: ca. 3-4 Main Tables, Performance-Tabelle fuer `best day`, drei Plot-Wochen und Heizperiode; separate Mechanismus-/Komfort-Tabelle; Surrogat-Validation mit R2 je KPI-/Family.
- Paper-facing Results-Notiz angelegt: `Documentation/Papers/thermflex_paper/results/07_main_table_scope.md`.
- Main-Table-Quellenmanifest angelegt: `Documentation/Papers/thermflex_paper/manifests/main_table_horizon_sources_tau4.csv`.
- Ersten schmalen Table-Builder angelegt und ausgefuehrt:
  `Documentation/Papers/thermflex_paper/tables/build_main_table_horizons_tau4.py`.
- Outputs im Tables-Ordner:
  - `table_main_performance_horizons_tau4.csv/.md`
  - `table_main_mechanism_horizons_tau4.csv/.md`
- Lower-2K `dur4 evt24` ergaenzt: vorhandener Screen
  `daily_thermflex_screen_lb20p5_dur4_evt24_20260513_partial` umfasst 92 Tage
  (`2023-01-01` bis `2023-04-09`) und wird in den Main Tables deshalb als
  `Available partial period`, nicht als volle Heizperiode, gefuehrt.
- Main-Table-Builder auf aktuelle Daily-Screens umgestellt: Performance-Tabelle
  liest Zeitraum, `n_days`, Kosten- und CO2-Deltas direkt aus den expliziten
  `heating_season_day_screen.csv`-Quellen; Best-Day bleibt als bester absoluter
  Kosteneinsparungstag definiert, weil Prozentdeltas bei nahe-null Referenzkosten
  instabil werden koennen.
- Aus den aktuell vorhandenen Truth-Artefakten ergibt sich:
  - `upper-only dur24` und `upper+lower 1K dur4` liegen als volle Heizperioden-Screens (`212` Tage) vor
  - `upper+lower 2K dur4` liegt aktuell nur als Partial-Screen (`92` Tage, `2023-01-01` bis `2023-04-09`) vor
  - fuer die staerkeren `lower 2K`-Effekte existieren zusaetzliche Chunk-/Target-Artefakte, aber noch kein sauberer Full-Heating-Period-Export fuer die Main-Tabelle
- Konkrete vorhandene tau4-Anker festgehalten:
  - `fig_15_upper_lower_relaxation_dispatch_response_tau4.csv` fuer die drei Plot-Wochen `December`, `February/March`, `April`
  - `fig_06b_cohort_duration_upper_lower_tau4.csv` fuer die Kohorten-/Duration-Mechanik

## 2026-05-16

### Review (surrogate modeling): ``Reviews zusammen.pdf`` → cite_key

- User merged review PDFs (959 pages, PDF24) at
  ``…\Review\Literatur\Reviews\Reviews zusammen.pdf``.
- Naive full-document DOI regex is **misleading** (reference lists add
  ~1000 DOIs); added ``paper_library/map_reviews_zusammen_pdf.py`` only
  as a diagnostic dump.
- Primary mapper: ``paper_library/map_reviews_zusammen_pdf_by_toc.py``
  uses PDF outline level-1 titles + **in-document title search** to find
  the true start page, then reads the first pages for the article DOI and
  matches ``review_paper_library.bib``.  Latest run: **14** unique
  DOI→cite_key pairs; **3** DOIs not in library / wrong first-page DOI;
  **1** title not found (BOM); several TOC entries are **section titles**
  not whole papers (listed in the report).
- Outputs: ``paper_library/reviews_zusammen_pdf_toc_map.{md,json}``;
  ``fulltexts/README.md`` documents the workflow.

## 2026-05-10

### Thermflex: Fig. 16 Duration-Sweep (MILP-Cache)

- Gecachter Punktläufe für Fig. 16 (Oktober–April, Durations 1/4/8/12 h): erster Hintergrundjob nach ~4.8 h **abgebrochen** (kein sauberer Exit; Log endete in April).
- Cache im Ordner `_fig_16_duration_performance_cache/`: vor Abbruch nahezu vollständig; **April** fehlten noch **dur4/dur8/dur12** (nur `apr_dur1` vorhanden).
- **Nachlauf** gestartet: `py -3 Documentation/Papers/thermflex_paper/figures/build_fig_16_flexibility_performance_map.py` (skipped bereits vorhandene Cache-Paare; ergänzt fehlende April-Fälle und rendert `fig_16_flexibility_performance_map.*`).
- **Zweiter Versuch** (~2026-05-10): nach ~**2,3 min** wieder **abgebrochen** (`exit_code unknown`); Log endete bei April-MILP (ThermFlex, Block 2/8). Cache **April** weiterhin nur `apr_dur1`; `dur4`/`dur8`/`dur12` fehlen. Empfehlung: gleichen Befehl **außerhalb** des IDE-Terminals (eigenes PowerShell-Fenster) laufen lassen, bis alle drei Fälle geschrieben sind, dann ggf. ohne MILP nur `--render-only`.
- **Dokumentation / Render:** `_fig_16_duration_performance_cache/README.md` listet die **gerechneten Monate** (Oktober–April, sieben Perioden) und Startdaten; `figures/README.md` Eintrag zu Fig. 16. Builder-Flag **`--allow-incomplete-duration-cache`** (nur mit `--render-only`): rendert bei fehlenden April-Durations mit **stderr-Warnungen** (Figur bis Nachrechnen der drei Fälle unvollständig). Ausgeführt: `… --render-only --allow-incomplete-duration-cache` → aktualisiert `fig_16_flexibility_performance_map.png` + `.csv`.

### Thermflex: Lower-relax `evt24` — CLI, SSOT-Overrides, Bundle

- **Screen** (`screen_vienna_constant_thermflex_heating_season_days.py`): CLI `--ref-override`, `--flex-override`, `--flex-label`, `--run-slug`; Ausgabe `gold/daily_thermflex_screen_<run-slug>_<timestamp>/` (Default `run-slug=dur24` liefert weiterhin `daily_thermflex_screen_dur24_*`).
- **Table 09** (`build_table_09_heating_season_kpis.py`): optional `--screen-csv` / `--output-md` / `--output-csv`; wenn nur `screen-csv` gesetzt, automatisch `table_09_*_<Screen-Ordnername>.md/.csv`. Ohne Argumente: neuester Ordner `daily_thermflex_screen_*` (nicht nur `dur24_`).
- **Acht Overrides** symmetrisch: 21.5 °C (**1.0 K**) und 20.5 °C (**2.0 K**) unter 22.5 °C × `max_flex_duration_h` 1/4/8/12, `max_flex_events_per_day=24`, Struktur von `upper_only dur24 evt24` geklont: Generator `Optimization/run/analysis/emit_symmetric_lower_relax_evt24_grid_overrides.py`, Dateien `…_lb21p5_dur*_evt24_paper_day_ahead.json`, `…_lb20p5_dur*_evt24_paper_day_ahead.json`.
- **Sammellauf** (8 volle Heizperioden-Screens + Table-09-Export): `Optimization/run/analysis/run_lower_relax_evt24_heating_season_kpi_bundle.py`.
- **Multi-Case KPI (Table‑09‑Layout pro Fall):** `Documentation/Papers/thermflex_paper/tables/build_table_tradeoff_extended_evt24_bundle.py` schreibt `table_tradeoff_extended_heating_season_kpis_evt24.md` + gestapelte CSV (+ Quellen-Manifest). **Hinweis:** `table_10_mechanism_*` im Repo bleibt die Mechanismus-Tabelle; Namenskonflikt im Paper bewusst im `tables/README.md` erklaert.
- **Pilot-Check:** `screen_vienna_constant_thermflex_heating_season_days.py --pilot-max-days 2` mit `lb21p5_dur4_evt24`: Diagnose `T_in` min ≈ 21.5 °C, max > 22.5 °C, Settings aus Payload wie erwartet (`exit_code 0`).
- **Bundle-Reparatur + Start:** `run_lower_relax_evt24_heating_season_kpi_bundle.py` importiert Table‑09‑Builder wieder per `sys.path` + normalem Import (wie `build_table_tradeoff_extended_evt24_bundle.py`), kein `importlib`-`exec_module` mehr (vorher `@dataclass`/`sys.modules`). Log-Ordner `Optimization/run/analysis/_runs/` angelegt (Tee-Path). **Großlauf** mit **`py -3 -u`** gestartet (Launcherreihenfolge: nicht `py -u -3`); Log z. B. `Optimization/run/analysis/_runs/lower_relax_evt24_bundle_*`.
- Aeltere manuelle Sweeps (`lb21p0_*`, `lb20p0_*` etc.) bleiben im Ordner; die neuen `lb21p5`/`lb20p5`+`evt24` sind die **exakten 1K/2K**-Relaxationen mit gleichem **evt24**-Budget wie der `upper_only`-Heizperioden-Screen.
- **Nicht verwechseln**: `build_constant_thermflex_sensitivity.py` nutzt `paper_dispatch_comparison.csv`, nicht den Heizperioden-Tages-Screen.

### Thermflex: Surrogat-Training Cache-Snapshot (Bundle-Stopp)

- **Ziel:** Keine Löschung der Gold-Screen-Daten; zusätzliche **Kopie** für Training/Archiv.
- **Pfad:** `Data/surrogate_training_cache/heating_season_thermflex_snapshot_20260511_bundle_stop/` mit `Vienna_gold_daily_thermflex_screens/` (alle `daily_thermflex_screen*` aus `Optimization/run/results/Vienna/gold` zum Snapshot-Zeitpunkt, **10** Ordner) und `thermflex_paper_tables_table09/` (`table_09*daily_thermflex_screen*.md/.csv`).
- **SSOT unverändert:** Originale bleiben unter `Optimization/run/results/Vienna/gold/`; siehe `SOURCES_manifest.txt` im Snapshot.
- Übergeordnet: `Data/surrogate_training_cache/README.md`.

### Review (surrogate modeling): Integration-Patterns Section — Zitations-Tabelle

- `Documentation/Papers/review_surrogate_modeling/tables/citations_sec_integration_patterns_key_doi_title_venue.md` + Builder `tables/build_citations_sec_integration_patterns_md.py` (`06_integration_patterns.tex`).

### Review (surrogate modeling): DOE-Section Zitations-Übersicht (Markdown-Tabelle)

- `Documentation/Papers/review_surrogate_modeling/tables/citations_sec_training_doe_key_doi_title_venue.md` — vier Spalten (Key, DOI, Titel, Verlag/Serie) für alle `\cite`-Keys in `manuscript/05_training_data_doe.tex`; Regenerieren: `tables/build_citations_sec_training_doe_md.py`. `tables/README.md` ergänzt.

## 2026-05-08

### Review-Paper: Inline-Tables-Regel + Section-PDF-Korpus-Workflow (User-Wuensche)

- User-Beobachtung: `\input{../tables/...}` in den Section-Files
  zerstoert den Overleaf-Compiler, weil das single-file
  Overleaf-Template `manuscript/main_overleaf_rser.tex` beim Pasten
  einer Section den Sibling-Ordner `tables/` nicht aufloesen kann.
- Hard rule eingefuehrt: kein `\input{../tables/...}` mehr in
  Section-Files. Tabellen muessen inline stehen, klar markiert mit

      % BEGIN inlined table <name>
      ... body ...
      % END inlined table <name>

  Die Tabellen-Dateien (`tables/table_T*.tex`) bleiben Single Source
  of Truth.
- Idempotenter Inliner gebaut:
  `tables/inline_tables_into_sections.py`. Erste Ausfuehrung
  konvertiert `\input{../tables/<name>}` zu BEGIN/END-Region; alle
  weiteren Ausfuehrungen synchronisieren den Body zwischen den
  Markern mit dem aktuellen Tabellen-Inhalt. Zwei Re-Runs auf
  dasselbe File sind safe.
- Inliner-Lauf gegen alle Section-Files ersetzt 8 \input-Calls in 6
  Dateien: `02_related_reviews.tex` (T7+T8),
  `04_taxonomy_surrogates.tex` (T1), `05_training_data_doe.tex`
  (T3), `06_integration_patterns.tex` (T2+T5),
  `07_validation_decision_aware.tex` (T4), `appendix.tex` (T6).
  Re-Run zeigt 0 \input + 8 BEGIN/END resyncs (idempotent).
- READMEs aktualisiert: `manuscript/README.md` und `tables/README.md`
  enthalten jetzt die Hard-Rule + Inliner-Workflow.
- Workflow-TODO eingetragen: pro First-Level-Section eigenen
  PDF-Volltext-Korpus aufbauen
  (`paper_library/fulltexts/by_section/<sec>/`), damit der Agent
  Aussagen analog zum T8-Verify-Workflow gegen Volltext pruefen
  kann. Empfohlene Reihenfolge: Sektion 4 (Taxonomy), 6
  (Integration Patterns), 7 (Validation), 8 (Applications).

### Review-Paper: T8 Software-Tabelle PDF-verifiziert (verify-Pipeline + auto-builder)

- User wies darauf hin, dass die Inline-Cites in T8 (``Primary use''-
  Spalte) nicht aus den PDFs verifiziert sind. Initiale Tabelle hatte
  Cite-Pairings basierend auf plausibler Inferenz -- nicht aus PDF-
  abgeglichenem Text. Korrekt: jedes Pairing muss durch eine PDF-
  Mention belegt sein.
- Verify-Pipeline gebaut: `paper_library/verify_T8_software_cites.py`
  - extrahiert Volltext aus allen 31 PDFs in `paper_library/fulltexts/`
    via PyMuPDF (fitz), Fallback auf pypdf.
  - Encoding-Fix: in-process Extraktion statt subprocess, weil Windows
    cp1252-stdout das `\u2217`-Zeichen nicht encoden kann.
  - 49 Software-Tools in der Suchliste mit Alias-Patterns (wort-
    grenzen-strikte Regex). Spezielle Disambiguation fuer ``TIMES''
    (englisches Wort vs. IEA-ETSAP-Modell): Context-Match auf
    ``TIMES <model|framework|tool|database|...>`` oder
    ``MARKAL[-/\s]TIMES`` oder ``IEA[-\s]TIMES``.
  - Output: `paper_library/verify_T8_software_cites.out.txt`,
    listet pro Paket die Cite-Keys aller Reviews, deren Volltext
    es explizit nennt.
- Ergebnis der Verifikation:
  - Hard-belegt (>=1 PDF-Mention): scikit-learn (4), XGBoost (3),
    LightGBM (2), TensorFlow (2), PyTorch (3), SMT (2), GPy (1),
    GPyTorch (1), botorch (1), GAMS (5), Gurobi (2), CPLEX (4),
    Mosek (2), IPOPT (2), BARON (1), PyPSA (1), oemof (1),
    Calliope (1), OSeMOSYS (2), HOMER (9), TIMES (2), MARKAL (3),
    REMix (2), EnergyPlus (3), TRNSYS (6), Modelica/Dymola (2),
    MATLAB (13).
  - 0 PDF-Mentions: Keras, JAX, scikit-optimize, emukit, chaospy,
    OpenTURNS, SALib, Modulus, DeepXDE, pymoo, DEAP, PyGMO,
    Platypus, pyDecision, AMPL, Couenne, Pyomo, JuMP, CVXPY,
    GenX, PowerModels.jl. Davon nicht-essentielle 12 Tools
    (scikit-optimize, emukit, SALib, PyGMO, Platypus, AMPL,
    Couenne, GenX, PowerModels.jl) gestrichen; essentielle 8
    Tools (Keras, JAX, chaospy, OpenTURNS, Modulus, DeepXDE,
    pymoo, DEAP, pyDecision, Pyomo, JuMP, CVXPY) als
    common-knowledge-Eintraege behalten und mit ``--$^\dagger$''
    plus Footnote markiert.
- T8 deterministisch neu gebaut via
  `tables/build_table_T8_software_packages.py`:
  - statisches Pkg-Definitions-Dict (label, block, language, gpu,
    dl, maint, primary_use)
  - parsed `verify_T8_software_cites.out.txt`, fuegt Cite-Keys in
    neue Spalte ``Sources'' ein (oder ``--$^\dagger$''+ footnote)
  - schreibt `tables/table_T8_software_packages.tex` plus
    `paper_library/software_landscape.csv` (mit confidence-Flag
    high/ck pro Paket).
- T8 hat jetzt 38 Pakete (vorher 49) in 5 Bloecken; Caption macht
  Verify-Workflow explizit; jede Cite-Cell ist PDF-belegt.
- `manuscript/02_related_reviews.tex` Software-Subsection
  umgeschrieben: zitiert Bhosekar2018 §7 explizit, listet die
  konkreten Klemm2021-Tool-Namen (PyPSA, oemof, Calliope, OSeMOSYS,
  TIMES, MARKAL, REMix), erklaert den Verify-Workflow, fuegt
  drittes strukturelles Muster hinzu (HOMER/MATLAB/GAMS dominanz
  vs.\ pymoo/DEAP/pyDecision Null-Mentions als quantitative
  Bestaetigung der ``algorithm-axis-without-software-axis''-Gap).
- Library rebuild: 285 mandatory keys (unveraendert, weil die
  belegten Cites alle schon ueber T7/Section02 mandatory waren).
  T6 nicht regeneriert (keine Library-Aenderung).

### Review-Paper: Zhang2026 (Energy & Buildings 2026, AI surrogate + MOO + MCDM in building design) nachgereicht

- User stellte zusaetzliches PDF bereit
  (`1-s2.0-S0378778826002987-main.pdf`, Energy & Buildings 358:117238,
  DOI 10.1016/j.enbuild.2026.117238). Inhalt: Systematic review of
  114 Studien zu AI surrogate fuer parametric optimization in
  sustainable building design; deckt fuenf Workflow-Dimensionen
  (parametric simulation, dataset construction, surrogate model
  state-of-the-art, optimization-algorithm selection, MCDM for
  design-scheme selection); identifizierte Gaps: limited DL
  exploration, surrogate interpretability, uncertainty handling,
  block-scale decarbonisation.
- Eintrag `Zhang2026_building` in `references/external_reviews.bib`
  ergaenzt; Bibliography-Rebuild liefert 2921 Eintraege (vorher 2920),
  15 davon mit Source `external_reviews`.
- Tabelle T7 in Surrogate-Methodology-Block um Zhang2026_building
  erweitert (jetzt 14 surrogate-side reviews); Caption / Header /
  ``thirty-one'' -> ``thirty-two'' aktualisiert.
- `manuscript/02_related_reviews.tex` Surrogate-Methodology- und
  Synthesis-Subsections um Zhang2026_building erweitert: dezidierter
  Abschnitt im Building-Subcluster (Westermann-Elwy-Zhang) mit den
  vier Gaps die Zhang nennt; Synthesis-Block-Cite-Liste fuer
  AI-MOO-MCDM-coupling erweitert.
- `paper_library/select_paper_library.py` Re-Run: Library waechst
  auf 285 Mandatory-Cites (vorher 284), B01_cornerstone_reviews auf
  32 (vorher 31). T6 Evidence-Map regeneriert (285 Reihen).
- `paper_library/fulltexts/README.md` Cite-Key-Mapping um
  `Zhang2026_building` -> `1-s2.0-S0378778826002987-main.pdf` ergaenzt.

### Review-Paper: 14 neue Reviews aus User-PDFs eingearbeitet, T7 auf 31 Reihen erweitert, Software-Tabelle T8 erstellt

- User stellte 31 heruntergeladene Review-PDFs unter
  `C:\Users\Philipp Thunshirn\Desktop\PhD\Papers\Journals\Review\Literatur\Reviews`
  bereit. Per Identifikations-Reads (erste 30-50 Zeilen) gemappt:
  17 sind bereits in der Bibliography (T7 v2-Entries), **14 sind
  neu** und fielen ausserhalb des Scopus-Suchstring-Keyword-Cones
  (z.B. Comp. Chem. Eng., Comp. Intelligence and Neuroscience,
  Mathematik-Journals, MCDM-Venues).

- Neue Reviews als externe Quelle in die Pipeline integriert:
  - `references/external_reviews.bib` mit 14 BibTeX-Eintraegen
    (Bhosekar2018, Westermann2019, Manco2024, Fattahi2020, Klemm2021,
    Li2025_hydrogen, Khan2024_DT, DiazManriquez2016,
    FernandezGodino2023, Sahoo2025, Etghani2025, Mohammadi2024,
    ChenRenZhou2023, Elwy2024). Jeder Eintrag aus dem PDF
    abstract-verifiziert.
  - `references/build_review_bibliography.py` um neuen
    `--extra-bib`-Argparser-Eintrag erweitert; default zeigt auf
    `external_reviews.bib`. Pool-Source-Tag: `external_reviews`.
  - Bibliography-Rebuild liefert 2920 Eintraege (vorher 2906),
    14 davon mit Source `external_reviews`.

- Tabelle T7 (Meta-Review related reviews) auf 31 Reihen + ``This
  work''-Zeile erweitert, in vier Bloecke gegliedert:
  - **Surrogate methodology (13 Reihen)**: Bhosekar2018,
    DiazManriquez2016, FernandezGodino2023, Westermann2019,
    Mohammadi2024, Tan2026, Khan2024_DT, Khaloie2025, Lim2025,
    Starke2025214, Ruan2021221, Elsheikh2019622, Elwy2024.
  - **MES-domain reviews (8 Reihen)**: Mylonopoulos202332697,
    Manco2024, Klemm2021, Fattahi2020,
    agha_kassab_comprehensive_2024, nallolla_multi-objective_2023,
    malla_sg_optimization_2024, Li2025_hydrogen.
  - **MOO und MCDM methodology (4 Reihen)**: ChenRenZhou2023,
    salgueiro_multi-objective_2019, Sahoo2025, Etghani2025.
  - **ESM-optimization und Bibliometric (6 Reihen)**: Zhou2024__2,
    vahidinasab_overview_2020, Conti2026, arar_tahir_scientific_2023,
    batista_optimizing_2023, velasquez_intelligence_2023.

- `manuscript/02_related_reviews.tex` komplett umgeschrieben mit
  konkreten Inhaltsangaben pro Block (was wurde gemacht), expliziten
  identified gaps pro Block, Synthesis-Subsection mit drei
  Beobachtungen (was bisher gemacht / was fehlt / interessante
  Cross-Review-Aspekte) plus neuer Subsection
  ``Software-package landscape'' die Tabelle T8 einfuehrt.

- Neue Tabelle T8 (`tables/table_T8_software_packages.tex`):
  Software-Package-Landschaft fuer Surrogate / MOO+MCDM / Solver /
  Energy-System-Specific. Spalten Package, Language, GPU, DL,
  Maintenance, Primary use. 36 Packages in fuenf Bloecken:
  General-Purpose ML (7), Surrogate-Specific (12), MOO + MCDM (5),
  Solver + Modelling (7), Energy-System-Specific (12). Jeder Eintrag
  zitiert mindestens eine T7-Quelle, die das Package belegt.

- `paper_library/select_paper_library.py` re-run liefert jetzt
  284 mandatory keys (vorher 270): die 14 neuen Reviews aus T7 plus
  alle T8-Software-Cite-Keys. Bucket B01_cornerstone_reviews waechst
  von 18 auf 31. Library-Bib enthaelt alle 14 neuen Reviews;
  Cite-Coverage ist vollstaendig (5 Scopus-Keys mit Spaces wie
  ``El Mestari2025'' sind bereits in der vorherigen Iteration
  korrekt eingebaut, das Verify-Skript-Issue war ein Regex-Bug).

- T6 Evidence-Map regeneriert via
  `tables/build_table_T6_evidence_map.py` (284 Reihen).

- `paper_library/fulltexts/`-Ordner angelegt mit ASCII-Kopien der
  31 PDFs (Mapping in `fulltexts/README.md` dokumentiert) plus
  `.gitignore` (PDFs werden nicht versioniert).

- `manuscript/main_overleaf_rser.tex` Section-02-Header-Comment
  aktualisiert: listet jetzt die sechs Subsections auf (inkl. neuer
  Software-package-landscape-Subsection mit T8).

- Open Issue: `B99_misc` zaehlt 1 Eintrag, der nicht in den 22
  thematischen Buckets gelandet ist; in einem spaeteren Pass
  pruefen, ob ein Bucket-Pattern fehlt oder ob der Eintrag eine
  Meta-Review-Zelle braucht.

## 2026-05-07

### Review-Paper: Sektionen 4-9 + Appendix ausformuliert, Library auf Submission-Niveau gecleaned

- Sektionen 4-9 plus Appendix komplett ausformuliert; bewusst formal-
  wissenschaftlicher Stil mit klassifikatorischen Topic Sentences,
  dichten Cite-Blocks am Satzende und sparsamem `we`. Auf den
  verengten Scope (Surrogates x MOO x MES) konsequent zugeschnitten.
  - `manuscript/04_training_data_doe.tex` -- Datenquellen, statische
    Designs (LHS, Sobol, factorial), adaptive Sampling / Active
    Learning, Multi-Fidelity, energy-data-spezifische Pitfalls.
  - `manuscript/05_integration_patterns.tex` -- Fuenf-Pattern-
    Klassifikation (P1 Replace, P2 Accelerate, P3 Warm-Start,
    P4 Decompose, P5 Uncertainty); cross-cutting framework.
  - `manuscript/06_validation_decision_aware.tex` -- Sechs
    Diagnostik-Klassen (Point/Interval, Feasibility, Decision-Aware,
    Stress-Tests, OOD, Reproducibility); argumentiert RMSE -> Regret.
  - `manuscript/07_application_evidence_map.tex` -- Pro
    Anwendungsdomaene (ED/UC, OPF, CapEx, DH, MES, MG/Hub, MOO-Design,
    Stoch/Robust) dominante Pattern + Cites + Speedup-Metriken;
    Synthesis-Subsektion am Ende.
  - `manuscript/08_open_challenges.tex` -- Sechs konkrete
    Forschungsrichtungen (Decision-Aware Benchmarks, Calibrated UQ,
    OOD across capacity mixes, Public Datasets, MCDM under
    Surrogate Uncertainty, Open-Source Tooling).
  - `manuscript/09_conclusion.tex` -- Drei beobachtete Patterns
    (grosse Speedups, schlecht dokumentierte Decision-Quality,
    aktivste MOO-MES-Domaene); knappe Klammer.
  - `manuscript/appendix.tex` -- Search Strategy + Screening
    Pipeline + Run-Statistiken + Verweis auf Evidence Map.

- BibTeX-Cleaner in `paper_library/select_paper_library.py`:
  - Whitelist erlaubter BibTeX-Felder, Content-Filter fuer `url`
    (drop wenn `scopus.com`) und `note` (drop wenn `cited by` /
    `open access`).
  - Source-Pool (`references/review_mes_moo_surrogates.bib`) wird
    nicht angetastet; Cleanup nur beim Schreiben des Library-Bib.
  - Run-End-Summary listet abgezogene Felder auf -- aktueller Lauf:
    260 url:scopus, 246 note:scopus, 246 type/source/publication_stage,
    235 author_keywords, 1 annotation gestrippt.
  - LaTeX-Kommentar-Aware Mandatory-Scan ergaenzt, damit
    `\cite{...}`-Beispiele in `%`-Kommentaren nicht als
    Pflicht-Cites zaehlen.

- Library-Rebuild nach Sektionen 4-9:
  - 233 Mandatory-Cites (aus allen Sektionen 1-9 + Appendix) gegen
    `review_mes_moo_surrogates_manifest.csv` validiert.
  - 260 Library-Eintraege (233 Mandatory + 27 Top-Up) in
    `paper_library/review_paper_library.bib`.
  - Voll-Coverage-Check: 233 zitierte Keys -> 0 missing.

- Uebersichtstabellen T1-T6 befuellt:
  - T1 (Taxonomie), T2 (Task x Role-Matrix), T3 (Training/DoE),
    T5 (Integration Patterns) inhaltlich gefuellt mit Cite-Blocks
    aus der curated paper library.
  - T4 (Validation) zuvor ohne Cite-Refs; jetzt nachgezogen, sodass
    jede Metrik / jeder Test-Design-Eintrag 2-5 representative
    Cites hat (Standard-Metriken, Decision-Aware-Metriken,
    Test-Designs).
  - T6 (Evidence Map) als deterministischer Auto-Builder umgesetzt:
    `tables/build_table_T6_evidence_map.py` liest
    `paper_library/review_paper_library_manifest.csv`, mappt jeden
    Eintrag ueber das Bucket-Schema auf Surrogat-Familie, Task-Klasse
    und Integration-Pattern und schreibt 260 longtable-Zeilen
    (sortiert year DESC, citations DESC, key) in
    `tables/table_T6_evidence_map.tex`.
  - Tabellen sind wie die Sektionen 4-9 abstract-/metadatengestuetzt
    und brauchen denselben Volltext-Audit vor Submission (siehe
    `Planning/TODO.md`, "Volltext-Verifikation").

- Meta-Review-Sektion und Tabelle T7 ergaenzt:
  - Neue Sektion `02_related_reviews.tex` zwischen Introduction und
    Background; positioniert die Arbeit gegen 10 cornerstone reviews
    aus B01 entlang vier Scope-Achsen (Methoden, Anwendungen, MOO,
    MES) plus Decision-Aware-Validation.
  - Neue Tabelle `tables/table_T7_related_reviews.tex`
    (Meta-Review-Tabelle): pro Review Method-Scope, Application-
    Scope, MOO/MES/DA-val-Indikatoren, Time-Window und Gap-Spalte;
    abschliessende "This work"-Zeile macht den Beitrag explizit.
  - Drei Argumentationslinien in der Sektion: kein bisheriger Review
    deckt die Surrogates x MOO x MES-Schnittmenge ab, kein Review
    nutzt Integration Patterns als Organisationsprinzip, kein Review
    macht Decision-Aware-Validation zum strukturierten Protokoll.

- Sektionsdateien renumeriert, damit Filename-Order und LaTeX-
  Section-Order wieder uebereinstimmen:
  - `02_background_optimization_in_esm.tex` -> `03_background_...`
  - `03_taxonomy_surrogates.tex` -> `04_taxonomy_surrogates.tex`
  - `04_training_data_doe.tex` -> `05_training_data_doe.tex`
  - `05_integration_patterns.tex` -> `06_integration_patterns.tex`
  - `06_validation_decision_aware.tex` -> `07_validation_decision_aware.tex`
  - `07_application_evidence_map.tex` -> `08_application_evidence_map.tex`
  - `08_open_challenges.tex` -> `09_open_challenges.tex`
  - `09_conclusion.tex` -> `10_conclusion.tex`
  - `main.tex` und `main_overleaf_rser.tex` entsprechend angepasst.

- Library-Rebuild + Cite-Coverage-Check nach den Tabellen- und
  Sektion-2-Updates:
  - 234 Mandatory-Cite-Keys aus 11 Sektionsdateien + 7 Tabellen.
  - Rebuild liefert 260 Library-Eintraege (alle Mandatory-Cites
    aufgeloest, kein Eintrag mehr nicht-zitiert).
  - T6-Auto-Builder neu ausgefuehrt: 260 Zeilen aktualisiert.

### Review-Klassifikator + T7-Erweiterung auf 17 verifizierte Reviews

- Strikten Review-Klassifikator als reproduzierbares Audit-Werkzeug
  unter `references/scan_review_candidates.py` angelegt:
  - Drei Signalquellen pro Eintrag: Title (regex auf eindeutige
    Marker wie `:\s*a review`, `comprehensive review`, `literature
    review`, `bibliometric (analysis|review|mapping)`,
    `scientific mapping`, `state-of-the-art`, `survey of/on`,
    `meta-analysis`, `overview of`), Abstract (Phrasen wie
    `this paper presents a review`, `we survey`, `bibliometric
    analysis`, `purpose of this review`), und Author/Index Keywords
    (`review`, `literature review`, `bibliometric`, `survey`,
    `state-of-the-art`).
  - Domain-Tagging der Treffer in {surrogate, moo, mes, esm_opt,
    off_topic} ueber Schluesselwortlisten; off-topic-Treffer (AUVs,
    Diesel-Engines, Heat-Wave-Building-Studies) werden gefiltert.
  - Trennt strict (>=2 Signale ODER unzweideutiges Title-Pattern) von
    weak (genau 1 Signal aus Abstract/Keyword) und sortiert beide nach
    Citations und Jahr; aktueller Pool 2906 Eintraege ergibt 22
    strict + 10 weak Treffer in scope.

- Manueller Abstract-Audit der bisherigen T7-Eintraege ergab drei
  Falsch-Klassifikationen (`Xiao2018` "Application and comparison",
  `Cao2023` "preliminary study", `Perera2019191` Methodenstudie mit
  surrogate-assisted Pareto-Search); diese drei Zeilen aus T7
  entfernt. Library-Eintraege bleiben (sie werden weiter in den
  Methoden-/Anwendungs-Sektionen zitiert), aber sie sind keine
  Reviews.

- T7 von 10 auf 17 verifizierte Reviews erweitert, gruppiert in
  vier Bloecke:
  - Surrogate-side (6): `Tan2026` (GP in power systems),
    `Khaloie2025` (ML-OPF), `Lim2025` (DL power decision),
    `Starke2025214` (energy metamodel), `Ruan2021221` (ML-power
    optimization), `Elsheikh2019622` (ANN solar).
  - MES-domain (4): `Mylonopoulos202332697` (ship MES),
    `agha_kassab_comprehensive_2024` (microgrid sizing/EMS),
    `nallolla_multi-objective_2023` (MOO hybrid AC/DC microgrid),
    `malla_sg_optimization_2024` (MES Power-to-X).
  - MOO-methodology (1): `salgueiro_multi-objective_2019` (MOO
    metaheuristics microgrid).
  - ESM-optimization + bibliometric (6): `Zhou2024__2` (storage
    sizing SOTA), `vahidinasab_overview_2020` (distribution
    expansion planning), `Conti2026` (PV smart distribution),
    `arar_tahir_scientific_2023` (bibliometric microgrid mapping),
    `batista_optimizing_2023` (HRES MOO bibliometric, RSER),
    `velasquez_intelligence_2023` (decade bibliometric AI x SE).
  - Sektion `02_related_reviews.tex` umgeschrieben mit
    Block-Paragraphen (Surrogate-side, MES-domain, MOO-methodology,
    ESM-optimization + bibliometric); drei strukturelle
    Beobachtungen am Ende verdichten die Gap-Argumentation.

- `select_paper_library.py`: `collect_mandatory_cites` scannt jetzt
  zusaetzlich zu `manuscript/*.tex` auch `tables/*.tex`, damit
  Cite-Keys, die ausschliesslich in T7 (oder anderen Tabellen)
  zitiert werden, automatisch als mandatory eingelesen werden.

- Library-Rebuild nach T7-Erweiterung:
  - Mandatory-Cite-Keys: 234 -> 270 (+10 durch neue T7-Reviews +
    weitere durch Abstract-Adds in Sektion 2).
  - Library: 260 -> 270 Eintraege; alle 17 T7-Reviews sind in der
    Library und im Manuscript zitiert (verifiziert via
    `_t7_check.py`, danach geloescht).
  - T6 Auto-Builder neu ausgefuehrt: 270 Zeilen.
  - B01_cornerstone_reviews-Bucket: 14 -> 18 Eintraege (Xiao2018,
    Cao2023, Perera2019191 bleiben aus historischen Gruenden in B01,
    werden aber nicht mehr in T7 gefuehrt).

Naechste Schritte:
- Sektionen 1, 3 (Background) und 4 (Taxonomy) stilistisch noch
  enger auf den Surrogates x MOO x MES-Scope zuschneiden.
- Cornerstone-PDFs (96 high-priority OpenAlex-Hits) ueber
  Zotero/Uni-Proxy beschaffen; Volltext-Audit gem. TODO-Item
  "Volltext-Verifikation" durchfuehren.

## 2026-05-05

### Review-Paper "Surrogate modeling in energy system modeling" aufgesetzt

- Neuen Paper-Ordner `Documentation/Papers/review_surrogate_modeling/`
  mit Sub-Layer (`manuscript/`, `references/`, `references/raw/`,
  `tables/`, `figures/`, `appendix/`) angelegt; jeder Layer hat ein
  eigenes README, das Zweck und Konventionen festhaelt.
- Forschungsfrage und Scope abgestimmt: methodische + anwendungsbezogene
  Uebersicht ueber Surrogatmodellierung in der Energiesystemmodellierung
  ueber Power, DH und MES, inkl. Dispatch, Capacity Expansion,
  multikriterielle Optimierung und Stochastik/Robustheit; ROM und reine
  Forecasting-Anwendungen sind explizit ausgeschlossen.
- Roh-Scopus-Export (3129 Eintraege, Zeitfenster 2016-2026) liegt unter
  `references/raw/scopus_export_2026-05-05.bib` und ist read-only SSOT.
- Offline-Filter `references/filter_bib.py` implementiert; klassifiziert
  Eintraege in Tier A (1270 Eintraege, expliziter Surrogat-Begriff +
  ESM-Kontext), Tier B (154 Kandidaten, implizite Surrogatnutzung) und
  rejected. Die Logik ist in `references/screening_log.md` dokumentiert.
- Anreicherungspipeline `references/enrich_openalex.py` ergaenzt OA-Status,
  freie PDF-URLs, Zitationszahl, primary_topic und eine
  Read-Priority-Spalte (high / medium / low) in
  `references/surrogates_esm_screening_enriched.csv`. 1205 von 1270 Tier-A-Eintraegen
  haben einen OpenAlex-Match; 246 sind Open Access, 96 high-priority
  Cornerstone-Refs (Reviews oder >=50 Zitationen).
- Auswahlhilfe `references/select_citations.py` listet pro Bucket
  (Surrogat-Familie und ESM-Task) die meistzitierten Tier-A-Eintraege.
- LaTeX-Skelett (Elsevier `elsarticle`, `bibtex` mit `elsarticle-num`)
  aufgesetzt: `manuscript/main.tex` plus 9 Sektionen plus Appendix plus
  Tabellen-Stubs T1-T6 unter `tables/`.
- Erste drei Sektionen (Introduction, Background, Taxonomy) ausformuliert
  mit insgesamt 483 `\cite{}`-Aufrufen ueber 103 unique Keys, alle gegen
  `references/surrogates_esm.bib` validiert (keine Spaces, keine
  Non-ASCII-Keys, keine Missing-Keys).
- Zotero-Plugins `Better BibTeX`, `Zutilo`, `Better Notes` als XPI nach
  `Downloads/zotero_plugins/` heruntergeladen, fuer manuelle Installation
  im Zotero-Plugin-Dialog.
- Spaeteren MOO-/Multicriteria-Export aus
  `Downloads/Exportierte Einträge MOO multicriteria/` als
  `references/raw/moo_multicriteria_scopus_export_2026-05-06.bib`
  gesichert. Import-Skript `references/import_moo_multicriteria_export.py`
  erzeugt daraus 2369 Screening-Zeilen; davon 1651 `moo_mes` und 23
  `moo_mes_surrogate`.
- Kombinierte Review-Bibliografie `references/review_mes_moo_surrogates.bib`
  mit `references/build_review_bibliography.py` gebaut: 2944 Input-Eintraege,
  2906 DOI-/Key-deduplizierte Eintraege, 0 doppelte Cite-Keys nach
  deterministischem Suffixing; Manuskript zeigt nun auf diese kombinierte Bib.
- Manuskripttitel und Abstract auf den verengten Scope
  "surrogate models for multi-objective optimization of multi-energy systems"
  angepasst.
- Review-Figuren auf Basis der gemergten Bibliografie neu aufgebaut:
  - `figures/build_review_figures.py` generiert Fig. 1, 3, 4 und 6 als
    PNG/PDF.
  - Fig. 1 ist ein PRISMA-aehnlicher Workflow fuer den zweigleisigen
    Literaturprozess (Surrogate-ESM + MOO/MES-Export).
  - Fig. 2 (Pareto-Front aus altem Draft) wird bewusst nicht uebernommen.
  - Fig. 3 wurde als konzeptuelle MES-Grafik neu gezeichnet.
  - Fig. 4 nutzt die gemergte Bibliografie fuer Jahresentwicklung,
    Top-Venues, Source-Komposition und Outlet-Familien.
  - Fig. 6 ist eine VOSviewer-aehnliche, reproduzierbare
    Keyword-Co-Occurrence-Landkarte; da kein VOSviewer-Export vorliegt,
    basiert sie auf kontrollierten Termen aus Title/Abstract/Keywords.
- Bibliometrische Excel-Artefakte fuer manuelle Abbildungen erzeugt:
  - `figures/bibliometric_data_review_mes_moo_surrogates.xlsx` mit
    Rohrecords, Yearly Counts, Source Counts, Top Venues, Outlet-Familien
    und Keyword-Terms.
  - `references/enrich_openalex_countries.py` nutzt OpenAlex-Authorships,
    um fehlende Laenderdaten aus DOI-Metadaten zu ergaenzen.
  - Country-Enrichment-Ergebnis: 2700/2906 Records mit OpenAlex-Match,
    2554/2906 mit mindestens einem Country-Code, 97 Laender.
  - Exportiert nach `figures/openalex_country_data.xlsx`,
    `figures/openalex_country_counts.csv` und
    `figures/openalex_country_records.csv`.
- Weltkarten fuer Country-Bibliometrik erzeugt:
  - `figures/build_openalex_country_map.py` nutzt
    `openalex_country_counts.csv` und Natural Earth 110m-Geometrien
    (Cache: `figures/_natural_earth/`).
  - Outputs: `fig_04_country_map_full_count`, `fig_04_country_map_fractional_count`
    und `fig_04_country_map_first_author_count` jeweils als PNG/PDF.

Naechste Schritte:
- Sektionen 4-9 (DoE, Integration Patterns, Validation,
  Applications, Open Challenges, Conclusion) ausformulieren.
- T6-Builder-Skript schreiben, das `surrogates_esm_screening_enriched.csv`
  in eine LaTeX-`longtable` exportiert.
- Tier-B-Kandidaten manuell sichten und Top-Kandidaten in Tier A heben.
- Better BibTeX nach Installation auf stabile Citation-Keys umstellen,
  damit Eintraege mit Diakritika oder Leerzeichen kein Risiko mehr sind.

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
  - standardisierten hourly transition dataset builder im `Learning/`-Layer vorbereiten
  - `Technical_model` bleibt auf EnergyPlus-Teacher und kanonische physikalische Exporte beschraenkt
  - `Learning` uebernimmt Feature-/Target-Aufbereitung, Dataset-Store, Training, Validation und Artefakte fuer den Building-Surrogate-Pfad
  - harte Validierung der Pflichtspalten einbauen
  - danach erstes Multi-Target-Building-Surrogat im bestehenden Learning-Layer trainieren und ueber 24/48h-Rollouts pruefen
- Ersten Layer-2-Dataset-Baustein umgesetzt:
  - `Learning/building_response/README.md`
  - `Learning/building_response/schema.py`
  - `Learning/building_response/build_transition_dataset.py`
- Der Builder liest `teacher.meta.json` und `teacher_plausibility_hourly.csv` aus dem bestehenden EnergyPlus-Teacher-Pfad und schreibt ein ML-ready Transition-CSV:
  - `state_t + weather_t + controls_t + cohort_context -> state_t+1 + q_heat_t + heat-balance diagnostics`
- Smoke mit zwei realen Teacher-Runs ausgefuehrt:
  - Output: `Learning/datasets/building_response_v1_smoke/building_response_teacher_hourly.csv`
  - Ergebnis: 46 Transition-Zeilen aus 2 Teacher-Runs
- Full-Dataset-Build auf alle vorhandenen geeigneten Teacher-Runs ausgefuehrt:
  - Output: `Learning/datasets/building_response_v1/building_response_teacher_hourly.csv`
  - Ergebnis: 7008 Transition-Zeilen aus 96 Teacher-Runs
  - Abdeckung:
    - 8 Kohorten
    - 12 Experimente
    - `reference` und `free_float`
    - direkte Air-Path-Spalten im kombinierten Dataset vorhanden
- Aktuelle V1-Spalten nutzen die vorhandenen Teacher-Exports:
  - `T_in`, `T_in_next`, `q_heat`, Aussentemperatur, Setpoint, Fenster-/Solar-Gewinne, interne Gains, approximierte Infiltration/Ventilation und EPW-Irradiance
  - direkte neuere `teacher_*`-Air-Path-Spalten werden bereits optional erkannt und im Full-Dataset mitgefuehrt, sobald sie im Teacher-Export vorhanden sind
- Ersten Multi-Target-Trainings-/Validierungsprototyp umgesetzt:
  - `Learning/building_response/train_transition_model.py`
  - Output: `Learning/models/building_response_v1/`
  - Modell: `RandomForestRegressor`, bewusst single-process (`n_jobs=1`) wegen Windows/Sandbox und token-/ressourcensparsamer Prototypik
- Wichtige Korrektur im Schema:
  - Heat-Balance-Fluesse wie Solar/Fenster/Infiltration/Ventilation sind Targets/Diagnostics
  - sie werden im V1-Modell nicht gleichzeitig als Inputs verwendet, um Target-Leakage zu vermeiden
- Erster gruppierter Teacher-Run-Holdout:
  - 7008 Zeilen gesamt
  - 5828 Trainingszeilen
  - 1180 Testzeilen
  - 76 Train-Teacher-IDs
  - 20 Test-Teacher-IDs
- One-step-Metriken:
  - `t_in_next_c`: MAE 0.117 C, RMSE 0.338 C, R2 0.986
  - `zone_total_heating_kwh`: MAE 0.825 kWh, RMSE 1.664 kWh, R2 0.926
  - Solar/Fenster/Internal-Gain Targets liegen im One-step-R2 grob bei 0.94-0.97
  - approximierte Infiltration/Ventilation sind schwacher, aber noch brauchbar (`R2` ca. 0.84 / 0.82)
- Rekursive Rollout-Metriken:
  - 24h: `T_in` MAE 0.241 C, RMSE 0.851 C; `q_heat` MAE 1.265 kWh
  - 48h: `T_in` MAE 0.507 C, RMSE 1.490 C; `q_heat` MAE 1.170 kWh
  - Interpretation: One-step ist stark, rekursiver Temperaturdrift bleibt der zentrale Layer-2-Validierungshebel
- Trainings-/Validierungsprototyp um KPI-nahe Aggregatmetriken erweitert:
  - neuer Output: `aggregate_kpi_metrics.csv`
  - berichtet runweise Summen-MAE/RMSE/Bias/R2 fuer Energie-/Flow-KPIs statt nur stundenweise Fehler
  - R2 wird fuer konstante Null-Ziele bewusst als `NaN` geschrieben, weil solche R2-Werte nicht informativ sind
- Zwei explizite Target-Modi eingefuehrt:
  - `complete`: nutzt alle Targets ohne fehlende Werte ueber alle 96 Teacher-Runs
    - Output: `Learning/models/building_response_v1_complete/`
    - Aggregat-R2 fuer Haupt-KPIs:
      - total heating: 0.990
      - transmitted solar: 0.970
      - window heat gain: 0.968
      - window heat loss: 0.990
      - internal gains: 0.9998
      - approx infiltration: 0.997
      - approx ventilation: 0.996
  - `all_available_subset`: nutzt auch direkte EnergyPlus-Air-Path-Flows, aber nur Rows ohne fehlende Direct-Flow-Targets
    - Output: `Learning/models/building_response_v1_direct_flows/`
    - reduziert sich aktuell auf 1927 Zeilen aus 17 Teacher-Runs
    - direkte Infiltration/Outdoor-Air-Loss Targets sind gut lernbar (`R2` ca. 0.981 stundenweise, ca. 0.999 aggregiert)
    - Heating/Solar/Window-Aggregate sind im kleinen Direct-Flow-Subset noch schwach bzw. instabil
- Interpretation:
  - mehr direkte EnergyPlus-Flows sind methodisch sinnvoll
  - fuer belastbare KPI-Metriken muessen diese Direct-Flow-Spalten aber in allen relevanten Teacher-Runs nachgezogen werden
  - sonst entsteht ein zu kleiner und verzerrter Direct-Flow-Trainingsschnitt
- Validierung um gruppierte Outputs erweitert:
  - `aggregate_kpi_metrics_by_group.csv`
  - `rollout_metrics_by_group.csv`
  - Gruppierung nach `cohort_id` und `experiment_id`
  - Komfort-False-Negatives im Rollout werden mitgezaehlt
- Wichtigste Diagnose aus `building_response_v1_complete`:
  - globaler 24h-Rollout bleibt bei `T_in` MAE 0.241 C und `q_heat` MAE 1.265 kWh
  - groesster Temperatur-Rollout-Ausreisser ist `winter_free_float_72h` mit `T_in` MAE 5.53 C
  - auf Kohortenebene dominiert `non_residential_1975_1990` den Rollout-Fehler mit `T_in` MAE 4.18 C
  - diese Ausreisser deuten auf freie Temperaturdrift-/Regimewechselprobleme hin und sollten vor Runtime-Nutzung getrennt behandelt werden
  - fuer papernahe KPI-Summen bleiben die globalen `complete`-Aggregat-R2-Werte hoch, aber einzelne kleine Gruppen mit wenigen Teacher-Runs haben instabile R2/MAE-Werte
- Reference-only Runtime-Regime separat trainiert und validiert:
  - Output: `Learning/models/building_response_v1_reference/`
  - Filter: `control_mode = reference`
  - 6440 Zeilen nach Filter
  - 70 Train-Teacher-IDs, 18 Test-Teacher-IDs
  - globale Aggregat-KPI-R2:
    - total heating: 0.998
    - transmitted solar: 0.932
    - window heat gain: 0.891
    - window heat loss: 0.996
    - internal gains: 0.9999
    - approx infiltration: 0.997
    - approx ventilation: 0.996
  - 24h-Rollout:
    - `T_in` MAE 0.137 C, RMSE 0.408 C
    - `q_heat` MAE 0.837 kWh, RMSE 1.478 kWh
  - 48h-Rollout:
    - `T_in` MAE 0.386 C, RMSE 0.783 C
    - `q_heat` MAE 1.377 kWh, RMSE 2.185 kWh
  - Interpretation:
    - das beheizte Reference-Regime ist deutlich stabiler als der gemischte All-Control-Schnitt
    - `free_float` sollte als separates Teacher-/Drift-Regime validiert werden, nicht als erstes Runtime-Freigabekriterium fuer den beheizten Dispatchpfad
- Hard-Split fuer das Reference-Regime ergaenzt:
  - neuer Split-Modus: `cohort_experiment`
  - Output: `Learning/models/building_response_v1_reference_hard_split/`
  - ganze `cohort_id + experiment_id`-Kombinationen werden aus dem Training gehalten
  - 6440 Zeilen, 70 Train-Gruppen, 18 Test-Gruppen
  - globale Aggregat-KPI-R2:
    - total heating: 0.999
    - transmitted solar: 0.970
    - window heat gain: 0.954
    - window heat loss: 0.998
    - internal gains: 0.9999
    - approx infiltration: 0.998
    - approx ventilation: 0.996
  - 24h-Rollout:
    - `T_in` MAE 0.140 C, RMSE 0.389 C
    - `q_heat` MAE 0.981 kWh, RMSE 1.547 kWh
  - 48h-Rollout:
    - `T_in` MAE 0.250 C, RMSE 0.593 C
    - `q_heat` MAE 1.291 kWh, RMSE 2.038 kWh
  - verbleibende Schwaechen:
    - einzelne kleine Gruppen mit nur 1-3 Teacher-Runs zeigen instabile R2-Werte
    - `non_residential_2000_2014`, `repday_shoulder_typical_day`, `winter_preheat_event` und `winter_recovery_event` sind relevante Rollout-/Komfort-Pruefpunkte
    - Event-Rebound-Metriken fehlen weiterhin als eigener Gate-Block

### Agent-/Coding-Regeln um tokenarmes Arbeiten ergaenzt

- `AGENTS.md` und `Documentation/coding_rules.md` ergaenzt:
  - token- und kontextsparsames Arbeiten
  - gezielte statt breite Exploration
  - keine unnoetig grossen Outputs, Artefakte oder Erklaerungen
  - umwelt- und kontextbewusste Arbeitsweise als feste Repo-Regel

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
- 2026-04-24: Scope-Grenze fuer Layer-2-Building-Surrogat-Validation geschaerft.
  - Building-Surrogat-Gates bleiben building-nah:
    - `T_in`, `q_heat`, Heat-balance-Flows, Komfort, Rollout, Event-Shift/Release/Rebound
  - Paper-Outcome-KPIs wie Kosten, CO2, Boiler-/CHP-Mix und Peak-Effekte bleiben downstream:
    - Dispatch-/System-Surrogat
    - oder End-to-End-Gold-Recheck
  - Damit wird vermieden, dass Layer 2 und das separate Systemsurrogat fachlich vermischt werden.
- 2026-04-24: Building-response Training um Event-Response-Metriken und einen paired Event-Split erweitert.
  - Neuer Output:
    - `event_response_metrics.csv`
  - Neue Metriken:
    - positives Heat-Delta gegen Referenz
    - negatives Heat-Delta gegen Referenz
    - Net-Heat-Delta
    - stundenweiser Heat-Delta-MAE
    - max/min und stundenweiser `T_in`-Delta-Fehler
  - Neuer Split-Modus:
    - `event_bundle`
    - haelt Preheat/Cutback plus `winter_event_reference_96h` gemeinsam
    - haelt Recovery plus `winter_recovery_reference_120h` gemeinsam
  - Validierter Lauf:
    - `Learning/models/building_response_v1_reference_event_bundle_split/`
    - 24h-Rollout `T_in` MAE `0.093 C`
    - 24h-Rollout `q_heat` MAE `0.679 kWh`
    - echte heldout Eventpaare: `4` Preheat, `4` Cutback, `2` Recovery
  - Befund:
    - allgemeine building-nahe Aggregatmetriken bleiben stark
    - heldout Event-Heat-Delta ist noch eine klare Qualitaetsbaustelle und sollte mit expliziteren Event-/Control-Features und mehr Event-Teacher-Daten verbessert werden
- 2026-04-24: Building-response Dataset um explizite Event-/Control- und thermische Abstandsfeatures erweitert.
  - Neue ML-Features aus der `Settings.technical.building_calibration`-SSOT:
    - `event_type`
    - `event_active`
    - `event_elapsed_h`
    - `event_remaining_h`
    - `event_setpoint_delta_c`
    - `reference_heating_setpoint_c`
    - `heating_setpoint_delta_c`
  - Neue physikalische Abstandsfeatures:
    - `t_in_minus_heating_setpoint_c`
    - `t_in_minus_reference_setpoint_c`
    - `t_in_minus_t_out_c`
    - `heating_setpoint_minus_t_out_c`
    - `reference_setpoint_minus_t_out_c`
  - Datensatz neu aufgebaut:
    - `Learning/datasets/building_response_v1/building_response_teacher_hourly.csv`
    - `7008` Transition-Zeilen aus `96` Teacher-Runs
  - Validierter `event_bundle`-Lauf nach Feature-Erweiterung:
    - `Learning/models/building_response_v1_reference_event_bundle_split/`
    - 24h-Rollout `T_in` MAE `0.077 C`
    - 24h-Rollout `q_heat` MAE `0.533 kWh`
    - heldout Preheat-Net-Heat-Delta-Fehler im Mittel `20.2 kWh` statt vorher rund `36.6 kWh`
  - Normaler `cohort_experiment`-Hard-Split ebenfalls neu gerechnet:
    - `Learning/models/building_response_v1_reference_hard_split/`
    - 24h-Rollout `T_in` MAE `0.141 C`
    - 24h-Rollout `q_heat` MAE `0.739 kWh`
  - Befund:
    - die expliziten Event- und Abstandsfeatures verbessern den Building-Surrogatpfad sichtbar
    - Event-Heat-Delta bleibt aber weiterhin das wichtigste naechste Gate, bevor Layer 2 als Runtime-Ersatz diskutiert wird
- 2026-04-27: EnergyPlus-Teacher um direkte Event-/Comfort-Bound-Exporte fuer den Building-Surrogatpfad erweitert.
  - Neue Teacher-Schedule-/Plausibility-Spalten:
    - `event_type`
    - `event_active`
    - `event_elapsed_h`
    - `event_remaining_h`
    - `event_setpoint_delta_c`
    - `reference_heating_setpoint_c`
    - `heating_setpoint_delta_c`
    - `lower_bound_c`
    - `upper_bound_c`
  - Bound-Semantik:
    - Preheat: `lower_bound_c = reference_heating_setpoint_c`, `upper_bound_c = heating_setpoint_c`
    - Cutback/Recovery: `lower_bound_c = heating_setpoint_c`, `upper_bound_c = reference_heating_setpoint_c`
    - Referenz: beide Bounds liegen am Referenz-Setpoint
  - `Learning/building_response/build_transition_dataset.py` nutzt neue Teacher-Spalten direkt.
  - Fuer vorhandene alte Teacher-Runs ohne diese Spalten gibt es eine explizite Legacy-Ableitung aus der Experiment-SSOT, damit die bestehenden Runs bis zum Neulauf weiter validierbar bleiben.
  - Validierung:
    - Python-Compile fuer Teacher und Learning-Module gruen
    - direkte Schedule-Pruefung fuer `residential_pre1975 / winter_preheat_event` zeigt waehrend des Events `lower_bound_c = 21`, `upper_bound_c = 23`
    - Datensatz neu aufgebaut: `7008` Transition-Zeilen aus `96` Teacher-Runs
    - `event_bundle`-Retrain:
      - 24h-Rollout `T_in` MAE `0.076 C`
      - 24h-Rollout `q_heat` MAE `0.536 kWh`
      - Heating-Aggregat `R2 = 0.9993`
      - heldout Preheat-Net-Heat-Delta-Fehler im Mittel `19.0 kWh`
  - Naechster fachlicher Schritt:
    - Teacher-Runs mit den neuen direkten Bound-Spalten neu erzeugen
    - zusaetzliche Event-Teacher-Laeufe fuer bessere heldout Event-Heat-Delta-Gates aufbauen
- 2026-04-27: Bound-Semantik fuer den Paper-Hauptfall korrigiert.
  - Die vorherige Interpretation als beidseitiges Event-Komfortband war fuer die Paper-Story zu breit.
  - Korrigierter Hauptfall:
    - `upper_only`
    - keine Absenkung unter den Setpoint
    - Setpoint / untere Grenze `22.0 C`
    - keine aktive obere Thermflex-Temperaturgrenze
  - Code-Anpassung:
    - `Settings/technical/building_calibration.py` fuehrt `teacher_reference_heating_setpoint_c = 22.0`
    - der EnergyPlus-Teacher exportiert weiter Event-/Control-Spalten, aber keine aktive Upper-Bound-Semantik
    - der Building-Dataset-Builder setzt `lower_bound_c = reference_heating_setpoint_c`
    - `upper_bound_active = 0`, `upper_bound_c` bleibt nur numerischer Platzhalter fuer Modelle/Exports
    - obere Komfort-False-Negatives werden nur gezaehlt, wenn `upper_bound_active = 1`
  - Validierung:
    - direkte Schedule-Pruefung fuer neue Teacher-Runs zeigt Preheat mit Referenz `22.0 C` und aktivem Heizsetpoint `24.0 C`
    - der aktuell kombinierte Datensatz nutzt noch alte Teacher-CSV-Werte mit `21.0 C`, bis die Teacher-Runs neu erzeugt werden
    - `event_bundle`-Retrain auf dem bestehenden Datensatz: 24h `T_in` MAE `0.077 C`, 24h `q_heat` MAE `0.535 kWh`
  - Cutback-/Recovery-Teacher bleiben damit nur separate Diagnose-Experimente und nicht Teil der Haupt-Use-Case-Semantik.
- 2026-04-27: Building-Surrogat-Modellstrategie festgehalten.
  - Aktueller V1-Pfad bleibt ein sklearn `RandomForestRegressor` als multi-output transition model.
  - Grund:
    - robust auf dem kleinen aktuellen Teacher-Datensatz
    - direkte Multi-Target-Faehigkeit fuer `T_in_next`, `q_heat` und Heat-balance-Diagnostics
    - geeignet als Baseline, solange Teacher-Daten, Splits und Event-Semantik noch stabilisiert werden
  - XGBoost wird nicht vor dem 22-C-Teacher-Rerun getunt.
  - Nach dem Rerun wird XGBoost als Benchmark geprueft:
    - ein Modell pro Target
    - oder `MultiOutputRegressor(XGBRegressor)`
- 2026-04-27: EnergyPlus-Teacher-Rerun fuer den Building-Surrogatpfad auf 22-C-Setpoint abgeschlossen.
  - Fehler im Teacher-Schedule-Export behoben:
    - EnergyPlus liest `Schedule:File` ueber feste one-based Column Numbers
    - neue Event-/Learning-Spalten hatten die Spaltenpositionen verschoben
    - Export haelt jetzt EnergyPlus-Spalten stabil vorne und haengt Metadaten danach an
  - Pilot `residential_pre1975 / winter_preheat_event` erfolgreich:
    - Referenzsetpoint `22.0 C`
    - Teacher-Preheat-Excitation `24.0 C`
    - Event-Spalten im Plausibility-Export vorhanden
  - Full Event Batch erfolgreich neu erzeugt:
    - `8` Kohorten x `5` Event-/Referenzexperimente
    - Summary unter `Technical_model/technologies/buildings/calibration/_teacher_runs/_event_batches/`
  - Building-Response-Datensatz neu gebaut:
    - `Learning/datasets/building_response_v1/building_response_teacher_hourly.csv`
    - `7008` Transition-Zeilen aus `96` Teacher-Runs
  - RF-V1 `event_bundle` neu trainiert:
    - Artefakt: `Learning/models/building_response_v1_reference_event_bundle_split/`
    - 24h-Rollout `T_in` MAE `0.209 C`
    - 24h-Rollout `q_heat` MAE `0.471 kWh`
    - Heizenergie-Aggregat: MAE `15.0 kWh`, R2 `0.9993`
    - heldout Event-Net-Heat-Delta-Fehler im Mittel: Preheat `13.0 kWh`, Cutback `9.7 kWh`, Recovery `31.9 kWh`
  - Befund:
    - EnergyPlus-Teacher-Stand ist jetzt konsistent mit der 22-C-Upper-only-Hauptstory
    - RF-Baseline trifft aggregierte Heizenergie gut
    - Event-Amplitude und Recovery-Generalisation bleiben der naechste Modellqualitaetshebel
- 2026-04-27: XGBoost-Benchmark fuer Building-Response-V1 gegen RF gerechnet.
  - Trainer um explizites `--model-type rf|xgb` erweitert; RF bleibt Default.
  - XGBoost-Variante:
    - `MultiOutputRegressor(XGBRegressor)`
    - bewusst target-wise statt experimenteller nativer Multi-Output-Nutzung
    - single-process fuer reproduzierbaren Windows-/Sandbox-Betrieb
  - Vergleichsartefakte:
    - RF: `Learning/models/building_response_v1_reference_event_bundle_split/`
    - XGB: `Learning/models/building_response_v1_reference_event_bundle_split_xgb/`
    - CSV: `Learning/models/building_response_v1_rf_xgb_benchmark.csv`
  - Zentrale Metriken:
    - RF 24h `T_in` MAE `0.209 C`, 24h `q_heat` MAE `0.471 kWh`, Heizenergie-Aggregat MAE `15.0 kWh`
    - XGB 24h `T_in` MAE `0.076 C`, 24h `q_heat` MAE `1.197 kWh`, Heizenergie-Aggregat MAE `46.7 kWh`
    - heldout Event-Net-Heat-Delta:
      - Preheat: RF `13.0 kWh`, XGB `7.4 kWh`
      - Cutback: RF `9.7 kWh`, XGB `17.3 kWh`
      - Recovery: RF `31.9 kWh`, XGB `20.4 kWh`
  - Befund:
    - XGB ist besser fuer Temperaturdynamik und Teile der Event-Response
    - RF ist klar besser fuer Heizenergie-/`q_heat`-Gates
    - deshalb kein pauschaler Wechsel auf XGB; naechster Schritt waere getrennte/gewichtete Modelle fuer `T_in` vs. `q_heat`
- 2026-04-27: XGBoost-`q_heat`-Diagnose und Hybrid-Benchmark nachgezogen.
  - Diagnose:
    - erster XGB-Run ueberschaetzt niedrige Heizlaststunden systematisch
    - Fehler liegt bereits one-step vor, nicht nur im rekursiven Rollout
    - `log1p(q_heat)` verschlechtert aggregierte Heizenergie wegen starker Unterprognose
  - Massnahmen getestet:
    - `xgb_heat` als flacher/regularisierter Preset: schlechter fuer `q_heat`
    - direkter `q_heat`-Grid: tieferes XGB (`max_depth=5`) lernt Heizenergie deutlich besser
    - neuer reproduzierbarer Preset `--xgb-preset qheat`
    - neuer Benchmarktyp `--model-type hybrid_temp_xgb_heat_rf`
  - Vergleich:
    - RF: 24h `T_in` MAE `0.209 C`, 24h `q_heat` MAE `0.471 kWh`, Heat-Aggregat MAE `15.0 kWh`
    - XGB balanced: 24h `T_in` MAE `0.076 C`, 24h `q_heat` MAE `1.197 kWh`, Heat-Aggregat MAE `46.7 kWh`
    - XGB qheat: 24h `T_in` MAE `0.059 C`, 24h `q_heat` MAE `0.668 kWh`, Heat-Aggregat MAE `19.2 kWh`
    - Hybrid: 24h `T_in` MAE `0.076 C`, 24h `q_heat` MAE `0.471 kWh`, Heat-Aggregat MAE `15.0 kWh`
  - Befund:
    - XGB kann Heizenergie besser lernen, aber nicht gleichzeitig stabiler als RF im Aggregat auf diesem kleinen Split
    - Hybrid trennt die Targets fachlich sauber und ist aktuell der beste Kompromiss
    - Event-Amplitude bleibt separat zu verbessern; dafuer braucht es eher mehr Upper-only-/Preheat-Teacher-Designs als weiteres blindes Tuning
- 2026-04-27: Hybrid-Building-Surrogat ueber mehrere Event-Bundle-Splits validiert.
  - Seeds: `7`, `21`, `42`, `84`, `126`.
  - Artefakte:
    - `Learning/models/building_response_v1_robustness_event_bundle/robustness_detail.csv`
    - `Learning/models/building_response_v1_robustness_event_bundle/robustness_summary.csv`
  - Ergebnis ueber die fuenf Splits:
    - RF mittlerer 24h `T_in` MAE `0.272 C` (`std 0.091`)
    - Hybrid mittlerer 24h `T_in` MAE `0.109 C` (`std 0.029`)
    - RF mittlerer 24h `q_heat` MAE `0.880 kWh`
    - Hybrid mittlerer 24h `q_heat` MAE `0.878 kWh`
    - Heat-Aggregat-MAE bleibt identisch, weil der Hybrid fuer Heizenergie und Heat-balance-Flows bewusst den RF-Teil nutzt
  - Befund:
    - Hybrid verbessert Temperaturdynamik robust, ohne die Heizenergie-Gates zu verschlechtern
    - damit ist der Hybrid der aktuelle V1-Kandidat fuer weitere Side-by-side-Validierung gegen ROM/Teacher
    - noch nicht produktiv aktivieren; erst Event-Amplitude/Rebound durch zusaetzliche Upper-only-/Preheat-Teacher-Designs staerken
- 2026-04-27: Paper-tauglichere reine XGBoost-Target-Blocks-Variante geprueft.
  - Neuer Modelltyp: `xgb_target_blocks`.
  - Idee:
    - gleiche Modellfamilie fuer alle Targets
    - XGB-balanced fuer `T_in_next`
    - XGB-qheat fuer `q_heat` und Heat-balance-Flows
    - dadurch methodisch besser erzaehlbar als RF/XGB-Hybrid
  - Seed-42:
    - 24h `T_in` MAE `0.076 C`
    - 24h `q_heat` MAE `0.669 kWh`
    - Heizenergie-Aggregat MAE `19.2 kWh`
  - Fuenf-Split-Robustheit:
    - XGB target blocks mittlerer 24h `T_in` MAE `0.109 C`
    - mittlerer 24h `q_heat` MAE `0.910 kWh`
    - mittlerer Heat-Aggregat-MAE `45.6 kWh`
    - mittlerer Preheat-Net-Delta-Fehler `18.4 kWh`
  - Vergleich:
    - Hybrid hat gleiche Temperaturguete, aber bessere Heizenergie und besseren Preheat-Delta-Fehler
    - reine XGB-Variante bleibt daher dokumentierte paperfreundliche Alternative, aber nicht bevorzugter V1-Kandidat
- 2026-04-27: XGB-Target-Blocks-Flowfehler gezielt analysiert und Feature-/Preset-Verbesserungen getestet.
  - Relativer MAE fuer Seed-42 `xgb_target_blocks` vor Feature-Erweiterung:
    - `window_heat_gain`: `3.42 %`, R2 `0.9939`
    - `zone_total_heating`: `1.95 %`, R2 `0.9990`
    - `zone_windows_transmitted_solar`: `1.86 %`, R2 `0.9960`
    - `window_heat_loss`: `1.51 %`, R2 `0.9990`
  - Neue deterministische Features im Building-Response-Datensatz:
    - hour/day zyklisch (`hour_sin`, `hour_cos`, `day_sin`, `day_cos`)
    - direkte `hour_of_day`, `day_of_year`
    - Solar-Lags/Rolling-Mittel (`epw_ghi_lag1`, `epw_dhi_lag1`, `epw_ghi_roll3`, `epw_dhi_roll3`)
  - Ergebnis `features_v2`:
    - `zone_total_heating` verbessert sich leicht: `1.95 % -> 1.90 %`
    - `window_heat_gain` verbessert sich minimal: `3.42 % -> 3.41 %`
    - `zone_windows_transmitted_solar` verschlechtert sich leicht: `1.86 % -> 1.99 %`
    - `window_heat_loss` verschlechtert sich leicht: `1.51 % -> 1.63 %`
  - Separater `solar_window`-XGB-Preset fuer Fensterziele getestet:
    - verschlechtert alle drei Fensterziele gegenueber `features_v2` und dem alten Target-Blocks-Lauf
    - daher nicht als bevorzugter Pfad weiterverfolgen
  - Befund:
    - die vier "schlechteren" Flows sind aggregiert bereits gut
    - kleine Feature-Verbesserungen helfen Heizenergie, aber Fenster-/Solarziele brauchen eher mehr gezielte Solar-/Glazing-Teacher-Coverage als weitere Preset-Heuristik
- 2026-04-27: Upper-only-/Preheat-Teacher-Coverage fuer Repraesentativtage erweitert und XGB-Blocks neu bewertet.
  - Neue Settings-SSOT-Experimente:
    - `repday_winter_peak_heat_reference_96h`
    - `repday_winter_peak_heat_preheat_96h`
    - `repday_winter_price_spike_reference_96h`
    - `repday_winter_price_spike_preheat_96h`
    - `repday_winter_sunny_heat_reference_96h`
    - `repday_winter_sunny_heat_preheat_96h`
    - `repday_shoulder_typical_reference_96h`
    - `repday_shoulder_typical_preheat_96h`
  - Teacher-Setup neu erzeugt:
    - Experiment-Library jetzt `21` Experimente
  - Selektiver EnergyPlus-Teacher-Batch:
    - `8` Experimente x `8` Kohorten = `64` neue Teacher-Laeufe
  - Building-Response-Datensatz neu gebaut:
    - `13088` Transition-Zeilen aus `160` Teacher-Runs
  - Augmentierter Vergleich auf gleichem Seed-42-Event-Bundle-Split:
    - RF: 24h `T_in` MAE `0.326 C`, 24h `q_heat` MAE `0.499 kWh`
    - XGB target blocks: 24h `T_in` MAE `0.168 C`, 24h `q_heat` MAE `0.627 kWh`
  - Flow-Rel-MAE Vergleich `RF` vs. `XGB target blocks` auf augmentiertem Split:
    - `zone_total_heating`: `3.10 %` vs. `2.53 %`
    - `zone_windows_transmitted_solar`: `3.36 %` vs. `1.85 %`
    - `window_heat_gain`: `3.88 %` vs. `3.11 %`
    - `window_heat_loss`: `2.21 %` vs. `2.82 %`
  - Artefakt:
    - `Learning/models/building_response_v1_augmented_flow_rel_mae_comparison.csv`
  - Befund:
    - Mehr Teacher-Coverage hilft der paperfreundlichen XGB-Target-Blocks-Variante sichtbar fuer Heizenergie, Solar-transmitted und Window-gain
    - Window-loss bleibt der einzige der vier betrachteten Flows, bei dem RF im augmentierten Split besser ist
- 2026-04-27: XGB-Target-Blocks fuer Window-loss nachkalibriert und finalen augmentierten Vergleich erzeugt.
  - Window-loss-Restfehler gezielt isoliert getestet.
  - Bester getesteter Window-loss-Preset:
    - `n_estimators=420`
    - `max_depth=5`
    - `learning_rate=0.02`
    - `subsample=0.95`
    - `colsample_bytree=0.95`
    - `reg_lambda=2.0`
    - `reg_alpha=0.02`
  - Finaler XGB-Target-Blocks-Lauf:
    - `Learning/models/building_response_v1_reference_event_bundle_split_xgb_target_blocks_augmented_final/`
  - Finaler augmentierter Flow-Rel-MAE Vergleich `RF` vs. `XGB target blocks`:
    - `zone_total_heating`: `3.10 %` vs. `2.53 %`
    - `zone_windows_transmitted_solar`: `3.36 %` vs. `1.85 %`
    - `window_heat_gain`: `3.88 %` vs. `3.11 %`
    - `window_heat_loss`: `2.21 %` vs. `2.26 %`
    - `approx_ventilation_loss`: `1.26 %` vs. `0.04 %`
    - `approx_infiltration_loss`: `0.90 %` vs. `0.02 %`
    - `internal_gains`: `0.52 %` vs. `0.001 %`
  - Befund:
    - XGB target blocks ist nach Teacher-Augmentierung und Window-loss-Preset bei fast allen Building-Response-Targets besser als RF
    - Window-loss bleibt minimal schlechter, aber praktisch sehr nah an RF
    - das ist jetzt die paperfreundliche V1-ML-Variante; RF bleibt konservative Baseline
- 2026-04-27: Aktive Thermflex-Paper-Figures/Tables bereinigt.
  - Peak-Boiler-Oil/Gas-Mix in die generelle Sensitivitaetsanalyse verschoben, nicht mehr als eigener Hauptpfad.
  - Fig. 07 aus aktueller Table 09 neu gerendert.
  - Tables 10-12 aus dem neuesten `paper_mechanism_bundle_20260423_221857` neu gebaut.
  - Klar veraltete aktive Outputs nach `old/` verschoben:
    - `table_03_representative_day_kpi_summary.md`
    - `table_04_preheat_timing_solar_contribution.md`
    - `table_07_upper_only_duration_response_top_days.md`
    - `table_08_lb21_vs_upper_residential_cohort_shift_top_days.md`
    - `fig_03_top_savings_upper_only_shift.png`
  - Aktiver Table-Bestand:
    - Table 02, 05, 06, 09, 10, 11, 12
  - Aktiver Figure-Bestand:
    - Fig. 00 teacher reference flow comparison
    - Fig. 06 cohort duration daily sums
    - Fig. 07 flexibility outcome atlas
    - Fig. 10 source redispatch facets
- 2026-04-27: Thermflex-Paper-Auswertung um aktuelle Fig. 02, Fig. 08 und Heizsaison-KPI-Zeile erweitert.
  - `fig_02_representative_upper_only_shift.png` mit aktuellem `upper_only dur24 evt24`-Override neu gerendert.
  - Fig. 02 trennt nun Zusatzheizleistung / Preheat von reduzierter Heizleistung / Release farblich.
  - Fig. 02 danach zur Mechanismusgrafik erweitert:
    - oberes Teilpanel: Referenz- und Flex-Waermelastpfad
    - unteres Teilpanel: explizite stündliche `Flex - Reference`-Balken
    - orange positive Balken = zusaetzliche Waerme / Preheat
    - blaue negative Balken = reduzierte Waerme / Release
    - Textbox je Tag zeigt Preheat-, Release- und Netto-MWh
  - Neue Wochenmechanismusgrafik erstellt:
    - `fig_11_weekly_upper_only_shift.png`
    - Woche `2023-11-01` bis `2023-11-07` um den Table-09-Top-Savings-Tag `2023-11-04`
    - oben Referenz/Flex-Waermelast, unten `Flex - Reference`-Balken
    - 169h-Solve und 168h-Plot, um den letzten Horizon-Step nicht als Mechanismus zu visualisieren
    - Laufzeit-Hinweis: 169h-Flex-Solve ist teuer und dauerte im Test mehrere Minuten
  - Fig. 11 anschliessend mit 6h-Uhrzeitmarken auf der horizontalen Achse neu gerendert, damit die Preheat-/Release-Zeitfenster lesbarer sind.
  - TODO ergaenzt: spaeter pruefen, ob Wochenmechanikplots die Tagespanels im Main Paper ersetzen und Fig. 02 ggf. in den Appendix wandert.
- 2026-04-27: Wochen-Dispatchgrafik fuer die obere Flex-Woche erstellt.
  - `fig_12_weekly_dispatch_shift.png` zeigt dieselbe Woche wie Fig. 11.
  - Aufbau:
    - Referenz-Dispatch als gestackte Waermeerzeugung
    - Flex-Dispatch als gestackte Waermeerzeugung
    - stündliche Quell-Deltas `Flex - Reference`
  - Quellen:
    - Gas-CHP heat
    - Heat pump
    - Peak boiler
  - `fig_12_weekly_dispatch_shift.csv` als Cache geschrieben, damit Layoutanpassungen ohne erneuten 169h-Gold-Solve moeglich sind.
  - Fig. 11 Builder angepasst, damit 6h-Minor-Ticks bis inklusive Wochenende/`00` erzeugt werden.
  - Fig. 11 kann den Fig.-12-CSV-Cache fuer reines Demand-Plot-Rendering nutzen, um Layoutupdates ohne erneuten 169h-Gold-Solve zu erlauben.
- 2026-04-27: Wiener 2023-DH-Referenzmix im aktiven Thermflex-Paperpfad um Waste Incineration korrigiert.
  - Lokale Quellenlage erneut geprueft:
    - Enable-DHC-/Wien-2023-Anker: `Muell- und Sondermuellverbrennung (eigene) = 1.200,0 GWh/a`
    - Enable-DHC-/Wien-2023-Anker: `Bezug Abwaerme = 1.200,9 GWh/a`
    - aktive FLH-Konvention fuer Waste: `7500 h/a`
  - Daten-SSOT aktualisiert:
    - `Data/energy_potentials/Vienna/energy_potentials.py`
    - `district_waste_incineration_gwh_per_year_max = 1200.0`
  - Aktive Thermflex-Paper-Overrides aktualisiert:
    - Referenz: `vienna_ref2023_dh_baseline_constant_no_thermflex_paper_day_ahead.json`
    - Flex: `vienna_ref2023_dh_baseline_constant_thermflex_lb22p5_dur24_evt24_upper_only_paper_day_ahead.json`
    - Hinweis: diese Override-Dateien liegen unter `Optimization/validation/` und sind im aktuellen Git-Setup ignoriert; fuer den finalen Paperpfad muessen sie noch in eine getrackte Settings-/Generator-SSOT ueberfuehrt werden.
    - `district_waste_incineration = true`
    - `district_waste_incineration.installed_kw_th_fixed = 160000`
    - `district_waste_incineration.thermal_availability = 1.0`
    - `district_external_heat.installed_kw_th_fixed = 160000`
    - `district_external_heat.thermal_availability = 1.0`
  - Waste wird bewusst als Fixed Capacity gefuehrt, nicht als Bounds-/Optimizer-Designvariable.
  - Wien-Economics fuer den Thermflex-Benchmark ergaenzt:
    - `district_waste_incineration.variable_opex_eur_per_kwh_th = 0.0`
    - `district_waste_incineration.direct_co2_t_per_mwh_th = 0.0`
    - Semantik: bestehende nicht-marginale Waste-Heat-Quelle, keine zusaetzliche fossile Waermeerzeugung durch Thermflex.
  - `build_constant_thermflex_isolation._evaluate_case_timeseries` um External Heat, Waste Incineration und Biomass CHP Heat erweitert.
  - Fig. 12 neu gerendert mit vollstaendigerem Source-Stack:
    - External waste heat
    - Waste incineration
    - Biomass CHP heat
    - Heat pump
    - Gas CHP heat
    - Peak boiler
  - Der direkte 169h-Flex-Solve mit Waste war zu teuer und wurde nach 15 min abgebrochen; Fig. 12 nutzt deshalb sieben 25h-Day-Slices und plottet jeweils die ersten 24h.
  - November-Wochen-Smoke aus Fig. 12:
    - Peak boiler delta: `-5907 MWh`
    - External heat delta: `+2159 MWh`
    - Waste incineration delta: `+2004 MWh`
    - Gas CHP heat delta: `-1 MWh`
    - Biomass CHP heat delta: `0 MWh`
  - Fig. 11 wurde aus dem neuen Fig.-12-Cache neu gerendert, damit Demand-Mechanik und Source-Dispatch dieselbe Erzeugerbasis verwenden.
  - Fig. 08 wieder nach `old/` verschoben, weil die positive/negative Balkenlogik in Fig. 06 die bessere Paper-Grafik bleibt.
  - Fig. 06 stattdessen direkt nachgeschaerft:
    - positive Balken = additional heat / preheat
    - negative Balken = avoided heat / release
    - kurzer schwarzer Endstrich = algebraischer Netto-Waermeeffekt
  - `table_09_tradeoff_day_summary_upper_only_dur24.md` um eine Heizsaison-Aggregation aus dem aktiven 212-Tage-Screen erweitert:
    - Kosten: `-11.13 MEUR` / `-0.41%`
    - CO2: `-31.05 kt` / `-1.48%`
    - Peak-Boiler-Energie: `-124.69 GWh` / `-3.60%`
    - Peak-Boiler-Spitzenleistung: `+3.38%`
    - shifted heat: `172.76 GWh`
    - rebound heat: `52.71 GWh`
  - TODO ergaenzt: Domestic-hot-water-Zeitreihe und Profilskalierung fuer Methoden / Appendix sauber dokumentieren.
- 2026-05-10: `table_09_tradeoff_day_summary_upper_only_dur24.md` auf Heizsaison-KPIs umgestellt.
  - Neuer Builder: `Documentation/Papers/thermflex_paper/tables/build_table_09_heating_season_kpis.py`.
  - Quelle bleibt der aktive Full-Season-Screen:
    `Optimization/run/results/Vienna/gold/daily_thermflex_screen_dur24_20260423_213718/heating_season_day_screen.csv`.
  - Hauptzeitraum ist jetzt die gesamte Heizsaison (`212` Screen-Tage), nicht mehr eine Selected-Day-Liste.
  - Ergaenzt wurden je KPI die staerksten zusammenhaengenden rollierenden `7`-Tage-Fenster mit Start-/Enddatum.
  - Zusaetzlich weist die Tabelle den Einzel-Tag mit maximaler absoluter Kosteneinsparung und den Einzel-Tag mit maximaler absoluter CO2-Einsparung aus.
- 2026-04-27: Quellenblock fuer DH-Bus-Aggregation und Netztraegheit dokumentiert.
  - Neue Quellen-Notiz: `Documentation/Sources/dh_bus_aggregation_quellen.md`.
  - Aufgenommen:
    - Weissmann/Hong/Graubner 2017 fuer Heizlastdiversitaet und zentrale DH-Peak-Reduktion.
    - Braas/Jordan/Best/Orozaliev/Vajen 2020 fuer DHW-Simultaneitaet.
    - Benonysson/Boehm/Ravn 1995 fuer operative DH-Netzdynamik, Zeitverzug und Waermespeicherung.
    - Larsen/Palsson/Boehm/Ravn 2002 fuer aggregierte dynamische Ersatznetzmodelle ohne vollstaendige Topologie.
    - Gu et al. 2017 und Zheng et al. 2018 fuer DH-Netz-/Gebaeudetraegheit in integrierten Dispatchmodellen.
  - TODO ergaenzt: optionaler `dh_bus_aggregation`-Pfad ohne kuenstliche Raumwaerme-Nutzungsprofile, mit settingsgefuehrter kausaler DH-Bus-Verzoegerung/Glaettung und klarer Trennung von Gebaeude- und Dispatch-KPIs.
- 2026-04-27: Visuellen Vorcheck fuer aggregierte DH-Bus-Traegheit erstellt.
  - Neuer Builder: `Documentation/Papers/thermflex_paper/figures/build_fig_13_dh_bus_inertia_sensitivity.py`.
  - Output:
    - `fig_13_dh_bus_inertia_sensitivity.png`
    - `fig_13_dh_bus_inertia_sensitivity.csv`
    - `fig_13_dh_bus_inertia_sensitivity_metrics.csv`
  - Datengrundlage ist nur der vorhandene Fig.-12-Wochen-Cache; kein Re-Dispatch und keine Modellintegration.
  - Modell im Vorcheck:
    - kausaler First-Order-DH-Bus:
      `q_bus[t] = q_bus[t-1] + alpha * (q_building[t] - q_bus[t-1])`
    - `alpha = 1 / (tau_h + 1)` bei stündlicher Aufloesung
    - Sensitivitaet `tau_h = 0/4/8/12`
  - Erste Kennzahlen fuer die November-Woche:
    - `tau_h=4`: Referenz-Peak `-29.2 %`, max. stündliche Referenz-Rampe `-81.0 %`, Flex-vs-Ref-Amplitude `-39.8 %`
    - `tau_h=8`: Referenz-Peak `-38.1 %`, max. stündliche Referenz-Rampe `-90.5 %`, Flex-vs-Ref-Amplitude `-55.9 %`
    - `tau_h=12`: Referenz-Peak `-42.9 %`, max. stündliche Referenz-Rampe `-93.9 %`, Flex-vs-Ref-Amplitude `-63.5 %`
  - Interpretation:
    - `tau_h=4` wirkt als plausibler erster Kandidat fuer Modellintegration.
    - `tau_h=8/12` zeigen starke Glaettung und sollten eher als Sensitivitaet/Upper-Bound gelesen werden.
  - Nach Diskussion festgehalten:
    - der Tau-Sensitivitaetsplot bleibt vorerst interne Analyse-/Entscheidungsgrafik, nicht Paper-Hauptgrafik.
    - Sensitivitaeten sollen spaeter direkt in passende Ergebnisplots/-tabellen integriert werden, statt als isolierter Appendix-Nachtrag.
    - Modellintegration wurde nicht finalisiert; vor echten Tau-4-Kosten-/CO2-KPIs muss zuerst die DH-Bus-Boundary-/Endzustandsbehandlung entschieden werden.
- 2026-04-27: Experimentellen DH-Bus-Traegheitspfad in den echten MILP-/Gold-Dispatch eingebaut und Wochen-KPIs gerechnet.
  - Settings-Parameter:
    - `dh_bus_inertia_enabled`
    - `dh_bus_inertia_tau_h`
    - `dh_bus_inertia_terminal_policy`
  - Dispatch exportiert nun getrennt:
    - Gebaeude-/Komfortseite: `dh_building_total_demand`
    - Kraftwerks-/Dispatchseite: `dh_bus_load`
  - Neuer Tabellenbuilder:
    - `Documentation/Papers/thermflex_paper/tables/build_table_13_dh_bus_inertia_weekly_kpis.py`
  - Output:
    - `Documentation/Papers/thermflex_paper/tables/table_13_dh_bus_inertia_weekly_kpis.csv`
    - `Documentation/Papers/thermflex_paper/tables/table_13_dh_bus_inertia_weekly_kpis.md`
  - Gepruefte Wochen:
    - `top_savings_week` ab `2023-11-01`
    - `cold_peak_week` ab `2023-01-15`
    - `december_week` ab `2023-12-10`
  - Ergebnisbild:
    - ohne DH-Bus-Traegheit (`tau_h = 0`) bleiben die bekannten Savings stark.
    - mit `tau_h = 4/8` bleiben Kosten-, CO2- und Peak-Boiler-Energie-Deltas in allen drei Wochen negativ.
    - die Effektgroessen werden durch die Glaettung aber stark kleiner; `tau_h = 4` ist aktuell eher Basiskandidat, `tau_h = 8` eher starke Sensitivitaet.
  - Offener Methodenpunkt:
    - Boundary-/Endzustandspolitik ist aktuell experimentell (`terminal_policy = free`) und muss vor finalen Paper-Zahlen festgelegt werden.
    - CHP-Rampen-/Traegheitslogik waere ein separater naechster Erzeugerpfad, weil Peak-Boiler selbst fachlich schnell reagieren koennen.
- 2026-04-27: Fig. 12 auf den experimentellen `tau_h = 4`-DH-Bus-Dispatch umgestellt.
  - Builder geaendert:
    - `Documentation/Papers/thermflex_paper/figures/build_fig_12_weekly_dispatch_shift.py`
  - Fig. 12 nutzt nun einen zusammenhaengenden `168 h`-Goldlauf mit `dispatch.horizon_h = 24`, statt einzelne 25h-Tages-Slices zu konkatenieren.
  - Der Dispatch wird gegen die geglaettete DH-Buslast gerechnet.
  - Die gestrichelte Linie zeigt weiterhin die raw/building-side Nachfrage, damit die Netz-/Busglaettung visuell sichtbar bleibt.
  - Output aktualisiert:
    - `Documentation/Papers/thermflex_paper/figures/fig_12_weekly_dispatch_shift.png`
    - `Documentation/Papers/thermflex_paper/figures/fig_12_weekly_dispatch_shift.csv`
  - Wochenbilanz aus dem aktualisierten CSV:
    - DH-Bus-Referenzpeak `1397.7 MW`, Building-Referenzpeak `1973.2 MW`
    - Upper-only vs Referenz:
      - External waste heat `+864.5 MWh`
      - Waste incineration `+472.2 MWh`
      - Biomass CHP heat `+16.0 MWh`
      - Heat pump `+29.2 MWh`
      - Gas CHP heat `-1.3 MWh`
      - Peak boiler `-304.8 MWh`
- 2026-04-27: Waste-Incineration-Must-run im MILP-Dispatch korrigiert und Cold-week-Fig.-12 erzeugt.
  - Befund:
    - Settings hatten `district_waste_incineration.must_run = true`, der MILP-Pfad hat diesen SSOT-Wert bisher aber nicht ausgewertet.
    - Dadurch konnte Waste in Niedriglaststunden optisch/operativ wegfallen.
  - Korrektur:
    - `Technical_model/energy_system/systems/integrated_energy_system.py` uebergibt jetzt:
      - `district_waste_incineration_min_partload`
      - `district_waste_incineration_must_run`
    - `dispatch/modes/milp_day_ahead.py` und `dispatch/modes/milp_two_stage.py` erzwingen bei `must_run=true`:
      - `waste_on = 1`
      - `waste_th + waste_spill = waste_available`
    - Fig. 12 stellt Waste als erzeugte Must-run-Waerme dar:
      - `district_waste_incineration_generation + district_waste_incineration_thermal_spillage`
  - Neue/aktualisierte Outputs:
    - `Documentation/Papers/thermflex_paper/figures/fig_12_weekly_dispatch_shift.png`
    - `Documentation/Papers/thermflex_paper/figures/fig_12_weekly_dispatch_shift.csv`
    - `Documentation/Papers/thermflex_paper/figures/fig_12_cold_weekly_dispatch_shift.png`
    - `Documentation/Papers/thermflex_paper/figures/fig_12_cold_weekly_dispatch_shift.csv`
  - Aktuelle Fig.-12-Top-savings-Woche (`2023-11-01`, `tau_h = 4`):
    - Cost `-0.375 %`
    - CO2 `-1.319 %`
    - Peak-boiler energy `-9.133 %`
    - Peak-boiler peak `-1.623 %`
  - Aktuelle Cold-week (`2023-01-15`, `tau_h = 4`):
    - Cost `-0.009 %`
    - CO2 `-0.025 %`
    - Peak-boiler energy `-0.045 %`
    - Peak-boiler peak `+0.000 %`
  - Hinweis:
    - Table 13 wurde dadurch methodisch stale und muss vor weiterer Paper-Nutzung neu gerechnet werden.
    - Cold-week-Figur ist eher Kontrast/Diagnose; wegen freier Wochen-Endbedingung ist der letzte Boiler-Drop nicht final paper-tauglich.
- 2026-04-27: Fig.-12-Interpretation und Wiener Speicherplausibilisierung nachgezogen.
  - Befund Fig. 12:
    - die Stackflaeche liegt in einzelnen Stunden ueber der DH-Buslast, weil sie aktuell erzeugte Waermequellen zeigt, waehrend die Linie die geglaettete Buslast zeigt
    - bei Must-run Waste / CHP / Spillage ist das keine direkte ThermFlex-Wirkung, sondern Bruttoerzeugung bzw. nicht nutzbare Ueberschusswaerme gegen eine Netto-Lastlinie
    - Top-savings-Woche: maximale optische Ueberdeckung liegt in Referenz und Flex vor; sie ist daher nicht per se Flex, sondern Stack-Semantik/Spillage
  - Wiener Speicherquelle dokumentiert:
    - Simmering: `11.000 m3`, `850 MWh`, rund `145.000 MWh/a` Entnahme ueber `2.200 h/a`
    - daraus mittlere Entladeleistung ca. `65,9 MW`
    - Urban DH Extended nennt fuer den vollen Speicher maximal `145 MW` ueber `6 h`
  - Modellimplikation:
    - aktueller Speicher braucht explizite Charge-/Discharge-Power-Limits in Settings
    - die Heat Pump braucht einen fachlichen Mittellast-Schnitt statt reiner Kapazitaets-/COP-Lueckenfuellerlogik
- 2026-04-29: Wiener Speicherleistungsgrenze in den Dispatchpfad integriert und Fig. 12 auf Winterwochen neu gerechnet.
  - Codepfad:
    - `DistrictThermalStorageConfig` hat nun explizite `max_charge_kw_th` und `max_discharge_kw_th`
    - `Settings/get_settings.py` validiert diese Werte fail-fast, sobald der zentrale DH-Speicher aktiv ist
    - `integrated_energy_system.py` uebergibt Charge-/Discharge-Leistung als `*_kwh_per_step` an den Dispatch
    - `milp_day_ahead.py` und `milp_two_stage.py` begrenzen Speicherladung/-entladung nun ueber diese Leistungswerte, nicht mehr ueber die Energiekapazitaet
  - Paper-Overrides:
    - aktive `*paper_day_ahead*.json` nutzen jetzt den Wiener Speicheranker:
      - `installed_kwh_th_max = 850000`
      - `max_charge_kw_th = 145000`
      - `max_discharge_kw_th = 145000`
    - alte Override-Dateien mit DH-Speicher erhielten explizite Legacy-Power-Werte, damit die neue Validierung nicht durch fehlende Settings, sondern nur durch bewusst gesetzte Annahmen laeuft
  - Fig. 12:
    - Hauptwoche auf eine kaeltere Winterwoche ab `2023-02-05` gesetzt
    - Cold-week-Gegenstueck bleibt `2023-01-15`
    - Speicherentladung ist nun auf `145 MW` gedeckelt; der fruehere `>500 MW` Ein-Stunden-Artefakt ist entfernt
  - Neue KPI-Schnellpruefung:
    - Winterwoche `2023-02-05`: Cost `-0.0089 %`, CO2 `-0.0298 %`, Peak-boiler energy `-0.0690 %`, Peak-boiler peak `-0.0470 %`
    - Cold week `2023-01-15`: Cost `-0.0094 %`, CO2 `-0.0250 %`, Peak-boiler energy `-0.0450 %`, Peak-boiler peak `+0.0000 %`
  - Interpretation:
    - Waste ist in beiden Wochen durchgehend mit `160 MW` sichtbar
    - Fig.-12-Stackueberdeckung ist kleiner bzw. besser erklaerbar, aber die Bruttoerzeugungs-/Spillage-Semantik bleibt als separate Plot-Bereinigung offen
- 2026-04-29: Gas-CHP- und Peak-Boiler-Groessenordnung fuer Fig. 12 geprueft.
  - Aktiver Paper-Override:
    - Gas-CHP `675,590 MW_el`, `eta_el = 0,55`, `eta_th = 0,30`
    - daraus `~368,5 MW_th` maximale DH-Waerme
    - das passt grob zum offiziellen KWK-Waermeanker `2,5696 TWh/a`, wenn man `~7500 h/a` annimmt (`~343 MW_th`)
  - Fig.-12-Winterwochen:
    - Gas-CHP laeuft in der Referenz bereits permanent am thermischen Maximum
    - hoher Boileranteil kommt daher nicht von zu geringer CHP-Nutzung, sondern von hoher Winter-DH-Buslast relativ zu den gesetzten Baselastquellen
  - Peak-Boiler-Ueberdeckung:
    - Restueberdeckung im Stack wurde auf `district_gas_boiler.min_partload = 0.15` zurueckgefuehrt
    - bei `2,2 GW_th` Aggregatkapazitaet erzwingt das `330 MW_th` Mindestoutput, sobald der Boiler an ist
    - fuer einen modularen aggregierten Spitzenkesselpark ist das zu grob
    - Paper-Day-Ahead-Overrides wurden auf `district_gas_boiler.min_partload = 0.0` gesetzt
    - Fig. 12 wurde danach neu gerechnet:
      - Winterwoche `2023-02-05`: rote/Stack-Ueberdeckung max. nur noch `~1,3 MW`, Wochenueberdeckung `~92,8 MWh`
      - Cold week `2023-01-15`: max. `~0,6 MW`, Wochenueberdeckung `~92,8 MWh`
    - die verbleibende kleine Ueberdeckung ist nicht mehr der Peak-Boiler-Mindestlastblock, sondern Plot-/Speicherverlust-/Bruttostack-Semantik und sollte in der geplanten Fig.-12-Stackbereinigung mit erledigt werden
- 2026-04-29: Wiener Gas-CHP-Waermekapazitaet recherchiert und Fig. 12 erneut geschnitten.
  - Quellenbefund:
    - Simmering 1 liegt je nach Quelle bei `450-500 MW_th`
    - Simmering 2 `150 MW_th`
    - Simmering 3 `350-450 MW_th`
    - Donaustadt aktuell `350 MW_th`
    - Leopoldau historisch `~170 MW_th`
    - damit ist `~1,4-1,6 GW_th` fuer den Gas-/KWK-Waermeblock plausibler als der bisherige `~368 MW_th` Proxy
  - Paper-Day-Ahead-Overrides:
    - Gas-CHP vorerst als heat-available Fixed-Ratio-Proxy gesetzt:
      - `installed_kw_el_max = 1.44 GW`
      - `eta_el = 0.40`
      - `eta_th = 0.45`
      - daraus `~1.62 GW_th`
    - dieser Schnitt ist ein Zwischenproxy, nicht die finale Gas-CHP-Methodik
  - Methodischer Befund:
    - milde Februarwochen sind mit der hoeheren CHP-Kapazitaet fuer Fig. 12 ungeeignet, weil die Brutto-CHP-Waerme die DH-Buslast uebersteigen kann
    - Fig. 12 wurde deshalb auf echte kalte Januarwochen umgestellt:
      - Hauptwoche `2023-01-15`
      - Vergleichswoche `2023-01-22`
    - die Fig.-12-Auswertung setzt ausserdem `district_thermal_storage.initial_soc_fraction = 0.0`, damit keine kostenlose Anfangsspeicherenergie die ersten Stunden dominiert
  - Aktuelle Schnellpruefung:
    - Woche `2023-01-15`: CHP `~260 GWh`, Boiler `~13.0 GWh`, Boileranteil `~3.9 %`
    - Woche `2023-01-22`: CHP `~255 GWh`, Boiler `~7.7 GWh`, Boileranteil `~2.4 %`
  - Offener Punkt:
    - der saubere Endzustand bleibt ein getrennter Gas-CHP-Kapazitaets-/Betriebsmoduspfad; `grid_import_cost` darf fuer reine DH-Paper-Zahlen nicht versteckt den CHP-Einsatz treiben
- 2026-04-29: Wiener Spitzen-/Reservekessel-Leistungsanker dokumentiert.
  - Quellenbefund:
    - Wien-Energie-/Fernheizwerk-Angaben nennen fuer die relevanten Spitzen-/Reserveanlagen:
      Spittelau `400 MW_th`, Arsenal `340 MW_th`, Kagran `200 MW_th`, Inzersdorf `340 MW_th`, Leopoldau `170-230 MW_th`
    - daraus ergibt sich ein installierter Plausibilitaetsbereich von `~1,45-1,51 GW_th` inklusive Leopoldau
    - der offizielle 2023-Energieanker `Spitzenkessel = 522,3 GWh/a` ist damit konsistent:
      bei `~1,45 GW_th` entspricht das rund `360` Vollbenutzungsstunden
  - Dokumentation:
    - Quellenanker in `Documentation/Sources/wien_und_dispatch_quellen.md` ergaenzt
    - TODO korrigiert: der bisherige `2,2 GW_th` Wert bleibt nur als alter winter-fit Benchmark-Proxy und soll nicht als historische Wien-Kesselleistung interpretiert werden
- 2026-04-29: Aktive Paper-Day-Ahead-Overrides auf Wiener Peak-Boiler-Kapazitaetsanker umgestellt.
  - Geaendert:
    - alle aktiven `*paper_day_ahead*.json`-Overrides im Thermflex-Ordner setzen `district_gas_boiler.installed_kw_th_fixed/max` nun auf `1.450.000 kW_th`
    - Fig.-12-Cache-Version wurde erhoeht und beide Fig.-12-Wochen wurden neu gerechnet
  - Schnellcheck der neuen Fig.-12-CSV:
    - Woche `2023-01-15`: DH-Bus-Peak `2339,7 MW`, Peak-Boiler-Peak `355,9 MW`, Peak-Boiler-Energie `12.973 -> 12.879 MWh`, Cost `-0,0107 %`, CO2 `-0,0195 %`
    - Woche `2023-01-22`: DH-Bus-Peak `2428,4 MW`, Peak-Boiler-Peak `444,6 MW`, Peak-Boiler-Energie `7.734 -> 7.740 MWh`, Cost `-0,0003 %`, CO2 `-0,0351 %`
  - Interpretation:
    - die reduzierte installierte Boiler-Kapazitaet bindet in diesen kalten Wochen nicht; der tatsaechliche Boiler-Peak bleibt deutlich unter `1,45 GW_th`
    - `2,2 GW_th` wird fuer diese Paper-Figuren nicht mehr benoetigt
- 2026-04-29: Gas-CHP-Zwischenproxy fuer Fig. 12 auf CCGT-naehere Wirkungsgrade korrigiert.
  - Geaendert:
    - alle aktiven `*paper_day_ahead*.json`-Overrides setzen `district_gas_chp.eta_el = 0,55` und `eta_th = 0,30`
    - bei `1,44 GW_el` ergibt das `~785 MW_th` Waerme statt der vorherigen `~1,62 GW_th`
    - Fig.-12-Cache-Version erhoeht und beide Fig.-12-Wochen neu gerechnet
  - Schnellcheck:
    - Woche `2023-01-15`: DH-Bus-Peak `2339,7 MW`, Gas-CHP `785,5 MW` konstant, Peak-Boiler-Peak `1190,5 MW`, Peak-Boiler-Energie `138,9 -> 138,8 GWh`, Cost `-0,0109 %`, CO2 `-0,0189 %`
    - Woche `2023-01-22`: DH-Bus-Peak `2428,4 MW`, Gas-CHP `785,5 MW` konstant, Peak-Boiler-Peak `1279,2 MW`, Peak-Boiler-Energie `127,7 -> 127,6 GWh`, Cost `-0,0115 %`, CO2 `-0,0194 %`
  - Interpretation:
    - die kalten Wochen bleiben ohne `dh_unserved_heat` loesbar und nutzen den Peak-Boiler sichtbar, aber unter dem `1,45 GW_th` Wien-Anker
    - final fachlich besser bleibt ein echter piecewise `power_led` / `heat_led` Gas-CHP-Pfad statt eines starren Fixed-Ratio-Proxys
- 2026-04-29: Gas-CHP-Zwischenproxy fuer Fig. 12 auf balancierten Mischbetrieb gesetzt.
  - Grund:
    - der reine CCGT-/stromgefuehrte Proxy `eta_el = 0,55`, `eta_th = 0,30` senkte Gas-CHP-Waerme auf `~785 MW_th` und liess den Peak-Boiler in Fig. 12 wieder zu stark erscheinen
  - Geaendert:
    - alle aktiven `*paper_day_ahead*.json`-Overrides setzen `district_gas_chp.eta_el = 0,50` und `eta_th = 0,35`
    - bei `1,44 GW_el` ergibt das `~1,01 GW_th` Waerme
    - Fig.-12-Cache-Version erhoeht und beide Fig.-12-Wochen neu gerechnet
  - Schnellcheck:
    - Woche `2023-01-15`: DH-Bus-Peak `2339,7 MW`, Gas-CHP `1008,0 MW` konstant, Peak-Boiler-Peak `967,9 MW`, Peak-Boiler-Energie `101,5 -> 101,5 GWh`, Cost `-0,0109 %`, CO2 `-0,0190 %`
    - Woche `2023-01-22`: DH-Bus-Peak `2428,4 MW`, Gas-CHP `1008,0 MW` konstant, Peak-Boiler-Peak `1056,6 MW`, Peak-Boiler-Energie `90,3 -> 90,2 GWh`, Cost `-0,0115 %`, CO2 `-0,0195 %`
  - Interpretation:
    - dieser Zwischenproxy balanciert die Fig.-12-Erzeuger optisch/fachlich besser als die beiden Extremvarianten
    - final soll der starre Fixed-Ratio-Proxy trotzdem durch einen echten piecewise `power_led` / `mixed` / `heat_led` Dispatchpfad ersetzt werden
- 2026-04-29: Zusaetzliche Fig.-12-Vergleichswochen fuer November und Maerz erzeugt.
  - Fig.-12-Builder erweitert um:
    - `fig_12_november_weekly_dispatch_shift.png/csv`, Start `2023-11-01`, um den Top-Savings-Tag `2023-11-04`
    - `fig_12_march_weekly_dispatch_shift.png/csv`, Start `2023-03-01`, um den starken Savings-Tag `2023-03-04`
  - Gemeinsame aktive Annahmen:
    - DH-Bus-Traegheit `tau_h = 4`
    - Speicher `850 MWh` / `145 MW`
    - Gas-CHP `1,44 GW_el`, `eta_el = 0,50`, `eta_th = 0,35` (`~1,01 GW_th`)
    - Peak-Boiler `1,45 GW_th`
  - Wochenvergleich:
    - `2023-01-15`: Bus-Peak `2339,7 MW`, Boiler `101,5 -> 101,5 GWh`, Cost `-0,011 %`, CO2 `-0,019 %`
    - `2023-01-22`: Bus-Peak `2428,4 MW`, Boiler `90,3 -> 90,2 GWh`, Cost `-0,012 %`, CO2 `-0,019 %`
    - `2023-11-01`: Bus-Peak `1397,7 MW`, Boiler `1,21 -> 1,11 GWh`, Cost `-0,058 %`, CO2 `-0,077 %`
    - `2023-03-01`: Bus-Peak `1812,1 MW`, Boiler `8,18 -> 5,17 GWh`, Cost `-0,499 %`, CO2 `-0,826 %`, Boiler-Peak `-11,3 %`
- 2026-04-29: Fig.-12-Dispatchsemantik fuer Must-run-Quellen bereinigt.
  - Grund:
    - `district_external_heat` war bisher nur als frei dispatchbare Verfuegbarkeit modelliert und konnte deshalb stundenweise reduziert werden
    - fuer den Wien-Paperpfad soll industrielle/externe Abwaerme analog zu Waste als exogene Must-run-Waerme behandelt werden
  - Geaendert:
    - `DistrictExternalHeatConfig` um `must_run` erweitert und in den integrierten Dispatchparametern verdrahtet
    - `milp_day_ahead` und `milp_two_stage` setzen bei aktivem `must_run`: `external_heat_th + external_heat_spill == external_heat_available`
    - alle aktiven `*paper_day_ahead*.json`-Overrides setzen `district_external_heat.must_run = true`
    - Fig. 12 zeigt Stackflaechen nun bus-allokiert; Must-run-Verfuegbarkeit bleibt separat als Linie sichtbar
    - Heat Pump wurde in der Fig.-12-Reihenfolge zwischen Biomass CHP und External Heat gesetzt
  - Schnellcheck nach Rebuild:
    - alle vier Wochen haben `max(stack - DH bus load) = 0,0 MW`
    - External-Heat-Verfuegbarkeit bleibt in allen Wochen konstant `160 MW`
    - `2023-01-15`: Cost `-0,011 %`, CO2 `-0,019 %`, Peak-Boiler-Energie `-0,093 %`
    - `2023-01-22`: Cost `-0,012 %`, CO2 `-0,019 %`, Peak-Boiler-Energie `-0,104 %`
    - `2023-11-01`: Cost `-0,060 %`, CO2 `-0,079 %`, Peak-Boiler-Energie `-8,528 %`
    - `2023-03-01`: Cost `-0,616 %`, CO2 `-1,027 %`, Peak-Boiler-Energie `-46,110 %`, Peak-Boiler-Peak `-8,850 %`
- 2026-04-29: Fig.-12-Visualisierung nach inhaltlichem Check angepasst.
  - Problem:
    - proportionale Bus-Allokation skalierte auch Waste und External Heat optisch herunter, obwohl diese Quellen bei ausreichender Nachfrage als durchlaufende Einspeiser sichtbar bleiben sollen
  - Geaendert:
    - bus-allokierte Darstellung nutzt nun die Source-Reihenfolge/Merit-Order statt proportionaler Skalierung
    - Waste, Biomass CHP, Heat Pump und External Heat werden vor Gas-CHP, Speicherentladung und Peak-Boiler allokiert
    - Upper-only-Panel markiert jetzt zusaetzlich Preheat oberhalb der Referenz-Buslast und vermiedene Waerme unterhalb der Referenz-Buslast
- 2026-04-29: Fig.-12-Stackreihenfolge und Must-run-Darstellung finalisiert.
  - Geaendert:
    - alte Building-Demand-Linien aus den Dispatch-Panels entfernt
    - Stackreihenfolge gesetzt auf Waste Incineration, External Waste Heat, Biomass CHP, Heat Pump, Gas CHP, Thermal Storage Discharge, Peak Boiler
    - Waste und External Heat werden fuer die Visualisierung aus ihrer verfuegbaren Must-run-Waerme (`generation + spillage`) allokiert und erst gegen die DH-Buslast gekappt
  - Schnellcheck nach Rebuild:
    - alle vier Fig.-12-Wochen haben weiterhin `max(stack - DH bus load) = 0,0 MW`
    - `2023-03-01`: Waste bleibt durchgehend `160 MW`; External Heat wird nur gekappt, wenn Waste plus External ueber der Buslast laegen
    - `2023-11-01`: Waste faellt nur in Stunden unter `160 MW`, in denen die geglaettete DH-Buslast selbst unter `160 MW` liegt
- 2026-04-29: Sechs gute Monatswochen als Fig.-12-Dispatchvarianten erzeugt.
  - Kandidaten:
    - November `2023-11-04`
    - Dezember `2023-12-02`
    - Jaenner `2023-01-15`
    - Februar `2023-02-19`
    - Maerz `2023-03-15`
    - April `2023-04-01`
  - Methode:
    - Tages-Screening/Table-09-Logik nur als Kandidatenfilter genutzt
    - jede Woche danach als kontinuierlicher 168h REF-vs-upper-only Gold/MILP-Dispatch mit dem aktiven Fig.-12-Setup neu gerechnet
  - Outputs:
    - `fig_12_good_week_november_dispatch_shift.png/csv`
    - `fig_12_good_week_december_dispatch_shift.png/csv`
    - `fig_12_good_week_january_dispatch_shift.png/csv`
    - `fig_12_good_week_february_dispatch_shift.png/csv`
    - `fig_12_good_week_march_dispatch_shift.png/csv`
    - `fig_12_good_week_april_dispatch_shift.png/csv`
  - Schnellcheck:
    - alle sechs Wochen haben `max(stack - DH bus load) = 0,0 MW`
    - groesste aktive Wochenwirkung aktuell Februar (`Cost -0,514 %`, CO2 `-0,643 %`, Boiler-Energie `-29,240 %`) und Maerz (`Cost -0,448 %`, CO2 `-0,503 %`, Boiler-Energie `-32,933 %`)
  - Festgehalten:
    - unterschiedliche Buslasten zwischen Referenz und Upper-only sind erwartbar, weil ThermFlex die Gebaeudewaermelast verschiebt und die DH-Bus-Traegheit diese verschobene Last glättet
    - neue TODOs fuer gebaeudeseitige Speicherwaerme des Wiener DH-Bestands und fuer einen konsistenten Surrogat-Architekturschnitt ergaenzt

- 2026-04-29: Day-ahead-Preisprofil und Gas-CHP-Objective fuer DH-Dispatch korrigiert.
  - Problem:
    - Paper-Day-ahead-Overrides hatten keine `day_ahead_price`-Zeitreihe im Profil
    - der gekoppelte Dispatch fiel deshalb auf einen konstanten Verbrauchstarif zurueck
    - dadurch war das Gas-CHP-Power-Priority-Gate in jeder Stunde aktiv und CHP konnte unrealistisch als Baseload laufen
  - Geaendert:
    - `integrated_energy_system` laedt historische MC-Auction-Day-ahead-Preise aus `Settings.dispatch.historical_day_ahead_root`, wenn das Profil keine explizite `day_ahead_price` enthaelt
    - `grid_import_cost` und `grid_export_revenue` werden in den Objective-Terms nur noch ausgewiesen, wenn sie auch explizit im Dispatch-Objective aktiv sind
    - `gas_chp_electric_value` bewertet CHP-Strom nur noch in expliziten Stromspitzenstunden des Day-ahead-Gates
  - Schnellcheck:
    - Aprilwoche `2023-04-01` nutzt Day-ahead-Preise von ca. `80-152 EUR/MWh`; das CHP-Gate ist in `6/24` Tagesstunden aktiv
    - Aprilwoche: Waste und External Heat laufen durch, Gas-CHP bleibt in Stromspitzen, Peak-Boiler sinkt um ca. `4,7 %`, CO2 um ca. `1,25 %`, Netto-Kosten um ca. `22,8 %`
    - Januarwoche `2023-01-15`: Kosten ca. `-0,33 %`, CO2 ca. `-0,21 %`; Peak-Boiler-Energie steigt leicht, Gas-CHP-Waerme sinkt, daher als Trade-off-/Kaltwochenfall weiter pruefen
  - Fig.-12-Rebuild:
    - alle Fig.-12-Cache-Versionen auf den Day-ahead-/CHP-Gate-Stand angehoben und neu gerechnet
    - Stack-Balance geprueft: keine Quelle liegt oberhalb der DH-Buslast
    - neue gute Monatswochen-KPIs:
      - November `2023-11-04`: Cost `-3,308 %`, CO2 `-1,340 %`, Boiler-Energie `-2,868 %`, Boiler-Peak `-1,533 %`
      - Dezember `2023-12-02`: Cost `-0,987 %`, CO2 `-0,498 %`, Boiler-Energie `+2,190 %`, Boiler-Peak `0,000 %`
      - Jaenner `2023-01-15`: Cost `-0,328 %`, CO2 `-0,207 %`, Boiler-Energie `+1,048 %`, Boiler-Peak `0,000 %`
      - Februar `2023-02-19`: Cost `-1,428 %`, CO2 `-0,263 %`, Boiler-Energie `-1,435 %`, Boiler-Peak `0,000 %`
      - Maerz `2023-03-15`: Cost `-2,222 %`, CO2 `-0,282 %`, Boiler-Energie `-2,060 %`, Boiler-Peak `0,000 %`
      - April `2023-04-01`: Cost `-22,801 %`, CO2 `-1,248 %`, Boiler-Energie `-4,674 %`, Boiler-Peak `-1,110 %`

- 2026-04-30: Fig.-12-/Dispatch-Basis nach Plausibilitaetscheck auf stabileren Gas-CHP-Pfad zurueckgeschnitten.
  - Problem:
    - `piecewise_power_heat_v1` mit stuendlichem Power-Gate erzeugte im April optisch und fachlich zu harte Gas-CHP-/Peak-Boiler-Spruenge
    - reiner Rueckfall ohne CHP-Stromwert machte Gas-CHP wiederum zu unattraktiv gegenueber Peak-Boiler
  - Aktiver Paper-Pfad:
    - `district_gas_chp.operating_mode_model = fixed_ratio`
    - `district_gas_chp.power_priority_mode = free`
    - `dispatch.objective_components = gas_chp_electric_value + fuel_cost + co2_cost + variable_opex`
    - `constraints.dispatch.gas_chp_before_peak_boiler = true`
    - Day-ahead-Preisprofil, Waste-/External-Must-run und Grid-Import-Kostenbereinigung bleiben aktiv
  - Fig.-12-Darstellung:
    - Stack wird gegen `DH bus load + thermal storage/preheat charging` allokiert
    - DH-Buslast bleibt als Linie sichtbar
    - dadurch verschwindet freie Must-run-Waerme bei niedriger April-Buslast nicht mehr optisch
  - April-Schnellcheck:
    - Gas-CHP ist wieder Mittellast (`~44 -> 47 GWh_th` pro Woche)
    - Peak-Boiler bleibt absolut klein (`0,27 -> 0,72 GWh_th`), auch wenn Prozentwerte wegen kleiner Referenzbasis gross wirken
    - Kosten `-10,6 %`, CO2 `-2,0 %`

- 2026-04-30: Fig.-12-Plotsemantik ohne DH-Speicher neu gerendert.
  - Geaendert:
    - `Thermal storage discharge` aus der Fig.-12-Source-Stack-Darstellung entfernt
    - Heat-Sink-/Storage-Charging-Linie und Storage-Sink-Flaeche aus den Panels entfernt
    - Source-Stack wieder strikt auf die DH-Buslast allokiert
    - Cache-Versionen auf `no_storage_plot_v1` angehoben und alle Wochenvarianten neu gerechnet
  - Schnellcheck:
    - alle Fig.-12-CSV-Dateien haben `max(stack - DH bus load) = 0.000 MW` in Referenz und Flex
    - April `2023-04-01`: Referenz liegt in `57 h` unter Waste+External-Availability, Flex nur in `31 h`
    - April-Preheat waehrend solcher Referenz-Low-Waste-Stunden: `7.611 GWh`
    - April-Gas-CHP sinkt in Release-Stunden um `2.836 GWh`, steigt ueber die Gesamtwoche aber um `1.067 GWh`; der Mechanismus ist daher sichtbar, aber noch keine saubere Wochen-Netto-Gas-CHP-Reduktion

- 2026-04-30: April-Fig.-12 nach White-Gap-Diagnose korrigiert.
  - Diagnose:
    - das Entfernen der Speicherentladung aus dem Stack erzeugte scheinbar unerfuellte DH-Buslast
    - die Luecke entsprach exakt der aktiven Speicherentladung (`max 145 MW`, April `6.411 GWh` Referenz / `7.574 GWh` Flex)
  - Korrektur:
    - Speicherentladung wieder als neutrale Bus-Deckungsquelle `DH buffer discharge` im Stack aufgenommen
    - Speicherladung / Heat-Sink-Flaechen bleiben entfernt
    - nur `fig_12_good_week_april_dispatch_shift.*` neu gerendert
  - Check:
    - April-Stack stimmt jetzt mit DH-Buslast ueberein (`max gap/overlap` nur numerisches Rauschen)

- 2026-04-30: DH-Speicher-Deaktivierung fuer Dispatch-Pfade gehaertet und April ohne Speicher getestet.
  - Problem:
    - `technology_activation.district_thermal_storage = false` setzte Charge/Discharge auf null, reichte aber weiterhin eine positive Speicherkapazitaet an den MILP-Dispatch durch
    - dadurch wurde der Speicher als aktiv interpretiert; bei null Charge/Discharge bzw. positiven Standverlusten konnte der No-Storage-Pfad infeasible werden
  - Geaendert:
    - `integrated_energy_system` exportiert `district_thermal_storage_kwh_th = 0`, wenn der Speicher deaktiviert ist
    - `milp_day_ahead` setzt DH-Speicherverluste auf `0`, wenn die Speicherkapazitaet `0` ist
    - Fig. 12 deaktiviert den DH-Speicher nun im temporaeren Plot-Override und rendert April ohne Speicher-Stack
  - April-Schnellcheck ohne zentralen DH-Speicher:
    - Stack deckt DH-Buslast ohne Luecken (`max gap/overlap` nur numerisches Rauschen)
    - Kosten `-17.259 %`, CO2 `-2.469 %`, Peak-Boiler-Energie `-3.029 %`, Peak-Boiler-Peak `-1.268 %`
    - Gas-CHP-Waerme `29.324 -> 29.100 GWh`, Peak-Boiler-Waerme `16.462 -> 15.963 GWh`
  - Nachpruefung:
    - der hohe Peak-Boiler-Anteil war durch eine temporaere Abschaltung von `gas_chp_before_peak_boiler` im Fig.-12-No-Storage-Test verursacht
    - mit aktivierter Merit-Order-Guardrail ist April ohne Speicher weiterhin optimal loesbar und der Peak-Boiler verschwindet (`0 GWh` Referenz/Flex)
    - neue April-Werte: Kosten `-15.503 %`, CO2 `-4.601 %`, Peak-Boiler-Energie/Pipe-Peak `-100 %`, Gas-CHP-Waerme `45.943 -> 44.826 GWh`

- 2026-04-30: Fig.-12-Monatswochen auf No-Storage-v2-Basis neu gerechnet.
  - Basis:
    - zentraler DH-Speicher im temporaeren Fig.-12-Override inaktiv
    - `gas_chp_before_peak_boiler` bleibt aktiv
    - Cache-Version `no_dh_storage_v2`
  - Balancecheck:
    - alle Fig.-12-CSV-Dateien haben `max(|stack - DH bus load|) = 0.000 MW` fuer Referenz und Flex
  - Monatswochen-KPI-Schnellcheck:
    - November good week: Cost `-3.250 %`, CO2 `-2.095 %`, Boiler-Energie `-53.821 %`
    - Dezember good week: Cost `-0.266 %`, CO2 `-0.051 %`, Boiler-Energie `-0.338 %`
    - Jaenner good week: Cost `-0.029 %`, CO2 `-0.019 %`, Boiler-Energie `-0.093 %`
    - Februar good week: Cost `-1.251 %`, CO2 `-0.419 %`, Boiler-Energie `-4.224 %`
    - Maerz good week: Cost `-3.101 %`, CO2 `-1.763 %`, Boiler-Energie `-10.317 %`
    - April good week: Cost `-15.503 %`, CO2 `-4.601 %`, Boiler-Energie `-100.000 %` bei `0 GWh` Boiler-Referenz/Flex

- 2026-04-30: Rolling-48/24-Dispatchpfad implementiert und April-Fig.-12 testweise neu gerechnet.
  - Code:
    - `dispatch.rolling_commit_h` als explizite Setting ergaenzt; Default `0` erhaelt den bisherigen nicht-ueberlappenden Blockbetrieb
    - `integrated_energy_system` loest bei `horizon_h > rolling_commit_h` den Lookahead-Horizont, uebernimmt aber nur die committed Stunden
    - ThermFlex-Zustand wird nach dem committed Ende weitergereicht, nicht nach dem Lookahead-Ende
    - Objective-Terms werden fuer Rolling aus committed hourly objective series aufsummiert, damit Lookahead-Kosten nicht doppelt gezaehlt werden
  - Fig.-12-April-Test:
    - temporaerer Fig.-12-Pfad: `horizon_h = 48`, `rolling_commit_h = 24`, DH-Speicher inaktiv
    - Stack-Balance bleibt sauber (`max |stack - DH bus load|` nur numerisches Rauschen)
    - April-KPIs: Cost `+4.365 %`, CO2 `-6.339 %`, Boiler `0 GWh` Ref/Flex
    - Apr-4/Apr-5-Uebergang nutzt trotz Lookahead weiterhin nicht die volle Waste+External-Kapazitaet in den tiefen Nachtstunden; daher sind Event-/Heizleistungsgrenzen als naechster Engpass wahrscheinlicher als reine 24h-Myopie

- 2026-04-30: Event-Bounds fuer April-Fig.-12 testweise gelockert.
  - Temporärer Fig.-12-Pfad:
    - `horizon_h = 48`, `rolling_commit_h = 24`
    - DH-Speicher inaktiv
    - `enforce_event_peak_bounds = false`
    - `enforce_event_energy_bounds = false`
    - `enforce_recovery_cooldown = false`
    - physikalisches `q_heat_max` bleibt aktiv
  - Ergebnis:
    - Waste und External Heat werden am Apr-4/Apr-5-Uebergang voll genutzt
    - Preheat wird aber sehr aggressiv und zieht viel Gas-CHP in die Vorheizstunden
    - April-KPIs: Cost `+9.012 %`, CO2 `-14.853 %`, Boiler weiterhin `0 GWh`
    - Gas-CHP-Waerme steigt `45.943 -> 57.174 GWh`
  - Interpretation:
    - die bisherigen Event-Bounds waren tatsaechlich ein Engpass fuer Waste-Nutzung
    - vollstaendiges Entfernen der Bounds ist fachlich zu offen; naechster sinnvoller Schritt waere ein lockerer, aber nicht unbeschraenkter Preheat-Pfad oder eine klarere Objective-Gewichtung fuer Kosten/CO2/Peak

- 2026-04-30: ThermFlex-Event-Bounds wieder aktiviert und moderat parametrierbar gemacht.
  - Code:
    - neue `constraints.thermflex`-Settings fuer Event-Bound-Multiplikatoren:
      - `event_preheat_peak_bound_multiplier`
      - `event_preheat_energy_bound_multiplier`
      - `event_cutback_peak_bound_multiplier`
      - `event_cutback_energy_bound_multiplier`
    - Default bleibt jeweils `1.0`; damit aendert sich bestehendes Verhalten nur bei explizitem Override
    - Fig. 12 nutzt testweise `1.25x` fuer Preheat-Peak und Preheat-Energie, Bounds und Cooldown bleiben aktiv
  - April-Schnellcheck:
    - Stack-Balance sauber (`max |stack - DH bus load|` nur numerisches Rauschen)
    - April-KPIs: Cost `+4.385 %`, CO2 `-6.456 %`, Boiler `0 GWh` Ref/Flex
    - Gas-CHP-Waerme `45.943 -> 45.031 GWh`
  - Interpretation:
    - 1.25x ist ein Zwischenpfad zwischen zu strengen Bounds und komplett offenen Event-Bounds
    - Gas-CHP-Spitzen bleiben weiter ein methodischer Punkt; `gas_chp_electric_value` sollte als KWK-Koproduktwert transparent gefuehrt oder als Sensitivitaet geprueft werden

- 2026-04-30: ThermFlex-Recovery-Cooldown als expliziten Regler ergänzt und April-Fig.-12 mit 12h getestet.
  - Code:
    - `constraints.thermflex.event_recovery_cooldown_h` ergänzt
    - `None` behält die alte Logik `max_flex_duration_h + recovery_time_to_reference_h`
    - explizite Werte überschreiben die alte Logik; Fig. 12 nutzt testweise `12`
  - April-Schnellcheck:
    - Cost `+4.602 %`, CO2 `-6.458 %`, Boiler `0 GWh` Ref/Flex
    - Gas-CHP-Wärme `45.943 -> 45.513 GWh`
    - Waste/External-Tal am Apr-4/Apr-5-Übergang bleibt weitgehend bestehen
  - Interpretation:
    - der alte 25h-Cooldown war nicht der alleinige Engpass
    - wahrscheinlich wirken Event-Energy-Bounds, Tages-/Rolling-Commit-Grenzen, DH-Bus-Inertia und das strompreisbasierte CHP-Objective gemeinsam
    - Gas-CHP-Ramp-/Glättungsannahmen bleiben fachlich abzustimmen und wurden nicht eingeführt

- 2026-04-30: Harte Diagnose zum Apr-4/Apr-5-Waste-Tal ohne Plot-Rendering.
  - Befund 1:
    - `therm_event_start` war nur nach unten an `therm_flex_active` gekoppelt
    - dadurch konnte der MILP-Solver Phantom-Event-Starts setzen, ohne dass Flex aktiv ist
    - das verzerrte Event-Energy-Budgets und Cooldown-Logik
    - minimaler Fix in `milp_day_ahead`: Event-Start muss nun zugleich aktiv sein und darf nur an der steigenden Flanke auftreten
  - Befund 2:
    - 48h-Apr-4/5-Isolation mit `gas_chp_electric_value` zeigt im Waste-Tal kein Preheat (`q_heat = q_ref = 0` in den Nachtstunden)
    - identischer 48h-Test ohne `gas_chp_electric_value` verschiebt Preheat genau in die Abend-/Nachtstunden mit freier Waste/External-Waerme
    - harte Schlussfolgerung: Der CHP-Stromwert ist der dominante Grund, warum der Optimierer freie Abwaerme nicht zum Vermeiden spaeterer Gas-CHP-Waerme nutzt
  - Methodische Konsequenz:
    - fuer den DH-Waerme-Hauptpfad sollte `gas_chp_electric_value` nicht ungebremst im Waerme-Objective stehen
    - sinnvoller: Hauptpfad ohne CHP-Stromwert fuer Waermekosten/CO2; CHP-Stromwert separat berichten oder als Sensitivitaet / power-led Betriebsmodus behandeln

- 2026-04-30: Fig. 12 April mit Must-run-Abwaerme-Prioritaet neu gerechnet.
  - Modellpfad:
    - `gas_chp_electric_value` wieder im Objective, damit CHP-Koproduktwert und MILP-Fuehrung erhalten bleiben
    - `must_run_heat_spill_penalty_eur_per_kwh = 1.0` fuer Fig. 12 gesetzt
    - `allow_gas_chp_thermal_spill = false` fuer Fig. 12 gesetzt, damit Gas-CHP-Stromwert nur aus waermeseitig genutzter CHP-Waerme entstehen kann
    - Upper-only: Event-Energy-Bound und Recovery-Cooldown aus, Preheat-Peak-Bound `1.25x` aktiv
  - Ergebnis:
    - voller April-Wochenrender laeuft wieder durch
    - Stack-Balance sauber (`max |stack - DH bus load|` nur numerisches Rauschen)
    - Waste/External werden am Apr-4/5-Uebergang durchgehend genutzt
    - April-KPIs: Cost `+40.076 %`, CO2 `-24.522 %`, Boiler-Energie/Pipe-Peak ~`-100 %`
  - Hinweis:
    - CO2-Mechanik sieht stark aus, aber Cost-KPI ist fuer diesen Pfad methodisch erneut zu pruefen, weil Must-run-Spillage-Penalty und CHP-Koproduktwert die Kosteninterpretation sichtbar veraendern

- 2026-04-30: DH-Spillage-Bilanz korrigiert und Fig. 12 April auf Waerme-Hauptpfad neu gerechnet.
  - Befund:
    - thermische `*_spill`-Terme standen in der DH-Bilanz auf der Nachfrageseite, obwohl `*_th` bereits die genutzte Waerme darstellt
    - dadurch entstanden Artefakte wie negative Netto-Erzeuger und ein zu schwer interpretierbarer Dispatch
  - Code:
    - thermische Spillage aus der DH-Bilanz und dem DH-Residual entfernt
    - `gas_chp_electric_value` fuer Fig. 12 wieder aus dem Hauptobjective entfernt
    - `must_run_heat_spill_penalty_eur_per_kwh = 1.0`, `allow_gas_chp_thermal_spill = false`
    - kleiner Tie-Breaker `thermflex_heat_deviation_penalty_eur_per_kwh = 1e-4` eingefuehrt
  - April-Ergebnis:
    - voller Fig.-12-April-Render laeuft wieder durch
    - Waste/External laufen am Apr-4/5-Uebergang sichtbar durch
    - Flex: Gas-CHP `44.62 GWh`, Boiler praktisch `0`, Waste `26.88 GWh`, External `26.83 GWh`
    - KPI: Cost `+3.62 %`, CO2 `-10.96 %`
  - Hinweis:
    - Referenz-Stackplot hat noch eine kleine Darstellungsdifferenz bis ca. `1.9 MW`, wahrscheinlich weil die Fig.-12-Stackquellen nicht alle kleinen Waermequellen/Spill-Semantiken visualisieren; Modellresidual ist separat zu pruefen

- 2026-05-01: ThermFlex-Cost-KPI fuer DH-Waermefall geklaert.
  - Befund:
    - `dispatch_operating_cost_eur` enthaelt den allgemeinen `grid_import_cost_eur`-Proxy und ist daher fuer die reine Fernwaerme-Kostenstory ungeeignet
    - im Apr-4/5-48h-Smoke stieg `dispatch_operating_cost_eur` um `+0.77 %`, obwohl `fuel_cost_eur`, `co2_cost_eur`, Gas-CHP-Waerme und Emissionen sanken
  - Code:
    - `dispatch_heat_operating_cost_eur = fuel_cost_eur + co2_cost_eur + variable_opex_eur` als explizites Waermebetriebskosten-KPI ergaenzt
    - Fig. 12 und Table-13-Helfer nutzen fuer Paper-Cost-Delta nun dieses Waerme-KPI statt des Grid-belasteten Operating-Cost-KPI
  - Apr-4/5-48h-Smoke:
    - `dispatch_heat_operating_cost_eur` `1.3697 -> 1.3264 Mio. EUR` (`-3.16 %`)
    - `fuel_cost_eur` `-3.07 %`
    - `co2_cost_eur` `-3.38 %`
    - `co2_emissions_total_t` `-2.08 %`
 
- 2026-05-01: Fig. 12 Wochenrender robuster gemacht, ohne methodische Dispatch-Settings zu aendern.
  - Statuscheck der vorhandenen Fig.-12-CSV:
    - aktiv gueltig: `jan_cold_1`, `jan_cold_2`, `good_apr`
    - vorhanden, aber nicht auf aktiver Heat-Cost-Cache-Version: `november_savings`, `march_savings`, `good_nov`, `good_dec`, `good_jan`, `good_feb`, `good_mar`
  - Code:
    - `build_fig_12_weekly_dispatch_shift.py` speichert Ref/Flex-Zeitreihen nun separat als validierte `.npz`-Caches je Variante und Case
    - Cache-Metadaten enthalten Startdatum, Variante, Override, Rolling-Horizon/Commit, DH-Bus-Inertia, Storage-Schalter und Cache-Version; Abweichungen brechen explizit ab
    - CLI ergaenzt: `--list-variants` und wiederholbares `--variant <slug>`, damit einzelne Wochen gezielt statt pauschal neu gerechnet werden koennen
  - Motivation:
    - wenn ein langer Flex-MILP-Lauf, z.B. November, spaet abbricht, bleibt eine bereits gerechnete Ref-Serie erhalten und der naechste Lauf setzt auf Case-Ebene fort
    - Rolling-Block-Caching wurde bewusst noch nicht eingefuehrt, weil dafuer tiefer in Dispatch/Engine eingegriffen werden muesste

- 2026-05-01: Einzelrender `fig_12 --variant good_feb` versucht.
  - Ergebnis:
    - der Referenz-Case wurde erfolgreich als Seriencache gespeichert
    - der Flex-Case lief nach mehr als drei Stunden weiter, ohne CSV/PNG zu aktualisieren
    - der gestartete Python-Prozess wurde beendet, damit kein langer MILP-Lauf im Hintergrund weiterrechnet
  - Konsequenz:
    - `good_feb` ist unter dem aktiven 48/24h-Fig.-12-Pfad noch nicht neu gerendert
    - naechster sinnvoller Schritt ist ein gezielter Flex-Diagnoselauf oder ein tieferes Rolling-Block-Resume, bevor weitere Wochen pauschal gestartet werden

- 2026-05-04: `good_feb`-Runtime-Diagnose fuer Fig. 12 durchgefuehrt.
  - Befund:
    - alter Februar-Plot stammt aus `fig12_good_monthly_week_bus_tau4_fixed_ratio_chp_revenue_no_dh_storage_v2_feb`
    - aktueller Zielpfad ist `heat_obj_mustrun_spill1_tiebreak_no_dh_storage_roll48_upper_only_peak_bounds125_v2_heat_cost`
    - der alte Plot war damit nicht derselbe methodische Pfad wie der aktuelle 48/24h-Heat-Cost-Pfad
  - A/B:
    - aktueller Code, `good_feb`, Flex, aber `horizon_h=24`, `profile_hours=24`: Solverzeit ca. `7.0 s`
    - aktueller Code, `good_feb`, Flex, `horizon_h=48`: Block 1/7 braucht ca. `551.6 s`
  - HiGHS-Kurzlauf mit 60s-Limit fuer den ersten 48h-Block:
    - MIP vor Presolve: `5776` Zeilen, `4856` Spalten, `720` Binärvariablen
    - nach Presolve: `2653` Zeilen, `2203` Spalten, `192` Binärvariablen
    - nach 60s: `4845` Nodes, `326255` LP-Iterationen, Gap `11.03 %`
    - HiGHS meldet stark gespreizte Koeffizienten (`1e-6` bis `3e+08`)
  - Interpretation:
    - der Runtime-Sprung ist reproduzierbar an den 48h-Lookahead gekoppelt
    - fuer `good_feb` ist 48h nicht nur doppelt so gross wie 24h, sondern loest ein deutlich schwereres Branch-and-Bound-Problem aus
    - bevor weitere Monatswochen unter 48/24h pauschal gestartet werden, sollte entschieden werden, ob Fig. 12 auf den frueheren 24h-Pfad zurueckgeht oder ob der 48h-Pfad gezielt mit Solver-/Modellskalierung stabilisiert wird

- 2026-05-04: Gas-CHP-Waermekostenallokation fuer Fig.-12-Objective vorbereitet.
  - Befund:
    - der aktuelle Heat-only-Fig.-12-Pfad bewertet Gas-CHP-Waerme mit vollem physischem Brennstoffinput, waehrend der Strom-Koproduktwert nicht im Hauptobjective enthalten ist
    - dadurch ist Gas-CHP-Waerme gegenueber Peak-Boiler-Waerme im Objective verzerrt teuer
  - Code:
    - `dispatch.modes.milp_day_ahead` ergaenzt die expliziten Objective-Komponenten `heat_allocated_fuel_cost` und `heat_allocated_co2_cost`
    - fixed-ratio-CHP nutzt `gas_chp_heat / (eta_el + eta_th)` fuer die Waermeallokation
    - piecewise-CHP allokiert mode-aware je Betriebspunkt ueber `sum_k heat_from_mode[k] / (eta_el[k] + eta_th[k])`
    - physische Exporte wie `district_gas_chp_fuel_input_kwh`, `district_gas_chp_co2_t`, `fuel_cost` und `co2_cost` bleiben unveraendert
    - Doppelzaehlung (`fuel_cost` plus `heat_allocated_fuel_cost`, bzw. `co2_cost` plus `heat_allocated_co2_cost`) bricht fail-fast ab
    - Fig. 12 schaltet testweise auf `heat_allocated_fuel_cost`, `heat_allocated_co2_cost`, `variable_opex` und eine neue Cache-Version um
  - Validierung:
    - `py -3 -m py_compile` fuer die geaenderten Python-Dateien erfolgreich
    - kleiner `dispatch_cost_model`-Smoke bestaetigt, dass allokierte Waermekosten in `dispatch_heat_operating_cost_eur` eingehen und Doppelzaehlung abbricht

- 2026-05-04: Piecewise-Gas-CHP-Smoke fuer Fig.-12-Diagnose ergaenzt.
  - Code:
    - `build_fig_12_weekly_dispatch_shift.py` hat nun `--piecewise-chp-smoke`, `--smoke-variant` und `--smoke-hours`
    - der Smoke aktiviert temporaer `district_gas_chp.operating_mode_model = piecewise_power_heat_v1` und `power_priority_mode = free`
    - es wird nur eine kurze Ref/Flex-Diagnose gerechnet und `fig_12_piecewise_chp_smoke.csv` geschrieben, kein Wochen-PNG
    - `integrated_energy_system.py` reicht `district_gas_chp_heat_allocated_fuel_input_kwh`, `district_gas_chp_heat_allocated_co2_t` und aktive heat-allocated Objective-Terme sauber durch
    - Rolling-/Block-Aggregation summiert nun nur aktive Objective-Komponenten plus echte Penalty-Terme, damit `fuel_cost` und `heat_allocated_fuel_cost` nicht gemeinsam in den KPI-Breakdown gelangen
  - Smoke:
    - Befehl: `py -3 Documentation/Papers/thermflex_paper/figures/build_fig_12_weekly_dispatch_shift.py --piecewise-chp-smoke --smoke-variant good_feb --smoke-hours 24`
    - Ref-Block: optimal, ca. `0.4 s`; Flex-Block: optimal, ca. `9.1 s`
    - Ref mode-share sums: power-led `2.846`, mixed `5.287`, heat-led `11.175`
    - Flex mode-share sums: power-led `7.339`, mixed `0.623`, heat-led `12.266`
    - Peak-boiler heat bleibt im 24h-Smoke gleich (`0.338 GWh`), CHP heat praktisch gleich (`24.21 -> 24.12 GWh`), CHP electricity steigt (`18.76 -> 20.90 GWh`)
  - Interpretation:
    - piecewise Mode Shares funktionieren technisch und werden vom MILP genutzt
    - der 24h-Smoke zeigt noch keine Peak-Boiler-Reduktion; bevor ein Wochenrender gestartet wird, sollte ein 36/48h-Smoke oder ein problematischer Morgenblock gezielt geprueft werden

- 2026-05-04: Physischer CO2-Tie-Breaker fuer Gas-CHP-Mode-Degeneracy ergaenzt und `good_feb`-Smokes gerechnet.
  - Befund:
    - bei gleichem Gesamtwirkungsgrad `0.85` sind `power_led`, `mixed` und `heat_led` in der heat-allocated Objective pro MWh Waerme gleich teuer
    - ohne weiteren Tie-Breaker kann der MILP physisch CO2-intensivere Mode-Mixe waehlen, obwohl die Waerme-Kostenobjective identisch ist
  - Code:
    - `constraints.dispatch.physical_co2_tiebreaker_eur_per_tco2` als explizites Setting ergaenzt
    - `milp_day_ahead` addiert den Term nur wenn das Setting positiv ist; Fig.-12-Diagnosepfad setzt `1e-4 EUR/tCO2`
    - der Piecewise-Smoke exportiert jetzt auch stündliche Diagnosewerte nach `fig_12_piecewise_chp_smoke_hourly.csv`
  - `good_feb`, 48h-Smoke:
    - Heat operating cost `4.6145 -> 4.6036 Mio. EUR` (`-0.237 %`)
    - physische CO2 `21.647 -> 21.610 kt` (`-0.169 %`)
    - Gas-CHP heat `44.236 -> 44.130 GWh` (`-0.241 %`)
    - Peak boiler energy/peak numerisch unveraendert (`0.338 GWh`, `71.3 MW`)
  - `good_feb`, 96h-Smoke:
    - Heat operating cost `7.6251 -> 7.6145 Mio. EUR` (`-0.139 %`)
    - physische CO2 `40.746 -> 40.605 kt` (`-0.346 %`)
    - Peak boiler energy/peak weiterhin numerisch unveraendert
  - Stündliche Diagnose:
    - der gesamte Boiler-Einsatz im 96h-Smoke liegt in den Stunden `2023-02-19 00:00` bis `06:00`
    - dort sind Ref/Flex identisch, Gas-CHP ist bereits bei `1440 MW_th` und im `heat_led`-Mode gesaettigt
    - Interpretation: verbleibender Boiler-Einsatz ist ein Profilstart-/Boundary-Effekt; ThermFlex kann vor dem Slice-Start nicht vorheizen

- 2026-05-04: Fig.-12-CO2-Systemgrenze auf Waermeallokation umgestellt.
  - Entscheidung:
    - fuer die Paper-Hauptfrage interessieren Kosten und CO2 des Fernwaerme-Waermeteils
    - physische Gesamt-CHP-CO2 bleiben Diagnose/Sensitivitaet, aber nicht Haupt-KPI
  - Code:
    - `dispatch_heat_allocated_co2_t` als explizites KPI aus `district_gas_chp_heat_allocated_co2_t + district_gas_boiler_co2_t` ergaenzt
    - `GoldEngine`, KPI-Engine und Reporting kennen das neue KPI
    - Fig. 12 nutzt fuer `co2_delta_pct` nun die waermeallokierte CO2-Systemgrenze
    - Fig.-12-Diagnosepfad setzt den physischen CO2-Tie-Breaker wieder auf `0.0`
    - Smoke-CSV berichtet getrennt `heat_allocated_co2_kt` und `physical_co2_emissions_kt`
  - `good_feb`, 96h plus 24h Warm-up, reine Waerme-Systemgrenze:
    - Peak boiler: Ref/Flex praktisch `0`
    - Heat operating cost `9.4840 -> 9.4734 Mio. EUR` (`-0.112 %`)
    - waermeallokierte CO2 `16.881 -> 16.849 kt` (`-0.192 %`)
    - physische Gesamt-CO2 steigen separat `32.649 -> 35.544 kt`, weil Flex deutlich mehr power-led/Strom-Koprodukt faehrt
  - Interpretation:
    - innerhalb der definierten Waerme-Systemgrenze zeigen Kosten und CO2 die erwartete Reduktion
    - der physische CO2-Anstieg ist kein Haupt-KPI-Widerspruch, sondern Folge der separaten Strom-Koprodukt-Systemgrenze

- 2026-05-04: Fig. 12 `good_feb` mit Warm-up und piecewise Gas-CHP neu gerendert.
  - Code:
    - der Hauptpfad von `build_fig_12_weekly_dispatch_shift.py` nutzt nun `FIGURE_WARMUP_HOURS = 24` und `FIGURE_GAS_CHP_PIECEWISE = True`
    - Ref/Flex-Serien werden 24h vor dem sichtbaren Wochenstart begonnen, danach auf die sichtbaren 168h getrimmt und erst dann in Cache/CSV geschrieben
    - die CSV traegt `data_schema_version`, `warmup_hours`, `gas_chp_piecewise` und `co2_kpi_boundary`, damit alte Dateien mit gleicher Modell-Cache-Version nicht still weiterverwendet werden
    - stundenweise Objective-Terme werden aus `integrated_energy_system.py` bis in den Analyse-Exporter durchgereicht; dadurch koennen Warm-up-Stunden sauber aus Kosten-KPIs herausgeschnitten werden
    - Fig.-12-Heat-Cost summiert bei heat-allocated Objective explizit nur `objective_heat_allocated_fuel_cost`, `objective_heat_allocated_co2_cost` und `objective_variable_opex`; physische `objective_fuel_cost`/`objective_co2_cost` bleiben Diagnose und werden nicht doppelt gezaehlt
  - Render:
    - Befehl: `py -3 Documentation/Papers/thermflex_paper/figures/build_fig_12_weekly_dispatch_shift.py --variant good_feb`
    - Ausgabe: `Documentation/Papers/thermflex_paper/figures/fig_12_good_week_february_dispatch_shift.png`
    - CSV: `Documentation/Papers/thermflex_paper/figures/fig_12_good_week_february_dispatch_shift.csv`
  - Ergebnis:
    - sichtbare Woche `2023-02-19` bis `2023-02-25`, mit 24h Warm-up ab `2023-02-18`
    - Heat operating cost `-0.345 %`
    - waermeallokierte CO2 `-0.399 %`
    - Peak boiler energy/peak `0.0 %`, weil Ref und Flex nach Warm-up praktisch keinen Peak-Boiler-Einsatz haben
    - Waste `26.880 -> 26.880 GWh`, External heat `26.521 -> 26.880 GWh`, Gas-CHP heat `120.514 -> 121.078 GWh`, Peak boiler `0.000 -> 0.000 GWh`
  - Hinweis:
    - der vorherige `+6 %`-Cost-Wert war ein CSV-Auswertungsfehler durch gleichzeitiges Summieren physischer und heat-allocated Objective-Reihen, nicht ein Optimierergebnis
    - weitere Wochen sollten selektiv per `--variant <slug>` laufen; nicht wieder pauschal alle Varianten starten

- 2026-05-04: Fig. 12 `good_jan` selektiv neu gerendert.
  - Befehl: `py -3 Documentation/Papers/thermflex_paper/figures/build_fig_12_weekly_dispatch_shift.py --variant good_jan`
  - Ausgabe: `Documentation/Papers/thermflex_paper/figures/fig_12_good_week_january_dispatch_shift.png`
  - CSV: `Documentation/Papers/thermflex_paper/figures/fig_12_good_week_january_dispatch_shift.csv`
  - Settings:
    - sichtbare Woche ab `2023-01-15`, 24h Warm-up ab `2023-01-14`
    - piecewise Gas-CHP aktiv
    - CO2-KPI: `heat_allocated_dispatch`
  - Ergebnis:
    - Heat operating cost `-0.032 %`
    - waermeallokierte CO2 `-0.036 %`
    - Peak-boiler energy `-0.361 %`
    - Waste `26.880 -> 26.880 GWh`, External heat `26.880 -> 26.880 GWh`, Gas-CHP heat `238.773 -> 238.792 GWh`, Peak boiler `30.597 -> 30.487 GWh`

- 2026-05-04: Fig. 12 `good_jan` mit hoeherem Peak-Boiler-OPEX getestet.
  - Motivation:
    - mit heat-allocated Gas-CHP-Kosten ist Peak-Boiler-Waerme wegen `eta_boiler = 0.90` gegenueber `eta_el + eta_th = 0.85` leicht guenstiger
    - fuer die Fig.-12-Mechanik soll der Peak-Boiler als teurere Spitzenquelle behandelt werden
  - Code:
    - `constraints.dispatch.district_gas_boiler_variable_opex_adder_eur_per_kwh_th` als explizites Setting ergaenzt
    - `integrated_energy_system.py` addiert den Wert fail-fast validiert auf die bestehenden Vienna-Boiler-OPEX
    - Fig. 12 setzt `FIGURE_GAS_BOILER_VARIABLE_OPEX_ADDER_EUR_PER_KWH_TH = 0.006`, d.h. Basis `1 EUR/MWh_th` plus Addierer `6 EUR/MWh_th`
    - Cache-/CSV-Schema-Version auf `boiler_opex7eurmwh` erhoeht
  - `good_jan` Render:
    - Ausgabe: `Documentation/Papers/thermflex_paper/figures/fig_12_good_week_january_dispatch_shift.png`
    - CSV: `Documentation/Papers/thermflex_paper/figures/fig_12_good_week_january_dispatch_shift.csv`
    - Heat operating cost `-0.034 %`
    - waermeallokierte CO2 `-0.036 %`
    - Peak-boiler energy `-0.353 %`
    - Gas-CHP heat `238.773 -> 238.790 GWh`, Peak boiler `30.597 -> 30.489 GWh`
  - Diagnose:
    - der OPEX-Aufschlag macht den Peak-Boiler formal teurer, aber loest die sichtbaren Januar-Taeler nicht generell als Vorheizfenster
    - `2023-01-18 12:00-21:00` bleibt praktisch unveraendert
    - `2023-01-20 12:00-18:00` bleibt praktisch unveraendert
    - nennenswerte zusaetzliche Verschiebung liegt stattdessen bei `2023-01-19 13:00-14:00`
  - Interpretation:
    - reine Boiler-OPEX-Erhoehung reicht nicht aus, um die gewuenschte Talnutzung robust zu erzwingen
    - naechster Diagnosepunkt ist die Gebaeude-/Event-Bound-Seite: verfuegbarer Preheat-Peak, thermischer Zustand und Rebound-/Terminalbedingungen in den Talfenstern

- 2026-05-04: Fig. 12 `good_jan` mit Gas-CHP-Gesamtwirkungsgrad `0.75` getestet.
  - Motivation:
    - Gas-CHP-Waermekapazitaet im Januar wirkte im `0.85`-Pfad sehr dominant
    - Sensitivitaet sollte pruefen, ob eine niedrigere plausible CHP-Waermeauskopplung die Mechanik klarer macht
  - Code:
    - JSON-Overrides fuer `district_gas_chp.operating_points_v1` werden in `get_settings.py` in typisierte `DistrictGasCHPOperatingPointConfig` normalisiert
    - Fig. 12 setzt fuer den piecewise-Pfad:
      - `power_led`: `eta_el=0.55`, `eta_th=0.20`
      - `mixed`: `eta_el=0.375`, `eta_th=0.375`
      - `heat_led`: `eta_el=0.30`, `eta_th=0.45`
    - damit bleibt jeder Punkt bei `eta_total=0.75`
    - Cache-/CSV-Version auf `piecewise_chp_eta75...boiler_opex7eurmwh` erhoeht
  - `good_jan` Render:
    - Ausgabe: `Documentation/Papers/thermflex_paper/figures/fig_12_good_week_january_dispatch_shift.png`
    - CSV: `Documentation/Papers/thermflex_paper/figures/fig_12_good_week_january_dispatch_shift.csv`
    - maximale Gas-CHP-Waerme sinkt von ca. `1440 MW_th` auf `1178 MW_th`
    - Heat operating cost `-0.032 %`
    - waermeallokierte CO2 `-0.033 %`
    - Peak-boiler energy `-0.131 %`
    - Gas-CHP heat `197.888 -> 197.888 GWh`, Peak boiler `71.482 -> 71.388 GWh`
  - Diagnose:
    - die Kapazitaetsreduktion macht die bisherigen visuellen Taeler nicht zu besseren Vorheizfenstern
    - im Gegenteil: in den betrachteten Januar-Taelern laeuft nun oft bereits Peak-Boiler, weil die Gas-CHP-Waermekapazitaet zu niedrig ist
    - `2023-01-18 12:00-21:00` und `2023-01-20 12:00-18:00` zeigen weiterhin praktisch keine Flex-Verschiebung
  - Interpretation:
    - `eta_total=0.75` ist als reine Fig.-12-Mechanik nicht ueberzeugend, weil es die source-seitigen Taeler beseitigt statt sie nutzbarer zu machen
    - der Engpass bleibt eher bei Gebaeude-/Flex-Dynamik und Horizon/Terminalbedingungen als bei zu hoher Gas-CHP-Kapazitaet allein

- 2026-05-05: Fig. 12 `good_jan` mit Gas-CHP-Gesamtwirkungsgrad `0.80` neu gerechnet und CHP-Preislogik geprueft.
  - Befund zur Betriebslogik:
    - im aktiven Fig.-12-Hauptpfad ist `district_gas_chp.power_priority_mode = "free"` gesetzt
    - die Objective enthaelt nur `heat_allocated_fuel_cost`, `heat_allocated_co2_cost` und `variable_opex`
    - Strompreisphasen treiben den `power_led`-Mode daher aktuell nicht; der Modus ist fuer Fig. 12 waerme-/kapazitaetsgetrieben
  - Kapazitaetscheck:
    - Override: Gas-CHP `1440 MW_el`, Peak-Boiler `1450 MW_th`
    - `eta_total=0.85` ergibt ca. `1440 MW_th` maximale Gas-CHP-Waerme
    - `eta_total=0.75` ergab ca. `1178 MW_th` und war fuer Januar zu niedrig
    - `eta_total=0.80` setzt:
      - `power_led`: `eta_el=0.55`, `eta_th=0.25`
      - `mixed`: `eta_el=0.40`, `eta_th=0.40`
      - `heat_led`: `eta_el=0.30`, `eta_th=0.50`
      - maximale Gas-CHP-Waerme ca. `1309 MW_th`
  - `good_jan` Render:
    - Ausgabe: `Documentation/Papers/thermflex_paper/figures/fig_12_good_week_january_dispatch_shift.png`
    - CSV: `Documentation/Papers/thermflex_paper/figures/fig_12_good_week_january_dispatch_shift.csv`
    - Heat operating cost `-0.033 %`
    - waermeallokierte CO2 `-0.034 %`
    - Peak-boiler energy `-0.188 %`
    - Gas-CHP heat `219.272 -> 219.272 GWh`, Peak boiler `50.098 -> 50.004 GWh`
  - Diagnose:
    - der Boiler kommt im eta80-Januar klar zum Einsatz: `160/168 h`, Peak ca. `666 MW`
    - die genannten Taeler `2023-01-18 12:00-21:00` und `2023-01-20 12:00-18:00` bleiben trotzdem Ref/Flex praktisch identisch
    - damit ist die fehlende Talnutzung nicht nur durch zu hohe Gas-CHP-Waermekapazitaet erklaert

- 2026-05-05: Fig. 12 `good_mar` selektiv mit aktuellem eta80-Pfad neu gerendert.
  - Befehl: `py -3 Documentation/Papers/thermflex_paper/figures/build_fig_12_weekly_dispatch_shift.py --variant good_mar`
  - Ausgabe: `Documentation/Papers/thermflex_paper/figures/fig_12_good_week_march_dispatch_shift.png`
  - CSV: `Documentation/Papers/thermflex_paper/figures/fig_12_good_week_march_dispatch_shift.csv`
  - Lauf:
    - 24h Warm-up, `horizon_h = 36`, `rolling_commit_h = 24`
    - piecewise Gas-CHP mit `eta_total = 0.80`
    - Peak-Boiler-OPEX-Addierer `+0.006 EUR/kWh_th`
  - Ergebnis:
    - Heat operating cost `-0.080 %`
    - waermeallokierte CO2 `-0.144 %`
    - Peak-boiler energy `-4.917 %`
    - Peak-boiler peak `-2.847 %`
    - Waste `26.880 -> 26.880 GWh`
    - External heat `25.940 -> 26.880 GWh`
    - Gas-CHP heat `103.172 -> 103.939 GWh`
    - Peak boiler `0.031 -> 0.029 GWh`

- 2026-05-05: Fig.-12-Wochenkandidatensuche fuer Jan/Feb/Maerz und Ankercheck durchgefuehrt.
  - `good_feb` wurde auf den aktuellen eta80-Pfad nachgezogen:
    - Heat operating cost `-0.238 %`
    - waermeallokierte CO2 `-0.266 %`
    - Peak boiler `0.346 -> 0.310 GWh`
    - Boiler-Peak `74.3 -> 74.3 MW`
  - Referenz-Screen mit eta80 fuer Wochenstarts:
    - `2023-01-15`: Peak boiler `50.10 GWh`, Peak `666 MW`
    - `2023-01-22`: Peak boiler `40.08 GWh`, Peak `689 MW`
    - `2023-02-05`: Peak boiler `11.64 GWh`, Peak `430 MW`
    - `2023-02-12`: Peak boiler `9.08 GWh`, Peak `287 MW`
    - `2023-02-26`: Peak boiler `0.90 GWh`, Peak `138 MW`
    - `2023-03-05`: Peak boiler `0.18 GWh`, Peak `54 MW`
  - Flex-Diagnose fuer die wahrscheinlichsten Edge-Wochen:
    - `2023-02-12`: Peak boiler `9.077 -> 9.076 GWh`, praktisch keine Reduktion
    - `2023-02-26`: Peak boiler `0.900 -> 0.883 GWh`, ca. `-1.86 %`
    - `2023-03-05`: Peak boiler `0.177 -> 0.050 GWh`, ca. `-71.9 %`, aber absolut klein
  - `march_savings` (`2023-03-01`) wurde auf eta80 gerendert:
    - Ausgabe: `Documentation/Papers/thermflex_paper/figures/fig_12_march_weekly_dispatch_shift.png`
    - CSV: `Documentation/Papers/thermflex_paper/figures/fig_12_march_weekly_dispatch_shift.csv`
    - Heat operating cost `-0.233 %`
    - waermeallokierte CO2 `-0.243 %`
    - Peak boiler `0.601 -> 0.453 GWh`, ca. `-24.5 %`
  - Interpretation:
    - ein perfekter Jan/Feb/Maerz-Fall mit relevantem Referenz-Boiler und `0` Boiler im Flex-Fall wurde in den geprueften Wochen nicht gefunden
    - beste absolute Boiler-Relevanz bleibt `good_jan`, aber mit kleiner relativer Reduktion
    - beste relative Edge-Story ist `2023-03-05` bzw. nahe daran `march_savings`, aber absolut ist der Boiler schon sehr klein
  - Ankercheck:
    - Peak-Boiler-Kapazitaet im Override `1450 MW_th` trifft den dokumentierten `~1.45-1.50 GW_th`-Anker
    - Waste `160 MW_th * 7500 h = 1200 GWh/a` trifft den offiziellen `~1200 GWh/a`-Anker
    - External heat `160 MW_th * 7500 h = 1200 GWh/a` trifft den offiziellen `1200.9 GWh/a`-Anker
    - Gas-CHP eta80 ergibt ca. `1309 MW_th` maximale Waerme und liegt damit unter dem dokumentierten `~1.4-1.6 GW_th`-Leistungsanker; eta80 ist daher eher konservativ fuer Gas-CHP-Waermekapazitaet

- 2026-05-05: Aktuelle eta80-Wochensuche auf Anfang Dezember bis Ende Maerz ohne alten Daily-Screen fortgefuehrt.
  - Der alte Daily-Screen wurde als Entscheidungsgrundlage verworfen, weil er aus einem nicht mehr vergleichbaren Dispatch-/Gas-CHP-Stand stammt.
  - Belastbare aktuelle eta80-Diagnoselaeufe:
    - `2023-12-01`: Peak boiler `29.933 -> 29.933 GWh`, Peak `451 -> 451 MW`, heat-allocated CO2 ca. `-0.037 %`
    - `2023-12-08`: Peak boiler `19.771 -> 19.771 GWh`, Peak `416 -> 416 MW`, heat-allocated CO2 ca. `-0.039 %`
    - `2023-01-22`: Peak boiler `40.080 -> 40.080 GWh`, Peak `689 -> 689 MW`, heat-allocated CO2 ca. `-0.036 %`
    - `2023-02-05`: Peak boiler `11.639 -> 11.639 GWh`, Peak `430 -> 430 MW`, heat-allocated CO2 ca. `-0.048 %`
  - Befund:
    - Im aktuellen eta80-Hauptpfad gibt es Wochen mit relevantem Ref-Boiler, aber Upper-only reduziert den Boiler dort praktisch nicht.
    - Wochen mit sichtbarer relativer Boiler-Reduktion liegen eher am warmen Rand, wo der absolute Boiler-Einsatz bereits klein ist.
  - Demand-Anker:
    - aktiver Paperpfad nutzt `district_heating.share = 0.35`
    - dokumentierter letzter Full-year-Check: annual DH demand `6.138 TWh`, Peak `3.084 GW`, p99 `2.739 GW`
    - offizieller Fernwaermeabsatz-Anker 2023: `5.427 TWh`
    - daraus folgt: der DH-Demand ist im aktuellen Paperpfad eher nicht zu klein, sondern bereits oberhalb des offiziellen Absatzankers
  - Zusaetzlicher aktueller eta80-Screen fuer weitere Startwochen:
    - Output: `Documentation/Papers/thermflex_paper/figures/fig_12_eta80_week_candidate_screen.csv`
    - `2023-12-15`: Peak boiler `16.632 -> 16.526 GWh`, ca. `-0.635 %`
    - `2023-12-22`: Peak boiler `7.919 -> 7.825 GWh`, ca. `-1.186 %`
    - `2023-01-29`: Peak boiler `7.680 -> 7.666 GWh`, ca. `-0.182 %`
    - `2023-02-12`: Peak boiler `9.077 -> 9.076 GWh`, ca. `-0.005 %`
    - `2023-02-26`: Peak boiler `0.900 -> 0.883 GWh`, ca. `-1.862 %`
    - `2023-03-05`: Peak boiler `0.177 -> 0.050 GWh`, ca. `-71.918 %`, aber absolut nur `0.127 GWh` Reduktion
  - Zusammenfassung:
    - Es wurden keine aktuellen eta80-Wochen gefunden, in denen relevante Peak-Boiler-Energie im Referenzfall durch Upper-only deutlich bis auf nahe null reduziert wird.
    - In boiler-relevanten Wochen bleibt der Boiler fast unveraendert; starke relative Reduktion tritt nur bei sehr kleinem Boiler-Rest auf.

- 2026-05-05: Fig.-12-Tau-/Nachfragesensitivitaet fuer die Peak-Boiler-Story geprueft.
  - Output: `Documentation/Papers/thermflex_paper/figures/fig_12_tau_demand_sensitivity_screen.csv`
  - Zusaetzlicher Diagnoseplot: `Documentation/Papers/thermflex_paper/figures/fig_12_sensitivity_mar05_tau2_share35_peak_boiler_reduction.png`
  - Gepruefte Sensitivitaeten:
    - `2023-03-05`, `tau_h = 2`, `district_heating.share = 0.35`: Peak boiler `1.480 -> 1.212 GWh`, Peak `238.6 -> 190.0 MW`, Cost `-2.338 %`, CO2 `-2.473 %`
    - `2023-03-05`, `tau_h = 4`, `district_heating.share = 0.40`: Peak boiler `4.404 -> 4.192 GWh`, Peak `300.4 -> 277.7 MW`, Cost `-0.564 %`, CO2 `-0.584 %`
    - `2023-02-05`, `tau_h = 4`, `district_heating.share = 0.40`: Peak boiler `31.031 -> 30.934 GWh`, Peak unveraendert `730.1 MW`, Cost/CO2 jeweils ca. `-0.045 %`
  - Befund:
    - Hoehere Nachfrage erhoeht den Ref-Boiler-Einsatz, macht die relative Flex-Reduktion aber nicht staerker.
    - Niedrigeres `tau_h = 2` macht die Boiler-Reduktion sichtbar, aber der Effekt ist nicht sauber Gas-CHP-getrieben: die Gas-CHP-Wochensumme sinkt dort sogar leicht.
    - Fuer eine belastbare Gas-CHP-Vorheizstory sind die vorhandenen `march_savings`- bzw. `good_nov`-Plots besser geeignet: dort gibt es mehrere Vorheizstunden mit Gas-CHP-Zunahme und spaetere Boiler-Reduktion.

- 2026-05-05: Boiler-OPEX-/Peak-Boiler-Energy-Sensitivitaet fuer `march_savings` gerechnet.
  - Output: `Documentation/Papers/thermflex_paper/figures/fig_12_boiler_penalty_sensitivity_screen.csv`
  - Diagnoseplot: `Documentation/Papers/thermflex_paper/figures/fig_12_sensitivity_march_savings_boiler_opex50eurmwh.png`
  - Getestete Boiler-OPEX-Addierer:
    - `+20 EUR/MWh_th`: Peak boiler `0.601 -> 0.443 GWh`, Peak `138.2 -> 138.2 MW`, Gas-CHP `-0.166 GWh`, Cost `-0.253 %`, CO2 `-0.248 %`
    - `+50 EUR/MWh_th`: Peak boiler `0.601 -> 0.397 GWh`, Peak `138.2 -> 131.0 MW`, Gas-CHP `-0.098 GWh`, Cost `-0.294 %`, CO2 `-0.231 %`
  - Plausibilitaet Gebaeudespeicher:
    - Flex-Diagnostics liefern ca. `3.2 GWh` effektive ThermFlex-Speicherkapazitaet bzw. Preheat-Headroom.
    - Die gesamte Referenz-Boiler-Wochenenergie im `march_savings`-Plot liegt nur bei ca. `0.60 GWh`.
    - Energetisch waere genug Gebaeudespeicher vorhanden; verbleibende Peak-Boiler-Anteile deuten daher eher auf Timing-, Rampen-, Event-/Temperaturgrenzen oder den Rolling-/Bus-Inertia-Zuschnitt als auf fehlende thermische Speicherkapazitaet.
  - Befund:
    - Ein deutlich hoeherer Boiler-Penalty reduziert die Boiler-Energie, buegelt die drei Peak-Load-Spitzen aber nicht vollstaendig aus.
    - Damit ist der schwache Preheat-Effekt nicht nur ein zu niedriger Boiler-Preis im Objective.

- 2026-05-05: Hourly ThermFlex-State-Diagnostic fuer Fig. 12 `march_savings` ergaenzt.
  - Neuer Builder: `Documentation/Papers/thermflex_paper/figures/build_fig_12_thermflex_state_diagnostic.py`
  - Output:
    - `Documentation/Papers/thermflex_paper/figures/fig_12_march_savings_thermflex_state_diagnostic.csv`
    - `Documentation/Papers/thermflex_paper/figures/fig_12_march_savings_thermflex_state_diagnostic.png`
  - Der Builder verwendet die bestehende Fig.-12-CSV als Dispatch-Anker und evaluiert nur den Upper-only-Flex-State neu; fehlende Member-State-Arrays schlagen fail-fast fehl.
  - Wichtigste Diagnose:
    - Beim ersten grossen Peak `2023-03-02 03:00-07:00` gibt es in den Stunden davor praktisch keine ThermFlex-Aktivitaet; alle 8 Member liegen exakt bei `22.5 C`.
    - Vor diesem Peak ist `thermflex_preheat_mwh` nur numerisches Rauschen; der Boiler bleibt daher praktisch unveraendert (`138.22 -> 138.22 MW`).
    - Beim spaeteren Peak `2023-03-05 05:00-08:00` gibt es dagegen echte Vorheizung am Vortag (`2023-03-04 13:00-18:00`, grob `2.6 GWh`) und danach Cutback; dieser Peak wird deutlich reduziert.
  - Interpretation:
    - Das Problem ist nicht fehlende aggregierte Gebaeudespeicherenergie.
    - Der verbleibende erste Morgenpeak sieht nach Timing-/Rolling-/Bus-Inertia-Zuschnitt aus: fuer diesen Tagesuebergang wird kein nutzbarer Preheat-Zustand in den sichtbaren Flex-State hineingebracht.
    - Zusaetzlich ist im aktuellen Upper-only-Diagnosepfad `therm_flex_active` bewusst kontinuierlich, daher sind `active_members` member-aequivalente Werte und nicht zwingend ganze Zahlen.

- 2026-05-05: Single-Block-Boundary-Probe fuer den ersten `march_savings`-Morgenpeak ausgewertet.
  - Output: `Documentation/Papers/thermflex_paper/figures/fig_12_march_single_block_boundary_probe.csv`
  - Setup:
    - einzelner 36h-Block ab `2023-03-01 00:00`, also ohne 24h-Commit-Stitching an der kritischen Stelle
    - gleiche Fig.-12-Methodik, nur Boiler-OPEX-Addierer als Diagnose variiert
  - Befund:
    - Basis-Addierer `+6 EUR/MWh_th`: praktisch kein Preheat vor `2023-03-02 03:00-07:00`; Boiler-Peak bleibt `138.6 MW`
    - Diagnose-Addierer `+50 EUR/MWh_th`: nur ca. `45 MWh` Preheat in `h25-h26`; Boiler-Peak bleibt fast unveraendert bei `136.9 MW`
    - Extrem-Diagnose `+500 EUR/MWh_th`: ca. `1.93 GWh` Preheat vor dem Peak, ca. `1.03 GWh` Cutback im Peakfenster; Boiler im Peakfenster faellt auf `0`
  - Interpretation:
    - Der erste Peak ist nicht durch einen harten Rolling-State-Reset oder fehlende physikalische Preheat-Faehigkeit erklaert.
    - Der Optimierer kann den Peak bei starkem Anreiz aus dem vorhandenen ThermFlex-Zustandsmodell voll wegschieben.
    - Im aktuellen Hauptpfad ist der Preis-/Objective-Anreiz fuer diesen langen Vorlauf aber zu schwach gegenueber zusaetzlicher Vorheizenergie und Waermeverlusten.
    - Fuer den Paper-Hauptpfad sollte daraus nicht automatisch ein extremer Boiler-Penalty folgen; sinnvoller ist eine explizit dokumentierte Peak-Boiler-Avoidance-Sensitivitaet oder ein sauber begruendeter, realistisch kalibrierter Boiler-Kosten-/CO2-Schnitt.

- 2026-05-05: Aktiven Peak-Boiler-Economics-Schnitt gegen MILP-Fuel-Cost-Pfad geprueft.
  - Repo-SSOT `Data/economic_data/location/vienna.py` enthaelt bereits einen fossilen Peak-Boiler-Mix:
    - `2/3 Erdgas + 1/3 Heizoel extra leicht`
    - resultierender Preis `77.4 EUR/MWh_fuel`
    - resultierender direkter CO2-Faktor `0.224 tCO2/MWh_fuel`
  - Gas-CHP bleibt bei:
    - `55.0 EUR/MWh_fuel`
    - `0.202 tCO2/MWh_fuel`
  - Aktiver Fig.-12-Pfad ergaenzt Boiler-Variable-OPEX um `0.006 EUR/kWh_th`; mit Katalog-OPEX `0.001 EUR/kWh_th` sind das insgesamt `7 EUR/MWh_th` variable Boiler-OPEX.
  - Wichtiger Befund:
    - `dispatch/modes/milp_day_ahead.py` nutzt bei vorhandener Serie `district_gas_day_ahead_price_eur_per_mwh_fuel` dieselbe Gaspreis-Zeitreihe fuer Gas-CHP und Peak-Boiler.
    - Dadurch ist der Wiener Oelpreisanteil aus `district_gas_boiler.fuel_eur_per_m3` im Fig.-12-Dispatch-Fuel-Cost aktuell nicht wirksam, solange eine Gaspreis-Serie vorhanden ist.
    - Der hoehere Boiler-CO2-Faktor ist dagegen aktiv, weil `district_gas_boiler_co2_t_per_mwh_fuel` separat gelesen wird.
  - Methodische Konsequenz:
    - Bevor freie Boiler-Energy-/Peak-Lambdas eingefuehrt werden, sollte der fossile Peak-Boiler-Mix im Dispatch-Fuel-Cost sauber wirksam gemacht werden, idealerweise ueber eine eigene `district_gas_boiler_*_price_eur_per_mwh_fuel`-Serie oder einen dokumentierten Fuel-Mix-Faktor auf die vorhandene Gaspreis-Zeitreihe.

- 2026-05-05: Peak-Boiler-Fuel-Price im MILP vom Gas-CHP-Preis getrennt.
  - Geaendert:
    - `dispatch/modes/milp_day_ahead.py`
    - `dispatch/modes/milp_two_stage.py`
    - `Technical_model/energy_system/systems/integrated_energy_system.py`
  - Neuer Pfad:
    - DispatchInput fuehrt `district_gas_boiler_day_ahead_price_eur_per_mwh_fuel`
    - der Wert wird aus der Wiener `district_gas_boiler.fuel_eur_per_m3`-SSOT und `district_gas_boiler.fuel_lhv_kwh_per_m3` abgeleitet
    - `milp_day_ahead` nutzt diese Boiler-Preisreihe fuer Boiler-Fuel-Cost und laesst die bestehende Gaspreisreihe bei Gas-CHP
    - `milp_two_stage` nutzt den getrennten Boilerpreis ebenfalls; bei aktiviertem Gas-Procurement wird nur Gas-CHP-Gas ueber das Procurement gebucht, Boiler-Fuel separat ueber den Boilerpreis
  - Damit ist der aktive Wiener fossile Peak-Boiler-Mix (`2/3 Gas + 1/3 Heizoel extra leicht`, aktuell `77.4 EUR/MWh_fuel`) nun auch kostenwirksam im MILP statt nur in der Economics-SSOT dokumentiert.
  - Gas-CHP-Heat-Allocation war bereits vorhanden:
    - im Fig.-12-piecewise-Pfad wird je Mode-Share mit `eta_total = eta_el + eta_th = 0.80` allokiert
    - dadurch kostet/emitttiert `1 kWh_th` Gas-CHP-Waerme im Heat-Allocated-Objective nur `1/0.80 = 1.25 kWh_fuel`, waehrend der Peak-Boiler bei `eta_th = 0.90` `1/0.90 = 1.11 kWh_fuel` verbraucht, aber mit fossilerem und teurerem Fuel-Mix
  - Verifikation:
    - `python -m py_compile dispatch/modes/milp_day_ahead.py dispatch/modes/milp_two_stage.py Technical_model/energy_system/systems/integrated_energy_system.py`
    - 1h Fig.-12-Day-ahead-Smoke fuer `2023-03-01` mit piecewise Gas-CHP erfolgreich geloest

- 2026-05-05: Wiener Peak-Boiler-Mix auf `1/2 Gas + 1/2 Heizoel extra leicht` gesetzt und ohne Fig.-12-Render gescreent.
  - Geaendert:
    - `Data/economic_data/location/vienna.py`
    - `Documentation/Sources/dh_economics_quellen.md`
  - Neuer aktiver Peak-Boiler-Fuel-Mix:
    - Preis `88.65 EUR/MWh_fuel`
    - direkter CO2-Faktor `0.235 tCO2/MWh_fuel`
    - mit `eta_th = 0.90` und `7 EUR/MWh_th` Boiler-OPEX im Fig.-12-Pfad: ca. `105.5 EUR/MWh_th`
    - CO2 auf Waermebasis: ca. `0.261 tCO2/MWh_th`
  - Vergleich Gas-CHP heat allocation im aktiven Fig.-12-piecewise-Pfad:
    - `eta_total = 0.80`
    - Heat-Fuel-Cost ca. `68.8 EUR/MWh_th`
    - heat-allocated CO2 ca. `0.253 tCO2/MWh_th`
  - Tabellarischer Screen ohne Plotrender:
    - Output: `Documentation/Papers/thermflex_paper/figures/fig_12_peak_boiler_mix50_screen.csv`
    - `good_dec`: Cost `-0.195 %`, CO2 `+0.112 %`, Peak boiler `25.070 -> 23.825 GWh` (`-4.97 %`), Peak fast unveraendert
    - `good_jan`: Cost `-0.029 %`, CO2 `-0.030 %`, Peak boiler `50.098 -> 50.070 GWh` (`-0.054 %`), Peak fast unveraendert
    - `good_feb`: Cost `-0.243 %`, CO2 `-0.271 %`, Peak boiler `0.346 -> 0.303 GWh` (`-12.53 %`), Peak `74.3 -> 73.6 MW`
    - `good_mar`: Cost `-0.080 %`, CO2 `-0.135 %`, Peak boiler `0.031 -> 0.029 GWh` (`-4.29 %`), Peak `29.6 -> 28.8 MW`
    - `march_savings`: Cost `-0.285 %`, CO2 `-0.244 %`, Peak boiler `0.601 -> 0.412 GWh` (`-31.38 %`), Peak `138.2 -> 132.5 MW`
  - Befund:
    - `march_savings` und `good_feb` profitieren sichtbar und bleiben bei Kosten und CO2 negativ.
    - `good_mar` ist KPI-seitig sauber, aber absolut fast ohne Boiler.
    - `good_jan` bleibt trotz korrekter Peak-Boiler-Economics kein guter Boiler-Reduction-Plot.
    - `good_dec` reduziert Boiler-Energie, erhoeht aber heat-allocated CO2 leicht, weil mehr Gas-CHP-Waerme genutzt wird; als Hauptmechanismusplot daher nicht geeignet.

- 2026-05-05: Fig.-12-Wochensuche fuer Dezember bis Ende Maerz mit leicht erhoehtem Preheat-Peak-Bound-Multiplier gescreent.
  - Setup:
    - kein Fig.-12-Plotrender, nur Wochen-KPI-Screen
    - `event_preheat_peak_bound_multiplier = 1.50`, danach als Fig.-12-Default gesetzt
    - Zeitraum: Dezember 2023 sowie Januar bis Maerz 2023, jeweils Wochenfenster mit Warm-up-Tag
  - Output:
    - `Documentation/Papers/thermflex_paper/figures/fig_12_dec_mar_multiplier15_week_screen.csv`
  - Bester All-KPI-Kandidat:
    - Woche ab `2023-03-05`
    - Cost `-0.715 %`
    - CO2 `-0.721 %`
    - Peak-Boiler-Energie `0.177 -> 0.034 GWh` (`-80.9 %`)
    - Peak-Boiler-Leistung `53.7 -> 33.8 MW` (`-37.0 %`)
  - Weitere Kandidaten:
    - `2023-02-26`: alle KPIs negativ, mehr absolute Boiler-Energie (`0.900 -> 0.850 GWh`), aber nur `-5.6 %` Boiler-Energie und `-4.2 %` Peak.
    - `2023-12-08`, `2023-12-15`, `2023-12-22`: deutlichere absolute Boiler-Reduktion, aber heat-allocated CO2 leicht positiv; daher nicht geeignet fuer eine Hauptfigur, die Kosten und CO2 gleichzeitig reduzieren soll.
  - Interpretation:
    - Der leicht groessere Preheat-Spielraum findet eine saubere Boiler-Reduction-Woche, aber der beste All-KPI-Fall liegt im Maerz und nicht in den kalten Dezember-/Januarwochen.
    - Fuer einen Paper-Hauptplot mit eindeutigem Mechanismus ist `2023-03-05` der naechste Render-Kandidat; fuer absolute Winter-Boiler-Energie waere `2023-02-26` als Zusatzcheck sinnvoll.

- 2026-05-05: Fig. 12 fuer den neuen Maerz-Peak-Boiler-Reduction-Kandidaten gerendert.
  - Geaendert:
    - `Documentation/Papers/thermflex_paper/figures/build_fig_12_weekly_dispatch_shift.py`
    - neuer Variant-Slug `march_peak_reduction` fuer Woche ab `2023-03-05`
    - eigene Outputs, damit bestehende Maerz-Dateien nicht ueberschrieben werden
    - Cache-Versionen auf `peak_bounds150` erhoeht, damit keine Serien mit altem `1.25`-Bound wiederverwendet werden
  - Outputs:
    - `Documentation/Papers/thermflex_paper/figures/fig_12_march_peak_reduction_dispatch_shift.png`
    - `Documentation/Papers/thermflex_paper/figures/fig_12_march_peak_reduction_dispatch_shift.csv`
  - Ergebnis:
    - Cost `-0.715 %`
    - CO2 `-0.721 %`
    - Peak-Boiler-Energie `0.177 -> 0.034 GWh` (`-80.9 %`)
    - Peak-Boiler-Leistung `53.7 -> 33.8 MW` (`-37.0 %`)
  - Kosteninterpretation:
    - Die moderate Kostenreduktion kommt nicht primaer von hohem Rebound.
    - Netto steigt die sichtbare Wochenlast nur um ca. `0.30 GWh_th` auf Gebaeudeseite bzw. `0.23 GWh_th` am DH-Bus.
    - Der Peak-Boiler faellt relativ stark, aber absolut nur um ca. `0.143 GWh_th`; deshalb bleibt der direkte Kosteneffekt begrenzt.
    - Die heat-allocated Objective sinkt um ca. `81.3 kEUR`; neben der Boiler-Reduktion tragen mehr External Heat, Biomass und Heat Pump sowie weniger Gas-CHP-Waerme zur Einsparung bei.
  - Verifikation:
    - `python -m py_compile Documentation/Papers/thermflex_paper/figures/build_fig_12_weekly_dispatch_shift.py`
    - Einzelrender `--variant march_peak_reduction` erfolgreich abgeschlossen

- 2026-05-05: Aktuelle `tau = 2/3/4 h`-Diagnose fuer sichtbarere Peak-Boiler-Reduktion durchgefuehrt.
  - Output:
    - `Documentation/Papers/thermflex_paper/figures/fig_12_tau234_current_week_screen.csv`
  - Gepruefte Wochen:
    - `2023-12-15`
    - `2023-12-22`
    - `2023-02-26`
    - `2023-03-05`
  - Bester sauberer Kandidat:
    - `2023-03-05`, `tau = 2 h`
    - Cost `-2.687 %`
    - CO2 `-2.560 %`
    - Peak-Boiler-Energie `1.480 -> 0.485 GWh` (`-67.2 %`)
    - Peak-Boiler-Leistung `238.6 -> 122.2 MW` (`-48.8 %`)
  - Vergleich:
    - `2023-03-05`, `tau = 3 h`: Cost `-1.924 %`, CO2 `-1.837 %`, Boiler `0.691 -> 0.220 GWh`
    - `2023-03-05`, `tau = 4 h`: Cost `-0.715 %`, CO2 `-0.721 %`, Boiler `0.177 -> 0.034 GWh`
    - Dezemberwochen zeigen mit kleinerem `tau` zwar grosse absolute Boiler-Reduktionen, aber heat-allocated CO2 bleibt positiv; daher weiter kein guter Hauptplot.
  - Reproduzierbarer Render:
    - `build_fig_12_weekly_dispatch_shift.py` unterstuetzt nun variant-spezifisches `bus_inertia_tau_h`
    - neuer Variant-Slug `march_peak_reduction_tau2`
    - Plot: `Documentation/Papers/thermflex_paper/figures/fig_12_march_peak_reduction_tau2_dispatch_shift.png`
    - CSV: `Documentation/Papers/thermflex_paper/figures/fig_12_march_peak_reduction_tau2_dispatch_shift.csv`
  - Interpretation:
    - Eine kleinere DH-Bus-Zeitkonstante macht die Peak-Boiler-Story klar sichtbar und verbessert gleichzeitig Kosten und CO2.
    - Das ist methodisch sauberer als zuerst einen zusaetzlichen freien Boiler-Penalty einzufuehren; ein Boiler-Penalty sollte hoechstens als Sensitivitaet folgen.

## 2026-05-06

- 2026-05-06: Tau-2-Winterscreen fuer Dezember, Januar und Februar nach besserer Fig.-12-Woche durchgefuehrt.
  - Output:
    - `Documentation/Papers/thermflex_paper/figures/fig_12_tau2_winter_week_screen.csv`
  - Ergebnis:
    - Dezemberwochen haben die groessten absoluten Boiler-Reduktionen, aber CO2 wird meistens leicht positiv.
    - `2023-12-01` bleibt CO2-seitig knapp negativ, reduziert den Peak aber fast nicht (`520.9 -> 515.0 MW`).
    - Januarwochen sind als Hauptplot ungeeignet, weil Boiler-Energie bzw. CO2 in mehreren Faellen steigen.
    - Bester Winter-Kompromiss ist `2023-02-26`:
      - Cost `-1.620 %`
      - CO2 `-1.571 %`
      - Peak-Boiler-Energie `3.646 -> 2.455 GWh` (`-32.7 %`)
      - Peak-Boiler-Leistung `262.2 -> 230.5 MW` (`-12.1 %`)
  - Reproduzierbarer Render:
    - neuer Variant-Slug `february_peak_reduction_tau2`
    - Plot: `Documentation/Papers/thermflex_paper/figures/fig_12_february_peak_reduction_tau2_dispatch_shift.png`
    - CSV: `Documentation/Papers/thermflex_paper/figures/fig_12_february_peak_reduction_tau2_dispatch_shift.csv`
  - Technischer Hinweis:
    - erste Render-Wiederholung scheiterte nicht methodisch, sondern an Windows-Pfadlaenge beim langen Cache-Dateinamen.
    - `FEBRUARY_PEAK_REDUCTION_TAU2_CACHE_VERSION` wurde deshalb kurz auf `fig12_feb_peak_tau2_pb150_v1` gesetzt.

- 2026-05-06: Februar-`tau=2` Boiler-OPEX-Sensitivitaet fuer staerkere Peak-Boiler-Vermeidung gescreent und gerendert.
  - Vorab-Quellencheck:
    - freie Peak-Boiler-Energie-/Peak-Lambdas sind nicht als Hauptpfad empfohlen
    - DEA stuetzt eine dynamische Start-/Cycling-Kostenlogik; fuer den Gas-DH-Boiler fehlt aber eine konkrete Startup-Kostenzahl
    - deshalb kurzfristig als explizite variable-OPEX-Sensitivitaet umgesetzt
  - Builder-Erweiterung:
    - `build_fig_12_weekly_dispatch_shift.py` unterstuetzt nun variant-spezifisches `gas_boiler_variable_opex_adder_eur_per_kwh_th`
    - Wert wird in Cache-Metadaten und CSV geschrieben
  - Screen:
    - `Documentation/Papers/thermflex_paper/figures/fig_12_february_tau2_boiler_opex_sensitivity_screen.csv`
    - Adders: `+6`, `+10`, `+15`, `+20`, `+30`, `+50 EUR/MWh_th`
  - Ergebnis:
    - `+30 EUR/MWh_th` ist ein brauchbarer Mittelweg:
      - Cost `-1.927 %`
      - CO2 `-1.382 %`
      - Peak-Boiler-Energie `3.646 -> 1.586 GWh` (`-56.5 %`)
      - Peak-Boiler-Leistung `262.2 -> 175.7 MW` (`-33.0 %`)
    - `+50 EUR/MWh_th` reduziert staerker (`0.952 GWh`, Peak `131.9 MW`), ist aber als harte obere Sensitivitaet zu behandeln.
    - Auch mit `+30` verschwinden die Boiler-Peaks nicht vollstaendig; es bleiben offenbar notwendige Reststunden.
  - Render:
    - neuer Slug `february_peak_reduction_tau2_boiler_opex30`
    - Plot: `Documentation/Papers/thermflex_paper/figures/fig_12_february_peak_reduction_tau2_boiler_opex30_dispatch_shift.png`
    - CSV: `Documentation/Papers/thermflex_paper/figures/fig_12_february_peak_reduction_tau2_boiler_opex30_dispatch_shift.csv`

- 2026-05-06: Peak-Boiler-Startlogik als explizite MILP-Sensitivitaet umgesetzt.
  - Modell:
    - `dispatch/modes/milp_day_ahead.py` hat nun `district_gas_boiler_start` als Binary mit Rolling-Initialzustand.
    - Startkosten laufen als eigener Objective-Term `startup_cost` und werden als `startup_cost_eur` in Kosten/KPI/Reporting exportiert.
    - `constraints.dispatch.district_gas_boiler_startup_cost_eur_per_mw_start` aktiviert die Logik explizit; negative Werte fail-fast.
    - Rolling-Dispatch uebergibt `district_gas_boiler_on_initial`, damit Blockgrenzen keine kuenstlichen Starts zaehlen.
  - Fig.-12-Sensitivitaet:
    - neuer Slug `february_peak_reduction_tau2_boiler_start`
    - Settings: `tau = 2 h`, Boiler-Mindestlast `15 %`, Startkosten `50 EUR/MW/start`
    - kurzer 72h-Screen: `Documentation/Papers/thermflex_paper/figures/fig_12_february_startcost_72h_screen.csv`
    - kleinste getestete wirksame Stufe war `50 EUR/MW/start`; damit verschwindet der Boiler im 72h-Flexfenster.
  - Wochenrender:
    - Plot: `Documentation/Papers/thermflex_paper/figures/fig_12_february_peak_reduction_tau2_boiler_start_dispatch_shift.png`
    - CSV: `Documentation/Papers/thermflex_paper/figures/fig_12_february_peak_reduction_tau2_boiler_start_dispatch_shift.csv`
    - Woche `2023-02-26`:
      - Cost `-4.462 %`
      - CO2 `-0.534 %`
      - Peak-Boiler-Energie `2.132 -> 0.000 GWh`
      - Peak-Boiler-Leistung `262.2 -> 0.0 MW`
  - Verifikation:
    - `python -m py_compile` fuer MILP, Integrated-System, Cost/KPI/CSV/Reporting und Fig.-12-Builder erfolgreich.

- 2026-05-06: Fig.-12-Stackplot fuer Peak-Boiler-Startkostenvarianten korrigiert und `tau=3` getestet.
  - Plot-Fix:
    - Solarthermie und Geothermie wurden als sichtbare Quellen in den Fig.-12-Stack aufgenommen.
    - Die Stack-Logik zieht Spillage bei normalen Dispatch-Generationsreihen nicht mehr ab, weil diese Reihen bereits nutzbare DH-Waerme darstellen.
    - Dadurch verschwinden die weissen Flaechen in den oberen Dispatch-Panels; gepruefte Restluecke nur numerisches Rauschen (`~1e-12 MW`).
  - Neu gerendert:
    - `Documentation/Papers/thermflex_paper/figures/fig_12_february_peak_reduction_tau2_boiler_start_dispatch_shift.png`
    - `Documentation/Papers/thermflex_paper/figures/fig_12_february_peak_reduction_tau3_boiler_start_dispatch_shift.png`
  - Vergleich:
    - `tau=2`: Cost `-4.462 %`, CO2 `-0.534 %`, Peak-Boiler-Energie/Peak jeweils `-100 %`.
    - `tau=3`: Cost `-3.190 %`, CO2 `+0.180 %`, Peak-Boiler-Energie/Peak jeweils `-100 %`.
    - `tau=4`: Cost `-2.534 %`, CO2 `+0.152 %`, Peak-Boiler-Energie/Peak jeweils `-100 %`.
  - Interpretation:
    - `tau=2` bleibt fuer diese Sensitivitaetsfigur klar besser, weil `tau=3` und `tau=4` CO2 leicht erhoehen.

- 2026-05-06: `tau=3`-Startkostenplot fuer Fig. 12 optisch geglaettet.
  - Aenderung:
    - reine Darstellungs-Glaettung im oberen Dispatch-Stack mit zentriertem `3 h`-Fenster
    - CSV/KPIs und MILP-Zeitreihen bleiben unveraendert roh
    - geglaettete Stack-Komponenten werden pro Stunde wieder auf die geglaettete DH-Buslast skaliert, damit keine visuellen Luecken entstehen
  - Neu gerendert:
    - `Documentation/Papers/thermflex_paper/figures/fig_12_february_peak_reduction_tau3_boiler_start_dispatch_shift.png`
  - CO2-Hinweis:
    - `tau=3` bleibt mit CO2 `+0.180 %` leicht positiv.
    - Ursache im Wochenvergleich: Flex reduziert zwar Boiler vollstaendig, erhoeht aber die DH-Busenergie um ca. `2.58 GWh`; die Zusatzdeckung kommt vor allem aus Gas-CHP, waehrend External-Heat-Zuwachs kleiner ist als bei `tau=2`.

- 2026-05-06: Legacy-Quellen aus dem sichtbaren Fig.-12-Stack entfernt.
  - Solarthermie und Geothermie sind im aktuellen Wiener Ist-System keine realen Last-/Quellbeitraege, sondern Legacy-Szenariofelder.
  - Sie werden deshalb nicht mehr als Fig.-12-Quellen exportiert/geplottet.
  - Der Stack bleibt geschlossen, weil der eigentliche Lueckenfix weiterhin ist: nutzbare `generation`-Reihen werden nicht mehr um Spillage gekuerzt.
  - `tau=3`-Plot/CSV neu aufgebaut:
    - `Documentation/Papers/thermflex_paper/figures/fig_12_february_peak_reduction_tau3_boiler_start_dispatch_shift.png`
    - `Documentation/Papers/thermflex_paper/figures/fig_12_february_peak_reduction_tau3_boiler_start_dispatch_shift.csv`

- 2026-05-06: Fig.-12-Wochenplots auf den aktuellen Plot-/KPI-Stand neu gerendert und alte Outputs archiviert.
  - Archiv:
    - alte `fig_12*dispatch_shift.{png,csv}` nach `Documentation/Papers/thermflex_paper/figures/old/fig12_dispatch_shift_archive_20260506_143038/` verschoben
    - archivierte Dateien: `34`
  - Neu gerendert:
    - `fig_12_weekly_dispatch_shift`
    - `fig_12_cold_weekly_dispatch_shift`
    - `fig_12_march_weekly_dispatch_shift`
    - `fig_12_march_peak_reduction_dispatch_shift`
    - `fig_12_february_peak_reduction_tau3_boiler_start_dispatch_shift`
    - `fig_12_good_week_{november,december,january,february,march,april}_dispatch_shift`
    - `fig_12_november_weekly_dispatch_shift`
  - Technischer Stand:
    - Solarthermie/Geothermie sind aus den sichtbaren Fig.-12-Stacks und CSV-Spalten entfernt.
    - Nutzbare Dispatch-`generation` wird nicht mehr um Spillage gekuerzt.
    - `3 h` Display-Smoothing ist nur im Plot aktiv; CSV/KPIs bleiben roh.
    - Stack-Abdeckung ueber alle neu gerenderten CSVs geprueft: maximale Luecke nur numerisches Rauschen (`< 1e-12 MW`).
    - November-Varianten liefen diesmal ohne Haenger durch.

- 2026-05-06: Fig.-12-Wochenplots final auf `tau=3` mit Peak-Boiler-Startkosten bereinigt.
  - Anlass:
    - Die erste Sammel-Neurenderung enthielt bei mehreren Wochen noch nicht die final gewaehlten Defaults.
    - Aktiver Stand ist jetzt `tau = 3 h`, Boiler-Mindestlast `15 %`, Peak-Boiler-Startkosten `50 EUR/MW/start`.
  - Archiv:
    - nicht passende Root-Outputs `fig_12*dispatch_shift.{png,csv}` nach `Documentation/Papers/thermflex_paper/figures/old/fig12_non_tau3_start_archive_20260506_160101/` verschoben
    - archivierte Dateien: `24`
  - Neu gerendert und im Root-Figures-Ordner belassen:
    - `fig_12_weekly_dispatch_shift`
    - `fig_12_cold_weekly_dispatch_shift`
    - `fig_12_november_weekly_dispatch_shift`
    - `fig_12_march_weekly_dispatch_shift`
    - `fig_12_march_peak_reduction_dispatch_shift`
    - `fig_12_february_peak_reduction_tau3_boiler_start_dispatch_shift`
    - `fig_12_good_week_{november,december,january,february,march,april}_dispatch_shift`
  - Verifikation:
    - Alle Root-CSV-Dateien haben `dh_bus_inertia_tau_h = 3.0`, `gas_boiler_startup_cost_eur_per_mw_start = 50.0` und `gas_boiler_min_partload = 0.15`.
    - Solarthermie/Geothermie sind nicht mehr als Fig.-12-CSV-Spalten exportiert.
    - Stack-Abdeckung geprueft: maximale Restluecke nur numerisches Rauschen.

- 2026-05-07: Neue Fig. 14 als Heizperioden-Mechanismusplot aufgebaut.
  - Neuer Builder:
    - `Documentation/Papers/thermflex_paper/figures/build_fig_14_heating_period_dispatch_response.py`
  - Plotlogik:
    - drei Spalten fuer `2023-12-05` bis `2023-12-07`, `2023-02-27` bis `2023-03-03` und `2023-04-04` bis `2023-04-07`
    - Reihe 1: Reference dispatch als Fig.-12-Stackplot
    - Reihe 2: Upper-only dur24 dispatch als Fig.-12-Stackplot
    - Reihe 3: ThermFlex-Preheat/Cutback-Balken mit `T_in_mean` und `T_in_max` auf Sekundaerachse
    - keine Einsparungsannotation; Legenden liegen ausserhalb der Panels
  - Daten:
    - Dispatch kommt aus den bestehenden aktiven Fig.-12-CSV-Dateien.
    - ThermFlex-State-Reihen werden in `Documentation/Papers/thermflex_paper/figures/_fig_14_state_cache/` separat gecacht und mit Metadata fail-fast geprueft.
  - Outputs:
    - `Documentation/Papers/thermflex_paper/figures/fig_14_heating_period_dispatch_response.png`
    - `Documentation/Papers/thermflex_paper/figures/fig_14_heating_period_dispatch_response.csv`
  - Verifikation:
    - `py_compile` erfolgreich.
    - CSV enthaelt `72 h` Dezember, `120 h` Februar/Maerz und `96 h` April.

- 2026-05-07: Fig. 14 Layout nach Sichtpruefung auf vier Reihen umgestellt.
  - Aenderung:
    - Preheat/Cutback-Balken und Innenraumtemperatur sind nun getrennte Panel-Reihen.
    - `Preheat above ref` und `Avoided heat below ref` sind wieder als transparente Flaechen im Upper-only-Dispatch-Panel sichtbar.
    - Temperaturdiagnostik unten separat mit `T_in_mean` und `T_in_max`.
  - Neu gerendert:
    - `Documentation/Papers/thermflex_paper/figures/fig_14_heating_period_dispatch_response.png`
  - Verifikation:
    - `py_compile` erfolgreich; Re-Render aus vorhandenen Fig.-14-State-Caches ohne neue MILP-Loesung.

- 2026-05-07: Fig. 14 visuell weiter bereinigt.
  - Aenderung:
    - horizontale Y-Gitternetzlinien entfernt; Tagestrennlinien bleiben als Orientierung erhalten.
    - `Preheat above ref` und `Avoided heat below ref` im Upper-only-Dispatch-Panel staerker eingefarbt und durch gestrichelte Referenz-Buslinie besser lesbar gemacht.
    - Setpoint-/untere Komforttemperatur `22.5 deg C` als gestrichelte Linie im Temperaturpanel eingezeichnet.
  - Neu gerendert:
    - `Documentation/Papers/thermflex_paper/figures/fig_14_heating_period_dispatch_response.png`

- 2026-05-07: Fig. 14 auf einheitliche `2 h`-Darstellungsglaettung gestellt.
  - Aenderung:
    - eigener Fig.-14-Display-Smoothing-Parameter `DISPLAY_SMOOTHING_WINDOW_H = 2`
    - geglaettet werden nur die gezeichneten Werte: Dispatch-Stacks, Buslinien, Ref/Flex-Schattierung, Preheat/Cutback-Balken und Temperaturkurven
    - exportierte CSV-Zeitreihen bleiben roh
  - Neu gerendert:
    - `Documentation/Papers/thermflex_paper/figures/fig_14_heating_period_dispatch_response.png`

- 2026-05-07: Fig. 14 Testvariante mit `1 h`-Display-Smoothing und erweitertem Dezemberfenster gerendert.
  - Aenderung:
    - `DISPLAY_SMOOTHING_WINDOW_H = 1`, also ungeglaettete Plotdarstellung
    - Dezember-Panel erweitert auf `2023-12-05 00:00` bis `2023-12-08 23:00`
  - Verifikation:
    - CSV enthaelt jetzt Dezember `96 h`, Februar/Maerz `120 h`, April `96 h`.
    - Re-Render aus vorhandenen Fig.-14-State-Caches ohne neue MILP-Loesung.

- 2026-05-07: Fig. 14 wieder auf `2 h`-Display-Smoothing gesetzt und Temperatur-Kohortenlinien ergaenzt.
  - Aenderung:
    - `DISPLAY_SMOOTHING_WINDOW_H = 2`
    - Fig.-14-State-Cache-Version auf `fig14_tau3_start50_min15_cohort_state_v1` erhoeht
    - State-Cache/CSV exportiert nun `t_in_cohort_01_c` bis `t_in_cohort_08_c`
    - Temperaturpanel zeichnet die acht Kohortenlinien farblich abgestuft; `T_in_mean`, `T_in_max` und Setpoint bleiben erhalten
  - Neu gerendert:
    - `Documentation/Papers/thermflex_paper/figures/fig_14_heating_period_dispatch_response.png`

- 2026-05-07: Gas-CHP-Kapazitaetssensitivitaet fuer das Februar/Maerz-Fig.-14-Panel gescreent.
  - Neuer Screen:
    - `Documentation/Papers/thermflex_paper/figures/build_fig_14_gas_chp_capacity_sensitivity_screen.py`
    - Output: `Documentation/Papers/thermflex_paper/figures/fig_14_gas_chp_capacity_sensitivity_screen.csv`
  - Setup:
    - Variante `february_peak_reduction_tau3_boiler_start`
    - thermische Gas-CHP-Reduktionen `0`, `50`, `100`, `150 MWth`
    - Umrechnung ueber Heat-led-Punkt `eta_th/eta_el = 0.50/0.30`, also `100 MWth` entspricht `60 MWel`
  - Ergebnis:
    - `100 MWth` Reduktion: Referenz-Boiler steigt auf `3.49 GWh` und `255 MW`, Flex-Boiler bleibt bei `0`; visueller Peak-Reduction-Effekt waere staerker.
    - `150 MWth` Reduktion: Referenz-Boiler steigt weiter, aber Flex braucht wieder `1.98 GWh` Boiler; damit zu stark fuer die gewuenschte Mechanismusstory.

- 2026-05-07: Fig. 14 mit `-100 MWth` Gas-CHP-Kapazitaet und Baualters-Temperaturkohorten neu gerendert.
  - Aenderung:
    - Fig.-14-Builder evaluiert die drei Panels nun mit aktiven Fig.-12-Methodensettings plus expliziter thermischer Gas-CHP-Reduktion `GAS_CHP_THERMAL_REDUCTION_MW = 100.0`.
    - Die reduzierten Dispatch- und State-Zeitreihen werden in `_fig_14_state_cache/` mit Metadata fail-fast gecacht.
    - Temperaturdiagnostik aggregiert die acht ThermFlex-Mitglieder zu vier Baualterslinien: `<1975`, `1975-1990`, `1990-2000`, `2000-2014`; `T_in_mean`, `T_in_max` und Setpoint bleiben erhalten.
  - Neu gerendert:
    - `Documentation/Papers/thermflex_paper/figures/fig_14_heating_period_dispatch_response.png`
    - `Documentation/Papers/thermflex_paper/figures/fig_14_heating_period_dispatch_response.csv`
  - Verifikation:
    - `py_compile` erfolgreich.
    - CSV enthaelt `gas_chp_thermal_reduction_mw = 100.0` fuer alle `312` Stunden und die vier `t_in_vintage_*`-Spalten.

- 2026-05-07: Fig. 14 Gas-CHP-Reduktion fuer sichtbare Nicht-Boiler-Grenze auf ca. `1500 MW` erhoeht.
  - Aenderung:
    - `GAS_CHP_THERMAL_REDUCTION_MW` im Fig.-14-Builder von `100.0` auf `320.0` gestellt.
    - Cache-Version auf `fig14_tau3_start50_min15_chpminus320_vintage_state_v1` erhoeht.
  - Ergebnis:
    - Februar/Maerz: Gas-CHP-Waerme-Maximum sinkt auf `1134.55 MW`.
    - Februar/Maerz: Nicht-Boiler-Grenze bei Gas-CHP-Cap liegt bei rund `1499 MW`.
    - Referenz-Boiler steigt auf `375 MW` Peak und `7218 MWh`; Upper-only braucht wegen der staerkeren Kapazitaetsreduktion noch `5677 MWh` Boiler.
  - Neu gerendert:
    - `Documentation/Papers/thermflex_paper/figures/fig_14_heating_period_dispatch_response.png`
    - `Documentation/Papers/thermflex_paper/figures/fig_14_heating_period_dispatch_response.csv`

- 2026-05-07: Februar/Maerz-Fig.-14-Mechanismus auf fehlendes Vorheizen in frueheren Taelern diagnostiziert.
  - Screens:
    - `Documentation/Papers/thermflex_paper/figures/fig_14_feb_mar_preheat_bound_screen.csv`
    - `Documentation/Papers/thermflex_paper/figures/fig_14_feb_mar_boiler_cost_screen.csv`
  - Befund:
    - Hoeherer `event_preheat_peak_bound_multiplier` (`1.25`, `1.5`, `2.0`) aendert Boiler/Preheat praktisch nicht; der Peak-Bound ist daher nicht der aktuelle Engpass.
    - Deutlich hoehere Boiler-Startkosten (`250 EUR/MW/start`) fuehren zu massiv mehr Vorheizen vor den frueheren Peaks und eliminieren den Flex-Boiler in diesem Screen.
  - Interpretation:
    - Das Modell kann die Verschiebung technisch auch an den frueheren Maerz-/Februartagen abbilden.
    - Die derzeitige Kosten-/Startkostenparametrisierung ist fuer diese aggressive Boiler-Vermeidung noch zu schwach; ein staerkerer, dokumentierter Start-/Hot-standby-/Wear-Kostenterm waere die naechste methodische Stellschraube.

- 2026-05-07: Fig. 14 als Boiler-Startkosten-Mechanismusplot mit `250 EUR/MW/start` neu gerendert.
  - Aenderung:
    - `GAS_BOILER_STARTUP_COST_EUR_PER_MW_START = 250.0`
    - Cache-Version `fig14_tau3_start250_min15_chpminus320_vintage_state_v2`
    - CSV-Metadaten korrigiert, sodass MILP-Override und exportierte `gas_boiler_startup_cost_eur_per_mw_start` konsistent `250.0` ausweisen.
  - Ergebnis:
    - Februar/Maerz: Reference-Boiler `7217.72 MWh`, Upper-only-Boiler `0.00 MWh`.
    - Februar/Maerz: Upper-only-Preheat `21157.93 MWh`, Cutback `16911.38 MWh`.
  - Quellencheck:
    - `Documentation/Sources/boiler_startup_cost_notes.md`
    - Befund: Start-/Cycling-Kosten sind literaturgestuetzt real, aber `250 EUR/MW/start` ist fuer Heat-only-DH-Boiler nicht direkt kalibriert und sollte vorerst als Sensitivitaet/Mechanismus-Stresstest behandelt werden.

- 2026-05-07: Startkosten-Schwelle fuer Februar/Maerz-Fig.-14 gescreent.
  - Output:
    - `Documentation/Papers/thermflex_paper/figures/fig_14_feb_mar_startcost_threshold_screen.csv`
  - Ergebnis:
    - `75 EUR/MW/start`: `4589 MWh` Flex-Boiler bleiben.
    - `100 EUR/MW/start`: `3364 MWh` Flex-Boiler bleiben.
    - `125 EUR/MW/start`: `1724 MWh` Flex-Boiler bleiben.
    - `150 EUR/MW/start` und hoeher: Flex-Boiler numerisch `0 MWh`.
  - Einordnung:
    - Die wirksame Schwelle fuer diesen Plot liegt bei rund `150 EUR/MW/start`.
    - Literatur stuetzt Start-/Cycling-Kosten grundsaetzlich, aber ein direkt kalibrierter Heat-only-DH-Boiler-Wert wurde noch nicht gefunden.

- 2026-05-07: Fig. 14 auf `150 EUR/MW/start` umgestellt und `T_in max` aus Plot entfernt.
  - Aenderung:
    - Fig.-14-Builder nutzt `GAS_BOILER_STARTUP_COST_EUR_PER_MW_START = 150.0`.
    - Cache-Version `fig14_tau3_start150_min15_chpminus320_vintage_state_v1`.
    - Rote `T_in max`-Linie wird nicht mehr gezeichnet; Temperaturpanel zeigt nur Baualterslinien, `T_in mean` und Setpoint.
  - Neu gerendert:
    - `Documentation/Papers/thermflex_paper/figures/fig_14_heating_period_dispatch_response.png`
    - `Documentation/Papers/thermflex_paper/figures/fig_14_heating_period_dispatch_response.csv`
  - Verifikation:
    - CSV weist `gas_boiler_startup_cost_eur_per_mw_start = 150.0` und `gas_chp_thermal_reduction_mw = 320.0` aus.
    - Februar/Maerz Upper-only-Boiler bleibt `0.00 MWh`.

- 2026-05-07: Technische Grundlage fuer zeitlich begrenzte ThermFlex-Lower-Relaxation ergaenzt.
  - Aenderung:
    - `Settings/constraints/thermflex.py` enthaelt nun explizit `use_lower_bound_relaxation` und `lower_bound_relaxation_windows`.
    - `integrated_energy_system._thermflex_lower_bound_schedule_c()` senkt die explizite Lower-Bound-Serie nur innerhalb konfigurierter Zeitfenster um `lower_bound_delta_k`.
    - Der Pfad ist fail-fast: Fenster ohne aktiven Schalter, aktiver Schalter ohne Fenster, fehlende Keys, unbekannte Keys, nicht-positive Deltas und `end <= start` brechen ab.
    - `Optimization/run/analysis/csv_exports.py` exportiert Lower-Relaxation-Metadaten in den Dispatch-KPI-Payload: aktiv, Fensteranzahl und maximales Delta.
  - Verifikation:
    - `py_compile` fuer die geaenderten Module erfolgreich.
    - Nicht-rendernder Smoke: Lower Bound bleibt ausserhalb eines Testfensters bei `22.5 C` und sinkt im Fenster `2023-02-27 02:00-05:00` bei `lower_bound_delta_k=1.0` auf `21.5 C`.
    - Gegenprobe: konfigurierte Fenster bei `use_lower_bound_relaxation=False` brechen wie erwartet mit ValueError ab.
  - Einordnung:
    - Es wurde kein neuer MILP-Modus eingefuehrt; die bestehende MILP nutzt weiterhin `thermflex_t_lower_bound_c`.
    - Fuer Tables/Figures muss der jeweilige Runner die Variante weiterhin explizit als eigenen `case_label`/Cache-Key fuehren, z.B. `upper_plus_lower_relaxation`.

- 2026-05-07: Ersten echten Lower-Relaxation-KPI-Screen fuer Februar/Maerz ausgefuehrt.
  - Neues Diagnose-Skript:
    - `Documentation/Papers/thermflex_paper/figures/build_fig_14_lower_relaxation_kpi_screen.py`
  - Output:
    - `Documentation/Papers/thermflex_paper/figures/fig_14_lower_relaxation_kpi_screen.csv`
  - Setup:
    - Variante `february_peak_reduction_tau3_boiler_start`
    - aktive Fig.-14-Settings: `tau_h=3`, `150 EUR/MW/start`, `15%` Boiler-Mindestlast, `-320 MWth` Gas-CHP-Kapazitaet
    - Lower-Relaxation-Fall mit `lower_bound_delta_k=1.0` in zehn expliziten Morgen-/Abendfenstern von `2023-02-27` bis `2023-03-03`
  - Ergebnis gegen Referenz:
    - Upper-only: Waermekosten `-7.59%`, heat-allocated CO2 `+3.85%`, Boiler-Energie/Peak numerisch `0`.
    - Upper+Lower: Waermekosten `-11.43%`, heat-allocated CO2 `-0.33%`, Boiler-Energie/Peak ebenfalls numerisch `0`, `T_in_min=21.5 C`.
  - Zusatznutzen Upper+Lower gegen Upper-only:
    - Waermekosten `-0.600 Mio. EUR` (`-4.16%`)
    - heat-allocated CO2 `-1442 t` (`-4.03%`)
    - Gas-CHP-Waerme `-5.71 GWh`
    - Preheat `-4.27 GWh`, Cutback `+1.49 GWh`
  - Einordnung:
    - Bei den aktuellen `150 EUR/MW/start` ist der Peak-Boiler im Upper-only-Fall bereits eliminiert; Lower Relaxation kann daher in diesem Screen keine weitere Boiler-Reduktion zeigen.
    - Der sichtbare Effekt ist stattdessen ein realistischerer Komfort-/Demand-Reduction-Effekt mit weniger CHP-Waerme, niedrigeren Waermekosten und niedrigeren allokierten CO2-Emissionen.

- 2026-05-07: Lower-Relaxation-KPI-Screen auf `0.5/1.0/2.0 K` Sensitivitaet erweitert und gerechnet.
  - Output aktualisiert:
    - `Documentation/Papers/thermflex_paper/figures/fig_14_lower_relaxation_kpi_screen.csv`
  - Ergebnis gegen Upper-only:
    - `0.5 K`: Waermekosten `-2.36%`, heat-allocated CO2 `-2.30%`, Gas-CHP-Waerme `-3.26 GWh`, Preheat `-2.61 GWh`, Cutback `+0.65 GWh`, `T_in_min=22.0 C`.
    - `1.0 K`: Waermekosten `-4.16%`, heat-allocated CO2 `-4.03%`, Gas-CHP-Waerme `-5.71 GWh`, Preheat `-4.27 GWh`, Cutback `+1.49 GWh`, `T_in_min=21.5 C`.
    - `2.0 K`: Waermekosten `-6.01%`, heat-allocated CO2 `-5.95%`, Gas-CHP-Waerme `-8.44 GWh`, Preheat `-4.62 GWh`, Cutback `+3.83 GWh`, `T_in_min=20.5 C`.
  - Einordnung:
    - Die Richtung ist monoton plausibel: groessere Lower-Relaxation reduziert Vorheizbedarf, Gas-CHP-Waerme, Waermekosten und allokierte CO2.
    - Boiler bleibt in allen Lower-Faellen wie im Upper-only-Fall numerisch eliminiert; die Zusatzstory ist also weniger Ueberheizen/Rebound statt zusaetzliche Boilerreduktion.

- 2026-05-07: Fenster-Sensitivitaet fuer `1.0 K` Lower Relaxation im Februar/Maerz-Screen gerechnet.
  - Neues Diagnose-Skript:
    - `Documentation/Papers/thermflex_paper/figures/build_fig_14_lower_relaxation_window_screen.py`
  - Output:
    - `Documentation/Papers/thermflex_paper/figures/fig_14_lower_relaxation_window_screen.csv`
  - Getestete Fenster:
    - `morning_only`: taeglich `00:00-10:00`
    - `morning_evening`: taeglich `00:00-10:00` und `17:00-22:00`
    - `broad_peak`: taeglich `00:00-12:00` und `16:00-23:00`
  - Zusatznutzen gegen Upper-only:
    - `morning_only`: Waermekosten `-4.07%`, heat-allocated CO2 `-3.96%`, Gas-CHP-Waerme `-5.62 GWh`, Preheat `-4.88 GWh`, Cutback `+0.74 GWh`, `T_in_min=21.5 C`.
    - `morning_evening`: Waermekosten `-4.16%`, heat-allocated CO2 `-4.03%`, Gas-CHP-Waerme `-5.71 GWh`, Preheat `-4.27 GWh`, Cutback `+1.49 GWh`, `T_in_min=21.5 C`.
    - `broad_peak`: Waermekosten `-4.77%`, heat-allocated CO2 `-4.66%`, Gas-CHP-Waerme `-6.61 GWh`, Preheat `-4.54 GWh`, Cutback `+2.06 GWh`, `T_in_min=21.5 C`.
  - Einordnung:
    - Die Richtung bleibt ueber alle Fenster stabil.
    - `morning_evening` ist ein guter mittlerer Hauptfall: staerker als nur Morgenfenster, aber weniger breit/komfortinvasiv als `broad_peak`.

- 2026-05-07: Max-Hours-Alternative fuer Lower Relaxation technisch angetestet.
  - Neues Diagnose-Skript:
    - `Documentation/Papers/thermflex_paper/figures/build_fig_14_lower_relaxation_max_hours_screen.py`
  - Setup:
    - `lower_bound_delta_k=1.0` ueber den gesamten Bewertungszeitraum
    - bestehendes `constraints.thermflex.max_flex_duration_h=6` als Tagesbudget
  - Ergebnis:
    - Reference und normales Upper-only liefen wie erwartet durch.
    - Der erste `upper_plus_lower_max6h`-MILP-Block blieb im Solver haengen und wurde nach `2 h` Timeout abgebrochen.
    - Keine Output-CSV wurde geschrieben; temporaere Override-Datei wurde entfernt.
  - Einordnung:
    - Der bestehende Max-Duration-Pfad schaltet `therm_flex_active` auf binaer und budgetiert jede Abweichung von der Referenzheizung, also Preheat und Cutback gemeinsam.
    - Fuer den aktuellen 192h-Fig.-14-Wochenlauf ist diese generische Max-Hours-Variante deutlich zu schwer.
    - Fuer die Paperfigur bleibt die explizite Zeitfenster-Lower-Relaxation vorerst der robustere Pfad; ein eigener leichter Lower-only-Budgetmechanismus waere ein separater Modellierungsbaustein.

- 2026-05-07: Lower-Relaxation-Zeitfenster gegen Peak-/Cutback-Stunden weiterer Fig.-12-Wochen geprueft.
  - Output:
    - `Documentation/Papers/thermflex_paper/figures/fig_14_lower_relaxation_window_peak_alignment_screen.csv`
  - Befund:
    - Die Top-Referenz-Boiler- und Top-DH-Buslaststunden liegen in den geprueften Heizwochen praktisch durchgehend in den Morgenstunden `00:00-10:00`.
    - Die Top-Upper-only-Cutback-Stunden liegen haeufig in den spaeten Abendstunden, oft auch `22:00`/`23:00`.
    - Das bisherige Fenster `17:00-22:00` schneidet diese spaeten Cutback-Stunden teilweise ab.
    - Ein Abendfenster `17:00-24:00` deckt die Top-Cutback-Stunden in November, Dezember, Maerz und im Februar/Maerz-Peakfall vollstaendig ab und ist robuster als `17:00-22:00`.
  - Einordnung:
    - Fuer den naechsten nicht-rendernden Lower-Relaxation-Lauf sollte der Hauptfall auf `00:00-10:00` plus `17:00-24:00` umgestellt werden.
    - Der Optimierer wird damit nicht zum Cutback gezwungen; er erhaelt nur in diesen Stunden die erlaubte Lower-Bound-Absenkung.

- 2026-05-07: Lower-Relaxation-Hauptscreen auf Peak-abdeckendes Abendfenster `17:00-24:00` umgestellt.
  - Aenderung:
    - `build_fig_14_lower_relaxation_kpi_screen.py` nutzt nun taeglich `00:00-10:00` und `17:00-24:00`.
    - Fig. 14 wurde nicht gerendert; nur der KPI-Screen wurde neu gerechnet.
  - Output aktualisiert:
    - `Documentation/Papers/thermflex_paper/figures/fig_14_lower_relaxation_kpi_screen.csv`
  - Ergebnis gegen Upper-only:
    - `0.5 K`: Waermekosten `-2.36%`, heat-allocated CO2 `-2.30%`, Gas-CHP-Waerme `-3.26 GWh`, Preheat `-2.50 GWh`, Cutback `+0.76 GWh`, `T_in_min=22.0 C`.
    - `1.0 K`: Waermekosten `-4.19%`, heat-allocated CO2 `-4.07%`, Gas-CHP-Waerme `-5.77 GWh`, Preheat `-4.04 GWh`, Cutback `+1.75 GWh`, `T_in_min=21.5 C`.
    - `2.0 K`: Waermekosten `-6.15%`, heat-allocated CO2 `-6.08%`, Gas-CHP-Waerme `-8.62 GWh`, Preheat `-5.36 GWh`, Cutback `+3.30 GWh`, `T_in_min=20.5 C`.
  - Einordnung:
    - Die Richtung bleibt monoton plausibel.
    - `1.0 K` mit `00:00-10:00` und `17:00-24:00` ist nun der bevorzugte Hauptfall fuer die naechste Fig.-14-Vorbereitung.

- 2026-05-07: Fig. 15 Builder fuer Upper-only vs. Upper+Lower vorbereitet, ohne zu rendern.
  - Neue Datei:
    - `Documentation/Papers/thermflex_paper/figures/build_fig_15_upper_lower_relaxation_dispatch_response.py`
  - Setup:
    - eigene Ausgabeziele `fig_15_upper_lower_relaxation_dispatch_response.png/.csv`
    - eigener Cache `_fig_15_state_cache/`
    - drei Periodenspalten analog Fig. 14: Dezember, Februar/Maerz, April
    - Dispatch-Reihen: Reference, Upper-only, Upper+Lower `1 K`
    - Lower-Relaxation-Fenster: taeglich `00:00-10:00` und `17:00-24:00`
    - Lower Bound: `22.5 C -> 21.5 C` nur in diesen Fenstern
  - Status:
    - Fig. 15 wurde nicht gerendert.
    - `py_compile` erfolgreich.
    - Output-Dateien existieren noch nicht; Rendering soll erst nach expliziter Freigabe erfolgen.

- 2026-05-07: Fig. 15 Upper+Lower-Relaxation gerendert.
  - Output:
    - `Documentation/Papers/thermflex_paper/figures/fig_15_upper_lower_relaxation_dispatch_response.png`
    - `Documentation/Papers/thermflex_paper/figures/fig_15_upper_lower_relaxation_dispatch_response.csv`
  - Setup:
    - drei Spalten analog Fig. 14: Dezember, Februar/Maerz, April
    - Reihen: Reference, Upper-only, Upper+Lower `1 K`, Preheat/Cutback, Indoor-Temperatur
    - Lower Relaxation: `22.5 C -> 21.5 C` in taeglichen Fenstern `00:00-10:00` und `17:00-24:00`
    - Upper-Relaxation bleibt im Upper+Lower-Fall unveraendert aktiv.
  - Validierung:
    - Render lief erfolgreich; der zweite Layout-Render nutzte den Fig.-15-Cache.
    - CSV enthaelt `312` Zeilen und `82` Spalten.
    - `py_compile` fuer den Fig.-15-Builder erfolgreich.
    - Layout nach visuellem Check angepasst, damit die linken Reihenlabels nicht abgeschnitten werden.

- 2026-05-07: Fig. 15 Lower-Relaxation auf gleitenden Recovery-Bound umgestellt.
  - Motivation:
    - Die harte Rueckkehr des Lower Bounds von `21.5 C` auf `22.5 C` um `10:00` erzeugte im Dezember sichtbare Recovery-/Nachheiz-Hoecker im Peak Boiler.
  - Modell-Aenderung:
    - `constraints.thermflex.lower_bound_relaxation_windows` akzeptiert nun optional `ramp_out_h`.
    - Innerhalb des Fensters gilt die volle Absenkung; danach laeuft die erlaubte Absenkung linear ueber `ramp_out_h` auf null zurueck.
    - Ueberlappende Fenster nutzen die maximale erlaubte Absenkung statt additiver Doppelabsenkung.
  - Fig.-15-Setup:
    - `ramp_out_h=3.0`
    - Morning-Fenster `00:00-10:00`: Bound `21.5 C` bis `10:00`, dann `21.83 C`, `22.17 C`, ab `13:00` wieder `22.5 C`.
    - Abendfenster `17:00-24:00` analog; Ueberlappung mit dem naechsten Morning-Fenster bleibt bei maximal `1 K` Absenkung.
  - Output:
    - `Documentation/Papers/thermflex_paper/figures/fig_15_upper_lower_relaxation_dispatch_response.png`
    - `Documentation/Papers/thermflex_paper/figures/fig_15_upper_lower_relaxation_dispatch_response.csv`
  - Validierung:
    - `py_compile` erfolgreich.
    - Schedule-Smoke fuer `2023-12-05 08:00-15:00`: `21.5, 21.5, 21.5, 21.833, 22.167, 22.5, 22.5, 22.5`.
    - Neuer Fig.-15-Render erfolgreich; CSV enthaelt `lower_relaxation_ramp_out_h=3.0`.

- 2026-05-07: Fig. 15 auf `4 h` Recovery-Ramp und direkten Upper-only/Upper+Lower-Vergleich in den Diagnose-Reihen umgestellt.
  - Aenderung:
    - `LOWER_RELAXATION_RAMP_OUT_H=4.0`
    - neuer Cache-Key `fig15_tau3_start150_min15_chpminus320_upperlower1k_rampout4h_v1`
    - Reihe 4 zeigt nun Upper-only Preheat/Cutback als blasse Balken und Upper+Lower Preheat/Cutback als kraeftige Balken.
    - Reihe 5 zeigt Upper-only `T_in mean` gestrichelt, Upper+Lower-Kohortenlinien und Upper+Lower `T_in mean` als schwarze Linie.
    - CSV enthaelt zusaetzlich `thermflex_preheat_upper_mwh`, `thermflex_cutback_upper_mwh`, `t_in_mean_upper_c`.
  - Validierung:
    - `py_compile` erfolgreich.
    - Schedule-Smoke fuer `2023-12-05 08:00-16:00`: `21.5, 21.5, 21.5, 21.75, 22.0, 22.25, 22.5, 22.5, 22.5`.
    - Neuer Fig.-15-Render erfolgreich; CSV enthaelt `312` Zeilen, `86` Spalten und `lower_relaxation_ramp_out_h=4.0`.

- 2026-05-07: Fig.-15-Reihe 4 visuell nachgeschaerft.
  - Aenderung:
    - Upper-only Preheat/Cutback wird in Reihe 4 als Outline-Balken dargestellt.
    - Upper+Lower Preheat/Cutback bleibt als gefuellter Balken dargestellt.
  - Status:
    - Keine Daten- oder Modell-Aenderung; Re-Render nutzte den bestehenden `4 h`-Ramp-Cache.
    - `py_compile` erfolgreich.

- 2026-05-07: Fig.-15-Reihe 4 auf blasse Upper-only-Balken mit schwarzer gestrichelter Kontur umgestellt.
  - Aenderung:
    - Upper-only Preheat/Cutback nutzt nun dieselben Orange-/Blau-Farbfamilien wie Upper+Lower, aber blasser und mit schwarzer gestrichelter Kontur.
    - Upper+Lower bleibt kraeftig gefuellt.
  - Status:
    - Reine Darstellungsanpassung; Re-Render nutzte den bestehenden `4 h`-Ramp-Cache.
    - `py_compile` erfolgreich.

- 2026-05-07: Fig.-15-Reihe 4 auf Balken-plus-Linien-Vergleich umgestellt.
  - Aenderung:
    - Upper+Lower Preheat/Cutback bleibt als gefuellte Balken dargestellt.
    - Upper-only Preheat/Cutback wird als gestrichelte Linie in derselben Farbfamilie ueberlagert.
  - Einordnung:
    - Diese Darstellung ist ruhiger als doppelte Balken oder Outline-Balken und trennt Hauptfall und Vergleichsfall klarer.
  - Status:
    - Reine Darstellungsanpassung; Re-Render nutzte den bestehenden `4 h`-Ramp-Cache.
    - `py_compile` erfolgreich.

- 2026-05-07: Fig.-15-Reihe 4 testweise vollstaendig auf Liniengrafik umgestellt.
  - Aenderung:
    - Upper+Lower Preheat/Cutback wird als durchgezogene Orange-/Blau-Linie gezeigt.
    - Upper-only Preheat/Cutback wird als gestrichelte Orange-/Blau-Linie gezeigt.
  - Einordnung:
    - Die Darstellung ist ruhiger als Balkenvarianten, entfernt sich aber von der Fig.-13-Balkenlogik.
  - Status:
    - Reine Darstellungsanpassung; Re-Render nutzte den bestehenden `4 h`-Ramp-Cache.
    - `py_compile` erfolgreich.

- 2026-05-07: Fig. 15 um 2K-Lower-Relaxation-Sensitivitaetsreihe erweitert.
  - Aenderung:
    - neue Dispatch-Reihe `Upper+lower 2K` direkt unter der `Upper+lower 1K`-Reihe
    - `LOWER_RELAXATION_SENSITIVITY_DELTA_K=2.0`
    - neuer Cache-Key `fig15_tau3_start150_min15_chpminus320_upperlower1k2k_rampout4h_v1`
    - CSV enthaelt Lower-2K-Dispatchspalten mit Suffix `_lower2_mw` sowie `lower_relaxation_sensitivity_delta_k=2.0`
    - Diagnose-Reihen unten bleiben bewusst auf dem 1K-Hauptfall und sind als `1K response` / `1K indoor temp.` beschriftet.
  - Validierung:
    - `py_compile` erfolgreich.
    - Schedule-Smoke 2K fuer `2023-12-05 08:00-16:00`: `20.5, 20.5, 20.5, 21.0, 21.5, 22.0, 22.5, 22.5, 22.5`.
    - Neuer Fig.-15-Render erfolgreich; CSV enthaelt `312` Zeilen und `108` Spalten.

- 2026-05-07: Fig. 15 wieder auf 1K-Lower-Relaxation-Hauptfall reduziert.
  - Aenderung:
    - 2K-Sensitivitaetsreihe aus dem Fig.-15-Builder entfernt.
    - Plotlayout wieder auf 5 Reihen gesetzt: Reference, Upper-only, Upper+lower 1K, 1K response, 1K indoor temp.
    - CSV-Export enthaelt keine `_lower2`- oder Sensitivitaetsspalten mehr.
  - Validierung:
    - `py_compile` erfolgreich.
    - Re-Render nutzte den bestehenden 1K-Cache `fig15_tau3_start150_min15_chpminus320_upperlower1k_rampout4h_v1`.
    - Output-CSV enthaelt `312` Zeilen und `86` Spalten; `lower_relaxation_delta_k=1.0`, `lower_relaxation_ramp_out_h=4.0`.

- 2026-05-07: Fig. 15 Diagnose-Reihen besser lesbar gemacht.
  - Aenderung:
    - `1K response`- und `1K indoor temp.`-Reihen im Plotlayout hoeher gesetzt.
    - Bottom-Zeitachse auf 4h-Tageszeitlabels umgestellt; Datumswechsel werden zweizeilig mit Tageslabel und `00` markiert.
  - Status:
    - reine Darstellungsanpassung ohne neue MILP-Rechnung.
    - Re-Render nutzte den bestehenden 1K-Cache.

- 2026-05-08: Fig. 15 auf Paper-Layout mit rechten Legenden und neuer Source-Farbgebung umgestellt.
  - Aenderung:
    - Alle fuenf Reihen gleich hoch gesetzt.
    - Temperaturreihe oben auf `27.5 deg C` begrenzt; Setpoint- und Lower-bound-Linien aus der Temperaturreihe entfernt.
    - Source-Stack nur im Plot neu gruppiert: Waste incineration und external waste heat werden als `Waste heat` lila zusammengefasst.
    - Plotfarben angepasst: Peak boiler schwarz, Gas CHP hellgrau, Waste lila, Biomass CHP gruen, Heat pump blau.
    - Verschobene Waermeflaechen in den Dispatch-Reihen werden transparent in der Farbe der dominant verschobenen Source gezeichnet.
    - Achsentitel entfernt; Legenden rechts neben den Plot gesetzt und nach Stack, Response und Temperatur getrennt.
  - Status:
    - reine Darstellungsanpassung; CSV/KPIs und Cache bleiben methodisch unveraendert.
    - `py_compile` erfolgreich; Re-Render aus bestehendem 1K-Cache.

- 2026-05-08: Fig. 15 Shift-Flaechen und Legendenposition nachjustiert.
  - Aenderung:
    - Y-Achsentitel fuer alle fuenf Reihen wieder ergaenzt.
    - Preheat-/Cutback-Flaechen in den Dispatch-Reihen wieder semantisch codiert: orange fuer `preheat above ref`, blau fuer `avoided heat below ref`.
    - Rechte Legenden naeher an die Panels geschoben und Schrift leicht vergroessert.
  - Status:
    - reine Darstellungsanpassung ohne neue MILP-Rechnung.
    - `py_compile` erfolgreich; Re-Render aus bestehendem 1K-Cache.

- 2026-05-08: Neue Fig.-06b Cohort-Duration-Figure vorbereitet, Render wegen Lower-Duration-Solvezeit gestoppt.
  - Aenderung:
    - Neuer additiver Builder `Documentation/Papers/thermflex_paper/figures/build_fig_06b_cohort_duration_upper_lower.py`.
    - Alte Fig. 06 bleibt unveraendert.
    - Ziel-Layout: drei Fig.-15-Perioden, zwei Reihen (`upper-only`, `upper+lower 1K`), Duration-Balken `1/4/8/12/24 h`, tau 4.
    - Eigener validierter Cache unter `_fig_06b_duration_cache/`.
    - Evaluation auf Periodenfenster plus 24h Warm-up gekuerzt; Cache-Version `v3` variiert nur `max_flex_duration_h`, nicht die Event-Anzahl.
  - Status:
    - `py_compile` erfolgreich.
    - `upper-only` fuer Dezember wurde vollstaendig gecacht.
    - Der erste `upper+lower 1K`-Duration-Case schreibt auch nach 60 Minuten keinen Cache; weitere Blind-Renderlaeufe wurden gestoppt.
    - Naechster sinnvoller Schritt ist eine gezielte Diagnose/Beschleunigung der lower-relaxation-plus-duration-MILP, bevor die volle 30-Case-Figure gerechnet wird.

- 2026-05-08: Fig.-06b Lower-Duration-Solvezeit diagnostiziert.
  - Aenderung:
    - `dispatch/modes/milp_day_ahead.py` um optionale Env-Diagnoseflags erweitert:
      - `THERMFLEX_MILP_DIAG=1` aktiviert Modellgroessen und HiGHS-Log.
      - `THERMFLEX_HIGHS_TIME_LIMIT_S` setzt ein HiGHS-Time-Limit.
      - `THERMFLEX_HIGHS_MIP_REL_GAP` setzt die HiGHS-MIP-Gap-Toleranz.
    - Fig.-06b-Builder um `--single-period/--single-case/--single-duration` ergaenzt, damit einzelne Cache-Cases diagnostiziert werden koennen.
  - Befund:
    - Langsamer Fall: `December`, `upper_plus_lower_1k`, `duration=1`, tau 4.
    - Jeder 36h-Rolling-Block hat ca. 4076 Variablen, 864 Binaries und 4496 Constraints; nach Presolve bleiben ca. 1850-1900 Variablen und ca. 360-470 Binaries.
    - Ursache ist nicht fehlende Feasibility: HiGHS findet schnell zulaessige Loesungen, haengt aber beim Optimalitaetsbeweis im Branch-and-bound.
    - Mit 0.1% MIP-Gap loesen die ersten drei Dezember-Bloecke in ca. 15-63 s; Block 4 (`2023-12-07`) erreicht nach 600 s nur ca. 0.222% Gap.
    - Die Kombination aus `upper+lower` und `max_flex_duration_h < 24` macht `therm_flex_active` binaer und nutzt dieselbe Variable zugleich fuer Heat-Deviation-Gating und Komfortgrenzen-Freigabe.

- 2026-05-08: Fig.-06b Duration-Set und 0.5%-MIP-Gap einzeln geprueft.
  - Aenderung:
    - Neuer Fig.-06b-Builder nutzt fuer beide Faelle nur noch `1, 6, 12 h`.
    - Fig.-06b setzt lokal `THERMFLEX_HIGHS_MIP_REL_GAP=0.005` und dokumentiert `mip_rel_gap_target` in der Cache-Metadatenlogik.
  - Test:
    - Einzelcase `December / upper+lower 1K / duration=1h`, tau 4, mit Diagnose-Log und 600s-Sicherheitslimit.
  - Befund:
    - Voller Einzelcase laeuft in ca. 384 s durch.
    - Die ersten drei 36h-Bloecke loesen mit 0.5%-Gap in ca. 11-14 s Solverzeit.
    - Der bekannte schwere Block `2023-12-07` loest mit 0.5%-Gap in ca. 295 s; vorher erreichte derselbe Block mit 0.1%-Gap nach 600 s noch keinen akzeptierten Abschluss.
  - Status:
    - 0.5%-Gap ist wirksam, aber der Lower-1h-Fall bleibt teuer; kein Full-Render gestartet.

- 2026-05-08: Fig.-06b Full-Render wegen Upper+Lower-Duration-Case gestoppt.
  - Versuch:
    - Full-Render mit `1, 6, 12 h` fuer upper-only und upper+lower 1K gestartet.
    - Der Lauf schrieb Cache-Dateien fuer Dezember komplett, Februar upper-only komplett und Februar upper+lower 1h.
  - Abbruch:
    - Der 3h-Full-Render brach waehrend `February/March / upper+lower 1K / duration=6h` ab.
    - Ein gezielter Resume dieses Einzelcases lief weitere 6h und brach erneut ab.
  - Befund:
    - `February/March / upper+lower 1K / duration=6h` ist deutlich schwerer als der zuvor getestete Dezember-1h-Fall.
    - Block 1 loeste in ca. 422 s, Block 2 in ca. 15612 s (~4.3 h), Block 3 in ca. 5506 s (~1.5 h); Block 4 war beim 6h-Timeout noch aktiv.
    - Da Fig.-06b aktuell nur pro komplettem Case cached, gehen erfolgreiche Rolling-Bloecke innerhalb eines abgebrochenen Cases wieder verloren.
  - Status:
    - Kein vollstaendiger Fig.-06b-Export erzeugt.
    - Naechster sinnvoller Schritt ist nicht ein weiterer Blind-Render, sondern Rolling-Block-/Case-Resume oder eine einfachere Darstellungslogik fuer upper+lower-Duration.

- 2026-05-09: Fig.-06b auf reine Upper-only-Duration-Story reduziert und gerendert.
  - Aenderung:
    - `build_fig_06b_cohort_duration_upper_lower.py` zeigt nur noch `upper-only`.
    - Duration-Set fuer den Plot: `1, 4, 8, 12 h`.
    - `upper+lower 1K` wurde aus dieser Mechanismusfigur entfernt; der Vergleich bleibt in Fig. 15.
    - Fuer die reine Mechanismusgrafik wird lokal `mip_rel_gap=0.005` gesetzt und in der Cache-Metadatenlogik dokumentiert.
  - Befund:
    - Auch upper-only ohne MIP-Gap kann einzelne Blöcke sehr lange beim Optimalitätsbeweis halten; der exakte April-4h-Case lief in Block 2 ca. 10610 s.
    - Mit dokumentiertem 0.5%-Gap wurde die vollstaendige upper-only-Figur in ca. 62 min gerendert.
  - Output:
    - `Documentation/Papers/thermflex_paper/figures/fig_06b_cohort_duration_upper_lower_tau4.png`
    - `Documentation/Papers/thermflex_paper/figures/fig_06b_cohort_duration_upper_lower_tau4.csv`

- 2026-05-10: Fig. 16 Flexibility-Performance-Map als erster Scatterplot-Builder angelegt.
  - Aenderung:
    - Neuer additiver Builder:
      - `Documentation/Papers/thermflex_paper/figures/build_fig_16_flexibility_performance_map.py`
    - Der Builder liest ausschliesslich vorhandene Fig.-15-CSVs und startet keine MILP-Laeufe.
    - Jeder Punkt entspricht `period x case x tau`.
  - Kodierung:
    - x: Kosteneinsparung [%] (`-cost_delta_pct`)
    - y: CO2-Einsparung [%] (`-co2_delta_pct`)
    - Farbe: Zeitraum (`December`, `February/March`, `April`)
    - Marker: `Upper-only` vs. `Upper + lower 1 K`
    - Punktgroesse: Peak-Boiler-Energie-Reduktion [%]
  - Output:
    - `Documentation/Papers/thermflex_paper/figures/fig_16_flexibility_performance_map.png`
    - `Documentation/Papers/thermflex_paper/figures/fig_16_flexibility_performance_map.csv`
  - Befund fuer naechste Iteration:
    - Prozentuale Peak-Boiler-Reduktion macht Februar/Maerz-Punkte sehr gross, weil der Boiler dort in einigen Faellen praktisch auf null faellt.
    - Fuer die Paper-Version wahrscheinlich absolute Boiler-Reduktion in MWh/GWh als Punktgroesse pruefen.

- 2026-05-10: Fig. 16 Scatterplot auf neutrale Trade-off-Darstellung erweitert.
  - Aenderung:
    - Punktgroesse auf absolute Peak-Boiler-Energie-Reduktion in GWh umgestellt.
    - Vorhandene Fig.-12-Wochenpunkte fuer November bis April ergaenzt.
    - Direkte Punkt- und Quadrantenannotation entfernt.
    - Bunte No-regret-/Trade-off-Flächen entfernt; Trade-off-Halbraeume nur noch hellgrau markiert.
  - Status:
    - Re-Render aus bestehenden CSVs, keine neuen MILP-Laeufe.

- 2026-05-08: Fig. 15 Paper-Layout weiter verdichtet.
  - Aenderung:
    - X-Achse von 4h- auf 6h-Zeitlabels umgestellt.
    - Legenden nochmals naeher an die Plotreihen geschoben und Schrift vergroessert.
    - Paneltitel, Y-Achsentitel und Ticklabels moderat vergroessert.
    - `Preheat above ref` als hellbraune Flaeche gesetzt, damit Preheat auf Peak-Boiler-Abschnitten weniger hart orange wirkt.
    - Stack-Legende um `Preheat above ref` und `Avoided heat below ref` erweitert.
    - Mittelwert-Temperaturlinien aus Reihe 5 entfernt; sichtbar bleiben nur die vier Kohortenlinien.
  - Status:
    - reine Darstellungsanpassung; CSV/KPIs unveraendert.
    - `py_compile` erfolgreich; Re-Render aus bestehendem 1K-Cache.

- 2026-05-08: Fig. 15 Tau-Sensitivitaet fuer `tau=4/5/6` gerechnet.
  - Aenderung:
    - Fig.-15-Builder um optionale Tau-Sensitivitaets-Outputs erweitert.
    - Neue Plots/CSVs:
      - `fig_15_upper_lower_relaxation_dispatch_response_tau4.{png,csv}`
      - `fig_15_upper_lower_relaxation_dispatch_response_tau5.{png,csv}`
      - `fig_15_upper_lower_relaxation_dispatch_response_tau6.{png,csv}`
    - KPI-Summaries:
      - `fig_15_tau_sensitivity_kpis.csv` fuer Tau 4-6
      - `fig_15_tau3_to_tau6_kpi_comparison.csv` inklusive Tau 3 Hauptfall
  - Zentrale KPI-Tendenz:
    - Hoeheres Tau glaettet die Buslast visuell, reduziert aber die Kosten-/CO2-Einsparungen, besonders im April.
    - Upper+lower 1K April-Kostendelta: Tau 3 `-21.06%`, Tau 4 `-16.52%`, Tau 5 `-12.89%`, Tau 6 `-6.17%`.
    - Upper+lower 1K April-CO2-Delta: Tau 3 `-21.56%`, Tau 4 `-16.99%`, Tau 5 `-13.42%`, Tau 6 `-6.50%`.
  - Status:
    - Neue MILP-Rechnungen fuer Tau 4-6 erfolgreich abgeschlossen.

- 2026-05-12: ThermFlex-Surrogat-Zielstruktur im `Learning/`-Layer additiv vorbereitet.
  - Motivation:
    - Heizperioden- und Sensitivitaetsauswertungen fuer das ThermFlex-Paper werden mit Truth-MILP fuer `tau`, `duration` sowie `0K/1K/2K` lower relaxation zu teuer.
    - Der neue Lernpfad soll nicht table-spezifisch sein, sondern allgemeine taegliche ThermFlex-Resultate fuer Paper- und Screening-Auswertungen tragen.
  - Aenderung:
    - neue Substruktur `Learning/thermflex_daily_results/` angelegt
    - `README.md` beschreibt Scope, Tagesvertrag, Validierungsrichtung und die bewusste Abgrenzung gegen einen nur `Table 09`-spezifischen Pfad
    - initiale Modul-Skelette angelegt:
      - `schema.py`
      - `dataset_builder.py`
      - `features.py`
      - `targets.py`
      - `train.py`
      - `validate.py`
      - `predict.py`
      - `aggregate.py`
    - `Learning/README.md` um den allgemeinen ThermFlex-Daily-Results-Layer erweitert
  - Status:
    - bewusst nur Architektur- und Vertragsvorbereitung; noch keine Trainings- oder Inferenzlogik implementiert
    - naechster Schritt ist die explizite Truth-/Feature-/Target-Spaltendefinition aus dem Cache-Snapshot und den Gold-Daily-Screens

- 2026-05-12: ThermFlex-Daily-Results-Vertrag auf reale Screen-CSV-Spalten geerdet.
  - Quelle:
    - `Optimization/run/results/Vienna/gold/daily_thermflex_screen_*/heating_season_day_screen.csv`
    - `Optimization/run/analysis/screen_vienna_constant_thermflex_heating_season_days.py`
    - `Documentation/Papers/thermflex_paper/tables/build_table_09_heating_season_kpis.py`
  - Aenderung:
    - `Learning/thermflex_daily_results/schema.py` auf die aktuell real exportierten Tages-Spalten erweitert
    - explizite Trennung eingefuehrt zwischen:
      - Policy-Deskriptoren
      - Kontext-Features
      - REF-Features
      - Zielspalten
      - Builder-Metadaten fuer Bundle-/Quelltracking
    - `dataset_builder.py` enthaelt jetzt einen ersten realen Loader:
      - `discover_screen_csvs()`
      - `load_daily_results_truth_table()`
    - der Loader merged mehrere Screen-Bundles zu einer auditierbaren Truth-Tabelle, fuegt Bundle-Metadaten hinzu und validiert die Pflichtspalten hart
  - Status:
    - persistierter `Learning/datasets/`-Datensatz ist noch offen
    - naechster fachlicher Schritt ist die Entscheidung, welche Policy-Parameter (`tau`, `duration`, lower relaxation) aus Bundle-/Override-Namen explizit als Modellfeatures abgeleitet werden

- 2026-05-12: Legacy-Daily-Screens explizit normalisiert und Policy-Metadaten aus Override-SSOT abgeleitet.
  - Aenderung:
    - `dataset_builder.py` unterstuetzt jetzt neben `screen_v2_current` auch explizit `screen_v1_upper_legacy`
    - Legacy-Normalisierung:
      - `*_upper_1h` -> `*_flex`
      - fehlende `flex_override_name` aus `heating_season_day_screen.md`
      - fehlende `irradiance_proxy_sum` / `solargains_proxy_sum` ueber den kanonischen Tageskontext nach Datum angereichert
    - policy descriptors werden jetzt aus der referenzierten ThermFlex-Override-Datei abgeleitet:
      - `policy_duration_h`
      - `policy_lower_relaxation_k`
      - `policy_tau_h`
      - `policy_max_events_per_day`
      - `policy_upper_only`
      - `policy_case_label_canonical`
    - exportierte Case-Labels bleiben erhalten; zusaetzlich wird `policy_case_label_matches_export` gespeichert
  - Befund:
    - Snapshot ergibt aktuell `7` fertige Bundles mit zusammen `1274` Tageszeilen
    - dabei wurden zwei explizite Inkonsistenzen sichtbar:
      - `daily_thermflex_screen_dur24_20260422_151407` exportiert `UPPER_24H`, referenziert laut Override aber faktisch `UPPER_1H`
      - `daily_thermflex_screen_pilot_lb21p5_dur4_evt24_20260510_165955` nutzt ein abweichendes Pilot-Label, ist kanonisch aber `LOWER1K_DUR4_EVT24`
  - Status:
    - Inkonsistenzen werden jetzt sichtbar statt still verschluckt
    - naechster Schritt ist der persistierte Datensatzvertrag in `Learning/datasets/` plus Split-/Group-Definition fuer Training und Holdout

- 2026-05-12: Erster kuratierter ThermFlex-Daily-Results-Datensatz nach `Learning/datasets/` exportiert und erste XGB-Baseline trainiert.
  - Datensatz-Export:
    - neuer kuratierter Exportpfad in `Learning/thermflex_daily_results/dataset_builder.py`
    - dedupliziert Bundles ueber Root-Reihenfolge, normalisiert Legacy-Screens explizit und persistiert:
      - `training_data.npz`
      - `training_data.meta.json`
      - `truth_dataset.csv`
      - `truth_dataset.meta.json`
      - `family_spec.json`
      - `source_runs.json`
    - aktueller Datensatz:
      - family hash `e0df98cac99aa1215507ccf8936833ed9df90cb71c857312ab15635aa3364de8`
      - Pfad `Learning/datasets/e0df98cac99aa1215507ccf8936833ed9df90cb71c857312ab15635aa3364de8/`
      - `1274` Truth-Zeilen im Snapshot gesichtet
      - `1272` Zeilen fuer Training selektiert
      - Pilot-Bundle mit `2` Zeilen standardmaessig ausgeschlossen
  - Split-/Group-Logik:
    - `Learning/thermflex_daily_results/validate.py` fuehrt ersten grouped holdout ueber `split_group_bundle`
    - erster Holdout:
      - Train-Bundles:
        - `daily_thermflex_screen_dur24_20260423_213718`
        - `daily_thermflex_screen_dur24_20260510_121921`
        - `daily_thermflex_screen_lb21p5_dur1_evt24_20260510_180853`
      - Test-Bundles:
        - `daily_thermflex_screen_20260421_160246`
        - `daily_thermflex_screen_dur24_20260422_151407`
        - `daily_thermflex_screen_lb21p5_dur4_evt24_20260510_194946`
  - XGB-Baseline:
    - `Learning/thermflex_daily_results/train.py` trainiert target-weise `XGBRegressor`
    - Modellartefakt:
      - `Learning/models/thermflex_daily_results_xgb_e0df98cac99a/`
    - Holdout-Metriken liegen unter:
      - `holdout_metrics.csv`
      - `holdout_split.json`
    - aktueller Baseline-Schnitt trainiert nur auf voll verfuegbaren Targets; explizit ausgeschlossen wurden:
      - `district_gas_boiler_peak_pct_change`
      - `district_gas_boiler_generation_pct_change`
      - Grund: NaNs bei Null-Referenzwerten, keine stille Imputation
  - Erster Befund:
    - Der End-to-End-Pfad steht technisch, aber die erste Baseline ist fachlich noch schwach.
    - Besonders schlecht generalisieren aktuell:
      - `thermflex_shifted_space_heat_kwh`
      - `thermflex_rebound_kwh`
      - `thermflex_rebound_over_shifted_pct`
      - `dispatch_operating_cost_eur_delta`
    - Deutlich brauchbarer sind erste Signale bei:
      - `co2_emissions_total_pct_change`
      - `district_gas_boiler_peak_kw_delta`
      - `thermflex_peak_change_kw`
    - naechster Hebel ist damit nicht mehr die Infrastruktur, sondern:
      - groessere / sauberere Trainingsbasis
      - explizite Entscheidung zum Umgang mit den Legacy-Bundles
      - ggf. zielgruppenspezifischerer Target-Schnitt statt alles in eine erste Baseline zu werfen

- 2026-05-12: ThermFlex-Daily-Results-Baseline um verwertbare Checkpoint-Bundles erweitert und gegen Legacy-Ausschluss gegengeprueft.
  - Aenderung:
    - `dataset_builder.py` kann jetzt optional groessere `heating_season_day_screen_checkpoint.csv`-Dateien aufnehmen
    - dabei werden nur Checkpoints ohne fertige End-CSV und nur ab einer expliziten Mindestzeilenzahl zugelassen
    - neuer Metadatenpfad:
      - `source_screen_kind = final|checkpoint`
      - optional `include_legacy_bundles`
  - Relevanter Zusatzfall:
    - `daily_thermflex_screen_lb21p5_dur8_evt24_20260511_074549`
    - nur als Checkpoint vorhanden, aber mit `83` Tageszeilen gross genug fuer kontrollierte Aufnahme
    - `daily_thermflex_screen_lb21p5_dur1_evt24_20260510_174132` bleibt draussen, weil nur `5` Checkpoint-Zeilen
  - Vergleichsstand 1: Snapshot + `dur8`-Checkpoint + Legacy drin
    - Datensatz:
      - family hash `5896cea66bbaf7b4351bee3ee983be0fa75e8811658d093be206c48d7b1b6011`
      - `1355` selektierte Zeilen
      - `7` Bundles
    - Modell:
      - `Learning/models/thermflex_daily_results_xgb_5896cea66bba/`
    - Befund:
      - `dur8` erhoeht die Policy-Breite, verbessert die Holdout-Qualitaet aber noch nicht substanziell
  - Vergleichsstand 2: nur `screen_v2_current` + `dur8`-Checkpoint, Legacy ausgeschlossen
    - Datensatz:
      - family hash `6161b53af912319129fbba0ab5c5984a97b74be6ce7359e1489c0661be5ac31d`
      - `931` selektierte Zeilen
      - `5` Bundles
    - Modell:
      - `Learning/models/thermflex_daily_results_xgb_6161b53af912/`
    - Befund:
      - reiner Legacy-Ausschluss loest das Generalisierungsproblem nicht
      - einige Targets werden leicht besser (`co2_emissions_total_pct_change`), andere deutlich instabiler (`dispatch_operating_cost_pct_change`, `joint_savings_score`)
  - Zwischenfazit:
    - der Engpass ist jetzt nicht mehr Datensatz-Infrastruktur, sondern:
      - zu wenige voneinander wirklich verschiedene Bundles
      - harter Bundle-Holdout bei kleinem Fallraum
      - zu breiter erster Target-Schnitt, vor allem bei Rebound-/Shift-Zielen

- 2026-05-12: Zentralen Artefakt-Katalog fuer wiederverwendbare Learning-Quellen aufgesetzt und alte Repo-Artefakte explizit klassifiziert.
  - Neuer Codepfad:
    - `Learning/datasets/artifact_inventory.py`
  - Persistierte Katalogartefakte:
    - `Learning/datasets/artifact_inventory.json`
    - `Learning/datasets/artifact_inventory.csv`
    - `Learning/datasets/artifact_inventory_summary.json`
  - Motivation:
    - alte Repo-Artefakte sollen fuer das Zielbild wiederverwendbar sein, aber nur familienrein
    - Modell-Metadaten (`surrogate_bundle.meta.json`) sind keine Trainingszeilen
    - alte `truth_dataset.csv`-Exporte duerfen nicht still mit den neuen Tages-Screen-Daten vermischt werden
  - Aktueller Katalogstand:
    - `318` Artefakte insgesamt
    - `160` `building_teacher_hourly`-Exporte -> kompatibel mit `building_response_v1`
    - `32` ThermFlex-Day-Screen-Tabellen (`9` eindeutige Bundles, jeweils Gold + Cache, final/checkpoint) -> kompatibel mit `thermflex_daily_results_v1`
    - `106` alte ThermFlex/System-`truth_dataset.csv`-Runs -> als eigene Truth-Familie `thermflex_system_design_future`
    - `12` `surrogate_model_bundle_meta`-Artefakte -> nur Audit/Modellhistorie, nicht Training
    - `8` bereits kuratierte `Learning/datasets/`-Truth-Datensaetze
  - Fachlicher Schluss:
    - fuer den aktuellen `thermflex_daily_results`-Pfad gibt es keine neue kompatible Truth-Familie ausser den `daily_thermflex_screen_*`-Screens
    - die alten `truth_dataset.csv`-Runs sind trotzdem wertvoll, aber fuer einen spaeteren separaten ThermFlex-System-/Design-Surrogatpfad
    - der zentrale Katalog verhindert, dass kuenftig alte Artefakte ad hoc und still vermischt werden

- 2026-05-12: Repo-Regel fuer strukturierte Ablage und Wiederverwendung von Run-Artefakten explizit verankert.
  - Kurzregel repo-weit ergaenzt in:
    - `AGENTS.md`
    - `Documentation/coding_rules.md`
  - Inhalt:
    - rohe Run-Outputs bleiben in den produzierenden Run-Pfaden
    - wiederverwendbare Learning-Artefakte muessen ueber `Learning/datasets/`-Inventar und kuratierte Dataset-Pfade sichtbar gemacht werden
    - inkompatible Artefaktfamilien duerfen nicht still in einem Trainingssatz vermischt werden

- 2026-05-12: Separaten ThermFlex-System-/MILP-Surrogatpfad aus alten `truth_dataset.csv`-Runs aufgesetzt und erste Baseline trainiert.
  - Neuer Layer:
    - `Learning/thermflex_system_results/`
    - Dateien:
      - `README.md`
      - `schema.py`
      - `dataset_builder.py`
      - `validate.py`
      - `train.py`
  - Datengrundlage:
    - `106` katalogisierte alte ThermFlex/System-`truth_dataset.csv`-Artefakte im Repo
    - fuer den ersten V1-Vertrag werden die `5` `gold_smoke`-Runs bewusst ausgeschlossen
    - verbleibender stabiler nicht-Smoke-Pool:
      - `101` Truth-Zeilen
      - `101` source runs
      - `42` gemeinsame Pflichtspalten ueber die nicht-Smoke-Schemata
  - Erster kuratierter Datensatz:
    - family hash `af85995ef7734d1914b58a9d981511e7106fb2d35664b4aa9450d6e37b993d6d`
    - Pfad:
      - `Learning/datasets/af85995ef7734d1914b58a9d981511e7106fb2d35664b4aa9450d6e37b993d6d/`
    - Family:
      - `thermflex_system_results`
    - Features:
      - Designvariablen
      - abgeleitete ThermFlex-Policy-Deskriptoren aus dem Run-Slug (`lb`, `dur`, `evt`, ThermFlex an/aus)
      - kategorische Run-Tags (`dispatch_formulation_tag`, `thermflex_case_slug`, `source_schema_version`)
  - Erste XGB-Baseline:
    - Modellpfad:
      - `Learning/models/thermflex_system_results_xgb_af85995ef773/`
    - Holdout:
      - grouped split ueber `split_group_case`
      - `72` Train-Zeilen, `29` Test-Zeilen
      - mittleres `R2` ueber alle Targets: `0.157`
    - staerkere erste Targets:
      - `E_district_gas_chp_thermal_generation_kWh`: `R2 0.723`
      - `E_district_gas_chp_fuel_input_kWh`: `R2 0.723`
      - `V_district_gas_chp_fuel_input_m3`: `R2 0.723`
      - `E_district_gas_chp_electric_generation_kWh`: `R2 0.723`
      - `E_district_thermal_storage_discharge_kWh`: `R2 0.450`
      - `E_district_thermal_storage_charge_kWh`: `R2 0.430`
    - schwache erste Targets:
      - `dispatch_cost_eur`: `R2 -0.661`
      - `E_district_heat_pump_thermal_generation_kWh`: `R2 -0.328`
      - `E_district_heat_pump_electricity_kWh`: `R2 -0.328`
      - `E_district_external_heat_generation_kWh`: `R2 -0.144`
      - Gasboiler-Outputs um `R2 -0.10`
  - Fachlicher Schluss:
    - ja, der MILP-/System-Run-Surrogatpfad sollte trainiert werden und ist jetzt als separater Strang aufgesetzt
    - die alten System-Truths sind dafuer brauchbar
    - sie duerfen aber nicht mit dem Tages-Screen-Surrogat vermischt werden

- 2026-05-12: Explizite Target-Profile fuer beide ThermFlex-Surrogatpfade eingefuehrt und fokussierte zweite Baselines trainiert.
  - Tages-Screen-Pfad:
    - neuer Profilname:
      - `robust_kpi`
    - Zielmenge:
      - `dispatch_operating_cost_pct_change`
      - `co2_emissions_total_pct_change`
      - `district_gas_boiler_peak_kw_delta`
      - `district_gas_boiler_generation_kwh_delta`
      - `dh_total_peak_change_kw`
      - `thermflex_peak_change_kw`
    - Modell:
      - `Learning/models/thermflex_daily_results_xgb_robust_kpi_5896cea66bba/`
    - Holdout:
      - weiterhin grouped split ueber Bundles
      - mittleres `R2`: `0.228`
    - Einzelziele:
      - `thermflex_peak_change_kw`: `R2 0.396`
      - `dh_total_peak_change_kw`: `R2 0.380`
      - `district_gas_boiler_peak_kw_delta`: `R2 0.371`
      - `co2_emissions_total_pct_change`: `R2 0.210`
      - `district_gas_boiler_generation_kwh_delta`: `R2 0.192`
      - `dispatch_operating_cost_pct_change`: `R2 -0.182`
    - Schluss:
      - der fokussierte KPI-Schnitt ist sinnvoller als der erste All-Target-Lauf
      - Kosten bleiben der schwache Punkt

  - System-/MILP-Pfad:
    - neuer Profilname:
      - `robust_heat_system`
    - Zielmenge:
      - Gas-CHP electric / thermal / fuel
      - Gasboiler generation / fuel
      - Thermal-storage charge / discharge
      - `dispatch_cost_eur`
    - Modell:
      - `Learning/models/thermflex_system_results_xgb_robust_heat_system_af85995ef773/`
    - Holdout:
      - grouped split ueber `split_group_case`
      - mittleres `R2`: `0.273`
    - Einzelziele:
      - Gas-CHP electric / thermal / fuel jeweils `R2 0.723`
      - Thermal-storage charge `R2 0.430`
      - Thermal-storage discharge `R2 0.450`
      - Gasboiler generation / fuel jeweils etwa `R2 -0.101`
      - `dispatch_cost_eur`: `R2 -0.661`
    - Schluss:
      - der fokussierte Heat-System-Schnitt verbessert die mittlere Modellguete
      - Kosten und Boiler bleiben auch hier die schwierigsten Targets

- 2026-05-12: Homogenitaetstests fuer die ThermFlex-Kostenziele durchgefuehrt.
  - Motivation:
    - bevor weitere Cost-Logik eingebaut wird, pruefen ob die schwachen Kostenziele primär aus gemischten Datensaetzen kommen
  - Daily-Pfad:
    - Test auf dem current-only-Datensatz
      - family hash `6161b53af912319129fbba0ab5c5984a97b74be6ce7359e1489c0661be5ac31d`
      - Modell:
        - `Learning/models/thermflex_daily_results_xgb_robust_kpi_6161b53af912/`
      - Ergebnis:
        - mittleres `R2`: `0.182`
        - damit schlechter als der gemischte `robust_kpi`-Stand mit Legacy + `dur8` (`R2 0.228`)
    - Schluss:
      - der reine Ausschluss der Legacy-Screens verbessert die paperrelevanten KPI-Ziele nicht automatisch

  - System-/MILP-Pfad:
    - `dispatch_formulation_tag`-Klassifikation geschaerft:
      - `paper_day_ahead` wird jetzt ueber Substring erkannt und nicht nur ueber exaktes Suffix
    - Test auf paper-day-ahead-only:
      - neuer Datensatz:
        - family hash `0e106b63c724eb4f944d074494e7704e81b5db6ab7732eec19b2063368fc5f9e`
        - `97` Truth-Zeilen
      - Modell:
        - `Learning/models/thermflex_system_results_xgb_robust_heat_system_0e106b63c724/`
      - Ergebnis:
        - mittleres `R2`: `0.152`
        - damit schlechter als der nicht-smoke Gesamtstand (`R2 0.273`)
    - Schluss:
      - reiner paper-day-ahead-Filter ist ebenfalls nicht der Hebel fuer die Kostenziele

  - Gesamtfazit:
    - die Cost-Schwaeche kommt nicht primaer von den bisherigen Homogenitaetsmischungen
    - naechster sinnvoller Hebel ist daher:
      - cost-spezifische Feature-/Target-Behandlung
      - nicht nur weiteres Wegfiltern von Runs

- 2026-05-12: Explizite Cost-Transforms fuer die fokussierten ThermFlex-Target-Profile eingefuehrt.
  - Tages-Screen-Pfad:
    - `dispatch_operating_cost_pct_change` wird jetzt mit `signed_log1p` trainiert
    - Metriken werden wieder auf der Originalskala ausgewertet
    - Effekt im `robust_kpi`-Profil auf Datensatz `5896...`:
      - vorher `dispatch_operating_cost_pct_change`: `R2 -0.182`
      - nach Transform: `R2 0.235`
      - mittleres `R2` des Profils steigt von `0.228` auf `0.297`

  - System-/MILP-Pfad:
    - `dispatch_cost_eur` wird jetzt mit `log1p` trainiert
    - Metriken werden wieder auf der Original-Euro-Skala ausgewertet
    - Effekt im `robust_heat_system`-Profil auf Datensatz `af8599...`:
      - vorher `dispatch_cost_eur`: `R2 -0.661`
      - nach Transform: `R2 -0.330`
      - mittleres `R2` des Profils steigt von `0.273` auf `0.315`

  - Schluss:
    - fuer die Kostenziele war numerische Zieltransformation der richtige naechste Hebel
    - der Daily-Cost-Target ist damit erstmals klar positiv
    - der System-Cost-Target verbessert sich deutlich, bleibt aber noch der schwaechste Teil des Heat-System-Profils

- 2026-05-12: Boiler-spezifischer Transform-Test verworfen; stattdessen System-Kontext aus den Run-Slugs als neuer Feature-Hebel integriert.
  - Boiler-Transform-Test:
    - Daily:
      - `signed_log1p` auf `district_gas_boiler_*_delta` verschlechterte den `robust_kpi`-Lauf massiv
      - insbesondere `district_gas_boiler_generation_kwh_delta` brach auf `R2 -21.88` ein
    - System:
      - `log1p` auf den Boiler-Energiezielen verschlechterte die Boilerziele ebenfalls
    - Schluss:
      - reine Boiler-Target-Transformation ist fuer diese Pfade nicht der richtige Hebel und wurde wieder entfernt

  - Neuer System-Feature-Hebel:
    - `Learning/thermflex_system_results/dataset_builder.py` leitet jetzt aus dem Run-Slug explizit ab:
      - `scenario_slice_tag`
      - `scenario_is_peak_window`
      - `scenario_is_price_window`
      - `scenario_is_sunny_window`
      - `scenario_is_wintertyp_window`
      - `scenario_is_shouldertyp_window`
      - `scenario_anchor_month`
      - `scenario_anchor_day_of_year`
    - Neuer Datensatz:
      - family hash `a998c613841fbdcf125aa4d5d5efdf56619d5740156f5e8f7372e55c9e5e47d5`
    - Neues Modell:
      - `Learning/models/thermflex_system_results_xgb_robust_heat_system_a998c613841f/`
    - Ergebnis:
      - mittleres `R2` des `robust_heat_system`-Profils steigt stark:
        - vorher `0.315`
        - nach Kontextfeatures `0.709`
      - `dispatch_cost_eur`:
        - vorher `R2 -0.330`
        - nach Kontextfeatures `R2 0.406`
      - Boilerziele:
        - `E_district_gas_boiler_generation_kWh`: `R2 0.971`
        - `E_district_gas_boiler_fuel_input_kWh`: `R2 0.971`
      - auch Storage verbessert sich:
        - charge `R2 0.583`
        - discharge `R2 0.602`

  - Daily-Pfad:
    - der gute Cost-transform-only-Stand wurde wiederhergestellt:
      - `Learning/models/thermflex_daily_results_xgb_robust_kpi_5896cea66bba/`
      - mittleres `R2 0.297`
      - `dispatch_operating_cost_pct_change R2 0.235`

- 2026-05-12: Daily-KPI-Test auf Absolutdeltas durchgefuehrt; hilft aktuell nicht.
  - Neuer expliziter Zielzuschnitt:
    - `robust_kpi_absolute` in `Learning/thermflex_daily_results/schema.py`
    - nutzt:
      - `dispatch_operating_cost_eur_delta`
      - `co2_emissions_total_t_delta`
      - `district_gas_boiler_peak_kw_delta`
      - `district_gas_boiler_generation_kwh_delta`
      - `dh_total_peak_change_kw`
      - `thermflex_peak_change_kw`
  - Training:
    - auf Datensatz `5896cea66bbaf7b4351bee3ee983be0fa75e8811658d093be206c48d7b1b6011`
    - Modell:
      - `Learning/models/thermflex_daily_results_xgb_robust_kpi_absolute_5896cea66bba/`
    - `dispatch_operating_cost_eur_delta` und `co2_emissions_total_t_delta` werden explizit mit `signed_log1p` trainiert und fuer die Metriken auf die Originalskala zurueckgefuehrt
  - Ergebnis:
    - mittleres Holdout-`R2`: `0.091`
    - `dispatch_operating_cost_eur_delta`: `R2 -0.708`
    - `co2_emissions_total_t_delta`: `R2 -0.084`
    - Boiler- und Peak-Ziele bleiben unveraendert, weil sie inhaltlich dieselben Targets wie im `robust_kpi`-Profil sind
  - Schluss:
    - fuer den Daily-Pfad ist die KPI-Schwaeche aktuell nicht primaer ein Prozent-vs.-Absolutdelta-Problem
    - naechster Hebel fuer paperrelevante Tages-KPIs ist eher:
      - mehr Bundle-Breite
      - oder reichere Features
      - nicht nur ein weiterer Target-Transform

- 2026-05-12: System-Kostenziel im robusten Heat-System-Profil target-spezifisch nachgetunt.
  - Motivation:
    - nach den neuen Run-Slug-Kontextfeatures war `dispatch_cost_eur` zwar positiv, aber mit `R2 0.406` weiterhin der schwaechste KPI im `robust_heat_system`-Profil
    - da der Systempfad target-wise trainiert, war ein kleiner costspezifischer Hyperparameter-Sweep der naechste billige Hebel
  - Sweep:
    - grouped holdout unveraendert auf Datensatz `a998c613841fbdcf125aa4d5d5efdf56619d5740156f5e8f7372e55c9e5e47d5`
    - nur fuer `dispatch_cost_eur`
    - beste getestete Kombination:
      - `n_estimators=300`
      - `max_depth=4`
      - `learning_rate=0.08`
      - `subsample=1.0`
      - `colsample_bytree=1.0`
      - `min_child_weight=1`
      - `reg_lambda=1.0`
    - diese Parametrisierung ist jetzt explizit nur fuer `dispatch_cost_eur` in `Learning/thermflex_system_results/train.py` hinterlegt
  - Retrain:
    - Modellpfad bleibt:
      - `Learning/models/thermflex_system_results_xgb_robust_heat_system_a998c613841f/`
    - Ergebnis:
      - `dispatch_cost_eur` verbessert sich:
        - vorher `R2 0.406`
        - jetzt `R2 0.471`
      - mittleres Profil-`R2` steigt:
        - vorher `0.709`
        - jetzt `0.717`
      - Boilerziele bleiben stabil stark:
        - `E_district_gas_boiler_generation_kWh`: `R2 0.971`
        - `E_district_gas_boiler_fuel_input_kWh`: `R2 0.971`
  - Schluss:
    - fuer den Systempfad gibt es bei paperrelevanten KPIs noch sinnvolle Trainingsreserve
    - der naechste Hebel ist dort jetzt eher:
      - weitere target-spezifische Tuning-/Featurearbeit fuer Storage/CHP
      - nicht primaer noch ein anderer Datensatzfilter

- 2026-05-12: System-CHP- und Storage-Ziele im robusten Heat-System-Profil ebenfalls target-spezifisch nachgetunt.
  - Motivation:
    - nach dem erfolgreichen Cost-Tuning blieben Gas-CHP und Thermal-Storage die naechsten klaren KPI-Kandidaten mit sichtbarer Reserve
    - grouped-holdout Sweeps auf dem bestehenden Datensatz `a998c613841fbdcf125aa4d5d5efdf56619d5740156f5e8f7372e55c9e5e47d5` wurden deshalb separat fuer:
      - `E_district_gas_chp_electric_generation_kWh`
      - `E_district_thermal_storage_charge_kWh`
      - `E_district_thermal_storage_discharge_kWh`
      gefahren
  - Explizit uebernommen in `Learning/thermflex_system_results/train.py`:
    - Gas-CHP electric / thermal / fuel:
      - `n_estimators=600`
      - `max_depth=3`
      - `learning_rate=0.08`
      - `subsample=0.8`
      - `colsample_bytree=1.0`
      - `min_child_weight=3`
      - `reg_lambda=3.0`
    - Storage charge:
      - `n_estimators=150`
      - `max_depth=6`
      - `learning_rate=0.03`
      - `subsample=1.0`
      - `colsample_bytree=0.8`
      - `min_child_weight=1`
      - `reg_lambda=3.0`
    - Storage discharge:
      - `n_estimators=150`
      - `max_depth=3`
      - `learning_rate=0.08`
      - `subsample=1.0`
      - `colsample_bytree=0.8`
      - `min_child_weight=1`
      - `reg_lambda=3.0`
  - Retrain:
    - Modellpfad bleibt:
      - `Learning/models/thermflex_system_results_xgb_robust_heat_system_a998c613841f/`
  - Ergebnis:
    - mittleres Profil-`R2` steigt weiter:
      - vorher `0.717`
      - jetzt `0.774`
    - Gas-CHP:
      - electric `R2 0.801`
      - thermal `R2 0.801`
      - fuel `R2 0.801`
    - Storage:
      - charge `R2 0.682`
      - discharge `R2 0.694`
    - Boiler bleibt stabil stark:
      - generation / fuel jeweils `R2 0.971`
    - Cost bleibt verbessert:
      - `dispatch_cost_eur R2 0.471`
  - Schluss:
    - der System-/MILP-KPI-Pfad reagiert weiterhin gut auf sauberes target-spezifisches Tuning
    - damit ist die Richtung bestaetigt:
      - fuer KPI-Qualitaet lohnt sich hier weiteres fokussiertes Training noch deutlich eher als beim Daily-Pfad

- 2026-05-12: Explizite Tages-Kontextfeatures fuer den Systempfad getestet; auf aktuellem Holdout nicht besser.
  - Motivation:
    - fuer das Kostenziel fehlten im Systempfad bisher echte Markt-/Wetter-/Lastwerte
    - deshalb wurde eine neue Datensatzfamilie aufgebaut, die fuer verankerte Szenariolaufe aus dem kanonischen Vienna-2023-Kontext explizit anhaengt:
      - `scenario_t_outdoor_mean_c`
      - `scenario_t_outdoor_min_c`
      - `scenario_dh_total_kwh`
      - `scenario_dh_space_heat_total_kwh`
      - `scenario_solargains_proxy_sum`
      - `scenario_irradiance_proxy_sum`
      - `scenario_mc_auction_mean_eur_mwh`
      - `scenario_mc_auction_peak_eur_mwh`
      - `scenario_gas_price_mean_eur_mwh_fuel`
      - `scenario_co2_price_mean_eur_tco2`
    - Runs ohne `scenario_anchor_date` behalten diese Felder explizit als `NaN`; es gibt keinen stillen Pseudo-Mittelwert fuer Full-Period-Faelle
  - Neuer Datensatz:
    - `Learning/datasets/9ce6d818fd832f172cec3b9f573d779906c309d3bdba047bd572238c4492c060/`
  - Neuer Modellkandidat:
    - `Learning/models/thermflex_system_results_xgb_robust_heat_system_9ce6d818fd83/`
  - Ergebnis gegenueber dem aktuell bevorzugten Kontextpfad `a998...`:
    - mittleres `R2` sinkt:
      - bevorzugter Pfad `a998...`: `0.774`
      - Tages-Kontext-Pfad `9ce6...`: `0.756`
    - `dispatch_cost_eur` bleibt praktisch gleich:
      - bevorzugter Pfad `a998...`: `R2 0.471`
      - Tages-Kontext-Pfad `9ce6...`: `R2 0.469`
    - auch CHP/Storage/Boiler werden leicht schlechter
  - Schluss:
    - der neue Tages-Kontext ist fachlich plausibel, aber auf dem aktuellen grouped holdout kein Gewinn
    - bevorzugter KPI-Pfad bleibt daher vorerst die einfachere Run-Slug-Kontextfamilie `a998...`
    - zusaetzlich wichtig:
      - der aktuelle System-Truthvertrag enthaelt noch kein explizites CO2-Target
      - ein echtes Cost/CO2-Systemprofil braucht daher spaeter eine Truthvertrag-Erweiterung und nicht nur ein neues Modellprofil

- 2026-05-12: KPI-angereicherte `thermflex_system_results`-Familie aus `truth_dataset.csv + dispatch_kpis.json` aufgebaut und paper-faehiges KPI-Profil trainiert.
  - Motivation:
    - der alte System-Truthvertrag war fuer Paper-KPIs zu grob:
      - keine expliziten Heat-Cost-Komponenten
      - kein direktes `co2_emissions_total_t`
      - ThermFlex-Behavior nur indirekt
    - ausserdem zeigte der erste KPI-Core-Test:
      - `dispatch_heat_operating_cost_eur`, `fuel_cost_eur`, `co2_cost_eur`, `variable_opex_eur` und die meisten ThermFlex-KPIs sind stark lernbar
      - der alte `dispatch_operating_cost_eur` bleibt dagegen als grid-tainted Aggregat klar der falsche Paper-Anker
  - Technischer Schnitt:
    - `Learning/thermflex_system_results/dataset_builder.py` kann jetzt eine explizite KPI-angereicherte Family mit `dispatch_kpi_mode='latest_point'` bauen
    - Quelle:
      - `truth_dataset.csv`
      - plus `dispatch_kpis.json -> latest_point`
    - harter Kompatibilitaetsfilter:
      - nur Runfolder mit passender `dispatch_kpis.json`
      - kein stiller Fallback
    - `dispatch_heat_operating_cost_eur` wird nur dort explizit abgeleitet, wo die drei Komponenten vorhanden sind:
      - `fuel_cost_eur + co2_cost_eur + variable_opex_eur`
  - Neuer Datensatz:
    - `Learning/datasets/612be5461a303ff3cbfd0fd044e124fe36662098497280403e3246ca7ddc5aab/`
    - `88` kompatible Runs
  - KPI-Profile:
    - `dispatch_kpi_core`
      - Modell:
        - `Learning/models/thermflex_system_results_xgb_dispatch_kpi_core_612be5461a30/`
      - mean `R2 = 0.855`
      - stark bei:
        - `dispatch_heat_operating_cost_eur 0.983`
        - `fuel_cost_eur 0.985`
        - `co2_cost_eur 0.971`
        - `thermflex_peak_change_kw 0.988`
      - schwach bleibt:
        - `dispatch_operating_cost_eur -0.042`
        - `district_gas_chp_co2_t 0.535`
        - `thermflex_rebound_kwh 0.692`
    - gezielte Nachschaerfung fuer paper-relevante KPI-Ziele:
      - `co2_emissions_total_t` mit target-spezifischem XGB-Satz:
        - bestes kleines Sweep-Ergebnis `R2 0.967`
      - `thermflex_rebound_kwh` mit target-spezifischem XGB-Satz:
        - bestes kleines Sweep-Ergebnis `R2 0.957`
    - `dispatch_kpi_paper`
      - neuer expliziter Paper-Zuschnitt:
        - `dispatch_heat_operating_cost_eur`
        - `fuel_cost_eur`
        - `co2_cost_eur`
        - `variable_opex_eur`
        - `co2_emissions_total_t`
        - `district_gas_boiler_co2_t`
        - shifted/additional/rebound heat
        - peak change
        - active-member hours
        - temperature-violation degree-hours
      - bewusst ausgeschlossen:
        - `dispatch_operating_cost_eur`
        - `district_gas_chp_co2_t`
      - Modell:
        - `Learning/models/thermflex_system_results_xgb_dispatch_kpi_paper_612be5461a30/`
      - grouped-holdout Ergebnis:
        - mean `R2 = 0.980`
        - `dispatch_heat_operating_cost_eur 0.983`
        - `fuel_cost_eur 0.985`
        - `co2_cost_eur 0.971`
        - `co2_emissions_total_t 0.967`
        - `thermflex_rebound_kwh 0.957`
        - `thermflex_peak_change_kw 0.988`
        - `thermflex_temperature_violation_degree_hours_total 0.992`
  - Zusatzcheck:
    - aus den vorhergesagten Kostenkomponenten ergibt sich fuer den Holdout:
      - `dispatch_heat_operating_cost_eur` als Summe aus `fuel + co2 + variable_opex`
      - `R2 0.984`
    - das bestaetigt den neuen Heat-Cost-Vertrag auch als komponentenbasierten Deployment-Pfad
  - Schluss:
    - das Ziel `R2 ~ 0.97` ist fuer den eigentlichen paper-faehigen KPI-Block jetzt auf dem Systempfad erreicht
    - der naechste Engpass ist nicht mehr allgemeines Retraining, sondern:
      - welche weiteren Paper-/Sensitivity-KPIs in diesen sauberen Vertrag aufgenommen werden sollen
      - ob wir spaeter noch einen separaten Carbon-Split-/Auxiliary-Pfad fuer `district_gas_chp_co2_t` brauchen

- 2026-05-12: Erster ausfuehrbarer Daily-Surrogatpfad fuer `Table 09` aufgebaut; technische Pipeline steht, Daily-Modellqualitaet bleibt der Engpass.
  - Motivation:
    - nach dem starken System-KPI-Pfad sollte `Table 09` endlich direkt aus dem Learning-Layer heraus erzeugbar sein
    - dafuer braucht es:
      - ein Daily-Profil mit genau den Table-09-noetigen Zielen
      - einen Inferenzpfad von Heizsaison-Template + Override -> surrogate day screen
      - einen Adapter in den bestehenden `build_table_09_heating_season_kpis.py`-Pfad
  - Neue Daily-Zielmenge:
    - `table_09_paper` in `Learning/thermflex_daily_results/schema.py`
    - Ziele:
      - `dispatch_operating_cost_pct_change`
      - `co2_emissions_total_pct_change`
      - `district_gas_boiler_peak_kw_delta`
      - `district_gas_boiler_generation_kwh_delta`
      - `thermflex_shifted_space_heat_kwh`
      - `thermflex_rebound_kwh`
    - Schnitt:
      - cost / CO2 bleiben auf Prozentbasis, weil die Daily-Modelle dort besser tragen als auf Absolutdelta-Basis
      - Boiler / shifted / rebound bleiben auf absoluten physikalischen Einheiten
  - Neue Ausfuehrungsschicht:
    - `Learning/thermflex_daily_results/predict.py`
      - nimmt:
        - eine Heizsaison-Template-Screen-CSV
        - ein trainiertes Daily-Modell
        - einen expliziten ThermFlex-Override
      - rekonstruiert daraus eine surrogate `heating_season_day_screen.csv`-artige Tabelle
      - fail-fast bei:
        - fehlenden Template-Spalten
        - unbekannten One-Hot-Kategorien
        - unvollstaendigem Zielblock fuer Table 09
    - `Learning/thermflex_daily_results/aggregate.py`
      - uebergibt die surrogate Screen-CSV direkt an den unveraenderten
        `Documentation/Papers/thermflex_paper/tables/build_table_09_heating_season_kpis.py`-Pfad
    - neuer CLI-Consumer:
      - `Documentation/Papers/thermflex_paper/tables/build_table_09_heating_season_kpis_surrogate.py`
  - Neues Daily-Modell:
    - `Learning/models/thermflex_daily_results_xgb_table_09_paper_5896cea66bba/`
    - grouped-holdout:
      - mean `R2 = -0.048`
    - Einzelziele:
      - `dispatch_operating_cost_pct_change 0.235`
      - `co2_emissions_total_pct_change 0.210`
      - `district_gas_boiler_peak_kw_delta 0.371`
      - `district_gas_boiler_generation_kwh_delta 0.192`
      - `thermflex_shifted_space_heat_kwh -1.020`
      - `thermflex_rebound_kwh -0.275`
    - current-only-Test:
      - `Learning/models/thermflex_daily_results_xgb_table_09_paper_6161b53af912/`
      - noch schlechter: mean `R2 = -0.291`
  - Smoke-Test:
    - surrogate Table 09 fuer den bestehenden `UPPER_24H`-Override erfolgreich end-to-end erzeugt:
      - surrogate screen:
        - `Documentation/Papers/thermflex_paper/tables/table_09_surrogate_screen_upper_only_dur24.csv`
      - markdown:
        - `Documentation/Papers/thermflex_paper/tables/table_09_tradeoff_day_summary_surrogate_upper_only_dur24.md`
      - csv:
        - `Documentation/Papers/thermflex_paper/tables/table_09_heating_season_kpis_surrogate_upper_only_dur24.csv`
  - Schluss:
    - der technische Nutzpfad `template screen + override + daily surrogate -> Table 09` funktioniert jetzt
    - aber die Daily-Surrogatqualitaet ist fuer shifted/rebound und damit fuer eine paper-faehige surrogate Table-09-Auswertung noch nicht ausreichend
    - fuer die eigentliche Paperstory bleibt der neue System-KPI-Pfad stark; fuer echte surrogate `Table 09`-Saisonscreens muss als naechstes der Daily-Pfad gezielt verbessert werden

- 2026-05-12: Daily-`Table 09`-Pfad mit engineered Features und partiellen Bundles verbessert; Boiler-Energie reagiert, shifted/rebound bleiben schwach.
  - Technischer Hebel:
    - neue explicite engineered Daily-Features in `Learning/thermflex_daily_results/features.py`:
      - `day_of_year_sin`, `day_of_year_cos`
      - `dh_space_heat_share`
      - `irradiance_per_space_heat`
      - `solargains_per_space_heat`
      - `dispatch_cost_ref_per_dh_mwh`
      - `co2_ref_per_dh_mwh`
      - `boiler_generation_ref_share`
      - `boiler_peak_ref_per_mean_dh_load`
      - `boiler_ref_load_factor`
    - diese Features werden jetzt:
      - im Dataset-Export
      - und identisch im Inferenzpfad
      genutzt
    - zusaetzlich target-spezifische Daily-Parameter fuer:
      - `district_gas_boiler_generation_kwh_delta`
      - `thermflex_shifted_space_heat_kwh`
      - `thermflex_rebound_kwh`
  - Neuer bester Daily-Datensatz fuer den Table-09-Pfad:
    - `Learning/datasets/d13030264a0b5582928f45de9470284270820ffd734aa4d00782ccdac91bbb88/`
    - Gegensatz zum vorherigen Lauf:
      - partielle / Checkpoint-Bundles sind explizit zugelassen
      - dadurch `7` statt `6` Bundles
      - insbesondere `dur8` kommt in den Trainingspool
  - Neuer bester Daily-Table-09-Lauf:
    - `Learning/models/thermflex_daily_results_xgb_table_09_paper_d13030264a0b/`
    - grouped-holdout:
      - vorheriger bester Stand:
        - mean `R2 = -0.048`
      - nach engineered Features:
        - mean `R2 = 0.005`
      - nach partial-bundle-Zulassung:
        - mean `R2 = 0.084`
      - nach kleinem Rebound-Parameterrueckbau:
        - mean `R2 = 0.094`
    - aktuelle Einzelziele:
      - `dispatch_operating_cost_pct_change 0.248`
      - `co2_emissions_total_pct_change 0.267`
      - `district_gas_boiler_peak_kw_delta 0.325`
      - `district_gas_boiler_generation_kwh_delta 0.599`
      - `thermflex_shifted_space_heat_kwh -0.650`
      - `thermflex_rebound_kwh -0.222`
  - Neuer bestverfuegbarer surrogate Table-09-Smoke-Test:
    - screen:
      - `Documentation/Papers/thermflex_paper/tables/table_09_surrogate_screen_upper_only_dur24_best_daily.csv`
    - markdown:
      - `Documentation/Papers/thermflex_paper/tables/table_09_tradeoff_day_summary_surrogate_upper_only_dur24_best_daily.md`
    - csv:
      - `Documentation/Papers/thermflex_paper/tables/table_09_heating_season_kpis_surrogate_upper_only_dur24_best_daily.csv`
  - Schluss:
    - der Daily-Pfad reagiert auf Feature- und Datensatzschnitt, aber nur moderat
    - Boiler-Energie ist jetzt deutlich besser
    - shifted/rebound sind weiterhin der strukturelle Engpass fuer surrogate `Table 09`

- 2026-05-12: `LOWER1K_DUR8_EVT24`-Resume und HiGHS-Gap fuer Daily-Truth geprueft; `1%` ist hier noch kein sauberer Surrogat-Truth-Vertrag.
  - Resume:
    - `Optimization/run/analysis/screen_vienna_constant_thermflex_heating_season_days.py` hat jetzt einen expliziten `--resume-output-dir`-Pfad
    - Checkpoint wird fail-fast geprueft auf:
      - vorhandene `date`-/Label-/Override-Spalten
      - gleiche `flex_case_label`
      - gleiche `flex_override_name`
      - keine doppelten Tage
    - Resume selbst funktioniert; der Lauf bleibt nicht organisatorisch, sondern fachlich am naechsten Flex-Tag haengen
  - Konkreter Blocker:
    - alter `dur8`-Checkpoint:
      - `daily_thermflex_screen_lb21p5_dur8_evt24_20260511_074549`
      - `83` Tage bis `2023-03-24`
    - erster fehlender Tag `2023-03-25`:
      - `REF` laeuft in ~`24 s`
      - `LOWER1K_DUR8_EVT24`:
        - mit `THERMFLEX_HIGHS_MIP_REL_GAP=0.005` und `time_limit=600 s`: Abbruch auf `maxTimeLimit`
        - mit `THERMFLEX_HIGHS_MIP_REL_GAP=0.01` und `time_limit=600 s`: ebenfalls Abbruch auf `maxTimeLimit`
  - KPI-Stabilitaetstest auf dem noch loesbaren Vortag `2023-03-24`:
    - exakter Solve:
      - Laufzeit ~`442 s`
      - boiler peak / energy fast `0`
      - shifted `~1.58 GWh`
      - rebound `~0.86 GWh`
    - `1%`-Gap:
      - Laufzeit ~`257 s`
      - boiler peak `~121 MW`
      - boiler energy `~0.192 GWh`
      - shifted `~1.44 GWh`
      - rebound `~0.72 GWh`
    - Schluss:
      - `1%` reduziert Laufzeit, veraendert aber genau die paperkritischen Daily-KPIs deutlich
      - fuer surrogate Daily-Truth ist `1%` auf diesen schweren Lower-Relax-Tagen derzeit nicht sauber genug belegt

- 2026-05-12: Partial-Truth-Pfad fuer Daily ThermFlex Screens operationalisiert; `LOWER1K_DUR8_EVT24` kann jetzt mit expliziten Heavy-Day-Luecken weiterkuratiert werden.
  - `Optimization/run/analysis/screen_vienna_constant_thermflex_heating_season_days.py`
    - neue explizite Config-/CLI-Felder:
      - `day_solver_time_limit_s`
      - `day_mip_rel_gap`
      - `allow_incomplete_days`
    - pro Tag wird der Solver jetzt optional unter einem expliziten lokalen Env-Vertrag gefahren; keine stille globale Solver-Aenderung
    - Fehltage werden bei gesetztem `--allow-incomplete-days` nach:
      - `heating_season_day_screen_failures.csv`
      - `heating_season_day_screen_failures.json`
      - `heating_season_day_screen_meta.json`
      geschrieben
    - bekannte Fehltage werden beim naechsten Resume explizit geladen und nicht erneut geloest
  - `Optimization/run/analysis/run_heating_season_day_screen_job.ps1`
    - duenne PowerShell-Wrapperdatei fuer explizite laengere Screen-Jobs mit stabiler Parametrisierung
  - Bugfix:
    - im neuen Solver-Env-Helper fehlte `import os`; das fuehrte zunaechst zu einem `NameError` statt zum echten Solververhalten
  - `LOWER1K_DUR8_EVT24`-Status nach gezielten Resume-Tests:
    - Bundle:
      - `Optimization/run/results/Vienna/gold/daily_thermflex_screen_lb21p5_dur8_evt24_20260511_074549`
    - bekannter Resume-Stand:
      - `83` geloeste Tage bis `2023-03-24`
    - neu explizit als Heavy-Day-Luecken markiert:
      - `2023-03-25`
      - `2023-03-26`
    - beide Tage:
      - `REF` loesbar in wenigen Sekunden
      - Flex-Fall endet unter `day_solver_time_limit_s=600` auf `maxTimeLimit`
  - Daily-Dataset-Kuration:
    - `Learning/thermflex_daily_results/dataset_builder.py`
      - Manifest erfasst jetzt pro Bundle:
        - `failure_csv`
        - `known_failure_rows`
        - `known_failure_dates`
    - bei gleicher Bundle-ID muss fuer aktive Kuration `gold` vor Snapshot kommen, damit live Failure-Manifeste / Partial-Truth nicht vom aelteren Snapshot ueberdeckt werden
  - neue gold-first Daily-Family:
    - Datensatz:
      - `Learning/datasets/755533f1129f9892d539157d4f7702013ffb844e9d27564ca27ccc3c249e3604/`
    - Modell:
      - `Learning/models/thermflex_daily_results_xgb_table_09_paper_755533f1129f/`
    - grouped-holdout:
      - `mean R2 = 0.0946`
      - `dispatch_operating_cost_pct_change 0.250`
      - `co2_emissions_total_pct_change 0.272`
      - `district_gas_boiler_peak_kw_delta 0.334`
      - `district_gas_boiler_generation_kwh_delta 0.608`
      - `thermflex_shifted_space_heat_kwh -0.668`
      - `thermflex_rebound_kwh -0.228`
    - Schluss:
      - Partial-Truth-/gold-first-Kuration ist jetzt methodisch sauberer und fuer weitere Daily-Truth-Erweiterung bereit
      - der Hauptengpass fuer surrogate `Table 09` bleibt weiterhin `shifted` / `rebound`, nicht mehr die reine Datenorchestrierung
  - `LOWER1K_DUR12_EVT24`-Probe:
    - neuer Partial-Ordner:
      - `Optimization/run/results/Vienna/gold/daily_thermflex_screen_lb21p5_dur12_evt24_20260513_partial`
    - Traktabilitaetstest mit `max_new_days=3`:
      - `2023-01-01` geloest
      - `2023-01-02` und `2023-01-03` als `maxTimeLimit` in das Failure-Manifest gelaufen
    - nach sofortiger Daily-Neukuration / Retrain:
      - Datensatz:
        - `Learning/datasets/9fb347f1b280ed6d3fded1ac7257e1f35989d68222b9f15c9a97261ffa85bc8e/`
      - Modell:
        - `Learning/models/thermflex_daily_results_xgb_table_09_paper_9fb347f1b280/`
      - grouped-holdout `mean R2 = -0.208`
    - Schluss:
      - `dur12` ist aktuell kein guter naechster Hebel fuer den Daily-`Table 09`-Pfad
      - Prioritaet bleibt auf `dur8`-Partial und spaeter eher auf `2K`-Breite als auf `dur12`

- 2026-05-13: Daily-`Table 09`-Pfad gezielt ueber `LOWER2K_*`-Partial-Truth und target-spezifisches XGB-Tuning fuer `shifted` / `rebound` weiter verbessert.
  - Neue Runner-Erweiterung:
    - `screen_vienna_constant_thermflex_heating_season_days.py`
      - neuer expliziter CLI-/Config-Schalter:
        - `--max-new-days`
      - damit koennen Resumes auf die naechsten `N` noch ungelösten Tage begrenzt werden, ohne mit kuenstlichen `pilot_max_days`-Offsets zu arbeiten
  - `LOWER1K_DUR8_EVT24` weitergezogen:
    - Bundle:
      - `Optimization/run/results/Vienna/gold/daily_thermflex_screen_lb21p5_dur8_evt24_20260511_074549`
    - neuer Stand:
      - `86` geloeste Tage
      - bekannte Heavy-Day-Luecken:
        - `2023-03-25`
        - `2023-03-26`
        - `2023-03-30`
      - neue geloeste Tage:
        - `2023-03-27`
        - `2023-03-28`
        - `2023-03-29`
        - `2023-03-31`
        - `2023-04-01`
  - `LOWER2K_DUR1_EVT24` neu als tractable Partial-Familie aufgebaut:
    - Bundle:
      - `Optimization/run/results/Vienna/gold/daily_thermflex_screen_lb20p5_dur1_evt24_20260513_partial`
    - Traktabilitaet:
      - erste `13` Tage ohne Failure-Manifest bis `2023-01-13`
      - Solve-Zeiten im Flex-Fall meist klar unter `1 min`
  - `LOWER2K_DUR4_EVT24` neu als besonders brauchbare Partial-Familie aufgebaut:
    - Bundle:
      - `Optimization/run/results/Vienna/gold/daily_thermflex_screen_lb20p5_dur4_evt24_20260513_partial`
    - Traktabilitaet:
      - aktuell `33` geloeste Tage bis `2023-02-12`
      - kein Failure-Manifest bisher
      - viele Flex-Tage loesbar in Sekunden bis niedrigen Minuten, einzelne ~`3-5 min`, aber weiterhin tractable
  - Daily-Kuration:
    - neue Family:
      - `Learning/datasets/f77eafde5cdc366ee47282e6755eaac41fec0f8da18321c709a6f4a094828e98/`
    - `selected_rows = 1447`
  - Vor erstem Retuning mit mehr `2K`-Truth:
    - Modell:
      - `Learning/models/thermflex_daily_results_xgb_table_09_paper_f77eafde5cdc/`
    - grouped-holdout `mean R2 ~ 0.267-0.288`
    - wichtiger Befund:
      - `shifted` erstmals positiv (`~0.32-0.34`)
      - `rebound` erstmals positiv (`~0.24-0.28`)
  - Kleiner target-spezifischer Parameter-Sweep auf dem aktuellen grouped holdout:
    - `thermflex_shifted_space_heat_kwh`
      - bester Testpunkt:
        - `n_estimators=900`
        - `max_depth=2`
        - `learning_rate=0.05`
        - `subsample=1.0`
        - `colsample_bytree=0.7`
        - `reg_lambda=1.0`
        - `min_child_weight=3`
      - Test-`R2 ~ 0.525`
    - `thermflex_rebound_kwh`
      - bester Testpunkt:
        - `n_estimators=900`
        - `max_depth=2`
        - `learning_rate=0.05`
        - `subsample=0.85`
        - `colsample_bytree=0.7`
        - `reg_lambda=1.0`
        - `min_child_weight=3`
      - Test-`R2 ~ 0.475`
  - Diese Params wurden in `Learning/thermflex_daily_results/train.py` uebernommen und das `table_09_paper`-Modell neu trainiert.
  - Neuer bester Daily-`Table 09`-Stand:
    - Modell:
      - `Learning/models/thermflex_daily_results_xgb_table_09_paper_f77eafde5cdc/`
    - grouped-holdout:
      - `mean R2 = 0.334`
      - `dispatch_operating_cost_pct_change = 0.595`
      - `co2_emissions_total_pct_change = 0.228`
      - `district_gas_boiler_peak_kw_delta = -0.063`
      - `district_gas_boiler_generation_kwh_delta = 0.241`
      - `thermflex_shifted_space_heat_kwh = 0.525`
      - `thermflex_rebound_kwh = 0.475`
    - Schluss:
      - Der entscheidende Fortschritt kam aus:
        - mehr tractable `2K`-Truth, besonders `dur4`
        - explizitem target-spezifischem Tuning fuer `shifted` / `rebound`
      - Daily-`Table 09` bleibt klar unter dem gewuenschten KPI-Ziel `R2 >= 0.95`, aber der vorherige strukturelle Negativbereich fuer `shifted` / `rebound` ist erstmals verlassen
  - Weitere Daily-Truth-Expansion:
    - `LOWER2K_DUR4_EVT24`
      - bis `2023-02-27` im Checkpoint weitergezogen
      - der laengere Lauf wurde durch Session-Timeout unterbrochen; `checkpoint.csv` ist weiter als die letzte `heating_season_day_screen.csv`
    - `LOWER2K_DUR8_EVT24`
      - Traktabilitaetsprobe mit `3` geloesten Tagen (`2023-01-01` bis `2023-01-03`)
      - deutlich teurer als `2K dur4`, aber nicht sofort unloesbar
  - Kuration-Bugfix:
    - `Learning/thermflex_daily_results/dataset_builder.py`
      - wenn ein Partial-Run unterbrochen wird, kann `heating_season_day_screen_checkpoint.csv` groesser sein als die letzte `heating_season_day_screen.csv`
      - der Builder bevorzugt nun explizit den groesseren Checkpoint gegenueber einem stale final export
      - zusaetzlich werden winzige Partial-Bundles unterhalb `min_checkpoint_rows` jetzt auch dann aus der kuratierten Daily-Family ausgeschlossen, wenn sie als `final`-CSV vorliegen
  - Vergleich der neuen Families:
    - mit den grossen `2K`-Partials und tuned `table_09_paper`:
      - `f77eafde5cdc366ee47282e6755eaac41fec0f8da18321c709a6f4a094828e98`
      - Modell:
        - `Learning/models/thermflex_daily_results_xgb_table_09_paper_f77eafde5cdc/`
      - bleibt der aktuell beste produktive Daily-Stand
    - die spaeteren Familien
      - `f55be3ef7202f3c3f6b73aec76613307847d6ee3609e68dd6966162786e6d0de`
      - `787549212d8397c247dee5391b4d6ca86d74859e884172ca62b821c4e1ebccb4`
      - zeigten auf ihren grouped splits schlechtere / instabilere Scores und sollen vorerst nicht als bevorzugte Baseline verwendet werden

- 2026-05-13: Daily-Dur8-Truth verbreitert und Family-Hash-Vertrag fuer Partial-Bundles repariert.
  - `Learning/thermflex_daily_results/dataset_builder.py`
    - `family_hash` haengt jetzt explizit auch an Bundle-Revisionen:
      - `screen_kind`
      - Zeilenanzahl
      - Schema-Version
      - bekannte Failure-Tage
    - Grund:
      - wachsende Partial-Bundles wie `LOWER2K_DUR8_EVT24` oder `LOWER1K_DUR8_EVT24` duerfen nicht mehr dieselben Dataset-/Modell-Hashes wiederverwenden und aeltere Artefakte still ueberschreiben
  - `LOWER2K_DUR8_EVT24`
    - Bundle:
      - `Optimization/run/results/Vienna/gold/daily_thermflex_screen_lb20p5_dur8_evt24_20260513_partial`
    - aktueller Stand:
      - `64` geloeste Tage bis `2023-03-17`
      - `13` explizite Heavy-Day-Failures bis `2023-03-18`
  - `LOWER2K_DUR4_EVT24`
    - Bundle:
      - `Optimization/run/results/Vienna/gold/daily_thermflex_screen_lb20p5_dur4_evt24_20260513_partial`
    - aktueller Stand:
      - `74` geloeste Tage bis `2023-03-20`
      - `5` Heavy-Day-Failures
  - `LOWER1K_DUR8_EVT24` Train-Checkpoint weitergezogen:
    - Bundle:
      - `Optimization/run/results/Vienna/gold/daily_thermflex_screen_lb21p5_dur8_evt24_20260512_182621`
    - aktueller Stand:
      - `39` geloeste Tage bis `2023-02-09`
      - `1` Heavy-Day-Failure (`2023-01-31`)
  - neue Daily-Retrains nach den erweiterten Dur8-/Dur4-Partials:
    - `Learning/models/thermflex_daily_results_xgb_table_09_paper_b75548cc8e26/`
      - grouped-holdout `mean R2 = -0.087`
    - `Learning/models/thermflex_daily_results_xgb_table_09_paper_701b0880525e/`
      - grouped-holdout `mean R2 = -0.082`
    - `Learning/models/thermflex_daily_results_xgb_table_09_paper_30b10dc743fe/`
      - grouped-holdout `mean R2 = -0.066`
    - `Learning/models/thermflex_daily_results_xgb_table_09_paper_4a083450ac81/`
      - grouped-holdout `mean R2 = -0.032`
  - letzter Daily-Stand `4a083450ac81`:
    - `dispatch_operating_cost_pct_change = 0.832`
    - `co2_emissions_total_pct_change = -0.544`
    - `district_gas_boiler_peak_kw_delta = 0.347`
    - `district_gas_boiler_generation_kwh_delta = 0.385`
    - `thermflex_shifted_space_heat_kwh = -0.832`
    - `thermflex_rebound_kwh = -0.378`
    - Schluss:
      - mehr `dur8`-Truth hilft, aber unter strengem `split_group_bundle`-Holdout bleiben `shifted` / `rebound` der Daily-Hauptengpass
      - Kosten- und Boiler-Ziele reagieren bereits deutlich besser als die eigentliche Flex-Mechanik
      - naechster Hebel:
        - noch mehr dur8-/lower-Relax-Trainbreite
        - oder gezielterer Modellzuschnitt fuer `shifted` / `rebound`
  - weitere `dur8`-Truth-Expansion:
    - `LOWER2K_DUR8_EVT24`
      - weiter bis `2023-03-28` gezogen
      - aktueller Stand:
        - `71` geloeste Tage
        - `16` Heavy-Day-Failures
    - `LOWER1K_DUR8_EVT24`
      - weiter bis `2023-02-19` gezogen
      - aktueller Stand:
        - `48` geloeste Tage
        - `2` Heavy-Day-Failures
  - neuer Daily-Retrain auf diesem Truth-Stand:
    - Datensatz:
      - `Learning/datasets/2b65d41fa47986623bdfd56c56ef107b10f7ddaf7527534f70c3f4754f4573a9/`
    - Modell:
      - `Learning/models/thermflex_daily_results_xgb_table_09_paper_2b65d41fa479/`
    - grouped-holdout:
      - `mean R2 = -0.007`
      - `dispatch_operating_cost_pct_change = 0.826`
      - `co2_emissions_total_pct_change = -0.387`
      - `district_gas_boiler_peak_kw_delta = 0.349`
      - `district_gas_boiler_generation_kwh_delta = 0.379`
      - `thermflex_shifted_space_heat_kwh = -0.795`
      - `thermflex_rebound_kwh = -0.416`
    - Schluss:
      - weitere `dur8`-Train- und Test-Breite verbessert den strengen Daily-Holdout insgesamt weiter Richtung `0`
      - Cost-/Boiler-Ziele werden robuster
      - `shifted` / `rebound` bleiben weiterhin negativ und sind der naechste zwingende Separate-Pfad
  - separater Daily-Zielpfad `shifted_rebound_only` aufgesetzt:
    - `Learning/thermflex_daily_results/schema.py`
      - neues Profil:
        - `SHIFTED_REBOUND_ONLY_TARGET_COLUMNS`
    - `Learning/thermflex_daily_results/train.py`
      - neues `target_profile = "shifted_rebound_only"`
  - auf demselben Truth-Stand kleiner Parameter-Sweep nur fuer:
    - `thermflex_shifted_space_heat_kwh`
    - `thermflex_rebound_kwh`
  - bessere Params uebernommen:
    - `thermflex_shifted_space_heat_kwh`
      - `n_estimators=1200`
      - `max_depth=3`
      - `learning_rate=0.03`
      - `subsample=0.85`
      - `colsample_bytree=0.7`
      - `min_child_weight=3`
    - `thermflex_rebound_kwh`
      - `n_estimators=700`
      - `max_depth=4`
      - `learning_rate=0.03`
      - `subsample=0.85`
      - `colsample_bytree=0.85`
      - `min_child_weight=5`
  - Retrain-Ergebnis `shifted_rebound_only`:
    - Modell:
      - `Learning/models/thermflex_daily_results_xgb_shifted_rebound_only_2b65d41fa479/`
    - grouped holdout:
      - `thermflex_shifted_space_heat_kwh = -0.623`
      - `thermflex_rebound_kwh = -0.256`
      - `mean R2 = -0.440`
    - Schluss:
      - Profiltrennung allein ist nicht der Hebel; das Problem bleibt in Truth-Abdeckung und Bundle-Generalisation
  - Retrain-Ergebnis `table_09_paper` mit den besseren `shifted/rebound`-Params:
    - Modell:
      - `Learning/models/thermflex_daily_results_xgb_table_09_paper_2b65d41fa479/`
    - grouped holdout:
      - `mean R2 = 0.048`
      - `dispatch_operating_cost_pct_change = 0.826`
      - `co2_emissions_total_pct_change = -0.387`
      - `district_gas_boiler_peak_kw_delta = 0.349`
      - `district_gas_boiler_generation_kwh_delta = 0.379`
      - `thermflex_shifted_space_heat_kwh = -0.623`
      - `thermflex_rebound_kwh = -0.256`
    - Schluss:
      - der gemeinsame Daily-Table-09-Pfad ist damit erstmals wieder leicht positiv im strengen grouped holdout
      - Cost und Boiler tragen den positiven Mittelwert
      - `shifted`, `rebound` und taegliches CO2 bleiben die echten Engpaesse
  - weitere Dur8-Truth-Expansion:
    - `LOWER2K_DUR8_EVT24`
      - bis `2023-04-07` gezogen
      - aktueller Stand:
        - `78` geloeste Tage
        - `19` Heavy-Day-Failures
    - `LOWER1K_DUR8_EVT24`
      - bis `2023-03-01` gezogen
      - aktueller Stand:
        - `58` geloeste Tage
        - `2` Heavy-Day-Failures
  - Daily-Retrain auf diesem Truth-Stand:
    - Datensatz:
      - `Learning/datasets/a78e80c85388cb70b273bf474525b9c93baa4eaed7d991eac8d7d2c126267949/`
    - Modell:
      - `Learning/models/thermflex_daily_results_xgb_table_09_paper_a78e80c85388/`
    - grouped holdout:
      - `mean R2 = 0.068`
      - `dispatch_operating_cost_pct_change = 0.815`
      - `co2_emissions_total_pct_change = -0.275`
      - `district_gas_boiler_peak_kw_delta = 0.369`
      - `district_gas_boiler_generation_kwh_delta = 0.369`
      - `thermflex_shifted_space_heat_kwh = -0.591`
      - `thermflex_rebound_kwh = -0.280`
    - Schluss:
      - mehr `dur8`-Train- und Test-Breite verbessert den strengen Daily-Holdout weiter
      - `shifted`, `rebound` und taegliches CO2 bleiben negativ, aber deutlich weniger negativ als zuvor
  - zusaetzlicher Daily-Profiltest `co2_only`:
    - Modell:
      - `Learning/models/thermflex_daily_results_xgb_co2_only_a78e80c85388/`
    - grouped holdout:
      - `co2_emissions_total_pct_change = -0.275`
    - Schluss:
      - CO2 wird isoliert nicht besser als im gemeinsamen `table_09_paper`-Profil
      - damit ist das taegliche CO2-Problem ebenfalls kein reines Profil-/Kopplungsproblem
  - weitere Truth-Ausdehnung nach April / Maerz:
    - `LOWER2K_DUR8_EVT24`
      - jetzt `84` geloeste Tage bis `2023-04-16`
      - `23` Heavy-Day-Failures
    - `LOWER1K_DUR8_EVT24`
      - jetzt `68` geloeste Tage bis `2023-03-11`
      - weiter nur `2` Heavy-Day-Failures
  - neuer Daily-Retrain auf diesem Truth-Stand:
    - Datensatz:
      - `Learning/datasets/29cc229d58203647cbb5851e7d66ecdcd401eff0cb9e3ced589c38c1dea74e8a/`
    - Modell:
      - `Learning/models/thermflex_daily_results_xgb_table_09_paper_29cc229d5820/`
    - grouped holdout:
      - `mean R2 = 0.134`
      - `dispatch_operating_cost_pct_change = 0.903`
      - `co2_emissions_total_pct_change = -0.012`
      - `district_gas_boiler_peak_kw_delta = 0.382`
      - `district_gas_boiler_generation_kwh_delta = 0.335`
      - `thermflex_shifted_space_heat_kwh = -0.579`
      - `thermflex_rebound_kwh = -0.224`
    - Schluss:
      - der Daily-Holdout verbessert sich mit mehr `dur8`-Truth jetzt kontinuierlich
      - Cost ist bereits sehr stark, CO2 fast neutral
      - die letzten echten Blocker bleiben:
        - `shifted`
        - `rebound`
        - zweitens Boiler energy
      - ab hier wird der naechste Hebel wahrscheinlich nicht nur mehr Truth, sondern auch ein inhaltlich reicherer Daily-Truthvertrag mit zusaetzlichen Wetter-/State-Metriken
  - Daily-Truthvertrag additiv um Aussentemperatur-Metriken erweitert:
    - neue Kontextgroessen:
      - `t_outdoor_max_c`
      - `t_outdoor_range_c`
      - `hdd18_kh`
      - `t_outdoor_mean_prevday_c`
      - `t_outdoor_mean_nextday_c`
    - neue engineered Wettergroessen:
      - `hdd18_per_space_heat`
      - `t_outdoor_prevday_delta_c`
      - `t_outdoor_nextday_delta_c`
    - Umsetzung in:
      - `Learning/thermflex_daily_results/schema.py`
      - `Learning/thermflex_daily_results/features.py`
      - `Learning/thermflex_daily_results/dataset_builder.py`
    - Datenquelle:
      - keine neuen MILP-Laeufe
      - explizite Anreicherung aus dem bestehenden kanonischen Vienna-2023-Tageskontext
  - Retrain mit wettererweitertem Daily-Vertrag:
    - Datensatz:
      - `Learning/datasets/d30bb08d4b86d53bb751d8d6fc389eefdd3a20804fd0f96ce0ace0b2452409b0/`
    - Modell:
      - `Learning/models/thermflex_daily_results_xgb_table_09_paper_d30bb08d4b86/`
    - grouped holdout:
      - `mean R2 = 0.065`
      - `dispatch_operating_cost_pct_change = 0.919`
      - `co2_emissions_total_pct_change = -0.108`
      - `district_gas_boiler_peak_kw_delta = 0.386`
      - `district_gas_boiler_generation_kwh_delta = 0.281`
      - `thermflex_shifted_space_heat_kwh = -0.756`
      - `thermflex_rebound_kwh = -0.330`
    - Schluss:
      - zusaetzliche Aussentemperaturmetriken verbessern Cost weiter
      - sie helfen aber nicht beim eigentlichen Daily-Blocker:
        - `shifted`
        - `rebound`
        - taegliches `CO2`
      - daher bleibt `29cc...` der bevorzugte Daily-Stand, waehrend `d30...` als dokumentierter Wetter-Contract-Test im Repo bleibt
  - Zusatztests auf dem wettererweiterten Vertrag:
    - `shifted_rebound_only`
      - Modell:
        - `Learning/models/thermflex_daily_results_xgb_shifted_rebound_only_d30bb08d4b86/`
      - mean `R2 = -0.543`
    - `co2_only`
      - Modell:
        - `Learning/models/thermflex_daily_results_xgb_co2_only_d30bb08d4b86/`
      - `co2_emissions_total_pct_change = -0.108`
    - Schluss:
      - auch auf dem wettererweiterten Vertrag bleiben diese Ziele isoliert schwach; das Problem ist damit nicht nur Profilkopplung
  - Daily-Kohortenmix als zusaetzlicher Mechanik-Kontext getestet.
    - Motivation:
      - `shifted` und `rebound` haengen nicht nur an Wetter und Gesamtlast, sondern daran, welche Baualters-/Sektor-Kohorten den taeglichen DH-space-heat-Mix dominieren.
    - Umsetzung:
      - `Learning/thermflex_daily_results/dataset_builder.py`
        - kanonischen Vienna-2023-Tageskontext um taegliche `dh_space_heat_share_*`-Anteile je `building_key` erweitert
        - zusaetzlich:
          - `dh_space_heat_share_residential_total`
          - `dh_space_heat_share_non_residential_total`
      - `Learning/thermflex_daily_results/schema.py`
        - neue explizite Kontextspalten fuer die acht Kohortenanteile
        - neue engineered Groessen:
          - `residential_to_non_residential_space_heat_ratio`
          - `old_stock_space_heat_share`
          - `modern_stock_space_heat_share`
      - `Learning/thermflex_daily_results/features.py`
        - additive engineered Kohortenmix-Indikatoren
    - Retrain auf gleichem Truth-Pool:
      - Datensatz:
        - `Learning/datasets/3aa909c1c12e3754f6320a25f697d797eef1dc6ce9a5c0b5f4c5aeabc6986078/`
      - Modell:
        - `Learning/models/thermflex_daily_results_xgb_table_09_paper_3aa909c1c12e/`
      - grouped holdout:
        - `mean R2 = 0.082`
        - `dispatch_operating_cost_pct_change = 0.906`
        - `co2_emissions_total_pct_change = 0.108`
        - `district_gas_boiler_peak_kw_delta = 0.377`
        - `district_gas_boiler_generation_kwh_delta = 0.268`
        - `thermflex_shifted_space_heat_kwh = -0.845`
        - `thermflex_rebound_kwh = -0.323`
    - Zusatztest:
      - `shifted_rebound_only`
        - `Learning/models/thermflex_daily_results_xgb_shifted_rebound_only_3aa909c1c12e/`
        - mean `R2 = -0.584`
      - `co2_only`
        - `Learning/models/thermflex_daily_results_xgb_co2_only_3aa909c1c12e/`
        - `co2_emissions_total_pct_change = 0.108`
    - Schluss:
      - taegliche Kohortenanteile helfen dem aktuellen Daily-`Table 09`-Pfad nicht robust
      - CO2 wird positiv, aber `shifted` / `rebound` werden schlechter
      - naechster plausibler Hebel ist nicht noch mehr statischer Kontext, sondern kuenftige Daily-Truth-Erweiterung um explizite Komfort-/Temperaturdiagnostik als Auxiliary-Targets
  - Future-Truth-Hebel fuer Daily-Screens vorbereitet.
    - `Optimization/run/analysis/screen_vienna_constant_thermflex_heating_season_days.py`
      exportiert ab jetzt zusaetzlich pro Flex-Tag:
      - `thermflex_t_in_min_c`
      - `thermflex_t_in_max_c`
      - `thermflex_temperature_violation_degree_hours_total`
    - Zweck:
      - kuenftige Daily-Truth-Familien koennen die Mechanik nicht nur ueber Cost/Boiler/Shift/Rebound sehen,
        sondern auch ueber explizite Komfort-/Temperaturdiagnostik als Auxiliary-Targets
    - bewusst noch nicht in den aktuellen V1-Trainingsvertrag aufgenommen:
      - bestehende Bundles enthalten diese Spalten noch nicht
      - zuerst muessen neue Partial-/Full-Screens mit dem erweiterten Export entstehen

- 2026-05-08: Fig. 15 Titel fuer Paper-Export entfernt.
  - Aenderung:
    - Gesamttitel aus Fig. 15 entfernt.
    - Spaltentitel mit Monats-/Datumsbeschriftung aus Fig. 15 entfernt.
    - Hauptplot sowie Tau-4/5/6-Varianten neu gerendert.
  - Status:
    - reine Darstellungsanpassung; Re-Render aus bestehenden Caches ohne neue MILP-Rechnung.

- 2026-05-14: Hourly-Thermflex-Mechanikpfad verbreitert und gegen den Daily-Blocker getestet.
  - Motivation:
    - Der Daily-`Table 09`-Pfad bleibt trotz mehr Truth, Wetter- und Kohortenmix-Features vor allem bei
      - `thermflex_shifted_space_heat_kwh`
      - `thermflex_rebound_kwh`
      schwach.
    - Daher wurde ein separater Hourly-Mechanikpfad als neuer Hebel weitergezogen.
  - Neuer Learning-Layer:
    - `Learning/thermflex_hourly_mechanism/`
    - neue Module:
      - `schema.py`
      - `dataset_builder.py`
      - `validate.py`
      - `train.py`
      - `README.md`
  - Erste Hourly-Truthfamilie:
    - nur die bereits vorhandenen `constant_thermflex_cohort_utilization_hourly.csv`
    - nach Deduplikation effektiv nur ein 13er-Set aus `paper_dispatch_comparison_20260423_120713`
    - Datensatz:
      - `Learning/datasets/806dae46fdf907838fe26fd3981e4f3e593dd5610386f1f8705969728c3e219b/`
    - erster grouped-holdout:
      - `mean R2 = -0.105`
      - positive Einzelziele:
        - `cohort_q_delta_kwh ~ 0.17`
        - `cohort_preheat_extra_kwh ~ 0.05`
        - `cohort_cutback_shed_kwh ~ 0.15`
      - schwach:
        - `cohort_flex_active_member_share`
        - `cohort_t_in_weighted_mean_c`
  - Reusable hourly-truth hydration aus bestehenden Bundles aufgebaut.
    - `Optimization/run/analysis/build_constant_thermflex_cohort_utilization.py`
      - generischen Kern `build_selected_run_cohort_utilization_bundle(...)` eingefuehrt
      - bestehender konstanter Pfad bleibt als Wrapper erhalten
    - neues Hilfsskript:
      - `Optimization/run/analysis/hydrate_thermflex_cohort_utilization_from_selected_runs.py`
    - Zweck:
      - fehlende reusable Hourly-Exports explizit aus vorhandenen `selected_runs.json`-Manifests nachziehen
      - Scope bewusst nur:
        - `paper_dispatch_comparison_*`
        - `dh_thermflex_run_*/paper_core`
      - keine stille Mischung anderer Bundle-Familien
    - Manifest-Normalisierung:
      - alte `selected_runs.json` ohne `override_path` werden explizit ueber den timestamped `run_dir`-Slug auf den thermflex-Override-SSOT aufgeloest
      - harter Fehler, falls diese Aufloesung nicht eindeutig moeglich ist
    - Coverage-Optimierung:
      - Hydrator liest bestehende Hourly-Truthbasis und replayt nur noch wirklich neue `run_dir`s
  - Hydrationsergebnis:
    - neue generische Hourly-Exports (`thermflex_cohort_utilization_hourly.csv`) erfolgreich fuer:
      - `paper_dispatch_comparison_20260402_195332`
      - `paper_dispatch_comparison_20260403_102050`
      - `paper_dispatch_comparison_20260403_111854`
      - `paper_dispatch_comparison_20260403_120453`
    - damit jetzt `16` explizite Thermflex-Run-Dirs im Hourly-Pool statt nur `12/13`
  - Verbreiterte Hourly-Familie:
    - Datensatz:
      - `Learning/datasets/8d1b317881d2deeb567f3934ecbea12f79f13dea10c47554e2c9cafde8894ea6/`
    - Truth:
      - `3072` Zeilen
      - `5` Bundlequellen
    - grouped-holdout:
      - Modell:
        - `Learning/models/thermflex_hourly_mechanism_xgb_mechanism_core_8d1b317881d2/`
      - `mean R2 ~ 0.00`
      - positive Ziele:
        - `cohort_q_delta_kwh ~ 0.10`
        - `cohort_preheat_extra_kwh ~ 0.05`
        - `cohort_cutback_shed_kwh ~ 0.10`
        - `cohort_temperature_violation_degree_h ~ 0.27`
  - Explizite Policy-/Steuerungsfeatures aus Override-SSOT getestet.
    - Hourly-Datasetbuilder reichert jetzt pro `run_dir` explicit an:
      - `control_mode`
      - `reference_control_mode`
      - `constant/day/night_setpoint_c`
      - `day/night_lower_bound_c`
      - Event-/Recovery-/Upper-bound Flags
    - Ergebnis:
      - fachlich plausibel, aber auf dem grouped holdout kein Durchbruch;
        breites `mechanism_core` blieb ungefaehr bei `mean R2 ~ 0`
  - Engerer Hourly-Zuschnitt mit energienahem Targetprofil.
    - absolute Energieversion:
      - Datensatz:
        - `Learning/datasets/2435c3708d461f9eba3194d8e10e5ef6c3d98b76522756de3f37499bd6b7ad68/`
      - Modell:
        - `Learning/models/thermflex_hourly_mechanism_xgb_mechanism_energy_2435c3708d46/`
      - grouped-holdout:
        - `mean R2 ~ 0.13`
    - flaechennormierte Energieversion:
      - zusätzliche engineered Targets:
        - `cohort_q_delta_wh_per_m2`
        - `cohort_preheat_extra_wh_per_m2`
        - `cohort_cutback_shed_wh_per_m2`
      - Datensatz:
        - `Learning/datasets/f8f5fa261ac29180f4272a22c77b1f779495415b1cd6e3e57a66c9f43b5da54d/`
      - Modell:
        - `Learning/models/thermflex_hourly_mechanism_xgb_mechanism_energy_intensive_f8f5fa261ac2/`
      - grouped-holdout:
        - `mean R2 ~ 0.20`
        - beste Einzelziele:
          - `cohort_preheat_extra_wh_per_m2 ~ 0.32`
          - `cohort_temperature_violation_degree_h ~ 0.27`
  - Rueckaggregationstest auf Daily-Mechanik:
    - aus den holdout-stuendlichen Vorhersagen wurden pro Run wieder Tagesserien aufgebaut
    - dann `compute_thermflex_series_metrics(...)` auf die aggregierten Serien angewandt
    - Befund:
      - area-normalisierte Hourly-Ziele sind besser als rohe absolute kWh,
      - aber die Rueckrechnung auf holdout-`shifted/rebound/peak` bleibt noch negativ
      - der Hourly-Pfad ist damit aktuell plausibler als der reine Daily-Kontextpfad, aber noch nicht stark genug fuer robuste direkte Table-09-Rekonstruktion
  - Explizite Policy-Familiensegmentierung getestet.
    - Dataset-Builder unterstuetzt jetzt explizit:
      - `family_slice = all`
      - `family_slice = constant_only`
      - `family_slice = day_night_only`
    - Ziel:
      - Regimewechsel (`constant` vs `day_night`) nicht mehr im selben grouped holdout mit der eigentlichen Stundenmechanik vermischen
    - `constant_only` auf dem besten area-normalisierten Hourly-Profil:
      - Datensatz:
        - `Learning/datasets/6fc7ad11f8bae814f2e29bff77ecea84c51425aa23a23d8f786e1ee7c8c960a5/`
      - Modell:
        - `Learning/models/thermflex_hourly_mechanism_xgb_mechanism_energy_intensive_6fc7ad11f8ba/`
      - grouped holdout:
        - `mean R2 ~ 0.345`
        - `cohort_temperature_violation_degree_h ~ 0.883`
        - `cohort_cutback_shed_wh_per_m2 ~ 0.294`
        - `cohort_q_delta_wh_per_m2 ~ 0.160`
        - `cohort_preheat_extra_wh_per_m2 ~ 0.042`
      - Schluss:
        - Segmentierung hilft deutlich; ein Teil der vorherigen Hourly-Schwäche kam aus Familienmischung
    - `day_night_only`:
      - Datensatz:
        - `Learning/datasets/e8d5924ae0d91f571795ce619e396b7b2a52bf384e2784678cd5aaca5ff2f867/`
      - Status:
        - nur `192` Zeilen aus genau einem `day_night_thermflex`-Run
      - grouped holdout:
        - fail-fast mit
          - `grouped holdout requires at least two distinct groups in split_group_run, got 1`
      - Schluss:
        - `day_night` ist aktuell explizit eine Truth-Basis-Luecke, nicht nur ein Modellproblem
  - Direkte `day_night`-Gold-Run-Dirs als Hourly-Truth angebunden.
    - neues Hilfsskript:
      - `Optimization/run/analysis/hydrate_thermflex_cohort_utilization_from_gold_run_dirs.py`
    - Scope:
      - top-level `*day_night_thermflex_paper_day_ahead`
      - genau ein Vertreter je `truth_dataset.csv`-Signatur
      - unvollstaendige Run-Dirs werden explizit als Skip-Status gemeldet
    - Befund auf direkter Gold-Basis:
      - `20260402_180447_...` unvollstaendig: weder `truth_dataset.csv` noch `X_opt.npy`
      - `20260402_183711_...` unvollstaendig: `truth_dataset.csv`, aber kein `X_opt.npy`
      - `20260402_183827_...` und `20260402_184012_...` teilen dieselbe Truth-Signatur `37cb...`
      - `20260402_192345_...` bildet eine zweite distincte Truth-Signatur `a7ae...`
    - Motivation:
      - ohne Signatur-Dedupe wuerden mehrere direkte Reruns kuenstlich leichte grouped holdouts erzeugen
  - `day_night_only` danach neu trainiert.
    - Datensatz:
      - `Learning/datasets/9a6779e1b8e6eaa4accf41b4846deaec755da9b84a6c94a73b1c36480766a004/`
    - Modell:
      - `Learning/models/thermflex_hourly_mechanism_xgb_mechanism_energy_intensive_9a6779e1b8e6/`
    - grouped holdout:
      - `mean R2 = 0.9979`
      - `cohort_q_delta_wh_per_m2 = 0.9982`
      - `cohort_preheat_extra_wh_per_m2 = 1.0000`
      - `cohort_cutback_shed_wh_per_m2 = 0.9985`
      - `cohort_temperature_violation_degree_h = 0.9950`
    - Rueckaggregation `hourly -> daily` auf Holdout:
      - `shifted_r2 = 0.9993`
      - `rebound_r2 = 0.9936`
      - `peak_r2 = 0.9992`
    - Schluss:
      - `day_night` war primaer eine Truth-Basis-Luecke; mit zwei distincten Signaturgruppen ist die Hourly-Mechanikfamilie praktisch geloest
  - Weitere Segmentierung innerhalb `constant` getestet.
    - Dataset-Builder unterstuetzt jetzt zusaetzlich:
      - `family_slice = constant_evt1_only`
      - `family_slice = constant_evt24_only`
    - `constant_evt1_only`:
      - Datensatz:
        - `Learning/datasets/c6d583a1294d20a396143ad8b272e35cd43f074b66d3f9dafebbb333f22f1888/`
      - Modell:
        - `Learning/models/thermflex_hourly_mechanism_xgb_mechanism_energy_intensive_c6d583a1294d/`
      - grouped holdout:
        - `mean R2 = 0.3405`
      - Rueckaggregation:
        - `shifted_r2 = 0.4149`
        - `rebound_r2 = 0.0911`
        - `peak_r2 = 0.5990`
      - Schluss:
        - `evt1` trennt einen brauchbaren Teil der konstanten Mechanik ab, aber Rebound bleibt deutlich schwerer
    - `constant_evt24_only`:
      - Datensatz:
        - `Learning/datasets/7dd2e36352ff716473e9cd94e88e810122f4bbbfe71168f86b81f6e373e77cc6/`
      - Modell:
        - `Learning/models/thermflex_hourly_mechanism_xgb_mechanism_energy_intensive_7dd2e36352ff/`
      - grouped holdout:
        - `mean R2 = -2.181`
      - Schluss:
        - das aktuelle `evt24`-Segment ist truthseitig zu klein und zudem heterogen (`upper_only` vs `lower_relax`)
    - `constant_evt1_lower_relax_only`:
      - Datensatz:
        - `Learning/datasets/9929a8c45518e55ffba54c28e930106c643afaad204def50217a8a00dea28b3a/`
      - Modell:
        - `Learning/models/thermflex_hourly_mechanism_xgb_mechanism_energy_intensive_9929a8c45518/`
      - grouped holdout:
        - `mean R2 = 0.1223`
      - Schluss:
        - das Entfernen des einzelnen `evt1 upper_only`-Runs verbessert den `evt1`-Slice nicht; der Rebound-Engpass im konstanten Regime liegt tiefer als dieser eine Mischfall
  - Direkte `constant evt24`-Szenarioruns als Hourly-Truth angebunden.
    - der direkte Gold-Run-Hydrator unterstuetzt jetzt explizit drei Familien:
      - `day_night`
      - `constant_evt24_lower_relax`
      - `constant_evt24_upper_only`
    - explizite Szenariosuffixe werden SSOT-konsistent auf den Baseline-Override zurueckgefuehrt:
      - `_peak_YYYYMMDD`
      - `_price_YYYYMMDD`
      - `_sunny_YYYYMMDD`
      - `_wintertyp_YYYYMMDD`
      - `_shouldertyp_YYYYMMDD`
    - hydratisierte `evt24 lower_relax`-Signaturen:
      - baseline
      - peak
      - price
      - sunny
      - wintertyp
      - shouldertyp
    - hydratisierte `evt24 upper_only`-Signaturen:
      - baseline
      - peak
      - price
      - sunny
      - wintertyp
      - shouldertyp
  - `evt24` danach neu segmentiert trainiert.
    - `constant_evt24_lower_relax_only`
      - Datensatz:
        - `Learning/datasets/4f124c87fe01b2b32221284cf22c24ed621e7a6908a04bd457061fae456989a9/`
      - Modell:
        - `Learning/models/thermflex_hourly_mechanism_xgb_mechanism_energy_intensive_4f124c87fe01/`
      - grouped holdout:
        - `mean R2 = 0.5344`
      - Rueckaggregation:
        - `shifted_r2 = 0.7879`
        - `rebound_r2 = 0.0000`
        - `peak_r2 = 0.3006`
    - `constant_evt24_upper_only`
      - Datensatz:
        - `Learning/datasets/5f5fdf867b21d4ec7bd836ba8ab5a014dbe1616dbc48f634c394ba2d8cee9dd8/`
      - Modell:
        - `Learning/models/thermflex_hourly_mechanism_xgb_mechanism_energy_intensive_5f5fdf867b21/`
      - grouped holdout:
        - `mean R2 = 0.4505`
      - Rueckaggregation:
        - `shifted_r2 = 0.3435`
        - `rebound_r2 = 0.3126`
        - `peak_r2 = 0.6051`
    - gemischtes `constant_evt24_only` nach Truth-Erweiterung:
      - Datensatz:
        - `Learning/datasets/04c7e1286d3f47787eea7fa87ce0ba2b39e9072d436d164e23c490565a5ebfc6/`
      - Modell:
        - `Learning/models/thermflex_hourly_mechanism_xgb_mechanism_energy_intensive_04c7e1286d3f/`
      - grouped holdout:
        - `mean R2 = 0.4939`
      - Rueckaggregation:
        - `shifted_r2 = 0.7405`
        - `rebound_r2 = 0.3155`
        - `peak_r2 = 0.6673`
    - Schluss:
      - `evt24` ist mit direktem Szenariotruth nicht mehr kaputt
      - aber weiterhin deutlich schwerer als `day_night`
      - speziell Rebound bleibt der hartnaeckigste Teil der konstanten `evt24`-Mechanik

- 2026-05-07: Story-aligned Paper-Library `paper_library/` fuer das Surrogate-MOO-MES-Review aufgesetzt.
  - Motivation:
    - `references/review_mes_moo_surrogates.bib` ist mit ~2900 Eintraegen die volle Literaturpoolbasis fuer Screening und Appendix-Evidence-Map.
    - Fuer Overleaf/Manuskript ist das zu schwer; gebraucht wird ein zitierfaehiger, kuratierter Subset (~240 Papers), der die bereits geschriebene Story exakt traegt.
  - Auswahlskript:
    - `Documentation/Papers/review_surrogate_modeling/paper_library/select_paper_library.py`
    - Liest alle `\cite{...}` aus `manuscript/*.tex` und macht diese Keys verpflichtend (aktuell 103 Mandatory-Keys).
    - Definiert 27 Story-Buckets (`B01_cornerstone_reviews` ... `B27_mcdm`), die die Sektionen 1-9 des Drafts spiegeln (Reviews, Surrogat-Familien GP/PCE/RBF/Trees/Neural/Constraint/Hybrid/L2O, DoE, Multi-Fidelity, Bayesian, Warm-Start, Decomposition, Uncertainty, Validation, Anwendungen ED/UC/OPF/CapEx/DH/MES/MG/MOO/Stoch, NSGA, Metaheuristiken, MCDM).
    - Jedes Bucket hat eine Quote und ein Predicate ueber `title_ascii` plus die `matched_*`-Tags aus `surrogates_esm_screening_enriched.csv` und `moo_multicriteria_screening.csv`. Mandatory-Keys werden zuerst eingebucht, dann wird per `cited_by_count` aufgefuellt.
    - Globaler Top-Up auf 240 Eintraege; harter Cap bei 260 (Mandatory wird nie verworfen).
  - Output:
    - `paper_library/review_paper_library.bib` (Subset von `review_mes_moo_surrogates.bib`, 260 Eintraege)
    - `paper_library/review_paper_library_manifest.csv` (Provenance: cite_key, primary_bucket, all_buckets, mandatory, year, title, venue, doi, cited_by_count, tier, focus, primary_topic, sources)
    - `paper_library/review_paper_library_buckets.csv` (Long-Format Bucket -> cite_key)
    - `paper_library/review_paper_library_citation_plan.md` (pro Bucket Liste der Cite-Keys mit `*` fuer bereits zitierte und ohne Stern fuer Top-Up; sortiert nach Citation-Count)
    - `paper_library/README.md` (Workflow- und Bucket-Doku, Overleaf-Anweisung)
  - Bucket-Verteilung im Run:
    - dichteste Buckets sind `B02_gp_kriging` (25), `B06_neural_surrogates` (18), `B04_rbf_kernel` (18), `B03_pce_response_surface` (16), `B23_moo_design` (14), `B01_cornerstone_reviews` (14), `B21_mes_sector_coupling` (12), `B22_microgrid_hub` (12), `B25_moo_algorithms_nsga` (10).
    - `B13_warm_start` ist intentional leer geblieben: das ist eine echte Luecke im Pool und wird in der Open-Challenges-Sektion adressiert.
    - `B27_mcdm` hat nur 1 Treffer, weil der Pool auf Surrogate+MOO+MES gefiltert ist; fuer MCDM-Vertiefung muesste ggf. die `moo_only`-Schicht aus `moo_multicriteria_screening.csv` separat zugemischt werden.
  - Manuskript-Konsistenz:
    - Sanity-Check des Skripts schlaegt fehl, falls ein Mandatory-Cite-Key nicht im Pool steht; aktuell sind alle 103 Keys aufloesbar.
    - Workflow: bei neuem `\cite{...}` im Manuskript einfach `py select_paper_library.py` re-runnen, dann ist die Library wieder konsistent.

- 2026-05-14: Hourly-Thermflex-Mechanik gezielt auf wirksame Hebel statt weiterer Breite geprueft.
  - Motivation:
    - Nach der Segmentierung `day_night` / `constant evt1` / `constant evt24` war noch offen, ob der naechste Hebel fuer `evt24` eher
      - mehr Truth,
      - Auxiliary-Targets,
      - oder eine schlankere Featurebasis ist.
  - Zuerst Architekturpunkt explizit geklaert:
    - `Learning/thermflex_hourly_mechanism/train.py` trainiert targetweise getrennte `XGBRegressor`.
    - Daraus folgt:
      - zusaetzliche Auxiliary-Targets staerken im aktuellen V1-Vertrag **nicht direkt** die Vorhersage von `q_delta` / `cutback` / `rebound`,
      - weil keine gemeinsame Multi-Task-Repraesentation gelernt wird.
    - Konsequenz:
      - fuer den aktuellen Pfad sind die wirksamen Hebel vor allem
        - Segmentierung,
        - Truth-Diversitaet,
        - Featurevertrag,
        - nicht bloss mehr Zielspalten.
  - Danach gezielte Ablation auf `evt24 lower_relax` und `evt24 upper_only` gefahren.
    - Getestete Featurebloecke:
      - `all`
      - `no_policy`
      - `no_weather_system`
      - `no_cohort_id`
      - `time_ref_only`
    - Targets fuer die Ablation:
      - `cohort_q_delta_wh_per_m2`
      - `cohort_cutback_shed_wh_per_m2`
      - `cohort_temperature_violation_degree_h`
    - Befund `evt24 lower_relax`:
      - alle Varianten liegen sehr nah beieinander (`mean R2 ~ 0.53` bis `0.55`)
      - `time_ref_only` und `no_weather_system` sind sogar leicht besser als der volle Block
      - Policy-, Wetter- und Kohortenbloecke sind dort also nicht der limitierende Hebel
    - Befund `evt24 upper_only`:
      - voller Block `mean R2 ~ 0.526`
      - `time_ref_only` leicht besser mit `mean R2 ~ 0.542`
      - auch hier tragen viele Zusatzfeatures nicht den Hauptgewinn
  - Zusatzbefund aus den Truthstatistiken:
    - `evt24 lower_relax`
      - `cohort_preheat_extra_wh_per_m2` ist praktisch degenerate (`mean ~ 0`, `std ~ 0`)
      - `cohort_temperature_violation_degree_h` ist identisch `0`
    - daraus folgt:
      - ein Teil des aktuellen Zielblocks ist in diesem Slice strukturell wenig informativ
      - das offene Problem sitzt dort eher in der Rueckaggregation / Rebound-Form als in fehlenden Zusatzfeatures
  - Tages-Rueckaggregation mit einem extrem schlanken `time_ref_only`-Nur-`q_delta`-Test geprueft.
    - Ergebnis:
      - `evt24 lower_relax`
        - `shifted_r2 ~ 0.845`
        - `peak_r2` deutlich negativ
        - `rebound_r2` nicht stabil auswertbar
      - `evt24 upper_only`
        - Rueckaggregation rein aus `q_delta` ist instabil und klar schlechter als der segmentierte Vollpfad
    - Schluss:
      - ein sehr schlanker Block reicht fuer einzelne stuendliche Teilziele,
      - aber nicht als alleiniger Rueckaggregationspfad fuer die gesamte taegliche Mechanik.
  - Verdichteter Schluss:
    - was das Modell aktuell wirklich besser macht:
      - homogene Policy-Familien
      - diverse Szenario-Truth innerhalb derselben Familie
      - kein ueberladener, verrauschter Featurevertrag
    - was im aktuellen V1-Pfad **nicht** der naechste direkte Hebel ist:
      - einfach mehr Zielspalten als Auxiliary-Targets
      - noch mehr generische Wetter-/Kohortenkontextfeatures fuer `evt24`

- 2026-05-14: Expliziten kompakten `evt24`-Feature-Mode in den Hourly-Layer aufgenommen und KPI-orientiert gegengeprueft.
  - Code:
    - `Learning/thermflex_hourly_mechanism/dataset_builder.py`
    - `Learning/thermflex_hourly_mechanism/train.py`
    - `Learning/thermflex_hourly_mechanism/README.md`
  - Neuer expliziter `feature_mode`:
    - `full`
    - `evt24_compact`
  - `evt24_compact` ist bewusst schmal:
    - `hour_of_day`, `day_of_year`, `month`
    - `t_outdoor_c`
    - `dh_space_heat_kwh`, `dh_total_kwh`
    - `cohort_q_heat_ref_kwh`
    - zyklische Zeitfeatures
    - `cohort_key` als einziges Kategorikum
  - Motivation:
    - die vorherige Ablation hatte gezeigt, dass fuer homogene `evt24`-Familien viele Zusatzbloecke kaum helfen oder leicht schaden
    - deshalb sollte der reduzierte Vertrag als reproduzierbare first-class Option in den Dataset-Hash eingehen
  - Kompakte `evt24`-Modelle trainiert:
    - `constant_evt24_lower_relax_only`
      - Datensatz:
        - `Learning/datasets/3d01c12e0c96e642f8c8b3bc43607bbad9a6c4b621f6cab9dbdc23d89248259b/`
      - Modell:
        - `Learning/models/thermflex_hourly_mechanism_xgb_mechanism_energy_intensive_3d01c12e0c96/`
      - grouped holdout `mean R2 = 0.5417`
    - `constant_evt24_upper_only`
      - Datensatz:
        - `Learning/datasets/9ef37b8c8d0d1b807653da0c2b6c93d1e3752f1208fb539722e73f55274fbe00/`
      - Modell:
        - `Learning/models/thermflex_hourly_mechanism_xgb_mechanism_energy_intensive_9ef37b8c8d0d/`
      - grouped holdout `mean R2 = 0.4523`
  - Einordnung gegen die bestehenden Vollmodelle:
    - `evt24 lower_relax`
      - voll: `mean R2 = 0.5344`
      - kompakt: `mean R2 = 0.5417`
      - also nur kleiner interner Vorteil
    - `evt24 upper_only`
      - voll: `mean R2 = 0.4505`
      - kompakt: `mean R2 = 0.4523`
      - praktisch gleich
  - KPI-orientierter Schluss:
    - der kompakte Modus ist als explizite Experimentachse sauber eingebaut
    - er ist aber aktuell **kein klarer Gewinner** fuer die rueckaggregierten Figure-/KPI-Groessen
    - damit bleibt der naechste Hebel weiterhin:
      - family-routed Nutzung
      - weitere Truth-Diversitaet innerhalb homogener Regime
      - und erst danach weitere Feature-Modus-Schaerfung

- 2026-05-14: Reproduzierbaren KPI-first-Evaluator fuer den Hourly-Pfad eingebaut und auf `evt24` gegengeprueft.
  - Neu:
    - `Learning/thermflex_hourly_mechanism/evaluate_kpi_reaggregation.py`
  - Zweck:
    - Holdout-Modelle nicht nur nach internem Hourly-`R2`, sondern direkt nach den rueckaggregierten Paper-Groessen vergleichen:
      - `thermflex_shifted_space_heat_kwh`
      - `thermflex_rebound_kwh`
      - `thermflex_peak_change_kw`
  - Auf die vier aktuellen `evt24`-Varianten angewandt:
    - `evt24_lower_full`
      - `shifted_r2 ~ 0.979`
      - `rebound_r2 = nan`
      - `peak_r2 ~ -8.51`
      - `2` Holdout-Tage / `2` Holdout-Runs
    - `evt24_lower_compact`
      - `shifted_r2 ~ 0.965`
      - `rebound_r2 = nan`
      - `peak_r2 ~ -8.53`
      - `2` Holdout-Tage / `2` Holdout-Runs
    - `evt24_upper_full`
      - `shifted_r2` stark negativ
      - `rebound_r2` stark instabil negativ
      - `peak_r2 = nan`
      - `2` Holdout-Tage / `2` Holdout-Runs
    - `evt24_upper_compact`
      - praktisch identisch zum Vollmodus
      - ebenfalls nur `2` Holdout-Tage / `2` Holdout-Runs
  - Wichtiger methodischer Befund:
    - Der neue KPI-Check macht sichtbar, dass die `evt24`-KPI-Bewertung aktuell selbst noch fragil ist, weil die gruppierte Holdout-Basis in diesen Regimen sehr klein bleibt.
    - Der naechste echte Hebel ist daher nicht weitere Featurefeinheit, sondern mehr **unabhaengige Truth-Gruppen innerhalb derselben `evt24`-Familien**, damit die KPI-Rueckaggregation ueberhaupt stabil beurteilbar wird.

- 2026-05-14: Figure-nahe `paper_mechanism_bundle_*`-Tage als generischen Hourly-Truthvertrag angeschlossen und die `evt24`-Slices erneut KPI-first bewertet.
  - Code:
    - `Optimization/run/analysis/build_vienna_constant_thermflex_mechanism_bundle.py`
    - `Optimization/run/analysis/hydrate_thermflex_cohort_utilization_from_mechanism_bundles.py`
    - `Learning/thermflex_hourly_mechanism/dataset_builder.py`
    - `Learning/thermflex_hourly_mechanism/README.md`
  - Mechanism-Bundle-Builder schreibt jetzt direkt:
    - `thermflex_cohort_utilization_hourly.csv`
    - `thermflex_cohort_utilization_summary.csv`
    in jeden neuen `paper_mechanism_bundle_*`-Ordner.
  - Bestehende Bundles hydriert:
    - `paper_mechanism_bundle_20260423_211704`
    - `paper_mechanism_bundle_20260423_221857`
  - Hourly-Dataset-Builder explizit um synthetische `_replay_..._YYYYMMDD_mechanism`-Run-Dirs erweitert, damit deren Override-SSOT sauber aufloesbar bleibt.
  - Neuer Befund fuer `constant_evt24_upper_only` nach figure-naher Truth-Erweiterung:
    - Datensatz:
      - `Learning/datasets/262fb2518c9421a49e9a31ae1e9b5cd9350d29a00b1b205f6fb157a95ceb49f6/`
    - Modell:
      - `Learning/models/thermflex_hourly_mechanism_xgb_mechanism_energy_intensive_262fb2518c94/`
    - grouped holdout:
      - `mean R2 ~ 0.12`
    - KPI-Reaggregation:
      - `shifted_r2 ~ -1.43`
      - `rebound_r2 ~ -0.57`
      - `peak_r2 ~ -0.28`
      - jetzt `3` Holdout-Tage / `3` Holdout-Runs statt der vorherigen fragilen 2/2-Bewertung
  - Neuer Befund fuer gemischtes `constant_evt24_only`:
    - Datensatz:
      - `Learning/datasets/ad012bde555a5b0510cca7023eba9b872961422fc07a577891563be4ed2351ab/`
    - Modell:
      - `Learning/models/thermflex_hourly_mechanism_xgb_mechanism_energy_intensive_ad012bde555a/`
    - grouped holdout:
      - `mean R2 ~ 0.55`
    - KPI-Reaggregation:
      - `shifted_r2 ~ 0.38`
      - `rebound_r2 ~ 0.55`
      - `peak_r2 ~ -4.62`
      - jetzt `5` Holdout-Tage / `5` Holdout-Runs
  - Schluss:
    - die neuen mechanism bundles sind nicht nur Zusatzdaten, sondern ein haerterer und ehrlicherer Figure-Holdout
    - der verbleibende gezielte KPI-Engpass ist jetzt enger:
      - `peak` im konstanten `evt24`
      - `upper_only dur24 evt24` als eigenes Figure-Regime
  - zusaetzlicher KPI-first Targetprofilvergleich auf dem erweiterten `constant_evt24_only`-Truth:
    - `mechanism_core`
      - Datensatz:
        - `Learning/datasets/a3a89d44afeb8df795a2693e7274017ef391b19a6c50680bcf3bfc43a1b77573/`
      - Modell:
        - `Learning/models/thermflex_hourly_mechanism_xgb_mechanism_core_a3a89d44afeb/`
      - KPI-Reaggregation:
        - `shifted_r2 ~ -2.77`
        - `rebound_r2 ~ -1.32`
        - `peak_r2 ~ -9.04`
    - `mechanism_energy`
      - Datensatz:
        - `Learning/datasets/1a5a6cf74563aaac790c95ccf4390047ac9e77c8cdef805d47e0c1cd3e32ebc6/`
      - Modell:
        - `Learning/models/thermflex_hourly_mechanism_xgb_mechanism_energy_1a5a6cf74563/`
      - KPI-Reaggregation:
        - praktisch identisch schlecht zu `mechanism_core`
    - `mechanism_energy_intensive`
      - bleibt fuer `constant_evt24_only` der beste KPI-Pfad:
        - `shifted_r2 ~ 0.38`
        - `rebound_r2 ~ 0.55`
        - `peak_r2 ~ -4.62`
  - Einordnung:
    - breitere Hourly-Zielbloecke mit Temperatur-/Aktivitaetszielen verbessern die Figure-KPIs im aktuellen targetweisen XGB-Setup nicht
    - der verbleibende Hebel ist damit enger:
      - peak-spezifische Truth-/Zielbehandlung
      - weitere unabhängige `upper_only dur24 evt24`-Gruppen

- 2026-05-14: Drittes `dur24 upper_only`-Mechanism-Bundle aus dem verbliebenen Daily-Screen erzeugt und `evt24` erneut KPI-first retrainiert.
  - Neuer Screen:
    - `Optimization/run/results/Vienna/gold/daily_thermflex_screen_dur24_20260510_121921/`
  - Neues figure-nahes Bundle:
    - `Optimization/run/results/Vienna/gold/paper_mechanism_bundle_20260514_204413/`
  - Neue ausgewaehlte Tage:
    - `best_joint_savings: 2023-10-16`
    - `robust_savings: 2023-04-05`
    - `co2_tradeoff: 2023-10-08`
    - `late_season_near_neutral: 2023-04-12`
    - `cold_contrast: 2023-01-21` bleibt Wiederholung
  - Effekt auf `constant_evt24_upper_only` (`mechanism_energy_intensive`, `full`):
    - Datensatz:
      - `Learning/datasets/dea7aac98eb2f01c57ef05cf880d0da8108aa9c5aff03afc51223f5d13c23dae/`
    - Modell:
      - `Learning/models/thermflex_hourly_mechanism_xgb_mechanism_energy_intensive_dea7aac98eb2/`
    - KPI-Reaggregation:
      - `shifted_r2 ~ -0.28` (besser als der vorherige `~ -1.43`)
      - `rebound_r2 ~ -1.11`
      - `peak_r2 ~ -0.44`
      - `4` Holdout-Runs / `4` Holdout-Tage
    - `evt24_compact` bleibt schlechter:
      - Datensatz:
        - `Learning/datasets/e4e6cd3a2974e3d69dcddfee75502b96a6799f07cff61feff5a91408eb845311/`
      - Modell:
        - `Learning/models/thermflex_hourly_mechanism_xgb_mechanism_energy_intensive_e4e6cd3a2974/`
      - KPI-Reaggregation:
        - `shifted_r2 ~ -2.90`
        - `rebound_r2 ~ -0.85`
        - `peak_r2 ~ -0.48`
  - Effekt auf gemischtes `constant_evt24_only` (`mechanism_energy_intensive`, `full`):
    - Datensatz:
      - `Learning/datasets/406423ed87865e656c55333047a2c87e928ef5d3308f5eb753f55e2e17dceb82/`
    - Modell:
      - `Learning/models/thermflex_hourly_mechanism_xgb_mechanism_energy_intensive_406423ed8786/`
    - KPI-Reaggregation:
      - `shifted_r2 ~ -1.03`
      - `rebound_r2 ~ 0.46`
      - `peak_r2 ~ -0.09`
      - `6` Holdout-Runs / `6` Holdout-Tage
  - Schluss:
    - zusaetzliche `upper_only`-Figure-Tage helfen klar beim `shifted`-Signal des reinen Upper-only-Regimes
    - der gemischte `evt24`-Pfad verbessert `peak` deutlich, verliert aber an stabilem `shifted`
    - damit bleibt der Resthebel jetzt noch praeziser:
      - `upper_only dur24 evt24` braucht weitere unabhaengige Rebound-Faelle
      - `peak` im gemischten `evt24` ist fast neutralisiert und sollte separat konserviert statt mit weiteren Zielblöcken wieder verschlechtert werden

- 2026-05-14: Vorhandene `upper_only dur24 evt24`-Truthquellen repo-weit abgeglichen.
  - Geprueft:
    - direkte scenario-tagged Gold-Runs `*lb22p5_dur24_evt24_upper_only_proxy_paper_day_ahead*`
    - `paper_dispatch_comparison_*`
    - `dh_thermflex_run_*/paper_core/selected_runs.json`
    - bestehende `paper_mechanism_bundle_*`
  - Befund:
    - die `selected_runs.json`-Manifeste verweisen fuer `upper_only dur24 evt24` immer wieder auf denselben Basis-Run
      - `20260403_122504_vienna_ref2023_dh_baseline_constant_thermflex_lb22p5_dur24_evt24_upper_only_proxy_paper_day_ahead`
    - die bisher zusaetzlich erschlossenen unabhängigen Figure-Tage kommen damit tatsaechlich aus den drei `daily_thermflex_screen_dur24_*`-basierten mechanism bundles
    - es gibt aktuell **keinen weiteren versteckten `upper_only dur24 evt24`-Truthpool** im Repo, der nur noch hydriert werden muesste
  - Schluss:
    - fuer `upper_only dur24 evt24` ist der naechste Hebel nicht weiteres Einsammeln alter Artefakte
    - sondern entweder
      - gezielt neue unabhaengige Figure-Tage rechnen
      - oder auf den bereits staerkeren `lower_relax`- / gemischten `evt24`-Pfaden weiter verbessern

- 2026-05-14: Mechanism-Bundle-Builder fuer beliebige ThermFlex-Overrides geoefnet und exakte Paper-`lower_relax`-Bundles angeschlossen.
  - Code:
    - `Optimization/run/analysis/build_vienna_constant_thermflex_mechanism_bundle.py`
  - Neuer Builder-Vertrag:
    - explizites `flex_override`
    - explizites `output_prefix`
    - optionales `allow_partial_selection`
  - Neue figure-nahe Bundles:
    - `paper_mechanism_bundle_lower1k_dur4_evt24_20260514_210036`
      - basiert auf:
        - `daily_thermflex_screen_lb21p5_dur4_evt24_20260510_194946`
      - exakte Paper-1K-Relaxation
      - `5` selektierte Tage
    - `paper_mechanism_bundle_lower2k_dur4_evt24_20260514_210733`
      - basiert auf:
        - `daily_thermflex_screen_lb20p5_dur4_evt24_20260513_partial`
      - exakte Paper-2K-Relaxation
      - `4` selektierte Tage
      - bewusst mit `allow_partial_selection=true`, weil der Partial-Screen noch keinen eindeutigen `late_season_near_neutral`-Kandidaten enthaelt
  - Wirkung auf `constant_evt24_lower_relax_only` (`mechanism_energy_intensive`, `full`):
    - Datensatz:
      - `Learning/datasets/4335e9b1c5cd2354f7843ab12a7bd9884f647cd7cf5dea8181ffcddd0c93039d/`
    - Modell:
      - `Learning/models/thermflex_hourly_mechanism_xgb_mechanism_energy_intensive_4335e9b1c5cd/`
    - KPI-Reaggregation:
      - `shifted_r2 ~ 0.781`
      - `rebound_r2 ~ -7.06`
      - `peak_r2 ~ 0.855`
      - `4` Holdout-Runs / `4` Holdout-Tage
  - Wirkung auf gemischtes `constant_evt24_only`:
    - Datensatz:
      - `Learning/datasets/f8ac31dca29ba08b6a02619526e3e8ae740ac87c92d53a67ef754d00af4e5c97/`
    - Modell:
      - `Learning/models/thermflex_hourly_mechanism_xgb_mechanism_energy_intensive_f8ac31dca29b/`
    - KPI-Reaggregation:
      - `shifted_r2 ~ -1.16`
      - `rebound_r2 ~ -0.01`
      - `peak_r2 ~ 0.31`
      - `8` Holdout-Runs / `8` Holdout-Tage
  - Schluss:
    - die exakten Paper-`lower_relax`-Bundles helfen deutlich bei `peak`
    - `shifted` im reinen `lower_relax`-Slice bleibt gut
    - `rebound` ist jetzt der klar isolierte Restengpass
    - fuer den gemischten `evt24`-Pfad liefert der breitere lower-relax-Truth ein ehrlicheres, aber schwierigeres Gesamtbild

- 2026-05-14: Expliziten KPI-level-Rebound-Postprocessor fuer `constant_evt24_lower_relax_only` eingebaut.
  - Code:
    - `Learning/thermflex_hourly_mechanism/rebound_postprocessor.py`
    - `Learning/thermflex_hourly_mechanism/evaluate_kpi_reaggregation.py`
  - Motivation:
    - im besten `lower_relax`-Hourly-Pfad
      - `Learning/models/thermflex_hourly_mechanism_xgb_mechanism_energy_intensive_4335e9b1c5cd/`
      war `shifted` bereits gut und `peak` stark
    - der isolierte Fehler war `rebound`
    - Diagnose:
      - kleine fruehe negative Prediction-Noise aktivierte die Rebound-Logik auf echten Null-Tagen
  - Expliziter Sonderpfad:
    - Profil:
      - `lower_relax_evt24_conservative_v1`
    - negativer Trigger-Deadband:
      - `25,000 kWh`
    - positiver Akkumulations-Deadband:
      - `0 kWh`
    - anschliessend train-seitig fitte Multiplikativskalierung
      - persistiert als
        - `Learning/models/thermflex_hourly_mechanism_xgb_mechanism_energy_intensive_4335e9b1c5cd/rebound_postprocessor.json`
  - Neuer Holdout-Stand mit explizitem Postprocessor:
    - `shifted_r2 ~ 0.781`
    - `rebound_r2 ~ 0.324`
    - `peak_r2 ~ 0.855`
  - Gegenueber Basis:
    - Basis-`rebound_r2 ~ -7.06`
    - `shifted` und `peak` bleiben unveraendert
  - Zusatzartefakte:
    - `holdout_daily_reconstruction_rebound_postprocessed.csv`
    - `holdout_rebound_postprocessed_metrics.json`
  - Schluss:
    - fuer `lower_relax evt24` ist ein expliziter KPI-level-Rebound-Sonderpfad sinnvoller als weiteres Family-Splitting
    - der Mechanikpfad bleibt family-routed; kein stiller globaler KPI-Wechsel

- 2026-05-14: `upper_only dur24 evt24` auf denselben KPI-Sonderpfad-Hebel geprueft.
  - Geprueft:
    - explizite Rebound-Deadbands plus train-fitted Skalierung analog zum `lower_relax`-Sonderpfad
    - einfache KPI-level Skalierung fuer
      - `shifted`
      - `rebound`
      - `peak`
    - kleine tägliche Rebound-Mappings aus bereits vorhergesagten Hourly-Aggregaten
      - `rebound_pred_raw`
      - `shifted_pred`
      - `peak_pred`
      - Tageskontext
  - Befund:
    - `upper_only` zeigt **nicht** denselben Fehler wie `lower_relax`
    - dort ist `rebound` nicht primär ein Null-vs-Positiv-Triggerproblem
    - vielmehr sind die positiven Rebound-Tage selbst systematisch falsch skaliert, und der Holdout deckt zu wenig unterschiedliche Proxy-/Replay-Mechaniken ab
    - die getesteten kleinen Sonderpfade verbessern den Holdout nicht robust:
      - Deadband-/Scale-Varianten bleiben negativ
      - einfache KPI-Skalierung bleibt negativ
      - kleine tägliche Regressionsmappings aus den Hourly-Aggregaten bleiben negativ
  - Schluss:
    - fuer `upper_only dur24 evt24` gibt es aus dem aktuellen Truth **keinen gleichwertig sauberen konservativen KPI-Postprocessor**
    - der naechste reale Hebel dort ist eher:
      - neue unabhaengige Figure-Tage
      - oder breitere homogene `upper_only`-Truth
    - also kein weiterer stiller Postprocessing-Ausbau ohne neue Information

- 2026-05-14: Gemischten `constant_evt24_only`-Pfad KPI-first erneut geprueft.
  - Aktueller Pfad:
    - Datensatz:
      - `Learning/datasets/f8ac31dca29ba08b6a02619526e3e8ae740ac87c92d53a67ef754d00af4e5c97/`
    - Modell:
      - `Learning/models/thermflex_hourly_mechanism_xgb_mechanism_energy_intensive_f8ac31dca29b/`
  - Holdout:
    - `shifted_r2 ~ -1.16`
    - `rebound_r2 ~ -0.01`
    - `peak_r2 ~ 0.31`
    - `8` Holdout-Tage / `8` Holdout-Runs
  - Zusaetzlich geprueft:
    - globaler durch-den-Ursprung-Peak-Scaler
    - negatives Peak-Regime separat skaliert
  - Befund:
    - der gemischte Pfad bleibt der derzeit brauchbarste `peak`-Pfad im konstanten `evt24`
    - ein einfacher globaler Peak-Scaler verbessert `peak_r2` von `~ 0.31` auf `~ 0.42`
    - negativer Peak-Regime-Scaler liegt leicht hoeher bei `~ 0.44`
    - gleichzeitig bleiben `shifted` und `rebound` im gemischten Slice strukturell zu schwach
  - Schluss:
    - `constant_evt24_only` ist aktuell eher als expliziter `peak`-Figure-Pfad brauchbar
    - `shifted/rebound` sollten weiter family-routed ueber
      - `day_night`
      - `lower_relax`
      - `upper_only`
      behandelt werden

- 2026-05-14: Expliziten Peak-Postprocessor fuer gemischtes `constant_evt24_only` eingebaut.
  - Code:
    - `Learning/thermflex_hourly_mechanism/peak_postprocessor.py`
    - `Learning/thermflex_hourly_mechanism/evaluate_kpi_reaggregation.py`
  - Motivation:
    - der gemischte `evt24`-Slice bleibt zu heterogen fuer einen gemeinsamen `shifted/rebound`-Pfad
    - als breiter `peak`-Pfad ist er aber weiterhin nuetzlich
  - Expliziter Sonderpfad:
    - Profil:
      - `mixed_evt24_peak_negative_scale_v1`
    - negative Peak-Regime:
      - durch-den-Ursprung-Scale auf Train-Tagen
    - nichtnegative Peak-Regime:
      - Scale `1.0`
  - Artefakt:
    - `Learning/models/thermflex_hourly_mechanism_xgb_mechanism_energy_intensive_f8ac31dca29b/peak_postprocessor.json`
  - Neuer Holdout-Stand:
    - `shifted_r2 ~ -1.16`
    - `rebound_r2 ~ -0.01`
    - `peak_r2 ~ 0.44`
  - Gegenueber Basis:
    - Basis-`peak_r2 ~ 0.31`
    - `shifted` und `rebound` bleiben unveraendert
  - Schluss:
    - gemischtes `evt24` kann aktuell als expliziter `peak`-Figure-Pfad konserviert werden
    - fuer `shifted/rebound` bleibt family routing der saubere Weg

- 2026-05-15: Zentralen model-first Target-Vertrag im Learning-Layer geschärft.
  - Ziel:
    - die Surrogatstruktur nicht weiter implizit an Paper-Skripten ausrichten
    - stattdessen eine explizite SSOT für KPI-/Target-Ownership im Learning-Layer halten
  - Code:
    - `Learning/model_target_matrix.py`
  - Erweiterungen:
    - explizites Feld `preferred_postprocessor_profile`
    - strikte Lookup-Helfer:
      - `find_entries_by_target(...)`
      - `get_primary_entry_for_target(...)`
  - Dokumentation:
    - `Learning/README.md`
    - `Learning/thermflex_hourly_mechanism/README.md`
  - Schluss:
    - Daily-, system- und hourly-Pfade sind jetzt explizit als Modellpfade mit Zielgruppen dokumentiert
    - missing/ambiguous KPI ownership soll kuenftig fail-fast in der Matrix auffallen statt ueber implizite Modellnamen

- 2026-05-15: `tau` explizit in den Hourly-Mechanikvertrag gezogen.
  - Motivation:
    - `dh_bus_inertia_tau_h` ist fachlich ein direkter Rebound-Hebel
    - bisher war `tau` im Daily-Vertrag schon sichtbar, im Hourly-Vertrag aber noch nicht explizit
  - Code:
    - `Learning/thermflex_hourly_mechanism/schema.py`
    - `Learning/thermflex_hourly_mechanism/dataset_builder.py`
    - `Learning/thermflex_hourly_mechanism/README.md`
  - Umsetzung:
    - `policy_tau_h` als numerisches Hourly-Feature ergänzt
    - Run-Policy-Enrichment liest `dh_bus_inertia_tau_h` jetzt direkt aus `settings.dispatch`
    - fehlendes `tau` wird nicht still auf `0` gesetzt, sondern fail-fast als Fehler behandelt
    - `evt24_compact` enthält `policy_tau_h` ebenfalls explizit
  - Schluss:
    - der Hourly-Vertrag ist jetzt methodisch bereit fuer `tau`-Sensitivitäten
    - modellseitiger Nutzen kommt erst mit echter Truth-Variation über `tau=3/4/5/6/...`

- 2026-05-15: Minimalen `tau`-Truth-Erweiterungspfad fuer ThermFlex-Screens angelegt.
  - Ziel:
    - echte `tau`-Variation fuer Daily-/Hourly-Retraining nicht ad hoc per Hand erzeugen
    - sondern ueber denselben expliziten Override-/Screen-Workflow wie die bisherigen ThermFlex-Familien
  - Neue Skripte:
    - `Optimization/run/analysis/emit_tau_evt24_grid_overrides.py`
    - `Optimization/run/analysis/run_tau_evt24_heating_season_screen_bundle.py`
  - Schnitt:
    - Template-SSOT:
      - `vienna_ref2023_dh_baseline_constant_thermflex_lb21p5_dur4_evt24_paper_day_ahead.json`
    - Default-Tau-Grid:
      - `3 / 4 / 5 / 6 h`
    - Default-Use-Case:
      - `LOWER1K_DUR4_EVT24`, weil tractable und bereits Teil der aktiven lower-relax Lernfamilie
  - Verhalten:
    - Override-Emitter setzt explizit:
      - `dispatch.dh_bus_inertia_enabled = true`
      - `dispatch.dh_bus_inertia_tau_h = tau`
      - `dispatch.dh_bus_inertia_terminal_policy = free`
    - Screen-Runner fuehrt daraus direkt heating-season Gold screens aus
    - optional mit dem bestehenden Partial-Truth-Vertrag:
      - `--allow-incomplete-days`
      - `--day-solver-time-limit-s`
      - `--day-mip-rel-gap`
  - Schluss:
    - `tau` ist jetzt nicht nur als Feature vorhanden, sondern hat einen klaren Truth-Nachzugspfad

- 2026-05-15: Tau4-Hourly-Mechanikpfad KPI-seitig stabilisiert.
  - Ausgangspunkt:
    - die erweiterte tau4-Truthbasis umfasst jetzt `27` lower-relax `evt24` Tage
    - rein zufaellige gruppierte Holdouts waren fuer `shifted`/`rebound` instabil, weil Januar-Tage wenig KPI-Varianz tragen und Uebergangstage den eigentlichen Mechanismus liefern
  - Code:
    - `Learning/thermflex_hourly_mechanism/validate.py`
    - `Learning/thermflex_hourly_mechanism/train.py`
    - `Learning/thermflex_hourly_mechanism/shifted_postprocessor.py`
    - `Learning/model_target_matrix.py`
  - Umsetzung:
    - expliziten Splitmodus `group_stratified_shuffle` eingefuehrt
    - `stratify_column=month` als tau4-Bewertungsvertrag getestet
    - tau4-Modell `thermflex_hourly_mechanism_xgb_mechanism_energy_intensive_74d382eb0b73` mit stratifiziertem Split `random_state=1` neu trainiert
    - `shifted_postprocessor.json` als expliziten Daily-XGB-Korrektor neben dem Modell persistiert
  - KPI-Befund auf `7` holdout days / `7` holdout runs:
    - raw:
      - `shifted_r2 ~ -4.52`
      - `rebound_r2 ~ 0.984`
      - `peak_r2 ~ 0.593`
    - mit shifted postprocessor:
      - `shifted_r2 ~ 0.977`
      - `rebound_r2 ~ 0.984`
      - `peak_r2 ~ 0.593`
  - Wiederholte Diagnose:
    - Tool:
      - `Learning/thermflex_hourly_mechanism/evaluate_repeated_kpi_holdouts.py`
    - Artefakte:
      - `Learning/models/thermflex_hourly_mechanism_xgb_mechanism_energy_intensive_74d382eb0b73/diagnostics/repeated_kpi_holdout_summary.csv`
      - `Learning/models/thermflex_hourly_mechanism_xgb_mechanism_energy_intensive_74d382eb0b73/diagnostics/repeated_kpi_holdout_summary.json`
      - `Learning/models/thermflex_hourly_mechanism_xgb_mechanism_energy_intensive_74d382eb0b73/diagnostics/repeated_kpi_holdout_summary_shifted_state.csv`
      - `Learning/models/thermflex_hourly_mechanism_xgb_mechanism_energy_intensive_74d382eb0b73/diagnostics/repeated_kpi_holdout_summary_shifted_state.json`
    - 10-Seed-Median mit raw-feature shifted postprocessor:
      - `shifted_r2 ~ 0.573`
    - 10-Seed-Median mit state-feature shifted postprocessor:
      - `shifted_r2 ~ 0.986`
      - `rebound_r2 ~ 0.293`
      - `peak_r2 ~ 0.549`
  - Schluss:
    - fuer tau4 sind `shifted` und `rebound` jetzt KPI-seitig plausibel geloest
    - `shifted` ist mit dem state-feature Profil im Median ueber dem `0.95`-Ziel
    - `rebound` ist im besten Seed stark, aber ueber wiederholte Splits noch nicht robust bei `0.95`
    - der alte Rebound-Deadband-Postprocessor ist fuer diesen tau4-Kandidaten nicht sinnvoll, weil raw rebound besser ist
    - offener Resthebel ist `peak`, vor allem negative Peak-Reduktionstage, die die hourly q_delta-Form noch nicht sauber rekonstruiert

- 2026-05-15: Tau3 mit demselben KPI-first Diagnosepfad geprueft.
  - Datensatz:
    - `Learning/datasets/dbae0b2847c885ada4c4812ef3a97bdb4bd3b0e0a650b1926552c1ba64742003/`
  - Modell-/Diagnosepfad:
    - `Learning/models/thermflex_hourly_mechanism_xgb_mechanism_energy_intensive_dbae0b2847c8/`
    - `diagnostics/repeated_kpi_holdout_summary_tau3_state.csv`
    - `diagnostics/repeated_kpi_holdout_summary_tau3_state.json`
  - Befund:
    - tau3 hat aktuell nur `9` Tage:
      - `6` Januar
      - je `1` Maerz/April/Oktober
    - Month-stratified holdout ist damit nicht zulaessig
    - plain grouped repeated holdout bleibt instabil:
      - shifted-state median `~ -1.58`
      - rebound median `~ -0.316`
      - peak median `~ -0.944`
  - Schluss:
    - tau3 ist derzeit kein Modellierungshebel
    - vor weiterem tau3-Training braucht es mehr unabhaengige Uebergangstags-Truth

- 2026-05-15: Daily-/Hourly-Surrogate-Hebel fuer KPI-R2 >= 0.95 systematisch weiter eingegrenzt.
  - Daily-Vertrag:
    - neue hourly-shape Tagesfeatures aus der Vienna-SSOT ergaenzt:
      - Preis-Min/Peak-Stunden
      - DH- und Space-Heat-Peak-Stunden
      - Preis-/Last-Korrelationen
      - Preisfenster- und Top/Bottom-Preis-Lastanteile
    - neuer Datensatz:
      - `Learning/datasets/d28a5c5fec00cf439a51092fb8bbb20c9c593f0812d8dfd36efd9199bbee81c9/`
    - repeated grouped daily holdout bleibt unter Ziel:
      - `table_09_paper` XGB median:
        - shifted `~0.906`
        - rebound `~0.637`
        - boiler peak `~0.328`
        - CO2 pct `~0.394`
      - `robust_kpi_absolute` XGB median:
        - cost delta `~0.866`
        - CO2 delta `~0.444`
        - thermflex peak `~0.448`
    - getestete, aber verworfene Hebel:
      - signed-log Zieltransforms fuer Peak/Rebound
      - KNN-Daily-Ansatz
      - season-spezifische Daily-Modelle
      - gestapeltes Shift-zu-Rebound/Peak Daily-Modell
  - Daily-Screen-Export:
    - `screen_vienna_constant_thermflex_heating_season_days.py` schreibt fuer neue Laeufe zusaetzlich stabile Heat-Cost-/Dispatch-Komponenten mit REF/flex/delta/pct:
      - `dispatch_heat_operating_cost_eur`
      - `fuel_cost_eur`
      - `co2_cost_eur`
      - `variable_opex_eur`
      - `district_gas_*_co2_t`
      - zentrale DH-Quellen-Generationen
    - Ziel:
      - kuenftige Daily-Truth nicht mehr nur auf dem alten, near-zero-anfaelligen `dispatch_operating_cost_eur`-Prozentziel aufbauen.
  - Hourly-Mechanismus:
    - neues upper-only hardday Bundle:
      - `Optimization/run/results/Vienna/gold/paper_mechanism_bundle_upper_harddays_surrogate_20260515_202116/`
    - weitere `30` einzelne upper-only Mechanism-Truth-Bundles:
      - Prefix `paper_mechanism_bundle_upper_moretruth_surrogate_*`
    - Hourly-Dedup-Vertrag korrigiert:
      - Duplikate werden jetzt ueber `run_dir/cohort_key/timestamp` entfernt, nicht mehr ueber label-abhaengige Keys.
    - neuer upper-only Datensatz nach Dedup:
      - `Learning/datasets/a09c7563a1c77c07c2b5d7edb1fcafcc16598237e6e573dfbac50971f2341163/`
      - `10176` rows
      - `53` runs
      - `40` bundles
    - KPI-Reaggregation bleibt deutlich unter Ziel:
      - shifted `~ -3.49`
      - rebound `~ -1.09`
      - peak `~0.46`
    - Schluss:
      - blosse upper-only Truth-Verbreiterung verbessert die aktuelle hourly-XGB-Reaggregation nicht genug.
      - der naechste Hebel muss den Mechanismus-/State-Vertrag selbst verbessern oder die Daily-Paper-KPIs gezielt ueber stabilere Dispatch-Komponenten routen.

- 2026-05-15: Daily Temperature-State Feature Block umgesetzt und gegen XGB/ExtraTrees verglichen.
  - Code:
    - `Learning/thermflex_daily_results/schema.py`
    - `Learning/thermflex_daily_results/dataset_builder.py`
  - Neue Features:
    - 3d/7d Temperatur- und HDD-Gedaechtnis
    - Intraday-Temperaturfenster und HDD-Fenster
    - Temperatur-Min/Max-Stunden
    - Temperatur an Preis-Min/Max sowie DH-/Space-Heat-Peakstunden
    - Temperatur-Ramps
  - Neuer Datensatz:
    - `Learning/datasets/829800a144e7268b2e3a1cef4874774e521e39428c30de1087ae1b20c67e21d4/`
    - `913` rows
    - `127` features
  - Repeated grouped holdout, `5` seeds:
    - `table_09_paper`, XGB:
      - cost pct median `~0.504`
      - CO2 pct median `~0.465`
      - boiler generation median `~0.874`
      - boiler peak median `~0.325`
      - shifted median `~0.912`
      - rebound median `~0.630`
    - `table_09_paper`, ExtraTrees smooth:
      - cost pct median `~0.089`
      - CO2 pct median `~0.584`
      - boiler generation median `~0.893`
      - boiler peak median `~0.530`
      - shifted median `~0.933`
      - rebound median `~0.668`
    - `robust_kpi_absolute`, ExtraTrees smooth:
      - CO2 delta median `~0.421`
      - DH peak median `~0.536`
      - boiler generation median `~0.893`
      - boiler peak median `~0.530`
      - thermflex peak median `~0.540`
  - Schluss:
    - Temperature-State hilft, vor allem in Kombination mit ExtraTrees.
    - Es reicht allein nicht fuer `R2 >= 0.95`.
    - Naechster Modellierungshebel ist target-spezifisches Routing:
      - Cost weiter mit XGB/stabilem Dispatch-Komponentenprofil
      - CO2/boiler peak/shifted/rebound/thermflex peak eher ExtraTrees
      - danach Regime-/Mechanismuspfad fuer Rebound und Peak.

- 2026-05-15: Rolling-Horizon- und EnergyPlus-Feature-Hebel fuer Surrogate vor dem Overnight-Lauf geprueft.
  - Hourly `full_thermal` Feature-Mode mit EnergyPlus-/Archetype-Parametern getestet:
    - tau4 lower-relax, 10-seed KPI-Reaggregation mit Shifted-State-Postprocessor:
      - shifted median `~0.986`
      - rebound median `~0.357`
      - peak median `~0.570`
    - upper-only:
      - shifted median `~0.235`
      - rebound median `~-0.983`
      - peak median `~0.257`
    - Schluss: EnergyPlus-Parameter sind leicht hilfreich, aber nicht der Haupthebel.
  - MILP-Solve-State in den Learning-Vertrag aufgenommen:
    - `policy_dispatch_horizon_h`
    - `policy_dispatch_rolling_commit_h`
    - `policy_dispatch_lookahead_h`
    - `policy_dispatch_is_rolling`
    - betrifft Daily und Hourly Learning-Builder; Daily-Dedup-Key trennt kuenftig 24/24 und 36/24.
  - Paper-Figure-Artefakte im zentralen Inventory klassifiziert:
    - `thermflex_paper_figure_truth`: `87` CSV-Artefakte, `11640` Zeilen
    - `thermflex_paper_figure_metadata`: `116` JSON-Metadaten
    - eigene Compatibility-Familie `thermflex_paper_figure_rolling_v1`, nicht still mit `thermflex_daily_results_v1` mischbar.
  - Schluss:
    - aktuelle normale Daily-Screens sind ueberwiegend 24/24 ohne Lookahead.
    - Figure-Caches nutzen 36h Horizon, 24h Commit, Warmup und Tau.
    - fuer Figures/Appendix sollte der naechste Truth-Lauf gezielt den Rolling-Horizon-Vertrag nachbilden oder zumindest separat als eigene Learning-Familie laufen.

- 2026-05-16: Overnight-Truth fuer tau3/tau4 Daily-Screens gesammelt und ausgewertet.
  - Laufvertrag:
    - `LOWER1K_DUR4_EVT24_TAU3H`
    - `LOWER1K_DUR4_EVT24_TAU4H`
    - per-day HiGHS time limit `600 s`
    - relative MIP gap `0.01`
    - incomplete days erlaubt, damit harte Tage nicht blockieren.
  - Ergebnisse:
    - tau3:
      - `212` Heiztage total
      - `193` solved
      - `19` failed
    - tau4:
      - `212` Heiztage total
      - `197` solved
      - `15` failed
  - Neuer Daily-Datensatz:
    - `Learning/datasets/22f11adcc5375d18f3cffe41a5973a5566f290a7a55ec1cd1d9890549b16a9a1/`
    - `1515` selected rows
    - `9` selected bundles
    - `131` numeric features
  - Repeated day/month holdout, 10 seeds, hybrid `xgb_cost_extra_trees_smooth_rest`:
    - `table_09_paper`:
      - shifted median `~0.931`
      - rebound median `~0.706`
      - boiler generation median `~0.871`
      - boiler peak median `~0.485`
      - CO2 pct median `~0.401`
      - cost pct median `~0.140`
    - `robust_kpi_absolute`:
      - DH peak median `~0.749`
      - cost delta median `~0.644` but unstable
      - CO2 delta median `~0.440`
      - boiler generation median `~0.871`
      - boiler peak median `~0.485`
      - thermflex peak median `~0.484`
  - Zusatzdiagnose:
    - die neuen v3 Dispatch-Komponenten sind nur fuer `344` Overnight-Zeilen verfuegbar.
    - isolierter Komponenten-Holdout hebt Kosten/CO2 nicht ausreichend.
  - Schluss:
    - mehr tau3/tau4 Truth verbessert Rebound und Peak, aber nicht Richtung `R2 >= 0.95`.
    - Haupthebel bleibt ein Rolling-Horizon-/Figure-KPI-spezifischer Truthvertrag sowie Regime-Routing fuer Dispatch-Source-Switches.

- 2026-05-16: Dispatch-Kosten-/CO2-Pfad fuer Daily-Surrogate geprueft.
  - Peak-Boiler-Oel ist in `Data/economic_data/location/vienna.py` bereits enthalten:
    - aktiver Vienna-v2-Proxy `gas_plus_heating_oil_extra_light_proxy`
    - `50 %` Gas / `50 %` Heizoel extra leicht auf Fuel-Energy-Basis
    - resultierender Peak-Boiler-Faktor `0.235 tCO2/MWh_fuel`
  - Gas-CHP nutzt weiterhin den reinen Gasfaktor `0.202 tCO2/MWh_fuel`.
  - ETS-CO2-Preis wird ueber `dispatch.historical_co2_price_csv` als `co2_price_eur_per_tco2` in die MILP gegeben und in den Dispatch-Zieltermen mit CHP-/Boiler-CO2 multipliziert.
  - Der aktive Paper-Day-Ahead-Vertrag nutzt `gas_chp_electric_value`, `fuel_cost`, `co2_cost`, `variable_opex`; `dispatch_operating_cost_eur` kann dadurch wegen abgezogenem CHP-Stromwert nahe null oder negativ werden.
  - Vertragsluecke geschlossen: `district_gas_chp.co2_t_per_mwh_fuel` wird nun wie der Boiler-CO2-Faktor fail-fast aus den Economics gelesen statt still auf `0.0` zu fallen.
  - Schluss fuer Surrogate:
    - Tages-/Kurzfenster-Kosten besser als absolute oder heat-allocated Kosten-/CO2-KPIs trainieren.
    - Pct-Kosten auf net operating cost nur als abgeleitete Reporting-Groesse verwenden, nicht als robuster Primaertarget.

- 2026-05-16: Heat-Cost-/CO2-Targetvertrag fuer Daily/Window-Surrogate umgesetzt und diagnostiziert.
  - Neuer Dispatch-Economics-Datensatz:
    - `Learning/datasets/ce7866fce50ab7e7c637818285dcc5ce640fdad103dc166f22a86a49cdef08e3/`
    - `344` Zeilen aus tau3/tau4 lower-relax v3-Truth
    - `157` Features, `29` Targets
    - `dispatch_heat_allocated_co2_t_*` ist in alten Truth-Artefakten noch nicht enthalten und bleibt daher als NaN sichtbar.
  - Neue Targetprofile:
    - `heat_cost_total_co2_absolute`
    - `heat_cost_allocated_co2_absolute`
    - `dispatch_source_co2`
    - `dispatch_cost_components`
    - `dispatch_source_generation`
  - Window-Diagnose unterstuetzt nun `--target-scale heat_absolute` und `heat_allocated_absolute`.
  - Ergebnis mit bestehender v3-Truth:
    - Heat-Cost-Delta ist mit XGB schlecht und mit ExtraTrees nur stabiler, aber weiterhin weit unter Ziel.
    - 3-Tage-Window ExtraTrees: Heat-Cost median `~0.15`, CO2 median `~0.26`.
    - Kostenkomponenten zeigen, dass Heat-Cost fast vollstaendig von Fuel-/CO2-Kosten und damit von Gas-CHP-Generation getrieben ist.
    - Source-Generation-Diagnose:
      - External heat und waste incineration sind sehr gut lernbar (`R2` median ca. `0.99`).
      - Boiler generation liegt nur mittel (`R2` median ca. `0.53`).
      - Gas-CHP thermal generation ist nicht lernbar (`R2` median negativ).
  - Smoke-Run fuer neuen Exportvertrag:
    - `Optimization/run/results/Vienna/gold/daily_thermflex_screen_smoke_heat_contract_20260516_103645/`
    - Export enthaelt jetzt `dispatch_heat_allocated_co2_t_*` und `district_thermal_storage_*` REF/flex/delta-Felder.
  - Schluss:
    - Kosten/CO2-R2 ist aktuell kein reines Target-Scaling-Problem.
    - Haupthebel ist Gas-CHP-/Storage-Dispatch-Regime; der naechste Truth-Lauf muss diese Felder exportieren und mehr CHP-Switching-Tage abdecken.

- 2026-05-16: Flow-basierte Kosten-/CO2-Rekonstruktion fuer Daily-Surrogate isoliert.
  - Neuer wiederverwendbarer Diagnostic:
    - `Learning/thermflex_daily_results/evaluate_flow_reconstruction.py`
    - Ergebnisordner:
      - `Learning/models/thermflex_daily_results_flow_reconstruction_bf116_regime_chp_ets5/`
  - Befund:
    - Heat-Cost-Delta ist exakt die Summe aus Fuel-, CO2-, Variable-OPEX- und Startup-Kostendelta.
    - Mit echten Source-Flows laesst sich CO2 exakt und Heat-Cost mit `R2` ca. `0.93` rekonstruieren.
    - Mit direkt gelernten Source-Flows bleibt Kosten/CO2 negativ.
    - Zweistufiges CHP-Regime-Modell hebt die rekonstruierte Daily-Qualitaet auf ca. `R2 0.50`.
    - Oracle-Regime fuer CHP zeigt ca. `R2 0.68-0.70`; der naechste Hebel ist daher bessere CHP-Regime-Erkennung und Regression innerhalb dieser Regime.
  - Entscheidung:
    - Storage wird aktuell nicht priorisiert.
    - Kosten/CO2 sollen primaer aus gelernten CHP-/Boiler-/Source-Flows rekonstruiert werden, nicht als Net-Cost-Blackbox.

- 2026-05-16: CHP-Regime- und Family-Luecken fuer Kosten/CO2-R2 > 0.9 konkretisiert.
  - Regimevergleich:
    - 3 Klassen (`down/neutral/up`) verbessert reconstructed Kosten/CO2 deutlich gegenueber direkter Flow-Regression.
    - 5 Klassen (`strong_down/down/neutral/up/strong_up`) ist besser:
      - predicted Regime-Rekonstruktion ca. `R2 0.58-0.65`
      - Oracle-Regime-Rekonstruktion ca. `R2 0.73-0.80`
    - reine Sign-Klassen sind schlechter.
  - Komponentencheck:
    - direkte Targets `fuel_cost_eur_delta`, `co2_cost_eur_delta`, `district_gas_chp_co2_t_delta` bleiben schwach/negativ.
    - Der Hebel bleibt daher CHP-Flow/Regime, nicht reine Kostenkomponenten-Regression.
  - Family-Luecke:
    - aktueller fokussierter Datensatz ist fast nur `LOWER1K_DUR4_EVT24`.
    - tau5-8 enthalten fast nur `strong_up` und kaum `down/neutral/strong_down`.
    - duration/lower-relax Families ausserhalb `LOWER1K_DUR4` sind fuer CHP-Regime-Lernen zu duenn.

- 2026-05-16: Hourly-Dispatch-Flow-Layer fuer ThermFlex-Surrogate aufgebaut und geprueft.
  - Neuer Exportvertrag:
    - Screen-Runner unterstuetzt `--write-hourly-dispatch`.
    - Pro Tag werden REF/FLEX/delta-Stundenwerte fuer CHP, Boiler, Fuel-Input, CO2, Kostenkomponenten, DH-Load und Preise/States in `heating_season_hourly_dispatch.csv` geschrieben.
    - Smoke-Summen stimmen fuer CHP/Boiler/Kosten/CO2 exakt mit Daily-Truth zusammen.
  - Neuer Learning-Layer:
    - `Learning/thermflex_hourly_dispatch/`
    - zentrale Registrierung ueber `Learning/datasets/`
    - Duplikate werden auf `flex_override_name + date + hour_index` dedupliziert; widerspruechliche Duplikate schlagen fail-fast fehl.
  - Truth-Ausbau:
    - tau3/tau4 `LOWER1K_DUR4_EVT24` fuer CHP-down, neutral/up und strong-up Kandidaten erzeugt.
    - aktueller kuratierter Hourly-Dispatch-Datensatz:
      - `Learning/datasets/c7185aee9b798489dcbd105f10b8032274487c6afa6ecebe9fd336e3da8f0e4b/`
      - `936` Stunden aus `39` Policy-Days und `20` Dates.
  - Befund:
    - Policy + REF-Dispatch + Wetter/Preis-State reicht nicht; Hourly-Kosten/CO2 bleiben klar unter Ziel.
    - Mit stündlichem `dh_bus_load_kwh_delta` als upstream Feature springt die Qualitaet deutlich:
      - Hourly Heat-Cost median ca. `0.95`
      - Hourly CO2 median ca. `0.95`
      - Daily CO2 median ca. `0.96`
      - Daily Heat-Cost median ca. `0.93-0.94`
    - Schluss:
      - Dispatch-Surrogate soll aus vorhergesagter ThermFlex-Load-Verschiebung lernen.
      - Naechster Hebel fuer Daily-Cost `>=0.95` ist Boiler/Fuel/Electric-Value-Fehler, nicht mehr CHP/CO2 allein.

- 2026-05-16: 14h-Truthlauf fuer Hourly-Dispatch-Family-Breite ausgefuehrt und ausgewertet.
  - Batch-Runner:
    - `Optimization/run/analysis/run_thermflex_hourly_dispatch_truth_batch.py`
    - priorisiert tau5/6, tau7/8-Anker, `dur8`, `lower2K` und `upper_only`.
    - nutzt `1 %` Gap, `300 s` Tageslimit, `allow-incomplete-days` und `--write-hourly-dispatch`.
  - Zusaetzliche gezielte Nachlaeufe:
    - `LOWER2K_DUR4` Winter- und positive-Shoulder-Faelle.
    - `LOWER1K_DUR8`, `LOWER2K_DUR8`, tau5-8 Winter-/Shoulder-Faelle.
    - `UPPER_ONLY` Winter-/Boiler-Extreme.
  - Aktueller kuratierter Datensatz:
    - `Learning/datasets/589eab46c9f1e6a631252a7c837de483beccb4cda756d9b1fb818b2d70e3be10/`
    - `5160` eindeutige Stunden aus `36` Source-Bundles.
  - Globaler Date-Holdout, ExtraTrees, 10 Seeds:
    - Daily `dispatch_heat_operating_cost_eur_delta`: median `R2 ~= 0.959`
    - Daily `co2_emissions_total_t_delta`: median `R2 ~= 0.986`
    - Hourly `dispatch_heat_operating_cost_eur_delta`: median `R2 ~= 0.920`
    - Hourly `co2_emissions_total_t_delta`: median `R2 ~= 0.960`
  - Global-train / Family-test:
    - Daily CO2 ist in allen betrachteten Families median `R2 >= 0.955`.
    - Daily Heat-Cost ist deutlich besser, aber noch nicht in jeder Family `>=0.95`:
      - unter Ziel u.a. `LOWER2K_DUR4`, `UPPER_ONLY`, tau7/8 und tau3/5/6 mit median ca. `0.935-0.947`.
      - `LOWER1K_DUR8`, `LOWER2K_DUR8`, `LOWER1K_DUR4_TAU4/5` liegen um oder ueber `0.95`.
  - Schluss:
    - Das globale Daily-Ziel ist erreicht.
    - Fuer die Aussage "alle Use-Cases Daily Heat-Cost >= 0.95" braucht es noch entweder family-spezifisches Routing/Modelle oder weitere gezielte Cost-/Electric-Value-Regime-Truth.

- 2026-05-17: Breiter Sensitivitaets-Truthlauf fuer ThermFlex-Hourly-Dispatch abgeschlossen.
  - TODO ergaenzt:
    - Two-stage-MILP als methodischer Preis-/Unsicherheitsblock klaeren.
    - surrogatbasierte Sensitivitaetsanalyse fuer Main-/Weather-/Economic-Bloecke festziehen.
  - Neue explizite Tau-Overrides:
    - `tau2h`
    - `tau12h`
  - Batch:
    - `Optimization/run/results/Vienna/gold/thermflex_hourly_dispatch_truth_batch_20260517_012657/`
    - Start bei den neuen Sensitivitaets-Tasks, real ca. `5.6 h` Laufzeit, `46/46` Tasks `ok`.
    - Abdeckung erweitert um `tau = 2/4/8/12`, `dur1`, `dur12`, `lower1K`, `lower2K`, `upper_only` und Winter-/Shoulder-/Autumn-/Dezember-Regime.
  - Neuer kuratierter Datensatz:
    - `Learning/datasets/fe23b4c1322061eb3f4d7f54084e840c7830bf784aad1453fcb9ce0fd9cecd49/`
    - `11256` ausgewaehlte Stunden aus `83` Source-Bundles.
  - Globaler Date-Holdout, ExtraTrees, 10 Seeds:
    - Daily Heat-Cost median `R2 ~= 0.962`
    - Daily CO2 median `R2 ~= 0.990`
    - Hourly Heat-Cost median `R2 ~= 0.938`
    - Hourly CO2 median `R2 ~= 0.964`
  - Family-Slices:
    - `UPPER_ONLY_DUR24`, `LOWER2K_DUR4`, `LOWER1K_DUR8/12`, `LOWER2K_DUR12`, tau3/4 erreichen Daily Heat-Cost grob `>=0.95`.
    - Neue `dur1`-Families bleiben schlecht fuer Daily Cost/CO2/CHP-Value; family-spezifisches Routing hat das nicht geloest.
    - Interpretation: sehr kurze Events erzeugen kleine/unstabile Tagesdeltas; fuer `dur1` braucht es entweder andere Metriksemantik, mehr gezielte Regime-Truth oder ein komponenten-/regimebasiertes Spezialmodell statt weiterer blinder Truth.

- 2026-05-17: Mechanism-/Load-Bridge, Family-Router und Peak/Rolling-Diagnostics fuer ThermFlex-Surrogate ergaenzt.
  - Neue Diagnose-Skripte:
    - `Learning/thermflex_hourly_dispatch/evaluate_load_bridge_end_to_end.py`
    - `Learning/thermflex_hourly_dispatch/evaluate_family_router.py`
    - `Learning/thermflex_hourly_dispatch/evaluate_peak_rolling_holdouts.py`
  - Ergebnis-Artefakte:
    - `Learning/models/thermflex_hourly_dispatch_load_bridge_fe23b4c13220_3seed/`
    - `Learning/models/thermflex_hourly_dispatch_family_router_fe23b4c13220_3seed/`
    - `Learning/models/thermflex_hourly_dispatch_peak_rolling_fe23b4c13220_3seed/`
  - Befund:
    - Dispatch mit Oracle-ThermFlex-Load ist global Daily stark: Heat-Cost ca. `R2 0.964`, CO2 ca. `R2 0.990`.
    - End-to-end mit vorhergesagtem Load bricht deutlich ein: Daily Heat-Cost ca. `R2 0.64`, CO2 ca. `R2 0.58`.
    - Family-Router verbessert Oracle-Dispatch nur leicht; er loest den End-to-end-Engpass nicht.
    - Daily Peak-Change ist global gut fuer Boiler/CHP, aber family-spezifisches R2 ist bei kleinen/nahe konstanten Peak-Deltas teilweise ungeeignet.
    - 7-Tage-Rolling-Metriken konnten mit der aktuellen sparse Daily-Truth nicht validiert werden, weil keine vollstaendig zusammenhaengenden Wochenfenster vorliegen.
  - Schluss:
    - Naechster Haupthebel ist der Mechanism-/Load-Surrogate, nicht weiteres Dispatch-Routing.
    - Fuer Weekly/Figure-15-artige Zeitraeume braucht es gezielte kontinuierliche Fenster-Truth statt nur isolierter Einzeltage.

- 2026-05-17: Mechanism-/Load-Surrogate-Slice-Diagnose ergaenzt.
  - Neuer Evaluator:
    - `Learning/thermflex_hourly_mechanism/evaluate_slice_holdouts.py`
    - repeated grouped holdouts, hourly target metrics und Daily-KPI-Reaggregation nach Policy-/Tau-/Duration-/Weather-/Cohort-Slices.
  - Diagnose-Artefakte:
    - `Learning/models/thermflex_hourly_mechanism_slice_holdouts_0915a417155e_upper_full_thermal_3seed/`
    - `Learning/models/thermflex_hourly_mechanism_slice_holdouts_ae928c1ff303_lower_tau4_full_thermal_3seed/`
    - `Learning/models/thermflex_hourly_mechanism_slice_holdouts_cc7f239d84f8_lower_relax_full_3seed/`
  - Befund:
    - Upper-only bleibt roh schwach: Daily `q_delta` ca. `R2 0.36`, shifted/rebound klar negativ, peak ca. `R2 0.25`.
    - Lower-relax tau4 roh lernt Hourly-`q_delta` moderat (`R2 ~0.54-0.59`) und Daily-`q_delta` gut (`R2 ~0.82`), aber shifted/rebound/peak sind ohne explizite KPI-Korrektur nicht robust.
    - Breiter lower-relax roh: Daily peak gut (`R2 ~0.96`), Daily `q_delta` moderat (`R2 ~0.76`), shifted nur ca. `R2 ~0.60`, rebound negativ.
  - Schluss:
    - Die echte End-to-end-Luecke liegt in der Uebersetzung von hourly load-shape zu Daily shifted/rebound, nicht allein im Dispatch.
    - Fuer tau4 lower-relax existiert bereits ein starker shifted-Spezialpfad mit explizitem state-basiertem Postprocessor; upper-only und breite tau/duration Families brauchen noch einen family-aware KPI-/Load-Pfad.

- 2026-05-17: Direct-Daily-Mechanism-KPI-Diagnose fuer Tabellen-KPIs ergaenzt.
  - Neuer Evaluator:
    - `Learning/thermflex_hourly_mechanism/evaluate_daily_kpi_direct_holdouts.py`
    - lernt Tages-KPIs direkt aus Policy-, Wetter-, Preis-, Referenzlast- und Kohortenfeatures.
    - unterstuetzt `extra_trees`, `xgb`, grouped/stratified grouped splits und einen expliziten Rebound-Aktivierungsgate.
  - Wichtigste Artefakte:
    - `Learning/models/thermflex_hourly_mechanism_daily_direct_0915a417155e_extra_trees_upper_full_thermal_5seed_strat_weather/`
    - `Learning/models/thermflex_hourly_mechanism_daily_direct_cc7f239d84f8_extra_trees_lower_relax_full_5seed_strat_weather/`
    - `Learning/models/thermflex_hourly_mechanism_daily_direct_cc7f239d84f8_extra_trees_lower_relax_full_5seed_rebound_gate25k/`
  - Befund:
    - `upper_only`: Direct-Daily verbessert `q_delta` deutlich (`R2 ~0.88`), aber `shifted` bleibt ca. `0.49`, `peak` ca. `0.26`, `rebound` negativ.
    - breites `lower_relax`: Direct-Daily erreicht median grob `shifted R2 ~0.96`, `peak R2 ~1.00`, `q_delta R2 ~0.90`, aber `rebound` bleibt negativ.
    - `xgb` war in diesen kleinen Daily-Sets schwächer als ExtraTrees.
    - Rebound-Gate reduziert False Positives in lower-relax, reicht aber noch nicht robust fuer `R2 >= 0.95`.
  - Schluss:
    - Fuer Daily-Tabellen ist ein family-aware Direct-Daily-KPI-Layer sinnvoll.
    - `lower_relax` kann damit fuer shifted/peak weitgehend abgedeckt werden; `upper_only` und `rebound` bleiben die gezielten Truth-/Modellluecken.

- 2026-05-17: Direct-Daily-Mechanism-KPI-Diagnose um Two-Stage-Rebound und 24h-Profile erweitert.
  - `evaluate_daily_kpi_direct_holdouts.py` kann Rebound nun optional als explizite Aktivierung plus Regression auf aktiven Tagen trainieren.
  - Zusaetzlich getestet wurden 24h-Profilfeatures fuer Referenzlast, Aussentemperatur, DH-Last, Strompreis, Irradiance und Solargains.
  - Wichtigste neue Artefakte:
    - `Learning/models/thermflex_hourly_mechanism_daily_direct_0915a417155e_extra_trees_upper_full_thermal_5seed_strat_weather_rebound_twostage25k/`
    - `Learning/models/thermflex_hourly_mechanism_daily_direct_0915a417155e_extra_trees_upper_full_thermal_5seed_strat_weather_profile_rebound_twostage25k/`
    - `Learning/models/thermflex_hourly_mechanism_daily_direct_cc7f239d84f8_extra_trees_lower_relax_full_5seed_strat_weather_rebound_twostage25k/`
    - `Learning/models/thermflex_hourly_mechanism_daily_direct_cc7f239d84f8_extra_trees_lower_relax_full_5seed_strat_weather_profile_rebound_twostage25k/`
  - Befund:
    - `upper_only`: 24h-Profile und Two-Stage-Rebound verbessern `shifted`/`rebound` etwas, bleiben aber weit unter dem Ziel (`shifted` grob `R2 ~0.55`, `rebound` grob `R2 ~0.12`, `peak` grob `R2 ~0.32`).
    - `lower_relax`: der nicht-profile weather-stratified Direct-Daily-Pfad bleibt besser fuer `shifted`/`peak` (`shifted` grob `R2 ~0.96`, `peak` grob `R2 ~1.00`); Rebound bleibt nicht robust.
    - Rebound ist wegen der Sequenzdefinition nicht ausreichend durch Tagesaggregate oder einfache 24h-Profilfeatures abgedeckt.
  - Schluss:
    - Naechster Hebel ist nicht noch ein generischer Featureblock, sondern gezielte Truth fuer rebound-aktive und upper-only Tagesformen sowie ein family-/state-aware Mechanism-KPI-Pfad.

- 2026-05-17: Gezielt `upper_only dur24 evt24` Truth nachgeschossen und in Learning registriert.
  - Neuer fokussierter Daily-/Hourly-Dispatch-Run:
    - `Optimization/run/results/Vienna/gold/daily_thermflex_screen_targeted_upper_only_dur24_rebound_truth_20260517_121515/`
    - `24` ausgewaehlte Winter-/Shoulder-/Dezember-Tage, `23` geloest, `2023-12-24` wegen Zeitlimit sauber uebersprungen.
    - Enthaelt starke Rebound-Tage, Null-Rebound-Gegenfaelle und Kosten-/CO2-Vorzeichenwechsel.
  - Neuer Mechanism-/Cohort-Bundle:
    - `Optimization/run/results/Vienna/gold/paper_mechanism_bundle_upper_targeted_truth_20260517_123511/`
    - `23` geloeste Tage als `thermflex_cohort_utilization_hourly.csv` exportiert.
  - Neue kuratierte Learning-Datensaetze:
    - Mechanism upper-only: `Learning/datasets/feda5c8c41fbd37a332390adab2c192d811114db89640c3552ed55b6552e6f44/`
      - `14208` selektierte Zeilen aus `40` Bundles.
    - Hourly dispatch: `Learning/datasets/ceabeed8fe641869813f9772ef24b80a9edc66a2d1dba2b794aea41204f5825b/`
      - `11784` selektierte Stunden aus `84` Bundles.
  - Diagnose:
    - Direct-Daily upper-only auf dem erweiterten Mechanism-Datensatz:
      - month-stratified: `q_delta` median `R2 ~0.94`, aber `shifted ~0.21`, `rebound ~-0.02`, `peak ~0.37`.
      - group-shuffle: `q_delta` median `R2 ~0.87`, `shifted ~0.29`, `rebound ~0.03`, `peak ~0.25`.
    - Dispatch mit Oracle-Load auf dem erweiterten Dispatch-Datensatz:
      - global Daily CO2 median `R2 ~0.985`, Heat-Cost median `R2 ~0.94`.
      - `UPPER_ONLY_DUR24_EVT24_DEFAULTTAU` Daily CO2 bleibt hoch; Heat-Cost liegt seed-abhaengig grob um `0.90-0.94`.
      - neue `UPPER_ONLY_DUR24_EVT24_TARGETED`-Family erreicht in zwei Seeds gute Cost/CO2-Werte, ein Seed bleibt schwach bei Cost/CO2 wegen Electric-Value/Fuel-Regime.
  - Schluss:
    - Mehr Upper-only Truth verbessert die Abdeckung und macht den Holdout ehrlicher, loest aber `shifted/rebound/peak` im Mechanism-KPI-Layer nicht.
    - Naechster Upper-only-Hebel ist ein expliziter state-/sequence-aware Mechanism-Pfad statt weiterer generischer Direct-Daily-Regression.

- 2026-05-17: Weitere Upper-only-Artefakte verwertet und Daily-Feature-Presets festgezogen.
  - Neue Upper-only-Mechanism-Truth:
    - `Optimization/run/results/Vienna/gold/daily_thermflex_screen_targeted_upper_only_dur24_dense_truth2_20260517_141418/`
      - `30/30` Tage geloest und als Mechanism-Bundle exportiert:
      - `Optimization/run/results/Vienna/gold/paper_mechanism_bundle_upper_dense_truth2_20260517_143106/`
    - Zusaetzlich wurden `33` bereits geloeste Upper-only-dur24 Screen-Tage aus vorhandenen `overnight`-/`overnight2`-Artefakten als Mechanism-Bundles wiederverwertet:
      - `paper_mechanism_bundle_upper_screen_reuse_20260517_152245/`
      - `paper_mechanism_bundle_upper_screen_reuse_20260517_152658/`
      - `paper_mechanism_bundle_upper_screen_reuse_20260517_152914/`
      - `paper_mechanism_bundle_upper_screen_reuse_20260517_153112/`
      - `paper_mechanism_bundle_upper_screen_reuse_20260517_153206/`
      - `paper_mechanism_bundle_upper_screen_reuse_20260517_153449/`
      - `paper_mechanism_bundle_upper_screen_reuse_20260517_153543/`
      - `paper_mechanism_bundle_upper_screen_reuse_20260517_153622/`
      - `paper_mechanism_bundle_upper_screen_reuse_20260517_153803/`
  - Neue kuratierte Learning-Datensaetze:
    - nach Dense2: `Learning/datasets/98f56fdf466914303017f4ec9adbf4eeae9e940cf913c1f2eff8f735edeebd68/`
      - `19968` Upper-only-Zeilen, `41` Bundles, `104` Daily-Rows.
    - nach Screen-Reuse: `Learning/datasets/6d058845d59b20453e43f83a1aec191c008683dee567ce9644a90d92d228a7fc/`
      - `26304` Upper-only-Zeilen, `50` Bundles, `137` Daily-Rows.
  - Code:
    - `Learning/thermflex_hourly_mechanism/evaluate_daily_kpi_direct_holdouts.py`
      - ergaenzt Archetype-Response-Aggregate fuer Daily-KPI-Features.
      - ergaenzt explizite Feature-Presets: `all`, `no_hourly_grid`, `tiny_state` und opt-in `*_prior_state`.
      - Vortags-/Mehrtags-State-Features bleiben opt-in, weil sie in den Upper-only-Holdouts nicht geholfen haben.
  - Diagnose:
    - Beste Dense2-Variante war `no_hourly_grid`:
      - `q_delta` median `R2 ~0.895`, `shifted ~0.524`, `rebound ~0.244`, `peak ~0.370`.
    - Nach Reuse aller gefundenen Screen-Artefakte ist die Abdeckung groesser, die Holdouts werden aber haerter:
      - month-stratified `no_hourly_grid`: `q_delta ~0.874`, `shifted ~0.450`, `rebound ~-0.047`, `peak ~0.360`.
      - group-shuffle `no_hourly_grid`: `q_delta ~0.804`, `shifted ~0.401`, `rebound ~0.189`, `peak ~0.426`.
    - Hourly-Reaggregation auf Dense2 bleibt fuer Upper-only schwach:
      - mit Shifted-State-Postprocessor nur `shifted` median grob `0.35`, `rebound` negativ, `peak` grob `0.16`.
  - Schluss:
    - Die Upper-only-Luecke ist kein reines Truth-Mengenproblem. Mehr Tage verbreitern die Regimes, aber der aktuelle Feature-/Modellvertrag erklaert `shifted/rebound/peak` nicht ausreichend.
    - Fuer `q_delta` reicht der Daily-Pfad bereits brauchbar; fuer `shifted/rebound/peak` braucht es als naechstes einen expliziten state-/sequence-aware Mechanism-Ansatz oder direkte Nutzung des physikalischen Mechanism-Solverpfads fuer relevante Figure/Table-Tage.

- 2026-05-17: Upper-only-Rebound gegen den frueheren lower-relax Rebound-Fix geprueft.
  - Der alte `lower_relax_evt24_conservative_v1`-Fix loeste ein False-Activation-Problem:
    - kleine fruehe negative hourly Prediction Noise aktivierte Rebound auf wahren Null-Rebound-Tagen.
  - Auf dem aktuellen Upper-only-137-Tage-Slice ist das nicht der Hauptfehler:
    - Rebound ist in vielen Holdout-Tagen real positiv und wird durch die hourly Rekonstruktion stark unterschaetzt.
    - Ein Deadband verschlechtert Upper-only-Rebound; eine train-side Skalierung allein reicht ebenfalls nicht.
  - Code:
    - `rebound_postprocessor.py` unterstuetzt nun zusaetzlich ein explizites `daily_xgb_rebound_v1`-Profil.
    - `evaluate_kpi_reaggregation.py` kann diesen Daily-Rebound-Postprocessor aus denselben Tagesfeatures wie die shifted-Korrektur anwenden.
    - `evaluate_repeated_kpi_holdouts.py` bewertet shifted/rebound-Postprocessor nun auch kombiniert.
  - Diagnose:
    - Neuer Upper-only Daily-XGB-Rebound-Postprocessor verbessert Rebound im Smoke von stark negativ auf naeher an null, aber nicht auf paper-ready Niveau.
    - Kombiniert mit dem bisherigen shifted-state-Postprocessor bleibt Upper-only deutlich unter `R2 >= 0.95`.
    - Die wichtigere Ursache liegt upstream: `cohort_preheat_extra_wh_per_m2` und `cohort_cutback_shed_wh_per_m2` werden im hourly Modell stark zu klein gelernt; daraus folgen zu kleine `shifted`-/`rebound`-Massen.
  - Schluss:
    - Die passende Analogie zum alten Rebound-Fix ist nicht der Deadband selbst, sondern ein expliziter family-spezifischer KPI-/State-Layer.
    - Naechster Upper-only-Hebel ist ein Mechanism-Vertrag, der Preheat/Cutback/Recovery-Sequenzen direkt und skalenrichtig lernt oder routet.

- 2026-05-17: Einfachere Upper-only-vs-lower-relax Analogie getestet.
  - Code:
    - `train_hourly_mechanism_model` unterstuetzt nun explizite Feature-Presets:
      - `all`
      - `no_case_label`
      - `no_case_or_cohort_label`
    - zusaetzlich explizite Target-Transform-Profile:
      - `default`
      - `positive_components_identity`
      - `mechanism_mass_identity`
    - Evaluator/Postprocessor verwenden nun die im Modellartefakt gespeicherten Feature-Spalten, damit reduzierte Feature-Vertraege korrekt evaluiert werden.
  - Befund auf Upper-only `137` Daily-Rows:
    - `no_case_label` allein bringt kaum Verbesserung.
    - `mechanism_mass_identity` verbessert die rohe hourly Reaggregation deutlich, aber nicht ausreichend:
      - `shifted` steigt im 2-Seed-Smoke grob von stark negativ auf etwa `R2 ~ -0.79`.
      - `rebound` bleibt negativ.
      - `peak` bleibt um `R2 ~ 0.33`.
    - Sample-Weighting auf grosse `q_delta`-Ausschlaege verschlechtert die Holdout-KPIs.
    - ExtraTrees auf `q_delta` ist etwas besser als XGB, aber ebenfalls nicht ausreichend.
  - Breiter aktueller `constant_evt24_only`-Dataset neu exportiert:
    - `Learning/datasets/8cc4c85b98e7cc9b75b6cec8454f7a4825fbce880a79955a2129120d13acf9d8/`
    - `37,248` Zeilen, `66` Bundles.
    - Gemeinsames evt24-Training mit `no_case_label + mechanism_mass_identity` verbessert die Gesamt-KPIs gegenueber isoliertem Upper-only:
      - `shifted` median grob `R2 ~ -0.48`
      - `rebound` median grob `R2 ~ -0.30`
      - `peak` median grob `R2 ~ 0.40`
    - Zerlegung zeigt aber:
      - lower-relax shifted/peak sind im gemeinsamen Modell wieder gut.
      - Upper-only bleibt der schwache Teil.
    - Mit Daily-Rebound-Postprocessor steigt breiter evt24-Rebound im 2-Seed-Smoke auf grob `R2 ~ 0.15`, aber shifted bleibt schwach.
  - Schluss:
    - Der User-Verdacht ist teilweise richtig: Infrastruktur und KPI-Layer sollten analog zum lower-relax-Fall bleiben.
    - Der konkrete Upper-only-Fehler ist aber nicht nur der alte Rebound-Deadband-Fall, sondern eine weiterhin falsche hourly Mechanismus-Amplitude.
    - Naechster sinnvoller Schritt ist ein skalenrichtiger Upper-only-Mechanism-Mass-Vertrag, nicht noch mehr generisches Daily-Postprocessing.

- 2026-05-18: Rebound gezielt upper-only vs lower-relax zerlegt.
  - Neue Diagnose-Datei:
    - `Learning/models/thermflex_hourly_mechanism_rebound_decomp_upper_vs_lower.csv`
  - Zerlegte Groessen:
    - true/predicted `rebound`
    - true/predicted positive/negative `q_delta`-Masse
    - positive Masse nach erstem negativen Trigger
    - Stunde des ersten negativen Triggers
    - Zero-vs-active Rebound-Tage
  - Befund lower-relax:
    - Fehlerbild entspricht dem alten Fix:
      - true Rebound meist `0`
      - prediction triggert fast immer in Stunde `0`
      - also False-Activation durch fruehe negative Prediction Noise.
  - Befund upper-only:
    - Nicht dasselbe Einzelproblem.
    - Nur `4/34` Holdout-Tage sind False-Active-Zero-Rebound-Tage, aber diese Fehler sind gross.
    - Die Mehrheit sind echte aktive Rebound-Tage; dort wird positive Masse nach Trigger meist stark unterschaetzt oder zeitlich falsch gesetzt.
    - Ein reiner Deadband wie bei lower-relax wuerde die False-Active-Tage helfen, aber viele echte aktive Tage verschlechtern.
  - Schluss:
    - Upper-only sollte wahrscheinlich denselben KPI-Layer-Stil behalten, aber zweistufig:
      - zuerst Rebound-Aktivierung/Nulltage sauber klassifizieren,
      - dann Rebound-Masse fuer aktive Tage separat kalibrieren.
    - Das passt methodisch zur lower-relax-Loesung, ist aber kein identisches Deadband-Profil.

- 2026-05-18: Zweistufigen Upper-only-Rebound-Postprocessor als opt-in Kandidat implementiert.
  - Code:
    - `evaluate_kpi_reaggregation.py`
      - neue Sequenzfeatures aus der rekonstruierten hourly `q_delta`-Serie:
        - positive/negative Masse
        - positive Masse nach erstem negativen Trigger
        - Stunde des ersten negativen Triggers
        - Min/Max und positive/negative Stundenanzahl.
      - neuer Postprocessor-Typ `two_stage_daily_rebound_v1`.
    - `rebound_postprocessor.py`
      - neues Profil `upper_only_rebound_twostage_sequence_et_v1`.
      - Stage 1: ExtraTrees active-vs-zero classifier.
      - Stage 2: ExtraTrees Rebound-Massenregressor auf aktiven Tagen.
  - Diagnose:
    - Upper-only `137`-Tage-Slice, `no_case_label + mechanism_mass_identity`:
      - raw Rebound median grob `R2 ~ -0.74`
      - zweistufiger Postprocessor grob `R2 ~ -0.49`
      - verbessert also, aber bleibt schlechter als der einfache Daily-XGB-Rebound auf diesem Slice.
    - Breiter `constant_evt24_only`-Slice:
      - raw Rebound median grob `R2 ~ -0.30`
      - zweistufiger Postprocessor grob `R2 ~ 0.00`
      - verbessert, aber bleibt unter dem einfachen Daily-XGB-Rebound-Smoke (`~0.15`).
  - Schluss:
    - Die Fehlerzerlegung ist als Diagnose nuetzlich.
    - Die konkrete ET-Zweistufe ist noch kein preferred Modellpfad.
    - Naechster Modellhebel bleibt die skalenrichtige hourly Upper-only-Masse/Sequenz, nicht nur ein Rebound-Postprocessor.

- 2026-05-18: Upper-only-Rebound nach Kohorten/Families zerlegt.
  - Neue Diagnose-Datei:
    - `Learning/models/thermflex_hourly_mechanism_upper_cohort_rebound_decomp.csv`
  - Befund:
    - Echte Rebound-Masse kommt dominant aus:
      - `residential_pre1975`
      - `non_residential_pre1975`
      - `residential_1975_1990`
    - Das aktuelle Modell unterschaetzt bei diesen alten Kohorten positive und negative hourly Massen deutlich.
    - Moderne `2000_2014`-Kohorten werden relativ ueberaktiviert; insbesondere `non_residential_2000_2014` erzeugt zu viel predicted Rebound gegenueber fast keiner echten Rebound-Masse.
    - Aggregation nach Baualter zeigt:
      - `pre1975` und `1975_1990` sind die relevanten Rebound-Families.
      - `2000_2014` ist eher eine False-Activation-/Overprediction-Family.
  - Schluss:
    - Der Upper-only-Hebel ist nicht nur Tagesregime, sondern cohort-/archetype-routed Sequenzlernen.
    - Naechster Modellvertrag sollte Rebound/Sign-Sequenz nach Baualtersfamilien bzw. alten vs modernen Kohorten getrennt behandeln.

- 2026-05-18: Upper-only q_delta-Sequenzfehler nach Stunde und Regime zerlegt.
  - Neue Diagnose-Datei:
    - `Learning/models/thermflex_hourly_mechanism_upper_sequence_error_decomp.csv`
  - Befund nach Stunden:
    - Grosse mittlere Absolute Errors konzentrieren sich in den Tagesstunden `7-15` und im Abend-/Tageswechselbereich `21-23`.
    - Sign-Mismatch ist besonders in fruehen Stunden haeufig, was false trigger beguenstigt.
  - Befund nach Saison/Regime:
    - Winter unterschätzt positive und negative Masse besonders stark.
    - High-price und high-DH Tage zeigen starke Unterprognose der positiven und negativen Masse.
    - Shoulder-Tage haben eher spezifische Stunden-/Timingfehler, insbesondere morgens und um den Tageswechsel.
  - Befund nach Baualter:
    - Die groessten absoluten Stundenfehler liegen erneut bei `pre1975`, danach `1975_1990`.
    - Der Fehler sitzt nicht nur in der Tagesaggregation, sondern in der Sequenzform der alten Kohorten.
  - Schluss:
    - Sequence-Router sollte mindestens Achsen enthalten:
      - Baualter alt/modern
      - Winter vs Shoulder
      - high-price/high-DH vs low-DH
      - Morgen-/Mittags-Preheatfenster und Abend-/Tageswechsel-Triggerfenster.

- 2026-05-18: Ersten simplen Upper-only Sequence-Router gesweept.
  - Neue Diagnose-Dateien:
    - `Learning/models/thermflex_hourly_mechanism_upper_sequence_router_sweep_remaining.csv`
    - `Learning/models/thermflex_hourly_mechanism_upper_sequence_router_sweep_summary.csv`
  - Getesteter Vertrag:
    - positive und negative `q_delta`-Komponente getrennt lernen.
    - ExtraTrees-Smoke auf dem aktuellen Upper-only Holdout.
    - Router-Achsen:
      - global
      - old/modern age bin
      - old/modern × hour block
      - age × season × hour
      - sector × age × hour
      - cohort × hour
  - Befund:
    - Bester einfacher Router ist `age_hour`:
      - `shifted_r2` grob von `-0.78` auf `-0.64`
      - `rebound_r2` grob von `-0.59` auf `-0.44`
    - Reines `age` verbessert Rebound kleiner, verschlechtert shifted leicht.
    - Feinere Router (`age_season_hour`, `cohort_hour`, `sector_age_hour`) fragmentieren und verschlechtern den Holdout.
  - Schluss:
    - Family-Routing hilft, aber nur grob.

- 2026-05-18: Upper-only Sequence-Router als reproduzierbaren Evaluator festgezogen.
  - Neue Diagnose:
    - `Learning/thermflex_hourly_mechanism/evaluate_sequence_router_holdouts.py`
    - `Learning/models/thermflex_hourly_mechanism_sequence_router_diagnostics/upper_only_sequence_router_holdout_seed42.csv`
  - Reproduzierbarer Seed-42-Lauf auf dem aktuellen Upper-only Slice:
    - `global`: `qdelta_r2 ~ 0.45`, `shifted_r2 ~ -0.48`, `rebound_r2 ~ -0.91`, `peak_r2 ~ 0.68`
    - `age_hour`: `qdelta_r2 ~ 0.43`, `shifted_r2 ~ -0.29`, `rebound_r2 ~ -0.86`, `peak_r2 ~ 0.62`
  - Zusatztest:
    - gemeinsames 24h-Vektorlernen pro Kohorte/Tag brachte keinen Durchbruch.
    - direkter Tages-KPI-Smoke aus ex-ante Tagesprofilen bleibt fuer `shifted/rebound` schwach (`R2` grob `0.0-0.25`), Peak besser (`~0.44-0.74`).
  - Schluss:
    - Kein starker Hinweis auf einen reinen Reaggregationsbug.
    - Upper-only `shifted/rebound` ist mit der aktuellen `137`-Tage-Truth und den vorhandenen ex-ante Features noch nicht robust generalisierbar.
    - Naechster Hebel ist gezielte Upper-only Truth in rebound-/shift-aktiven State-Familien oder ein expliziterer aktivierter Sequenz-/State-Vertrag; Case-/Datumslabels sollten nicht als Lernsignal missbraucht werden.

- 2026-05-18: Upper-only KPI-Fehler per Oracle-Ablation isoliert.
  - Neues Diagnose-Skript:
    - `Learning/thermflex_hourly_mechanism/diagnose_upper_only_sequence_failure.py`
  - Output:
    - `Learning/models/thermflex_hourly_mechanism_xgb_mechanism_energy_intensive_6d058845d59b_features_no_case_label_transforms_mechanism_mass_identity/diagnostics/upper_only_sequence_failure/`
  - Oracle-Ergebnis:
    - `oracle_pred_timing_true_mass` macht `shifted` perfekt (`R2 = 1.0`), aber `rebound` bleibt schwach (`R2 ~ 0.07`) und `peak` negativ.
    - `oracle_true_timing_pred_mass` verbessert `peak` (`R2 ~ 0.73`), aber `shifted/rebound` bleiben schwach.
  - Fehlerbild:
    - kein generelles Aktivierungsproblem fuer shifted; alle Holdout-Tage sind relevant aktiv.
    - Rebound hat zwei getrennte Fehlerzustaende:
      - Shoulder-Null-Rebound-Tage werden durch fruehe negative Prediction-Trigger falsch aktiviert.
      - Winter-Rebound-Tage werden massiv unterschaetzt.
    - Groesste Massendefizite liegen bei alten Wohngebaeuden:
      - `residential_pre1975`
      - `residential_1975_1990`
      - danach alte Nichtwohngebaeude.
  - Zusatztest:
    - train-seitig gelernte Family/Hour-Block-Massenskalierung verbessert `shifted` etwas, verschlechtert aber `rebound/peak`.
  - Schluss:
    - Reine Massenskalierung ist kein sauberer Fix.
    - Upper-only braucht getrennte Behandlung fuer:
      - Shift-Massenkalibrierung alter Winter-Familien.
      - Rebound-Null-/Timing-Gate fuer Shoulder-Tage.

- 2026-05-18: Upper-only Subcontracts separat evaluiert.
  - Neues Diagnose-Skript:
    - `Learning/thermflex_hourly_mechanism/evaluate_upper_only_subcontracts.py`
  - Output:
    - `.../diagnostics/upper_only_subcontracts_enhanced/`
  - Mass-Contract:
    - Family-Day positive/negative q_delta mass ist gut lernbar:
      - all family-day: positive `R2 ~ 0.96`, negative `R2 ~ 0.93`
      - winter old family-day: positive `R2 ~ 0.86`, negative `R2 ~ 0.88`
    - Daily KPI nach Family-Massenkorrektur:
      - `shifted_r2 ~ 0.86`
      - `rebound_r2 ~ -0.23`
      - `peak_r2 ~ -0.16`
  - Rebound-Gate:
    - Gate plus active-regressor mit massenkorrigierten Sequenzfeatures:
      - `rebound_r2 ~ 0.21`
      - active-state `F1 ~ 0.95`
    - False-Rebound-Oracle zeigt obere Grenze:
      - nur False-Activation-Tage korrekt auf Null setzen wuerde `rebound_r2 ~ 0.63` erreichen.
      - zusaetzlich der eine Missed-Activation-Tag korrekt wuerde `rebound_r2 ~ 0.74` erreichen.
  - Schluss:
    - Shifted ist methodisch erreichbar ueber Family-Day-Mass-Contract.
    - Rebound-Restfehler sitzt in wenigen Shoulder-/Grenztagen, wo Null-Rebound und starker Rebound ex-ante sehr nahe beieinander liegen.
    - Naechster Truth-Hebel sollte gezielt diese Grenzzone abdecken, nicht generisch weitere Upper-only Tage.

- 2026-05-18: Upper-only Subcontracts ueber wiederholte Splits geprueft.
  - Neues Diagnose-Skript:
    - `Learning/thermflex_hourly_mechanism/evaluate_repeated_upper_only_subcontracts.py`
  - 3-Seed `group_shuffle`:
    - Family-Day-Massen bleiben robust gut:
      - positive mass median `R2 ~ 0.97`
      - negative mass median `R2 ~ 0.95`
    - Daily `shifted` nach Family-Massenkorrektur:
      - median `R2 ~ 0.77`
    - Gate+Regressor-Rebound:
      - median `R2 ~ 0.38`
  - 3-Seed month-stratified:
    - Daily `shifted` nach Family-Massenkorrektur:
      - median `R2 ~ 0.83`
    - Gate+Regressor-Rebound:
      - median `R2 ~ 0.21`
  - Zusatzdiagnose:
    - Oracle mit wahrer Family-Masse und predicted Timing erreicht im aktuellen Split `shifted_r2 ~ 0.97`.
    - direkte aggregierte Tages-Masse ist schlechter als Family-Masse.
    - Ratio-/Residual-Massenkalibrierung ist schlechter als absolute Family-Massenregression.
    - Daily Shifted-Korrektor auf massenkorrigierten Features verbessert repeated nicht.
  - Schluss:
    - Der Mass-Subcontract ist richtig, aber fuer `R2 >= 0.95` braucht er entweder mehr robuste Family-/Timing-Truth oder einen besseren Sequenzvertrag.
    - Der Rebound-Subcontract braucht vor allem mehr/trennschaerfere Beispiele in der Shoulder-Null-vs-High-Rebound-Grenzzone.

- 2026-05-18: Upper-only Truthbasis aus vorhandenen Screen-Artefakten voll aufgefuellt.
  - Neue Planung/Runner:
    - `Learning/thermflex_hourly_mechanism/plan_upper_only_truth_targets.py`
    - `Optimization/run/analysis/run_upper_only_truth_target_plan.py`
  - Builder erweitert:
    - `build_vienna_constant_thermflex_mechanism_bundle(..., screen_csv=...)`
    - nicht-default Split-Vertraege werden in `train.py` nun im Modellordnernamen codiert.
  - Neue Run-Artefakte:
    - `paper_mechanism_bundle_upper_target_plan_truth_20260518_131554/`
      - 33 gezielte neue Tage, 6.336 Hourly-Cohort-Zeilen.
    - `paper_mechanism_bundle_upper_remaining_truth_20260518_133748/`
      - weitere 47 Tage, 9.024 Hourly-Cohort-Zeilen.
    - zusammen damit Upper-only-dur24 Screen-Abdeckung aus `heating_season_screen_joined.csv` voll ausgeschoepft.
  - Neue Datasets/Modelle:
    - Zwischenstand `6f6f33800d11...`: 32.640 Upper-only-Zeilen.
    - Vollstand `b3ffb29c9855...`: 41.664 Upper-only-Zeilen, 52 Bundles.
    - XGB Default:
      - `thermflex_hourly_mechanism_xgb_mechanism_energy_intensive_b3ffb29c9855_features_no_case_label_transforms_mechanism_mass_identity`
    - XGB month-stratified:
      - `..._split_group_stratified_shuffle_month`
  - Validierter Stand auf Full-Truth Default-Split:
    - Family-Day Mass:
      - positive mass `R2 ~0.974`
      - negative mass `R2 ~0.974`
      - winter old-family positive/negative `R2 ~0.98`
    - Daily KPI mit Family-Mass-Korrektur:
      - shifted `R2 ~0.92`
      - rebound bleibt schwach (`gate+regressor R2 ~0.45`)
      - peak `R2 ~0.47`
    - Direct-Daily ExtraTrees/XGB ist kein besserer Ersatz.
  - Fehlerdiagnose:
    - Rebound-Restfehler ist fast vollstaendig Gate/Timing:
      - wenn true Zero-/Low-Rebound-Tage korrekt auf Null gesetzt werden, steigt Rebound auf `R2 ~0.91`.
      - aktiver Rebound-Magnitude-Fehler allein ist deutlich kleiner.
    - Zusätzliche Dispatch-/24h-Profilfeatures wurden getestet, aber nicht als Standard behalten, weil sie den Gate-Holdout verschlechterten.
  - Schluss:
    - Mehr Truth allein loest Upper-only Rebound/Peak nicht.
    - Shifted ist mit Family-Mass-Contract nahe brauchbar, Rebound braucht einen expliziten Zero-/Late-trigger-Sequenzvertrag.

- 2026-05-18: Upper-only Zero-/Late-trigger-Vertrag als reproduzierbare Diagnose ergaenzt.
  - Neues Diagnose-Skript:
    - `Learning/thermflex_hourly_mechanism/evaluate_upper_only_trigger_contract.py`
  - Saubere Train-Split-Schwellenwahl fuer Rebound-Aktivierung getestet:
    - bester sauberer Holdout: `logistic_balanced + active_regressor`
    - `rebound_r2 ~0.52`, `MAE ~447 MWh`, active-state `F1 ~0.90`.
    - Oracle, der nur echte Zero-/Low-Rebound-Tage korrekt auf Null setzt: `rebound_r2 ~0.86`.
  - Modellvorhersagen fuer `preheat_extra`/`cutback_shed` als optionale Trigger-Features getestet:
    - verschlechtern den besten Holdout auf `rebound_r2 ~0.43`.
    - daher nur explizit zuschaltbar, nicht Standard.
  - Sequenzdiagnose:
    - Hauptfehler sind echte Null-Rebound-Tage mit spaetem/fehlendem negativen Trigger, waehrend das Modell kleine fruehe negative Artefakte erzeugt.
    - Test-optimierte Suppression ueber fruehen Trigger und kleines Negativ/Positiv-Massenverhaeltnis kaeme auf `rebound_r2 ~0.65`, ist aber nicht als sauberer Holdout-Vertrag verwendbar.
  - Schluss:
    - Der Engpass ist weiterhin State-/Timing-Identifikation, nicht mehr generische Tages-Truth.
    - Naechster sinnvoller Schritt ist ein expliziter Trigger-/Timing-Zielvertrag oder gezielte neue Truth mit gepaarten Zero-vs-High-Rebound Shoulder-Faellen.

- 2026-05-18: Weitere Upper-only Rebound-Fixrichtungen negativ geprueft.
  - Expliziter Timing-Label-Vertrag:
    - `Learning/thermflex_hourly_mechanism/evaluate_upper_only_timing_contract.py`
    - Label: frueher nutzbarer negativer Trigger plus positive Masse nach Trigger.
    - Ergebnis faellt auf denselben besten Holdout wie der direkte Gate-Vertrag zurueck:
      - `rebound_r2 ~0.52`.
    - Interpretation: das Timing-Label trennt mit den aktuellen Features nicht besser als `rebound_active`.
  - Train-Template-Rekonstruktion aus Family-Massen:
    - Rebound nur `R2 ~0.11-0.20`, Shifted/Peak deutlich schlechter.
    - Durchschnittsprofile sind daher kein geeigneter Ersatz fuer echtes Timing.
  - Deep-XGB-Diagnose:
    - separater nicht bevorzugter Artefaktordner:
      - `Learning/models/thermflex_hourly_mechanism_xgb_deep6_mechanism_energy_intensive_b3ffb29c9855_features_no_case_label_transforms_mechanism_mass_identity/`
    - Hourly `q_delta` verbessert nur minimal (`R2 ~0.37`), Daily-Subcontracts verschlechtern sich:
      - shifted `R2 ~0.77`
      - rebound `R2 ~0.19`
      - peak `R2 ~0.47`
  - Schluss:
    - Mehr Modellkapazitaet, einfache Timinglabels und Mittelwert-Templates loesen Upper-only Rebound/Peak nicht.
    - Naechster Hebel ist gezielte Boundary-Truth fuer gepaarte Shoulder-Faelle und/oder ein expliziter State-Target-Export aus dem Mechanism-Runner.

- 2026-05-18: Upper-only Boundary-Truth-Plan und Batchvorbereitung erstellt.
  - Neuer Planer:
    - `Learning/thermflex_hourly_mechanism/plan_upper_only_boundary_truth.py`
    - Output:
      - `.../diagnostics/upper_only_boundary_truth_plan/upper_only_boundary_pairs.csv`
      - `.../upper_only_boundary_truth_run_plan.csv`
      - `.../upper_only_boundary_truth_run_plan_core.csv`
    - Ergebnis:
      - 9 False-Active-Low-Rebound-Ankertage.
      - 23 High-Rebound-Paartage.
      - volle Matrix: 288 empfohlene Tau-/Duration-Rows.
      - Core-Plan: 72 Rows, davon Tier 0: 18 `tau4/dur24` Boundary-Runs.
  - Neuer Override-Emitter:
    - `Optimization/run/analysis/emit_upper_only_tau_duration_grid_overrides.py`
    - erzeugt Upper-only Overrides fuer `tau 2/4/8/12` und `dur 1/4/8/24`.
  - Neuer Batchrunner:
    - `Optimization/run/analysis/run_upper_only_boundary_truth_batch.py`
    - Dry-run erfolgreich fuer Tier 0:
      - `Optimization/run/results/Vienna/gold/upper_only_boundary_truth_batch_20260518_154716/`
    - Es wurden noch keine echten MILP-Runs gestartet.

- 2026-05-18: Upper-only tau4/dur24 Boundary-Truth ausgefuehrt und ausgewertet.
  - Tier-0 Boundary-Run gestartet und in Mechanism-Bundles rehydriert:
    - Batch: `Optimization/run/results/Vienna/gold/upper_only_boundary_truth_batch_20260518_155627/`
    - 16 erfolgreiche tau4/dur24-Tage; `2023-12-25` blieb wegen `maxTimeLimit` unvollstaendig.
  - Zusaetzliche gezielte tau4/dur24-Truth gesammelt:
    - Expansion/Shoulder/Winter/Oct-Nov Boundary-Batches:
      - `upper_only_boundary_truth_batch_20260518_164727/`
      - `upper_only_boundary_truth_batch_20260518_171803/`
      - `upper_only_boundary_truth_batch_20260518_173649/`
      - `upper_only_boundary_truth_batch_20260518_175405/`
    - Finaler tau4-only Dataset-Export:
      - `Learning/datasets/eddcb2b7be8e7fd85c7d16b45a87d5bfd58cf5a6ac024693daa3d54c0632ce4e`
      - 92 echte tau4/dur24-Tage, 17,664 Zeilen, 26 Bundles.
  - Dataset-Vertrag erweitert:
    - neues Family-Slice `constant_evt24_upper_only_tau4_only`.
    - explizite Split-Strata fuer kleine tau-spezifische Holdouts:
      - `split_stratum_season_rebound`
      - `split_stratum_season_rebound_active`
  - Wichtigste Diagnose:
    - alte Upper-only-Artefakte tragen `policy_tau_h == 0` und duerfen nicht als tau4-Truth vermischt werden.
    - viele alte `tau0` High-Rebound-Auswahltage werden in echter tau4-Wahrheit zu Low-Rebound.
  - Bester aktueller tau4/dur24 Stand:
    - Modell:
      - `Learning/models/thermflex_hourly_mechanism_xgb_mechanism_energy_intensive_eddcb2b7be8e_features_no_case_label_transforms_mechanism_mass_identity_split_group_stratified_shuffle_split_stratum_season_rebound_active`
    - Family-Massen: positive/negative jeweils `R2 ~0.95`.
    - Daily shifted nach Family-Mass: `R2 ~0.93`.
    - Daily rebound bester Trigger-Vertrag: `R2 ~0.60`.
    - Rebound-Oracle mit perfektem Zero/Low-Gate: `R2 ~0.89`; damit bleibt der echte Engpass die Active-State-/Trigger-Grenze, nicht generische Truth-Menge.
    - ExtraTrees-Hourly wurde getestet und war schlechter als XGB.

- 2026-05-18: Upper-only tau4/dur24 State-Target-Varianten geprueft.
  - State-/Trigger-Diagnostik erweitert:
    - `evaluate_upper_only_state_contract.py` prueft globale, saisonale und score-basierte Gates.
    - `evaluate_upper_only_trigger_contract.py` kann optionale Modell-Komponenten- und ex-ante Profilfeatures zuschalten.
  - Ergebnis auf dem aktuellen tau4/dur24 Holdout:
    - Timing-Contract allein bleibt bei `rebound_r2 ~0.60`.
    - einfache vorhergesagte Modell-Komponentenfeatures verbessern den sauberen Trigger-Vertrag von `~0.60` auf `~0.70`.
    - breite Zeitblock-/ex-ante-Profilfeatures verschlechtern den Holdout und bleiben daher nicht Default.
  - Neues explizites Zielprofil getestet:
    - `mechanism_core` mit `cohort_flex_active_member_share` und Innenzustand.
    - bester Rebound-Contract: `R2 ~0.81` (`random_forest_leaf3` Gate plus aktive Magnitude).
    - Cross-Routing Gate/Magnitude verbessert leicht auf `R2 ~0.82`.
  - Nicht weiterverfolgt:
    - `full_thermal` Feature-Mode fuer diese kleine Upper-only-Scheibe.
    - kombiniertes `mechanism_energy_state_intensive` Profil; die getrennte Core/Energy-Router-Idee ist besser.
  - Aktueller Schluss:
    - Der Haupthebel war tatsaechlich der fehlende Flex-/State-Targetblock.
    - Fuer `R2 >= 0.95` fehlen weiterhin gezielte Boundary-Truth bzw. ein expliziteres Event-/Trigger-State-Target fuer die November-/Shoulder-False-Active-Faelle.

- 2026-05-18: Upper-only Rebound weiter isoliert und zusaetzliche tau4/dur24 Boundary-Truth gesammelt.
  - Dataset-/Target-Vertrag erweitert:
    - `mechanism_core_event` enthaelt nun zusaetzlich `cohort_event_start_count`.
    - Duration-Family-Slices fuer Upper-only tau4 wurden ergaenzt, damit `dur1/4/8` nicht durch den alten `evt24`-Filter verloren gehen.
  - Diagnostik erweitert:
    - `evaluate_upper_only_cross_router_contract.py` prueft Gate/Magnitude-Cross-Routing.
    - `evaluate_upper_only_trigger_contract.py` enthaelt nun positive-Mass-Magnitude-Kandidaten.
  - Beste saubere 92-Tage-Diagnose:
    - Core/Event bringt nur marginal mehr als Core-State.
    - `raw_positive_mass` als Magnitude verbessert den besten tau4/dur24 Upper-only Rebound-Holdout leicht auf `R2 ~0.823`.
  - Zusaetzliche Truth gesammelt und rehydriert:
    - dur1/4/8 Boundary-Batch:
      - `Optimization/run/results/Vienna/gold/upper_only_boundary_truth_batch_20260518_194503/`
    - tau4/dur24 Gap-Batches:
      - `Optimization/run/results/Vienna/gold/upper_only_boundary_truth_batch_20260518_201318/`
      - `Optimization/run/results/Vienna/gold/upper_only_boundary_truth_batch_20260518_204519/`
    - Die Markdown-Fehler in einzelnen Zero-Chunks traten nach erfolgreicher CSV-Erzeugung auf; die CSVs wurden verwertet.
  - Neuer erweiterter tau4/dur24 Datasetstand:
    - `Learning/datasets/de97990c6d57d3efd7d148b2cdf7414f16b02a89747362a3a2ec0b9ccfc5b8e3`
    - 133 tau4/dur24 Upper-only Tage, 25,536 Zeilen, 38 Bundles.
  - Schluss:
    - Einfaches Mergen weiterer harter Boundary-Tage macht den Holdout strenger und loest Rebound nicht automatisch.
    - Der aktuelle Upper-only Rebound-Contract ist noch nicht robust; der naechste Hebel ist ein expliziter Trigger-/False-Active-State-Contract statt weiterer generischer XGB/ExtraTrees-Varianten.

- 2026-05-18: Upper-only Trigger-State-Labels exportiert.
  - Screen-Markdown-Export gefixt:
    - undefinierte Prozentwerte werden im Markdown als `n/a` geschrieben.
    - CSV/JSON bleiben unveraendert und der Run scheitert nicht mehr nach erfolgreichen Solves.
  - Neuer Diagnose-Exporter:
    - `Learning/thermflex_hourly_mechanism/build_upper_only_trigger_state_labels.py`
    - Output fuer das aktuelle 133-Tage Core/Event-Modell:
      - `.../diagnostics/upper_only_trigger_state_labels/daily_trigger_state_labels.csv`
      - `.../hourly_trigger_state_labels.csv`
      - `.../trigger_state_label_summary.json`
  - Diagnose auf dem persisted Holdout:
    - 33 Testtage.
    - 12 true rebound-active Tage.
    - 10 shifted-without-rebound Tage.
    - 8 Testtage sind `false_active_on_shifted_without_rebound`.
    - `positive_after_cutback` ist mit dem aktuellen Sequenzmodell im Test deutlich falsch (`R2 < 0`).
  - Schluss:
    - Der naechste Router muss shifted-without-rebound und echte rebound-active Tage explizit trennen.
    - Rebound-Magnitude sollte danach auf dem State-Contract aufbauen, nicht direkt auf dem rohen Hourly-Delta.
  - Erster State-Router:
    - `Learning/thermflex_hourly_mechanism/evaluate_upper_only_trigger_state_router.py`
    - Output:
      - `.../upper_only_trigger_state_labels/state_router/state_router_metrics.csv`
      - `.../state_router_predictions.csv`
    - Ergebnis auf demselben 133-Tage-Holdout:
      - bester Test-Rebound `R2 ~0.47`.
      - Active-State Accuracy `~0.85`, F1 `~0.78`.
    - Das ist noch nicht zielreif, aber deutlich besser als der erweiterte direkte Rebound-Contract auf diesem harten Holdout.

- 2026-05-18: Upper-only Trigger-State-Router weiter zerlegt.
  - `build_upper_only_trigger_state_labels.py` additiv um Daily-State-Kontext erweitert:
    - Preisprofil, Temperaturprofil, Referenzlast-Zeitblockfeatures, Solar-/Irradiance-Summen.
  - `evaluate_upper_only_trigger_state_router.py` erweitert:
    - explizites shifted-without-rebound Veto.
    - Feature-Profile `compact_state` und `state_plus_daily_context`, damit neue Kontextfeatures nicht unkontrolliert den alten Vertrag ersetzen.
  - Ergebnis auf dem 133-Tage-Hard-Holdout:
    - bestes robustes Profil bleibt `compact_state`.
    - bester Rebound `R2 ~0.47`; Veto verbessert den Test-R2 nicht.
    - Kontextprofil overfittet auf 100 Train-Tage und faellt auf `R2 ~0.26`.
  - Orakel-/Fehlerdiagnose:
    - perfekte Active/Inactive-Entscheidung mit aktueller Magnitude kaeme nur auf `R2 ~0.83`.
    - echte Timing-/Signstruktur mit vorhergesagter Masse kaeme auf `R2 ~0.88`.
    - damit ist der Engpass weiterhin Trigger-/Sequenz-Timing plus Magnitude, nicht nur ein simpler Zero-Rebound-Filter.
  - Neuer gezielter Truth-Plan erzeugt:
    - `.../diagnostics/upper_only_boundary_truth_plan_current/`
    - 3 Low-/False-Active-Anker, 9 High-Rebound-Paare.
    - 96 empfohlene tau/duration Run-Zeilen; 24 Core-Zeilen.
    - Dry-run der Batch-Queue erfolgreich: 8 Tasks fuer Tier 0/1.

- 2026-05-18: Upper-only Overnight-Truth-Batch gestartet und verwertet.
  - Voller Boundary-Plan ausgefuehrt:
    - `upper_only_boundary_truth_batch_20260518_220159` (Tier 0/1, tau4 dur24/8/4/1).
    - `upper_only_boundary_truth_batch_20260518_221404` (Tier 2, tau2/8/12 dur24).
    - `upper_only_boundary_truth_batch_20260518_222127` (Tier 3/4, restliche tau/duration Boundary-Kombinationen).
    - Alle 32 Tasks erfolgreich.
  - Aus den 32 Screen-Folders wurden Mechanism-Bundles mit `thermflex_cohort_utilization_hourly.csv` gebaut.
  - Dataset-Slices ergaenzt:
    - `constant_upper_only_evt24_tau_sensitivity`
    - `constant_upper_only_tau_duration_family`
  - Neue kuratierte Datasets:
    - tau4 duration family: `f0b6d0f47c01...`
    - evt24 tau sensitivity: `c16e77c05ac0...`
    - tau-duration family: `fbdca3592839...`
  - Sauberer tau4/dur24-Slice nach Boundary-Plan blieb bei denselben unabhaengigen Tagen (`837b6f16560d...`) und verbesserte den Router nicht.
  - Zusaetzliche 9 unabhaengige Winter-/Mass-Timing-Tage aus dem zweiten Target-Plan replayed:
    - neuer tau4/dur24 Datasetstand `f658c724ffb1...`, 142 Tage.
    - bester State-Router: `rebound R2 ~0.68`, Active-F1 `~0.92`, MAE `~240 MWh`.
  - Noch breitere 26-Tage-Erweiterung replayed:
    - neuer tau4/dur24 Datasetstand `573814bf8d82...`, 168 Tage.
    - bester State-Router faellt auf `rebound R2 ~0.50`; die zusaetzliche Mischung macht den Holdout haerter und ist nicht automatisch besser.
  - Aktueller bester verwertbarer Stand fuer Upper-only tau4/dur24 bleibt daher `f658c724ffb1...`.

- 2026-05-19: Upper-only Shoulder-Boundary-Truth gezielt erweitert und Router neu bewertet.
  - Neuer Diagnose-Router:
    - `Learning/thermflex_hourly_mechanism/evaluate_upper_only_trigger_family_router.py`
    - Ergebnis auf `f658...`: grobes Season-/Load-Family-Routing verbessert nicht (`~0.63` vs pooled `~0.68`); Fehler sitzt in Shoulder-Null-vs-Rebound und Magnitude.
  - Gezielt geloeste neue tau4/dur24 Upper-only Shoulder-Tage:
    - Screen: `daily_thermflex_screen_upper_only_shoulder_boundary_tau4_dur24_test_20260519_083802`
    - Screen: `daily_thermflex_screen_upper_only_shoulder_boundary_tau4_dur24_target_20260519_083915`
    - Mechanism-Bundles:
      - `paper_mechanism_bundle_upper_only_shoulder_boundary_tau4_dur24_test_20260519_085225`
      - `paper_mechanism_bundle_upper_only_shoulder_boundary_tau4_dur24_target_20260519_085334`
  - Neuer kuratierter Datasetstand:
    - `Learning/datasets/1f41fdd475cfb7a75a45cb2525d7686081a413c89111a3433151126a2c5eb2fa`
    - 179 tau4/dur24 Upper-only Tage im Trigger-State-Label-Export.
  - Anchor-Holdout gegen die alten `f658...` Testtage:
    - bester State-Router: `rebound R2 ~0.935`, MAE `~119 MWh`, Active-F1 `1.0`.
    - Das bestaetigt gezielte Shoulder-Boundary-Truth als Haupthebel.
  - Eine zweite, kaeltere Shoulder-Ergaenzung:
    - `daily_thermflex_screen_upper_only_shoulder_boundary_tau4_dur24_target2_20260519_091420`
    - `paper_mechanism_bundle_upper_only_shoulder_boundary_tau4_dur24_target2_20260519_091830`
    - neuer Datasetstand `86a559fc3b86...`
    - verschlechtert den alten Anchor auf `R2 ~0.79`; vorerst nicht als bevorzugter Upper-only tau4/dur24 Stand verwenden.
  - Lagged-context-Test:
    - `build_upper_only_trigger_state_labels.py` exportiert nun optionale Vortags-/3-Tage-Kontextfeatures.
    - `evaluate_upper_only_trigger_state_router.py` trennt diese sauber als `state_plus_lagged_context`, sodass der bisherige `state_plus_daily_context` unveraendert bleibt.
    - Ergebnis auf dem alten Anchor:
      - bester unveraenderter Daily-Kontext bleibt `R2 ~0.935`.
      - Lagged-Kontext verbessert nicht und overfittet teilweise.
    - Schluss: Die letzten Punkte bis `0.95` liegen eher in der aktiven Magnitude-Struktur bzw. in spezifischen gepaarten High/Low-Faellen, nicht in einem simplen Vortags-Wetterproxy.

- 2026-05-19: ThermFlex paper sensitivity quadrant und LOWER2K overnight path additiv aufgesetzt.
  - Neuer expliziter Overnight-Bundle-Runner:
    - `Optimization/run/analysis/run_lower2k_tau_evt24_heating_season_screen_bundle.py`
    - Scope bleibt eng und paper-spezifisch:
      - `LOWER2K`
      - durations `1/4/8/12 h`
      - tau `2/4/8/12 h`
      - optionaler Table-09 export pro neuem heating-season screen
  - Neuer Quadrant-/Sensitivity-Builder:
    - `Documentation/Papers/thermflex_paper/figures/build_fig_scatter_concept_flexibility_performance_map.py`
    - liest vorhandene `daily_thermflex_screen_*` Artefakte direkt ein
    - aggregiert saisonale Kosten/CO2/Shifted/Rebound/Boiler-KPIs
    - schreibt explizite Begleitdaten:
      - `fig_scatter_concept_flexibility_performance_map.csv`
      - `fig_scatter_concept_flexibility_performance_map_r2.csv`
      - `fig_scatter_concept_flexibility_performance_profiles.csv`
    - bindet den aktuellen `dispatch_kpi_paper` System-Surrogat-Holdout als R2-Slice ein
  - Aktueller Stand des neuen Quadranten:
    - Builder laeuft erfolgreich im expliziten Incomplete-Mode.
    - unbeschriftete/alte Screen-Ordner ohne klare Family-ID werden explizit uebersprungen, nicht still mitgemischt.
    - `upper_lower_2k` Heatmap ist derzeit noch lueckig; das ist der direkte Overnight-Fuellstand, nicht ein Plot-Bug.

- 2026-05-19: Zentralen MILP-Table-Runner fuer die Main-Paper-Ergebnistabelle angelegt.
  - Neues Skript:
    - `Documentation/Papers/thermflex_paper/tables/run_main_table_central_truth_tau4.py`
  - Vertrag des Runners:
    - Cases:
      - upper-only `dur24`
      - upper+lower `1K` mit `dur1/4/8/12`
      - upper+lower `2K` mit `dur1/4/8/12`
    - Horizonte:
      - `selected day` per case via maximalem `joint_savings_score`
      - drei fixe 7-Tage-Fenster:
        - December week (`2023-12-02` bis `2023-12-08`)
        - February week (`2023-02-19` bis `2023-02-25`)
        - April week (`2023-04-01` bis `2023-04-07`)
      - full heating period
    - KPI-Block:
      - cost / CO2 jeweils absolut und prozentual
      - shifted heat
      - rebound heat
      - rebound / shifted
      - boiler peak delta absolut und prozentual
  - Der Runner verwendet bewusst den bestehenden MILP heating-season screen als einen konsistenten KPI-Vertrag; die Wochen werden daraus ueber feste Kalenderfenster aggregiert statt ueber einen zweiten, leicht abweichenden KPI-Pfad.

- 2026-05-20: Hybrid-/Surrogat-Fuellung fuer zentrale ThermFlex-Paper-Tabelle erzeugt.
  - Kreditrechner-Notizen aus Worklog/TODO entfernt.
  - Neuer Draft-Builder:
    - `Documentation/Papers/thermflex_paper/tables/build_main_table_central_hybrid_surrogate_tau4.py`
  - Output:
    - `table_main_central_results_tau4_hybrid_surrogate_filled.csv`
    - `table_main_central_results_tau4_hybrid_surrogate_filled.md`
    - `table_main_central_results_tau4_hybrid_surrogate_filled_sources.csv`
    - `table_main_central_results_tau4_hybrid_surrogate_model_metrics.csv`
  - Quellenvertrag:
    - vollstaendige MILP-Screens bleiben bevorzugt.
    - fehlende Full-Season-Cases werden explizit als `surrogate_fill` markiert.
    - Surrogat-Screens liegen unter `Documentation/Papers/thermflex_paper/tables/surrogate_screens/`.
  - Technische Anpassung:
    - `Learning/thermflex_daily_results/predict.py` reichert alte kompakte Template-Screens bei Inferenz explizit mit kanonischem Tageskontext an.
    - ungesehene Policy-Labels koennen nur per Opt-in als numerische Policy-Extrapolation verwendet werden.
  - Einschraenkung:
    - verwendeter Daily-Table09-Surrogatstand hat nur moderate Holdout-R2 (`cost ~0.59`, `CO2 ~0.43`, `shifted ~0.53`, `rebound ~0.48`, `boiler peak ~0.03`).
    - `2K dur4` und `2K dur8` sind im Draft identisch vorhergesagt; diese Duration-Trennung ist daher nicht paper-final belastbar.
  - Zusaetzliche kurzfristige Paper-Table-Kandidatin:
    - `Documentation/Papers/thermflex_paper/tables/build_main_table_strongest_horizons_tau4.py`
    - Output:
      - `table_main_strongest_horizons_tau4.csv`
      - `table_main_strongest_horizons_tau4.md`
      - `table_main_strongest_horizons_tau4_sources.csv`
      - `table_main_strongest_horizons_tau4_surrogate_metrics.csv`
    - Vertrag:
      - gleiche KPI-Bloecke fuer `strongest_day`, `strongest_week`, `heating_period`.
      - Selector aktuell: staerkste Cost-Saving-Zeile bzw. staerkstes rolling 7-day Cost-Saving-Fenster.
      - `evidence_type` bleibt pro Case sichtbar (`milp_truth` vs `surrogate_fill`).
  - Targeted-MILP Handoff erstellt:
    - `build_targeted_milp_candidate_plan_tau4.py`
    - `run_targeted_milp_candidate_plan_tau4.py`
    - Nach Candidate-Hit-Validierung wurde der Plan von minimalen 46 auf robustere 145 eindeutige Case-Date-Tasks erweitert:
      - Top-5 surrogate strongest days.
      - Top-5 surrogate rolling strongest weeks.
      - Validierungsanker aus einem bekannten Miss (`1K dur1`: 2023-10-05 und 2023-12-21..27).
    - `validate_strongest_candidate_hits_tau4.py` zeigt auf bestehenden Full-Season-MILP-Cases:
      - strongest-day Top-1/Top-5 Hit: 2/3.
      - strongest-week Top-1/Top-5 Hit: 2/3.
      - Schluss: Surrogat reicht als Top-1-Kandidatenfinder nicht; robuste Kandidatenliste ist noetig.
    - Erster echter targeted Lauf gestartet fuer `upper_lower_1k_dur12_evt24`:
      - Ordner `daily_thermflex_screen_targeted_main_table_upper_lower_1k_dur12_evt24_tau4_20260520_125258`.
      - Stand nach zwei zeitbegrenzten Tool-Laeufen: 21 geloeste Tage, 2 Time-Limit-Failures (`2023-01-29`, `2023-12-24`), kein laufender Python-Prozess.
    - Overnight-Handoff stabilisiert:
      - Bootstrap-Skript `run_targeted_milp_overnight_tau4.cmd` ergaenzt, damit der Windows-Startpfad trotz Leerzeichen im Projektpfad nachvollziehbar geloggt wird.
      - Windows Scheduled Task `ThermFlexTau4Overnight_20260520_1448` gestartet, weil normale losgeloeste Shell-Kindprozesse im Tool-Kontext vorzeitig verschwinden.
      - Aktiver Overnight-Log: `targeted_milp_overnight_tau4_20260520_145054.log`.
  - Startzustand: Resume aus 21 Checkpoint-Tagen und 2 bekannten Time-Limit-Failures; Run begann mit `2023-12-25`.

- Updated after stopping the heavy full-season central-table path:
  - Confirmed that the original central-table MILP workflow was solver-bound on
    hard individual days and therefore too expensive for the intended paper table.
  - Stopped the long-running Python processes from that path.
  - Replaced `Documentation/Papers/thermflex_paper/tables/run_main_table_central_truth_tau4.py`
    with an explicit selected-window contract:
    - one shared mandatory `--selected-day`
    - one fixed `December` week
    - one fixed `February/March` week
    - one fixed `April` week
  - The runner now compares all use cases on identical windows and no longer
    depends on a full heating-season screen.

- 2026-05-21: ThermFlex surrogate architecture lessons consolidated before the
  next season-surrogate step.
  - Rechecked the documented failure mode of the old Table09-style daily model:
    - the hybrid fill model `thermflex_daily_results_xgb_table_09_paper_f77eafde5cdc`
      remains weak on the paper-relevant daily Table09 outputs
      (`dispatch_operating_cost_pct_change ~0.59`, `CO2 pct ~0.43`, shifted and
      rebound around `0.5`, boiler peak near zero).
    - this path should stay a draft/layout aid, not the general surrogate.
  - Rechecked the successful path:
    - `thermflex_system_results_xgb_dispatch_kpi_paper_612be5461a30` reaches
      strong grouped holdout quality for the paper-facing KPI contract:
      heat operating cost, fuel cost, CO2 cost, total CO2, shifted/rebound heat,
      peak change and comfort/activity KPIs.
  - Architectural decision:
    - Table09 / central tables / sensitivity figures are downstream consumers.
    - The reusable surrogate should learn general ThermFlex KPI components and
      aggregate absolute predictions to daily, weekly and seasonal report rows.
    - `dispatch_heat_operating_cost_eur` and its components are the cost story;
      `dispatch_operating_cost_eur` remains a legacy/global diagnostic because
      CHP electric-value and grid-related terms make it unsuitable as the
      primary paper target.

- 2026-05-21: Direct season-level system surrogate tested for the tau4 central
  heating-period table and rejected as promoted fill.
  - Added diagnostic builder:
    - `Documentation/Papers/thermflex_paper/tables/build_main_table_season_surrogate_v2_tau4.py`
  - Outputs:
    - `table_main_season_surrogate_v2_tau4.csv`
    - `table_main_season_surrogate_v2_tau4.md`
    - `table_main_season_surrogate_v2_tau4_sources.csv`
    - `table_main_season_surrogate_v2_tau4_validation.csv`
  - Result:
    - complete V2-compatible MILP screens are used for `upper_only_dur24` and
      `upper_lower_1k_dur1_evt24`.
    - old complete `1K dur4` screen exists but predates the heat-cost component
      contract, so it is not used as V2 heat-cost truth.
    - direct system-model predictions for the exact evt24 duration grid fail the
      complete-screen validation badly and collapse several unseen duration/
      relaxation cases to identical values.
  - Decision:
    - keep this output as diagnostic only
      (`system_surrogate_v2_diagnostic_not_promoted`).
    - continue from the stronger hourly-dispatch / daily-sum KPI path:
      latest useful diagnostic family `fe23b4c13220...` has daily-sum oracle-load
      R2 around `0.97` for heat cost and `0.99` for CO2, while predicted-load
      end-to-end remains weak.

- 2026-05-21: Tau4 season-table oracle-dispatch coverage evaluated.
  - Added:
    - `Documentation/Papers/thermflex_paper/tables/build_main_table_season_oracle_dispatch_evaluator_tau4.py`
  - Outputs:
    - `table_main_season_oracle_dispatch_tau4_coverage.csv`
    - `table_main_season_oracle_dispatch_tau4_r2_summary.csv`
    - `table_main_season_oracle_dispatch_tau4_anchor_checks.csv`
    - `table_main_season_oracle_dispatch_tau4_evaluator.md`
  - Finding:
    - `upper_only_dur24` and `upper_lower_1k_dur1_evt24` already have
      V2-compatible full-season MILP truth, so they do not need surrogate fills.
    - Remaining `upper+lower` duration cases have only `24-48` complete
      oracle-load dispatch days in the `fe23b4...` hourly-dispatch family, not
      212 days.
    - The daily-sum oracle-load R2 remains the right quality anchor
      (`heat-cost` median about `0.96`, `CO2` median about `0.99`), but the
      missing piece for promoted full-season fills is complete load templates /
      mechanism bridge for the unsolved days.

- 2026-05-21: Tau4 daily-anchor inventory and sparse season estimator updated
  to reuse interrupted V2 screen checkpoints.
  - Added/updated:
    - `Documentation/Papers/thermflex_paper/tables/build_main_table_tau4_daily_anchor_coverage.py`
    - `Documentation/Papers/thermflex_paper/tables/build_main_table_season_sparse_anchor_tau4.py`
  - Important fix:
    - reusable `heating_season_day_screen_checkpoint.csv` rows are now included
      when no final screen exists in the same bundle.
    - legacy numeric policy folders such as `lb20p5_dur1_evt24_tau4h` are matched
      explicitly and token-exactly; non-tau4 folders are excluded.
  - Current V2 daily-anchor coverage for the central tau4 season table:
    - full MILP truth: `upper_only_dur24`, `upper_lower_1k_dur1_evt24`
    - near/partial season anchors: `upper_lower_1k_dur4_evt24` has `161/212`
      days, `upper_lower_2k_dur1_evt24` has `205/212` days.
    - sparse selected-window anchors only: `1K dur8` has `36` days, `1K dur12`
      and `2K dur4/8/12` have `22` days each.
  - The sparse-anchor season table writes evidence tags per row:
    - `milp_full_season`
    - `partial_v2_anchor_plus_weather_knn_fill`
    - `near_full_v2_anchor_plus_weather_knn_fill`
    - `sparse_anchor_weather_knn_estimate`
  - Validation from selected-window anchors to full season on the two complete
    cases gives heat-cost percent errors around `0.26-0.50` percentage points
    and CO2 percent errors around `0.06-0.25` percentage points; shifted/rebound
    remains less reliable for upper-only season extrapolation.

- 2026-05-21: Targeted tau4 missing-anchor runner added and first gaps filled.
  - Added:
    - `Documentation/Papers/thermflex_paper/tables/run_main_table_tau4_missing_anchor_truth.py`
  - The runner writes an explicit missing-date plan and only starts MILP solves
    with `--execute`.
  - It can resume compatible checkpoints for interrupted full-season screens
    while the coverage inventory still avoids double-counting final/checkpoint
    rows from the same bundle.
  - Completed runs:
    - `upper_lower_2k_dur1_evt24`: solved the 7 missing days
      (`2023-12-25` to `2023-12-31`) and reached `212/212` merged V2 daily
      anchors.
    - `upper_lower_1k_dur4_evt24`: solved two additional 10-day chunks
      (`2023-11-04` to `2023-11-23`) and increased coverage from `161/212` to
      `181/212`.
  - Current central tau4 full-season evidence:
    - `milp_full_season`: `upper_only_dur24`, `upper_lower_1k_dur1_evt24`
    - `merged_v2_daily_anchor_full_season`: `upper_lower_2k_dur1_evt24`
    - `near_full_v2_anchor_plus_weather_knn_fill`: `upper_lower_1k_dur4_evt24`
    - still sparse: `1K dur8/12`, `2K dur4/8/12`.

- 2026-05-21: Explicit skip policy applied for hard tau4 daily truth gaps.
  - Reran the remaining `upper_lower_1k_dur4_evt24` gaps with a pragmatic
    per-day solver limit (`900 s`, `mip_rel_gap=0.01`) and incomplete-day
    logging enabled.
  - Result:
    - solved 30 additional days optimally,
    - skipped only `2023-12-24` with explicit `maxTimeLimit` failure in
      `heating_season_day_screen_failures.csv`,
    - improved `upper_lower_1k_dur4_evt24` V2 anchor coverage to `211/212`.
  - The remaining single day is now treated as an explicit KNN-fill gap in the
    season table, not as hidden truth.

- 2026-05-21: Tau4 long-duration truth coverage broadened under the same skip
  contract.
  - Continued targeted daily V2 MILP anchors with per-day `900 s` and
    `mip_rel_gap=0.01`.
  - `upper_lower_1k_dur8_evt24` increased from `113/212` to `142/212` merged
    daily anchors. Newly hard days are logged explicitly in the source failure
    CSVs rather than silently retried.
  - `upper_lower_2k_dur4_evt24` increased from `22/212` to `132/212` merged
    daily anchors. This promoted the central tau4 season-table evidence from
    `sparse_anchor_weather_knn_estimate` to
    `partial_v2_anchor_plus_weather_knn_fill`.
  - `upper_lower_2k_dur8_evt24` was broadened from `22/212` to `123/212`
    merged daily anchors. The run exposed several explicit max-time-limit days,
    but the case is now promoted from `sparse_anchor_weather_knn_estimate` to
    `partial_v2_anchor_plus_weather_knn_fill`.
  - Fixed the daily-anchor inventory so newer resume checkpoints next to older
    final screen files are still counted; row-level date de-duplication prevents
    double counting.
  - Current central tau4 table state:
    - complete/full-season truth: `upper_only_dur24`,
      `upper_lower_1k_dur1_evt24`, `upper_lower_2k_dur1_evt24`
    - near-full: `upper_lower_1k_dur4_evt24` (`211/212`)
    - partial: `upper_lower_1k_dur8_evt24` (`142/212`),
      `upper_lower_2k_dur4_evt24` (`132/212`),
      `upper_lower_2k_dur8_evt24` (`123/212`)
    - still sparse: `upper_lower_1k_dur12_evt24`,
      `upper_lower_2k_dur12_evt24`

- 2026-05-22: Tau4 duration-12 cases probed under the existing `900 s` / `1%`
  skip contract.
  - `upper_lower_2k_dur12_evt24` increased from `44/212` to `72/212` merged
    daily anchors. Several days were expensive and explicit max-time-limit
    skips appeared, so larger blind blocks are not recommended for this case.
  - `upper_lower_1k_dur12_evt24` increased from `44/212` to `68/212` merged
    daily anchors. This path was much cheaper in the tested blocks and had no
    new skips in the larger `19/19` block.
  - Both duration-12 rows are still `sparse_anchor_weather_knn_estimate`; more
    truth is needed before treating them as comparable to the partial
    duration-8 rows.

- 2026-05-22: Tau4 central-table daily anchor basis broadened after the first
  duration-12 probe.
  - Purpose: these daily V2 anchors are the validation/fill basis for the
    promoted season aggregation path and future surrogate sensitivity runs; full
    MILP season truth remains preferred where it exists.
  - Continued the same explicit skip contract (`900 s`, `mip_rel_gap=0.01`) and
    rebuilt the coverage and season tables after each meaningful block.
  - Current merged V2 daily-anchor coverage:
    - `upper_lower_1k_dur4_evt24`: `211/212` (near-full; one explicit hard day)
    - `upper_lower_1k_dur8_evt24`: `142/212`
    - `upper_lower_1k_dur12_evt24`: `134/212`
    - `upper_lower_2k_dur4_evt24`: `147/212`
    - `upper_lower_2k_dur8_evt24`: `135/212`
    - `upper_lower_2k_dur12_evt24`: `123/212`
  - All long-duration central tau4 rows are now at least
    `partial_v2_anchor_plus_weather_knn_fill`; `2K dur8` changed materially while
    the October/shoulder anchors were added, confirming that additional truth is
    still useful for stabilizing the long-duration season rows.

- 2026-05-22: Additional tau4 central-table truth broadening after stabilization
  checks.
  - Added targeted shoulder/autumn daily anchors for the remaining partial rows
    and rebuilt:
    - `Documentation/Papers/thermflex_paper/tables/table_main_tau4_daily_anchor_coverage.*`
    - `Documentation/Papers/thermflex_paper/tables/table_main_tau4_missing_anchor_truth_plan.csv`
    - `Documentation/Papers/thermflex_paper/tables/table_main_season_sparse_anchor_tau4.*`
  - Updated merged V2 daily-anchor coverage:
    - `upper_lower_1k_dur8_evt24`: `151/212`
    - `upper_lower_1k_dur12_evt24`: `152/212`
    - `upper_lower_2k_dur4_evt24`: `162/212`
    - `upper_lower_2k_dur8_evt24`: `135/212`
    - `upper_lower_2k_dur12_evt24`: `127/212`
  - Observed stability:
    - `2K dur8` changed strongly during the first October fills, then only
      slightly after the later block (`cost_delta_pct` around `-3.58%`).
    - `2K dur12` changed only moderately after additional April anchors
      (`cost_delta_pct` around `-3.42%`).
    - `1K dur8/12` still moved when October anchors were added; they remain
      usable as partial-anchor season estimates but should still be marked with
      evidence type in paper-facing outputs.

- 2026-05-22: Weekend broadening started for tau4 central-table truth anchors.
  - Continued guarded daily V2 MILP truth collection for the partial central
    rows with the same explicit `900 s` / `1%` contract.
  - New coverage after this block:
    - `upper_lower_1k_dur8_evt24`: `151/212`
    - `upper_lower_1k_dur12_evt24`: `171/212`
    - `upper_lower_2k_dur4_evt24`: `179/212`
    - `upper_lower_2k_dur8_evt24`: `149/212`
    - `upper_lower_2k_dur12_evt24`: `151/212`
  - `2K dur4`, `2K dur8`, and `2K dur12` exposed additional hard days under
    the solve contract; these are now explicit failure rows rather than hidden
    gaps.
  - The season estimates still moved materially for some long-duration rows
    when autumn anchors were added, so continued filling remains useful before
    freezing paper-grade full-heating-period values.

- 2026-05-23: Tau4 central-table weekend truth broadening consolidated.
  - Added `run_main_table_tau4_weekend_truth_queue.py` to cycle guarded missing
    daily-anchor solves and rebuild coverage/season outputs after each block.
  - Fixed the missing-anchor plan so explicit
    `heating_season_day_screen_failures.csv` dates are not repeatedly selected
    ahead of later unsolved dates; unresolved failures are now visible as
    `failure_days`.
  - Ran long guarded fill blocks under the unchanged `900 s` / `1%` contract and
    rebuilt:
    - `table_main_tau4_daily_anchor_coverage.*`
    - `table_main_tau4_missing_anchor_truth_plan.csv`
    - `table_main_season_sparse_anchor_tau4.*`
  - Final merged V2 daily-anchor state for the central long-duration tau4 rows:
    - `upper_lower_1k_dur8_evt24`: `201` solved anchors, `11` unresolved
      explicit failure days, no unknown missing dates.
    - `upper_lower_1k_dur12_evt24`: `209` solved anchors, `3` unresolved
      explicit failure days, no unknown missing dates.
    - `upper_lower_2k_dur4_evt24`: `209` solved anchors, `3` unresolved
      explicit failure days, no unknown missing dates.
    - `upper_lower_2k_dur8_evt24`: `196` solved anchors, `16` unresolved
      explicit failure days, no unknown missing dates.
    - `upper_lower_2k_dur12_evt24`: `204` solved anchors, `8` unresolved
      explicit failure days, no unknown missing dates.
  - The remaining gaps are now solve-contract failures, not unattempted days;
    paper-facing outputs must retain evidence labels and should not describe
    these rows as complete full-season MILP truth.

- 2026-06-13: Critical ThermFlex learning dataset alignment guard.
  - Audited recent Learning/ThermFlex surrogate training paths for high-impact
    correctness issues and found that trainers split by `truth_dataset.csv` rows
    while indexing `training_data.npz` arrays without checking that both files
    still describe the same row contract.
  - Added a shared fail-fast row-alignment validator and wired it into the daily
    results and hourly mechanism trainers before holdout indices are applied.
  - Added a focused regression test for matching rows, desynchronized truth CSVs
    and stale row-count metadata.
