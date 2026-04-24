# Solarthermie in DH: Literatur- und Tool-Notizen

## Kernfazit fuer unseren Anwendungsfall

- Klassische grosse Solarthermie in Fernwaermenetzen wird in der Literatur typischerweise fuer mittlere bis hohe DH-Temperaturniveaus eingesetzt, aber der Standardbereich liegt eher bei `80-120 C` als bei `150 C` direkter Wintereinspeisung.
- Literatur und Praxis unterscheiden im Wesentlichen drei Integrationsarten:
  - `direct_feed`, wenn das Kollektorfeld das erforderliche Netztemperaturniveau erreicht,
  - `return_preheat`, wenn der Ruecklauf vorgewaermt wird,
  - `storage_or_booster`, wenn Solarwaerme erst gespeichert oder ueber Waermepumpe/Zusatzheizer auf das Vorlaufniveau gebracht wird.
- Je hoeher das Temperaturniveau, desto staerker sinkt der nutzbare Ertrag durch thermische Verluste.
- `150 C` sollte daher fuer unseren Produktionspfad nicht als stiller Standard fuer direkte Einspeisung angenommen werden.

## Primaerquellen

- IEA SHC Task 68 Report RA1
  Link: `https://www.iea-shc.org/Data/Sites/1/publications/IEA-SHC-Task68--Report-RA1.pdf`
  Relevante Aussagen:
  - fuer Fernwaermenetze liegt das Temperaturniveau oft im Bereich `80 C bis 120 C`
  - Solarthermie kann entweder die Vorlauftemperatur liefern oder den Ruecklauf vorwaermen
  - fuer hohe Solarfraktionen werden Speicher zentral
  - bei hoeheren Kollektortemperaturen sinkt der Ertrag; fuer `>75 C` koennen andere Kollektortypen Vorteile bekommen
  - Parabolic trough / Fresnel werden fuer breitere bzw. hoehere Temperaturbereiche explizit genannt

- IEA SHC Task 68 Info Package
  Link: `https://task68.iea-shc.org/Data/Sites/1/publications/Solar-District-Heating-Info-Package-of-IEA-SHC-Task-68.pdf`
  Relevante Aussagen:
  - grosse reale SDH-Anlagen koppeln Solarthermie typischerweise mit Biomasse, Speicher oder Waermepumpen
  - im Beispiel Pristina werden Absorptionswaermepumpen genutzt, um Wasser aus dem saisonalen Speicher auf das Niveau der Versorgungsleitung anzuheben

- Tschopp et al., Applied Energy 2020
  DOI: `https://doi.org/10.1016/j.apenergy.2020.114997`
  Relevanz:
  - Ueberblick ueber grosse SDH-Systeme in fuehrenden Laendern
  - guter Referenzanker fuer typische Solarfraktionen, Speicherkonzepte und Integrationsarten

- Xu et al., Renewable Energy 2024
  DOI: `https://doi.org/10.1016/j.renene.2024.121490`
  Relevanz:
  - Solar district heating + Luft/Wasser-Waermepumpe + Speicher
  - methodisch nah an `preheat/storage/booster`

- Pans et al., Energy Conversion and Management 2023
  DOI: `https://doi.org/10.1016/j.enconman.2022.116545`
  Relevanz:
  - stundenweise Modellierung von DH mit erneuerbaren Waermequellen und thermischem Speicher
  - gutes methodisches Vorbild fuer unseren Dispatch-Schnitt

## Tooling / Pakete

- `oemof.thermal`
  Doku: `https://oemof-thermal.readthedocs.io/en/latest/`
  Staerken:
  - Solarthermiekollektor
  - stratified thermal storage
  - optimierungsnah
  Einschraenkung:
  - kein fertiger Fernwaerme-Entscheider fuer `direct_feed` vs `return_preheat` vs `booster`

- `TESPy`
  Doku: `https://tespy.readthedocs.io/en/dev/basic_tutorials/district_heating.html`
  Staerken:
  - thermodynamische Netz- und Komponentenmodelle
  - Temperaturen, Massenstroeme, HEX
  Einschraenkung:
  - kein Jahresdispatch-/Optimierungsframework wie unser Repo

- `DisHeatLib` / Modelica
  Doku: `https://build.openmodelica.org/Documentation/DisHeatLib.html`
  Staerken:
  - detaillierte dynamische Fernwaermenetzsimulation
  - hydraulisch-thermische Validierung
  Einschraenkung:
  - eher High-Fidelity-Validierung als schlanker Produktionskern

- `TRNSYS`
  In der SDH-Literatur sehr haeufig fuer detaillierte Solarthermie-/Speicher-/DH-Simulation.
  Einschraenkung:
  - eher Referenz- und Validierungsumgebung als Repo-Kern

## Paketentscheidung fuer unser Repo

- Wenn mit "Paket" der **Kollektor- und Temperaturphysik-Kern** gemeint ist, ist fuer unseren Schnitt `oemof.thermal` aktuell die beste Passung.
- Grund:
  - `oemof.thermal.solar_thermal_collector` bildet die uebliche flache Kollektorgleichung mit `eta_0`, `a_1`, `a_2`, Einstrahlung, Umgebungstemperatur und Kollektor-Eintrittstemperatur ab.
  - `oemof.thermal.stratified_thermal_storage` passt methodisch gut zu unserem DH-Speicherpfad.
  - Das Paket ist deutlich schlanker fuer einen stundenweisen Produktionspfad als ein volles thermodynamisches Netzmodell.
- `TESPy` bleibt trotzdem relevant:
  - nicht als erster Produktionskern,
  - sondern spaeter als Sidecar-Validierung fuer ausgewaehlte Temperatur-/Massenstromfaelle.
- Konsequenz fuer die Implementierung:
  - **Kollektorphysik** aus Paket + Literatur,
  - **DH-Logik** (`direct_feed`, `return_preheat`, `storage`, `booster`) weiter im Repo.
- Wichtige methodische Einschraenkung von `oemof.thermal` fuer unseren Fall:
  - `flat_plate_precalc(...)` berechnet den nutzbaren Kollektorertrag fuer ein **vorgegebenes Temperaturniveau**.
  - Das Paket loest damit nicht von selbst die Frage: "Welche maximale Einspeisetemperatur ist in Stunde `t` erreichbar?"
  - Diese Frage muss im Repo zusaetzlich formuliert werden, z. B. als:
    - iterative Suche ueber moegliche Zieltemperaturen,
    - oder explizite Betriebslogik `direct_feed` / `return_preheat` / `storage`.
- Aktueller Repo-Schnitt v1:
  - `oemof.thermal` wird fuer die Kollektorphysik verwendet,
  - `GHI` wird explizit ueber `Erbs` zu `DHI/DNI` zerlegt,
  - die Solarthermie-Verfuegbarkeit wird vektorisiert ueber die Stundenserie vorbereitet,
  - der heuristische IES-/DH-Bus nutzt jetzt `direct_feed`, `return_preheat`, `storage_charge` und `spill`,
  - der gekoppelte MILP-Pfad nutzt jetzt denselben Schnitt ueber getrennte Serien fuer
    direkte Hochtemperatur-Verfuegbarkeit und gesamte nutzbare Solarwaerme;
    im Result werden `district_solar_thermal_direct_feed`,
    `district_solar_thermal_preheat` und `district_solar_thermal_storage_charge` explizit ausgewiesen.
- Wichtige Abgrenzung:
  - Die aktuelle Logik in [district_solar_thermal.py](/c:/Users/Philipp%20Thunshirn/Desktop/PhD/Python%20model/Master/Technical_model/technologies/district_heating/sources/district_solar_thermal.py) ist damit nur als provisorischer Repo-Entwurf zu verstehen und noch **nicht** die finale fachliche Grundlage.

## Erbs-Modell fuer die Strahlungszerlegung

- `Erbs` ist ein empirisches **Decomposition Model**, das aus gemessener oder gegebener `GHI` die Komponenten `DHI` und `DNI` abschaetzt.
- In `pvlib` ist das direkt verfuegbar als:
  - `pvlib.irradiance.erbs(ghi, zenith, datetime_or_doy)`
- Relevanz fuer unseren Fall:
  - Wenn wir `collector_tilt_deg` und `collector_azimuth_deg` in `oemof.thermal.flat_plate_precalc(...)` wirklich aktiv nutzen wollen,
    brauchen wir nicht nur horizontale Gesamtstrahlung, sondern auch eine Zerlegung in direkte und diffuse Anteile.
  - `oemof.thermal.flat_plate_precalc(...)` erwartet dafuer explizit:
    - `irradiance_global`
    - `irradiance_diffuse`
- V1-Schnitt fuer das Repo:
  - Wenn nur `GHI` vorliegt und `tilt/azimuth` aktiv genutzt werden sollen, dann `Erbs` **explizit** als Zerlegungsmodell setzen.
  - Kein stilles Erfinden von `DHI`.
- Quellen:
  - pvlib decomposition overview:
    `https://pvlib-python.readthedocs.io/en/stable/reference/irradiance/decomposition.html`
  - pvlib `erbs` API:
    `https://pvlib-python.readthedocs.io/en/latest/reference/generated/pvlib.irradiance.erbs.html`
  - Original paper:
    D. G. Erbs, S. A. Klein, J. A. Duffie (1982),
    `Estimation of the diffuse radiation fraction for hourly, daily and monthly-average global radiation`,
    Solar Energy 28(4), 293-302,
    DOI: `https://doi.org/10.1016/0038-092X(82)90302-4`

## Repräsentative Wien-Koordinate fuer die Kollektor-Transposition

- Fuer Wien-v1 ist der sauberste Referenzpunkt der meteorologische Standort
  `Wien-Hohe Warte` (`WMO 11035`), nicht ein frei gewaehlter Stadtmittelpunkt.
- Verwendbare Koordinate:
  - `latitude = 48.2486`
  - `longitude = 16.3564`
  - gerundet aus `48°14'55"N`, `16°21'23"E`
- Warum dieser Punkt:
  - Er ist meteorologisch etabliert und naheliegend zu den bereits verwendeten Wiener Wetter-/Temperaturpfaden.
  - Er ist fuer v1 deutlich belastbarer als ein beliebiger Stadtzentrumspunkt.
- Quellen:
  - NHESS Supplement Table S1 mit Liste der GeoSphere-Austria-Stationen im Wiener Raum:
    `https://nhess.copernicus.org/articles/25/4807/2025/nhess-25-4807-2025-supplement.pdf`
    Eintrag `11035 Wien-Hohe Warte`: `16°21'23"`, `48°14'55"`, `198 m`
  - ECA&D station detail:
    `https://www.ecad.eu/utils/stationdetail.php?stationid=16`

## Umrechnung `installed_kw_th -> collector_area_m2`

- `oemof.thermal` arbeitet kollektor- und strahlungsseitig, nicht direkt mit einer installierten thermischen Nennleistung.
- Fuer den Repo-Schnitt brauchen wir deshalb eine explizite Modellkonvention, wie aus
  `installed_kw_th` eine Kollektorflaeche wird.
- Fuer den jetzt verwendeten v1-Pfad nutzen wir die IEA-SHC-Nominalkapazitaet fuer verglaste Flachkollektoren:
  - `specific_nominal_capacity_kw_per_m2 = 0.671`
  - damit `collector_area_m2 = installed_kw_th / 0.671`
- Quelle:
  - IEA SHC Technical Note:
    `https://www.iea-shc.org/data/sites/1/documents/statistics/technical_note-new_solar_thermal_statistics_Conversion.pdf`
  - dort:
    - typische Kennwerte fuer verglaste Flachkollektoren:
      `eta_0 = 0.78`, `a_1 = 3.2`, `a_2 = 0.015`
    - typische Betriebsbedingungen fuer die Nennleistung:
      `G = 1000 W/m²`, `Ta = 20 °C`, `Tm = 50 °C`
    - resultierende spezifische Nennkapazitaet:
      `P/A = 0.671 kWth/m²`
- Wichtig fuer das Repo:
  - `installed_kw_th` ist damit v1-seitig als installierte nominelle thermische Kollektorleistung im Sinn dieser IEA-SHC-Umrechnung zu verstehen.
  - Kein stilles Ableiten der Flaeche mehr; die Umrechnung ist explizit an eine zitierte Quelle gebunden.

## Verwendete v1-Kollektorparameter und Ausrichtung

- Verwendeter Kollektortyp im Repo-v1:
  - verglaster Flachkollektor
  - `eta_0 = 0.78`
  - `a_1 = 3.2 W/(K*m²)`
  - `a_2 = 0.015 W/(K²*m²)`
  - `specific_nominal_capacity_kw_per_m2 = 0.671`
- Quelle:
  - IEA SHC Technical Note:
    `https://www.iea-shc.org/data/sites/1/documents/statistics/technical_note-new_solar_thermal_statistics_Conversion.pdf`
- Verwendete Ausrichtung im Repo-v1:
  - `collector_azimuth_deg = 180`
  - `collector_tilt_deg = 50`
- Grundlage fuer die Ausrichtung:
  - DOE Energy Saver:
    `https://www.energy.gov/energysaver/siting-your-solar-water-heating-system`
  - dort wird fuer Solarthermie `true south` als optimale Orientierung auf der Nordhalbkugel genannt, und ein Tilt in der Naehe der Breite bzw. fuer Winter etwas steiler empfohlen.
- Repo-Interpretation:
  - fuer Wien mit Breite `48.2486` wird im v1-Pfad ein leicht winterbetonter fixer Tilt von `50°` angesetzt.
  - Das ist eine dokumentierte technische Annahme, keine gemessene Wien-Energie-Anlagenwahrheit.

## Einordnung fuer unser Repo

- Es gibt Pakete, aber kein einzelnes Standard-Python-Paket, das unseren Fall direkt komplett abbildet:
  - stundenweiser Dispatch,
  - DH-Temperaturfaehigkeit,
  - Speicherkopplung,
  - Booster-Logik,
  - Optimierung in unserem IES-Schnitt.
- Der sinnvollste Produktionspfad bleibt daher:
  - eigenes schlankes Modell im Repo,
  - orientiert an der Literaturlogik,
  - optionale spaetere Validierung gegen TESPy / Modelica / TRNSYS.

## Grundlage fuer gleitende Netztemperaturen

- Die Literatur steuert Fernwaerme-Vorlauftemperaturen typischerweise **wettergefuehrt** ueber eine Heizkurve, nicht direkt ueber eine frei erfundene Lastfunktion.
- Praktisch heisst das:
  - sinkende Aussentemperatur -> hoeherer erforderlicher Netzvorlauf,
  - steigende Aussentemperatur -> niedrigerer Netzvorlauf,
  - mit unteren/oberen Grenzen aus Netz- und Anlagenrealitaet.
- Fuer Wien gibt es dafuer einen belastbaren historischen Anker:
  - Umweltbundesamt `REP-0074` berichtet fuer das Wiener Netz:
    - Winter: gleitend bis `max. 150 C`
    - Sommer: `min. 95 C`
    - Ruecklauf: typischerweise `55-75 C`
  Link: `https://www.umweltbundesamt.at/fileadmin/site/publikationen/REP0074.pdf`
- Damit ist fuer unseren Produktionspfad v1 plausibel:
  - `network_supply_temp_c = heating_curve(T_outdoor)`
  - mit `95 C <= network_supply_temp_c <= 150 C`
  - und Ruecklaufband zunaechst ebenfalls settingsbasiert.
- Last kann spaeter als zusaetzlicher Korrekturfaktor genutzt werden, sollte aber in v1 nicht die primaere Grundlage sein.

## Empfohlene Modellstufen

## Wie die Literatur das Temperaturniveau behandelt

- Im einfachen bis mittleren Systemmodell wird haeufig **nicht** zuerst die maximal erreichbare Austrittstemperatur des Kollektors geloest.
- Stattdessen wird der Kollektorertrag gegen ein oder mehrere **vorgegebene Systemtemperaturniveaus** bewertet:
  - Netzvorlauf fuer `direct_feed`
  - Ruecklaufniveau fuer `return_preheat`
  - Speichertemperatur fuer `storage`
- Damit wird also gefragt:
  - "Wie viel nutzbare Waerme bleibt uebrig, wenn ich auf diesem Temperaturniveau arbeiten will?"
  - nicht direkt:
  - "Welche Temperatur schafft der Kollektor maximal?"
- Hoeher aufgeloeste thermodynamische Modelle gehen den umgekehrten Weg:
  - sie loesen mit Massenstrom, Eintrittstemperatur und Waermebilanz eine Kollektor-Austrittstemperatur
  - und pruefen danach die Netzeinspeisung.
- Fuer unseren Produktionspfad ist der erste Ansatz realistischer und schlanker:
  - systemtemperaturbasiert bewerten,
  - dann `direct_feed` / `preheat` / `storage` entscheiden,
  - statt sofort ein detailliertes Austrittstemperaturmodell in den Dispatch zu ziehen.

### Produktions-v1

- `q_solar_useful[t]`
- `direct_feed_feasible[t]`
- wenn nicht feasible:
  - `return_preheat`
  - oder `storage_charge`
  - oder `booster_required`

### Produktions-v2

- explizite Ruecklaufvorwaermung
- Speicherkopplung
- Booster-Waermepumpe / Zusatzheizer
- bessere Temperaturabhaengigkeit des Kollektorwirkungsgrads

### Spaetere High-Fidelity-Validierung

- TESPy oder Modelica/DisHeatLib fuer Temperatur- und Massenstromvalidierung
- nur falls der einfache Produktionspfad fachlich nicht mehr reicht

## Bezug zu unserem aktuellen Smoke

- Separater Testschnitt:
  [run_solar_thermal_smoke.py](/c:/Users/Philipp%20Thunshirn/Desktop/PhD/Python%20model/Master/Optimization/validation/model_validation/run_solar_thermal_smoke.py)
- Letzter Ergebnisstand:
  [summary.json](/c:/Users/Philipp%20Thunshirn/Desktop/PhD/Python%20model/Master/Optimization/run/results/Vienna/validation/solar_thermal_smoke_20260326_193836/summary.json)
- Der Smoke bestaetigt die Literaturtendenz:
  - der aktuelle irradiance-only-Pfad ueberschaetzt hohe direkte Nutzbarkeit deutlich,
  - `150/70 C` Winter-Direktfeed ist nur in sehr wenigen Stunden plausibel,
  - `90/50 C` ist deutlich realistischer, aber ebenfalls stark temperaturabhaengig.
