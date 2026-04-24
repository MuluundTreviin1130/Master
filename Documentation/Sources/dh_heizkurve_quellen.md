# DH-Heizkurve: Quellen und Ableitung

## Kurzfassung

- Die belastbarste Grundlage fuer die DH-Heizkurve ist **nicht** eine frei erfundene Lastfunktion, sondern eine **wettergefuehrte Heizkurve**.
- Fuer Wien haben wir dafuer drei Ebenen von Quellen:
  - aktuelle offizielle Wien-Energie-Anschlussbedingungen,
  - historische/technische Wiener Temperaturanker,
  - methodische Literatur zur wettergefuehrten DH-Temperaturregelung.

## 1. Aktuelle offizielle Wien-Energie-Basis

- Wien Energie TAB-FW 2025-09
  Link: `https://dokumente.wienenergie.at/link/technische-anschlussbedingungen-fernwaerme-tab-fw/`
  Relevante Aussagen:
  - `3.1`: ab 2035 plant Wien Energie eine Absenkung der primaeren Vorlauftemperatur auf `120 C` bzw. `130 C` bei `-12 C` Aussentemperatur sowie eine Absenkung der primaeren Mindestvorlauftemperatur im Sommer auf `75 C`
  - `3.1`: maximale netzseitige Ruecklauftemperaturen ab 2035:
    - Primaernetz `63 C`
    - Sekundaernetz `58 C`
  - `3.2`: im hydraulischen Schema ist die **Heizkurve** explizit anzugeben
  Einordnung:
  - gute offizielle Grundlage fuer einen **zukuenftigen/abgesenkten Wien-Modus**
  - liefert aber nicht die komplette historische Operator-Kurve als fertige Funktion

## 2. Historische Wiener Netztemperatur-Anker

- Umweltbundesamt REP-0074
  Link: `https://www.umweltbundesamt.at/fileadmin/site/publikationen/REP0074.pdf`
  Relevante Aussagen:
  - Wiener Netz im Winter gleitend bis max. `150 C`
  - Sommer mindestens `95 C`
  - Ruecklauftemperaturen typischerweise `55-75 C`
  Einordnung:
  - gute Grundlage fuer einen **Legacy-/Bestands-Wien-Modus**
  - gibt Min/Max und Ruecklaufband, aber nicht die exakte vollstaendige Heizkurvenfunktion

## 3. Wiener technische Auslegungsblaetter / Temperaturkurvenblaetter

- Wien Energie Technische Auslegungsbedingungen 2013
  Link: `https://dokumente.wienenergie.at/wp-content/uploads/technische-auslegungsbedingungen-2013.pdf`
  Relevante Aussagen:
  - enthaelt explizite **gleitende** Temperaturkurvenblaetter fuer verschiedene Primaer-/Sekundaernetzbereiche
  - enthaelt Vorlauf-/Ruecklauftemperatur ueber Aussentemperatur
  - zeigt damit direkt, dass Wien die Temperaturfuehrung wettergefuehrt abbildet
  Einordnung:
  - beste aktuell gefundene direkte Kurvenbasis fuer Wien
  - historisch/technisch sehr nuetzlich fuer einen ersten settingsbasierten V1-Schnitt
  Konkrete relevante Blaetter:
  - `Blatt 1.2a`: Primaernetz - Stationen, OMV bis Kaiser-Ebersdorfer-Strasse / Florian-Hedorfer-Strasse, `T_max = 180 C`
  - `Blatt 1.2b`: Primaernetz - Stationen, Kaiser-Ebersdorfer-Strasse / Florian-Hedorfer-Strasse bis Kraftwerk Simmering, `T_max = 180 C`
  - `Blatt 1.4`: Primaernetz - Stationen, Abschnitt FHW Kagran - Aspern, `T_max = 160 C`
  - `Blatt 1.5`: Primaernetz - Stationen, Gartenbaubetriebe Simmering, `T_max = 120 C`
  - `Blatt 1.6`: Primaernetz - Stationen, FL Sued-Ost, `T_max = 160 C`
  - `Blatt 2.1 energieeffiziente Gebaeude`: Sekundaernetz, `direkt`, `konstant`, `T_max = 95 C`
  - `Blatt 2.1 Standard Neubau`: Sekundaernetz, `direkt`, `gleitend`, `T_max = 95 C`
  - `Blatt 2.2`: Sekundaernetz - Stationen Dirmhirngasse - Liesing, `direkt`, `gleitend`, `T_max = 120 C`
  Interpretationspunkt:
  - Das Dokument liefert damit **keine einzige allgemeine Wien-Kurve**, sondern mehrere temperaturgefuehrte Kurvenfamilien je Netzbereich und Gebaeudetyp.

## 4. Methodische Literaturbasis

- IEA DHC Annex TS4 Guidebook
  Link: `https://www.iea-dhc.org/fileadmin/documents/Annex_TS4/IEA_DHC_Annex_TS4_Guidebook_2023.pdf`
  Relevante Aussagen:
  - erforderliche minimale Versorgungstemperaturen werden auf Basis der **Aussentemperatur** und der kritischen Radiatoren bestimmt
  - die resultierende DH-Vorlauftemperatur wird als **control curve** gegen `T_outdoor` gefuehrt
  - fuer grosse Teile der Heizsaison kann eine deutlich niedrigere Temperatur ausreichen; hohe Temperaturen werden nur in kaelteren Perioden benoetigt
  Einordnung:
  - methodische Grundlage dafuer, dass auch unser Repo v1 eine **wettergefuehrte Heizkurve** nutzen sollte
  - Last kann spaeter zusaetzlich wirken, sollte aber v1 nicht die primaere Fuehrung sein

## 5. Ableitung fuer das Repo

### V1-Empfehlung

- Die Heizkurve als **Settings-Wahrheit** fuehren, nicht versteckt in Code.
- Nicht eine einzige Wien-Kurve erzwingen, sondern zunaechst klar benannte Modi vorbereiten:
  - `legacy_vienna`
    - Anker aus Umweltbundesamt:
      - `T_supply_min = 95 C`
      - `T_supply_max = 150 C`
      - `T_return_min = 55 C`
      - `T_return_max = 75 C`
    - Interpretation:
      - generischer historischer Hochtemperatur-Referenzmodus fuer das Wiener Verbundnetz
  - `target_vienna_2035`
    - Anker aus TAB-FW:
      - `T_supply_min = 75 C`
      - `T_supply_max = 120/130 C` bei `-12 C`
      - `T_return_max = 63 C` bzw. `58 C`
    - Interpretation:
      - abgesenkter Zukunftsmodus gemaess aktueller Wien-Energie-Richtung
  - optional spaeter netzbereichsspezifisch:
    - `vienna_primary_180C`
    - `vienna_primary_160C`
    - `vienna_secondary_95C`
    - `vienna_secondary_120C`

### V1-Funktion

- wettergefuehrte, einfache lineare oder stueckweise lineare Heizkurve:
  - `network_supply_temp_c = heating_curve(T_outdoor_c)`
  - `network_return_temp_c = return_curve(T_outdoor_c)` oder zunaechst settingsbasiertes Band
- `pinch_point_c` separat in die Settings

### Was noch fehlt

- Die exakte aktuelle Wiener Betreiber-Heizkurve ist aus den oeffentlich zugreifbaren Quellen nicht als eine eindeutige, allgemeingueltige Funktion ablesbar.
- Die Auslegungsblaetter geben zwar die Kurvenfamilien, aber nicht schon als direkt maschinenlesbare Algebra.
- Wenn wir spaeter mehr Genauigkeit wollen, waeren die besten Quellen:
  - direkte Wien-Energie-Temperaturkurvenblaetter / Planfreigabeunterlagen
  - historische Betriebsdaten
  - ggf. netzbereichsspezifische Auslegungsunterlagen

## Bezug zum Solarthermie-Pfad

- Diese Heizkurve ist die Referenz, gegen die `direct_feed` fuer Solarthermie geprueft werden sollte.
- Ohne solche Netztemperaturwahrheit bleibt `direct_feed_feasible` methodisch zu frei.
