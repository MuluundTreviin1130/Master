from __future__ import annotations

"""Run the explicit constant-thermflex sensitivity case block.

This runner exists to keep the sensitivity study reproducible:
- every case is backed by an explicit override JSON,
- all cases use the same constant-reference paper slice,
- there are no hidden generated overrides at runtime.
"""

import json
import time
from pathlib import Path
import sys


current = Path(__file__).resolve()
project_root = None
for parent in current.parents:
    if (parent / "Optimization").is_dir() and (parent / "Data").is_dir():
        project_root = parent
        break
if project_root is None:
    raise RuntimeError("[run_vienna_constant_thermflex_sensitivity_cases] project root not found.")
project_root_str = str(project_root.resolve())
if project_root_str not in sys.path:
    sys.path.insert(0, project_root_str)

from Settings import get_settings
from Optimization.framework.Orchestrator.optimize import run


BASE_DIR = (
    Path("Optimization")
    / "validation"
    / "model_validation"
    / "overrides"
    / "thermflex"
)

CASE_FILES = (
    "vienna_ref2023_dh_baseline_constant_no_thermflex_paper_day_ahead.json",
    "vienna_ref2023_dh_baseline_constant_thermflex_lb21p0_dur1_evt1_paper_day_ahead.json",
    "vienna_ref2023_dh_baseline_constant_thermflex_paper_day_ahead.json",
    "vienna_ref2023_dh_baseline_constant_thermflex_lb21p0_dur2_evt1_paper_day_ahead.json",
    "vienna_ref2023_dh_baseline_constant_thermflex_lb21p0_dur6_evt1_paper_day_ahead.json",
    "vienna_ref2023_dh_baseline_constant_thermflex_lb21p0_dur8_evt1_paper_day_ahead.json",
    "vienna_ref2023_dh_baseline_constant_thermflex_lb21p0_dur24_evt1_paper_day_ahead.json",
    "vienna_ref2023_dh_baseline_constant_thermflex_lb21p0_dur24_evt24_paper_day_ahead.json",
    "vienna_ref2023_dh_baseline_constant_thermflex_lb22p5_dur4_evt1_upper_only_paper_day_ahead.json",
    "vienna_ref2023_dh_baseline_constant_thermflex_lb22p5_dur24_evt24_upper_only_proxy_paper_day_ahead.json",
    "vienna_ref2023_dh_baseline_constant_thermflex_lb21p5_dur4_evt1_paper_day_ahead.json",
    "vienna_ref2023_dh_baseline_constant_thermflex_lb20p0_dur4_evt1_paper_day_ahead.json",
    "vienna_ref2023_dh_baseline_constant_thermflex_lb21p0_dur4_evt2_paper_day_ahead.json",
)


def _load_overrides(path: Path) -> dict:
    if not path.exists():
        raise FileNotFoundError(f"[run_vienna_constant_thermflex_sensitivity_cases] overrides file not found: {path}")
    return json.loads(path.read_text(encoding="utf-8-sig"))


if __name__ == "__main__":
    results: list[dict[str, object]] = []
    for filename in CASE_FILES:
        path = BASE_DIR / filename
        t0 = time.perf_counter()
        overrides = _load_overrides(path)
        settings = get_settings(overrides=overrides)
        result = run(settings)
        dt = time.perf_counter() - t0
        results.append(
            {
                "case": filename,
                "run_dir": result.get("run_dir"),
                "walltime_s": float(dt),
            }
        )
        print(
            f"[run_vienna_constant_thermflex_sensitivity_cases] finished {filename} -> {result.get('run_dir')} "
            f"({dt:.2f} s)",
            flush=True,
        )
    print(json.dumps(results, indent=2, ensure_ascii=False), flush=True)
