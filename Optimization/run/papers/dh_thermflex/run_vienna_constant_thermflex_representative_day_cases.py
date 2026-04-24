from __future__ import annotations

"""Run the explicit constant thermflex sensitivity block on representative days."""

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
    raise RuntimeError("[run_vienna_constant_thermflex_representative_day_cases] project root not found.")
project_root_str = str(project_root.resolve())
if project_root_str not in sys.path:
    sys.path.insert(0, project_root_str)

from Settings import get_settings  # noqa: E402
from Optimization.framework.Orchestrator.optimize import run  # noqa: E402
from Optimization.run.analysis.build_constant_thermflex_representative_day_summary import (  # noqa: E402
    build_constant_thermflex_representative_day_summary,
)


OVERRIDE_DIR = (
    project_root
    / "Optimization"
    / "validation"
    / "model_validation"
    / "overrides"
    / "thermflex"
)
GOLD_ROOT = project_root / "Optimization" / "run" / "results" / "Vienna" / "gold"
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


def _resolve_latest_representative_day_json() -> Path:
    matches = []
    for path in GOLD_ROOT.iterdir():
        if not path.is_dir() or not path.name.startswith("dh_thermflex_run_"):
            continue
        candidate = path / "representative_days" / "representative_days.json"
        if candidate.exists():
            matches.append(candidate)
    if not matches:
        raise FileNotFoundError(
            f"[run_vienna_constant_thermflex_representative_day_cases] No representative_days.json found in {GOLD_ROOT}"
        )
    matches.sort(key=lambda path: path.parent.parent.name, reverse=True)
    return matches[0]


def _load_overrides(path: Path) -> dict:
    if not path.exists():
        raise FileNotFoundError(
            f"[run_vienna_constant_thermflex_representative_day_cases] overrides file not found: {path}"
        )
    return json.loads(path.read_text(encoding="utf-8-sig"))


def _day_slug(label: str, date_str: str) -> str:
    prefix_map = {
        "winter_peak_heat_day": "peak",
        "winter_price_spike_day": "price",
        "winter_sunny_heat_day": "sunny",
        "winter_typical_day": "wintertyp",
        "shoulder_typical_day": "shouldertyp",
    }
    prefix = prefix_map.get(label, label.replace("_", ""))
    return f"{prefix}_{date_str.replace('-', '')}"


def _resolve_existing_run_dir(tag: str) -> Path | None:
    matches = [path for path in GOLD_ROOT.iterdir() if path.is_dir() and path.name.endswith(tag)]
    if not matches:
        return None
    matches.sort(key=lambda path: path.name, reverse=True)
    candidate = matches[0]
    if not (candidate / "dispatch_kpis.json").exists():
        return None
    return candidate


def _load_dispatch_point(dispatch_kpis_path: Path) -> dict:
    payload = json.loads(dispatch_kpis_path.read_text(encoding="utf-8"))
    points = payload.get("points")
    if not isinstance(points, list) or not points:
        raise ValueError(
            f"[run_vienna_constant_thermflex_representative_day_cases] dispatch_kpis points missing in {dispatch_kpis_path}."
        )
    point = points[0]
    if not isinstance(point, dict):
        raise TypeError(
            f"[run_vienna_constant_thermflex_representative_day_cases] dispatch_kpis first point invalid in {dispatch_kpis_path}."
        )
    return point


if __name__ == "__main__":
    representative_path = _resolve_latest_representative_day_json()
    representative_payload = json.loads(representative_path.read_text(encoding="utf-8"))
    selected_days = representative_payload.get("selected_days", [])
    if not selected_days:
        raise ValueError(
            f"[run_vienna_constant_thermflex_representative_day_cases] No selected days found in {representative_path}."
        )

    run_rows: list[dict[str, object]] = []
    for day in selected_days:
        day_label = str(day["label"])
        day_date = str(day["date"])
        slug = _day_slug(day_label, day_date)
        for case_label, suffix in CASE_SPECS:
            override_path = OVERRIDE_DIR / f"{suffix}.json"
            overrides = _load_overrides(override_path)
            overrides["run"]["profile_start"] = f"{day_date} 00:00:00"
            overrides["run"]["profile_hours"] = 24
            overrides["run"]["tag"] = f"{suffix}_{slug}"
            tag = str(overrides["run"]["tag"])

            t0 = time.perf_counter()
            existing_run_dir = _resolve_existing_run_dir(tag)
            if existing_run_dir is not None:
                run_dir = existing_run_dir
                walltime_s = 0.0
            else:
                settings = get_settings(overrides=overrides)
                result = run(settings)
                walltime_s = float(time.perf_counter() - t0)
                run_dir = Path(str(result.get("run_dir"))).resolve()
            dispatch_kpis_path = run_dir / "dispatch_kpis.json"
            if not dispatch_kpis_path.exists():
                raise FileNotFoundError(
                    f"[run_vienna_constant_thermflex_representative_day_cases] dispatch_kpis.json missing: {dispatch_kpis_path}"
                )
            dispatch_kpis = _load_dispatch_point(dispatch_kpis_path)
            run_rows.append(
                {
                    "day_label": day_label,
                    "date": day_date,
                    "case_label": case_label,
                    "run_suffix": suffix,
                    "run_dir": str(run_dir),
                    "walltime_s": walltime_s,
                    "dispatch_operating_cost_eur": float(dispatch_kpis["dispatch_operating_cost_eur"]),
                    "co2_emissions_total_t": float(dispatch_kpis["co2_emissions_total_t"]),
                    "dh_unserved_heat_kwh": float(dispatch_kpis["dh_unserved_heat_kwh"]),
                    "thermflex_shifted_space_heat_kwh": float(dispatch_kpis["thermflex_shifted_space_heat_kwh"]),
                    "thermflex_rebound_kwh": float(dispatch_kpis["thermflex_rebound_kwh"]),
                    "thermflex_peak_change_kw": float(dispatch_kpis["thermflex_peak_change_kw"]),
                }
            )
            print(
                f"[run_vienna_constant_thermflex_representative_day_cases] {day_label} | {case_label} -> {run_dir}",
                flush=True,
            )

    latest_run_dir = Path(str(run_rows[-1]["run_dir"])).resolve()
    output_dir = latest_run_dir.parent / f"constant_thermflex_representative_day_summary_{latest_run_dir.name.split('_')[0]}"
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "selected_representative_days.json").write_text(
        json.dumps(selected_days, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    build_constant_thermflex_representative_day_summary(
        output_dir=output_dir,
        run_rows=run_rows,
    )
    (output_dir / "run_manifest.json").write_text(
        json.dumps(run_rows, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    print(f"[run_vienna_constant_thermflex_representative_day_cases] output_dir={output_dir}", flush=True)
