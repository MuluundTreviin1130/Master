# Optimization/framework/Orchestrator/optimize.py
from __future__ import annotations

from pathlib import Path
from datetime import datetime
from typing import Any, Dict, Optional
import json
import numpy as np
import traceback

# --- Paket-relative Importe (korrekt zur gezeigten Struktur) ---
from .registry import resolve_engine
from ..Problem.builder import build_pymoo_problem
from ..Optimizers.wrappers import run_pymoo

from .paths import _scenario_tag

# Reporting-Module liegen in run/analysis
from ...run.analysis import csv_exports
from ...run.analysis import plots
from ...run.analysis import summary


# -------------------------------
# Helper
# -------------------------------
def _safe_str(x: Any, fallback: str = "") -> str:
    try:
        return str(x) if x is not None else fallback
    except Exception:
        return fallback


def _now_run_id(tag: str) -> str:
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    tag = tag.strip().replace(" ", "_") if tag else "run"
    return f"{ts}_{tag}"


def _resolve_runs_root(output_root: Optional[str | Path]) -> Path:
    """
    Wohin sollen Ergebnisse geschrieben werden?
    - Wenn settings.reporting.output_root gesetzt ist -> dorthin.
    - Sonst Standard: ./Optimization/run/results
    """
    if output_root:
        root = Path(output_root).expanduser().resolve()
    else:
        root = Path.cwd() / "Optimization" / "run" / "results"
    root.mkdir(parents=True, exist_ok=True)
    return root


def _write_json(path: Path, payload: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False)


# -------------------------------
# Public API
# -------------------------------
def run(s) -> Dict[str, Any]:
    """
    Orchestriert einen vollständigen Optimierungslauf:
      1) Engine per Registry wählen (gold/fast/surrogate)
      2) Run-Verzeichnis aufbauen
      3) Optimierungsproblem bauen & Optimizer laufen lassen
      4) Ergebnisse (X/F/G) persistieren
      5) Reporting: CSV, Pareto-Plot, Summary
      6) _LATEST_RUN Marker schreiben
    """

    # ---- (1) Settings auslesen ----
    eng_cfg = getattr(s, "engine", None)

    eng_name = _safe_str(getattr(eng_cfg, "name", "surrogate")).lower().strip() or "surrogate"
    location = _safe_str(getattr(eng_cfg, "location", "UnknownLocation")) or "UnknownLocation"
    system_id = _safe_str(getattr(eng_cfg, "system_id", "UNKNOWN_SYSTEM")) or "UNKNOWN_SYSTEM"

    # Szenario (V2H / NoV2H) abgeleitet aus system_id, nicht mehr aus einem Flag
    mode = _scenario_tag(system_id)


    reporting = getattr(s, "reporting", None)
    output_root = getattr(reporting, "output_root", None)
    write_csv = bool(getattr(reporting, "write_csv", True))
    write_plot = bool(getattr(reporting, "write_plot", True))
    write_summary_flag = bool(getattr(reporting, "write_summary", True))

    run_tag = _safe_str(getattr(getattr(s, "run", None), "tag", "run"))
    run_id = _now_run_id(run_tag)

    runs_root = _resolve_runs_root(output_root)
    run_dir = (runs_root / location / mode / eng_name / run_id).resolve()
    run_dir.mkdir(parents=True, exist_ok=True)

    print(f"[optimize] results root : {runs_root}")
    print(f"[optimize] run dir      : {run_dir}")
    print(f"[optimize] run id       : {run_id}")
    print(f"[optimize] engine       : {eng_name} | location={location} | system_id={system_id} | mode={mode}")

    # ---- (2) Engine wählen & instanziieren ----
    Eng = resolve_engine(eng_name)
    try:
        engine = Eng(settings=s, run_dir=str(run_dir))  # manche Engines akzeptieren run_dir
    except TypeError:
        engine = Eng(settings=s)

    # Optionale Artefakt-Spiegelung (z. B. Surrogat-Training in den Run-Ordner legen)
    if hasattr(engine, "run"):
        try:
            engine.run(str(run_dir))
        except Exception as e:
            print(f"[optimize] engine.run() skipped: {e}")

    # ---- (3) Optimierungsproblem bauen ----
    try:
        problem = build_pymoo_problem(
            getattr(s, "bounds", None),
            getattr(s, "objectives", None),
            getattr(s, "constraints", None),
            engine,
        )
    except Exception:
        print("[optimize] FAILED to build problem. See traceback below.")
        traceback.print_exc()
        raise

    # ---- (4) Optimizer laufen lassen ----
    try:
        optimizer_cfg = getattr(s, "optimizer", None)
        seed = getattr(optimizer_cfg, "seed", None)
        res = run_pymoo(problem, optimizer_cfg, seed=seed)
    except Exception:
        print("[optimize] FAILED to run optimizer. See traceback below.")
        traceback.print_exc()
        raise

    # Ergebnisse herausziehen und auf 2D normalisieren
    X_attr = getattr(res, "X", None)
    F_attr = getattr(res, "F", None)

    X_opt = np.asarray(X_attr, dtype=float) if X_attr is not None else np.empty((0, len(getattr(s.bounds, "names", []))))
    F_opt = np.asarray(F_attr, dtype=float) if F_attr is not None else np.empty((0, len(getattr(s.objectives, "names", []))))

    # Immer 2D: (n_points, n_vars) / (n_points, n_obj)
    if X_opt.ndim == 0:
        X_opt = np.empty((0, len(getattr(s.bounds, "names", []))), float)
    elif X_opt.ndim == 1:
        X_opt = X_opt.reshape(1, -1)

    if F_opt.ndim == 0:
        F_opt = np.empty((0, len(getattr(s.objectives, "names", []))), float)
    elif F_opt.ndim == 1:
        F_opt = F_opt.reshape(1, -1)


    G_attr = getattr(res, "G", None)
    if G_attr is not None:
        # Pymoo hat G bereits mit der richtigen Form geschrieben (n_points, n_con)
        G_opt = np.asarray(G_attr, dtype=float)
    else:
        # Keine Nebenbedingungen → leere G-Matrix mit passender Zeilenzahl
        n_points = X_opt.shape[0] if X_opt.ndim >= 2 else 0
        G_opt = np.zeros((n_points, 0), dtype=float)

    # ---- (5) Roh-Ergebnisse persistieren ----
    try:
        np.save(run_dir / "X_opt.npy", X_opt)
        np.save(run_dir / "F_opt.npy", F_opt)
        if G_opt.size:
            np.save(run_dir / "G_opt.npy", G_opt)
        _write_json(
            run_dir / "results.json",
            {
                "run_id": run_id,
                "engine": eng_name,
                "location": location,
                "mode": mode,
                "objectives": getattr(getattr(s, "objectives", None), "names", []),
                "constraints": getattr(getattr(s, "constraints", None), "names", []),
                "X_shape": list(X_opt.shape),
                "F_shape": list(F_opt.shape),
                "G_shape": list(G_opt.shape) if G_opt.size else [0, 0],
            },
        )
    except Exception:
        print("[optimize] FAILED to persist raw results (npy/json). See traceback below.")
        traceback.print_exc()

    # ---- (6) Reporting je Settings ----
    try:
        if write_csv:
            csv_exports.export_pareto_csv(
                run_dir=str(run_dir),
                settings=s,
                X_opt=X_opt,
                F_opt=F_opt,
                G_opt=G_opt if G_opt.size else None,
                use_teacher_for_details=True,  # auf True stellen, wenn FAST-KPIs verfügbar
            )
    except Exception:
        print("[optimize] CSV export failed. See traceback below.")
        traceback.print_exc()

    try:
        if write_csv and len(X_opt):
            # Zweiter Export: stündliche Lastflüsse für ausgewählte Punkte
            csv_exports.export_load_flows_timeseries(
                run_dir=str(run_dir),
                settings=s,
                X_opt=X_opt,
                max_points=5,  # oder None, wenn du ALLE Pareto-Punkte willst
            )
    except Exception:
        print("[optimize] Load-flows export failed. See traceback below.")
        traceback.print_exc()


    try:
        if write_plot:
            obj_names = getattr(getattr(s, "objectives", None), "names", [])
            plots.save_pareto_plot(str(run_dir), F_opt, obj_names)
    except Exception:
        print("[optimize] Pareto plot failed. See traceback below.")
        traceback.print_exc()

    try:
        if write_summary_flag:
            summary.write_summary(str(run_dir), s, X_opt, F_opt)
    except Exception:
        print("[optimize] Summary writer failed. See traceback below.")
        traceback.print_exc()

    # ---- (7) _LATEST_RUN Marker setzen ----
    try:
        eng_root = (runs_root / location / mode / eng_name).resolve()
        eng_root.mkdir(parents=True, exist_ok=True)
        _write_json(eng_root / "_LATEST_RUN.json", {"run_id": run_id, "path": str(run_dir)})
        (eng_root / "_LATEST_RUN.txt").write_text(run_id, encoding="utf-8")
    except Exception:
        print("[optimize] Failed to write _LATEST_RUN markers.")
        traceback.print_exc()

    return {
        "run_dir": str(run_dir),
        "run_id": run_id,
        "engine": eng_name,
        "location": location,
        "system_id": system_id,
        "mode": mode,
        "n_points": int(len(X_opt)),
    }
