# Building Calibration

Dieser Ordner enthaelt den Offline-Kalibrierungspfad fuer thermische Gebaeudearchetypen.

## Zweck

- High-Fidelity-Sidecar bewusst ausserhalb des Runtime-Dispatchs halten
- Teacher-Runs, Event-Experimente und Reduced-Order-Fits reproduzierbar strukturieren
- kalibrierte effektive Gebaeudeparameter fuer den Runtime-Pfad ableiten

## Hauptteile

- `teachers/`
  Teacher-Adapter, aktuell mit `EnergyPlus`-Pfad.
- `weather/`
  Wettervorbereitung inklusive `pseudo_epw`.
- `from_repo.py`
  Ableitung der Teacher-Inputs aus bestehender Repo-SSOT.
- `experiments.py`
  standardisierte Experimente wie `reference`, `free_float`, `preheat`, `cutback`, `recovery`.
- `fit_reduced_order.py`
  Fit von effektiven Verlust- und Kapazitaetsparametern.
- `fit_event_response.py`
  Fit von Event-/Recovery-Kennwerten.
- `export_calibrated_archetypes.py`
  Export von `calibrated_v1` und spaeteren Varianten.

## Layer-2 Surrogate Target

Der langfristige Gebaeudepfad soll vom heutigen Reduced-Order-Runtime-Modell
auf einen `EnergyPlus`-trainierten building-response surrogate wechseln. Der
technische Schnitt ist in
`Documentation/Planning/building_surrogate_layer2_design.md` dokumentiert.
Dieser Zielpfad nutzt den bestehenden `EnergyPlus`-Teacher und den bestehenden
`Learning/`-Layer, statt einen separaten Modellpfad neben dem Repo aufzubauen.

## Output-Ordner

- `_teacher_runs/`
- `_reduced_order_fits/`
- `_event_response_fits/`
- `_smoke/`

Diese Ordner sind Artefakt- und Ergebnispfade, nicht der fachliche SSOT fuer aktive Runtime-Parameter.
Der aktive Datenexport geht nach `Data/thermal_archetypes/...`.

## Regeln

- Keine stillen Fallbacks bei Wetter, Teacher-Inputs oder Fit-Artefakten.
- Keine dauerhaften Modellannahmen hart im Runner verstecken.
- Aktivierung und Varianten muessen ueber `Settings/technical/building_calibration.py` oder Daten-SSOT nachvollziehbar sein.
