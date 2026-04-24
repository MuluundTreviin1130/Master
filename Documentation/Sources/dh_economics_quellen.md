# DH Economics Quellen und Annahmen

Dieser Block dokumentiert die aktuell verwendeten bzw. bewusst noch offenen Economics-Annahmen fuer den DH-/Thermflex-Pfad.

## 1. Uebernommen aus dem Technology Data Catalogue

Quelle:

- Danish Energy Agency, *Technology Data Catalogue for el and DH*, Kapitel 44 `District Heating Boiler, Gas Fired`
- lokale Datei:
  [Technology Data Catalogue for el and DH - 0017.pdf](/c:/Users/Philipp%20Thunshirn/Desktop/PhD/Daten/CAPEX_OPEX_Data/Technology%20Data%20Catalogue%20for%20el%20and%20DH%20-%200017.pdf)

Aktuell uebernommen fuer `district_gas_boiler`:

- `capex_eur_per_kw_th = 60.0`
  - Herleitung: `0.06 MEUR per MJ/s` im 2020-Datenblatt
  - Annahme: `1 MJ/s = 1 MW_th`
  - daraus: `0.06 MEUR/MW_th = 60 EUR/kW_th`
- `maintenance_rate = 0.0325`
  - Herleitung aus `1,950 EUR/MW_th/year` fixed O&M relativ zu `60,000 EUR/MW_th` CAPEX
- `variable_opex_eur_per_kwh_th = 0.001`
  - Herleitung aus `1.0 EUR/MWh_th other O&M`

Im Repo angeschlossen in:

- [vienna.py](/c:/Users/Philipp%20Thunshirn/Desktop/PhD/Python%20model/Master/Data/economic_data/location/vienna.py)
- [financial_model.py](/c:/Users/Philipp%20Thunshirn/Desktop/PhD/Python%20model/Master/Cost_model/financial_model.py)
- [milp_day_ahead.py](/c:/Users/Philipp%20Thunshirn/Desktop/PhD/Python%20model/Master/dispatch/modes/milp_day_ahead.py)
- [milp_two_stage.py](/c:/Users/Philipp%20Thunshirn/Desktop/PhD/Python%20model/Master/dispatch/modes/milp_two_stage.py)

## 2. Lokale Marktannahmen, nicht Katalogwerte

### Erdgas-Fuel-Costs

Aktuell:

- `district_gas_boiler.fuel_eur_per_m3 = 0.55`
- `district_gas_chp.fuel_eur_per_m3 = 0.55`

Das ist **kein** Technology-Catalogue-Wert, sondern eine lokale Preisannahme.

Einordnung:

- Wenn man grob `10.5 kWh/m3` LHV annimmt, entspricht `0.55 EUR/m3` etwa `52 EUR/MWh_fuel`
- Das liegt grob in der Naehe des oesterreichischen/mitteleuropaeischen Grosshandelsniveaus 2023, aber unter typischen Endkunden-/Retailwerten

Online-Anker:

- E-Control Statistikbroschuere 2023:
  `Kassamarkt Erdgas 2023`, `CEGH (AT) Durchschnitt = 46.52 EUR/MWh`
  - Quelle:
    https://www.e-control.at/documents/1785851/0/E-Control-Statbro-2023-Deutsch.pdf/0e53351d-53f2-957a-0ea4-319aa912a0cf?t=1697713460702
- E-Control Statistikbroschuere 2025:
  `Spotmarkt Erdgas 2023`, `CEGH (AT) Durchschnitt = 41.52 EUR/MWh`
  - Quelle:
    https://www.e-control.at/documents/1785851/1811582/E-Control-Statistikbroschuere-2025-barrierefrei.pdf/d601e4a2-8f47-3b3c-eb78-884b9ade6f8c?t=1765983087192
- Europaeische Kommission, Quartalsbericht zu Gas-/Strommaerkten:
  `average gas retail price in 2023 = 116 EUR/MWh`
  - EU-Durchschnitt, nicht Oesterreich spezifisch
  - Quelle:
    https://energy.ec.europa.eu/news/quarterly-reports-confirm-significant-recovery-eu-gas-and-electricity-markets-4th-quarter-2023-2024-06-06_en
- Statistik Austria:
  offizielle Seite fuer Energiepreise und -steuern, inkl. kommerziellem Einsatz
  - Quelle:
    https://www.statistik.at/statistiken/energie-und-umwelt/energie/energiepreise-steuern
  - Hinweis:
    die Seite belegt die offizielle Datenbasis, der exakte historische kommerzielle Erdgaswert fuer den gewaehlten Fall sollte spaeter direkt aus `STATcube` gezogen werden

Interpretation:

- `0.55 EUR/m3` ist als Proxy fuer einen **markt-/beschaffungsnahen Brennstoffpreis** plausibel
- fuer einen belastbaren Wien-Case sollte spaeter explizit entschieden werden, ob der Modellpreis eher
  - am `CEGH`-Grosshandel,
  - an nicht-haushaltlichen oesterreichischen Endkundenpreisen,
  - oder an einem contract-/utility-spezifischen DH-Gaspreis kalibriert wird

### Heizöl extra leicht fuer Wiener Spitzenkessel-Proxy

Seit `2026-04-21` wird der aktive Wiener `district_gas_boiler`-Economics-Block
nicht mehr als reiner Gaspreis-Proxy gelesen, sondern als expliziter
**fossiler Peak-Boiler-Mix**:

- `2/3 Erdgas`
- `1/3 Heizöl extra leicht`

Grund:

- in den Wiener Quellen sind `Spitzenkessel` explizit als
  `Erdgas oder Heizoel extra leicht` beschrieben
- fuer die aktuelle Thermflex-Peak-Diskussion war die reine Gas-Bepreisung zu
  glatt und zu CO2-arm fuer einen fossilen Peakblock

Preisanker fuer `Heizoel extra leicht`:

- BMWET Wochenreihe `Heizoel Extraleicht: ab 2000 Liter`, Kalenderjahr `2023`
  - lokaler 2023-Mittelwert ueber 52 Wochen: `1.2143 EUR/l`
  - Quelle:
    https://www.bmwet.gv.at/Themen/Energie/kosten/2023.html

Umrechnung auf Fuel-Energy-Basis:

- Statistik Austria Guetereinsatz-Erlaeuterung:
  - `Gasoel fuer Heizzwecke (Heizoel extra leicht) = 0.841 kg/l`
  - Quelle:
    https://www.statistik.at/fileadmin/pages/1150/PI_2024_Erlaeuterung.pdf
- Heizöl-LHV-Proxy:
  - `42.5 MJ/kg` (`= 11.8056 kWh/kg`)
  - daraus `9.9285 kWh/l`
  - Quelle:
    https://www.forestresearch.gov.uk/tools-and-resources/fthr/biomass-energy-resources/reference-biomass/facts-figures/typical-calorific-values-of-fuels/

Ergebnis:

- `Heizoel extra leicht ~= 122.3 EUR/MWh_fuel`

Direkte CO2-Faktoren:

- Erdgas:
  - aktiver Repo-Proxy `0.202 tCO2/MWh_fuel`
- Heizoel extra leicht / gas-diesel-oil Proxy:
  - `0.268 tCO2/MWh_fuel`
  - Herleitung aus `20.2 kg C/GJ` gemaess IPCC 2006
  - Quelle:
    https://www.ipcc-nggip.iges.or.jp/public/2006gl/pdf/2_Volume2/V2_1_Ch1_Introduction.pdf

Aktiver v2-Mix im Wiener Economics-SSOT:

- Preis:
  - `77.4 EUR/MWh_fuel`
  - im aktuellen Runtime-Pfad als `0.774 EUR/m3` gas-aequivalenter Proxy
- CO2:
  - `0.224 tCO2/MWh_fuel`

Wichtiger Methodenhinweis:

- Die Technik bleibt weiter ein einzelner `district_gas_boiler`-Block.
- Nur die Economics-/CO2-Seite repraesentiert jetzt explizit einen Wiener
  fossilen Peakmix.
- Das ist bewusst ein **v2 Proxy**, keine harte historische Brennstoffbilanz.

## 3. Noch offene bzw. nur plausible Proxy-Annahmen

### District Heat Pump

Aktuell:

- `district_heat_pump.capex_eur_per_kw_th = 900`
- `maintenance_rate = 0.02`

Wichtige Kontextannahme:

- Im Wiener Referenzfall wird die zentrale DH-Waermepumpe derzeit fachlich als **Donau-/seawater-type heat pump** interpretiert

Noch offen:

- die aktuelle Economics-Zahl ist **noch nicht sauber auf das Seawater-Datenblatt des Katalogs gemappt**
- Kapitel 40 des Katalogs unterscheidet stark nach:
  - `air source`
  - `industrial excess heat`
  - `seawater`
  - und nach Groesse

Konsequenz:

- `900 EUR/kW_th` ist aktuell nur ein plausibler generischer Proxy
- fuer Wien spaeter explizit auf einen `seawater`-Fall aus Kapitel 40 ziehen

### District Thermal Storage

Aktuell:

- `district_thermal_storage.capex_eur_per_kwh_th = 40`
- `maintenance_rate = 0.01`

Hinweis:

- diese Zahl ist aktuell **nicht** ueber das vorliegende `el and DH`-Katalogdokument sauber belegt
- dafuer spaeter eine belastbarere Storage-Quelle oder ein Storage-Katalog nachziehen

### District External Heat

Aktuell:

- `district_external_heat.variable_opex_eur_per_kwh_th = 0.0`

Interpretation:

- bewusste Modellannahme fuer `must-take` / sehr niedrige Grenzkosten
- keine belastbare generische Katalogzahl

### CHP-Economics

Aktuell plausible, aber noch nicht sauber kataloggemappte Werte:

- `district_gas_chp.capex_eur_per_kw_el = 1400`
- `district_biogas_chp.capex_eur_per_kw_el = 2500`
- `district_biomass_chp.capex_eur_per_kw_th = 2200`

Noch offen:

- sauberer Katalogabgleich
- konsistente Leistungsbasis (`kW_el` vs. `kW_th`)

### Gas-CHP / CCGT mit DH-Extraktion

Der aktuelle `district_gas_chp`-Pfad ist technisch noch bewusst einfach:

- feste `eta_el`
- feste `eta_th`
- also implizit ein **fixes Heat-Power-Verhaeltnis**

Das ist fuer einen ersten Wiener Systembenchmark okay, aber fuer die
Thermflex-/Peakdiskussion methodisch begrenzt:

- reale Extraktions-/Kondensationsanlagen koennen das Verhaeltnis zwischen
  Strom und Waerme verschieben
- ausserhalb elektrischer Spitzen koennen sie mehr Waerme bei geringerem
  Stromoutput bereitstellen als ein starres Kennwertmodell zulaesst

Literatur-/Quellenanker fuer spaeteren Ausbau:

- DEA Technology Catalogue for Electricity and District Heating:
  verweist explizit auf `extraction plants` und getrennte Kapazitaetsbasen
  im Katalog-/Anhangspfad
  - https://ens.dk/en/analyses-and-statistics/technology-data-generation-electricity-and-district-heating
- CCGT + DH mit variablem Power-Heat-Verhalten:
  `Power-heat conversion coordinated control of combined-cycle gas turbine with thermal energy storage in district heating network`
  - https://www.sciencedirect.com/science/article/abs/pii/S1359431122015940
- reduzierte DH-Temperaturen / ECT-Flexibilitaet:
  `Energy-economic assessment of reduced district heating system temperatures`
  - https://www.sciencedirect.com/science/article/pii/S2666955221000113

Konsequenz fuer das aktuelle Repo:

- Die neue fossilere Peak-Boiler-SSOT ist kurzfristig der saubere Hebel.
- Ein variableres Gas-CHP-Kennfeld ist ein eigener methodischer Schritt und
  sollte nicht als stilles Nebenupdate in die aktuelle Thermflex-Paperlinie
  rutschen.

## 4. Methodischer Hinweis

Fuel costs und technology costs muessen im Modell getrennt gelesen werden:

- `dispatch_cost_eur` nutzt operative Kosten:
  - Markt-/Importpreis
  - Fuel costs
  - variable O&M
  - Unserved penalties
- `npc_eur` nutzt:
  - CAPEX
  - maintenance
  - Fuel costs
  - variable O&M
  - Strom-/Community-Kosten ueber den Finanzpfad

Deshalb ist es korrekt, dass der Technology Catalogue nicht direkt den Wiener `fuel_eur_per_m3` liefert:

- der Katalog ist primaer fuer Technikdaten und Tech-Kosten
- Brennstoffpreise muessen separat als Marktdatenannahme verankert werden
