# CO2 ETS Quellen

Dieser Block dokumentiert den aktuellen ETS-/CO2-Preispfad fuer den operativen Dispatch.

## 1. Modellschlussfolgerung

Im aktuellen Dispatch werden CO2-Kosten bewusst **getrennt** von:

- Brennstoffpreis (`OEGPI` fuer Gas)
- LCA-/LCIA-Kategorien

modelliert.

Der operative CO2-Kostenterm ist:

- `co2_cost = fuel_input_mwh * emission_factor_tco2_per_mwh_fuel * co2_price_eur_per_tco2`

Wichtig:

- dafuer wird **kein** LCA-Emissionsfaktor verwendet
- sondern ein direkter Verbrennungsfaktor fuer Erdgas

Aktueller Default fuer Erdgas im Repo:

- `0.202 tCO2/MWh_fuel`

Das entspricht grob:

- `56.1 kg CO2/GJ`

## 2. Preisquelle

Aktueller Repo-Default:

- lokale historische ETS-Datei:
  - `C:\Users\Philipp Thunshirn\Desktop\PhD\Daten\CO2_ETS_price_2020-2026.txt`

Diese Tagesreihe wird auf Monatsmittel aggregiert und als taegliche Monats-Proxyserie
fuer den robusten Modellzeitraum `2020-01-01` bis `2025-12-31` abgelegt unter:

- [ets_monthly_daily_proxy_2020_2025.csv](/c:/Users/Philipp%20Thunshirn/Desktop/PhD/Python%20model/Master/Data/profiles/common/co2/ets_monthly_daily_proxy_2020_2025.csv)

## 3. Offizielle Marktanker

- EEX EU ETS Spot, Futures and Options:
  https://www.eex.com/en/markets/environmental-markets/eu-ets-spot-futures-options?cHash=46ce218ccdf6e9ee1113a96073e2beab&mdrv=www.eex.com

- EEA EU ETS Data:
  https://www.eea.europa.eu/data-and-maps/data/european-union-emissions-trading-scheme-1/eu-ets-data-download-latest-version

## 4. Abgrenzung zum OEGPI

- der normale `OEGPI` ist **kein** automatischer ETS-Vollkostenindex
- laut Methodenbeschreibung existiert eine eigene `OEGPI-Clean`-Familie
- deshalb werden im Repo aktuell:
  - `OEGPI` fuer Gas
  - `ETS` separat fuer CO2

verwendet

## 5. Methodischer Stand

Aktueller Repo-Schnitt:

- Strom:
  - historisch stuendlich ueber `MC Auction`
- Gas:
  - historisch monatlich ueber `OEGPI`
- CO2:
  - historisch monatlich ueber ETS-Monatsmittel

Das ist fuer den operativen Dispatch bewusst asymmetrisch, aber energiemarktwirtschaftlich plausibler
als ein voll stuendlicher Gas-/ETS-Spotpass-through.
