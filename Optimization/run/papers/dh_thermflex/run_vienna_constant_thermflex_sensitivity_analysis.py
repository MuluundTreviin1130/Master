from __future__ import annotations

"""Analyse the explicit constant thermflex sensitivity case block."""

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
    raise RuntimeError("[run_vienna_constant_thermflex_sensitivity_analysis] project root not found.")
project_root_str = str(project_root.resolve())
if project_root_str not in sys.path:
    sys.path.insert(0, project_root_str)

from Optimization.run.analysis.build_paper_dispatch_comparison import build_paper_dispatch_comparison
from Optimization.run.analysis.build_constant_thermflex_sensitivity import (
    build_constant_thermflex_sensitivity_bundle,
)
from Optimization.run.analysis.build_constant_thermflex_cohort_utilization import (
    build_constant_thermflex_cohort_utilization_bundle,
)


CASE_SPECS = (
    ("constant_no_thermflex", "vienna_ref2023_dh_baseline_constant_no_thermflex_paper_day_ahead"),
    ("lb21p0_dur1_evt1", "vienna_ref2023_dh_baseline_constant_thermflex_lb21p0_dur1_evt1_paper_day_ahead"),
    ("lb21p0_dur4_evt1", "vienna_ref2023_dh_baseline_constant_thermflex_paper_day_ahead"),
    ("lb21p0_dur2_evt1", "vienna_ref2023_dh_baseline_constant_thermflex_lb21p0_dur2_evt1_paper_day_ahead"),
    ("lb21p0_dur6_evt1", "vienna_ref2023_dh_baseline_constant_thermflex_lb21p0_dur6_evt1_paper_day_ahead"),
    ("lb21p0_dur8_evt1", "vienna_ref2023_dh_baseline_constant_thermflex_lb21p0_dur8_evt1_paper_day_ahead"),
    ("lb21p0_dur24_evt1", "vienna_ref2023_dh_baseline_constant_thermflex_lb21p0_dur24_evt1_paper_day_ahead"),
    ("lb21p0_dur24_evt24", "vienna_ref2023_dh_baseline_constant_thermflex_lb21p0_dur24_evt24_paper_day_ahead"),
    ("lb22p5_dur4_evt1_upper_only", "vienna_ref2023_dh_baseline_constant_thermflex_lb22p5_dur4_evt1_upper_only_paper_day_ahead"),
    ("lb22p5_dur24_evt24_upper_only_proxy", "vienna_ref2023_dh_baseline_constant_thermflex_lb22p5_dur24_evt24_upper_only_proxy_paper_day_ahead"),
    ("lb21p5_dur4_evt1", "vienna_ref2023_dh_baseline_constant_thermflex_lb21p5_dur4_evt1_paper_day_ahead"),
    ("lb20p0_dur4_evt1", "vienna_ref2023_dh_baseline_constant_thermflex_lb20p0_dur4_evt1_paper_day_ahead"),
    ("lb21p0_dur4_evt2", "vienna_ref2023_dh_baseline_constant_thermflex_lb21p0_dur4_evt2_paper_day_ahead"),
)
OVERRIDE_DIR = (
    project_root
    / "Optimization"
    / "validation"
    / "model_validation"
    / "overrides"
    / "thermflex"
)


def _resolve_latest_run_dir(results_root: Path, run_suffix: str) -> Path:
    matches = [p for p in results_root.iterdir() if p.is_dir() and p.name.endswith(run_suffix)]
    if not matches:
        raise FileNotFoundError(
            f"[run_vienna_constant_thermflex_sensitivity_analysis] no run directory found for suffix '{run_suffix}' in {results_root}"
        )
    matches.sort(key=lambda p: p.name, reverse=True)
    selected = matches[0]
    dispatch_path = selected / "dispatch_kpis.json"
    if not dispatch_path.exists():
        raise FileNotFoundError(
            f"[run_vienna_constant_thermflex_sensitivity_analysis] dispatch_kpis.json missing in selected run: {selected}"
        )
    return selected


if __name__ == "__main__":
    results_root = project_root / "Optimization" / "run" / "results" / "Vienna" / "gold"
    if not results_root.exists():
        raise FileNotFoundError(
            f"[run_vienna_constant_thermflex_sensitivity_analysis] results root not found: {results_root}"
        )

    labels: list[str] = []
    run_dirs: list[Path] = []
    resolution_report: list[dict[str, str]] = []
    cohort_case_specs: list[dict[str, str]] = []
    for label, suffix in CASE_SPECS:
        run_dir = _resolve_latest_run_dir(results_root, suffix)
        override_path = OVERRIDE_DIR / f"{suffix}.json"
        if not override_path.exists():
            raise FileNotFoundError(
                f"[run_vienna_constant_thermflex_sensitivity_analysis] override file not found: {override_path}"
            )
        labels.append(label)
        run_dirs.append(run_dir)
        resolution_report.append(
            {
                "label": label,
                "run_dir": str(run_dir),
                "override_path": str(override_path),
            }
        )
        cohort_case_specs.append(
            {
                "label": label,
                "run_dir": str(run_dir),
                "override_path": str(override_path),
            }
        )

    output_dir = build_paper_dispatch_comparison(run_dirs=run_dirs, labels=labels)
    build_constant_thermflex_sensitivity_bundle(output_dir)
    build_constant_thermflex_cohort_utilization_bundle(
        output_dir=output_dir,
        case_specs=cohort_case_specs,
    )
    report_path = output_dir / "selected_runs.json"
    report_path.write_text(json.dumps(resolution_report, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"[run_vienna_constant_thermflex_sensitivity_analysis] output_dir={output_dir}")
