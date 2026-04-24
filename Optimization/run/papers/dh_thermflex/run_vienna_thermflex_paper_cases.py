from __future__ import annotations

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
    raise RuntimeError("[run_vienna_thermflex_paper_cases] project root not found.")
project_root_str = str(project_root.resolve())
if project_root_str not in sys.path:
    sys.path.insert(0, project_root_str)

from Settings import get_settings
from Optimization.framework.Orchestrator.optimize import run


DEFAULT_CASES = (
    Path("Optimization")
    / "validation"
    / "model_validation"
    / "overrides"
    / "thermflex",
    (
        "vienna_ref2023_dh_baseline_constant_no_thermflex_paper_day_ahead.json",
        "vienna_ref2023_dh_day_night_no_thermflex_paper_day_ahead.json",
        "vienna_ref2023_dh_day_night_thermflex_paper_day_ahead.json",
    ),
)


def _load_overrides(path: Path) -> dict:
    if not path.exists():
        raise FileNotFoundError(f"[run_vienna_thermflex_paper_cases] overrides file not found: {path}")
    return json.loads(path.read_text(encoding="utf-8-sig"))


if __name__ == "__main__":
    base_dir, filenames = DEFAULT_CASES
    results: list[dict[str, object]] = []
    for filename in filenames:
        path = base_dir / filename
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
            f"[run_vienna_thermflex_paper_cases] finished {filename} -> {result.get('run_dir')} "
            f"({dt:.2f} s)",
            flush=True,
        )
    print(json.dumps(results, indent=2, ensure_ascii=False), flush=True)
