# Wien- und Dispatch-Quellen

## Externe lokale Dokumente / Daten

- Citiwatt-Indikatoren Wien
  Pfad: `C:\Users\Philipp Thunshirn\Desktop\PhD\Daten\Citiwatt_indicators_Vienna.txt`
  Verwendung:
  - Waermeanker gesamt / residential / non-residential
  - GFA / Volumen
  - Bauperiodenanteile
  - Wien-Energiepotenziale: Solarthermie, Waste, Biomasse, Biogas, Wastewater Heat, Large Wind

- PVGIS PV-Zeitreihe
  Pfad: `C:\Users\Philipp Thunshirn\Desktop\PhD\Daten\PV_GIS_2016-23.csv`
  Verwendung:
  - historische PV-Leistung `P`
  - historische Windbasis `WS10m`
  - gemeinsamer stochastic Datenblock aktuell sinnvoll fuer `2020-2023`

- Donau-Durchfluss Korneuburg
  Pfad: `C:\Users\Philipp Thunshirn\Desktop\PhD\Daten\Korneuburg-Durchfluss-Jahr.xlsx`
  Verwendung:
  - mehrjaehriger Tages-Proxy fuer Wiener Laufwasserkraft / Freudenau
  - Datengrundlage fuer die geglaettete run-of-river-Klimatologie im Vienna-Data-Layer

- Temperatur Wien 2016-2026
  Pfad: `C:\Users\Philipp Thunshirn\Desktop\PhD\Daten\Temperatur_2016_2026.csv`
  Verwendung:
  - stündliche Wiener Außentemperaturbasis über `2016-2025`
  - Datengrundlage für das repo-interne Median-Referenzjahr `8760 h`
  - soll als einheitlicher Wettertreiber für `space_heat`, DH-Vorlauf-/Rücklauf und temperaturabhängige HP-Logik dienen

- Wiener Energiebericht 2025
  Pfad: `C:\Users\Philipp Thunshirn\Downloads\2025.pdf`
  Verwendung:
  - Stromanker Haushalte
  - sektorale Stromaufteilung fuer Wiener Kohortenpfad
  - Plausibilisierung von DH-/Heizungsanteilen

## Offizielle Webquellen

- Wiener Energiebericht 2025
  URL: `https://www.wien.gv.at/spezial/energiebericht/files/Stadt_Wien_Energiebericht_2025.pdf`
  Verwendung:
  - Haushaltsstrom
  - Haushaltszahlen / Wohnflaeche
  - sektorale Einordnung
  - Heizungsart in Hauptwohnsitzwohnungen als Status-quo-Anker fuer 2021/2022:
    - Gesamt `929.195`
    - Fernwaerme `424.146`
    - Zentral `445.054`
    - Elektroheizung `45.884`
    - Einzelofen `14.111`
  - wichtige Semantik:
    - `Zentral` umfasst sowohl gebaeudezentrale Heizungen als auch wohnungszentrale Heizungen wie Etagenheizungen / Gasthermen

- Wiener Chart elektrische Energie nach Sektoren 2023
  URL: `https://stp.wien.gv.at/viennaviz/anonymous/chart/1bca71d5-c66b-44cd-ae23-6dd52a1e7a88/pdf`
  Verwendung:
  - `residential`- und `non_residential_buildings`-Stromanker fuer Wien

- Heizungsart in Hauptwohnsitzwohnungen
  URL: `https://stp.wien.gv.at/viennaviz/anonymous/chart/63be6f47-5f98-4064-a60d-4ac5b0ae20e1/pdf`
  Verwendung:
  - offizielle Wien-Visualisierung zu Heizungsarten im Wohnbereich
  - guter Plausibilitaetsanker dafuer, dass der 2023-Referenzfall ausserhalb von DH nicht als voll-elektrischer HP-Bestand modelliert werden sollte

- Smart-City-Wien Rahmenstrategie: Dokumentation der Berechnungen
  URL: `https://smartcity.wien.gv.at/wp-content/uploads/sites/3/2019/06/Dokumentation-der-Berechnungen-zur-Aktualisierung-der-Smart-City-Wien-Rahmenstrategie.pdf`
  Verwendung:
  - brauchbarer Status-quo-Proxy fuer die Energietraegerverteilung von Raumwaerme und Warmwasser im Wiener Bestand
  - Raumwaerme 2016:
    - Wohngebaeude: Fernwaerme `31,3 %`, Gas `54,7 %`, Erneuerbare `4,3 %`, Strom `5,2 %`, sonstige Fossile `4,5 %`
    - Nicht-Wohngebaeude: Fernwaerme `55,5 %`, Gas `22,6 %`, Erneuerbare `3,0 %`, Strom `11,1 %`, sonstige Fossile `7,8 %`
  - Warmwasser 2016:
    - Wohngebaeude: Fernwaerme `34,1 %`, Gas `47,7 %`, Erneuerbare `1,5 %`, Strom `14,7 %`, sonstige Fossile `2,1 %`
    - Nicht-Wohngebaeude: Fernwaerme `56,3 %`, Gas `18,7 %`, Erneuerbare `1,8 %`, Strom `16,1 %`, sonstige Fossile `7,2 %`
  - methodisch nuetzlich fuer einen groben 2023-Referenzfall, wenn keine bessere 2023-scharfe Energietraegeraufteilung vorliegt

- Studie Gasetagenheizungen im Licht der Energiewende in Wien
  URL: `https://www.wien.gv.at/stadtentwicklung/energie/pdf/gasetagenheizungen-studie.pdf`
  Verwendung:
  - Zusatzanker fuer heutige Warmwasserbereitung in Wien
  - zitiert fuer Wiener Haushalte:
    - Gas deckt rund `47,3 %` des Energieverbrauchs fuer Warmwasser
    - grobe Warmwasser-Nachfrage `~930 kWh pro Person und Jahr`
  - hilfreich fuer die Diskussion, wie lokales Warmwasser ausserhalb DH im 2023-Referenzfall zu behandeln ist

- Stadt Wien: neue Grosswaermepumpe fuer Wien
  URL: `https://www.wien.gv.at/presse/2024/01/10/neue-grosswaermepumpe-fuer-wien`
  Verwendung:
  - offizieller aktueller Fernwaerme-Bestandsanker:
    - Wien Energie versorgt laut Stadt Wien aktuell rund `479.000 Haushalte` und mehr als `8.000 Grosskund*innen` mit Fernwaerme
  - offizieller Zielanker:
    - der Fernwaermeanteil am gesamten Wiener Waermebedarf soll von gut `40 %` auf `56 %` steigen

- Stadt Wien / Wiener Waermeplan 2040
  URL: `https://www.wien.gv.at/stadtentwicklung/energie/pdf/waerme-und-kaelte-2040.pdf`
  Verwendung:
  - strategischer Zielanker fuer die Waermewende in Wien
  - offizielle Aussage, dass Fernwaerme bis 2040 rund `56 %` des Bedarfs fuer Raumwaerme und Warmwasser decken soll

- Stadt Wien: Fernwaerme Heute-Gebiete
  URL: `https://www.wien.gv.at/umwelt/fernwaerme-heute-gebiet`
  Verwendung:
  - offizielle Einordnung, dass bestehende Fernwaermegebiete bereits ueberwiegend fernwaermeversorgt sind
  - wichtige qualitative Grundlage dafuer, dass spaeter eher sektor-/gebiets- oder kohortenspezifische `dh_connected_share`-Annahmen gebraucht werden als nur ein globaler Wert

- Stadt Wien Presse 2025-04-04: Energie statt Deponie
  URL: `https://presse.wien.gv.at/presse/2025/04/04/energie-statt-deponie-wiener-abfallwirtschaft-einzigartig`
  Verwendung:
  - weiterer offizieller aktueller Fernwaerme-Bestandsanker:
    - Wien Energie versorgt rund `460.000 Wohnungen` und rund `7.000 Grosskunden` mit Fernwaerme
  - nuetzlich als Plausibilitaetsbereich fuer heutige DH-Anschlussgroessenordnung

- Wiener Weg zur E-Mobilitaet
  URL: `https://www.wien.gv.at/umwelt/e-mobilitaet`
  Verwendung:
  - offizieller Wien-Zielanker fuer E-Mobilitaet:
    - `2030 circa 30 % aller Autos elektrisch`
    - `2040 100 % der Pkw elektrisch`
  - qualitative Grundlage fuer den separaten EV-Block im Modell

- Statistik Austria, Pkw-Bestand 2025
  URL: `https://www.statistik.at/fileadmin/announcement/2026/02/20260224KfzBestand2025.pdf`
  Verwendung:
  - aktueller Wiener Pkw-Bestand:
    - `741.985`
  - aktueller Wiener Elektro-Pkw-Anteil:
    - `6,1 %`
  - daraus als grobe aktuelle Inferenz:
    - `~45.300` Elektro-Pkw in Wien

- Wien Energie / Stadt am Strom(e)
  URL: `https://positionen.wienenergie.at/wp-content/uploads/2025/06/Stadt-am-Strome.pdf`
  Verwendung:
  - offizieller Wiener Strombedarfs-Szenariorahmen fuer E-Mobilitaet:
    - `2030: 697-915 GWh/a`
    - `2040: 1.775-2.802 GWh/a`
  - wichtiger Zukunftsanker fuer den EV-Block

- Niederoesterreich Wasserstand / Messstelle 207241 Korneuburg
  URL: `https://www.noe.gv.at/wasserstand/#/de/Messstellen/Details/207241/Durchfluss/Jahr`
  Verwendung:
  - offizieller Online-Referenzanker fuer den Donau-Durchfluss bei Korneuburg
  - methodischer Referenzpunkt fuer den Freudenau-Proxy; im Repo aktuell ueber die lokal exportierte Datei
    `Korneuburg-Durchfluss-Jahr.xlsx` als mehrjaehrige Tagesreihe verwendet

- Energie in Zahlen 2025
  URL: `https://www.wien.gv.at/pdf/ma20/energie-in-zahlen2025.pdf`
  Verwendung:
  - Wiener Stromstartmix 2023:
    - PV-Leistung Wien 2023: `164 MWp`
    - Wasserkraftwerke Wien 2023:
      - Freudenau `172 MW`
      - Nußdorf `4,8 MW`
      - Gesamt Wien `178,5 MW`
    - Windkraftanlagen Wien 2023:
      - Gesamt `7,3 MW`
    - Erneuerbare Kraftwerke 2023:
      - Biomasse Simmering `37 MW_th`, `16 MW_el`
      - Deponiegasanlage Rautenweg `1 MW_el`
    - Fossile Kraftwerke 2023:
      - Kraftwerk Donaustadt `347 MW_el`
      - Kraftwerk Simmering `443 MW_el`
    - Müllverbrennungsanlagen 2023:
      - Spittelau `6 MW_el`
      - Pfaffenau `14 MW_el`
      - Simmeringer Haide `9 MW_el`

- Produktion elektrischer Energie aus Erneuerbaren 2023
  URL: `https://stp.wien.gv.at/viennaviz/anonymous/chart/ca894286-95b3-42ce-9d96-adecd4c4e2d9/pdf`
  Verwendung:
  - erneuerbare Wiener Stromerzeugung 2023:
    - Wasserkraft `1.099 GWh`
    - Photovoltaik `197 GWh`
    - biogene Brenn- und Treibstoffe `309 GWh`

- Strom- und Fernwärmeerzeugung der Wien Energie seit 2015
  URL: `https://www.wien.gv.at/statistik/strom-fernwaermeerzeugung`
  Verwendung:
  - Wien-Energie-/Wien-Systemwelt als Startmix-Proxy:
    - Stromerzeugung gesamt 2023 `5.475 GWh`
    - kalorisch `4.050 GWh`
    - Biomasse `85,9 GWh`
    - Wasserkraft `834,4 GWh`
    - Windkraft `398,2 GWh`
  - im Repo aktuell als expliziter 2023-Proxy fuer den lokalen Strommix verwendet, ohne zu behaupten, dass dies exakt nur das Wiener Stadtgebiet abbildet

- Wien Energie TAB-FW 2025-09
  URL: `https://dokumente.wienenergie.at/link/technische-anschlussbedingungen-fernwaerme-tab-fw/`
  Verwendung:
  - aktueller offizieller Anker fuer künftige Netztemperaturabsenkung
  - maximale netzseitige Ruecklauftemperaturen ab 2035
  - formale Grundlage dafuer, dass die Heizkurve im hydraulischen Schema anzugeben ist

- Wien Energie Technische Auslegungsbedingungen 2013
  URL: `https://dokumente.wienenergie.at/wp-content/uploads/technische-auslegungsbedingungen-2013.pdf`
  Verwendung:
  - historische/technische Temperaturkurvenblaetter
  - explizite gleitende Vorlauf-/Ruecklaufkurven ueber Aussentemperatur

- Umweltbundesamt REP-0074
  URL: `https://www.umweltbundesamt.at/fileadmin/site/publikationen/REP0074.pdf`
  Verwendung:
  - historischer Wien-Anker fuer Netztemperaturen:
    Winter bis `150 C`, Sommer mindestens `95 C`, Ruecklauf typischerweise `55-75 C`

- IEA DHC Annex TS4 Guidebook
  URL: `https://www.iea-dhc.org/fileadmin/documents/Annex_TS4/IEA_DHC_Annex_TS4_Guidebook_2023.pdf`
  Verwendung:
  - methodische Grundlage fuer wettergefuehrte DH-Heizkurven auf Basis von Aussentemperatur und kritischen Radiatoren

- Journal: Opportunities and Challenges of Future District Heating Portfolios of an Austrian Utility
  URL: `https://doi.org/10.3390/en13102457`
  Verwendung:
  - wissenschaftlicher Anker fuer den oesterreichischen DH-Kontext
  - modelliert Status quo und Portfoliooptionen eines oesterreichischen DH-Versorgers in einem Dispatch-Optimierungsmodell
  - wichtig fuer die Forschungsrichtung:
    - Flexibilitaetswert von `CHP + heat pumps + storage`
    - Dekarbonisierungspfad bei aehnlicher Kostenlage
  - methodisch nuetzlich fuer unsere spaetere Flex-/Portfolioanalyse, aber nicht die primaere SSOT fuer den Wiener 2023-Status quo

- Wien Energie FAQ: Woher kommt die Fernwärme in Wien?
  URL: `https://www.wienenergie.at/faqs/woher-stammt-die-fernwaerme-in-wien-bislang/`
  Verwendung:
  - offizielle qualitative Einordnung der heutigen Wiener DH-Aufbringung:
    - gut die Haelfte aus erdgasbefeuerter KWK
    - Spitzenabdeckung ueber Heizkraftwerke / Fernheizwerke
    - Rest aus industrieller Abwaerme, Muellverbrennung, Biomasse sowie Erd- und Umgebungswaerme
  - offizieller Fernwaerme-GHG-Anker fuer gelieferte Fernwaerme:
    - `22 g CO2/kWh`

- Wien Energie / TÜV-Zertifikat Energiemix Fernwärme
  URL: `https://dokumente.wienenergie.at/link/fernwaerme-energiemix-tuev-zertifikat/`
  Verwendung:
  - zertifizierte Kategorien fuer den Fernwaermemix nach EAG §88
  - Kategorien:
    - `Erneuerbare Energie`
    - `Abwärme`
    - `KWK-Wärme (fossil)`
    - `Fossile Energie`
    - `Sonstige Energieträger`
  - methodisch wichtig:
    - `Abwärme` ist als eigene Kategorie vom fossilen Block getrennt
    - `Bezug Abwärme` sollte daher im Modell/LCA nicht pauschal als Erdgas modelliert werden

- Wien Energie Umwelterklärung 2021
  URL: `https://dokumente.wienenergie.at/wp-content/uploads/umwelterklaerung-2021.pdf`
  Verwendung:
  - offizielle technische Einordnung der Fernheizwerke:
    - Fernheizwerke sind Spitzenlast-/Reserveanlagen
    - sie arbeiten mit Heißwasser-Spitzenkesseln
    - Brennstoffe: `Erdgas oder Heizöl extra leicht`
  - offizielle technische Einordnung dezentraler Wärmeversorgungsanlagen von Wien Energie:
    - in Gebieten ohne wirtschaftlich sinnvolle Fernwärme betreibt Wien Energie dezentrale Wärmeversorgungsanlagen
    - der überwiegende Anteil davon wird mit `Erdgas` betrieben
    - kleinere Anteile mit Biomasse; zunehmend auch Wärmepumpen

## Repo-interne abgeleitete SSOT-Dateien

- Wiener Energiepotenziale
  [energy_potentials.py](/c:/Users/Philipp%20Thunshirn/Desktop/PhD/Python%20model/Master/Data/energy_potentials/Vienna/energy_potentials.py)
  Nutzung:
  - aus Citiwatt abgeleitete Potenziale im Data-Layer

- Wiener Building Stock
  [building_stock.py](/c:/Users/Philipp%20Thunshirn/Desktop/PhD/Python%20model/Master/Data/building_stock/Vienna/building_stock.py)
  Nutzung:
  - 8 Kohorten `residential` / `non_residential` x Bauperiode
  - Waermeanker je Kohorte
  - offizieller sektoraler Stromanker je Kohorte
  - exogener Profilanker je Kohorte

- Gemeinsames Warmwasserprofil
  Pfad: `Data/profiles/common/usage/usage_profiles.xlsx`
  Nutzung:
  - gemeinsame stündliche DHW-Intensität über `Warmwasserbedarf_W_m2`
  - aktueller Repo-Pfad für DHW in [household_hotwater.py](/c:/Users/Philipp%20Thunshirn/Desktop/PhD/Python%20model/Master/Technical_model/technologies/household_hotwater.py)
  - Einheit:
    - `W/m2`
  - implizite Jahresintensität:
    - rund `15.5 kWh/m2a`

- Wiener thermische Archetypen
  [thermal_archetypes.py](/c:/Users/Philipp%20Thunshirn/Desktop/PhD/Python%20model/Master/Data/thermal_archetypes/Vienna/thermal_archetypes.py)
  Nutzung:
  - U-Werte
  - Flaechenratios pro `GFA`
  - `c_th_wh_per_m2k`

- Wiener DH-Heizkurve
  [network_temperature_curve.py](/c:/Users/Philipp%20Thunshirn/Desktop/PhD/Python%20model/Master/Data/district_heating/Vienna/network_temperature_curve.py)
  Nutzung:
  - feste Wien-v1-Referenzkurve fuer effektiven DH-Bus
  - Stuetzstellen fuer Netzvorlauf / Netzruecklauf ueber Aussentemperatur

- Wiener Median-Temperatur-Referenzjahr
  Pfad: `Data/profiles/Vienna/temperature/Median_Temperatur_Referenzjahr_2016_2025.csv`
  Nutzung:
  - repo-interner stündlicher Median-Wetterpfad aus `2016-2025`
  - ersetzt aktuell den alten Wiener Einzeljahr-Temperaturpfad in `load_profiles()`
  - bildet die Basis für ein typisches Wiener Referenzjahr; Extrem-/Stressjahre sollen bei Bedarf später separat ergänzt werden

- Historische stochastic Szenarien
  [historical_data.py](/c:/Users/Philipp%20Thunshirn/Desktop/PhD/Python%20model/Master/dispatch/scenarios/historical_data.py)
  Nutzung:
  - `baseline + historical residuals`
  - PV ueber PVGIS-`P`
  - Wind ueber PVGIS-`WS10m`
  - MC-only Preislogik

## Wichtige Validierungs-/Smoke-Skripte

- Wien all-tech heuristischer Smoke
  [run_vienna_alltech_heuristic_smoke.py](/c:/Users/Philipp%20Thunshirn/Desktop/PhD/Python%20model/Master/Optimization/validation/model_validation/run_vienna_alltech_heuristic_smoke.py)

- Wien DH MILP Smoke
  [run_vienna_dh_milp_smoke.py](/c:/Users/Philipp%20Thunshirn/Desktop/PhD/Python%20model/Master/Optimization/validation/model_validation/run_vienna_dh_milp_smoke.py)

- Wien Anchor Check
  [run_vienna_anchor_check.py](/c:/Users/Philipp%20Thunshirn/Desktop/PhD/Python%20model/Master/Optimization/validation/model_validation/run_vienna_anchor_check.py)
  Nutzung:
  - prueft offizielle vs. exogene Wiener Stromanker
  - prueft den Wiener Gesamt-Waermeanker gegen `space_heat + hotwater`
  - enthaelt jetzt zusaetzlich einen jaehrlichen Referenz-Bilanzblock fuer:
    - zentralen `district_heat_pump`-Strom
    - separaten EV-Referenzblock
    - gesamte Wiener Referenz-Strombilanz ohne erzwungene Sektorisierung von DH-HP oder EV

- Wien two-stage Smoke
  [run_vienna_two_stage_smoke.py](/c:/Users/Philipp%20Thunshirn/Desktop/PhD/Python%20model/Master/Optimization/validation/model_validation/run_vienna_two_stage_smoke.py)

- Solarthermie Varianten-Smoke

## Ergaenzungen 2026-03-28

- Wien Energie Umwelterklaerung 2025
  URL: `https://positionen.wienenergie.at/wp-content/uploads/2025/06/Umwelterklaerung-2025.pdf`
  Verwendung:
  - offizieller Output-Anker fuer fossile Wiener Stromerzeugung 2023 in der Wien-Energie-/Anlagenwelt:
    - Kraftwerk Donaustadt `1.392,610 GWh_el`
    - Kraftwerk Simmering `2.753,278 GWh_el`
  - im aktuellen Strom-Referenzmix genutzt als Jahresanker fuer `gas_chp`
  - wichtige Semantik:
    - nicht blind mit dem Wiener Endverbrauchsanker gleichsetzen; das ist eine andere Systemgrenze

- Wiener Sonnenstrom-Offensive / Zielerreichung
  URL: `https://www.wien.gv.at/spezial/5-jahre-sonnenstrom-offensive/ziele-und-deren-erreichung/kurzfristige-und-langfristige-zielsetzungen/`
  Verwendung:
  - offizieller PV-Bestandsanker 2025:
    - Ende September 2025 `308 MWp`
  - im aktuellen Strom-Referenzmix genutzt fuer den PV-2025-Proxy:
    - `197 GWh/a * 308 / 164 = 369,98 GWh/a`

- Klimafahrplan Wien: Strom- und Fernwaermeerzeugung
  URL: `https://www.wien.gv.at/spezial/klimafahrplan/klimaschutz-wien-wird-klimaneutral/strom-und-fernwarmeerzeugung/`
  Verwendung:
  - offizielle Grundlage gegen einen abrupten fossilen Sofortausstieg im Modell
  - wichtige Aussage:
    - Wien wird auch in einer CO2-freien Zukunft gasbetriebene Anlagen fuer Strom- und Fernwaerme brauchen, besonders fuer Spitzenlastzeiten
  - methodische Folge fuer Szenarien:
    - gestufter Phase-out / Restreserve statt harter Binärschalter

- Stadt Wien: Waerme und Kaelte 2040
  URL: `https://www.wien.gv.at/umwelt/waerme-und-kaelte-2040`
  Verwendung:
  - offizieller Zielrahmen fuer die Wiener Waermewende
  - methodische Grundlage fuer:
    - steigenden DH-Anteil
    - sinkende fossile Einzelversorgung
    - Transformationspfad `2023 -> 2030 -> 2035 -> 2040`

- Aktuell verwendete Wiener Strom-Erzeugungsanker im Referenzmix
  Verwendung:
  - Laufwasser:
    - Leistung aus `Energie in Zahlen 2025`
    - Jahreserzeugung aus `Produktion elektrischer Energie aus Erneuerbaren 2023`
  - PV:
    - `2023` Jahresanker `197 GWh`
    - `2025` Proxy `369,98 GWh`
    - Stundenform ueber PVGIS-Zeitreihe
  - Wind:
    - Jahresanker `398,2 GWh` aus `Strom- und Fernwaermeerzeugung der Wien Energie seit 2015`
    - Stundenform ueber Wiener Windprofil / PVGIS-basierte Wetterzeitreihe
  - Biomass CHP:
    - Jahresanker `85,9 GWh` aus `Strom- und Fernwaermeerzeugung der Wien Energie seit 2015`
  - Waste-to-power:
    - Leistungsanker `29 MW_el` aus `Energie in Zahlen 2025`
    - aktuell als konstanter Jahresproxy modelliert
  - Gas CHP:
    - Jahresanker Simmering + Donaustadt aus `Wien Energie Umwelterklaerung 2025`
    - Stundenform aktuell als DH-lastnaher Proxy
  [run_solar_thermal_smoke.py](/c:/Users/Philipp%20Thunshirn/Desktop/PhD/Python%20model/Master/Optimization/validation/model_validation/run_solar_thermal_smoke.py)

## Methodische Notizen

- Citiwatt-`Heat demand` wird im neuen Wiener Kohortenpfad aktuell als Gesamtwaermeanker `space_heat + hotwater` interpretiert.
- Im aktuell verdrahteten Repo stammt die Warmwasser-Zeitreihe jedoch nicht aus Citiwatt, sondern aus `usage_profiles.xlsx` ueber `Warmwasserbedarf_W_m2` (`W/m2`).
- Wenn eine separate Citiwatt-DHW-Zeitreihe verfuegbar wird, waere das die sauberere Grundlage fuer die Aufteilung von Gesamtwaerme auf `space_heat` und `hotwater`.
- Fuer einen Wiener 2023-Referenzfall sollte ausserhalb von DH aktuell **nicht** implizit von voll-elektrischer Heiz- und Warmwasserbereitstellung ausgegangen werden:
  - offizielle Heizungsart-Daten zeigen weiter einen sehr grossen Block `Zentral` im Wohnbereich
  - Smart-City-Wien / MA20 deuten fuer Status quo klar auf gasdominierte Nicht-DH-Raumwaerme und lokal ausserhalb DH weiterhin relevante Gas- und Stromanteile bei Warmwasser
- Abgeleiteter schlanker 2023-Referenzschnitt fuer das Modell:
  - fuer die Stromkalibrierung ist primaer relevant, welcher Anteil der Nicht-DH-Waerme **elektrisch** ist;
    Gas / sonstige Fossile / Erneuerbare muessen dafuer nicht sofort technologisch ausmodelliert werden
  - vorgeschlagene elektrische Nicht-DH-Anteile als Proxy aus Smart-City-Wien 2016, auf den Nicht-DH-Block normiert:
    - `residential_space_heat_non_dh_electric_share ≈ 7,6 %`
    - `residential_hotwater_non_dh_electric_share ≈ 22,3 %`
    - `non_residential_space_heat_non_dh_electric_share ≈ 24,9 %`
    - `non_residential_hotwater_non_dh_electric_share ≈ 36,8 %`
  - Wohnungsseitiger Plausibilitaetscheck aus der offiziellen Heizungsarten-Statistik 2021/2022:
    - unter den Nicht-DH-Hauptwohnsitzwohnungen entfallen grob `88,1 %` auf `Zentral`, `9,1 %` auf `Elektroheizung` und `2,8 %` auf `Einzelofen`
  - fuer den aktuellen Repo-Schnitt bedeutet das:
    - Nicht-DH-Raumwaerme 2023 nicht pauschal als HP-elektrisch modellieren
    - lokales Warmwasser ausserhalb DH 2023 nicht pauschal als voll-elektrisch modellieren
    - `non_residential_hotwater = 0` bleibt im aktuellen V1-Modell weiterhin eine bewusste Vereinfachung, auch wenn die Status-quo-Quellen dort spaeter einen positiven Anteil nahelegen
- DH-Aufbringungsbloecke 2023 fuer Modell/LCA:
  - `Spitzenkessel`:
    - offizielle technische Grundlage: Fernheizwerke / Heisswasser-Spitzenkessel
    - Brennstoffe: `Erdgas` oder `Heizoel extra leicht`
    - fuer GHG/LCA daher fossiler Peak-Boiler-Proxy
    - alter v1-Stand: primaer gasbasiert, Heizoel nur als Reserve-/Mischrisiko dokumentieren
    - aktiver v2-Stand seit `2026-04-21`: Economics-/CO2-Proxy mit explizitem
      `2/3 Gas + 1/3 Heizoel extra leicht` Mischanteil fuer den Wiener
      Spitzenkessel-/Heizzentralen-Block
  - `Heizzentralen`:
    - keine gleichwertig klare 2023-Quellenstelle gefunden, die den Brennstoff dieser Statistikposition direkt ausweist
    - beste offizielle Naeherung derzeit:
      Wien Energie betreibt dezentrale Waermeversorgungsanlagen, deren ueberwiegender Anteil mit `Erdgas` betrieben wird
    - methodische Inferenz:
      `Heizzentralen` vorerst als gasdominierter Restblock modellieren, aber explizit als Inferenz dokumentieren und nicht als harte Wahrheit ausgeben
  - `Bezug Abwärme` / externer Wärmebezug:
    - im Jahresbericht explizit als `Bezug Abwärme` ausgewiesen
    - Wien Energie ordnet den nicht-fossilen Rest der Fernwaerme u. a. `industrieller Abwärme` zu
    - im Energiemix-Zertifikat ist `Abwärme` explizit getrennt von `fossiler Energie`
    - fuer GHG/LCA daher **nicht** mit Erdgas gleichsetzen; eigener niedrigerer Proxy bzw. spaeter saubere Waste-Heat-/Purchased-Heat-SSOT noetig
- konkrete 2023-Groessenordnung aus Enable DHC Factsheet Wien, Tabelle 1:
  - `KWK WIEN ENERGIE = 2.569,6 GWh`
  - `Muell- und Sondermuellverbrennung (eigene) = 1.200,0 GWh`
  - `Spitzenkessel = 522,3 GWh`
  - `Erd- und Umgebungsenergie = 96,0 GWh`
  - `Heizzentralen = 206,3 GWh`
  - `Biomassekraftwerk = 117,4 GWh`
  - `Bezug Abwaerme = 1.200,9 GWh`
  - `Netzverluste = -485,0 GWh`
  - `Absatz Fernwaerme = 5.427,4 GWh`
  - Modellschluss fuer den 2023-Benchmark:
    - `district_external_heat` als expliziter `Bezug Abwaerme`-/Industrieabwaerme-Block
    - `district_waste_incineration` bleibt im aktuellen Wiener 2023-Referenzpreset vorerst auf die
      aktuell im Repo erzwungene Potenzialgrenze gekappt (`~108 MW_th`);
      der Widerspruch zum offiziellen 2023-Jahresanker `~1,2 TWh/a` ist bewusst offen und in `Documentation/Planning/TODO.md` notiert
    - `district_waste_incineration` wird im aktuellen heuristischen Referenzpfad technisch als
      `must-run`-/baseload-artige DH-Quelle behandelt; Ueberschuesse duerfen in Speicher oder Spillage laufen,
      statt dass Waste nur residual nach Restlast gefahren wird
    - `district_gas_boiler` als v1-Proxy fuer `Spitzenkessel + Heizzentralen`
    - fuer den aktuellen vereinfachten Winterbenchmark braucht `district_gas_boiler` in der Januarwoche `2023-01-15` einen winter-fit Peakblock von grob `2,2 GW_th`, damit `dh_unserved_heat = 0`; dieser Wert ist ein Validation-Proxy, keine harte historische Kapazitaetsaussage
  - Quelle:
    - Enable DHC Factsheet Wien 2025
    - URL: `https://enabledhc.ambienteitalia.it/wp-content/uploads/2025/06/D2.2-Wien-Deutsch.pdf`
- Die offiziellen Wiener Daten sind fuer die 2023-Kalibrierung wichtiger als Journal-Literatur;
  Journals sind hier vor allem methodischer Anker fuer spaetere Flexibilitaets- und Portfolioanalysen.
- Der Stromschnitt ist im Wiener `building_stock` jetzt explizit getrennt in:
  - offiziellen sektoralen Stromanker
  - exogenen Profilanker fuer die `load_profile`-Skalierung
- Im aktuellen 2023-Kalibrierungsstand sind beide Groessen bewusst **nicht** gleich:
  der exogene Profilanker ist jetzt aus einem expliziten 2023-End-Use-Proxy abgeleitet.
  Aktuelle Wiener Exogen-Anker:
  - `residential: 2.7378 TWh/a`
  - `non_residential_buildings: 2.2641 TWh/a`
  - `total: 5.0019 TWh/a`
  Herleitung:
  - offizieller Wiener Gebaeude-Stromanker
  - minus modellierte lokale thermische Elektrizitaet im 2023-Proxy
    (`space_heat`, `hotwater`, `cooling` ausserhalb DH)
- `dh_connected_share` ist aktuell global ueber `district_heating.share` und noch nicht kohortenspezifisch.
- Fuer Wien gibt es aus offiziellen Quellen belastbare globale Anker und Ziele fuer Fernwaerme:
  - aktueller Bestandsanker grob `460.000-479.000` Wohnungen/Haushalte plus `7.000-8.000` Grosskund*innen,
  - strategischer Zielanker: rund `56 %` des Wiener Bedarfs fuer Raumwaerme und Warmwasser bis 2040.
- Fuer Wien gibt es jetzt auch erste belastbare EV-Anker:
  - aktueller BEV-Bestand grob `~45.300` als Inferenz aus offiziellem Wiener Pkw-Bestand und offiziellem Elektro-Anteil
  - grober heutiger BEV-Stromanker `~118 GWh/a` als V1-Inferenz
  - offizielle Wiener Zukunfts-Szenarien fuer E-Mobilitaet:
    - `2030: 697-915 GWh/a`
    - `2040: 1.775-2.802 GWh/a`
  Details und Herleitung in:
  [wien_ev_quellen.md](/c:/Users/Philipp%20Thunshirn/Desktop/PhD/Python%20model/Master/Documentation/Sources/wien_ev_quellen.md)
- Solarthermie ist im Produktionspfad inzwischen paketbasiert (`oemof.thermal`) und am DH-Bus als `direct_feed -> preheat -> storage -> spill` verdrahtet;
  offen ist aktuell vor allem noch die staerkere temperaturseitige Rueckkopplung auf HP/CHP/Boiler statt `preheat` nur als Restlastreduktion zu behandeln.
- Die Heizkurven-/Temperaturquellen fuer den künftigen DH-Temperaturpfad sind separat gesammelt in:
  [dh_heizkurve_quellen.md](/c:/Users/Philipp%20Thunshirn/Desktop/PhD/Python%20model/Master/Documentation/Sources/dh_heizkurve_quellen.md)
