from __future__ import annotations

"""Build one curated DH thermflex run bundle for paper work."""

import json
import shutil
from datetime import datetime
from pathlib import Path

from Optimization.run.analysis.build_energyplus_cohort_day_plots import (
    build_energyplus_cohort_day_plots_bundle,
)
from Optimization.run.analysis.build_nonres_2000_2014_debug import (
    build_nonres_2000_2014_debug_bundle,
)
from Optimization.run.analysis.select_vienna_dh_thermflex_representative_days import (
    build_vienna_dh_thermflex_representative_days_bundle,
)


PROJECT_ROOT = Path(__file__).resolve().parents[3]
GOLD_ROOT = PROJECT_ROOT / "Optimization" / "run" / "results" / "Vienna" / "gold"


def build_dh_thermflex_run_bundle(*, output_dir: Path | None = None) -> Path:
    bundle_dir = Path(output_dir) if output_dir is not None else _default_output_dir()
    bundle_dir = bundle_dir.resolve()
    bundle_dir.mkdir(parents=True, exist_ok=True)

    latest_comparison_dir = _resolve_latest_directory(
        GOLD_ROOT,
        prefix="paper_dispatch_comparison_",
    )
    paper_core_dir = bundle_dir / "paper_core"
    paper_core_dir.mkdir(parents=True, exist_ok=True)
    copied_paper_artifacts = _copy_core_artifacts(paper_core_dir)

    nonres_dir = build_nonres_2000_2014_debug_bundle(bundle_dir / "nonres_2000_2014_debug")
    representative_dir = build_vienna_dh_thermflex_representative_days_bundle(
        bundle_dir / "representative_days"
    )
    teacher_dir = build_energyplus_cohort_day_plots_bundle(bundle_dir / "teacher_day_plots")

    manifest = {
        "bundle_dir": str(bundle_dir),
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "source_comparison_dir": str(latest_comparison_dir),
        "paper_core_artifacts": copied_paper_artifacts,
        "subdirs": {
            "nonres_2000_2014_debug": str(nonres_dir),
            "representative_days": str(representative_dir),
            "teacher_day_plots": str(teacher_dir),
        },
        "notes": [
            "This bundle curates the current DH thermflex paper path.",
            "The source comparison directory stays the official source of truth for the already solved gold runs.",
            "The bundle adds explicit diagnosis, representative-day selection, and cohort-day plot artifacts on top.",
        ],
    }
    (bundle_dir / "manifest.json").write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    _write_bundle_readme(bundle_dir=bundle_dir, manifest=manifest)
    return bundle_dir


def _default_output_dir() -> Path:
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    return GOLD_ROOT / f"dh_thermflex_run_{stamp}"


def _resolve_latest_directory(root: Path, *, prefix: str) -> Path:
    if not root.exists():
        raise FileNotFoundError(f"[dh_thermflex_bundle] Gold root not found: {root}")
    matches = [path for path in root.iterdir() if path.is_dir() and path.name.startswith(prefix)]
    if not matches:
        raise FileNotFoundError(
            f"[dh_thermflex_bundle] No directory found with prefix '{prefix}' in {root}."
        )
    matches.sort(key=lambda path: path.name, reverse=True)
    selected = matches[0]
    required = selected / "paper_dispatch_comparison.csv"
    if not required.exists():
        raise FileNotFoundError(
            f"[dh_thermflex_bundle] Required comparison csv missing in selected dir: {required}"
        )
    return selected


def _resolve_latest_comparison_artifact(filename: str) -> Path:
    matches: list[Path] = []
    for path in GOLD_ROOT.iterdir():
        if not path.is_dir() or not path.name.startswith("paper_dispatch_comparison_"):
            continue
        candidate = path / filename
        if candidate.exists():
            matches.append(candidate)
    if not matches:
        raise FileNotFoundError(
            f"[dh_thermflex_bundle] No comparison artifact found for '{filename}' in {GOLD_ROOT}."
        )
    matches.sort(key=lambda candidate: candidate.parent.name, reverse=True)
    return matches[0]


def _copy_core_artifacts(target_dir: Path) -> list[str]:
    copied: list[str] = []
    expected_files = [
        "paper_dispatch_comparison.csv",
        "paper_dispatch_comparison.json",
        "paper_dispatch_comparison.md",
        "paper_dispatch_comparison.png",
        "constant_thermflex_sensitivity_summary.json",
        "constant_thermflex_sensitivity_summary.md",
        "constant_thermflex_sensitivity.png",
        "constant_thermflex_cohort_utilization_summary.csv",
        "constant_thermflex_cohort_utilization_summary.json",
        "constant_thermflex_cohort_utilization_summary.md",
        "constant_thermflex_cohort_utilization.png",
        "constant_thermflex_timeseries.png",
        "constant_thermflex_timeseries_settings.md",
        "constant_thermflex_isolation.png",
        "constant_thermflex_isolation_summary.json",
        "constant_thermflex_isolation_summary.md",
        "selected_runs.json",
    ]
    for filename in expected_files:
        source = _resolve_latest_comparison_artifact(filename)
        target = target_dir / filename
        shutil.copy2(source, target)
        copied.append(str(target))
    return copied


def _write_bundle_readme(*, bundle_dir: Path, manifest: dict[str, object]) -> None:
    lines = [
        "# DH Thermflex Run Bundle",
        "",
        "This bundle curates the current Vienna DH thermflex paper path.",
        "",
        "## Contains",
        "",
        "- `paper_core/`",
        "  Copied paper comparison and constant thermflex sensitivity artifacts from the latest official comparison directory.",
        "- `nonres_2000_2014_debug/`",
        "  Explicit diagnosis of the suspicious zero-load day for `non_residential_2000_2014`.",
        "- `representative_days/`",
        "  Daily 2023 feature table plus explicit representative-day selection.",
        "- `teacher_day_plots/`",
        "  Cohort/day EnergyPlus teacher plots for reference and cutback event views.",
        "",
        "## Source",
        "",
        f"- Official comparison source dir: `{manifest['source_comparison_dir']}`",
        "",
        "## Why this exists",
        "",
        "- keep the DH thermflex paper path discoverable in one folder",
        "- show which artifacts already exist and are worth reusing",
        "- avoid hunting through many timestamped gold directories",
        "",
    ]
    (bundle_dir / "README.md").write_text("\n".join(lines), encoding="utf-8")
