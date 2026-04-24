# DH Thermflex Vienna Paper

## Scope

Dieses Paper ist ein enger, publishbarer Teil des groesseren PhD-Scopes.

Im Fokus stehen:

- Wiener District-Heating-Dispatch
- gebaeudeseitige Thermflexibilitaet
- `EnergyPlus`-kalibrierte Gebaeudearchetypen ueber `calibrated_v1`
- operativer Hauptpfad ueber `milp_day_ahead`
- ergaenzende Surrogat-/biobjektive Suche fuer Thermflex-Policy- und Designfragen

Dieses Paper ist **nicht** das volle Wien-2040-MES-Paper.

## Core Questions

Kurzer Paperschnitt fuer den aktuellen Beitrag:

1. Wie stark und in welcher Form kann gebaeudeseitige Thermflexibilitaet den Wiener DH-Dispatch beeinflussen?
2. Wie haengen Kosten-, CO2- und Flexibilitaetswirkung vom Tagtyp und von einfachen globalen Thermflex-Policies ab?
3. Welche vereinfachte, global einheitliche Thermflex-Policy ist fuer den aktuellen Paper-Schnitt plausibel und gut begruendbar?

## Active Method Path

Aktueller methodischer Hauptpfad:

- `EnergyPlus` als Offline-Teacher
- Export nach `Data/thermal_archetypes/Vienna/calibrated_v1.py`
- Runtime-/Dispatch-Modell mit expliziten Thermflex-Bounds
- Gold-/Truth-Pfad ueber `milp_day_ahead`

Methodische Einordnung:

- `milp_day_ahead`
  robuster und aktuell publishbarer Hauptpfad
- `milp_two_stage`
  wichtiger weiterfuehrender Endpunkt-/Limitationspfad, aber derzeit nicht der tragfaehige Paper-Hauptpfad

## What `milp_two_stage` Means Here

`milp_two_stage` bedeutet im aktuellen Repo:

- zweistufiger, szenariobasierter Dispatch-Pfad
- erste Stufe mit vorgezogenen Entscheidungen
- zweite Stufe als Recourse/Nachregelung ueber historische Szenarien

Aktueller Status fuer dieses Paper:

- fachlich wichtig
- methodisch jetzt als historischer Robustheitscheck tragfaehig
- deshalb aktuell:
  - Hauptaussage ueber `milp_day_ahead`
  - `milp_two_stage` als gezielter historischer Robustheitscheck, nicht als Hauptsuchpfad

Aktueller Debug-Stand:

- der erste konkrete Bruch war kein generischer Solverfehler
- sondern ein Kopplungsvertrag im Thermflex-Pfad:
  - `milp_two_stage` lieferte bisher nicht dieselben member-level Thermflex-Hourly-Arrays
    wie `milp_day_ahead`
- dieser Exportgap ist jetzt in `dispatch/modes/milp_two_stage.py` geschlossen
- reproduzierter Ladder-Status fuer `biobj_co2_end`:
  - `raw1_red1`: feasible
  - `raw4_red1`: feasible
  - `raw8_red2`: feasible
  - `raw16_red3`: feasible
  - `raw48_red6`: feasible
- zusaetzlicher Debug-Fix:
  - CO2-Tagesproxy im historischen Szenariobau sauber von der Gaspreislogik entkoppelt
- offener Restpunkt nur noch optional:
  - einen zweiten Voll-Recheck fuer weitere biobjektive Kandidaten ziehen, falls mehr als ein Two-Stage-Beispiel im Haupttext gezeigt werden soll

## Case Naming

Fallnamen muessen lesbar und paper-tauglich interpretierbar sein.

Beispiel:

- `lb21p0_dur24_evt1`

Bedeutung:

- `lb21p0`
  `constant_lower_bound_c = 21.0`
- `dur24`
  `max_flex_duration_h = 24`
- `evt1`
  `max_flex_events_per_day = 1`

Das ist also:

- Setpoint bleibt konstant
- auf `21.0 C` darf abgesenkt werden
- globale Flexdauer pro Tag ist bis `24 h` erlaubt
- aber es gibt nur `1` Eventstart pro Tag

Weitere haeufige Codes:

- `lb22p5`
  kein Absenken unter den Setpoint von `22.5 C`
- `upper_only`
  praktisch nur nach oben vorheizen, nicht nach unten absenken
- `evt24`
  bis zu `24` Eventstarts pro Tag erlaubt

## Current Interpretation

Aktueller Befund aus dem Representative-Day- und Sensitivitaetsblock:

- es gibt keine universell beste Thermflex-Policy ueber alle Tagtypen
- `lb21p0_dur24_evt1` ist oft stark auf Preis-, typischen Winter- und Schultertagen
- `constant_no_thermflex` bleibt auf Peak-Heat- und Sunny-Winter-Tagen teilweise bei Cost/CO2 vorne
- `evt1` vs. `evt24` ist oft nicht der entscheidende Hebel
- `lower_bound` und `duration` sind wichtiger als hohe Eventzahlen

## Main Case Candidates

Aktuell plausible Kandidaten fuer den Paper-Hauptfall:

- `constant_no_thermflex`
  als Referenzfall ohne aktive Gebaeudeflex
- `constant_thermflex`
  als isolierter Grundnachweis von Thermflex
- `lb21p0_dur24_evt1`
  als derzeit staerkster globaler Main-Case-Kandidat fuer den konstanten Thermflex-Schnitt

Warum `lb21p0_dur24_evt1` aktuell naheliegt:

- oft stark im Representative-Day-Block
- einfacher und klarer als kohortenspezifische Policies
- Eventzahl bleibt konservativ bei `1`
- erlaubt sichtbare Flex, ohne die Policy unnötig zu verkomplizieren

## What Is Still Open

Die noch offenen Paper-Restpunkte sind jetzt vor allem Verdichtung, nicht neue Kernlogik:

1. finalen Main Case bewusst festziehen
2. zentrale Paper-Runs nach dem Gebaeudelast-Fix sauber neu rechnen
3. finale KPI-Tabelle und Hauptfiguren bauen
4. biobjektiven Zusatzblock sauber als Erweiterung innerhalb des Thermflex-Falls auswerten
5. Limitations explizit schreiben:
   - `milp_two_stage` aktuell nicht Hauptpfad
   - Representative Days statt Jahresbeweis
   - `non_residential` methodisch schwächer
   - Runtime-Solarpfad noch nicht voll teacher-harmonisiert

## Key Result Bundles

Wichtige aktuelle Ergebnisordner:

- `Optimization/run/results/Vienna/gold/paper_dispatch_comparison_20260403_131344`
- `Optimization/run/results/Vienna/gold/constant_thermflex_representative_day_summary_20260403`
- `Optimization/run/results/Vienna/gold/dh_thermflex_run_20260403_140316`
- `Optimization/run/results/Vienna/gold/biobj_gold_candidates_20260403_093146`
