# Learning Datasets

Dieser Ordner ist die SSOT fuer persistierte Trainingsdatensaetze im `Learning/`-Layer.

## Zweck

- Truth-Daten fuer Surrogat-Training reproduzierbar ablegen
- Family-basierte Wiederverwendung und Caching ermoeglichen
- lesbare CSV-/JSON-Artefakte fuer Audit, Doku und Debug bereitstellen

## Struktur

Jeder Family-Datensatz liegt unter:

- `Learning/datasets/<family_hash>/`

Ein Family-Datensatz soll mindestens enthalten:

- `training_data.npz`
- `training_data.meta.json`
- `truth_dataset.csv`
- `truth_dataset.meta.json`

Falls vorhanden oder erforderlich:

- `family_spec.json`
- `source_runs.json`
- `teacher_eval/summary.json`
- `teacher_eval/infeasible_points.csv`

Zusaetzlich gibt es einen zentralen Artefaktkatalog fuer wiederverwendbare
Truth-, Dataset-, Modell- und Diagnoseartefakte:

- `Learning/datasets/artifact_inventory.py`
- `Learning/datasets/artifact_inventory.json`
- `Learning/datasets/artifact_inventory.csv`
- `Learning/datasets/artifact_inventory_summary.json`

Dieser Katalog ist bewusst breiter als ein einzelner Datensatz-Export. Er soll
sichtbar machen, welche alten Repo-Artefakte:

- direkt als Truth fuer Training taugen,
- bereits kuratierte `Learning/datasets/`-SSOT sind,
- nur Modellhistorie / Diagnose sind,
- und welcher Surrogatfamilie sie ueberhaupt kompatibel sind.

Paper-Figure-Caches mit eigenem Solve-Vertrag werden separat als
`thermflex_paper_figure_rolling_v1` klassifiziert. Diese Artefakte duerfen fuer
dedizierte Rolling-Horizon-/Figure-KPI-Surrogate wiederverwendet werden, aber
nicht still mit `thermflex_daily_results_v1` vermischt werden.

## Regeln

- Keine ad-hoc-Datensaetze ausserhalb dieses Pfads als neue SSOT einfuehren.
- `truth_dataset.csv` soll ueber den offiziellen Exportpfad erzeugt werden, nicht ueber still abweichende Hilfsskripte.
- Reuse/Caching muss sowohl bekannte feasible als auch bekannte infeasible Truth-Punkte beruecksichtigen.
- Fehlende Pflichtartefakte sind Fehler und duerfen nicht still uebersprungen werden.
- Alte Artefakte duerfen nur ueber explizit klassifizierte Familien wiederverwendet werden; Modell-Metadaten und Holdout-Reports sind keine Trainingszeilen.

## Codepfade

Die offizielle Persistenz liegt in:

- `Learning/datasets/save_dataset.py`
- `Learning/datasets/load_dataset.py`
