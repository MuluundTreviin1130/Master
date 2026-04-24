# TODO

## Active

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
  - als naechsten Umsetzungsschritt einen standardisierten hourly transition dataset builder vorbereiten:
    - `state_t + exogenous_t + control_t + cohort_context -> state_t+1 + q_heat_t + heat-balance diagnostics`
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
  - der aktuelle Validation-Preset braucht für die Januarwoche `2023-01-15` einen winter-fit `district_gas_boiler` von rund `2,2 GW_th`, damit der vereinfachte 2023-Winterbenchmark ohne `dh_unserved_heat` läuft; das ist ein Benchmark-Proxy und keine Aussage über die exakte historische installierte Kesselleistung
  - Widerspruch explizit prüfen:
    offizieller Wiener 2023-Anker für `Muell- und Sondermuellverbrennung (eigene) = 1.199,981 GWh_th`
    vs. aktuelle Repo-SSOT `district_waste_incineration_gwh_per_year_max = 811,11`;
    solange das nicht sauber aufgelöst ist, bleibt der 2023-Referenzpreset bewusst auf die Potenzialgrenze gekappt
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
- [ ] Oil-Sensitivitaet fuer den fossilen Peak-Boiler als eigenen Paper-Sensitivitaetsblock zeigen:
  - aktuellen v2-Proxy `2/3 Gas + 1/3 Heizoel extra leicht` gegen mindestens `1/2 Gas + 1/2 Heizoel extra leicht` pruefen
  - Effekte auf `dispatch_cost_eur`, `co2_emissions_total_t`, `district_gas_boiler_peak_kw` und Day-Ranking vergleichen
  - nicht den Hauptpfad aufblasen; explizit als Sensitivitaet rahmen
- [ ] Generelle Sensitivitaetsanalyse fuer das Paper sauber planen und spaeter konsistent durchziehen:
  - Peak-Boiler-Fuel-Mix (`Gas/Oel`)
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
- [ ] Wiener fossilen Peak-Boiler nach der neuen `2/3 Gas + 1/3 Heizoel extra leicht` Economics-SSOT erneut gegen die reprÃ¤sentativen Thermflex-Tage screenen:
  - prÃ¼fen, wie stark `dispatch_cost_eur`, `co2_emissions_total_t` und `district_gas_boiler_peak_kw` gegen den alten reinen Gasproxy kippen
  - danach entscheiden, ob `1/3` als konservativer v2-Proxy reicht oder ob `1/2` Oelanteil als SensitivitÃ¤t nÃ¶tig ist
- [ ] Gas-CHP methodisch sauberer schneiden:
  - aktueller Pfad ist noch ein fixes `eta_el` / `eta_th`-Modell
  - fÃ¼r die Wien-/Thermflex-Story spÃ¤ter prÃ¼fen, ob ein variables Extraktions-/Kondensations-Kennfeld gebraucht wird
  - das nur mit belastbarer Literatur-/Katalogbasis umstellen, nicht heuristisch
- [ ] Paperfigur-Idee weiterverfolgen:
  - Tages-Shiftplot mit zusätzlicher Hintergrundlinie für den thermischen Freiheitsgrad / die noch variable Energie
  - diese Linie soll über den Innenzustand bzw. die Nähe zur oberen Temperaturgrenze erzählen, damit sichtbar wird, wann weiteres Vorheizen überhaupt noch möglich ist
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
