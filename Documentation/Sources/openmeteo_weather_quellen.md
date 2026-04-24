# Open-Meteo Weather Quellen

## Zweck

Offene historische Wetterquelle fuer den geplanten Offline-Kalibrierungs- und
pseudo-EPW-Pfad der Wiener Gebaeude-/Thermflex-Modelle.

## Verwendete Quelle

- Open-Meteo Historical Archive API:
  - https://open-meteo.com/en/docs/historical-weather-api

## Repo-interne SSOT / Artefakte

- Downloader-Skript:
  - [fetch_openmeteo_archive_vienna.py](/c:/Users/Philipp%20Thunshirn/Desktop/PhD/Python%20model/Master/Data/profiles/Vienna/weather/fetch_openmeteo_archive_vienna.py)
- Exportierte 10-Jahres-Zeitreihe:
  - [openmeteo_hourly_archive_2016_2025.csv](/c:/Users/Philipp%20Thunshirn/Desktop/PhD/Python%20model/Master/Data/profiles/Vienna/weather/openmeteo_hourly_archive_2016_2025.csv)
- Export-Metadaten:
  - [openmeteo_hourly_archive_2016_2025.csv.meta.json](/c:/Users/Philipp%20Thunshirn/Desktop/PhD/Python%20model/Master/Data/profiles/Vienna/weather/openmeteo_hourly_archive_2016_2025.csv.meta.json)
- Reproduzierbare Jahresauswahl:
  - [select_representative_openmeteo_years.py](/c:/Users/Philipp%20Thunshirn/Desktop/PhD/Python%20model/Master/Data/profiles/Vienna/weather/select_representative_openmeteo_years.py)
  - [openmeteo_year_summary_2016_2025.csv](/c:/Users/Philipp%20Thunshirn/Desktop/PhD/Python%20model/Master/Data/profiles/Vienna/weather/openmeteo_year_summary_2016_2025.csv)
  - [openmeteo_representative_years_2016_2025.json](/c:/Users/Philipp%20Thunshirn/Desktop/PhD/Python%20model/Master/Data/profiles/Vienna/weather/openmeteo_representative_years_2016_2025.json)
- Gebaute `pseudo_epw`-Dateien:
  - [vienna_openmeteo_average_year_2020.epw](/c:/Users/Philipp%20Thunshirn/Desktop/PhD/Python%20model/Master/Data/profiles/Vienna/weather/epw/vienna_openmeteo_average_year_2020.epw)
  - [vienna_openmeteo_cold_year_2021.epw](/c:/Users/Philipp%20Thunshirn/Desktop/PhD/Python%20model/Master/Data/profiles/Vienna/weather/epw/vienna_openmeteo_cold_year_2021.epw)
  - [vienna_openmeteo_mild_year_2024.epw](/c:/Users/Philipp%20Thunshirn/Desktop/PhD/Python%20model/Master/Data/profiles/Vienna/weather/epw/vienna_openmeteo_mild_year_2024.epw)
  - Builder:
    - [pseudo_epw.py](/c:/Users/Philipp%20Thunshirn/Desktop/PhD/Python%20model/Master/Technical_model/technologies/buildings/calibration/weather/pseudo_epw.py)

## Enthaltene Wettervariablen

- Temperatur / Feuchte:
  - `temperature_2m`
  - `relative_humidity_2m`
  - `dew_point_2m`
  - `apparent_temperature`
  - `pressure_msl`
  - `surface_pressure`
- Wolken / Wetter:
  - `cloud_cover`
  - `cloud_cover_low`
  - `cloud_cover_mid`
  - `cloud_cover_high`
  - `weather_code`
- Wind:
  - `wind_speed_10m`
  - `wind_direction_10m`
  - `wind_speed_100m`
  - `wind_direction_100m`
  - `wind_gusts_10m`
- Niederschlag / Schnee:
  - `precipitation`
  - `rain`
  - `snowfall`
  - `snow_depth`
- Strahlung:
  - `shortwave_radiation`
  - `direct_radiation`
  - `diffuse_radiation`
  - `direct_normal_irradiance`
  - `terrestrial_radiation`
  - plus die jeweiligen `_instant`-Varianten
- Boden / Hilfsvariablen:
  - `soil_temperature_*`
  - `soil_moisture_*`
  - `et0_fao_evapotranspiration`
  - `vapour_pressure_deficit`

## Zeitabdeckung

- `2016-01-01 00:00 UTC` bis `2025-12-31 23:00 UTC`
- `87672` Stunden

## Erste Kalibrierungs-Jahresauswahl

- `average_year = 2020`
- `cold_year = 2021`
- `mild_year = 2024`

Methodik:

- `cold_year` = Jahr mit maximalem `HDD18`
- `mild_year` = Jahr mit minimalem `HDD18`
- `average_year` = minimierte z-standardisierte Distanz auf:
  - `annual_mean_temp_c`
  - `annual_shortwave_kwh_m2`
  - `hdd18`
  - `winter_mean_temp_c`
  - `winter_shortwave_kwh_m2`
  - `winter_hdd18`

## Hinweise

- Der Downloader zieht die Jahre explizit als Jahres-Chunks und schreibt diese
  unter `Data/profiles/Vienna/weather/_openmeteo_chunks/`.
- Kein stiller Fallback:
  - fehlende Variablen
  - falsche Zeilenanzahl
  - doppelte Zeitstempel
  - fehlende Chunk-Metadaten
  fuehren zu einem harten Fehler.
- Der Open-Meteo-Archivpfad ist fuer den historischen Wetterlayer und eine
  spaetere `pseudo_epw`-Erzeugung gedacht, nicht als Ersatz fuer die bereits
  genutzten Produktivprofile (`temperature`, `irradiance`, `wind`) im heutigen
  Hauptlauf.
