from __future__ import annotations

"""Optimization entrypoint.

Default behavior is unchanged: without scheduler flag this runs a normal
optimization. All runtime mutations flow through get_settings(overrides=...).
"""

import argparse
import json
import time
from pathlib import Path
import sys

# Project-root bootstrap so `Settings` is importable when script is run directly.
current = Path(__file__).resolve()
project_root = None
for parent in current.parents:
    if (parent / "Optimization").is_dir() and (parent / "Data").is_dir():
        project_root = parent
        break
if project_root is None:
    raise RuntimeError(
        f"[run_optimization] Project root (with Optimization + Data) not found.\n"
        f"  cwd={Path.cwd()}\n"
        f"  script={current}"
    )
project_root_str = str(project_root.resolve())
if project_root_str not in sys.path:
    sys.path.insert(0, project_root_str)

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(line_buffering=True)
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(line_buffering=True)

from Settings import get_settings
from Optimization.framework.Orchestrator.optimize import run
from Optimization.framework.scheduler.successive_halving import run_scheduler
from Optimization.run.analysis.run_metrics import write_run_metrics

CLICK_RUN_DEFAULT_OVERRIDES = (
    Path("Optimization")
    / "validation"
    / "model_validation"
    / "overrides"
    / "thermflex"
    / "vienna_ref2023_dh_day_night_thermflex_two_stage.json"
)


def _load_json(path: str | None) -> dict:
    if not path:
        if len(sys.argv) <= 1:
            if not CLICK_RUN_DEFAULT_OVERRIDES.exists():
                raise FileNotFoundError(
                    "[run_optimization] click-run default overrides file not found: "
                    f"{CLICK_RUN_DEFAULT_OVERRIDES}. Pass --overrides-json explicitly "
                    "or restore the tracked SSOT override file."
                )
            print(
                "[run_optimization] No CLI arguments provided. "
                f"Using click-run default overrides: {CLICK_RUN_DEFAULT_OVERRIDES}",
                flush=True,
            )
            path = str(CLICK_RUN_DEFAULT_OVERRIDES)
        else:
            return {}
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"[run_optimization] overrides file not found: {p}")
    return json.loads(p.read_text(encoding="utf-8-sig"))


def _parse_args() -> argparse.Namespace:
    ap = argparse.ArgumentParser()
    ap.add_argument("--overrides-json", type=str, default=None, help="Path to JSON overrides passed to get_settings(overrides=...).")
    ap.add_argument("--scheduler-enabled", action="store_true", help="Enable Optuna SH/Hyperband meta-run.")
    ap.add_argument("--scheduler-pruner", type=str, choices=["successive_halving", "hyperband"], default=None)
    ap.add_argument("--scheduler-trials", type=int, default=None)
    ap.add_argument("--scheduler-ref-point", type=str, default=None, help="Comma-separated HV ref point, e.g. '1e7,1e7'.")
    ap.add_argument("--scheduler-min-resource", type=int, default=None)
    ap.add_argument("--scheduler-reduction-factor", type=int, default=None)
    return ap.parse_args()


def _build_overrides(args: argparse.Namespace) -> dict:
    overrides = _load_json(args.overrides_json)
    if args.scheduler_enabled:
        sched = overrides.setdefault("scheduler", {})
        sched["enabled"] = True
        if args.scheduler_pruner:
            sched["pruner"] = args.scheduler_pruner
        if args.scheduler_trials is not None:
            sched["n_trials"] = int(args.scheduler_trials)
        if args.scheduler_min_resource is not None:
            sched["min_resource"] = int(args.scheduler_min_resource)
        if args.scheduler_reduction_factor is not None:
            sched["reduction_factor"] = int(args.scheduler_reduction_factor)
        if args.scheduler_ref_point:
            hv = overrides.setdefault("hypervolume", {})
            hv["mode"] = "fixed"
            hv["reference_point"] = [float(x.strip()) for x in str(args.scheduler_ref_point).split(",") if x.strip()]
    return overrides


if __name__ == "__main__":
    args = _parse_args()
    overrides = _build_overrides(args)

    t0 = time.perf_counter()
    settings = get_settings(overrides=overrides)
    if bool(getattr(settings.scheduler, "enabled", False)):
        result = run_scheduler(base_overrides=overrides)
    else:
        result = run(settings)
    t1 = time.perf_counter()

    print("Run finished. Results:", result.get("run_dir"), flush=True)
    print(f"[timing] total_run_s = {t1 - t0:.2f} s", flush=True)
    if result.get("run_dir"):
        write_run_metrics(
            result["run_dir"],
            {
                "entrypoint_total_walltime_s": float(t1 - t0),
            },
        )
