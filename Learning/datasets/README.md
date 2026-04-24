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

## Regeln

- Keine ad-hoc-Datensaetze ausserhalb dieses Pfads als neue SSOT einfuehren.
- `truth_dataset.csv` soll ueber den offiziellen Exportpfad erzeugt werden, nicht ueber still abweichende Hilfsskripte.
- Reuse/Caching muss sowohl bekannte feasible als auch bekannte infeasible Truth-Punkte beruecksichtigen.
- Fehlende Pflichtartefakte sind Fehler und duerfen nicht still uebersprungen werden.

## Codepfade

Die offizielle Persistenz liegt in:

- `Learning/datasets/save_dataset.py`
- `Learning/datasets/load_dataset.py`
