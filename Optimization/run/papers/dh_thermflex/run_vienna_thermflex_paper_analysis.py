from __future__ import annotations

import json
from pathlib import Path
import sys

current = Path(__file__).resolve()
project_root = None
for parent in current.parents:
    if (parent / "Optimization").is_dir() and (parent / "Data").is_dir():
        project_root = parent
        break
if project_root is None:
    raise RuntimeError("[run_vienna_thermflex_paper_analysis] project root not found.")
project_root_str = str(project_root.resolve())
if project_root_str not in sys.path:
    sys.path.insert(0, project_root_str)

from Optimization.run.analysis.build_paper_dispatch_comparison import build_paper_dispatch_comparison


CASE_SPECS = (
    ("baseline_constant_no_thermflex", "vienna_ref2023_dh_baseline_constant_no_thermflex_paper_day_ahead"),
    ("day_night_no_thermflex", "vienna_ref2023_dh_day_night_no_thermflex_paper_day_ahead"),
    ("day_night_thermflex", "vienna_ref2023_dh_day_night_thermflex_paper_day_ahead"),
)


def _resolve_latest_run_dir(results_root: Path, run_suffix: str) -> Path:
    matches = [p for p in results_root.iterdir() if p.is_dir() and p.name.endswith(run_suffix)]
    if not matches:
        raise FileNotFoundError(
            f"[run_vienna_thermflex_paper_analysis] no run directory found for suffix '{run_suffix}' in {results_root}"
        )
    matches.sort(key=lambda p: p.name, reverse=True)
    selected = matches[0]
    dispatch_path = selected / "dispatch_kpis.json"
    if not dispatch_path.exists():
        raise FileNotFoundError(
            f"[run_vienna_thermflex_paper_analysis] dispatch_kpis.json missing in selected run: {selected}"
        )
    return selected


if __name__ == "__main__":
    results_root = project_root / "Optimization" / "run" / "results" / "Vienna" / "gold"
    if not results_root.exists():
        raise FileNotFoundError(f"[run_vienna_thermflex_paper_analysis] results root not found: {results_root}")

    labels: list[str] = []
    run_dirs: list[Path] = []
    resolution_report: list[dict[str, str]] = []
    for label, suffix in CASE_SPECS:
        run_dir = _resolve_latest_run_dir(results_root, suffix)
        labels.append(label)
        run_dirs.append(run_dir)
        resolution_report.append({"label": label, "run_dir": str(run_dir)})

    output_dir = build_paper_dispatch_comparison(run_dirs=run_dirs, labels=labels)
    report_path = output_dir / "selected_runs.json"
    report_path.write_text(json.dumps(resolution_report, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"[run_vienna_thermflex_paper_analysis] output_dir={output_dir}")
