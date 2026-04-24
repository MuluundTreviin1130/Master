# Vienna 2040 MES Target System

## Zweck

Dieses Dokument beschreibt das uebergeordnete Zielsystem der Energiesystemmodellierung.
Der aktuelle Paper-Scope bleibt bewusst enger, soll aber in dieses groessere Zielbild passen.

## Zielbild

Das Zielsystem ist ein Wiener Multi-Energy-System fuer den Transformationspfad Richtung `2040`.
Es umfasst vor allem:

- `Strom`
- `Waerme`
- `Verkehr`

Diese Sektoren sollen weitgehend dekarbonisiert und ueber gemeinsame Flexibilitaets-,
Dispatch- und Infrastrukturpfade gekoppelt modelliert werden.

## Systembild

Das angestrebte Zielsystem besteht aus mehreren gekoppelten Ebenen:

- elektrisches System mit lokalen und zentralen Erzeugern, Speichern und Netzanbindung
- DH-System mit `dh_bus`, zentralen Quellen, Speichern und thermischer Flexibilitaet im Gebaeudebestand
- Gebaeudebestand mit `residential`- und `non_residential`-Kohorten
- Verkehrsblock mit EV-Lasten, spaeter optional `V2H` / `V2G`
- spaeter optional lokale `EC`- oder Quartierslogik als zusaetzlicher Kopplungslayer

## Wien-2040-Richtung

Fuer Wien 2040 ist das Zielbild:

- stark dekarbonisierte Strombereitstellung
- stark dekarbonisierte Waermeversorgung
- weitgehend elektrifizierter und flexibilisierter Verkehr
- DH als zentraler Infrastrukturpfad fuer urbane Waerme
- Gebaeude-Thermflex als expliziter Flexibilitaetsbaustein
- fossile Resttechnologien hoechstens als Uebergangs-, Reserve- oder Validierungspfad

## Szenario-Logik

Die grobe Szenario-Richtung bleibt:

- `2023` als Referenzwelt
- `2030`, `2035`, `2040` als Transformationspunkte

Der aktuelle enge Paperschnitt fokussiert jedoch zuerst auf:

- Wien-Referenzwelt
- DH-Dispatch
- Gebaeude-Thermflex
- Vergleichsfaelle `baseline_constant_no_thermflex`, `day_night_no_thermflex`, `day_night_thermflex`

## Modellierungslogik

Das Zielsystem soll nicht nur technisch korrekt, sondern auch rechnerisch tractable sein.
Deshalb bleibt die Modellierung in Schichten organisiert:

- physikalische und datenlogische SSOT in `Settings/` und `Data/`
- operative Dispatch-Pfade ueber `milp_day_ahead` und gezielt `milp_two_stage`
- kalibrierte Gebaeudelogik ueber `calibrated_v1` und spaetere Nachfolger
- Surrogat-, Caching- und Budget-Logik im `Learning/`-Layer

## Rolle von J1 / AI

Die J1-/AI-Bausteine sind kein Selbstzweck.
Sie sollen das Modell schneller und zugleich praeziser machen.

Der angestrebte J1-Kern ist:

- `DesignSpace`
- `Evaluator`
- `SurrogateModel`
- `BudgetScheduler`
- `FeasibilityGate`
- `TruthAllocator`
- `ExperimentRunner`

Die Funktion davon ist:

- teure Truth-Laeufe gezielt einsetzen
- bereits bekannte Punkte per Dataset-Reuse/Caching nicht neu rechnen
- schnelle Surrogat-Approximation fuer breite Suchraeume nutzen
- harte Modellgrenzen ueber Gate- und Truth-Logik absichern
- `milp_two_stage` nur dort einsetzen, wo der zusaetzliche Wahrheitsgewinn wirklich relevant ist

## Aktueller Paper-Scope innerhalb des Zielsystems

Der aktuelle Paperschnitt ist kein komplettes Wien-2040-MES.
Er ist ein fokussierter Teil des Zielsystems:

- Wiener DH-System
- thermische Gebaeudeflexibilitaet
- kalibrierte Gebaeudeparameter aus dem `EnergyPlus`-Sidecar
- `milp_day_ahead` als breiter Truth-/Teacher-Pfad
- `milp_two_stage` als gezielte Endpunkt-Validierung
- `xgb`-Surrogat als Beschleuniger fuer weitere Optimierung

## Leitprinzip

Der Modellkern soll so wachsen, dass er:

- physikalisch plausibel bleibt
- rechnerisch tractable bleibt
- dokumentiert und reproduzierbar bleibt
- auf das groessere Wiener MES-Zielbild von `Strom + Waerme + Verkehr` weiter ausgebaut werden kann
