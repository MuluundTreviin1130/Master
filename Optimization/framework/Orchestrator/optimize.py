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
from ..feasibility import apply_feasibility_gate
from ..Problem.builder import build_pymoo_problem
from ..Optimizers.wrappers import run_pymoo

# Reporting-Module liegen in run/analysis
from ...run.analysis import csv_exports
from ...run.analysis import plots
from ...run.analysis import run_metrics
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


def _scheduler_metadata(s: Any) -> Dict[str, Any]:
    sched = getattr(s, "scheduler", None)
    hv_cfg = getattr(s, "hypervolume", None)
    enabled = bool(getattr(sched, "enabled", False)) if sched is not None else False
    out: Dict[str, Any] = {
        "enabled": enabled,
        "mode": "normal_optimization" if not enabled else "scheduler_meta_run",
    }
    if not enabled or sched is None:
        return out

    n_gen = int(getattr(getattr(s, "optimizer", None), "kwargs", {}).get("n_gen", 0))
    min_resource = int(getattr(sched, "min_resource", 1))
    reduction = int(getattr(sched, "reduction_factor", 3))
    stages = 1
    b = max(1, min_resource)
    while b < max(1, n_gen):
        stages += 1
        b *= max(2, reduction)

    out.update(
        {
            "name": "successive_halving" if str(getattr(sched, "pruner", "successive_halving")).lower() == "successive_halving" else "hyperband",
            "pruner": str(getattr(sched, "pruner", "successive_halving")),
            "reduction_factor": reduction,
            "min_resource": min_resource,
            "n_stages": int(stages),
            "n_trials": int(getattr(sched, "n_trials", 0)),
            "hv_mode": str(getattr(hv_cfg, "mode", "off")) if hv_cfg is not None else "off",
            "hv_reference_point": list(getattr(hv_cfg, "reference_point", None) or []),
            "budget_param": str(getattr(sched, "budget_param", "n_gen")),
        }
    )
    return out


def _print_run_header(s: Any, runs_root: Path, run_dir: Path, run_id: str, eng_name: str, location: str, system_id: str) -> None:
    sched_meta = _scheduler_metadata(s)
    dispatch_cfg = getattr(s, "dispatch", None)
    dispatch_mode = _safe_str(getattr(dispatch_cfg, "mode", None), "none")
    stochastic_enabled = bool(getattr(dispatch_cfg, "stochastic_enabled", False)) if dispatch_cfg is not None else False
    scenario_source = _safe_str(getattr(dispatch_cfg, "scenario_source", None), "")
    obj_names = list(getattr(getattr(s, "objectives", None), "names", []) or [])
    feat = getattr(getattr(s, "engine", None), "features", None)
    thermflex_enabled = bool(getattr(feat, "enable_thermflex", False)) if feat is not None else False
    run_cfg = getattr(s, "run", None)
    profile_start = getattr(run_cfg, "profile_start", None) if run_cfg is not None else None
    profile_hours = getattr(run_cfg, "profile_hours", None) if run_cfg is not None else None

    print(f"[optimize] results root : {runs_root}", flush=True)
    print(f"[optimize] run dir      : {run_dir}", flush=True)
    print(f"[optimize] run id       : {run_id}", flush=True)
    print(f"[optimize] engine       : {eng_name} | location={location} | system_id={system_id}", flush=True)
    print(
        "[optimize] dispatch     : "
        f"{dispatch_mode}"
        + (" | stochastic=on" if stochastic_enabled else " | stochastic=off")
        + (f" | source={scenario_source}" if scenario_source else "")
    , flush=True)
    print(
        "[optimize] objective    : "
        + (", ".join(str(x) for x in obj_names) if obj_names else "none")
    , flush=True)
    print(f"[optimize] thermflex    : {'on' if thermflex_enabled else 'off'}", flush=True)
    if profile_start and profile_hours:
        print(f"[optimize] run slice    : start={profile_start} | hours={profile_hours}", flush=True)
    if bool(sched_meta.get("enabled", False)):
        print(
            "[optimize] scheduler    : "
            f"{sched_meta.get('name', 'scheduler')} | "
            f"pruner={sched_meta.get('pruner')} | "
            f"budget={sched_meta.get('budget_param')} | "
            f"min_resource={sched_meta.get('min_resource')} | "
            f"reduction_factor={sched_meta.get('reduction_factor')} | "
            f"n_trials={sched_meta.get('n_trials')} | "
            f"n_stages={sched_meta.get('n_stages')}"
        , flush=True)
    else:
        print("[optimize] scheduler    : disabled", flush=True)


def _run_metadata(s: Any, runtime_meta: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    eng = getattr(s, "engine", None)
    feat = getattr(eng, "features", None) if eng is not None else None
    members_cfg = getattr(eng, "members", None) if eng is not None else None
    members_total = int(getattr(members_cfg, "N_EC", 0)) if members_cfg is not None else 0
    active_member_types = 0
    if members_cfg is not None and getattr(members_cfg, "members", None):
        active_member_types = sum(1 for m in members_cfg.members if int(getattr(m, "count", 0)) > 0)

    meta: Dict[str, Any] = {
        "system_id": str(getattr(eng, "system_id", "")),
        "location": str(getattr(eng, "location", "")),
        "country_code": str(getattr(eng, "country_code", "")),
        "features": {
            "enable_bess": bool(getattr(feat, "enable_bess", False)),
            "enable_v2h": bool(getattr(feat, "enable_v2h", False)),
            "enable_h2": bool(getattr(feat, "enable_h2", False)),
            "enable_thermflex": bool(getattr(feat, "enable_thermflex", False)),
            "enable_small_wind": bool(getattr(feat, "enable_small_wind", False)),
            "enable_large_wind": bool(getattr(feat, "enable_large_wind", False)),
            "enable_biogas_engine": bool(getattr(feat, "enable_biogas_engine", False)),
            "enable_wood_gasifier": bool(getattr(feat, "enable_wood_gasifier", False)),
        },
        "counts": {
            "N_EC": int(getattr(eng, "N_EC", 0)),
            "N_HH": int(getattr(eng, "N_HH", 0)),
            "N_EV_total": int(getattr(eng, "N_EV_total", 0)),
            "N_EV_bidirectional": int(getattr(eng, "N_EV_bidirectional", 0)),
            "members_total_count": members_total,
            "active_member_types": int(active_member_types),
        },
        "scheduler": _scheduler_metadata(s),
        "constraints": {
            "names": list(getattr(getattr(s, "constraints", None), "names", []) or []),
            "senses": list(getattr(getattr(s, "constraints", None), "senses", []) or []),
            "rhs": [float(x) for x in (getattr(getattr(s, "constraints", None), "rhs", []) or [])],
        },
    }
    if runtime_meta:
        meta.update(runtime_meta)
    return meta


# -------------------------------
# Public API
# -------------------------------
def run(s, runtime_meta: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """
    Orchestriert einen vollstÃ¤ndigen Optimierungslauf:
      1) Engine per Registry wÃ¤hlen (gold/surrogate/gated)
      2) Run-Verzeichnis aufbauen
      3) Optimierungsproblem bauen & Optimizer laufen lassen
      4) Ergebnisse (X/F/G) persistieren
      5) Reporting: CSV, Pareto-Plot, Summary
      6) _LATEST_RUN Marker schreiben
    """

    t_run_start = datetime.now()

    # ---- (1) Settings auslesen ----
    eng_cfg = getattr(s, "engine", None)
    setattr(s, "_runtime_meta", dict(runtime_meta or {}))

    eng_name = _safe_str(getattr(eng_cfg, "name", "surrogate")).lower().strip() or "surrogate"
    location = _safe_str(getattr(eng_cfg, "location", "UnknownLocation")) or "UnknownLocation"
    system_id = _safe_str(getattr(eng_cfg, "system_id", "UNKNOWN_SYSTEM")) or "UNKNOWN_SYSTEM"

    reporting = getattr(s, "reporting", None)
    output_root = getattr(reporting, "output_root", None)
    write_csv = bool(getattr(reporting, "write_csv", True))
    write_timeseries = bool(getattr(reporting, "write_timeseries", True))
    timeseries_max_points = getattr(reporting, "timeseries_max_points", 5)
    write_plot = bool(getattr(reporting, "write_plot", True))
    write_summary_flag = bool(getattr(reporting, "write_summary", True))

    run_tag = _safe_str(getattr(getattr(s, "run", None), "tag", "run"))
    run_id = _now_run_id(run_tag)

    runs_root = _resolve_runs_root(output_root)
    run_dir = (runs_root / location / eng_name / run_id).resolve()
    run_dir.mkdir(parents=True, exist_ok=True)

    _print_run_header(s, runs_root, run_dir, run_id, eng_name, location, system_id)

    optimizer_cfg = getattr(s, "optimizer", None)
    optimizer_kwargs = getattr(optimizer_cfg, "kwargs", {}) or {}
    pop_size = int(optimizer_kwargs.get("pop_size", 0) or 0)
    n_gen = int(optimizer_kwargs.get("n_gen", 0) or 0)
    block_timings: Dict[str, float] = {
        "engine_init_walltime_s": 0.0,
        "problem_build_walltime_s": 0.0,
        "optimization_walltime_s": 0.0,
        "persist_walltime_s": 0.0,
        "csv_export_walltime_s": 0.0,
        "timeseries_export_walltime_s": 0.0,
        "plot_walltime_s": 0.0,
        "summary_walltime_s": 0.0,
        "postprocess_walltime_s": 0.0,
        "latest_marker_walltime_s": 0.0,
    }

    # ---- (2) Engine wÃ¤hlen & instanziieren ----
    t_block = datetime.now()
    print("[optimize] engine init  : start", flush=True)
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
            print(f"[optimize] engine.run() skipped: {e}", flush=True)
    block_timings["engine_init_walltime_s"] = (datetime.now() - t_block).total_seconds()
    print(f"[optimize] engine init  : done | walltime_s={block_timings['engine_init_walltime_s']:.1f}", flush=True)

    # ---- (3) Optimierungsproblem bauen ----
    t_block = datetime.now()
    print("[optimize] problem build : start", flush=True)
    try:
        problem = build_pymoo_problem(
            getattr(s, "bounds", None),
            getattr(s, "objectives", None),
            getattr(s, "constraints", None),
            engine,
        )
    except Exception:
        print("[optimize] FAILED to build problem. See traceback below.", flush=True)
        traceback.print_exc()
        raise
    block_timings["problem_build_walltime_s"] = (datetime.now() - t_block).total_seconds()
    print(f"[optimize] problem build : done | walltime_s={block_timings['problem_build_walltime_s']:.1f}", flush=True)

    # ---- (4) Optimizer laufen lassen ----
    t_block = datetime.now()
    print("[optimize] optimizer     : start", flush=True)
    try:
        seed = getattr(optimizer_cfg, "seed", None)
        res = run_pymoo(problem, optimizer_cfg, seed=seed)
    except Exception:
        print("[optimize] FAILED to run optimizer. See traceback below.", flush=True)
        traceback.print_exc()
        raise
    block_timings["optimization_walltime_s"] = (datetime.now() - t_block).total_seconds()
    print(f"[optimize] optimizer     : done | walltime_s={block_timings['optimization_walltime_s']:.1f}", flush=True)

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
    n_constraints = int(len(getattr(getattr(s, "constraints", None), "names", []) or []))
    if G_attr is not None:
        # Pymoo hat G bereits mit der richtigen Form geschrieben (n_points, n_con)
        G_opt = np.asarray(G_attr, dtype=float)
        if G_opt.ndim == 1:
            G_opt = G_opt.reshape(1, -1)
    else:
        # Fallback: preserve declared constraint width, even with zero points.
        n_points = X_opt.shape[0] if X_opt.ndim >= 2 else 0
        G_opt = np.zeros((n_points, n_constraints), dtype=float)

    # ---- (4b) Optional feasibility-aware gold verification on selected final candidates ----
    try:
        F_opt, G_opt, feasibility_meta = apply_feasibility_gate(
            settings=s,
            engine=engine,
            X=X_opt,
            F=F_opt,
            G=G_opt,
            runtime_meta=runtime_meta,
        )
        setattr(s, "_feasibility_meta", dict(feasibility_meta or {}))
    except Exception:
        print("[optimize] feasibility-aware verification failed. See traceback below.")
        traceback.print_exc()
        setattr(s, "_feasibility_meta", {"enabled": True, "applied": False, "reason": "exception"})

    # ---- (5) Roh-Ergebnisse persistieren ----
    t_block = datetime.now()
    try:
        np.save(run_dir / "X_opt.npy", X_opt)
        np.save(run_dir / "F_opt.npy", F_opt)
        if n_constraints > 0:
            np.save(run_dir / "G_opt.npy", G_opt)
        objective_names = list(getattr(getattr(s, "objectives", None), "names", []) or [])
        run_metadata = _run_metadata(s, runtime_meta=runtime_meta)
        run_metadata["feasibility"] = dict(getattr(s, "_feasibility_meta", {}) or {})
        # Keep objective names in metadata for scheduler/meta-run labeling.
        run_metadata["objective_names"] = objective_names
        _write_json(
            run_dir / "results.json",
            {
                "run_id": run_id,
                "engine": eng_name,
                "location": location,
                "mode": "features",
                "objectives": objective_names,
                "constraints": {
                    "names": list(getattr(getattr(s, "constraints", None), "names", []) or []),
                    "senses": list(getattr(getattr(s, "constraints", None), "senses", []) or []),
                    "rhs": [float(x) for x in (getattr(getattr(s, "constraints", None), "rhs", []) or [])],
                },
                "X_shape": list(X_opt.shape),
                "F_shape": list(F_opt.shape),
                "G_shape": list(G_opt.shape) if G_opt.size else [0, 0],
                "metadata": run_metadata,
                "exports": {
                    "dispatch_kpis_json": str(getattr(getattr(s, "reporting", None), "dispatch_kpis_json_filename", "dispatch_kpis.json")),
                    "dispatch_kpis_csv": str(getattr(getattr(s, "reporting", None), "dispatch_kpis_csv_filename", "dispatch_kpis.csv")),
                    "thermflex_hourly_csv": str(getattr(getattr(s, "reporting", None), "thermflex_hourly_csv_filename", "thermflex_hourly.csv")),
                },
            },
        )
    except Exception:
        print("[optimize] FAILED to persist raw results (npy/json). See traceback below.")
        traceback.print_exc()
    block_timings["persist_walltime_s"] = (datetime.now() - t_block).total_seconds()

    # ---- (6) Reporting je Settings ----
    t_post = datetime.now()
    t_block = datetime.now()
    try:
        if write_csv:
            csv_exports.export_pareto_csv(
                run_dir=str(run_dir),
                settings=s,
                X_opt=X_opt,
                F_opt=F_opt,
                G_opt=G_opt if G_opt.size else None,
                use_teacher_for_details=False,  # set True to include teacher-side detailed KPIs
            )
    except Exception:
        print("[optimize] CSV export failed. See traceback below.")
        traceback.print_exc()
    block_timings["csv_export_walltime_s"] = (datetime.now() - t_block).total_seconds()

    t_block = datetime.now()
    try:
        if write_csv and write_timeseries and len(X_opt):
            # Zweiter Export: stÃ¼ndliche LastflÃ¼sse fÃ¼r ausgewÃ¤hlte Punkte
            csv_exports.export_load_flows_timeseries(
                run_dir=str(run_dir),
                settings=s,
                X_opt=X_opt,
                max_points=timeseries_max_points,
            )
    except Exception:
        print("[optimize] Load-flows export failed. See traceback below.")
        traceback.print_exc()
    block_timings["timeseries_export_walltime_s"] = (datetime.now() - t_block).total_seconds()


    t_block = datetime.now()
    try:
        if write_plot:
            obj_names = getattr(getattr(s, "objectives", None), "names", [])
            plots.save_pareto_plot(str(run_dir), F_opt, obj_names)
    except Exception:
        print("[optimize] Pareto plot failed. See traceback below.")
        traceback.print_exc()
    block_timings["plot_walltime_s"] = (datetime.now() - t_block).total_seconds()

    t_block = datetime.now()
    try:
        if write_summary_flag:
            summary.write_summary(str(run_dir), s, X_opt, F_opt)
    except Exception:
        print("[optimize] Summary writer failed. See traceback below.")
        traceback.print_exc()
    block_timings["summary_walltime_s"] = (datetime.now() - t_block).total_seconds()
    block_timings["postprocess_walltime_s"] = (datetime.now() - t_post).total_seconds()

    # ---- (7) _LATEST_RUN Marker setzen ----
    t_block = datetime.now()
    try:
        eng_root = (runs_root / location / eng_name).resolve()
        eng_root.mkdir(parents=True, exist_ok=True)
        _write_json(eng_root / "_LATEST_RUN.json", {"run_id": run_id, "path": str(run_dir)})
        (eng_root / "_LATEST_RUN.txt").write_text(run_id, encoding="utf-8")
    except Exception:
        print("[optimize] Failed to write _LATEST_RUN markers.")
        traceback.print_exc()
    block_timings["latest_marker_walltime_s"] = (datetime.now() - t_block).total_seconds()

    total_walltime_s = (datetime.now() - t_run_start).total_seconds()
    effective_evaluations = int(pop_size * n_gen) if pop_size > 0 and n_gen > 0 else None
    run_metrics.write_run_metrics(
        run_dir,
        {
            "run_type": "optimization",
            "engine": eng_name,
            "location": location,
            "system_id": system_id,
            "run_id": run_id,
            "run_dir": str(run_dir),
            "started_at": t_run_start.isoformat(timespec="seconds"),
            "finished_at": datetime.now().isoformat(timespec="seconds"),
            "total_walltime_s": total_walltime_s,
            "n_points": int(len(X_opt)),
            "optimizer": {
                "name": _safe_str(getattr(optimizer_cfg, "name", "")),
                "pop_size": pop_size,
                "n_gen": n_gen,
                "n_jobs": int(getattr(optimizer_cfg, "n_jobs", 0) or 0),
                "seed": getattr(optimizer_cfg, "seed", None),
            },
            "evaluation_metrics": {
                "baseline_full_evaluations": effective_evaluations,
                "effective_evaluations": effective_evaluations,
                "evaluations_saved_abs": 0,
                "evaluations_saved_pct": 0.0,
                "mean_eval_walltime_s": (
                    float(block_timings["optimization_walltime_s"] / effective_evaluations)
                    if effective_evaluations
                    else None
                ),
                "median_eval_walltime_s": None,
                "p95_eval_walltime_s": None,
                "max_eval_walltime_s": None,
            },
            "block_timings_s": block_timings,
        },
    )

    return {
        "run_dir": str(run_dir),
        "run_id": run_id,
        "engine": eng_name,
        "location": location,
        "system_id": system_id,
        "mode": "features",
        "n_points": int(len(X_opt)),
        "metrics_path": str(Path(run_dir) / "run_metrics.json"),
    }

