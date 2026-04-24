# Gas Procurement Quellen und Modellierungsschnitt

Dieser Block dokumentiert die relevanten Marktquellen fuer gasseitige Beschaffung im DH-/CHP-Dispatch und den daraus abgeleiteten Modellierungsschnitt.

## 1. Warum Gas nicht wie Strom modelliert werden sollte

Im aktuellen IES-/Dispatchpfad ist Strom sauber ueber stueckweise kurzfristige Marktpreise (`MC Auction`) an den stuentlichen Dispatch gekoppelt.

Fuer Erdgas ist dieselbe Logik nur eingeschraenkt realistisch:

- Gas wird von Utilities typischerweise nicht vollstaendig stuentlich spotbasiert beschafft
- ueblich ist eher ein Portfolio aus:
  - vorab gehedgten Mengen
  - taeglicher Prompt-Beschaffung
  - kurzfristigem Balancing / Imbalance

Fuer den Modellpfad bedeutet das:

- konstante `fuel_eur_per_m3` sind zu grob
- ein reiner hourly-spot-pass-through ist aber ebenfalls zu aggressiv
- ein gestufter Beschaffungsschnitt ist methodisch am plausibelsten

## 2. Relevante Marktquellen

### CEGH / EEX Gas Spot und Futures

- CEGH Product Specifications
  - zeigt Within-Day, Day-Ahead und Futures-Produkte fuer `CEGH VTP Austria`
  - Quelle:
    https://www.cegh.at/en/exchange-market/product-specifications/

- EEX Natural Gas Spot
  - offizielle Uebersicht der EEX Gas Spot Maerkte
  - Quelle:
    https://www.eex.com/en/markets/natural-gas/gas-spot

- EEX EGSI Futures / CEGH Futures
  - offizieller Futures-Zugang fuer Gasmarktprodukte
  - Quelle:
    https://www.eex.com/en/markets/natural-gas/egsi-futures

### CEGHIX / Day-Ahead-Preisanker

- CEGHIX Spezifikation
  - CEGHIX ist der taegliche Spot-/Day-Ahead-Index fuer den CEGH-Markt
  - historische CEGHIX-Daten werden dort explizit als Powernext/EEX-Datenprodukt beschrieben
  - Quelle:
    https://www.cegh.at/wp-content/uploads/2023/05/Specification-CEGHIX.pdf

- CEGH Indices
  - offizielle Index-Uebersicht
  - Quelle:
    https://www.cegh.at/en/exchange-market/eex-cegh-indices/

### Marktstatistik Spot vs. Futures

- CEGH Result Year 2025
  - offizieller Jahresbericht mit Marktvolumina fuer den oesterreichischen EEX CEGH Markt
  - 2025: `Spot = 154.12 TWh`, `Futures = 216.96 TWh`
  - das ist ein brauchbarer Marktanker fuer die grobe Einordnung Spot vs. Futures
  - Quelle:
    https://www.cegh.at/wp-content/uploads/2026/02/CEGH-Result_Year_2025.pdf

- CEGH Market Statistics
  - offizielle Marktstatistik und Churn-Rate des Hubs
  - Quelle:
    https://www.cegh.at/en/services/cegh-gas-market-statistics/

### Historische Datenverfuegbarkeit

- EEX Group DataSource sFTP
  - beschreibt End-of-Day-, historische und aktuelle Datenprodukte fuer Spot und Futures
  - Quelle:
    https://www.eex.com/en/market-data/eex-group-datasource/sftp-server

- EEX Group DataSource Interface Specification
  - dokumentiert u. a. die Dateinamen fuer historische Spot-/Futures-Dateien
  - relevant:
    - `GasSpotHistory_CEGH_VTP_YYYY.xlsx`
    - `GasFutureHistory_CEGH_VTP_YYYY.xlsx`
  - Quelle:
    https://www.eex.com/fileadmin/EEX/Downloads/Market_Data/EEX_Group_DataSource/sFTP_Server/eex-market-data-sftp-xlsx--interface-specification-en-data.pdf

## 3. Modellschlussfolgerung

### Aktueller Repo-Schnitt

Der Dispatch kann jetzt zeitvariable Gaspreise ueber explizite Serien verarbeiten:

- `district_gas_day_ahead_price_eur_per_mwh_fuel`
- optional zusaetzlich `district_gas_balance_price_eur_per_mwh_fuel`

Die Legacy-Serie

- `district_gas_price_eur_per_mwh_fuel`

bleibt nur als Rueckwaertskompatibilitaetsalias fuer den Day-Ahead-Pfad erhalten.

Wenn keine explizite Gaspreisserie vorhanden ist, faellt der einfache Pfad auf die bisherige lokale Economics-Annahme

- `fuel_eur_per_m3`

umgerechnet in `EUR/MWh_fuel` zurueck.

Aktueller historischer Default fuer die Basisgaspreise im Repo:

- `ÖGPI Monat` aus `oegpi_data.xlsx`
- als taegliche Monats-Proxyserie auf den gemeinsamen robusten Dispatch-Zeitraum `2020-01-01` bis `2025-12-31` gemappt
- bewusst dieselbe robuste Zeitabdeckung wie der historische `MC Auction`-Strompfad
- nicht als stuentlicher Spotpreis, sondern als exogener monatlicher Beschaffungsproxy

Fuer den **Procurement-Mode** gibt es dagegen **keine** stillen Preisaufschlaege oder Markup-Faktoren:

- Day-Ahead und Balance muessen dort explizit als getrennte Preisserien vorliegen
- fehlen diese Serien, bricht der Lauf bewusst ab

### Empfohlener Zielpfad

High-end und energiemarktwirtschaftlich plausibel ist:

1. Hedge-/Portfolio-Layer
   - Futures / Forwardpreis fuer gehedgte Mengen
2. Prompt-Layer
   - taeglicher `CEGHIX` / Day-Ahead-Preis fuer Restmengen
3. Balancing-Layer
   - Within-Day / Hourly nur fuer kurzfristige Abweichungen

### Offene Methodenentscheidung

Der aktuelle High-End-Zielpfad im Repo ist:

- First stage:
  - gemeinsame Gasbasisbeschaffung ueber `district_gas_day_ahead_price_eur_per_mwh_fuel`
- Second stage:
  - szenarioweise Nachbeschaffung ueber `district_gas_balance_price_eur_per_mwh_fuel`

Noch offen ist, ob der Repo-Pfad spaeter:

- zunaechst nur exogene Gaspreiszeitreihen verwendet
  - z. B. `CEGHIX` daily
- oder echte Beschaffungsvariablen in `milp_two_stage` modelliert
  - `q_hedge`
  - `q_prompt`
  - `q_balance`

### Warum zunaechst OEGPI statt CEGH-Front-Month-Historie

- `CEGH 1FM Reference Index` waere fachlich ein sehr guter Marktanker fuer eine prompt-/front-month-nahe Gasbeschaffung
- frei verfuegbar war fuer den aktuellen Schnitt jedoch keine belastbare lange Historie auffindbar
- `ÖGPI` ist dagegen lokal vorhanden, sauber dokumentiert und reicht lang genug zurueck
- damit ist `ÖGPI` aktuell der pragmatisch beste lange Gaspreisanker, obwohl er nur monatlich und nicht taeglich/stuendlich aufgeloest ist

## 4. Wichtige methodische Klarstellung

Die Marktstatistik liefert **keinen echten Wiener Utility-Hedge-Anteil**.

Also:

- Spot-/Futures-Volumina des Hubs sind **kein** direkter Proxy fuer den Wiener Fernwaerme-Beschaffungsmix
- diese Zahlen helfen nur, die Marktlogik und die Groessenordnung des Marktes zu verstehen
- ein konkreter Utility-Beschaffungsmix muesste entweder:
  - aus unternehmensnaher Literatur / Disclosure kommen
  - oder explizit als Modellannahme gesetzt werden
