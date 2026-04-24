# Building Calibration Quellen

## Zweck

Quellen und Tool-Referenzen fuer den neuen Offline-Kalibrierungs-/`pseudo_epw`-
Pfad der Gebaeude- und Thermflex-Modelle.

## Weather / EPW

- Open-Meteo Historical Weather API:
  - https://open-meteo.com/en/docs/historical-weather-api
- Climate.OneBuilding / Wien-Innere-Stadt TMYx-EPW als Header-/Formatanker:
  - https://climate.onebuilding.org/WMO_Region_6_Europe/AUT_Austria/index.html

## Building Archetypes / Envelope / Solar

### Bereits belastbar fuer V1

- Austrian TABULA / EPISCOPE country page:
  - https://episcope.eu/building-typology/country/at/
  - Relevant fuer:
    - Statistik `S-1.2.2` zu charakteristischen `U`-Werten und Fenstertypen
    - oesterreichische Wohngebaeude-Typologie als nationaler Referenzrahmen
- Austrian TABULA scientific report:
  - https://episcope.eu/fileadmin/tabula/public/docs/scientific/AT_TABULA_ScientificReport_AEA.pdf
  - Relevant fuer:
    - typische Bauperioden
    - charakteristische `U`-Werte
    - typische Fenstertypologien nach Periode
    - typische Dach-/Decken-Subtypologien
    - Wohngebaeude-/Apartmentblock-Kontext fuer die heutigen Wiener V1-Archetypen
  - Konkreter Mehrwert fuer den neuen SSOT:
    - fuer Oesterreich sind periodische Fenstertypologien explizit beschrieben:
      - bis in die 1960er: `single glazing, wooden frame`
      - bei `MFH/AB` haeufig `single glazing, box-types`
      - spaeter `double glazing (composite windows)`
      - ab den 1990ern `heat-protection glazing`
      - heute auch `triple-glazing` / `passive-house windows`
    - damit gibt es jetzt eine belastbare periodische Residential-Logik fuer
      `glazing`, die ueber alte Repo-Defaults hinausgeht
- TABULA common calculation procedure:
  - https://episcope.eu/building-typology/tabula-structure/calculation/
  - Relevant fuer:
    - Standardwerte fuer Nutzung
    - Standardwerte fuer Luftwechsel
    - Standardwerte fuer Shading als **Verfahrensannahme**
  - Wichtige Einordnung:
    - TABULA verwendet Standardwerte fuer Shading/Solarreduktion und nicht automatisch gebaeudespezifische Verschattung.
    - die dokumentierten Verfahrenswerte sind:
      - `Fsh = 0.6` fuer vertikale Fenster
      - `Fsh = 0.8` fuer horizontale Fenster
      - `frame fraction FF = 0.3`
      - `non-perpendicular factor FW = 0.9`
      - `mc = 45 Wh/(m2K)`
    - diese Werte taugen als methodischer Fallback oder Plausibilitaetsanker,
      aber noch nicht als kohortenspezifische Wiener Solar-/Shading-SSOT
- TABULA WebTool FAQ:
  - https://episcope.eu/building-typology/webtool/
  - Wichtige Einordnung:
    - die im TABULA-Verfahren genutzte interne Waermekapazitaet `45 Wh/(m2K)` ist laut WebTool selbst **unrealistisch niedrig** und fuer Forschungsfragen nicht geeignet
    - die fruehere vereinfachte Ableitung der Solarstrahlung an Heiztagen fuehrte laut WebTool zu einer Ueberschaetzung; fuer den neuen Teacher ist das ein starkes Argument fuer unseren expliziten stuendlichen `EnergyPlus`-/EPW-Pfad
- TABULA Final Report Appendix Volume:
  - https://episcope.eu/fileadmin/tabula/public/docs/report/TABULA_FinalReport_AppendixVolume.pdf
  - Relevant fuer:
    - mittlere Huelle-/Flaechenrelationen nach Gebaeudegroesse
    - pragmatische Startwerte fuer synthetische Durchschnittsgebaeude
  - Konkreter Mehrwert fuer Wien:
    - fuer `AT apartment blocks` liefert Table 62 die heute bereits verwendeten
      Huelle/Flaechen-Ratios:
      - `roof_area_per_gfa = 0.37`
      - `window_area_per_gfa = 0.18`
      - `wall_area_per_gfa = 0.82`
      - `floor_exposed_per_gfa = 0.36`
- OIB-Richtlinie 6 / Kostenoptimalitaet:
  - https://www.oib.or.at/sites/default/files/kostenoptimalitaet_0.pdf
  - Relevant fuer:
    - oesterreichische Standard-/Plausibilitaetsanker fuer thermische Randbedingungen
  - Konkrete Anker aus den Referenzfaellen:
    - `mittlerer g-Wert = 0.67`
    - `Infiltrationsrate n50 = 0.60 1/h`
    - `Gebaeudesystem Luftwechsel = 0.40 1/h`
    - `Winter-Solltemperatur = 20 C`
    - `Sommer-Solltemperatur = 26 C`
  - Wichtige Einordnung:
    - brauchbar als oesterreichischer Plausibilitaetsanker
    - aber nicht automatisch kohortenspezifisch oder fenstertypspezifisch
- TABULA Thematic Report No. 3 / Non-Residential Buildings:
  - https://episcope.eu/building-typology/tabula-structure/non-residential/
  - Relevant fuer:
    - Einordnung, wie schwach die Datenlage fuer `non_residential` im Vergleich zu `residential` ist
    - sinnvolle Differenzierungsachsen fuer spaetere Non-Res-Archetypen
  - Wichtige Einordnung:
    - offizielle Statistik fuer Nichtwohngebaeude ist laut Bericht generell schwach
    - fuer Oesterreich werden Datenbanken wie `ZEUS` / `ImmoZEUS` als aussichtsreiche Quelle genannt
    - empfohlene Klassifikationsachsen:
      - Nutzung
      - Bauperiode
      - Groesse / Kubatur
      - surface-to-volume ratio
      - Versorgungssysteme
      - Sanierungsstand
    - das stuetzt den heutigen Befund:
      `non_residential`-Geometrie und Solarannahmen sind im Repo noch deutlich offener als `residential`

### Repo-interne SSOT / V1-Annahmen

- Wiener thermische Archetypen:
  - [thermal_archetypes.py](/c:/Users/Philipp%20Thunshirn/Desktop/PhD/Python%20model/Master/Data/thermal_archetypes/Vienna/thermal_archetypes.py)
  - Der Code ist bereits explizit kommentiert:
    - `U`-Werte residential an TABULA/EPISCOPE
    - residential Geometrie-Ratios an TABULA apartment-block averages
    - non-residential Geometrie und `c_th` noch pragmatische V1-Annahmen
- Wiener Building Stock:
  - [building_stock.py](/c:/Users/Philipp%20Thunshirn/Desktop/PhD/Python%20model/Master/Data/building_stock/Vienna/building_stock.py)
  - Nutzung:
    - Kohortenhaeufigkeiten
    - Flaechen- und Volumenanker
    - Waermeanker pro Kohorte

### Legacy-Artefakte, nicht mehr SSOT fuer den Teacher

- Alte Solar-/Gebaeude-Defaults:
  - [building.py](/c:/Users/Philipp%20Thunshirn/Desktop/PhD/Python%20model/Master/Data/technology_data/building.py)
  - Diese enthalten noch:
    - `solar_multipliers`
    - `g_glazing`
    - `g_glazing_shaded`
  - Einordnung:
    - hilfreicher Altpfad / Repo-Historie
    - aber **keine** belastbare Quellenbasis fuer die neuen Wiener Kohorten
- Fruehere Solar-/Forcing-Artefakte:
  - [Solar_gains.csv](/c:/Users/Philipp%20Thunshirn/Desktop/PhD/Python%20model/Master/Data/profiles/Vienna/solar_gains/Solar_gains.csv)
  - [Strahlungsdaten_Felixgasse22.csv](/c:/Users/Philipp%20Thunshirn/Desktop/PhD/Python%20model/Master/Data/profiles/Vienna/irradiance/Strahlungsdaten_Felixgasse22.csv)
  - Einordnung:
    - fuer den neuen `EnergyPlus`-Teacher **nicht** mehr Wetter-/Solar-SSOT
    - bleiben nur Legacy-/Vergleichsartefakte, solange sie nicht explizit re-promoted werden

### Noch offen

- Kohortenspezifische `g`-/`SHGC`-Werte nach Bauperiode / Fenstertyp:
  - Residential ist jetzt **teilweise geschlossen**:
    - die periodischen Fenstertypologien aus TABULA werden im Teacher jetzt
      explizit in periodenspezifische `SimpleGlazingSystem`-Optikparameter
      (`SHGC`, `visible transmittance`) uebersetzt.
    - die `SHGC`-Werte sind dabei jetzt datenbasierter an aehnliche TABULA-
      Fenstertypdaten aus mehreren Laenderberichten angelehnt:
      - Einfachverglasung ~ `0.85`
      - Doppelverglasung ~ `0.75-0.76`
      - Waermeschutz-/double-low-e ~ `0.60-0.63`
      - Dreifach-/high-performance ~ `0.50`
    - diese numerischen Optikwerte sind damit als **cross-TABULA Proxy** zu
      lesen:
      - AT-TABULA liefert die Typenfolge
      - DE/DK/PL-TABULA liefern numerische `g`-Wert-Anker fuer vergleichbare
        Fenstertypen
    - `visible transmittance` bleibt vorerst ein dokumentierter V1-Begleitproxy
      und ist noch nicht gleich stark quellenfest wie `SHGC`.
    - die periodenspezifische Fenster-SSOT ist inzwischen auch strukturell feiner
      hinterlegt:
      - `n_panes`
      - `glazing_family`
      - `frame_type`
      - `has_low_e`
      - `has_inert_gas_fill`
      - `has_thermal_break`
      - `g_value`
      - `visible_transmittance`
      - `source_note`
    - Wichtige Einordnung:
      - diese Zusatzfelder machen die Fensterlogik besser rekonstruierbar
      - sie erzeugen aber nicht automatisch eine voll quellenfeste Fensterkonstruktion
  - Weiter offen bleibt:
    - eine staerker quellenfeste, direkte Zuordnung
      `construction_period -> glazing class -> g/SHGC`
    - sowie eine gleich starke Nichtwohn-Logik; `non_residential` bleibt
      vorerst bei einem expliziten globalen V1-Teacher-Glazingpfad.
- Kohortenspezifische Shading-/Solar-Exposure-Annahmen:
  - TABULA liefert hier nur Verfahrenswerte (`Fsh`), keine Wiener
    kohortenspezifische Exposition.
  - Genau hier ist der heutige Teacher noch zu homogen.
- belastbarere non-residential Geometrie statt reiner Prototype-Inference
- realistischere effektive Waermekapazitaet je Kohorte:
  - die heutige `c_th_wh_per_m2k`-Leiter ist V1-pragmatisch, nicht endgueltig quellenfest
  - der TABULA-Verfahrenswert `45 Wh/(m2K)` ist laut WebTool selbst fuer Forschung zu grob

## EnergyPlus

- Offizielle Releases:
  - https://github.com/NREL/EnergyPlus/releases
- Lokal verwendeter Build im Workspace:
  - `Technical_model/technologies/buildings/calibration/_vendor/EnergyPlus-26.1.0/.../energyplus.exe`

## Repo-interne Artefakte

- Calibration-SSOT:
  - [building_calibration.py](/c:/Users/Philipp%20Thunshirn/Desktop/PhD/Python%20model/Master/Settings/technical/building_calibration.py)
- `pseudo_epw`-Builder:
  - [pseudo_epw.py](/c:/Users/Philipp%20Thunshirn/Desktop/PhD/Python%20model/Master/Technical_model/technologies/buildings/calibration/weather/pseudo_epw.py)
- EnergyPlus-Mini-Smoke:
  - [run_energyplus_smoke.py](/c:/Users/Philipp%20Thunshirn/Desktop/PhD/Python%20model/Master/Technical_model/technologies/buildings/calibration/run_energyplus_smoke.py)
  - [energyplus.py](/c:/Users/Philipp%20Thunshirn/Desktop/PhD/Python%20model/Master/Technical_model/technologies/buildings/calibration/teachers/energyplus.py)
- Erster echter Teacher-Pilot:
  - [run_energyplus_teacher_pilot.py](/c:/Users/Philipp%20Thunshirn/Desktop/PhD/Python%20model/Master/Technical_model/technologies/buildings/calibration/run_energyplus_teacher_pilot.py)
  - [teacher_hourly.csv](/c:/Users/Philipp%20Thunshirn/Desktop/PhD/Python%20model/Master/Technical_model/technologies/buildings/calibration/_teacher_runs/residential_1975_1990/winter_reference_week/teacher_hourly.csv)
  - [teacher.meta.json](/c:/Users/Philipp%20Thunshirn/Desktop/PhD/Python%20model/Master/Technical_model/technologies/buildings/calibration/_teacher_runs/residential_1975_1990/winter_reference_week/teacher.meta.json)
- Teacher-Setup / Experimentbibliothek:
  - [schemas.py](/c:/Users/Philipp%20Thunshirn/Desktop/PhD/Python%20model/Master/Technical_model/technologies/buildings/calibration/schemas.py)
  - [from_repo.py](/c:/Users/Philipp%20Thunshirn/Desktop/PhD/Python%20model/Master/Technical_model/technologies/buildings/calibration/from_repo.py)
  - [experiments.py](/c:/Users/Philipp%20Thunshirn/Desktop/PhD/Python%20model/Master/Technical_model/technologies/buildings/calibration/experiments.py)
  - [run_prepare_teacher_setup.py](/c:/Users/Philipp%20Thunshirn/Desktop/PhD/Python%20model/Master/Technical_model/technologies/buildings/calibration/run_prepare_teacher_setup.py)
  - [teacher_inputs_v1.json](/c:/Users/Philipp%20Thunshirn/Desktop/PhD/Python%20model/Master/Data/profiles/Vienna/weather/calibration_setup/teacher_inputs_v1.json)
  - [experiment_library_v1.json](/c:/Users/Philipp%20Thunshirn/Desktop/PhD/Python%20model/Master/Data/profiles/Vienna/weather/calibration_setup/experiment_library_v1.json)
- Reduced-Order-Fit:
  - [fit_reduced_order.py](/c:/Users/Philipp%20Thunshirn/Desktop/PhD/Python%20model/Master/Technical_model/technologies/buildings/calibration/fit_reduced_order.py)
  - [run_fit_reduced_order.py](/c:/Users/Philipp%20Thunshirn/Desktop/PhD/Python%20model/Master/Technical_model/technologies/buildings/calibration/run_fit_reduced_order.py)
  - [reduced_order_fit_summary.csv](/c:/Users/Philipp%20Thunshirn/Desktop/PhD/Python%20model/Master/Technical_model/technologies/buildings/calibration/_reduced_order_fits/reduced_order_fit_summary.csv)
- Event-Response-Fit:
  - [fit_event_response.py](/c:/Users/Philipp%20Thunshirn/Desktop/PhD/Python%20model/Master/Technical_model/technologies/buildings/calibration/fit_event_response.py)
  - [run_fit_event_response.py](/c:/Users/Philipp%20Thunshirn/Desktop/PhD/Python%20model/Master/Technical_model/technologies/buildings/calibration/run_fit_event_response.py)
  - [event_response_fit_summary.csv](/c:/Users/Philipp%20Thunshirn/Desktop/PhD/Python%20model/Master/Technical_model/technologies/buildings/calibration/_event_response_fits/event_response_fit_summary.csv)
- `calibrated_v1`-Export:
  - [export_calibrated_archetypes.py](/c:/Users/Philipp%20Thunshirn/Desktop/PhD/Python%20model/Master/Technical_model/technologies/buildings/calibration/export_calibrated_archetypes.py)
  - [run_export_calibrated_v1.py](/c:/Users/Philipp%20Thunshirn/Desktop/PhD/Python%20model/Master/Technical_model/technologies/buildings/calibration/run_export_calibrated_v1.py)
  - [calibrated_v1.json](/c:/Users/Philipp%20Thunshirn/Desktop/PhD/Python%20model/Master/Data/thermal_archetypes/Vienna/calibrated_v1.json)
  - [calibrated_v1.py](/c:/Users/Philipp%20Thunshirn/Desktop/PhD/Python%20model/Master/Data/thermal_archetypes/Vienna/calibrated_v1.py)
