# Optimization/sensitivity/sobol_global/sobol_eval.py
from __future__ import annotations

from pathlib import Path
from typing import Dict, Any

import numpy as np

from Optimization.framework.engines.Surrogat_model.surrogate_engine import SurrogateEngine


def _find_latest_surrogate_dir(base_dir: Path) -> Path:
    """
    Sucht im Basisordner (output_root/location/tag) den jüngsten Ordner
    mit Präfix 'surrogate_'.

    Struktur laut persist.save.make_outdir:
      {output_root}/{location}/{tag}/surrogate_{timestamp}/
    """
    if not base_dir.exists():
        raise FileNotFoundError(f"[sobol] Basisordner existiert nicht: {base_dir}")

    candidates = [
        d for d in base_dir.iterdir()
        if d.is_dir() and d.name.startswith("surrogate_")
    ]
    if not candidates:
        raise FileNotFoundError(f"[sobol] Keine surrogate_* Ordner in: {base_dir}")

    # Einfach lexikographisch sortieren – Timestamp ist YYYYMMDD_HHMMSS
    latest = sorted(candidates)[-1]
    return latest


def resolve_surrogate_artifact_path(settings) -> str:
    """
    Ermittelt den Pfad zum Surrogat-Artefakt (surrogate_rf.joblib).

    Reihenfolge:
    1) Wenn settings.engine.surrogate_artifact_path gesetzt und existent → verwenden.
    2) Sonst: {output_root}/{location}/{tag}/surrogate_*/surrogate_rf.joblib
       (jüngster surrogate_* Unterordner).
    """
    # 1) Direkter Pfad aus Settings (falls gesetzt)
    path = getattr(settings.engine, "surrogate_artifact_path", None)
    if isinstance(path, str) and path.strip() and Path(path).is_file():
        return path

    # 2) Aus der Ordnerstruktur ableiten
    output_root = Path(str(settings.reporting.output_root))
    location = str(settings.engine.location)
    tag = str(settings.run.tag)

    base_dir = output_root / location / tag
    latest_surrogate_dir = _find_latest_surrogate_dir(base_dir)

    joblib_path = latest_surrogate_dir / "surrogate_rf.joblib"
    if not joblib_path.is_file():
        raise FileNotFoundError(
            f"[sobol] surrogate_rf.joblib nicht gefunden in: {latest_surrogate_dir}"
        )

    # Settings updaten, damit weitere Nutzer denselben Pfad verwenden
    settings.engine.surrogate_artifact_path = str(joblib_path)
    return str(joblib_path)


def make_surrogate_engine(settings) -> SurrogateEngine:
    """
    Baut eine SurrogateEngine-Instanz auf Basis des existierenden Artefakts.

    Wichtig: Wir setzen vor dem Konstruktor den artifact_path, damit
    SurrogateEngine.__init__ KEIN auto_train_surrogate mehr triggert.
    """
    artifact_path = resolve_surrogate_artifact_path(settings)
    settings.engine.surrogate_artifact_path = artifact_path
    # run_dir ist für Sobol irrelevant – wir schreiben hier nichts weg
    engine = SurrogateEngine(settings=settings, run_dir=None)
    return engine


def eval_surrogate(
    settings,
    X: np.ndarray,
) -> Dict[str, np.ndarray]:
    """
    Evaluiert das Surrogat für eine Menge an Designpunkten X.

    Parameters
    ----------
    settings : Settings
        Dein bestehendes Settings-Objekt.
    X : ndarray, shape (N, D)
        Design-Samples (z.B. pv_kwp, bess_kwh).

    Returns
    -------
    outputs : dict[str, ndarray]
        Dictionary mit Zielgrößen:
          { objective_name: values }
        z.B. {"npc_eur": npc_array, "pef_pt": pef_array, "grid_import_kwh": grid_imp_array}
    """
    X = np.asarray(X, float)
    if X.ndim == 1:
        X = X.reshape(1, -1)

    engine = make_surrogate_engine(settings)
    F, G = engine.evaluate(X)  # F: (N, n_obj)

    obj_names = list(settings.objectives.names)
    if F.shape[1] != len(obj_names):
        raise RuntimeError(
            f"[sobol] F-Spaltenzahl ({F.shape[1]}) passt nicht zu objectives.names ({len(obj_names)})."
        )

    outputs: Dict[str, np.ndarray] = {}
    for j, name in enumerate(obj_names):
        outputs[name] = F[:, j].copy()

    # Optional: Autarkie als zusätzliche "Output-Spalte" ergänzen
    # Autarkie = 1 - E_import_grid_L / E_load_L; hier hast du nur die
    # grid_import_kwh (Lebensdauer) und die Last in engine._year_load_kwh * lifetime.
    # Wenn du das brauchst, kannst du hier später noch eine autarky-Spalte ergänzen.

    return outputs
