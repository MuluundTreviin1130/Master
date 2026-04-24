# Run Analysis

Dieser Ordner enthaelt reproduzierbare Analyse- und Reporting-Helfer fuer Optimierungslaeufe.

## Zweck

- KPI- und Summary-Exporte konsistent aus den offiziellen Run-Artefakten erzeugen
- wiederkehrende Vergleiche, vor allem fuer Paper-Faelle, reproduzierbar machen
- keine ad-hoc-Einweg-Skripte als versteckte Analyse-SSOT entstehen lassen

## Wichtige Dateien

- `csv_exports.py`
  offizieller KPI-/CSV-Exportpfad aus Run-Ergebnissen
- `summary.py`
  kompakte textuelle Summary
- `build_paper_dispatch_comparison.py`
  generischer Vergleich mehrerer `dispatch_kpis.json`-Runs
- `dh_thermflex_inputs.py`
  gemeinsamer Volljahres-Inputlayer fuer Vienna-DH-Thermflex-Analysen
- `build_nonres_2000_2014_debug.py`
  expliziter Debug-Report fuer den verdaechtigen Nichtwohn-Kohortenfall
- `select_vienna_dh_thermflex_representative_days.py`
  datengetriebene Representative-Day-Auswahl fuer 2023
- `build_energyplus_cohort_day_plots.py`
  cohort/day-Plots aus bestehenden EnergyPlus-Teacher-Artefakten
- `build_dh_thermflex_run_bundle.py`
  kuratiert die aktuellen DH-Thermflex-Paper-Artefakte in einem Run-Bundle

## Runner

Projektweite Wrapper koennen diesen Analysis-Layer direkt aufrufen, zum Beispiel:

- `Optimization/run/papers/dh_thermflex/run_vienna_thermflex_paper_analysis.py`
- `Optimization/run/papers/dh_thermflex/run_vienna_dh_thermflex_bundle.py`

## Regeln

- Analyse-Skripte duerfen keine stillen Fallbacks auf fehlende KPI-Felder nutzen.
- Vergleichslogik soll auf offiziellen Exporten beruhen, nicht auf rohen Zwischenobjekten.
- Wenn ein neuer langlebiger Analysepfad hinzukommt, hier kurz dokumentieren.
