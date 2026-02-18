from __future__ import annotations
from dataclasses import dataclass
from typing import Optional

@dataclass
class ReportingConfig:
    auto_report: bool = True
    write_csv: bool = True
    write_plot: bool = True
    write_summary: bool = True
    plot_max_points: Optional[int] = None
    output_root: str = "Optimization/run/results"


def make_reporting() -> ReportingConfig:
    return ReportingConfig(
        auto_report=True,
        write_csv=True,
        write_plot=True,
        write_summary=True,
        plot_max_points=None,
        output_root="Optimization/run/results",
    )
