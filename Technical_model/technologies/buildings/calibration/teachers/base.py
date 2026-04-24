from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class TeacherSmokeResult:
    teacher: str
    epw_path: Path
    workdir: Path
    command: tuple[str, ...]
    stdout_path: Path
    stderr_path: Path
    err_path: Path


@dataclass(frozen=True)
class TeacherExperimentResult:
    teacher: str
    cohort_id: str
    experiment_id: str
    epw_path: Path
    workdir: Path
    command: tuple[str, ...]
    stdout_path: Path
    stderr_path: Path
    err_path: Path
    hourly_csv_path: Path
    meta_path: Path
    plausibility_hourly_csv_path: Path | None = None
    plausibility_summary_path: Path | None = None
    plausibility_plot_path: Path | None = None
